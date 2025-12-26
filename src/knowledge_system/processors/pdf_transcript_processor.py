"""
PDF Transcript Processor for Knowledge System.

Handles processing of PDF transcripts with speaker attribution, timestamp parsing,
and quality scoring. Designed to work with podcaster-provided transcripts that
have explicit speaker labels and formatting.
"""

import hashlib
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from ..database import DatabaseService
from ..logger import get_logger
from ..processors.base import BaseProcessor, ProcessorResult

logger = get_logger(__name__)


class PDFTranscriptMetadata:
    """Container for PDF transcript metadata."""

    def __init__(self):
        self.title: str | None = None
        self.speakers: list[str] = []
        self.date: datetime | None = None
        self.duration: int | None = None  # seconds
        self.episode_number: str | None = None
        self.show_name: str | None = None
        self.description: str | None = None
        self.page_count: int = 0
        self.has_timestamps: bool = False
        self.has_speaker_labels: bool = False
        self.speaker_format: str | None = None  # e.g., "Name:", "SPEAKER 1:", etc.

    def to_dict(self) -> dict[str, Any]:
        """Convert metadata to dictionary."""
        return {
            "title": self.title,
            "speakers": self.speakers,
            "date": self.date.isoformat() if self.date else None,
            "duration": self.duration,
            "episode_number": self.episode_number,
            "show_name": self.show_name,
            "description": self.description,
            "page_count": self.page_count,
            "has_timestamps": self.has_timestamps,
            "has_speaker_labels": self.has_speaker_labels,
            "speaker_format": self.speaker_format,
        }


