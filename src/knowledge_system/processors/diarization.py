import subprocess
import warnings
from collections.abc import Callable
from pathlib import Path
from typing import Any

from knowledge_system.logger import get_logger
from knowledge_system.processors.base import BaseProcessor, ProcessorResult
from knowledge_system.utils.model_cache import cache_diarization_model
from knowledge_system.utils.validation import validate_audio_input

logger = get_logger(__name__)

# Suppress ML library warnings for diarization processing
try:
    from ..utils.warning_suppressions import suppress_ml_library_warnings

    suppress_ml_library_warnings()
except ImportError:
    # Fallback warning suppression for PyAnnote/TorchAudio
    warnings.filterwarnings(
        "ignore", category=UserWarning, module="torchaudio._backend.utils"
    )
    warnings.filterwarnings(
        "ignore", category=UserWarning, module="pyannote.audio.models.blocks.pooling"
    )
    warnings.filterwarnings(
        "ignore", message=".*std\\(\\): degrees of freedom.*", category=UserWarning
    )

# Lazy loading of diarization dependencies
PIPELINE_AVAILABLE = False
PIPELINE = None


def _check_diarization_dependencies() -> bool:
    """Check if diarization dependencies are available."""
    global PIPELINE_AVAILABLE, PIPELINE

    if PIPELINE_AVAILABLE:
        return True

    # CRITICAL: We cannot import pyannote.audio here because it imports torchcodec
    # which segfaults with PyTorch 2.8.0. Instead, we check for the dependencies
    # and defer the actual import until the pipeline is needed.
    try:
        # Check for core dependencies without importing pyannote.audio
        import torch  # noqa: F401
        import torchaudio  # noqa: F401
        import transformers  # noqa: F401

        # Mark as available but don't load Pipeline yet
        PIPELINE_AVAILABLE = True
        PIPELINE = None  # Will be loaded lazily
        logger.info("Diarization dependencies available (deferred loading)")
        return True
    except ImportError as e:
        PIPELINE_AVAILABLE = False
        PIPELINE = None
        logger.warning(
            f"Diarization dependencies not available: {e}. "
            "Install with: pip install -e '.[diarization]' or pip install torch transformers pyannote.audio"
        )
        return False
    except Exception as e:
        PIPELINE_AVAILABLE = False
        PIPELINE = None
        logger.error(f"Error checking diarization dependencies: {e}")
        return False


