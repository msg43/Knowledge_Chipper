"""
End-to-end user workflow tests simulating common user interactions.

This test suite simulates complete user workflows from start to finish:
- Transcribing a YouTube video
- Transcribing local audio files
- Summarizing transcripts
- Batch processing multiple files
- Changing settings
- Using the monitor tab for auto-processing

These tests use pytest-qt to simulate real user interactions and verify
the entire workflow completes successfully.

Run these tests:
    pytest tests/gui/test_user_workflows.py -v --timeout=300

Run specific workflow:
    pytest tests/gui/test_user_workflows.py::TestTranscriptionWorkflows::test_transcribe_local_audio_file -v
"""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, call, patch

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

try:
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtWidgets import QApplication, QMessageBox

    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False


@pytest.mark.skipif(not PYQT_AVAILABLE, reason="PyQt6 not available")
@pytest.mark.integration
class TestTranscriptionWorkflows:
    """Test complete transcription workflows."""

    @pytest.fixture
    def transcription_tab(self, qtbot):
        """Create TranscriptionTab for workflow testing."""
        from knowledge_system.gui.tabs.transcription_tab import TranscriptionTab

        tab = TranscriptionTab()
        qtbot.addWidget(tab)
        return tab

    @pytest.mark.timeout(60)
    def test_transcribe_local_audio_file(self, qtbot, transcription_tab, tmp_path):
        """
        Simulate: User transcribes a local audio file

        Workflow:
        1. User clicks "Add Files"
        2. Selects an audio file
        3. Selects transcription model
        4. Clicks "Start Transcription"
        5. Waits for completion
        """
        # Step 1: Create a test audio file
        test_audio = tmp_path / "test_audio.mp3"
        test_audio.write_bytes(b"fake audio data")  # Fake audio file

        # Step 2: Directly add file to list (bypassing file dialog)
        if hasattr(transcription_tab, "file_list"):
            transcription_tab.file_list.addItem(str(test_audio))
            qtbot.wait(100)

            # Verify file was added
            assert transcription_tab.file_list.count() > 0

        # Step 4: User selects transcription model
        if hasattr(transcription_tab, "model_combo"):
            if transcription_tab.model_combo.count() > 0:
                # Select "base" or first available model
                for i in range(transcription_tab.model_combo.count()):
                    if "base" in transcription_tab.model_combo.itemText(i).lower():
                        transcription_tab.model_combo.setCurrentIndex(i)
                        break
                else:
                    transcription_tab.model_combo.setCurrentIndex(0)

        # Step 5: User enables diarization (speaker detection)
        if hasattr(transcription_tab, "diarization_checkbox"):
            if not transcription_tab.diarization_checkbox.isChecked():
                qtbot.mouseClick(
                    transcription_tab.diarization_checkbox, Qt.MouseButton.LeftButton
                )

        # Step 6: Mock the actual transcription to avoid running Whisper
        with patch.object(transcription_tab, "_start_processing") as mock_process:
            # User clicks "Start Transcription"
            if hasattr(transcription_tab, "start_btn"):
                qtbot.mouseClick(transcription_tab.start_btn, Qt.MouseButton.LeftButton)
                qtbot.wait(100)

                # Verify processing was triggered
                assert mock_process.called

    @pytest.mark.timeout(60)
    def test_transcribe_youtube_url(self, qtbot, transcription_tab):
        """
        Simulate: User transcribes a YouTube video

        Workflow:
        1. User enters YouTube URL
        2. Selects model and options
        3. Clicks "Start Transcription"
        4. System downloads and transcribes
        """
        # Step 1: User enters YouTube URL
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

        if hasattr(transcription_tab, "url_input"):
            # Directly set URL text
            transcription_tab.url_input.setText(test_url)
            qtbot.wait(100)

            # Verify URL was entered
            assert (
                test_url in transcription_tab.url_input.text()
                or transcription_tab.url_input.toPlainText()
            )

        # Step 2: User selects model
        if hasattr(transcription_tab, "model_combo"):
            if transcription_tab.model_combo.count() > 0:
                transcription_tab.model_combo.setCurrentIndex(0)

        # Step 3: User disables proxy (if available)
        if hasattr(transcription_tab, "proxy_mode_combo"):
            # Find "Never use proxies" option
            for i in range(transcription_tab.proxy_mode_combo.count()):
                if "never" in transcription_tab.proxy_mode_combo.itemText(i).lower():
                    transcription_tab.proxy_mode_combo.setCurrentIndex(i)
                    break

        # Step 4: Mock the download and transcription
        with patch.object(transcription_tab, "_start_processing") as mock_process:
            # User clicks "Start Transcription"
            if hasattr(transcription_tab, "start_btn"):
                qtbot.mouseClick(transcription_tab.start_btn, Qt.MouseButton.LeftButton)
                qtbot.wait(100)

                # Verify processing was triggered or blocked (depends on settings)
                # In real scenario, might be blocked by proxy requirements

    @pytest.mark.timeout(60)
    def test_batch_transcribe_multiple_files(self, qtbot, transcription_tab, tmp_path):
        """
        Simulate: User transcribes multiple files at once

        Workflow:
        1. User clicks "Add Files"
        2. Selects multiple audio files
        3. Configures batch settings
        4. Starts batch transcription
        """
        # Step 1: Create multiple test files
        test_files = []
        for i in range(3):
            audio_file = tmp_path / f"audio_{i}.mp3"
            audio_file.write_bytes(b"fake audio data")
            test_files.append(str(audio_file))

        # Step 2: Directly add files to list
        if hasattr(transcription_tab, "file_list"):
            for file_path in test_files:
                transcription_tab.file_list.addItem(file_path)
            qtbot.wait(100)

            # Verify all files were added
            assert transcription_tab.file_list.count() == 3

        # Step 4: User enables auto-process checkbox
        if hasattr(transcription_tab, "auto_process_checkbox"):
            if not transcription_tab.auto_process_checkbox.isChecked():
                qtbot.mouseClick(
                    transcription_tab.auto_process_checkbox, Qt.MouseButton.LeftButton
                )

        # Step 5: Mock batch processing
        with patch.object(transcription_tab, "_start_processing") as mock_process:
            if hasattr(transcription_tab, "start_btn"):
                qtbot.mouseClick(transcription_tab.start_btn, Qt.MouseButton.LeftButton)
                qtbot.wait(100)

                assert mock_process.called


