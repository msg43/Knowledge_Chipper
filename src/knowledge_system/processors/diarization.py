import warnings
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

    try:
        from pyannote.audio import Pipeline

        PIPELINE = Pipeline
        PIPELINE_AVAILABLE = True
        logger.info("Diarization dependencies loaded successfully")
        return True
    except ImportError:
        PIPELINE_AVAILABLE = False
        PIPELINE = None
        logger.warning(
            "Diarization dependencies not available. "
            "Install with: pip install -e '.[diarization]' or pip install torch transformers pyannote.audio"
        )
        return False
    except Exception as e:
        PIPELINE_AVAILABLE = False
        PIPELINE = None
        logger.error(f"Error loading diarization dependencies: {e}")
        return False


class SpeakerDiarizationProcessor(BaseProcessor):
    """Performs speaker diarization using pyannote.audio with lazy loading."""

    def __init__(
        self,
        model: str = "pyannote/speaker-diarization-3.1",
        device: str | None = None,
        hf_token: str | None = None,
        progress_callback: callable = None,
    ) -> None:
        self.model = model
        self.device = device or self._detect_best_device()
        self.hf_token = hf_token
        self.progress_callback = progress_callback
        self._pipeline = None
        self._dependencies_checked = False

    def _detect_best_device(self) -> str:
        """Detect the best available device for diarization."""
        try:
            import torch

            if torch.backends.mps.is_available() and torch.backends.mps.is_built():
                logger.info("Apple Silicon MPS detected for diarization")
                return "mps"
            elif torch.cuda.is_available():
                logger.info("CUDA detected for diarization")
                return "cuda"
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
        if not self._check_dependencies():
            raise ImportError(
                "Diarization dependencies not available. "
                "Install with: pip install -e '.[diarization]' or pip install torch transformers pyannote.audio"
            )

        if self._pipeline is None:
            if self.progress_callback:
                self.progress_callback(
                    "Loading diarization model (this may take a moment)...", 20
                )

            # Use cached model loading
            def pipeline_loader():
                logger.info(f"Loading pyannote.audio pipeline: {self.model}")
                if self.progress_callback:
                    self.progress_callback(f"Downloading/loading {self.model}...", 40)

                # Set HuggingFace token as environment variable for better compatibility
                # This works around authentication issues in pyannote.audio 3.x
                import os

                if self.hf_token:
                    os.environ["HF_TOKEN"] = self.hf_token
                    os.environ["HUGGINGFACE_HUB_TOKEN"] = self.hf_token
                    logger.info(
                        "Set HuggingFace environment variables for authentication"
                    )

                pipeline = PIPELINE.from_pretrained(
                    self.model, use_auth_token=self.hf_token
                )

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
                if self.device and self.device != "cpu":
                    try:
                        import torch

                        logger.info(
                            f"Moving diarization pipeline to device: {self.device}"
                        )
                        if self.progress_callback:
                            self.progress_callback(
                                f"Moving model to {self.device}...", 80
                            )

                        # Convert device string to torch.device object
                        torch_device = torch.device(self.device)
                        pipeline = pipeline.to(torch_device)
                        logger.info(
                            f"Diarization pipeline successfully moved to {self.device}"
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to move pipeline to {self.device}, falling back to CPU: {e}"
                        )
                        if self.progress_callback:
                            self.progress_callback(
                                "Using CPU for diarization (GPU failed)", 80
                            )

                return pipeline

            # Get cached pipeline
            self._pipeline = cache_diarization_model(
                model_name=self.model,
                device=self.device,
                loader_func=pipeline_loader,
                hf_token=self.hf_token,
            )

            if self.progress_callback:
                self.progress_callback("Diarization pipeline ready!", 100)
            logger.info("pyannote.audio pipeline ready (cached or newly loaded)")

    def validate_input(self, input_path: str | Path) -> bool:
        return validate_audio_input(input_path)

    def can_process(self, input_path: str | Path) -> bool:
        return self.validate_input(input_path)

    def process(
        self, input_data: Any, dry_run: bool = False, **kwargs: Any
    ) -> ProcessorResult:
        # Extract parameters from kwargs for backwards compatibility
        kwargs.get("device", None)

        # Handle input_data as input_path for backwards compatibility
        input_path = input_data

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

            # Report start of actual diarization processing
            if self.progress_callback:
                self.progress_callback("🎙️ Analyzing speakers in audio...", 0)

            logger.info(f"Starting diarization processing for: {path}")

            # Create ETA calculator for progress tracking
            import time

            from ..utils.eta_calculator import ETACalculator

            start_time = time.time()
            eta_calc = ETACalculator() if self.progress_callback else None
            if eta_calc:
                eta_calc.start()

            # Estimate audio duration for better progress tracking
            try:
                import subprocess

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

                        self.progress_callback(
                            f"🎙️ Analyzing speakers - {phase}... ({elapsed:.1f}s elapsed{eta_str})",
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

            diarization = self._pipeline(str(path))

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

            # Process segments with progress updates
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                segments.append(
                    {"start": turn.start, "end": turn.end, "speaker": speaker}
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

                    self.progress_callback(
                        f"🎙️ Processing speaker segments: {segment_count} found...{eta_str}",
                        int(progress_percent),
                    )

            # Final progress update
            if self.progress_callback:
                self.progress_callback(
                    f"✅ Diarization complete! Found {len(segments)} speaker segments",
                    100,
                )

            logger.info(
                f"Diarization completed successfully: {len(segments)} segments found"
            )

            return ProcessorResult(
                success=True,
                data=segments,
                metadata={"model": self.model, "segments_count": len(segments)},
            )
        except Exception as e:
            logger.error(f"Diarization error: {e}")
            # Report error through progress callback
            if self.progress_callback:
                self.progress_callback(f"❌ Diarization failed: {str(e)}", 0)
            return ProcessorResult(success=False, errors=[str(e)])


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
