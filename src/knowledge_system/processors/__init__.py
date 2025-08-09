""" Processors for the Knowledge System."""

from .audio_processor import AudioProcessor
from .base import BaseProcessor, ProcessorResult
from .diarization import SpeakerDiarizationProcessor
from .html import HTMLProcessor
from .moc import MOCProcessor
from .pdf import PDFProcessor
from .summarizer import SummarizerProcessor

# Keep WhisperCppTranscribeProcessor internal - users should use AudioProcessor
# from .whisper_cpp_transcribe import WhisperCppTranscribeProcessor
from .youtube_download import YouTubeDownloadProcessor
from .youtube_metadata import YouTubeMetadataProcessor
from .youtube_transcript import YouTubeTranscriptProcessor

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
    "HTMLProcessor",
    "SpeakerDiarizationProcessor",
]
