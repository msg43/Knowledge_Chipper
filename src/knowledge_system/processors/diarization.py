from pathlib import Path
from typing import Any

from knowledge_system.logger import get_logger
from knowledge_system.processors.base import BaseProcessor, ProcessorResult
from knowledge_system.utils.model_cache import cache_diarization_model
from knowledge_system.utils.validation import validate_audio_input

logger = get_logger(__name__)

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
                        logger.info(
                            f"Moving diarization pipeline to device: {self.device}"
                        )
                        if self.progress_callback:
                            self.progress_callback(
                                f"Moving model to {self.device}...", 80
                            )
                        pipeline = pipeline.to(self.device)
                        logger.info(
                            f"Diarization pipeline successfully moved to {self.device}"
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to move pipeline to {self.device}, falling back to CPU: {e}"
                        )
                        if self.progress_callback:
                            self.progress_callback(
                                f"Using CPU for diarization (GPU failed)", 80
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

            # Create a more detailed progress callback during diarization processing
            import time

            start_time = time.time()

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
            if self.progress_callback and audio_duration:

                def progress_monitor():
                    while True:
                        elapsed = time.time() - start_time
                        # Rough estimate: diarization typically takes 0.1-0.3x real-time
                        estimated_completion = (
                            audio_duration * 0.2
                        )  # 20% of audio duration
                        if elapsed >= estimated_completion:
                            break
                        progress_percent = min(
                            45, int((elapsed / estimated_completion) * 45)
                        )
                        self.progress_callback(
                            f"🎙️ Analyzing speakers... ({elapsed:.1f}s elapsed)",
                            progress_percent,
                        )
                        time.sleep(2)  # Update every 2 seconds

                import threading

                progress_thread = threading.Thread(target=progress_monitor, daemon=True)
                progress_thread.start()

            diarization = self._pipeline(str(path))

            # Report completion of diarization analysis
            if self.progress_callback:
                elapsed_time = time.time() - start_time
                self.progress_callback(
                    f"🎙️ Speaker analysis complete ({elapsed_time:.1f}s) - Processing segments...",
                    50,
                )

            segments = []
            segment_count = 0

            # Process segments with progress updates
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                segments.append(
                    {"start": turn.start, "end": turn.end, "speaker": speaker}
                )
                segment_count += 1

                # Provide periodic progress updates for segment processing
                if segment_count % 10 == 0 and self.progress_callback:
                    self.progress_callback(
                        f"🎙️ Processed {segment_count} speaker segments...",
                        min(90, 50 + (segment_count * 2)),  # Progress from 50% to 90%
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
