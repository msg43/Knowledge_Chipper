import re
from pathlib import Path

from knowledge_system.processors.base import BaseProcessor
from knowledge_system.processors.document_processor import DocumentProcessor
from knowledge_system.processors.html import HTMLProcessor
from knowledge_system.processors.pdf import PDFProcessor
from knowledge_system.processors.rss_processor import RSSProcessor
from knowledge_system.processors.youtube_download import YouTubeDownloadProcessor
from knowledge_system.processors.youtube_metadata import YouTubeMetadataProcessor

# Registry maps extension or pattern to processor class
_PROCESSOR_REGISTRY: list[dict] = []


def register_processor(
    processor_cls: type[BaseProcessor],
    extensions: list[str] | None = None,
    url_patterns: list[str] | None = None,
    name: str | None = None,
):
    """Register a processor for file extensions and/or URL patterns."""
    _PROCESSOR_REGISTRY.append(
        {
            "name": name or processor_cls.__name__,
            "cls": processor_cls,
            "extensions": [e.lower() for e in (extensions or [])],
            "url_patterns": url_patterns or [],
        }
    )


def get_processor_for_input(
    input_path_or_url: str | Path,
) -> type[BaseProcessor] | None:
    """Return the processor class for a given file path or URL."""
    s = str(input_path_or_url)
    # Check URL patterns first
    for entry in _PROCESSOR_REGISTRY:
        for pat in entry["url_patterns"]:
            if re.match(pat, s):
                return entry["cls"]
    # Check file extension
    ext = Path(s).suffix.lower()
    for entry in _PROCESSOR_REGISTRY:
        if ext in entry["extensions"]:
            return entry["cls"]
    return None


def list_processors() -> list[str]:
    return [entry["name"] for entry in _PROCESSOR_REGISTRY]


def get_all_processor_stats() -> dict[str, dict]:
    """Get statistics from all registered processor instances."""
    from knowledge_system.processors.base import get_processor_registry

    registry = get_processor_registry()
    all_stats = {}

    for name in registry.list_processors():
        processor = registry.get(name)
        if processor:
            all_stats[name] = processor.get_stats()

    return all_stats


# Register built-in processors
register_processor(
    YouTubeMetadataProcessor,
    url_patterns=[r"https?://(www\.)?(youtube\.com|youtu\.be)/.*/?"],
    name="YouTubeMetadataProcessor",
)
register_processor(
    YouTubeDownloadProcessor,
    url_patterns=[r"https?://(www\.)?(youtube\.com|youtu\.be)/.*/?"],
    name="YouTubeDownloadProcessor",
)
register_processor(PDFProcessor, extensions=[".pdf"], name="PDFProcessor")
register_processor(HTMLProcessor, extensions=[".html", ".htm"], name="HTMLProcessor")
register_processor(
    DocumentProcessor,
    extensions=[".txt", ".md", ".docx", ".doc", ".rtf"],
    name="DocumentProcessor",
)
register_processor(
    RSSProcessor,
    url_patterns=[
        r".*\.rss$",
        r".*rss\.xml$",
        r".*/rss/?$",
        r".*/feed/?$",
        r".*feeds?\..*",
        r".*/atom\.xml$",
        r".*/index\.xml$",
    ],
    name="RSSProcessor",
)
