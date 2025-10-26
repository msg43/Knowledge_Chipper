"""Processors for the Knowledge System."""

from .audio_processor import AudioProcessor
from .base import BaseProcessor, ProcessorResult
from .diarization import SpeakerDiarizationProcessor
from .document_processor import DocumentProcessor
from .html import HTMLProcessor
from .moc import MOCProcessor
from .pdf import PDFProcessor
from .rss_processor import RSSProcessor

# Keep WhisperCppTranscribeProcessor internal - users should use AudioProcessor
# from .whisper_cpp_transcribe import WhisperCppTranscribeProcessor
from .youtube_download import YouTubeDownloadProcessor

# YouTubeMetadataProcessor removed - YouTubeDownloadProcessor handles all metadata extraction
# YouTube transcript processor removed - use YouTubeDownloadProcessor + AudioProcessor instead
# SummarizerProcessor removed - GUI uses System2Orchestrator instead

__all__ = [
    "BaseProcessor",
    "ProcessorResult",
    "AudioProcessor",
    # "WhisperCppTranscribeProcessor",  # Internal use only
    "DocumentProcessor",
    "YouTubeDownloadProcessor",
    # "YouTubeMetadataProcessor",  # Removed - YouTubeDownloadProcessor handles metadata
    "MOCProcessor",  # Still used by GUI
    "PDFProcessor",
    "HTMLProcessor",
    "RSSProcessor",
    "SpeakerDiarizationProcessor",
]
