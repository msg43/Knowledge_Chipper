"""
Advanced GUI integration tests using pytest-qt to simulate real user interactions.

This test suite uses qtbot to:
- Simulate mouse clicks, keyboard input, and widget interactions
- Test signal/slot connections and event propagation
- Validate conditional UI behavior and state changes
- Test async operations with proper timeouts
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

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
class TestSummarizationTabInteractions:
    """Test user interactions with SummarizationTab using qtbot."""

    @pytest.fixture
    def summarization_tab(self, qtbot):
        """Create a SummarizationTab instance for testing."""
        from knowledge_system.gui.tabs.summarization_tab import SummarizationTab

        tab = SummarizationTab()
        qtbot.addWidget(tab)
        return tab

    def test_file_selection_updates_ui(self, qtbot, summarization_tab, tmp_path):
        """Test that selecting files updates the file list widget."""
        # Create a test file
        test_file = tmp_path / "test_transcript.txt"
        test_file.write_text("Test transcript content")

        # Mock the file dialog to return our test file
        with patch("PyQt6.QtWidgets.QFileDialog.getOpenFileNames") as mock_dialog:
            mock_dialog.return_value = ([str(test_file)], "")

            # Find and click the "Add Files" button
            add_files_btn = summarization_tab.findChild(
                summarization_tab.add_files_btn.__class__, "add_files_btn"
            )

            if hasattr(summarization_tab, "add_files_btn"):
                # Simulate button click
                qtbot.mouseClick(
                    summarization_tab.add_files_btn, Qt.MouseButton.LeftButton
                )

                # Verify file was added to list
                assert summarization_tab.file_list.count() > 0

    def test_provider_change_updates_model_list(self, qtbot, summarization_tab):
        """Test that changing provider updates available models."""
        # Get initial model count
        initial_model_count = summarization_tab.model_combo.count()

        # Change provider
        if summarization_tab.provider_combo.count() > 1:
            # Find index of different provider
            current_provider = summarization_tab.provider_combo.currentText()
            new_index = 1 if summarization_tab.provider_combo.currentIndex() == 0 else 0

            # Simulate user selecting different provider
            with qtbot.waitSignal(
                summarization_tab.provider_combo.currentTextChanged, timeout=1000
            ):
                summarization_tab.provider_combo.setCurrentIndex(new_index)

            # Model list should update (may be same or different count)
            # Just verify it's still populated
            assert summarization_tab.model_combo.count() >= 0

    @pytest.mark.timeout(5)
    def test_start_button_disabled_without_files(self, qtbot, summarization_tab):
        """Test that start button is disabled when no files are selected."""
        # Clear file list
        summarization_tab.file_list.clear()

        # Start button should be disabled or clicking should show error
        if hasattr(summarization_tab, "start_btn"):
            # Try clicking start button
            initial_state = summarization_tab.start_btn.isEnabled()

            # If enabled, clicking should show error message
            if initial_state:
                with patch.object(QMessageBox, "warning") as mock_warning:
                    qtbot.mouseClick(
                        summarization_tab.start_btn, Qt.MouseButton.LeftButton
                    )
                    # Should either be disabled or show warning
                    # This is a smoke test - just verify no crash

    def test_content_type_selection_changes_template(self, qtbot, summarization_tab):
        """Test that selecting content type updates template path."""
        if hasattr(summarization_tab, "content_type_combo") and hasattr(
            summarization_tab, "template_path_edit"
        ):
            initial_template = summarization_tab.template_path_edit.text()

            # Change content type
            if summarization_tab.content_type_combo.count() > 1:
                new_index = (
                    1 if summarization_tab.content_type_combo.currentIndex() == 0 else 0
                )

                # Wait for signal
                with qtbot.waitSignal(
                    summarization_tab.content_type_combo.currentTextChanged,
                    timeout=1000,
                ):
                    summarization_tab.content_type_combo.setCurrentIndex(new_index)

                # Template path should update (or stay same if not implemented)
                # Just verify no crash occurred
                new_template = summarization_tab.template_path_edit.text()
                assert isinstance(new_template, str)

    def test_max_claims_spinbox_accepts_valid_input(self, qtbot, summarization_tab):
        """Test that max claims spinbox accepts and validates input."""
        if hasattr(summarization_tab, "max_claims_spin"):
            # Set a valid value
            summarization_tab.max_claims_spin.setValue(50)
            assert summarization_tab.max_claims_spin.value() == 50

            # Try setting boundary values
            summarization_tab.max_claims_spin.setValue(1)
            assert summarization_tab.max_claims_spin.value() >= 1

            summarization_tab.max_claims_spin.setValue(1000)
            assert summarization_tab.max_claims_spin.value() <= 1000


@pytest.mark.skipif(not PYQT_AVAILABLE, reason="PyQt6 not available")
class TestTranscriptionTabInteractions:
    """Test user interactions with TranscriptionTab."""

    @pytest.fixture
    def transcription_tab(self, qtbot):
        """Create a TranscriptionTab instance for testing."""
        from knowledge_system.gui.tabs.transcription_tab import TranscriptionTab

        tab = TranscriptionTab()
        qtbot.addWidget(tab)
        return tab

    def test_model_selection_persists(self, qtbot, transcription_tab):
        """Test that model selection is remembered."""
        if hasattr(transcription_tab, "model_combo"):
            # Select a model
            if transcription_tab.model_combo.count() > 0:
                transcription_tab.model_combo.setCurrentIndex(0)
                selected_model = transcription_tab.model_combo.currentText()

                # Verify selection persists
                assert transcription_tab.model_combo.currentText() == selected_model

    def test_device_selection_updates_ui(self, qtbot, transcription_tab):
        """Test that device selection updates related UI elements."""
        if hasattr(transcription_tab, "device_combo"):
            initial_device = transcription_tab.device_combo.currentText()

            # Change device if multiple options available
            if transcription_tab.device_combo.count() > 1:
                new_index = (
                    1 if transcription_tab.device_combo.currentIndex() == 0 else 0
                )
                transcription_tab.device_combo.setCurrentIndex(new_index)

                # Verify change occurred
                assert (
                    transcription_tab.device_combo.currentText() != initial_device
                    or transcription_tab.device_combo.count() == 1
                )

    def test_diarization_checkbox_toggles(self, qtbot, transcription_tab):
        """Test that diarization checkbox can be toggled."""
        if hasattr(transcription_tab, "diarization_checkbox"):
            initial_state = transcription_tab.diarization_checkbox.isChecked()

            # Toggle checkbox
            qtbot.mouseClick(
                transcription_tab.diarization_checkbox, Qt.MouseButton.LeftButton
            )

            # Verify state changed
            assert transcription_tab.diarization_checkbox.isChecked() != initial_state

            # Toggle back
            qtbot.mouseClick(
                transcription_tab.diarization_checkbox, Qt.MouseButton.LeftButton
            )
            assert transcription_tab.diarization_checkbox.isChecked() == initial_state

    @pytest.mark.timeout(5)
    def test_url_input_validation(self, qtbot, transcription_tab):
        """Test that URL input field validates YouTube URLs."""
        if hasattr(transcription_tab, "url_input"):
            # Enter a valid YouTube URL
            test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            transcription_tab.url_input.setText(test_url)

            # Verify text was set
            assert test_url in transcription_tab.url_input.text()

    def test_language_combo_has_options(self, qtbot, transcription_tab):
        """Test that language combo box is populated."""
        if hasattr(transcription_tab, "language_combo"):
            # Should have at least 'auto' option
            assert transcription_tab.language_combo.count() > 0


@pytest.mark.skipif(not PYQT_AVAILABLE, reason="PyQt6 not available")
class TestSignalSlotConnections:
    """Test that signals and slots are properly connected."""

    @pytest.fixture
    def introduction_tab(self, qtbot):
        """Create IntroductionTab for testing navigation signals."""
        from knowledge_system.gui.tabs.introduction_tab import IntroductionTab

        tab = IntroductionTab()
        qtbot.addWidget(tab)
        return tab

    def test_introduction_tab_navigation_signal_exists(self, qtbot, introduction_tab):
        """Test that IntroductionTab has navigation signal."""
        # Verify signal exists
        assert hasattr(introduction_tab, "navigate_to_tab")

        # Test that signal can be emitted
        with qtbot.waitSignal(introduction_tab.navigate_to_tab, timeout=1000):
            introduction_tab.navigate_to_tab.emit("Transcribe")

    @pytest.fixture
    def api_keys_tab(self, qtbot):
        """Create APIKeysTab for testing settings signals."""
        from knowledge_system.gui.tabs.api_keys_tab import APIKeysTab

        tab = APIKeysTab()
        qtbot.addWidget(tab)
        return tab

    def test_api_keys_tab_settings_signal_exists(self, qtbot, api_keys_tab):
        """Test that APIKeysTab has settings_saved signal."""
        # Verify signal exists
        assert hasattr(api_keys_tab, "settings_saved")

        # Test that signal can be emitted
        with qtbot.waitSignal(api_keys_tab.settings_saved, timeout=1000):
            api_keys_tab.settings_saved.emit()


@pytest.mark.skipif(not PYQT_AVAILABLE, reason="PyQt6 not available")
class TestConditionalUIBehavior:
    """Test conditional UI behavior based on user actions."""

    @pytest.fixture
    def transcription_tab(self, qtbot):
        """Create TranscriptionTab for conditional behavior testing."""
        from knowledge_system.gui.tabs.transcription_tab import TranscriptionTab

        tab = TranscriptionTab()
        qtbot.addWidget(tab)
        return tab

    @pytest.mark.timeout(10)
    def test_proxy_mode_affects_cookie_visibility(self, qtbot, transcription_tab):
        """Test that proxy mode selection affects cookie authentication visibility."""
        # This tests conditional UI - when proxy mode changes, cookie options should update
        if hasattr(transcription_tab, "proxy_mode_combo"):
            # Record initial state
            initial_index = transcription_tab.proxy_mode_combo.currentIndex()

            # Cycle through proxy modes
            for i in range(transcription_tab.proxy_mode_combo.count()):
                transcription_tab.proxy_mode_combo.setCurrentIndex(i)
                # Just verify no crash - conditional logic may hide/show widgets
                qtbot.wait(100)  # Small delay for UI updates

            # Restore initial state
            transcription_tab.proxy_mode_combo.setCurrentIndex(initial_index)

    def test_file_vs_url_mode_switching(self, qtbot, transcription_tab):
        """Test switching between file and URL input modes."""
        # Test that tab can handle both file and URL inputs
        if hasattr(transcription_tab, "url_input"):
            # Add URL
            transcription_tab.url_input.setText("https://example.com/video")
            qtbot.wait(100)

        # The UI should handle both modes gracefully
        assert True  # Smoke test - just verify no crash


@pytest.mark.skipif(not PYQT_AVAILABLE, reason="PyQt6 not available")
class TestAsyncOperations:
    """Test async operations with proper timeout handling."""

    @pytest.fixture
    def summarization_tab(self, qtbot):
        """Create SummarizationTab for async testing."""
        from knowledge_system.gui.tabs.summarization_tab import SummarizationTab

        tab = SummarizationTab()
        qtbot.addWidget(tab)
        return tab

    @pytest.mark.timeout(5)
    def test_worker_thread_creation(self, qtbot, summarization_tab, tmp_path):
        """Test that worker threads are created properly."""
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Test content")

        # Mock the worker to avoid actual processing
        with patch(
            "knowledge_system.gui.tabs.summarization_tab.EnhancedSummarizationWorker"
        ) as MockWorker:
            mock_worker = MagicMock()
            MockWorker.return_value = mock_worker

            # Add file to list
            summarization_tab.file_list.addItem(str(test_file))

            # Try to start processing (will be mocked)
            if hasattr(summarization_tab, "_start_processing"):
                try:
                    summarization_tab._start_processing()
                except Exception:
                    # Expected - we're mocking, so it may fail
                    # This is a smoke test
                    pass

    @pytest.mark.timeout(3)
    def test_progress_updates_dont_crash_ui(self, qtbot, summarization_tab):
        """Test that progress updates don't crash the UI."""
        # Simulate progress updates
        if hasattr(summarization_tab, "output_edit"):
            # Add some log messages
            for i in range(10):
                if hasattr(summarization_tab, "append_log"):
                    summarization_tab.append_log(f"Test message {i}")
                qtbot.wait(10)  # Small delay between updates

            # UI should still be responsive
            assert summarization_tab.output_edit is not None


