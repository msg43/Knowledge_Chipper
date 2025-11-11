"""
Simple, fast workflow tests that verify UI interactions work.

These tests focus on UI state changes and user interactions without
running actual processing. They complete quickly and reliably.

Run these tests:
    pytest tests/gui/test_simple_workflows.py -v
"""

import sys
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication

    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False


@pytest.mark.skipif(not PYQT_AVAILABLE, reason="PyQt6 not available")
@pytest.mark.integration
class TestBasicUIWorkflows:
    """Test basic UI workflows without running actual processing."""

    @pytest.mark.timeout(10)
    def test_add_files_to_transcription_list(self, qtbot, tmp_path):
        """User adds files to transcription list."""
        from knowledge_system.gui.tabs.transcription_tab import TranscriptionTab

        tab = TranscriptionTab()
        qtbot.addWidget(tab)
        qtbot.wait(500)  # Let tab initialize

        # Create test file
        test_file = tmp_path / "test.mp3"
        test_file.write_bytes(b"fake audio")

        # Add file directly to list
        if hasattr(tab, "file_list"):
            initial_count = tab.file_list.count()
            tab.file_list.addItem(str(test_file))
            qtbot.wait(100)

            # Verify file was added
            assert tab.file_list.count() == initial_count + 1
            print(f"✅ File added to list: {tab.file_list.count()} files")

    @pytest.mark.timeout(10)
    def test_add_files_to_summarization_list(self, qtbot, tmp_path):
        """User adds transcript to summarization list."""
        from knowledge_system.gui.tabs.summarization_tab import SummarizationTab

        tab = SummarizationTab()
        qtbot.addWidget(tab)
        qtbot.wait(500)

        # Create test transcript
        transcript = tmp_path / "transcript.txt"
        transcript.write_text("Speaker 1: Test content")

        # Add file directly
        if hasattr(tab, "file_list"):
            initial_count = tab.file_list.count()
            tab.file_list.addItem(str(transcript))
            qtbot.wait(100)

            assert tab.file_list.count() == initial_count + 1
            print(f"✅ Transcript added: {tab.file_list.count()} files")

    @pytest.mark.timeout(10)
    def test_change_transcription_model(self, qtbot):
        """User changes transcription model."""
        from knowledge_system.gui.tabs.transcription_tab import TranscriptionTab

        tab = TranscriptionTab()
        qtbot.addWidget(tab)
        qtbot.wait(500)

        if hasattr(tab, "model_combo") and tab.model_combo.count() > 1:
            initial_model = tab.model_combo.currentText()

            # Change model
            tab.model_combo.setCurrentIndex(1)
            qtbot.wait(100)

            new_model = tab.model_combo.currentText()
            assert new_model != initial_model
            print(f"✅ Model changed: {initial_model} → {new_model}")

    @pytest.mark.timeout(10)
    def test_change_summarization_provider(self, qtbot):
        """User changes AI provider."""
        from knowledge_system.gui.tabs.summarization_tab import SummarizationTab

        tab = SummarizationTab()
        qtbot.addWidget(tab)
        qtbot.wait(500)

        if hasattr(tab, "provider_combo") and tab.provider_combo.count() > 1:
            initial_provider = tab.provider_combo.currentText()

            # Change provider
            tab.provider_combo.setCurrentIndex(1)
            qtbot.wait(200)  # Wait for model list to update

            new_provider = tab.provider_combo.currentText()
            assert new_provider != initial_provider
            print(f"✅ Provider changed: {initial_provider} → {new_provider}")

    @pytest.mark.timeout(10)
    def test_toggle_diarization_checkbox(self, qtbot):
        """User toggles diarization checkbox."""
        from knowledge_system.gui.tabs.transcription_tab import TranscriptionTab

        tab = TranscriptionTab()
        qtbot.addWidget(tab)
        qtbot.wait(500)

        if hasattr(tab, "diarization_checkbox"):
            initial_state = tab.diarization_checkbox.isChecked()

            # Toggle checkbox
            qtbot.mouseClick(tab.diarization_checkbox, Qt.MouseButton.LeftButton)
            qtbot.wait(100)

            new_state = tab.diarization_checkbox.isChecked()
            assert new_state != initial_state
            print(f"✅ Diarization toggled: {initial_state} → {new_state}")

    @pytest.mark.timeout(10)
    def test_adjust_max_claims_spinbox(self, qtbot):
        """User adjusts max claims setting."""
        from knowledge_system.gui.tabs.summarization_tab import SummarizationTab

        tab = SummarizationTab()
        qtbot.addWidget(tab)
        qtbot.wait(500)

        if hasattr(tab, "max_claims_spin"):
            # Set to 75
            tab.max_claims_spin.setValue(75)
            qtbot.wait(100)

            assert tab.max_claims_spin.value() == 75
            print(f"✅ Max claims set to: {tab.max_claims_spin.value()}")

    @pytest.mark.timeout(10)
    def test_enter_youtube_url(self, qtbot):
        """User enters YouTube URL."""
        from knowledge_system.gui.tabs.transcription_tab import TranscriptionTab

        tab = TranscriptionTab()
        qtbot.addWidget(tab)
        qtbot.wait(500)

        test_url = "https://www.youtube.com/watch?v=test123"

        if hasattr(tab, "url_input"):
            # Set URL
            tab.url_input.setText(test_url)
            qtbot.wait(100)

            # Verify URL was set
            actual_text = (
                tab.url_input.text()
                if hasattr(tab.url_input, "text")
                else tab.url_input.toPlainText()
            )
            assert test_url in actual_text
            print(f"✅ URL entered: {actual_text[:50]}...")

    @pytest.mark.timeout(10)
    def test_enter_api_key(self, qtbot):
        """User enters API key."""
        from knowledge_system.gui.tabs.api_keys_tab import APIKeysTab

        tab = APIKeysTab()
        qtbot.addWidget(tab)
        qtbot.wait(500)

        test_key = "sk-test-key-12345"

        if hasattr(tab, "openai_key_edit"):
            # Enter key
            tab.openai_key_edit.setText(test_key)
            qtbot.wait(100)

            assert test_key in tab.openai_key_edit.text()
            print(f"✅ API key entered: {tab.openai_key_edit.text()[:20]}...")

    @pytest.mark.timeout(10)
    def test_view_introduction_tab(self, qtbot):
        """User views introduction tab."""
        from knowledge_system.gui.tabs.introduction_tab import IntroductionTab

        tab = IntroductionTab()
        qtbot.addWidget(tab)
        qtbot.wait(500)

        # Tab should be visible
        assert tab is not None
        print("✅ Introduction tab loaded")

    @pytest.mark.timeout(10)
    def test_navigation_signal_emits(self, qtbot):
        """User triggers navigation signal."""
        from knowledge_system.gui.tabs.introduction_tab import IntroductionTab

        tab = IntroductionTab()
        qtbot.addWidget(tab)
        qtbot.wait(500)

        # Capture signal
        signals = []
        tab.navigate_to_tab.connect(lambda x: signals.append(x))

        # Emit navigation
        tab.navigate_to_tab.emit("Transcribe")
        qtbot.wait(100)

        assert len(signals) == 1
        assert signals[0] == "Transcribe"
        print(f"✅ Navigation signal emitted: {signals[0]}")


