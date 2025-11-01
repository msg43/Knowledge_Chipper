"""Processors for the Knowledge System."""

# AudioProcessor removed - functionality moved to WhisperCppTranscribeProcessor
# from .audio_processor import AudioProcessor
from .base import BaseProcessor, ProcessorResult
from .diarization import SpeakerDiarizationProcessor
from .document_processor import DocumentProcessor
from .html import HTMLProcessor
from .pdf import PDFProcessor
from .rss_processor import RSSProcessor

# Keep WhisperCppTranscribeProcessor internal - direct usage discouraged
# from .whisper_cpp_transcribe import WhisperCppTranscribeProcessor
from .youtube_download import YouTubeDownloadProcessor

# YouTubeMetadataProcessor removed - YouTubeDownloadProcessor handles all metadata extraction
# YouTube transcript processor removed - use YouTubeDownloadProcessor + WhisperCppTranscribeProcessor instead
# SummarizerProcessor removed - GUI uses System2Orchestrator instead
# MOCProcessor removed - claim-centric architecture supersedes this functionality
# QualityEvaluator removed - not used anywhere in codebase
# YouTubeMetadataProxyProcessor removed - functionality absorbed by YouTubeDownloadProcessor

__all__ = [
    "BaseProcessor",
    "ProcessorResult",
    # "AudioProcessor",  # Removed
    # "WhisperCppTranscribeProcessor",  # Internal use only
    "DocumentProcessor",
    "YouTubeDownloadProcessor",
    "PDFProcessor",
    "HTMLProcessor",
    "RSSProcessor",
    "SpeakerDiarizationProcessor",
]
