"""
Document Processor for Knowledge System.

Handles processing of documents (PDF, DOCX, TXT, MD) with author attribution
and metadata extraction for whitepapers, academic papers, and general documents.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from ..database import DatabaseService
from ..logger import get_logger
from ..processors.base import BaseProcessor, ProcessorResult
from ..utils.validation import validate_document_input

logger = get_logger(__name__)


class DocumentMetadata:
    """Container for document metadata."""

    def __init__(self):
        self.title: str | None = None
        self.authors: list[str] = []
        self.date: datetime | None = None
        self.abstract: str | None = None
        self.keywords: list[str] = []
        self.organization: str | None = None
        self.document_type: str = "document"  # paper, whitepaper, article, report
        self.doi: str | None = None
        self.url: str | None = None
        self.citations: list[dict[str, str]] = []

    def to_dict(self) -> dict[str, Any]:
        """Convert metadata to dictionary."""
        return {
            "title": self.title,
            "authors": self.authors,
            "date": self.date.isoformat() if self.date else None,
            "abstract": self.abstract,
            "keywords": self.keywords,
            "organization": self.organization,
            "document_type": self.document_type,
            "doi": self.doi,
            "url": self.url,
            "citations": self.citations,
        }


class DocumentProcessor(BaseProcessor):
    """Process documents with author attribution and metadata extraction."""

    # Common author patterns
    AUTHOR_PATTERNS = [
        # Academic style: "John Doe^1, Jane Smith^2"
        r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*(?:\^?\d+|,|\sand\s|$)",
        # By line: "By John Doe"
        r"^By\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
        # Author: line
        r"^Authors?:\s*(.+)$",
        # Written by
        r"^Written\s+by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
    ]

    # Title patterns
    TITLE_PATTERNS = [
        r"^#\s+(.+)$",  # Markdown H1
        r"^Title:\s*(.+)$",  # Title: line
        r"^(.+)\n[=]{3,}$",  # Underlined with =
    ]

    # Date patterns
    DATE_PATTERNS = [
        r"(\d{4}-\d{2}-\d{2})",  # YYYY-MM-DD
        r"(\d{1,2}/\d{1,2}/\d{4})",  # MM/DD/YYYY
        r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4})",  # Month DD, YYYY
    ]

    # Abstract patterns
    ABSTRACT_PATTERNS = [
        r"^Abstract[:\s]*\n(.+?)(?:\n\n|\n[A-Z])",  # Abstract: followed by text
        r"^Summary[:\s]*\n(.+?)(?:\n\n|\n[A-Z])",  # Summary: followed by text
    ]

    @property
    def supported_formats(self) -> list[str]:
        """Return list of supported formats."""
        return [".pdf", ".txt", ".md", ".docx", ".doc", ".rt"]

    def validate_input(self, input_data: Any) -> bool:
        """Validate input data for document processing."""
        return validate_document_input(input_data)

    def validate(self, input_data: Any) -> None:
        """Validate input document."""
        if not validate_document_input(input_data):
            raise ValueError(f"Invalid document input: {input_data}")

    def extract_metadata(self, text: str, file_path: Path) -> DocumentMetadata:
        """Extract metadata from document text."""
        metadata = DocumentMetadata()

        # Try to extract from first 1000 lines or 5000 characters
        preview = "\n".join(text.split("\n")[:1000])[:5000]

        # Extract title
        metadata.title = self._extract_title(preview, file_path)

        # Extract authors
        metadata.authors = self._extract_authors(preview)

        # Extract date
        metadata.date = self._extract_date(preview)

        # Extract abstract
        metadata.abstract = self._extract_abstract(preview)

        # Extract keywords
        metadata.keywords = self._extract_keywords(preview)

        # Determine document type
        metadata.document_type = self._determine_document_type(text, file_path)

        return metadata

    def _extract_title(self, text: str, file_path: Path) -> str:
        """Extract document title."""
        # Try patterns first
        for pattern in self.TITLE_PATTERNS:
            match = re.search(pattern, text, re.MULTILINE)
            if match:
                return match.group(1).strip()

        # Try first non-empty line
        for line in text.split("\n"):
            line = line.strip()
            if line and not line.startswith("#") and len(line) > 10:
                return line

        # Fall back to filename
        return file_path.stem.replace("_", " ").replace("-", " ").title()

    def _extract_authors(self, text: str) -> list[str]:
        """Extract author names from text."""
        authors = []

        # Look for author patterns
        lines = text.split("\n")
        for i, line in enumerate(lines[:50]):  # Check first 50 lines
            for pattern in self.AUTHOR_PATTERNS:
                match = re.search(pattern, line.strip(), re.IGNORECASE)
                if match:
                    # Extract author names
                    author_text = match.group(1) if match.lastindex else match.group(0)

                    # Split multiple authors
                    for sep in [",", " and ", "&", ";"]:
                        if sep in author_text:
                            parts = author_text.split(sep)
                            authors.extend([p.strip() for p in parts if p.strip()])
                            break
                    else:
                        authors.append(author_text.strip())

                    break

        # Clean and deduplicate
        cleaned_authors = []
        for author in authors:
            # Remove superscripts and extra whitespace
            author = re.sub(r"\^?\d+", "", author).strip()
            author = re.sub(r"\s+", " ", author)

            # Basic validation
            if author and len(author) > 3 and " " in author:
                cleaned_authors.append(author)

        return list(
            dict.fromkeys(cleaned_authors)
        )  # Remove duplicates preserving order

    def _extract_date(self, text: str) -> datetime | None:
        """Extract publication date from text."""
        for pattern in self.DATE_PATTERNS:
            match = re.search(pattern, text)
            if match:
                date_str = match.group(1)
                try:
                    # Try different date formats
                    for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y", "%b %d, %Y"]:
                        try:
                            return datetime.strptime(date_str.replace(",", ""), fmt)
                        except ValueError:
                            continue
                except Exception:
                    pass
        return None

    def _extract_abstract(self, text: str) -> str | None:
        """Extract abstract from text."""
        for pattern in self.ABSTRACT_PATTERNS:
            match = re.search(pattern, text, re.MULTILINE | re.DOTALL | re.IGNORECASE)
            if match:
                abstract = match.group(1).strip()
                # Clean up
                abstract = re.sub(r"\s+", " ", abstract)
                if len(abstract) > 50:  # Reasonable minimum length
                    return abstract
        return None

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract keywords from text."""
        keywords = []

        # Look for explicit keywords section
        keyword_match = re.search(r"Keywords?:\s*(.+?)(?:\n|$)", text, re.IGNORECASE)
        if keyword_match:
            keyword_text = keyword_match.group(1)
            # Split by common separators
            for sep in [",", ";", "•", "|"]:
                if sep in keyword_text:
                    keywords = [k.strip() for k in keyword_text.split(sep)]
                    break
            else:
                keywords = [keyword_text.strip()]

        return [k for k in keywords if k and len(k) > 2]

    def _determine_document_type(self, text: str, file_path: Path) -> str:
        """Determine the type of document."""
        text_lower = text.lower()
        filename_lower = file_path.name.lower()

        if "whitepaper" in filename_lower or "white paper" in text_lower[:1000]:
            return "whitepaper"
        elif "abstract" in text_lower[:1000] and "references" in text_lower:
            return "paper"
        elif "technical report" in text_lower[:1000]:
            return "report"
        elif any(word in filename_lower for word in ["article", "blog", "post"]):
            return "article"
        else:
            return "document"

    def process(self, input_data: Any, **kwargs) -> ProcessorResult:
        """Process a document file."""
        try:
            file_path = Path(input_data)
            self.validate(file_path)

            # Read the document content based on type
            if file_path.suffix.lower() == ".pdf":
                text = self._process_pdf(file_path)
            elif file_path.suffix.lower() in [".txt", ".md"]:
                text = file_path.read_text(encoding="utf-8")
            elif file_path.suffix.lower() in [".docx", ".doc"]:
                text = self._process_docx(file_path)
            elif file_path.suffix.lower() == ".rt":
                text = self._process_rtf(file_path)
            else:
                return ProcessorResult(
                    success=False,
                    errors=[f"Unsupported document format: {file_path.suffix}"],
                )

            # Extract metadata
            metadata = self.extract_metadata(text, file_path)

            # Create media source record in database with deterministic ID
            db = DatabaseService()

            # Use deterministic hash based on file path (like audio_processor)
            # This ensures re-processing the same file updates the existing record
            import hashlib

            path_hash = hashlib.md5(
                str(file_path.absolute()).encode(), usedforsecurity=False
            ).hexdigest()[:8]
            source_id = f"doc_{file_path.stem}_{path_hash}"

            # Check if source already exists
            existing_source = db.get_source(source_id)

            if existing_source:
                # Update existing source
                logger.info(f"Updating existing document source: {source_id}")
                db.update_source(
                    source_id,
                    title=metadata.title,
                    url=metadata.url or f"file://{file_path.absolute()}",
                    description=metadata.abstract,
                    author=", ".join(metadata.authors) if metadata.authors else None,
                    organization=metadata.organization,
                    processed_at=datetime.now(),
                )
                _media_record = existing_source
            else:
                # Create new source
                logger.info(f"Creating new document source: {source_id}")
                _media_record = db.create_source(
                    source_id=source_id,
                    title=metadata.title,
                    url=metadata.url or f"file://{file_path.absolute()}",
                    source_type="document",
                    description=metadata.abstract,
                    author=", ".join(metadata.authors) if metadata.authors else None,
                    organization=metadata.organization,
                    language="en",  # TODO: Detect language
                )

            # Create transcript record with full text
            transcript_record = db.create_transcript(
                source_id=source_id,
                text=text,
                language="en",  # TODO: Detect language
                source="document",
                metadata={
                    "word_count": len(text.split()),
                    "character_count": len(text),
                    "paragraph_count": len(re.findall(r"\n\n+", text)) + 1,
                },
            )

            return ProcessorResult(
                success=True,
                data={
                    "source_id": source_id,
                    "title": metadata.title,
                    "authors": metadata.authors,
                    "document_type": metadata.document_type,
                    "text": text,
                    "metadata": metadata.to_dict(),
                },
                metadata={
                    "processor": self.name,
                    "file_path": str(file_path),
                    "processing_time": datetime.now().isoformat(),
                    "db_records": {
                        "media_sources": media_id,
                        "transcripts": (
                            transcript_record.transcript_id
                            if transcript_record
                            else None
                        ),
                    },
                },
            )

        except Exception as e:
            logger.error(f"Document processing failed: {e}")
            return ProcessorResult(success=False, errors=[str(e)])

    def _process_pdf(self, file_path: Path) -> str:
        """Extract text from PDF file."""
        try:
            import PyPDF2

            text_parts = []
            with open(file_path, "rb") as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    text_parts.append(page.extract_text())

            return "\n".join(text_parts)

        except ImportError:
            # Fall back to pdfplumber if available
            try:
                import pdfplumber

                text_parts = []
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        text = page.extract_text()
                        if text:
                            text_parts.append(text)

                return "\n".join(text_parts)

            except ImportError:
                raise ImportError("PDF processing requires PyPDF2 or pdfplumber")

    def _process_docx(self, file_path: Path) -> str:
        """Extract text from DOCX file."""
        try:
            import docx

            doc = docx.Document(file_path)
            text_parts = []

            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_parts.append(paragraph.text)

            return "\n\n".join(text_parts)

        except ImportError:
            raise ImportError("DOCX processing requires python-docx")

    def _process_rtf(self, file_path: Path) -> str:
        """Extract text from RTF file."""
        try:
            import striprtf

            with open(file_path, encoding="utf-8") as file:
                rtf_content = file.read()

            return striprtf.rtf_to_text(rtf_content)

        except ImportError:
            # Basic RTF stripping
            with open(file_path, encoding="utf-8") as file:
                content = file.read()

            # Remove basic RTF formatting
            content = re.sub(r"\\[a-z]+\d*\s?", "", content)
            content = re.sub(r"[{}]", "", content)

            return content