class PDFTranscriptProcessor(BaseProcessor):
    """
    Process PDF transcripts with speaker attribution and YouTube matching.
    
    Features:
    - Extract text with speaker labels preserved
    - Parse timestamps if present
    - Extract metadata (title, date, speakers)
    - Calculate quality score
    - Match to YouTube videos (automatic or manual)
    """

    # Speaker label patterns (common formats in podcast transcripts)
    SPEAKER_PATTERNS = [
        r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*):\s*(.+)$",  # "John Doe: text"
        r"^\[([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\]:\s*(.+)$",  # "[John Doe]: text"
        r"^([A-Z\s]+):\s*(.+)$",  # "JOHN DOE: text"
        r"^SPEAKER\s+(\d+):\s*(.+)$",  # "SPEAKER 1: text"
        r"^Speaker\s+(\d+):\s*(.+)$",  # "Speaker 1: text"
    ]

    # Timestamp patterns
    TIMESTAMP_PATTERNS = [
        r"\[(\d{1,2}:\d{2}(?::\d{2})?)\]",  # [12:34] or [12:34:56]
        r"\((\d{1,2}:\d{2}(?::\d{2})?)\)",  # (12:34) or (12:34:56)
        r"^(\d{1,2}:\d{2}(?::\d{2})?)\s",  # 12:34 or 12:34:56 at start of line
    ]

    # Title patterns
    TITLE_PATTERNS = [
        r"^#\s+(.+)$",  # Markdown H1
        r"^Title:\s*(.+)$",  # Title: line
        r"^Episode:\s*(.+)$",  # Episode: line
        r"^(.+)\n[=]{3,}$",  # Underlined with =
    ]

    # Date patterns
    DATE_PATTERNS = [
        r"Date:\s*(\d{4}-\d{2}-\d{2})",  # Date: YYYY-MM-DD
        r"Date:\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4})",
        r"(\d{4}-\d{2}-\d{2})",  # YYYY-MM-DD anywhere
        r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4})",
    ]

    def __init__(self, db_service: DatabaseService = None):
        """Initialize PDF transcript processor."""
        super().__init__()
        self.db_service = db_service or DatabaseService()

    @property
    def name(self) -> str:
        """Return processor name."""
        return "pdf_transcript_processor"

    def validate(self, input_data: Any) -> None:
        """Validate input PDF file."""
        file_path = Path(input_data)
        if not file_path.exists():
            raise ValueError(f"PDF file not found: {file_path}")
        if file_path.suffix.lower() != ".pdf":
            raise ValueError(f"Not a PDF file: {file_path}")

    def process(
        self,
        input_data: Any,
        youtube_url: str = None,
        source_id: str = None,
        **kwargs: Any
    ) -> ProcessorResult:
        """
        Process a PDF transcript file.
        
        Args:
            input_data: Path to PDF file
            youtube_url: Optional YouTube URL to link to
            source_id: Optional source_id if already known
            **kwargs: Additional arguments
        
        Returns:
            ProcessorResult with transcript data and metadata
        """
        try:
            file_path = Path(input_data)
            self.validate(file_path)

            logger.info(f"Processing PDF transcript: {file_path.name}")

            # Extract text from PDF
            text = self._extract_pdf_text(file_path)
            if not text:
                return ProcessorResult(
                    success=False,
                    errors=["Failed to extract text from PDF"]
                )

            # Extract metadata
            metadata = self._extract_metadata(text, file_path)
            
            # Parse speaker labels
            speaker_data = self._extract_speaker_labels(text)
            metadata.has_speaker_labels = speaker_data["has_speakers"]
            metadata.speakers = speaker_data["speakers"]
            metadata.speaker_format = speaker_data["format"]
            
            # Parse timestamps
            timestamp_data = self._parse_timestamps(text)
            metadata.has_timestamps = timestamp_data["has_timestamps"]
            
            # Calculate quality score
            quality_score = self._calculate_quality_score(metadata, text)
            
            # Generate or use provided source_id
            if not source_id:
                if youtube_url:
                    # Extract video ID from URL
                    source_id = self._extract_youtube_id(youtube_url)
                else:
                    # Generate deterministic ID based on file path
                    path_hash = hashlib.md5(
                        str(file_path.absolute()).encode(),
                        usedforsecurity=False
                    ).hexdigest()[:8]
                    source_id = f"pdf_{file_path.stem}_{path_hash}"
            
            # Store transcript in database
            transcript_id = str(uuid.uuid4())
            
            # Create or update media source
            existing_source = self.db_service.get_source(source_id)
            if existing_source:
                logger.info(f"Found existing source: {source_id}")
            else:
                # Create new source record
                logger.info(f"Creating new source: {source_id}")
                self.db_service.create_source(
                    source_id=source_id,
                    title=metadata.title or file_path.stem,
                    url=youtube_url or f"file://{file_path.absolute()}",
                    source_type="youtube" if youtube_url else "document",
                    description=metadata.description,
                    author=", ".join(metadata.speakers) if metadata.speakers else None,
                    duration_seconds=metadata.duration,
                    language="en",
                )
            
            # Create transcript record
            transcript_segments = []
            if timestamp_data["has_timestamps"]:
                transcript_segments = timestamp_data["segments"]
            else:
                # Create single segment with full text
                transcript_segments = [{
                    "start": "00:00",
                    "end": "00:00",
                    "text": text,
                    "duration": 0
                }]
            
            transcript_record = self.db_service.create_transcript(
                source_id=source_id,
                text=text,
                language="en",
                source="pdf_provided",
                metadata={
                    "transcript_type": "pdf_provided",
                    "quality_score": quality_score,
                    "has_speaker_labels": metadata.has_speaker_labels,
                    "has_timestamps": metadata.has_timestamps,
                    "source_file_path": str(file_path.absolute()),
                    "extraction_metadata": metadata.to_dict(),
                    "speakers": metadata.speakers,
                    "speaker_format": metadata.speaker_format,
                    "page_count": metadata.page_count,
                }
            )
            
            logger.info(
                f"✅ PDF transcript processed: {file_path.name} "
                f"(quality: {quality_score:.2f}, speakers: {len(metadata.speakers)}, "
                f"timestamps: {metadata.has_timestamps})"
            )
            
            return ProcessorResult(
                success=True,
                data={
                    "source_id": source_id,
                    "transcript_id": transcript_record.transcript_id if transcript_record else transcript_id,
                    "title": metadata.title,
                    "text": text,
                    "metadata": metadata.to_dict(),
                    "quality_score": quality_score,
                    "has_speaker_labels": metadata.has_speaker_labels,
                    "has_timestamps": metadata.has_timestamps,
                    "speakers": metadata.speakers,
                },
                metadata={
                    "processor": self.name,
                    "file_path": str(file_path),
                    "processing_time": datetime.now().isoformat(),
                    "quality_score": quality_score,
                }
            )

        except Exception as e:
            logger.error(f"PDF transcript processing failed: {e}", exc_info=True)
            return ProcessorResult(success=False, errors=[str(e)])

    def _extract_pdf_text(self, file_path: Path) -> str:
        """Extract text from PDF file."""
        try:
            import PyPDF2
            
            text_parts = []
            page_count = 0
            
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                page_count = len(pdf_reader.pages)
                
                for page in pdf_reader.pages:
                    text_parts.append(page.extract_text())
            
            text = "\n".join(text_parts)
            logger.debug(f"Extracted {len(text)} characters from {page_count} pages")
            
            return text
            
        except ImportError:
            logger.error("PyPDF2 not installed. Install with: pip install PyPDF2")
            return ""
        except Exception as e:
            logger.error(f"Failed to extract PDF text: {e}")
            return ""

    def _extract_metadata(self, text: str, file_path: Path) -> PDFTranscriptMetadata:
        """Extract metadata from transcript text."""
        metadata = PDFTranscriptMetadata()
        
        # Extract title
        lines = text.split('\n')
        for i, line in enumerate(lines[:20]):  # Check first 20 lines
            line = line.strip()
            if not line:
                continue
                
            for pattern in self.TITLE_PATTERNS:
                match = re.search(pattern, line, re.MULTILINE)
                if match:
                    metadata.title = match.group(1).strip()
                    break
            
            if metadata.title:
                break
        
        # If no title found, use filename
        if not metadata.title:
            metadata.title = file_path.stem.replace('_', ' ').replace('-', ' ')
        
        # Extract date
        for pattern in self.DATE_PATTERNS:
            match = re.search(pattern, text[:2000])  # Check first 2000 chars
            if match:
                date_str = match.group(1)
                try:
                    # Try parsing different date formats
                    for fmt in ["%Y-%m-%d", "%B %d, %Y", "%b %d, %Y"]:
                        try:
                            metadata.date = datetime.strptime(date_str, fmt)
                            break
                        except ValueError:
                            continue
                except Exception:
                    pass
                break
        
        return metadata

    def _extract_speaker_labels(self, text: str) -> dict[str, Any]:
        """
        Extract speaker labels from transcript.
        
        Returns:
            dict with keys: has_speakers, speakers (list), format (str)
        """
        speakers = set()
        speaker_format = None
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            for pattern in self.SPEAKER_PATTERNS:
                match = re.match(pattern, line)
                if match:
                    speaker_name = match.group(1).strip()
                    speakers.add(speaker_name)
                    if not speaker_format:
                        speaker_format = pattern
                    break
        
        return {
            "has_speakers": len(speakers) > 0,
            "speakers": sorted(list(speakers)),
            "format": speaker_format if speaker_format else None,
        }

    def _parse_timestamps(self, text: str) -> dict[str, Any]:
        """
        Parse timestamps from transcript.
        
        Returns:
            dict with keys: has_timestamps, segments (list)
        """
        timestamps = []
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            for pattern in self.TIMESTAMP_PATTERNS:
                match = re.search(pattern, line)
                if match:
                    timestamps.append(match.group(1))
                    break
        
        has_timestamps = len(timestamps) > 0
        
        # Create segments if timestamps found
        segments = []
        if has_timestamps:
            # Simple segmentation based on timestamps
            # This is a basic implementation - could be enhanced
            for i, ts in enumerate(timestamps):
                segments.append({
                    "start": ts,
                    "end": timestamps[i+1] if i+1 < len(timestamps) else ts,
                    "text": "",  # Would need more sophisticated parsing
                    "duration": 0,
                })
        
        return {
            "has_timestamps": has_timestamps,
            "segments": segments,
        }

    def _calculate_quality_score(self, metadata: PDFTranscriptMetadata, text: str) -> float:
        """
        Calculate quality score for transcript.
        
        Factors:
        - Has speaker labels: +0.3
        - Has timestamps: +0.2
        - Formatting quality: +0.3
        - Length/completeness: +0.2
        """
        score = 0.0
        
        # Speaker labels
        if metadata.has_speaker_labels:
            score += 0.3
        
        # Timestamps
        if metadata.has_timestamps:
            score += 0.2
        
        # Formatting quality (check for paragraph breaks, proper spacing)
        lines = text.split('\n')
        non_empty_lines = [l for l in lines if l.strip()]
        if len(non_empty_lines) > 10:
            # Check for paragraph breaks
            paragraph_breaks = text.count('\n\n')
            if paragraph_breaks > 5:
                score += 0.15
            
            # Check for consistent formatting
            avg_line_length = sum(len(l) for l in non_empty_lines) / len(non_empty_lines)
            if 50 < avg_line_length < 200:  # Reasonable line length
                score += 0.15
        
        # Length/completeness
        word_count = len(text.split())
        if word_count > 1000:
            score += 0.2
        elif word_count > 500:
            score += 0.1
        
        return min(score, 1.0)  # Cap at 1.0

    def _extract_youtube_id(self, youtube_url: str) -> str:
        """Extract YouTube video ID from URL."""
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, youtube_url)
            if match:
                return match.group(1)
        
        # If no match, return a hash of the URL
        return hashlib.md5(youtube_url.encode(), usedforsecurity=False).hexdigest()[:11]

