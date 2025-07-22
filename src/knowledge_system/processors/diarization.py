from typing import Any, Union, Optional
from pathlib import Path
from knowledge_system.processors.base import BaseProcessor, ProcessorResult
from knowledge_system.utils.validation import validate_audio_input
from knowledge_system.logger import get_logger

logger = get_logger(__name__)

try:
    from pyannote.audio import Pipeline
except ImportError:
    Pipeline = None


class SpeakerDiarizationProcessor(BaseProcessor):
    """Performs speaker diarization using pyannote.audio."""

    def __init__(
        self,
        model: str = "pyannote/speaker-diarization@2023.07",
        device: Optional[str] = None,
        hf_token: Optional[str] = None,
    ):
        self.model = model
        self.device = device or "cpu"
        self.hf_token = hf_token
        self._pipeline = None

    @property
    def supported_formats(self) -> list:
        """Audio formats supported by pyannote.audio for diarization."""
        return [".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac", ".mp4", ".webm"]

    def _load_pipeline(self):
        if self._pipeline is None:
            if Pipeline is None:
                raise ImportError("pyannote.audio is not installed.")
            logger.info(f"Loading pyannote.audio pipeline: {self.model}")
            self._pipeline = Pipeline.from_pretrained(
                self.model, use_auth_token=self.hf_token
            )
            logger.info("pyannote.audio pipeline loaded successfully")

    def validate_input(self, input_path: Union[str, Path]) -> bool:
        return validate_audio_input(input_path)

    def can_process(self, input_path: Union[str, Path]) -> bool:
        return self.validate_input(input_path)

    def process(
        self, input_data: Any, dry_run: bool = False, **kwargs: Any
    ) -> ProcessorResult:
        # Extract parameters from kwargs for backwards compatibility
        device = kwargs.get('device', None)
        
        # Handle input_data as input_path for backwards compatibility
        input_path = input_data
        
        if Pipeline is None:
            return ProcessorResult(
                success=False, errors=["pyannote.audio is not installed."], dry_run=dry_run
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
                    success=False, errors=["Failed to load diarization pipeline"], dry_run=dry_run
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
                metadata={
    "model": self.model,
     "segments_count": len(segments)},
            )
        except Exception as e:
            logger.error(f"Diarization error: {e}")
            return ProcessorResult(success=False, errors=[str(e)])
