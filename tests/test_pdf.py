"""
Tests for PDF Processor.

Covers text extraction, error handling, batch/folder processing, and fetch_pdf_text.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from knowledge_system.errors import ProcessingError
from knowledge_system.processors.pdf import PDFProcessor, fetch_pdf_text


class TestPDFProcessor:
    def setup_method(self):
        self.processor = PDFProcessor()

    def test_supported_formats(self):
        assert ".pdf" in self.processor.supported_formats

    def test_validate_input_pdf_file(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            temp_file = f.name
        try:
            assert self.processor.validate_input(temp_file) is True
        finally:
            Path(temp_file).unlink()

    def test_validate_input_folder(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "file.pdf"
            pdf_path.touch()
            assert self.processor.validate_input(tmpdir) is True

    def test_validate_input_invalid(self):
        assert self.processor.validate_input("not_a_pdf.txt") is False
        assert self.processor.validate_input(123) is False

    @patch("PyPDF2.PdfReader")
    def test_extract_text_pypdf2_success(self, mock_reader):
        mock_page = Mock()
        mock_page.extract_text.return_value = "Hello PDF"
        mock_reader.return_value.pages = [mock_page]
        mock_reader.return_value.is_encrypted = False
        mock_reader.return_value.metadata = {"author": "Test"}
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            temp_file = Path(f.name)
        try:
            result = self.processor._extract_text_pypdf2(temp_file)
            assert result["text"] == "Hello PDF"
            assert result["page_count"] == 1
            assert result["metadata"]["author"] == "Test"
        finally:
            temp_file.unlink()

    @patch("pdfplumber.open")
    def test_extract_text_pdfplumber_success(self, mock_open):
        mock_pdf = Mock()
        mock_page = Mock()
        mock_page.extract_text.return_value = "Hello PDFPlumber"
        mock_pdf.pages = [mock_page]
        mock_pdf.metadata = {"author": "Plumber"}
        mock_open.return_value.__enter__.return_value = mock_pdf
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            temp_file = Path(f.name)
        try:
            result = self.processor._extract_text_pdfplumber(temp_file)
            assert "Hello PDFPlumber" in result["text"]
            assert result["page_count"] == 1
            assert result["metadata"]["author"] == "Plumber"
        finally:
            temp_file.unlink()

    @patch("PyPDF2.PdfReader")
    def test_extract_text_pypdf2_encrypted(self, mock_reader):
        mock_reader.return_value.is_encrypted = True
        mock_reader.return_value.decrypt.side_effect = Exception("Encrypted!")
        mock_reader.return_value.pages = []
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            temp_file = Path(f.name)
        try:
            result = self.processor._extract_text_pypdf2(temp_file)
            assert "error" in result
        finally:
            temp_file.unlink()

    @patch("PyPDF2.PdfReader")
    def test_extract_text_pypdf2_corrupt(self, mock_reader):
        mock_reader.side_effect = Exception("Corrupt PDF")
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            temp_file = Path(f.name)
        try:
            result = self.processor._extract_text_pypdf2(temp_file)
            assert "error" in result
        finally:
            temp_file.unlink()

    @patch("PyPDF2.PdfReader")
    @patch("pdfplumber.open")
    def test_process_single_pdf_success(self, mock_pdfplumber_open, mock_pypdf2_reader):
        # PyPDF2 fails, pdfplumber succeeds
        mock_pypdf2_reader.return_value.pages = []
        mock_pypdf2_reader.return_value.is_encrypted = False
        mock_pypdf2_reader.return_value.metadata = {}
        mock_pypdf2_reader.return_value.pages = []
        mock_pypdf2_reader.return_value.__bool__.return_value = False
        mock_pypdf2_reader.return_value.__len__.return_value = 0
        mock_pypdf2_reader.return_value.extract_text = Mock(return_value=None)
        mock_pdf = Mock()
        mock_page = Mock()
        mock_page.extract_text.return_value = "Hello PDFPlumber"
        mock_pdf.pages = [mock_page]
        mock_pdf.metadata = {"author": "Plumber"}
        mock_pdfplumber_open.return_value.__enter__.return_value = mock_pdf
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            temp_file = Path(f.name)
        try:
            result = self.processor.process(temp_file)
            assert result.success is True
            assert result.data["count"] == 1
            assert "Hello PDFPlumber" in result.data["results"][0]["text"]
        finally:
            temp_file.unlink()

    @patch("PyPDF2.PdfReader")
    @patch("pdfplumber.open")
    def test_process_batch_folder(self, mock_pdfplumber_open, mock_pypdf2_reader):
        # Both extractors succeed
        mock_pypdf2_reader.return_value.pages = []
        mock_pypdf2_reader.return_value.is_encrypted = False
        mock_pypdf2_reader.return_value.metadata = {}
        mock_pdf = Mock()
        mock_page = Mock()
        mock_page.extract_text.return_value = "Batch PDF"
        mock_pdf.pages = [mock_page]
        mock_pdf.metadata = {"author": "Batch"}
        mock_pdfplumber_open.return_value.__enter__.return_value = mock_pdf
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf1 = Path(tmpdir) / "a.pdf"
            pdf2 = Path(tmpdir) / "b.pdf"
            pdf1.touch()
            pdf2.touch()
            result = self.processor.process(tmpdir)
            assert result.success is True
            assert result.data["count"] == 2

    def test_process_no_pdfs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.processor.process(tmpdir)
            assert result.success is False
            assert "No PDF files found" in result.errors[0]


class TestFetchPDFText:
    @patch("knowledge_system.processors.pdf.PDFProcessor")
    def test_fetch_pdf_text_success(self, mock_proc_class):
        mock_proc = Mock()
        mock_result = Mock()
        mock_result.success = True
        mock_result.data = {"results": [{"text": "Hello PDF"}]}
        mock_proc.process.return_value = mock_result
        mock_proc_class.return_value = mock_proc
        out = fetch_pdf_text("/tmp/file.pdf")
        assert out == "Hello PDF"

    @patch("knowledge_system.processors.pdf.PDFProcessor")
    def test_fetch_pdf_text_failure(self, mock_proc_class):
        mock_proc = Mock()
        mock_result = Mock()
        mock_result.success = False
        mock_result.errors = ["Corrupt"]
        mock_proc.process.return_value = mock_result
        mock_proc_class.return_value = mock_proc
        with pytest.raises(ProcessingError, match="Failed to extract PDF text"):
            fetch_pdf_text("/tmp/file.pdf")

    @patch("knowledge_system.processors.pdf.PDFProcessor")
    def test_fetch_pdf_text_no_text(self, mock_proc_class):
        mock_proc = Mock()
        mock_result = Mock()
        mock_result.success = True
        mock_result.data = {"results": []}
        mock_proc.process.return_value = mock_result
        mock_proc_class.return_value = mock_proc
        with pytest.raises(ProcessingError, match="No text extracted from PDF"):
            fetch_pdf_text("/tmp/file.pdf")