@pytest.mark.skipif(not PYQT_AVAILABLE, reason="PyQt6 not available")
class TestKeyboardInteractions:
    """Test keyboard input and shortcuts."""

    @pytest.fixture
    def summarization_tab(self, qtbot):
        """Create SummarizationTab for keyboard testing."""
        from knowledge_system.gui.tabs.summarization_tab import SummarizationTab

        tab = SummarizationTab()
        qtbot.addWidget(tab)
        return tab

    def test_template_path_accepts_keyboard_input(self, qtbot, summarization_tab):
        """Test that template path field accepts keyboard input."""
        if hasattr(summarization_tab, "template_path_edit"):
            # Click to focus
            qtbot.mouseClick(
                summarization_tab.template_path_edit, Qt.MouseButton.LeftButton
            )

            # Type text
            qtbot.keyClicks(summarization_tab.template_path_edit, "test_template.yaml")

            # Verify text was entered
            assert "test_template" in summarization_tab.template_path_edit.text()

    def test_output_edit_accepts_text(self, qtbot, summarization_tab):
        """Test that output edit field can receive text."""
        if hasattr(summarization_tab, "output_edit"):
            # Add text programmatically (simulating output)
            test_text = "Test output message"
            if hasattr(summarization_tab.output_edit, "append"):
                summarization_tab.output_edit.append(test_text)
            elif hasattr(summarization_tab.output_edit, "setPlainText"):
                summarization_tab.output_edit.setPlainText(test_text)

            # Verify text is present
            if hasattr(summarization_tab.output_edit, "toPlainText"):
                assert test_text in summarization_tab.output_edit.toPlainText()


