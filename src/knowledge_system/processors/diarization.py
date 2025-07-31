from pathlib import Path
from typing import Any, Optional, Union

from knowledge_system.logger import get_logger
from knowledge_system.processors.base import BaseProcessor, ProcessorResult
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
    except ImportError as e:
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
        model: str = "pyannote/speaker-diarization@2023.07",
        device: str | None = None,
        hf_token: str | None = None,
    ) -> None:
        self.model = model
        self.device = device or "cpu"
        self.hf_token = hf_token
        self._pipeline = None
        self._dependencies_checked = False

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
            logger.info(f"Loading pyannote.audio pipeline: {self.model}")
            self._pipeline = PIPELINE.from_pretrained(
                self.model, use_auth_token=self.hf_token
            )
            logger.info("pyannote.audio pipeline loaded successfully")

    def validate_input(self, input_path: str | Path) -> bool:
        return validate_audio_input(input_path)

    def can_process(self, input_path: str | Path) -> bool:
        return self.validate_input(input_path)

    def process(
        self, input_data: Any, dry_run: bool = False, **kwargs: Any
    ) -> ProcessorResult:
        # Extract parameters from kwargs for backwards compatibility
        device = kwargs.get("device", None)

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

            diarization = self._pipeline(str(path))
            segments = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                segments.append(
                    {"start": turn.start, "end": turn.end, "speaker": speaker}
                )

            return ProcessorResult(
                success=True,
                data=segments,
                metadata={"model": self.model, "segments_count": len(segments)},
            )
        except Exception as e:
            logger.error(f"Diarization error: {e}")
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