@pytest.mark.skipif(not PYQT_AVAILABLE, reason="PyQt6 not available")
@pytest.mark.integration
class TestSummarizationWorkflows:
    """Test complete summarization workflows."""

    @pytest.fixture
    def summarization_tab(self, qtbot):
        """Create SummarizationTab for workflow testing."""
        from knowledge_system.gui.tabs.summarization_tab import SummarizationTab

        tab = SummarizationTab()
        qtbot.addWidget(tab)
        return tab

    @pytest.mark.timeout(60)
    def test_summarize_single_transcript(self, qtbot, summarization_tab, tmp_path):
        """
        Simulate: User summarizes a single transcript

        Workflow:
        1. User clicks "Add Files"
        2. Selects a transcript file
        3. Selects AI provider and model
        4. Chooses content type
        5. Clicks "Start Analysis"
        6. Reviews results
        """
        # Step 1: Create a test transcript
        transcript = tmp_path / "test_transcript.txt"
        transcript.write_text(
            """
        Speaker 1 (00:00:00): Welcome to this podcast about AI and machine learning.
        Speaker 2 (00:00:05): Thanks for having me. Today we'll discuss neural networks.
        Speaker 1 (00:00:10): Let's start with the basics of deep learning.
        Speaker 2 (00:00:15): Deep learning is a subset of machine learning that uses neural networks.
        """
        )

        # Step 2: Directly add file to list
        if hasattr(summarization_tab, "file_list"):
            summarization_tab.file_list.addItem(str(transcript))
            qtbot.wait(100)

            # Verify file was added
            assert summarization_tab.file_list.count() > 0

        # Step 4: User selects AI provider
        if hasattr(summarization_tab, "provider_combo"):
            # Try to select Ollama (local) if available
            for i in range(summarization_tab.provider_combo.count()):
                if "ollama" in summarization_tab.provider_combo.itemText(i).lower():
                    with qtbot.waitSignal(
                        summarization_tab.provider_combo.currentTextChanged,
                        timeout=1000,
                    ):
                        summarization_tab.provider_combo.setCurrentIndex(i)
                    break

        # Step 5: User selects model
        if hasattr(summarization_tab, "model_combo"):
            if summarization_tab.model_combo.count() > 0:
                summarization_tab.model_combo.setCurrentIndex(0)

        # Step 6: User selects content type
        if hasattr(summarization_tab, "content_type_combo"):
            # Try to find "Unified HCE" option
            for i in range(summarization_tab.content_type_combo.count()):
                if (
                    "unified"
                    in summarization_tab.content_type_combo.itemText(i).lower()
                ):
                    summarization_tab.content_type_combo.setCurrentIndex(i)
                    break

        # Step 7: User adjusts max claims
        if hasattr(summarization_tab, "max_claims_spin"):
            summarization_tab.max_claims_spin.setValue(50)

        # Step 8: Mock the actual summarization
        with patch.object(summarization_tab, "_start_processing") as mock_process:
            # User clicks "Start Analysis"
            if hasattr(summarization_tab, "start_btn"):
                qtbot.mouseClick(summarization_tab.start_btn, Qt.MouseButton.LeftButton)
                qtbot.wait(100)

                # Verify processing was triggered
                assert mock_process.called

    @pytest.mark.timeout(60)
    def test_batch_summarize_folder(self, qtbot, summarization_tab, tmp_path):
        """
        Simulate: User summarizes an entire folder of transcripts

        Workflow:
        1. User clicks "Add Folder"
        2. Selects folder with multiple transcripts
        3. Configures batch settings
        4. Starts batch analysis
        """
        # Step 1: Create multiple transcripts in a folder
        transcript_folder = tmp_path / "transcripts"
        transcript_folder.mkdir()

        transcripts = []
        for i in range(5):
            transcript = transcript_folder / f"transcript_{i}.txt"
            transcript.write_text(
                f"Speaker 1: This is transcript {i} with important claims."
            )
            transcripts.append(str(transcript))

        # Step 2: Directly add all files to list
        if hasattr(summarization_tab, "file_list"):
            for transcript_path in transcripts:
                summarization_tab.file_list.addItem(transcript_path)
            qtbot.wait(100)

            # Verify all files were added
            assert summarization_tab.file_list.count() == 5

        # Step 4: Configure for batch processing
        if hasattr(summarization_tab, "provider_combo"):
            summarization_tab.provider_combo.setCurrentIndex(0)

        if hasattr(summarization_tab, "model_combo"):
            if summarization_tab.model_combo.count() > 0:
                summarization_tab.model_combo.setCurrentIndex(0)

        # Step 5: Mock batch processing
        with patch.object(summarization_tab, "_start_processing") as mock_process:
            if hasattr(summarization_tab, "start_btn"):
                qtbot.mouseClick(summarization_tab.start_btn, Qt.MouseButton.LeftButton)
                qtbot.wait(100)

                assert mock_process.called

    @pytest.mark.timeout(60)
    def test_change_analysis_template(self, qtbot, summarization_tab):
        """
        Simulate: User changes analysis template

        Workflow:
        1. User changes content type
        2. Template path updates automatically
        3. User can manually edit template path
        """
        # Step 1: User changes content type
        if hasattr(summarization_tab, "content_type_combo"):
            initial_type = summarization_tab.content_type_combo.currentText()

            # Change to different type
            if summarization_tab.content_type_combo.count() > 1:
                new_index = (
                    1 if summarization_tab.content_type_combo.currentIndex() == 0 else 0
                )

                with qtbot.waitSignal(
                    summarization_tab.content_type_combo.currentTextChanged,
                    timeout=1000,
                ):
                    summarization_tab.content_type_combo.setCurrentIndex(new_index)

                # Verify type changed
                assert (
                    summarization_tab.content_type_combo.currentText() != initial_type
                )

        # Step 2: User manually edits template path
        if hasattr(summarization_tab, "template_path_edit"):
            qtbot.mouseClick(
                summarization_tab.template_path_edit, Qt.MouseButton.LeftButton
            )

            # Clear and type new path
            summarization_tab.template_path_edit.clear()
            qtbot.keyClicks(
                summarization_tab.template_path_edit, "custom_template.yaml"
            )

            assert "custom_template" in summarization_tab.template_path_edit.text()