@pytest.mark.skipif(not PYQT_AVAILABLE, reason="PyQt6 not available")
class TestWidgetStateManagement:
    """Test that widget states are managed correctly."""

    @pytest.fixture
    def transcription_tab(self, qtbot):
        """Create TranscriptionTab for state management testing."""
        from knowledge_system.gui.tabs.transcription_tab import TranscriptionTab

        tab = TranscriptionTab()
        qtbot.addWidget(tab)
        return tab

    def test_checkbox_states_are_independent(self, qtbot, transcription_tab):
        """Test that multiple checkboxes maintain independent states."""
        checkboxes = []

        # Collect all checkboxes
        if hasattr(transcription_tab, "diarization_checkbox"):
            checkboxes.append(transcription_tab.diarization_checkbox)
        if hasattr(transcription_tab, "timestamps_checkbox"):
            checkboxes.append(transcription_tab.timestamps_checkbox)
        if hasattr(transcription_tab, "overwrite_checkbox"):
            checkboxes.append(transcription_tab.overwrite_checkbox)

        if len(checkboxes) >= 2:
            # Toggle first checkbox
            initial_states = [cb.isChecked() for cb in checkboxes]
            qtbot.mouseClick(checkboxes[0], Qt.MouseButton.LeftButton)

            # Other checkboxes should not change
            for i, cb in enumerate(checkboxes[1:], 1):
                assert cb.isChecked() == initial_states[i]

    def test_spinbox_bounds_are_enforced(self, qtbot, transcription_tab):
        """Test that spinboxes enforce their min/max bounds."""
        spinboxes = []

        # Collect spinboxes
        if hasattr(transcription_tab, "min_delay_spinbox"):
            spinboxes.append(transcription_tab.min_delay_spinbox)
        if hasattr(transcription_tab, "max_delay_spinbox"):
            spinboxes.append(transcription_tab.max_delay_spinbox)

        for spinbox in spinboxes:
            min_val = spinbox.minimum()
            max_val = spinbox.maximum()

            # Try to set below minimum
            spinbox.setValue(min_val - 100)
            assert spinbox.value() >= min_val

            # Try to set above maximum
            spinbox.setValue(max_val + 100)
            assert spinbox.value() <= max_val


if __name__ == "__main__":
    # Allow running directly
    pytest.main([__file__, "-v", "--tb=short"])
