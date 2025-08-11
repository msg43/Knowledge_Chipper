"""
HTML Processor
HTML Processor

Extracts text content from HTML files using BeautifulSoup.
Handles single files and folders, returns clean text content stripped of HTML tags.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from ..errors import ProcessingError
from ..logger import get_logger
from .base import BaseProcessor, ProcessorResult

logger = get_logger(__name__)

try:
    from bs4 import BeautifulSoup

    BEAUTIFULSOUP_AVAILABLE = True
except ImportError:
    BEAUTIFULSOUP_AVAILABLE = False
    logger.warning("BeautifulSoup4 not available. HTML processing will not work.")


class HTMLProcessor(BaseProcessor):
    """ Processor for extracting text from HTML files or folders."""

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name or "html_processor")

        if not BEAUTIFULSOUP_AVAILABLE:
            raise ProcessingError(
                "BeautifulSoup4 is required for HTML processing. "
                "Install it with: pip install beautifulsoup4"
            )

    @property
    def supported_formats(self) -> list[str]:
        return [".html", ".htm"]

    def validate_input(self, input_data: Any) -> bool:
        if isinstance(input_data, (str, Path)):
            path = Path(input_data)
            if path.is_file() and path.suffix.lower() in [".html", ".htm"]:
                return True
            if path.is_dir():
                return any(
                    f.suffix.lower() in [".html", ".htm"] for f in path.iterdir()
                )
        return False

    def _extract_text_from_html(self, html_path: Path) -> dict[str, Any]:
        """ Extract text content from HTML file."""
        try:
            with open(html_path, encoding="utf-8", errors="replace") as f:
                html_content = f.read()

            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(html_content, "html.parser")

            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            # Extract title if available
            title = soup.title.string if soup.title else html_path.stem

            # Get text content
            text = soup.get_text()

            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = " ".join(chunk for chunk in chunks if chunk)

            # Extract some basic metadata
            meta_description = ""
            if soup.find("meta", {"name": "description"}):
                meta_description = soup.find("meta", {"name": "description"}).get(
                    "content", ""
                )

            return {
                "text": text,
                "title": title,
                "word_count": len(text.split()) if text else 0,
                "char_count": len(text) if text else 0,
                "meta_description": meta_description,
            }

        except UnicodeDecodeError:
            # Try with different encoding
            try:
                with open(html_path, encoding="latin-1") as f:
                    html_content = f.read()

                soup = BeautifulSoup(html_content, "html.parser")

                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()

                title = soup.title.string if soup.title else html_path.stem
                text = soup.get_text()

                # Clean up whitespace
                lines = (line.strip() for line in text.splitlines())
                chunks = (
                    phrase.strip() for line in lines for phrase in line.split("  ")
                )
                text = " ".join(chunk for chunk in chunks if chunk)

                return {
                    "text": text,
                    "title": title,
                    "word_count": len(text.split()) if text else 0,
                    "char_count": len(text) if text else 0,
                    "meta_description": "",
                }

            except Exception as e:
                logger.error(
                    f"Failed to process HTML file {html_path} with latin-1 encoding: {e}"
                )
                return {"error": str(e)}

        except Exception as e:
            logger.error(f"Failed to process HTML file {html_path}: {e}")
            return {"error": str(e)}

    def process(
        self, input_data: Any, dry_run: bool = False, **kwargs: Any
    ) -> ProcessorResult:
        """ Process HTML files and extract text content."""
        paths = []
        if isinstance(input_data, (str, Path)):
            path = Path(input_data)
            logger.info(
                f"HTML Processor received input: {path} (type: {type(input_data)})"
            )
            logger.info(f"HTML Processor absolute path: {path.absolute()}")
            logger.info(f"HTML Processor path exists: {path.exists()}")

            if path.is_file() and path.suffix.lower() in [".html", ".htm"]:
                paths = [path]
            elif path.is_dir():
                paths = [
                    f for f in path.iterdir() if f.suffix.lower() in [".html", ".htm"]
                ]

        logger.info(
            f"HTML Processor will process {len(paths)} files: {[str(p) for p in paths]}"
        )

        if not paths:
            return ProcessorResult(
                success=False, errors=["No HTML files found in input"]
            )

        results = []
        errors = []

        for html_path in paths:
            logger.info(f"Processing HTML file: {html_path.absolute()}")
            logger.info(
                f"HTML file size: {html_path.stat().st_size if html_path.exists() else 'File not found'}"
            )

            result = self._extract_text_from_html(html_path)

            if result.get("error") or not result.get("text"):
                errors.append(
                    f"Failed to extract from {html_path}: {result.get('error', 'No text extracted')}"
                )
                continue

            # Log first 200 characters of extracted text for debugging
            text_preview = result["text"][:200] if result["text"] else "No text"
            logger.info(
                f"Extracted text preview from {html_path.name}: {text_preview}..."
            )
            logger.info(f"Total text length: {len(result['text'])} characters")

            results.append(
                {
                    "file": str(html_path),
                    "text": result["text"],
                    "title": result["title"],
                    "word_count": result["word_count"],
                    "char_count": result["char_count"],
                    "meta_description": result.get("meta_description", ""),
                }
            )

        return ProcessorResult(
            success=len(errors) == 0,
            data={
                "results": results,
                "errors": errors,
                "count": len(results),
            },
            errors=errors if errors else None,
            metadata={
                "files_processed": len(results),
                "errors_count": len(errors),
                "timestamp": datetime.now().isoformat(),
            },
        )


def fetch_html_text(html_path: str | Path) -> str:
    """ Convenience function to extract text from a single HTML file."""
    processor = HTMLProcessor()
    result = processor.process(html_path)
    if not result.success:
        raise ProcessingError(f"Failed to extract HTML text: {result.errors}")
    results = result.data.get("results", [])
    if not results:
        raise ProcessingError("No text extracted from HTML")
    return results[0]["text"]