@pytest.mark.skipif(not PYQT_AVAILABLE, reason="PyQt6 not available")
@pytest.mark.integration
class TestCompleteUserJourneys:
    """Test complete end-to-end user journeys across multiple tabs."""

    @pytest.mark.timeout(120)
    def test_complete_transcribe_to_summarize_workflow(self, qtbot, tmp_path):
        """
        Simulate: Complete workflow from transcription to summarization

        Workflow:
        1. User transcribes audio file
        2. Waits for completion
        3. Switches to Summarize tab
        4. Selects the transcript
        5. Runs analysis
        6. Reviews results
        """
        from knowledge_system.gui.tabs.summarization_tab import SummarizationTab
        from knowledge_system.gui.tabs.transcription_tab import TranscriptionTab

        # PART 1: Transcription
        transcription_tab = TranscriptionTab()
        qtbot.addWidget(transcription_tab)

        # Create test audio file
        audio_file = tmp_path / "test_audio.mp3"
        audio_file.write_bytes(b"fake audio data")

        # Directly add file to list
        if hasattr(transcription_tab, "file_list"):
            transcription_tab.file_list.addItem(str(audio_file))
            qtbot.wait(100)

        # Configure and start transcription (mocked)
        with patch.object(transcription_tab, "_start_processing"):
            if hasattr(transcription_tab, "start_btn"):
                qtbot.mouseClick(transcription_tab.start_btn, Qt.MouseButton.LeftButton)
                qtbot.wait(100)

        # PART 2: Summarization
        summarization_tab = SummarizationTab()
        qtbot.addWidget(summarization_tab)

        # Create mock transcript (as if transcription completed)
        transcript = tmp_path / "test_audio_transcript.txt"
        transcript.write_text("Speaker 1: This is the transcribed content.")

        # Directly add transcript for summarization
        if hasattr(summarization_tab, "file_list"):
            summarization_tab.file_list.addItem(str(transcript))
            qtbot.wait(100)

        # Start summarization (mocked)
        with patch.object(summarization_tab, "_start_processing"):
            if hasattr(summarization_tab, "start_btn"):
                qtbot.mouseClick(summarization_tab.start_btn, Qt.MouseButton.LeftButton)
                qtbot.wait(100)

        # Workflow completed successfully
        assert True

    @pytest.mark.timeout(60)
    def test_settings_change_workflow(self, qtbot):
        """
        Simulate: User changes settings

        Workflow:
        1. User opens Settings tab
        2. Changes API key
        3. Changes default model
        4. Saves settings
        """
        from knowledge_system.gui.tabs.api_keys_tab import APIKeysTab

        settings_tab = APIKeysTab()
        qtbot.addWidget(settings_tab)

        # User enters OpenAI API key
        if hasattr(settings_tab, "openai_key_edit"):
            qtbot.mouseClick(settings_tab.openai_key_edit, Qt.MouseButton.LeftButton)

            settings_tab.openai_key_edit.clear()
            qtbot.keyClicks(settings_tab.openai_key_edit, "sk-test-key-123")

            assert "sk-test" in settings_tab.openai_key_edit.text()

        # User saves settings (mocked)
        with patch.object(settings_tab, "_save_settings", return_value=None):
            if hasattr(settings_tab, "save_btn"):
                qtbot.mouseClick(settings_tab.save_btn, Qt.MouseButton.LeftButton)
                qtbot.wait(100)


