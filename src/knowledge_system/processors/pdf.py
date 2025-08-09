""" PDF Processor.
PDF Processor

Extracts text from PDF files using PyPDF2 and pdfplumber.
Handles single files and folders, returns text, page count, and metadata.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pdfplumber
import PyPDF2

from ..errors import ProcessingError
from ..logger import get_logger
from .base import BaseProcessor, ProcessorResult

logger = get_logger(__name__)


class PDFProcessor(BaseProcessor):
    """ Processor for extracting text from PDF files or folders.""".

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name or "pdf_processor")

    @property
    def supported_formats(self) -> list[str]:
        return [".pdf"]

    def validate_input(self, input_data: Any) -> bool:
        if isinstance(input_data, (str, Path)):
            path = Path(input_data)
            if path.is_file() and path.suffix.lower() == ".pdf":
                return True
            if path.is_dir():
                return any(f.suffix.lower() == ".pdf" for f in path.iterdir())
        return False

    def _extract_text_pypdf2(self, pdf_path: Path) -> dict[str, Any]:
        try:
            with open(pdf_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                if reader.is_encrypted:
                    try:
                        reader.decrypt("")
                    except Exception:
                        return {"error": "Encrypted PDF"}
                text = ""
                for page in reader.pages:
                    try:
                        text += page.extract_text() or ""
                    except Exception:
                        continue
                return {
                    "text": text,
                    "page_count": len(reader.pages),
                    "metadata": reader.metadata,
                }
        except Exception as e:
            logger.error(f"PyPDF2 failed: {e}")
            return {"error": str(e)}

    def _extract_text_pdfplumber(self, pdf_path: Path) -> dict[str, Any]:
        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
                return {
                    "text": text,
                    "page_count": len(pdf.pages),
                    "metadata": pdf.metadata,
                }
        except Exception as e:
            logger.error(f"pdfplumber failed: {e}")
            return {"error": str(e)}

    def process(
        self, input_data: Any, dry_run: bool = False, **kwargs: Any
    ) -> ProcessorResult:
        paths = []
        if isinstance(input_data, (str, Path)):
            path = Path(input_data)
            logger.info(
                f"PDF Processor received input: {path} (type: {type(input_data)})"
            )
            logger.info(f"PDF Processor absolute path: {path.absolute()}")
            logger.info(f"PDF Processor path exists: {path.exists()}")

            if path.is_file() and path.suffix.lower() == ".pdf":
                paths = [path]
            elif path.is_dir():
                paths = [f for f in path.iterdir() if f.suffix.lower() == ".pdf"]

        logger.info(
            f"PDF Processor will process {len(paths)} files: {[str(p) for p in paths]}"
        )

        if not paths:
            return ProcessorResult(
                success=False, errors=["No PDF files found in input"]
            )

        results = []
        errors = []

        for pdf_path in paths:
            logger.info(f"Processing PDF file: {pdf_path.absolute()}")
            logger.info(
                f"PDF file size: {pdf_path.stat().st_size if pdf_path.exists() else 'File not found'}"
            )

            # Try PyPDF2 first
            result = self._extract_text_pypdf2(pdf_path)
            if result.get("error") or not result.get("text"):
                # Fallback to pdfplumber
                result = self._extract_text_pdfplumber(pdf_path)

            if result.get("error") or not result.get("text"):
                errors.append(
                    f"Failed to extract from {pdf_path}: {result.get('error', 'No text extracted')}"
                )
                continue

            # Log first 200 characters of extracted text for debugging
            text_preview = result["text"][:200] if result["text"] else "No text"
            logger.info(
                f"Extracted text preview from {pdf_path.name}: {text_preview}..."
            )
            logger.info(f"Total text length: {len(result['text'])} characters")

            results.append(
                {
                    "file": str(pdf_path),
                    "text": result["text"],
                    "page_count": result["page_count"],
                    "metadata": result.get("metadata", {}),
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


def fetch_pdf_text(pdf_path: str | Path) -> str:
    """ Convenience function to extract text from a single PDF file.""".
    processor = PDFProcessor()
    result = processor.process(pdf_path)
    if not result.success:
        raise ProcessingError(f"Failed to extract PDF text: {result.errors}")
    results = result.data.get("results", [])
    if not results:
        raise ProcessingError("No text extracted from PDF")
    text_result = results[0]["text"]
    return str(text_result) if text_result is not None else ""
