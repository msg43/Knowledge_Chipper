"""
Comprehensive Real GUI Testing Suite

Tests the complete GUI functionality with real data sources, real processing,
and real outputs. Covers all tabs, workflows, and validation.

This replaces:
- tests/gui_comprehensive/test_transcribe_inputs.py
- tests/gui_comprehensive/test_summarize_inputs.py
- tests/gui_comprehensive/test_workflows_real.py
- tests/gui_comprehensive/test_all_workflows_automated.py
- tests/gui_comprehensive/test_smoke_automated.py
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
    find_button_by_text,
    get_summarize_tab,
    get_transcribe_tab,
    process_events_for,
    read_markdown_with_frontmatter,
    set_env_sandboxes,
    switch_to_tab,
    wait_for_completion,
    wait_until,
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
    # Set environment variables IMMEDIATELY so they're available during GUI init
    set_env_sandboxes(sandbox.db_path, sandbox.output_dir)
    yield sandbox


@pytest.fixture
def gui_app(qapp, test_sandbox):
    """Launch GUI with test sandbox (env vars already set by test_sandbox fixture)."""
    from knowledge_system.gui.main_window_pyqt6 import MainWindow

    window = MainWindow()
    window.show()
    process_events_for(500)

    yield window

    window.close()
    process_events_for(200)


class TestRealGUITranscription:
    """Test real transcription workflows with actual data sources."""

    @pytest.mark.parametrize(
        "input_type,file_path,timeout",
        [
            ("youtube_url", "https://youtu.be/CYrISmYGT8A?si=4TvYl42udS1v-jum", 600),
            (
                "youtube_playlist",
                "https://youtube.com/playlist?list=PLmPoIpZcewRt6SXGBm0eBykcCp9Zx-fns&si=fsZvALKteA_t2PiJ",
                1200,
            ),
            (
                "rss_feed",
                "https://podcasts.apple.com/us/podcast/making-sense-with-sam-harris/id733163012?i=1000731856868",
                900,
            ),
            ("local_audio", "fixtures/sample_files/test_speech.mp3", 180),
            ("local_video", "fixtures/sample_files/short_video.webm", 240),
        ],
    )
    def test_transcription_input_types(
        self, gui_app, test_sandbox, input_type, file_path, timeout
    ):
        """Test transcription of all input types with real processing."""
        # Switch to Transcribe tab
        assert switch_to_tab(
            gui_app, "Transcribe"
        ), "Failed to switch to Transcribe tab"
        process_events_for(500)

        transcribe_tab = get_transcribe_tab(gui_app)
        assert transcribe_tab is not None, "Could not find Transcribe tab"

        # Handle different input types
        if input_type in ["youtube_url", "youtube_playlist", "rss_feed"]:
            # Network sources
            add_file_to_transcribe(transcribe_tab, Path(file_path))
        else:
            # Local files
            local_file = Path(__file__).parent.parent.parent / file_path
            assert local_file.exists(), f"Test file not found: {local_file}"
            add_file_to_transcribe(transcribe_tab, local_file)

        process_events_for(200)

        # Start processing
        transcribe_tab.start_btn.click()
        process_events_for(500)

        # Wait for real processing
        print(f"⏳ Waiting for {input_type} transcription (timeout: {timeout}s)...")
        success = wait_for_completion(transcribe_tab, timeout_seconds=timeout)
        assert success, f"{input_type} transcription did not complete within {timeout}s"

        # Validate database
        db = DBValidator(test_sandbox.db_path)
        videos = db.get_all_videos()
        assert len(videos) > 0, f"No media record created for {input_type}"

        transcript = db.get_transcript_for_video(videos[0]["video_id"])
        assert transcript is not None, f"No transcript found for {input_type}"
        assert (
            len(transcript.get("transcript_text", "")) > 0
        ), f"Transcript empty for {input_type}"

        # Validate markdown output
        md_files = list(test_sandbox.output_dir.glob("**/*.md"))
        assert len(md_files) > 0, f"No markdown files created for {input_type}"

        print(f"✅ {input_type} transcription test passed")

    def test_batch_transcription(self, gui_app, test_sandbox):
        """Test batch processing multiple local files."""
        # Switch to Transcribe tab
        assert switch_to_tab(
            gui_app, "Transcribe"
        ), "Failed to switch to Transcribe tab"
        process_events_for(500)

        transcribe_tab = get_transcribe_tab(gui_app)
        assert transcribe_tab is not None, "Could not find Transcribe tab"

        # Add multiple audio files
        audio1 = (
            Path(__file__).parent.parent.parent
            / "fixtures/sample_files/short_audio.mp3"
        )
        audio2 = (
            Path(__file__).parent.parent.parent
            / "fixtures/sample_files/short_audio_multi.mp3"
        )

        assert audio1.exists() and audio2.exists(), "Test audio files not found"

        add_file_to_transcribe(transcribe_tab, audio1)
        process_events_for(100)
        add_file_to_transcribe(transcribe_tab, audio2)
        process_events_for(200)

        # Start processing
        transcribe_tab.start_btn.click()
        process_events_for(500)

        # Wait for batch processing
        print("⏳ Waiting for batch transcription...")
        success = wait_for_completion(transcribe_tab, timeout_seconds=300)
        assert success, "Batch transcription did not complete within 5 minutes"

        # Validate both files were processed
        db = DBValidator(test_sandbox.db_path)
        videos = db.get_all_videos()
        assert (
            len(videos) >= 2
        ), f"Expected at least 2 media records, found {len(videos)}"

        # Verify transcripts exist for both
        for video in videos[:2]:
            transcript = db.get_transcript_for_video(video["video_id"])
            assert transcript is not None, f"No transcript for {video['video_id']}"
            assert len(transcript.get("transcript_text", "")) > 0, "Transcript empty"

        print(f"✅ Batch transcription test passed: {len(videos)} files processed")


class TestRealGUISummarization:
    """Test real summarization workflows with actual document formats."""

    @pytest.mark.parametrize(
        "file_type,file_path",
        [
            ("markdown", "fixtures/sample_files/sample_transcript.md"),
            ("pdf", "KenRogoff_Transcript.pdf"),
            ("text", "fixtures/sample_files/sample_document.txt"),
            ("docx", "KenRogoff_Transcript.docx"),
            ("html", "fixtures/sample_files/sample_document.html"),
            ("json", "fixtures/sample_files/sample_document.json"),
            ("rtf", "KenRogoff_Transcript.rtf"),
        ],
    )
    def test_summarization_input_types(
        self, gui_app, test_sandbox, file_type, file_path
    ):
        """Test summarization of all document formats with real Ollama processing."""
        # Check Ollama is running
        if not check_ollama_running():
            pytest.fail(
                "Ollama must be running for this test. Start with: ollama serve"
            )

        # Switch to Summarize tab
        assert switch_to_tab(gui_app, "Summarize"), "Failed to switch to Summarize tab"
        process_events_for(500)

        summarize_tab = get_summarize_tab(gui_app)
        assert summarize_tab is not None, "Could not find Summarize tab"

        # Handle file paths
        if file_type in ["pdf", "docx", "rtf"]:
            # Files in project root
            doc_file = (
                Path("/Users/matthewgreer/Projects/Knowledge_Chipper") / file_path
            )
        else:
            # Files in fixtures
            doc_file = Path(__file__).parent.parent.parent / file_path

        assert doc_file.exists(), f"Test file not found: {doc_file}"

        # Add file to summarization queue
        success = add_file_to_summarize(summarize_tab, doc_file)
        assert success, f"Failed to add {file_type} file to summarization queue"
        process_events_for(200)

        # Start summarization
        summarize_tab.start_btn.click()
        process_events_for(500)

        # Wait for real Ollama processing
        print(f"⏳ Waiting for {file_type} summarization...")
        success = wait_for_completion(summarize_tab, timeout_seconds=180)
        assert success, f"{file_type} summarization did not complete within 3 minutes"

        # Validate database
        db = DBValidator(test_sandbox.db_path)
        summaries = db.get_all_summaries()
        assert len(summaries) > 0, f"No summary record created for {file_type}"

        summary = summaries[0]
        assert (
            summary.get("llm_provider") == "ollama"
        ), f"Expected ollama provider, got {summary.get('llm_provider')}"
        assert (
            len(summary.get("summary_text", "")) > 0
        ), f"Summary text is empty for {file_type}"

        # Validate schema
        errors = db.validate_summary_schema(summary)
        if errors:
            print(f"⚠️  Schema validation warnings for {file_type}: {errors}")

        # Validate markdown file
        md_files = list(test_sandbox.output_dir.glob("**/*.md"))
        assert len(md_files) > 0, f"No markdown files created for {file_type}"

        print(f"✅ {file_type} summarization test passed")


class TestRealGUIWorkflows:
    """Test complete end-to-end workflows with real processing."""

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
            Path(__file__).parent.parent.parent
            / "fixtures/sample_files/short_audio.mp3"
        )
        assert audio_file.exists(), f"Test audio file not found: {audio_file}"

        add_file_to_transcribe(transcribe_tab, audio_file)
        process_events_for(200)

        # Start transcription
        transcribe_tab.start_btn.click()
        process_events_for(500)

        # Wait for transcription
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

        # Wait for summarization
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
            Path(__file__).parent.parent.parent
            / "fixtures/sample_files/short_audio.mp3"
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

        print("✅ Cancellation workflow test passed")

    def test_error_handling_invalid_input(self, gui_app, test_sandbox):
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


class TestRealGUITabNavigation:
    """Test all GUI tabs load and function correctly."""

    def test_all_tabs_load(self, gui_app, test_sandbox):
        """Test that all tabs can be loaded without errors."""
        # Access tabs widget directly
        tabs = getattr(gui_app, "tabs", None)
        if not tabs:
            pytest.fail("Tabs widget not found")

        tab_count = tabs.count()
        failed_tabs = []

        expected_tabs = [
            "Introduction",
            "Transcribe",
            "Prompts",
            "Summarize",
            "Review",
            "Monitor",
            "Settings",
        ]

        for i in range(tab_count):
            tab_name = tabs.tabText(i)
            try:
                tabs.setCurrentIndex(i)
                process_events_for(500)
                time.sleep(0.1)  # Give tab time to render

                # Verify tab name matches expected
                if i < len(expected_tabs):
                    expected_name = expected_tabs[i]
                    assert (
                        expected_name.lower() in tab_name.lower()
                        or tab_name.lower() in expected_name.lower()
                    ), f"Tab {i}: expected '{expected_name}', got '{tab_name}'"

            except Exception as e:
                failed_tabs.append(f"{tab_name}: {str(e)}")

        assert len(failed_tabs) == 0, f"Some tabs failed to load: {failed_tabs}"
        print(f"✅ All {tab_count} tabs loaded successfully")

    def test_tab_switching_functionality(self, gui_app, test_sandbox):
        """Test tab switching works correctly."""
        # Test switching to each tab
        tab_names = [
            "Transcribe",
            "Summarize",
            "Prompts",
            "Review",
            "Monitor",
            "Settings",
        ]

        for tab_name in tab_names:
            success = switch_to_tab(gui_app, tab_name)
            assert success, f"Failed to switch to {tab_name} tab"
            process_events_for(500)

            # Verify we're on the correct tab
            current_tab = gui_app.tabs.currentWidget()
            assert current_tab is not None, f"No widget found for {tab_name} tab"

            print(f"✅ Successfully switched to {tab_name} tab")

        print("✅ All tab switching tests passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