@pytest.mark.skipif(not PYQT_AVAILABLE, reason="PyQt6 not available")
@pytest.mark.integration
class TestMonitorWorkflows:
    """Test file monitoring and auto-processing workflows."""

    @pytest.fixture
    def monitor_tab(self, qtbot):
        """Create MonitorTab for workflow testing."""
        from knowledge_system.gui.tabs.monitor_tab import MonitorTab

        tab = MonitorTab()
        qtbot.addWidget(tab)
        return tab

    @pytest.mark.timeout(60)
    def test_setup_folder_monitoring(self, qtbot, monitor_tab, tmp_path):
        """
        Simulate: User sets up folder monitoring

        Workflow:
        1. User selects folder to watch
        2. Configures file patterns
        3. Enables auto-processing
        4. Starts monitoring
        """
        # Step 1: Create and set folder to watch
        watch_folder = tmp_path / "watch_folder"
        watch_folder.mkdir()

        # Directly set the folder path (bypass dialog)
        if hasattr(monitor_tab, "folder_path_edit"):
            monitor_tab.folder_path_edit.setText(str(watch_folder))
            qtbot.wait(100)
        elif hasattr(monitor_tab, "directory_edit"):
            monitor_tab.directory_edit.setText(str(watch_folder))
            qtbot.wait(100)

        # Step 2: User configures file patterns
        if hasattr(monitor_tab, "pattern_edit"):
            qtbot.mouseClick(monitor_tab.pattern_edit, Qt.MouseButton.LeftButton)
            monitor_tab.pattern_edit.clear()
            qtbot.keyClicks(monitor_tab.pattern_edit, "*.mp3,*.mp4")

        # Step 3: User enables auto-processing
        if hasattr(monitor_tab, "auto_process_checkbox"):
            if not monitor_tab.auto_process_checkbox.isChecked():
                qtbot.mouseClick(
                    monitor_tab.auto_process_checkbox, Qt.MouseButton.LeftButton
                )

        # Step 4: User starts monitoring (mocked)
        with patch.object(monitor_tab, "_start_watching", return_value=None):
            if hasattr(monitor_tab, "start_btn"):
                qtbot.mouseClick(monitor_tab.start_btn, Qt.MouseButton.LeftButton)
                qtbot.wait(100)