class SpeakerDiarizationProcessor(BaseProcessor):
    """Performs speaker diarization using pyannote.audio with lazy loading."""

    def __init__(
        self,
        model: str = "pyannote/speaker-diarization-3.1",
        device: str | None = None,
        hf_token: str | None = None,
        progress_callback: Callable[[str, int], None] | None = None,
        sensitivity: str = "conservative",
    ) -> None:
        self.model = model

        # Allow MPS to be used - we'll identify and fix specific failures
        # Resolve "auto" to actual device
        if device == "auto" or device is None:
            self.device = self._detect_best_device()
        else:
            self.device = device

        self.hf_token = hf_token
        self.progress_callback = progress_callback
        self.sensitivity = sensitivity
        self._pipeline = None
        self._dependencies_checked = False
        self._mps_operations_status = {}  # Track which operations work on MPS

        logger.info(
            f"Diarization processor initialized with device: {self.device}, sensitivity: {sensitivity}"
        )

        # Set no-fallback mode for MPS to catch issues early
        if self.device == "mps":
            import os

            os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "0"
            logger.info(
                "MPS no-fallback mode enabled - will fail fast on unsupported operations"
            )

        # Track which operations need CPU fallback
        self._cpu_fallback_ops = set()  # Will be populated as we discover failing ops

    def _detect_best_device(self) -> str:
        """Detect the best available device for diarization."""
        try:
            import torch

            if torch.cuda.is_available():
                logger.info("CUDA detected for diarization")
                return "cuda"
            elif torch.backends.mps.is_available() and torch.backends.mps.is_built():
                logger.info("Apple Silicon MPS detected for diarization")
                return "mps"  # Use MPS - we'll handle specific failures
            else:
                logger.info("No GPU acceleration available, using CPU for diarization")
                return "cpu"
        except ImportError:
            logger.warning("PyTorch not available, using CPU for diarization")
            return "cpu"
        except Exception as e:
            logger.warning(f"Error detecting device, using CPU for diarization: {e}")
            return "cpu"

    @property
    def supported_formats(self) -> list:
        """Audio formats supported by pyannote.audio for diarization."""
        return [".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac", ".mp4", ".webm"]

    def _check_dependencies(self) -> bool:
        """Check if diarization dependencies are available."""
        if not self._dependencies_checked:
            self._dependencies_checked = True
            return _check_diarization_dependencies()
        return PIPELINE_AVAILABLE

    def _load_pipeline(self) -> None:
        """Lazy load the diarization pipeline."""
        import sys

        print(
            f"\n[DIARIZATION DEBUG] _load_pipeline called, device={self.device}",
            flush=True,
        )
        print(
            f"[DIARIZATION DEBUG] Pipeline status: {self._pipeline is not None}",
            flush=True,
        )
        sys.stdout.flush()

        if not self._check_dependencies():
            raise ImportError(
                "Diarization dependencies not available. "
                "Install with: pip install -e '.[diarization]' or pip install torch transformers pyannote.audio"
            )

        if self._pipeline is None:
            print(
                "[DIARIZATION DEBUG] Pipeline is None, starting load process...",
                flush=True,
            )
            sys.stdout.flush()
            import os

            # Check for bundled model first (in DMG distributions for internal use)
            bundled_model_path = None
            if os.environ.get("PYANNOTE_BUNDLED") == "true":
                bundled_base = os.environ.get("PYANNOTE_MODEL_PATH")
                if bundled_base:
                    bundled_model_path = Path(bundled_base) / "speaker-diarization-3.1"
                    if bundled_model_path.exists():
                        logger.info(
                            f"Found bundled diarization model at: {bundled_model_path}"
                        )
                        if self.progress_callback:
                            self.progress_callback(
                                "Loading bundled diarization model...", 20
                            )

            # If no bundled model, check both HuggingFace and pyannote caches
            cached_models = []
            if not bundled_model_path or not bundled_model_path.exists():
                # Check both possible cache locations
                hf_cache = Path.home() / ".cache" / "huggingface" / "hub"
                pyannote_cache = Path.home() / ".cache" / "torch" / "pyannote"
                model_id = self.model.replace("/", "--")

                # Check HuggingFace cache first
                if hf_cache.exists():
                    cached_models = list(hf_cache.glob(f"models--{model_id}*"))

                # Also check pyannote torch cache (where it actually stores models)
                if not cached_models and pyannote_cache.exists():
                    cached_models = list(pyannote_cache.glob(f"models--{model_id}*"))

            if cached_models:
                logger.info(f"Found cached diarization model: {self.model}")
                if self.progress_callback:
                    self.progress_callback("Loading cached diarization model...", 20)
                # Force offline mode to prevent network checks
                os.environ["HF_HUB_OFFLINE"] = "1"
                logger.info("Enabled offline mode for cached model loading")
            else:
                logger.warning(
                    f"Diarization model {self.model} not cached. "
                    "First run will download ~400MB from HuggingFace. "
                    "This may take several minutes depending on connection speed."
                )
                if self.progress_callback:
                    self.progress_callback(
                        "⏬ Downloading diarization model (first time only, ~400MB)...",
                        20,
                    )

            # Use cached model loading with timeout
            def pipeline_loader():
                logger.info("Pipeline loader started...")

                # Save original offline mode state
                original_offline = os.environ.get("HF_HUB_OFFLINE", "0")

                # If we have a bundled model, use it directly
                if bundled_model_path and bundled_model_path.exists():
                    try:
                        logger.info(f"Loading bundled model from: {bundled_model_path}")
                        # Load from bundled path without authentication
                        # Import pyannote.audio here to avoid torchcodec segfault on startup
                        from pyannote.audio import Pipeline as PyannoteP

                        if PyannoteP:
                            pipeline = PyannoteP.from_pretrained(
                                str(bundled_model_path)
                            )
                            logger.info("Bundled model loaded successfully")
                            return pipeline
                    except Exception as e:
                        logger.warning(f"Failed to load bundled model: {e}")
                        # Fall back to normal loading

                logger.info(f"Loading pyannote.audio pipeline: {self.model}")
                if self.progress_callback and not cached_models:
                    self.progress_callback(
                        f"⏬ Downloading {self.model} from HuggingFace (this may take a while)...",
                        40,
                    )

                # Set HuggingFace token as environment variable for better compatibility
                # This works around authentication issues in pyannote.audio 3.x
                if self.hf_token:
                    os.environ["HF_TOKEN"] = self.hf_token
                    os.environ["HUGGINGFACE_HUB_TOKEN"] = self.hf_token
                    logger.info(
                        "Set HuggingFace environment variables for authentication"
                    )

                try:
                    # Set comprehensive offline mode for cached models
                    if cached_models:
                        logger.info(
                            "Model is cached, setting comprehensive offline mode"
                        )
                        os.environ["HF_HUB_OFFLINE"] = "1"
                        os.environ["TRANSFORMERS_OFFLINE"] = "1"
                        os.environ["HF_DATASETS_OFFLINE"] = "1"
                    else:
                        logger.info("Model not cached, will download if needed")

                    logger.info(
                        f"Calling pyannote.audio Pipeline.from_pretrained for {self.model}..."
                    )
                    logger.debug(f"HuggingFace token present: {bool(self.hf_token)}")
                    logger.debug(
                        f"HF_HUB_OFFLINE: {os.environ.get('HF_HUB_OFFLINE', 'not set')}"
                    )

                    # Note: pyannote Pipeline doesn't support local_files_only parameter
                    try:
                        # Import pyannote.audio here to avoid torchcodec segfault on startup
                        from pyannote.audio import Pipeline as PyannoteP

                        # Use token parameter (replaces deprecated use_auth_token in pyannote.audio 4.0+)
                        pipeline = PyannoteP.from_pretrained(
                            self.model, token=self.hf_token  # type: ignore[call-arg]
                        )
                        logger.info(f"Successfully loaded pipeline for {self.model}")
                    except Exception as model_error:
                        logger.error(
                            f"Failed to load model {self.model}: {model_error}"
                        )
                        # Re-raise with more context
                        raise Exception(
                            f"Model loading failed for {self.model}: {model_error}"
                        ) from model_error

                    # Optimize clustering for CPU/MPS performance
                    if self.device in ["cpu", "mps"]:
                        logger.info(
                            f"Optimizing diarization parameters for {self.device} with {self.sensitivity} sensitivity..."
                        )

                        # Configure parameters based on sensitivity level
                        # Initialize variables that will be used across different pipeline components
                        if self.sensitivity == "aggressive":
                            threshold = 0.55  # Even lower threshold for maximum speaker detection
                            min_duration_on = 0.25
                            min_cluster_size = 8
                        elif self.sensitivity == "balanced":
                            threshold = (
                                0.65  # Reduced from 0.7 for better speaker separation
                            )
                            min_duration_on = (
                                0.4  # Reduced from 0.5 for quicker exchanges
                            )
                            min_cluster_size = 12  # Reduced from 15
                        else:  # conservative - now relies on voice fingerprinting for quality
                            threshold = 0.75  # Reasonable threshold - voice fingerprinting will merge false splits
                            min_duration_on = 1.0  # Normal segments - voice fingerprinting will handle micro-segments
                            min_cluster_size = 20  # Moderate setting - let voice fingerprinting handle the rest

                        # Use centroid clustering - works on both CPU and MPS
                        # Avoid spectral clustering which fails on MPS due to eigenvalue decomposition
                        if hasattr(pipeline, "clustering"):
                            pipeline.clustering.method = (
                                "centroid"  # Works on MPS, faster than spectral
                            )
                            pipeline.clustering.min_cluster_size = min_cluster_size

                            # Apply threshold if supported
                            if hasattr(pipeline.clustering, "threshold"):
                                pipeline.clustering.threshold = threshold

                            logger.info(
                                f"Applied {self.sensitivity} clustering: min_cluster_size={pipeline.clustering.min_cluster_size}, threshold={threshold}"
                            )

                        if hasattr(pipeline, "segmentation"):
                            pipeline.segmentation.min_duration_on = min_duration_on

                            # Optimize silence detection based on sensitivity
                            if self.sensitivity == "aggressive":
                                pipeline.segmentation.min_duration_off = (
                                    0.2  # Very short silence detection
                                )
                            elif self.sensitivity == "balanced":
                                pipeline.segmentation.min_duration_off = (
                                    0.3  # Optimized for interview turn-taking
                                )
                            else:  # conservative
                                pipeline.segmentation.min_duration_off = (
                                    0.5  # Longer silence required
                                )
                    logger.info("PyannoteP.from_pretrained completed successfully")
                except Exception as e:
                    # Provide more helpful error message
                    if "401" in str(e) or "authorization" in str(e).lower():
                        raise RuntimeError(
                            f"HuggingFace authentication failed for {self.model}. "
                            "Please check:\n"
                            "1. Your HuggingFace token is set in settings\n"
                            "2. You have accepted the model license at https://huggingface.co/pyannote/speaker-diarization\n"
                            "3. Your token has 'read' permissions"
                        )
                    else:
                        raise
                finally:
                    # Restore original offline mode after model loading attempt
                    if cached_models and original_offline == "0":
                        logger.info("Restoring original offline mode settings")
                        os.environ.pop("HF_HUB_OFFLINE", None)
                        os.environ.pop("TRANSFORMERS_OFFLINE", None)
                        os.environ.pop("HF_DATASETS_OFFLINE", None)

                # Check if pipeline loaded successfully
                if pipeline is None:
                    raise RuntimeError(
                        f"Failed to load diarization pipeline '{self.model}'. "
                        "This usually means:\n"
                        "1. HuggingFace token authentication failed\n"
                        "2. Model license not accepted at https://huggingface.co/pyannote/speaker-diarization\n"
                        "3. Network connectivity issues\n"
                        "Please check your HuggingFace token and model access permissions."
                    )

                if self.progress_callback:
                    self.progress_callback(
                        "Diarization model loaded, configuring device...", 60
                    )

                # Move pipeline to GPU if available
                logger.info(f"Pipeline loaded, current device setting: {self.device}")

                # Skip GPU logic entirely if we're using CPU
                if self.device == "cpu":
                    logger.info("Using CPU for diarization, skipping GPU transfer")
                    return pipeline

                if self.device and self.device != "cpu":
                    try:
                        import sys

                        import torch

                        logger.info(f"Checking if {self.device} is available...")

                        # Check if requested device is available
                        if (
                            self.device.startswith("cuda")
                            and not torch.cuda.is_available()
                        ):
                            logger.warning(
                                "CUDA requested but not available. Using CPU instead."
                            )
                            self.device = "cpu"
                        elif (
                            self.device == "mps"
                            and not torch.backends.mps.is_available()
                        ):
                            logger.warning(
                                "MPS (Apple Silicon) requested but not available. Using CPU instead."
                            )
                            self.device = "cpu"

                        # Only try to move if we still have a non-CPU device
                        if self.device != "cpu":
                            logger.info(
                                f"Moving diarization pipeline to device: {self.device}"
                            )
                            print(
                                f"\n[DIARIZATION 80%] About to report 80% progress",
                                flush=True,
                            )
                            sys.stdout.flush()

                            if self.progress_callback:
                                self.progress_callback(
                                    f"Moving model to {self.device}...", 80
                                )

                            print(
                                f"[DIARIZATION 80%] CRITICAL - Reached 80%, device={self.device}",
                                flush=True,
                            )
                            print(
                                f"[DIARIZATION 80%] Pipeline type: {type(pipeline)}",
                                flush=True,
                            )
                            print(
                                f"[DIARIZATION 80%] Device requested: {self.device}",
                                flush=True,
                            )
                        sys.stdout.flush()

                        logger.debug(f"Preparing to move pipeline to {self.device}")
                        logger.debug(f"Pipeline type: {type(pipeline)}")
                        logger.debug(f"Device requested: {self.device}")

                        # Convert device string to torch.device object
                        torch_device = torch.device(self.device)

                        # Add timeout for GPU transfer
                        logger.info("Starting GPU transfer...")
                        import concurrent.futures

                        def move_to_device():
                            logger.info(
                                f"Inside move_to_device, calling pipeline.to({torch_device})"
                            )
                            return pipeline.to(torch_device)

                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(move_to_device)
                            try:
                                pipeline = future.result(
                                    timeout=30
                                )  # 30 second timeout
                                logger.info(
                                    f"Diarization pipeline successfully moved to {self.device}"
                                )
                            except concurrent.futures.TimeoutError:
                                logger.error(
                                    f"GPU transfer timed out after 30 seconds. Falling back to CPU."
                                )
                                self.device = "cpu"
                                # Pipeline stays on CPU
                            except Exception as e:
                                logger.error(
                                    f"Failed to move model to {self.device}: {e}. Using CPU instead."
                                )
                                self.device = "cpu"
                                # Pipeline stays on CPU
                    except Exception as e:
                        logger.warning(
                            f"Failed to move pipeline to {self.device}, falling back to CPU: {e}"
                        )
                        if self.progress_callback:
                            self.progress_callback(
                                "Using CPU for diarization (GPU failed)", 80
                            )

                return pipeline

            # Get cached pipeline with timeout
            import concurrent.futures

            logger.info(f"Submitting pipeline to cache with device={self.device}")

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    cache_diarization_model,
                    model_name=self.model,
                    device=self.device,
                    loader_func=pipeline_loader,
                    hf_token=self.hf_token,
                )
                try:
                    logger.info("Waiting for pipeline to load (max 2 minutes)...")
                    # 2 minute timeout for model loading/downloading
                    self._pipeline = future.result(timeout=120)
                    logger.info("Pipeline loaded successfully from cache!")
                except concurrent.futures.TimeoutError:
                    raise RuntimeError(
                        "Diarization model loading timed out after 2 minutes. "
                        "This may be due to slow network connection or large model download. "
                        "Please check your internet connection and try again."
                    )

            if self.progress_callback:
                self.progress_callback("Diarization pipeline ready!", 100)
            logger.info("pyannote.audio pipeline ready (cached or newly loaded)")

    def validate_input(self, input_data: str | Path) -> bool:
        return validate_audio_input(input_data)

    def can_process(self, input_path: str | Path) -> bool:
        return self.validate_input(input_path)

    def process(
        self, input_data: Any, dry_run: bool = False, **kwargs: Any
    ) -> ProcessorResult:
        # SECURITY CHECK: Verify app authorization before diarization
        try:
            from knowledge_system.utils.security_verification import (
                ensure_secure_before_transcription,
            )

            ensure_secure_before_transcription()
        except ImportError:
            logger.warning(
                "Security verification module not available - proceeding with diarization"
            )
        except Exception as e:
            logger.error(f"Security verification failed: {e}")
            return ProcessorResult(
                success=False,
                errors=[
                    f"App not properly authorized for diarization: {e}. Please restart the app and complete the authorization process."
                ],
                dry_run=dry_run,
            )

        # Extract parameters from kwargs for backwards compatibility
        kwargs.get("device", None)

        # Handle input_data as input_path for backwards compatibility
        input_path = str(input_data)

        # Check dependencies first
        if not self._check_dependencies():
            return ProcessorResult(
                success=False,
                errors=[
                    "Diarization dependencies not available. "
                    "Install with: pip install -e '.[diarization]' or pip install torch transformers pyannote.audio"
                ],
                dry_run=dry_run,
            )

        path = Path(input_path)
        if not path.exists() or not path.is_file():
            return ProcessorResult(
                success=False, errors=[f"File not found: {input_path}"]
            )

        try:
            self._load_pipeline()
            if self._pipeline is None:
                return ProcessorResult(
                    success=False,
                    errors=["Failed to load diarization pipeline"],
                    dry_run=dry_run,
                )

            # Get file info for better logging context
            filename = Path(path).name
            try:
                file_size_mb = Path(path).stat().st_size / (1024 * 1024)
                file_info = f"({file_size_mb:.1f}MB)"
            except Exception:
                file_info = ""

            # Report start of actual diarization processing
            if self.progress_callback:
                self.progress_callback(
                    f"🎙️ Starting speaker analysis for {filename} {file_info}...", 0
                )

            logger.info(
                f"✅ Starting diarization processing for '{filename}' {file_info}"
            )

            # Create ETA calculator for progress tracking
            import time

            from ..utils.eta_calculator import ETACalculator

            start_time = time.time()
            eta_calc = ETACalculator() if self.progress_callback else None
            if eta_calc:
                eta_calc.start()

            # Estimate audio duration for better progress tracking
            try:
                duration_cmd = [
                    "ffprobe",
                    "-v",
                    "quiet",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "csv=p=0",
                    str(path),
                ]
                result = subprocess.run(
                    duration_cmd, capture_output=True, text=True, timeout=5
                )
                audio_duration = (
                    float(result.stdout.strip())
                    if result.returncode == 0 and result.stdout.strip()
                    else None
                )
            except (subprocess.SubprocessError, ValueError, OSError):
                audio_duration = None

            # Add progress monitoring during diarization
            import threading

            progress_stop_event = None

            if self.progress_callback:

                def progress_monitor(stop_event):
                    time.time()
                    while not stop_event.is_set():
                        elapsed = time.time() - start_time

                        # Dynamic progress estimation based on elapsed time
                        # Use exponential progress curve that approaches but never exceeds 80%
                        # This leaves room for segment processing (80-100%)
                        max_analysis_progress = 80.0

                        # Adaptive estimation - starts slow, accelerates, then slows as it approaches completion
                        if elapsed < 5:
                            progress_percent = min(10, elapsed * 2)
                            phase = "initializing models"
                        elif elapsed < 15:
                            progress_percent = min(25, 10 + (elapsed - 5) * 1.5)
                            phase = "detecting speech segments"
                        elif elapsed < 30:
                            progress_percent = min(50, 25 + (elapsed - 15) * 1.67)
                            phase = "extracting speaker embeddings"
                        else:
                            # Asymptotic approach to max_analysis_progress
                            progress_factor = 1 - (1 / (1 + (elapsed - 30) / 20))
                            progress_percent = min(
                                max_analysis_progress,
                                50 + (max_analysis_progress - 50) * progress_factor,
                            )
                            phase = "clustering speakers"

                        # Calculate ETA using the ETACalculator
                        eta_str = ""
                        if eta_calc:
                            eta_text, eta_seconds = eta_calc.update(progress_percent)
                            if eta_text:
                                eta_str = f", ETA: {eta_text}"

                        if self.progress_callback:
                            # Add file context and more detailed progress info
                            duration_info = ""
                            if audio_duration:
                                duration_info = f" | {audio_duration/60:.1f}min audio"

                            self.progress_callback(
                                f"🎙️ {filename}: {phase}... ({elapsed:.1f}s elapsed{eta_str}{duration_info})",
                                int(progress_percent),
                            )

                        # Check for stop event more frequently
                        if stop_event.wait(
                            timeout=3
                        ):  # 3 second timeout for smoother updates
                            break

                progress_stop_event = threading.Event()
                progress_thread = threading.Thread(
                    target=progress_monitor, args=(progress_stop_event,), daemon=True
                )
                progress_thread.start()

            # Run pipeline with better error handling
            try:
                # Add timeout for pipeline execution to prevent indefinite hangs
                import concurrent.futures

                print(
                    f"\n[DIARIZATION EXECUTION] About to run pipeline on: {path}",
                    flush=True,
                )
                print(
                    f"[DIARIZATION EXECUTION] Pipeline type: {type(self._pipeline)}",
                    flush=True,
                )
                print(f"[DIARIZATION EXECUTION] Device: {self.device}", flush=True)

                # Check if pipeline has device attribute
                if hasattr(self._pipeline, "device"):
                    print(
                        f"[DIARIZATION EXECUTION] Pipeline internal device: {self._pipeline.device}",
                        flush=True,
                    )
                if hasattr(self._pipeline, "_models"):
                    print(
                        f"[DIARIZATION EXECUTION] Pipeline has models: {list(self._pipeline._models.keys()) if hasattr(self._pipeline._models, 'keys') else 'unknown'}",
                        flush=True,
                    )

                import sys

                sys.stdout.flush()

                # Move pipeline components to target device with debugging
                if self.device in ["mps", "cuda"]:
                    try:
                        print(
                            f"[DIARIZATION EXECUTION] Setting pipeline components to {self.device}...",
                            flush=True,
                        )
                        import torch

                        target_device = torch.device(self.device)

                        # Track which components successfully move to MPS/CUDA
                        components_moved = []
                        components_failed = []

                        # Try moving segmentation model
                        if hasattr(self._pipeline, "_segmentation") and hasattr(
                            self._pipeline._segmentation, "model"
                        ):
                            try:
                                print(
                                    f"[DIARIZATION EXECUTION] Moving segmentation model to {self.device}...",
                                    flush=True,
                                )
                                self._pipeline._segmentation.model = (
                                    self._pipeline._segmentation.model.to(target_device)
                                )
                                components_moved.append("segmentation")
                                print(
                                    f"[DIARIZATION EXECUTION] ✅ Segmentation model moved to {self.device}",
                                    flush=True,
                                )
                            except Exception as e:
                                print(
                                    f"[DIARIZATION EXECUTION] ❌ Segmentation failed on {self.device}: {e}",
                                    flush=True,
                                )
                                components_failed.append(("segmentation", str(e)))
                                # Move to CPU as fallback
                                self._pipeline._segmentation.model = (
                                    self._pipeline._segmentation.model.to(
                                        torch.device("cpu")
                                    )
                                )
                                self._cpu_fallback_ops.add("segmentation")

                        # Try moving embedding model
                        if hasattr(self._pipeline, "_embedding") and hasattr(
                            self._pipeline._embedding, "model_"
                        ):
                            try:
                                print(
                                    f"[DIARIZATION EXECUTION] Moving embedding model to {self.device}...",
                                    flush=True,
                                )
                                self._pipeline._embedding.model_ = (
                                    self._pipeline._embedding.model_.to(target_device)
                                )
                                components_moved.append("embedding")
                                print(
                                    f"[DIARIZATION EXECUTION] ✅ Embedding model moved to {self.device}",
                                    flush=True,
                                )
                            except Exception as e:
                                print(
                                    f"[DIARIZATION EXECUTION] ❌ Embedding failed on {self.device}: {e}",
                                    flush=True,
                                )
                                components_failed.append(("embedding", str(e)))
                                # Move to CPU as fallback
                                self._pipeline._embedding.model_ = (
                                    self._pipeline._embedding.model_.to(
                                        torch.device("cpu")
                                    )
                                )
                                self._cpu_fallback_ops.add("embedding")

                        # Report summary
                        print(
                            f"[DIARIZATION EXECUTION] Device setup complete:",
                            flush=True,
                        )
                        print(
                            f"  - Successfully on {self.device}: {components_moved}",
                            flush=True,
                        )
                        print(
                            f"  - Failed (using CPU): {[c[0] for c in components_failed]}",
                            flush=True,
                        )

                        if components_failed:
                            logger.warning(
                                f"Some diarization components require CPU fallback: {components_failed}"
                            )

                    except Exception as e:
                        print(
                            f"[DIARIZATION EXECUTION] Unexpected error during device setup: {e}",
                            flush=True,
                        )
                        logger.error(f"Device setup failed: {e}")

                # TEST: Try running pipeline directly without thread to isolate issue
                TEST_DIRECT_RUN = False  # Set to True to test direct execution
                if TEST_DIRECT_RUN:
                    print(
                        f"[TEST] Running pipeline directly without thread...",
                        flush=True,
                    )
                    sys.stdout.flush()
                    try:
                        diarization = self._pipeline(str(path))
                        print(f"[TEST] Direct execution succeeded!", flush=True)
                    except Exception as e:
                        print(f"[TEST] Direct execution failed: {e}", flush=True)
                    sys.stdout.flush()
                    # Exit early for testing
                    import os

                    os._exit(1)

                sys.stdout.flush()

                def run_pipeline_with_debug(audio_path):
                    """Wrapper to add debugging inside the thread"""
                    print(
                        f"[THREAD] Inside executor thread, about to call pipeline",
                        flush=True,
                    )
                    sys.stdout.flush()

                    if self._pipeline is None:
                        raise RuntimeError("Pipeline not loaded - cannot process audio")

                    # 🔧 FIX: Adjust clustering parameters based on audio duration
                    # For short videos (< 5 minutes), use lower min_cluster_size to prevent over-segmentation
                    if audio_duration and hasattr(self._pipeline, "clustering"):
                        duration_minutes = audio_duration / 60.0
                        
                        # Adaptive min_cluster_size based on video length
                        # Short videos (< 5 min) need much lower cluster size to avoid false splits
                        if duration_minutes < 5:
                            # Very short videos: use minimal cluster size
                            adaptive_min_cluster_size = max(3, int(duration_minutes * 2))
                            logger.info(
                                f"🔧 Short video detected ({duration_minutes:.1f} min): "
                                f"Using adaptive min_cluster_size={adaptive_min_cluster_size} "
                                f"(was {getattr(self._pipeline.clustering, 'min_cluster_size', 'default')})"
                            )
                        elif duration_minutes < 10:
                            # Short videos: reduce cluster size proportionally
                            adaptive_min_cluster_size = max(5, int(duration_minutes * 2.5))
                            logger.info(
                                f"🔧 Short video detected ({duration_minutes:.1f} min): "
                                f"Using adaptive min_cluster_size={adaptive_min_cluster_size} "
                                f"(was {getattr(self._pipeline.clustering, 'min_cluster_size', 'default')})"
                            )
                        else:
                            # Normal/long videos: use default settings
                            adaptive_min_cluster_size = getattr(
                                self._pipeline.clustering, 'min_cluster_size', 20
                            )
                            logger.debug(
                                f"Using default min_cluster_size={adaptive_min_cluster_size} "
                                f"for {duration_minutes:.1f} min video"
                            )
                        
                        # Apply adaptive cluster size
                        if hasattr(self._pipeline.clustering, 'min_cluster_size'):
                            original_size = self._pipeline.clustering.min_cluster_size
                            self._pipeline.clustering.min_cluster_size = adaptive_min_cluster_size
                            logger.info(
                                f"✅ Adjusted clustering: min_cluster_size {original_size} → {adaptive_min_cluster_size} "
                                f"(duration: {duration_minutes:.1f} min)"
                            )

                    try:
                        # Preload audio using torchaudio to avoid torchcodec FFmpeg issues
                        # See: https://github.com/pyannote/pyannote-audio/issues/1707
                        import torchaudio

                        print(
                            f"[THREAD] Preloading audio with torchaudio...", flush=True
                        )
                        waveform, sample_rate = torchaudio.load(audio_path)

                        # Pass as dictionary per pyannote.audio docs
                        audio_input = {"waveform": waveform, "sample_rate": sample_rate}

                        print(
                            f"[THREAD] Audio preloaded: {waveform.shape}, {sample_rate}Hz",
                            flush=True,
                        )
                        print(
                            f"[THREAD] Calling pipeline with preloaded audio...",
                            flush=True,
                        )

                        result = self._pipeline(audio_input)
                        print(f"[THREAD] Pipeline returned result", flush=True)
                        sys.stdout.flush()
                        return result
                    except Exception as e:
                        print(
                            f"[THREAD] Pipeline raised exception: {type(e).__name__}: {e}",
                            flush=True,
                        )
                        sys.stdout.flush()
                        raise

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    print(
                        f"[DIARIZATION EXECUTION] Submitting pipeline to executor...",
                        flush=True,
                    )
                    sys.stdout.flush()

                    future = executor.submit(run_pipeline_with_debug, str(path))

                    print(
                        f"[DIARIZATION EXECUTION] Waiting for result (5 min timeout)...",
                        flush=True,
                    )
                    sys.stdout.flush()

                    try:
                        # 5 minute timeout for diarization processing
                        diarization = future.result(timeout=300)

                        print(
                            f"[DIARIZATION EXECUTION] Got result! Type: {type(diarization)}",
                            flush=True,
                        )
                        sys.stdout.flush()
                    except concurrent.futures.TimeoutError:
                        logger.error("Diarization timed out after 5 minutes")
                        if self.progress_callback:
                            self.progress_callback("❌ Diarization timed out", 0)
                        # Stop the progress monitor thread
                        if progress_stop_event:
                            progress_stop_event.set()

                        # Check if this was likely a download timeout
                        hf_cache = Path.home() / ".cache" / "huggingface" / "hub"
                        model_id = self.model.replace("/", "--")
                        cached_models = (
                            list(hf_cache.glob(f"models--{model_id}*"))
                            if hf_cache.exists()
                            else []
                        )

                        if not cached_models:
                            return ProcessorResult(
                                success=False,
                                errors=[
                                    "Diarization model download timed out. The pyannote model is ~400MB. "
                                    "Please check your internet connection and try again, or disable diarization "
                                    "in settings to proceed without speaker identification."
                                ],
                            )
                        else:
                            return ProcessorResult(
                                success=False,
                                errors=[
                                    "Diarization processing timed out. This may be due to insufficient system resources."
                                ],
                            )
            except Exception as e:
                logger.error(f"Diarization pipeline error: {e}")
                if self.progress_callback:
                    self.progress_callback(f"❌ Diarization error: {str(e)}", 0)
                # Stop the progress monitor thread
                if progress_stop_event:
                    progress_stop_event.set()
                raise

            # Stop the progress monitor thread
            if progress_stop_event:
                progress_stop_event.set()

            # Report completion of diarization analysis
            if self.progress_callback:
                elapsed_time = time.time() - start_time
                self.progress_callback(
                    f"🎙️ Speaker analysis complete ({elapsed_time:.1f}s) - Processing segments...",
                    80,
                )

            segments = []
            segment_count = 0
            total_segment_estimate = None  # Will be estimated as we process

            # In pyannote.audio 4.0+, the pipeline returns a DiarizeOutput object
            # which is a wrapper containing the actual annotation in the .speaker_diarization attribute
            # See: https://github.com/pyannote/pyannote-audio/releases/tag/4.0.0

            # Access the actual Annotation object from DiarizeOutput
            if hasattr(diarization, "speaker_diarization"):
                annotation = diarization.speaker_diarization
                logger.info(
                    f"✅ Accessed speaker_diarization attribute, type: {type(annotation)}"
                )
            else:
                # Fallback for older versions or unexpected structure
                logger.warning(
                    f"⚠️ DiarizeOutput missing .speaker_diarization attribute. Type: {type(diarization)}"
                )
                public_attrs = [a for a in dir(diarization) if not a.startswith("_")]
                logger.warning(f"⚠️ Available attributes: {public_attrs}")
                raise AttributeError(
                    f"DiarizeOutput object missing expected .speaker_diarization attribute. "
                    f"Type: {type(diarization)}, Available: {public_attrs}"
                )

            # Process segments with progress updates
            for segment, speaker in annotation:
                segments.append(
                    {"start": segment.start, "end": segment.end, "speaker": speaker}
                )
                segment_count += 1

                # Provide progress updates every 5 segments for more granular feedback
                if segment_count % 5 == 0 and self.progress_callback:
                    # Estimate total segments based on audio duration if available
                    if audio_duration and not total_segment_estimate:
                        # Rough estimate: 1 segment per 3-10 seconds of audio
                        total_segment_estimate = max(10, int(audio_duration / 5))

                    # Calculate progress from 80% to 95% based on segment processing
                    if total_segment_estimate:
                        segment_progress = min(
                            0.95, segment_count / total_segment_estimate
                        )
                        progress_percent = 80 + (segment_progress * 15)  # 80% to 95%
                    else:
                        # Fallback: gradual increase from 80% approaching 95%
                        progress_factor = 1 - (1 / (1 + segment_count / 20))
                        progress_percent = 80 + (progress_factor * 15)

                    # Calculate ETA if available
                    eta_str = ""
                    if eta_calc:
                        eta_text, _ = eta_calc.update(progress_percent)
                        if eta_text:
                            eta_str = f" | ETA: {eta_text}"

                    # Estimate remaining segments for better user feedback
                    if (
                        total_segment_estimate
                        and segment_count < total_segment_estimate
                    ):
                        remaining_segments = total_segment_estimate - segment_count
                        segment_info = f"Processing {segment_count} speaker segments (~{remaining_segments} remaining)..."
                    else:
                        segment_info = f"Processing {segment_count} speaker segments..."

                    self.progress_callback(
                        f"🎙️ {filename}: {segment_info}{eta_str}",
                        int(progress_percent),
                    )

            # Final progress update
            # Calculate final statistics
            total_time = time.time() - start_time
            processing_speed = (
                audio_duration / total_time if audio_duration and total_time > 0 else 0
            )
            speed_info = (
                f" ({processing_speed:.1f}x realtime)" if processing_speed > 0 else ""
            )

            if self.progress_callback:
                self.progress_callback(
                    f"✅ {filename}: Diarization complete! Found {len(segments)} speaker segments{speed_info}",
                    100,
                )

            logger.info(
                f"✅ Diarization completed for '{filename}': {len(segments)} segments found in {total_time:.1f}s{speed_info}"
            )

            return ProcessorResult(
                success=True,
                data=segments,
                metadata={"model": self.model, "segments_count": len(segments)},
            )
        except Exception as e:
            import traceback

            # Log full traceback for debugging
            error_traceback = traceback.format_exc()
            logger.error(f"Diarization error: {e}")
            logger.debug(f"Full diarization error traceback:\n{error_traceback}")

            # Create detailed error message
            error_details = str(e)

            # Add context about what operation failed
            if "from_pretrained" in error_traceback:
                error_details += " (Failed during model loading)"
            elif "apply" in error_traceback or "forward" in error_traceback:
                error_details += " (Failed during audio processing)"
            elif "Authentication" in error_details or "401" in error_details:
                error_details += " (HuggingFace authentication failed)"

            # Report error through progress callback
            if self.progress_callback:
                self.progress_callback(f"❌ Diarization failed: {error_details}", 0)

            return ProcessorResult(success=False, errors=[error_details])


def is_diarization_available() -> bool:
    """Check if diarization is available without loading dependencies."""
    # Force a fresh check each time to avoid caching issues in GUI context
    global PIPELINE_AVAILABLE, PIPELINE
    PIPELINE_AVAILABLE = False
    PIPELINE = None
    return _check_diarization_dependencies()


def get_diarization_installation_instructions() -> str:
    """Get installation instructions for diarization dependencies."""
    return (
        "To enable speaker diarization, install the required dependencies:\n"
        "  pip install -e '.[diarization]'\n\n"
        "Or install manually:\n"
        "  pip install torch transformers pyannote.audio\n\n"
        "Note: This will add ~377MB to your installation size."
    )