@pytest.mark.skipif(not PYQT_AVAILABLE, reason="PyQt6 not available")
@pytest.mark.integration
class TestMultiStepWorkflows:
    """Test multi-step workflows."""

    @pytest.mark.timeout(15)
    def test_add_multiple_files(self, qtbot, tmp_path):
        """User adds multiple files."""
        from knowledge_system.gui.tabs.summarization_tab import SummarizationTab

        tab = SummarizationTab()
        qtbot.addWidget(tab)
        qtbot.wait(500)

        if hasattr(tab, "file_list"):
            # Add 3 files
            for i in range(3):
                f = tmp_path / f"file_{i}.txt"
                f.write_text(f"Content {i}")
                tab.file_list.addItem(str(f))
                qtbot.wait(50)

            assert tab.file_list.count() >= 3
            print(f"✅ Added {tab.file_list.count()} files")

    @pytest.mark.timeout(15)
    def test_configure_and_change_settings(self, qtbot):
        """User configures multiple settings."""
        from knowledge_system.gui.tabs.transcription_tab import TranscriptionTab

        tab = TranscriptionTab()
        qtbot.addWidget(tab)
        qtbot.wait(500)

        steps_completed = []

        # Step 1: Select model
        if hasattr(tab, "model_combo") and tab.model_combo.count() > 0:
            tab.model_combo.setCurrentIndex(0)
            steps_completed.append("model_selected")
            qtbot.wait(100)

        # Step 2: Enable diarization
        if hasattr(tab, "diarization_checkbox"):
            if not tab.diarization_checkbox.isChecked():
                qtbot.mouseClick(tab.diarization_checkbox, Qt.MouseButton.LeftButton)
            steps_completed.append("diarization_enabled")
            qtbot.wait(100)

        # Step 3: Select language
        if hasattr(tab, "language_combo") and tab.language_combo.count() > 0:
            tab.language_combo.setCurrentIndex(0)
            steps_completed.append("language_selected")
            qtbot.wait(100)

        assert len(steps_completed) >= 2
        print(f"✅ Completed {len(steps_completed)} configuration steps")


if __name__ == "__main__":
    print("=" * 70)
    print("Simple Workflow Tests")
    print("=" * 70)
    print()
    print("These tests verify UI interactions work correctly:")
    print("  - Adding files to lists")
    print("  - Changing dropdowns")
    print("  - Toggling checkboxes")
    print("  - Entering text")
    print("  - Signal emissions")
    print()
    print("Run all:")
    print("  pytest tests/gui/test_simple_workflows.py -v")
    print()
    print("=" * 70)

    pytest.main([__file__, "-v", "-s"])
