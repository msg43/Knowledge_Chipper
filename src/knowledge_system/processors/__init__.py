"""Processors for the Knowledge System."""

from .base import BaseProcessor, ProcessorResult
from .audio_processor import AudioProcessor
# Keep WhisperCppTranscribeProcessor internal - users should use AudioProcessor
# from .whisper_cpp_transcribe import WhisperCppTranscribeProcessor
from .youtube_download import YouTubeDownloadProcessor
from .youtube_transcript import YouTubeTranscriptProcessor
from .youtube_metadata import YouTubeMetadataProcessor
from .summarizer import SummarizerProcessor
from .moc import MOCProcessor
from .pdf import PDFProcessor
from .diarization import SpeakerDiarizationProcessor

__all__ = [
    "BaseProcessor",
    "ProcessorResult",
    "AudioProcessor",
    # "WhisperCppTranscribeProcessor",  # Internal use only
    "YouTubeDownloadProcessor",
    "YouTubeTranscriptProcessor",
    "YouTubeMetadataProcessor",
    "SummarizerProcessor",
    "MOCProcessor",
    "PDFProcessor",
    "SpeakerDiarizationProcessor",
]
