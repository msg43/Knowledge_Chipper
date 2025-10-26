"""
Parameterized summarization input tests.

Tests all input types with provider=Ollama, model=qwen2.5:7b-instruct:
- .md (markdown)
- .pdf
- .txt (plain text)
- .docx (Word document)
- .html/.htm
- .json
- .rtf

Uses default prompts (flagship/mining).
"""

import os
from pathlib import Path

import pytest

# Set testing mode before any imports
os.environ["KNOWLEDGE_CHIPPER_TESTING_MODE"] = "1"
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication

from .utils import (
    DBValidator,
    add_file_to_summarize,
    check_ollama_running,
    create_sandbox,
    get_summarize_tab,
    process_events_for,
    read_markdown_with_frontmatter,
    switch_to_tab,
    wait_for_completion,
)


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def test_sandbox(tmp_path):
    """Create isolated test sandbox with DB and output dirs."""
    sandbox = create_sandbox(tmp_path / "sandbox")
    yield sandbox


@pytest.fixture
def gui_app(qapp, test_sandbox):
    """Launch GUI with test sandbox."""
    from knowledge_system.gui.main_window_pyqt6 import MainWindow

    window = MainWindow()
    window.show()
    process_events_for(500)

    yield window

    window.close()
    process_events_for(200)


@pytest.fixture
def sample_md_file():
    """Path to sample markdown transcript."""
    return (
        Path(__file__).parent.parent
        / "fixtures"
        / "sample_files"
        / "sample_transcript.md"
    )


@pytest.fixture
def sample_txt_file():
    """Path to sample text document."""
    return (
        Path(__file__).parent.parent
        / "fixtures"
        / "sample_files"
        / "sample_document.txt"
    )


