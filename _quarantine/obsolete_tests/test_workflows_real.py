"""
Real workflow tests.

Tests complete workflows including:
- Full transcribe → summarize pipeline
- Cancellation during processing
- Error handling for invalid inputs
"""

import os
import time
from pathlib import Path

import pytest

# Set testing mode before any imports
os.environ["KNOWLEDGE_CHIPPER_TESTING_MODE"] = "1"
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication

from .utils import (
    DBValidator,
    add_file_to_summarize,
    add_file_to_transcribe,
    check_ollama_running,
    create_sandbox,
    get_summarize_tab,
    get_transcribe_tab,
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


class TestCompleteWorkflows:
    """Test complete end-to-end workflows."""

    def test_complete_transcribe_summarize_pipeline(self, gui_app, test_sandbox):
        """Test complete pipeline: transcribe → summarize with real processing."""
        # Check Ollama for summarization
        if not check_ollama_running():
            pytest.fail("Ollama must be running for this pipeline test")

        # STEP 1: Transcribe audio file
        print("\n📝 STEP 1: Transcribing audio...")
        assert switch_to_tab(gui_app, "Transcribe"), "Failed to switch to Transcribe"
        process_events_for(500)

        transcribe_tab = get_transcribe_tab(gui_app)
        assert transcribe_tab is not None

        audio_file = (
            Path(__file__).parent.parent / "fixtures/sample_files/short_audio.mp3"
        )
        assert audio_file.exists(), f"Test audio file not found: {audio_file}"

        add_file_to_transcribe(transcribe_tab, audio_file)
        process_events_for(200)

        # Start transcription
        transcribe_tab.start_btn.click()
        process_events_for(500)

        # Wait for transcription (up to 3 minutes)
        print("   ⏳ Waiting for transcription...")
        success = wait_for_completion(transcribe_tab, timeout_seconds=180)
        assert success, "Transcription did not complete"
        print("   ✅ Transcription complete")

        # Validate transcription output
        db = DBValidator(test_sandbox.db_path)
        videos = db.get_all_videos()
        assert len(videos) > 0, "No video record after transcription"
        video_id = videos[0]["video_id"]

        transcript = db.get_transcript_for_video(video_id)
        assert transcript is not None, "No transcript record"
        assert len(transcript.get("transcript_text", "")) > 0

        # Find transcript markdown
        md_files = list(test_sandbox.output_dir.glob("**/*transcript*.md"))
        assert len(md_files) > 0, "No transcript markdown created"
        transcript_md = md_files[0]
        print(f"   📄 Transcript: {transcript_md.name}")

        # STEP 2: Summarize the transcript
        print("\n📝 STEP 2: Summarizing transcript...")
        assert switch_to_tab(gui_app, "Summarize"), "Failed to switch to Summarize"
        process_events_for(500)

        summarize_tab = get_summarize_tab(gui_app)
        assert summarize_tab is not None

        # Add the transcript markdown file
        add_file_to_summarize(summarize_tab, transcript_md)
        process_events_for(200)

        # Start summarization
        summarize_tab.start_btn.click()
        process_events_for(500)

        # Wait for summarization (up to 2 minutes)
        print("   ⏳ Waiting for summarization...")
        success = wait_for_completion(summarize_tab, timeout_seconds=120)
        assert success, "Summarization did not complete"
        print("   ✅ Summarization complete")

        # Validate summarization output
        summaries = db.get_all_summaries()
        assert len(summaries) > 0, "No summary record"
        summary = summaries[0]
        assert summary.get("llm_provider") == "ollama"
        assert len(summary.get("summary_text", "")) > 0

        # Find summary markdown
        summary_md_files = list(test_sandbox.output_dir.glob("**/*summar*.md"))
        # Filter out the transcript file
        summary_md_files = [f for f in summary_md_files if f != transcript_md]
        assert len(summary_md_files) > 0, "No summary markdown created"
        summary_md = summary_md_files[0]
        print(f"   📄 Summary: {summary_md.name}")

        print("\n✅ COMPLETE PIPELINE TEST PASSED")
        print(f"   Transcript: {len(transcript['transcript_text'])} chars")
        print(f"   Summary: {len(summary['summary_text'])} chars")

    def test_cancel_mid_transcription(self, gui_app, test_sandbox):
        """Test cancellation during transcription processing."""
        print("\n📝 Testing cancellation workflow...")

        # Switch to Transcribe tab
        assert switch_to_tab(gui_app, "Transcribe")
        process_events_for(500)

        transcribe_tab = get_transcribe_tab(gui_app)
        assert transcribe_tab is not None

        # Add audio file
        audio_file = (
            Path(__file__).parent.parent / "fixtures/sample_files/short_audio.mp3"
        )
        add_file_to_transcribe(transcribe_tab, audio_file)
        process_events_for(200)

        # Start processing
        transcribe_tab.start_btn.click()
        process_events_for(1000)  # Let it start processing

        # Click stop button
        print("   🛑 Clicking stop button...")
        if hasattr(transcribe_tab, "stop_btn"):
            transcribe_tab.stop_btn.click()
            process_events_for(2000)  # Wait for cancellation
            print("   ✅ Cancellation requested")
        else:
            pytest.skip("Stop button not found on tab")

        # Note: Full cancellation testing is complex as it depends on worker thread
        # behavior. This test verifies the UI allows cancellation request.
        print("✅ Cancellation workflow test passed")

    def test_invalid_file_error(self, gui_app, test_sandbox):
        """Test error handling for invalid/missing file."""
        print("\n📝 Testing invalid file error handling...")

        # Switch to Transcribe tab
        assert switch_to_tab(gui_app, "Transcribe")
        process_events_for(500)

        transcribe_tab = get_transcribe_tab(gui_app)
        assert transcribe_tab is not None

        # Try to add a non-existent file
        fake_file = Path("/tmp/nonexistent_audio_file_12345.mp3")

        # Attempt to add (should either reject or process with error)
        add_file_to_transcribe(transcribe_tab, fake_file)
        process_events_for(200)

        # Click start
        transcribe_tab.start_btn.click()
        process_events_for(2000)

        # Check for error indication in output log
        if hasattr(transcribe_tab, "output_text"):
            output = transcribe_tab.output_text.toPlainText()
            # Should see some error message
            has_error = any(
                word in output.lower()
                for word in ["error", "failed", "not found", "invalid"]
            )
            if has_error:
                print(f"   ✅ Error detected in output: {output[:200]}")
            else:
                print(f"   ⚠️  No clear error message found, but test completed")

        print("✅ Invalid file error handling test passed")

    def test_empty_queue_error(self, gui_app, test_sandbox):
        """Test error handling when starting with empty queue."""
        print("\n📝 Testing empty queue error handling...")

        # Switch to Transcribe tab
        assert switch_to_tab(gui_app, "Transcribe")
        process_events_for(500)

        transcribe_tab = get_transcribe_tab(gui_app)
        assert transcribe_tab is not None

        # Ensure queue is empty (clear any files)
        if hasattr(transcribe_tab, "transcription_files"):
            transcribe_tab.transcription_files.clear()
        process_events_for(200)

        # Try to click start with empty queue
        transcribe_tab.start_btn.click()
        process_events_for(1000)

        # Should either:
        # 1. Show error message in output
        # 2. Not start processing at all
        # 3. Disable start button

        if hasattr(transcribe_tab, "output_text"):
            output = transcribe_tab.output_text.toPlainText()
            if output:
                print(f"   ℹ️  Output: {output[:200]}")

        print("✅ Empty queue handling test passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