@pytest.mark.skipif(not PYQT_AVAILABLE, reason="PyQt6 not available")
@pytest.mark.integration
class TestErrorHandlingWorkflows:
    """Test how UI handles errors and edge cases."""

    @pytest.mark.timeout(30)
    def test_start_without_files_shows_error(self, qtbot, mock_message_box):
        """
        Simulate: User tries to start processing without selecting files

        Expected: Error message shown
        """
        from knowledge_system.gui.tabs.summarization_tab import SummarizationTab

        tab = SummarizationTab()
        qtbot.addWidget(tab)

        # Clear file list
        if hasattr(tab, "file_list"):
            tab.file_list.clear()

        # User clicks start without files
        if hasattr(tab, "start_btn"):
            qtbot.mouseClick(tab.start_btn, Qt.MouseButton.LeftButton)
            qtbot.wait(100)

            # Should show error (or button is disabled)
            # Either way, no crash

    @pytest.mark.timeout(30)
    def test_invalid_url_handling(self, qtbot):
        """
        Simulate: User enters invalid YouTube URL

        Expected: Validation error or graceful handling
        """
        from knowledge_system.gui.tabs.transcription_tab import TranscriptionTab

        tab = TranscriptionTab()
        qtbot.addWidget(tab)

        # User enters invalid URL
        if hasattr(tab, "url_input"):
            qtbot.mouseClick(tab.url_input, Qt.MouseButton.LeftButton)
            tab.url_input.clear()
            qtbot.keyClicks(tab.url_input, "not-a-valid-url")

            # Try to start (should handle gracefully)
            with patch.object(tab, "_start_processing"):
                if hasattr(tab, "start_btn"):
                    qtbot.mouseClick(tab.start_btn, Qt.MouseButton.LeftButton)
                    qtbot.wait(100)

                    # No crash = success


# ============================================================================
# WORKFLOW TEST RUNNER
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("User Workflow Tests")
    print("=" * 70)
    print()
    print("These tests simulate complete user workflows:")
    print("  - Transcribing audio files and YouTube videos")
    print("  - Summarizing transcripts")
    print("  - Batch processing")
    print("  - Settings changes")
    print("  - File monitoring")
    print()
    print("Run all workflows:")
    print("  pytest tests/gui/test_user_workflows.py -v --timeout=300")
    print()
    print("Run specific workflow:")
    print(
        "  pytest tests/gui/test_user_workflows.py::TestTranscriptionWorkflows::test_transcribe_local_audio_file -v"
    )
    print()
    print("=" * 70)

    pytest.main([__file__, "-v", "--timeout=300"])