class TestSummarizeInputs:
    """Test all summarization input types."""

    def test_markdown_input(self, gui_app, test_sandbox, sample_md_file):
        """Test REAL summarization of a markdown file using Ollama."""
        # 1. Check Ollama is running
        if not check_ollama_running():
            pytest.fail(
                "Ollama must be running for this test. Start with: ollama serve"
            )

        # 2. Switch to Summarize tab
        assert switch_to_tab(gui_app, "Summarize"), "Failed to switch to Summarize tab"
        process_events_for(500)

        summarize_tab = get_summarize_tab(gui_app)
        assert summarize_tab is not None, "Could not find Summarize tab"

        # 3. Add markdown file
        assert sample_md_file.exists(), f"Sample file not found: {sample_md_file}"
        success = add_file_to_summarize(summarize_tab, sample_md_file)
        assert success, "Failed to add markdown file to summarization queue"
        process_events_for(200)

        # 4. Start summarization
        assert hasattr(summarize_tab, "start_btn"), "Summarize tab has no start_btn"
        summarize_tab.start_btn.click()
        process_events_for(500)

        # 5. Wait for REAL Ollama processing (30-90 seconds depending on model and content)
        print("⏳ Waiting for real Ollama summarization (this may take 1-2 minutes)...")
        success = wait_for_completion(summarize_tab, timeout_seconds=120)
        assert success, "Summarization did not complete within 2 minutes"

        # 6. Validate database
        db = DBValidator(test_sandbox.db_path)
        summaries = db.get_all_summaries()
        assert len(summaries) > 0, "No summary record created in database"

        summary = summaries[0]
        assert (
            summary.get("llm_provider") == "ollama"
        ), f"Expected ollama provider, got {summary.get('llm_provider')}"
        assert len(summary.get("summary_text", "")) > 0, "Summary text is empty"

        # Validate schema
        errors = db.validate_summary_schema(summary)
        if errors:
            print(f"⚠️  Schema validation warnings: {errors}")

        # 7. Validate markdown file
        md_files = list(test_sandbox.output_dir.glob("**/*.md"))
        assert (
            len(md_files) > 0
        ), f"No markdown files created in {test_sandbox.output_dir}"

        # Find summary markdown
        summary_md = None
        for md_file in md_files:
            if (
                "summary" in md_file.stem.lower()
                or "summar" in md_file.parent.name.lower()
            ):
                summary_md = md_file
                break

        if summary_md:
            frontmatter, body = read_markdown_with_frontmatter(summary_md)
            assert (
                "llm_provider" in frontmatter or "title" in frontmatter
            ), "Markdown missing required frontmatter"
            assert len(body) > 50, f"Summary body too short: {len(body)} chars"
            print(f"   Markdown: {summary_md.name}")

        print(f"✅ Test passed: {len(summary['summary_text'])} chars summarized")

    def test_pdf_input(self, gui_app, test_sandbox):
        """Test REAL summarization of a PDF file using Ollama."""
        # Check Ollama
        if not check_ollama_running():
            pytest.fail("Ollama must be running for this test")

        # Switch to Summarize tab
        assert switch_to_tab(gui_app, "Summarize"), "Failed to switch to Summarize tab"
        process_events_for(500)

        summarize_tab = get_summarize_tab(gui_app)
        assert summarize_tab is not None, "Could not find Summarize tab"

        # Use KenRogoff PDF from main directory
        pdf_file = Path(
            "/Users/matthewgreer/Projects/Knowledge_Chipper/KenRogoff_Transcript.pdf"
        )
        assert pdf_file.exists(), f"PDF file not found: {pdf_file}"

        success = add_file_to_summarize(summarize_tab, pdf_file)
        assert success, "Failed to add PDF file"
        process_events_for(200)

        # Start summarization
        summarize_tab.start_btn.click()
        process_events_for(500)

        # Wait for processing
        print("⏳ Waiting for PDF summarization...")
        success = wait_for_completion(summarize_tab, timeout_seconds=180)
        assert success, "Summarization did not complete"

        # Validate database
        db = DBValidator(test_sandbox.db_path)
        summaries = db.get_all_summaries()
        assert len(summaries) > 0, "No summary created"
        assert len(summaries[0].get("summary_text", "")) > 0, "Summary empty"

        print(f"✅ PDF summarization test passed")

    def test_text_input(self, gui_app, test_sandbox, sample_txt_file):
        """Test REAL summarization of a plain text file using Ollama."""
        # Check Ollama
        if not check_ollama_running():
            pytest.fail("Ollama must be running for this test")

        # Switch to Summarize tab
        assert switch_to_tab(gui_app, "Summarize"), "Failed to switch to Summarize tab"
        process_events_for(500)

        summarize_tab = get_summarize_tab(gui_app)
        assert summarize_tab is not None, "Could not find Summarize tab"

        # Add text file
        assert sample_txt_file.exists(), f"Sample file not found: {sample_txt_file}"
        success = add_file_to_summarize(summarize_tab, sample_txt_file)
        assert success, "Failed to add text file"
        process_events_for(200)

        # Start summarization
        summarize_tab.start_btn.click()
        process_events_for(500)

        # Wait for processing
        print("⏳ Waiting for text summarization...")
        success = wait_for_completion(summarize_tab, timeout_seconds=120)
        assert success, "Summarization did not complete"

        # Validate database
        db = DBValidator(test_sandbox.db_path)
        summaries = db.get_all_summaries()
        assert len(summaries) > 0, "No summary created"
        assert len(summaries[0].get("summary_text", "")) > 0, "Summary empty"

        print(f"✅ Text summarization test passed")

    def test_docx_input(self, gui_app, test_sandbox):
        """Test REAL summarization of a DOCX file using Ollama."""
        # Check Ollama
        if not check_ollama_running():
            pytest.fail("Ollama must be running for this test")

        # Switch to Summarize tab
        assert switch_to_tab(gui_app, "Summarize"), "Failed to switch to Summarize tab"
        process_events_for(500)

        summarize_tab = get_summarize_tab(gui_app)
        assert summarize_tab is not None, "Could not find Summarize tab"

        # Use KenRogoff DOCX from main directory
        docx_file = Path(
            "/Users/matthewgreer/Projects/Knowledge_Chipper/KenRogoff_Transcript.docx"
        )
        assert docx_file.exists(), f"DOCX file not found: {docx_file}"

        success = add_file_to_summarize(summarize_tab, docx_file)
        assert success, "Failed to add DOCX file"
        process_events_for(200)

        # Start summarization
        summarize_tab.start_btn.click()
        process_events_for(500)

        # Wait for processing
        print("⏳ Waiting for DOCX summarization...")
        success = wait_for_completion(summarize_tab, timeout_seconds=180)
        assert success, "Summarization did not complete"

        # Validate database
        db = DBValidator(test_sandbox.db_path)
        summaries = db.get_all_summaries()
        assert len(summaries) > 0, "No summary created"
        assert len(summaries[0].get("summary_text", "")) > 0, "Summary empty"

        print(f"✅ DOCX summarization test passed")

    def test_html_input(self, gui_app, test_sandbox):
        """Test REAL summarization of an HTML file using Ollama."""
        # Check Ollama
        if not check_ollama_running():
            pytest.fail("Ollama must be running for this test")

        # Switch to Summarize tab
        assert switch_to_tab(gui_app, "Summarize"), "Failed to switch to Summarize tab"
        process_events_for(500)

        summarize_tab = get_summarize_tab(gui_app)
        assert summarize_tab is not None, "Could not find Summarize tab"

        # Add HTML file
        html_file = (
            Path(__file__).parent.parent / "fixtures/sample_files/sample_document.html"
        )
        assert html_file.exists(), f"Sample HTML file not found: {html_file}"

        success = add_file_to_summarize(summarize_tab, html_file)
        assert success, "Failed to add HTML file"
        process_events_for(200)

        # Start summarization
        summarize_tab.start_btn.click()
        process_events_for(500)

        # Wait for processing
        print("⏳ Waiting for HTML summarization...")
        success = wait_for_completion(summarize_tab, timeout_seconds=120)
        assert success, "Summarization did not complete"

        # Validate database
        db = DBValidator(test_sandbox.db_path)
        summaries = db.get_all_summaries()
        assert len(summaries) > 0, "No summary created"
        assert len(summaries[0].get("summary_text", "")) > 0, "Summary empty"

        print(f"✅ HTML summarization test passed")

    def test_json_input(self, gui_app, test_sandbox):
        """Test REAL summarization of a JSON file using Ollama."""
        # Check Ollama
        if not check_ollama_running():
            pytest.fail("Ollama must be running for this test")

        # Switch to Summarize tab
        assert switch_to_tab(gui_app, "Summarize"), "Failed to switch to Summarize tab"
        process_events_for(500)

        summarize_tab = get_summarize_tab(gui_app)
        assert summarize_tab is not None, "Could not find Summarize tab"

        # Add JSON file
        json_file = (
            Path(__file__).parent.parent / "fixtures/sample_files/sample_document.json"
        )
        assert json_file.exists(), f"Sample JSON file not found: {json_file}"

        success = add_file_to_summarize(summarize_tab, json_file)
        assert success, "Failed to add JSON file"
        process_events_for(200)

        # Start summarization
        summarize_tab.start_btn.click()
        process_events_for(500)

        # Wait for processing
        print("⏳ Waiting for JSON summarization...")
        success = wait_for_completion(summarize_tab, timeout_seconds=120)
        assert success, "Summarization did not complete"

        # Validate database
        db = DBValidator(test_sandbox.db_path)
        summaries = db.get_all_summaries()
        assert len(summaries) > 0, "No summary created"
        assert len(summaries[0].get("summary_text", "")) > 0, "Summary empty"

        print(f"✅ JSON summarization test passed")

    def test_rtf_input(self, gui_app, test_sandbox):
        """Test REAL summarization of an RTF file using Ollama."""
        # Check Ollama
        if not check_ollama_running():
            pytest.fail("Ollama must be running for this test")

        # Switch to Summarize tab
        assert switch_to_tab(gui_app, "Summarize"), "Failed to switch to Summarize tab"
        process_events_for(500)

        summarize_tab = get_summarize_tab(gui_app)
        assert summarize_tab is not None, "Could not find Summarize tab"

        # Use KenRogoff RTF from main directory
        rtf_file = Path(
            "/Users/matthewgreer/Projects/Knowledge_Chipper/KenRogoff_Transcript.rtf"
        )
        assert rtf_file.exists(), f"RTF file not found: {rtf_file}"

        success = add_file_to_summarize(summarize_tab, rtf_file)
        assert success, "Failed to add RTF file"
        process_events_for(200)

        # Start summarization
        summarize_tab.start_btn.click()
        process_events_for(500)

        # Wait for processing
        print("⏳ Waiting for RTF summarization...")
        success = wait_for_completion(summarize_tab, timeout_seconds=180)
        assert success, "Summarization did not complete"

        # Validate database
        db = DBValidator(test_sandbox.db_path)
        summaries = db.get_all_summaries()
        assert len(summaries) > 0, "No summary created"
        assert len(summaries[0].get("summary_text", "")) > 0, "Summary empty"

        print(f"✅ RTF summarization test passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
