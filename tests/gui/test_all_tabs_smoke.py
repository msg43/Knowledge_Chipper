"""
Comprehensive smoke tests for ALL GUI tabs.

This will definitively show which of the 122 static analysis warnings are real bugs
vs false positives by actually instantiating each tab and checking for AttributeErrors.
"""

import sys
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

try:
    from PyQt6.QtWidgets import QApplication

    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False


@pytest.mark.skipif(not PYQT_AVAILABLE, reason="PyQt6 not available")
class TestAllTabsSmoke:
    """Smoke tests for all GUI tabs to catch initialization bugs."""

    @pytest.fixture(scope="class")
    def qapp(self):
        """Create QApplication instance for tests."""
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        yield app

    def test_summarization_tab(self, qapp):
        """Test SummarizationTab instantiation."""
        from knowledge_system.gui.tabs.summarization_tab import SummarizationTab

        try:
            tab = SummarizationTab()
            assert tab is not None
            # Check a few key widgets
            assert hasattr(tab, "file_list"), "Missing file_list widget"
            assert hasattr(tab, "output_edit"), "Missing output_edit widget"
        except AttributeError as e:
            pytest.fail(f"SummarizationTab failed: {e}")

    def test_transcription_tab(self, qapp):
        """Test TranscriptionTab instantiation."""
        from knowledge_system.gui.tabs.transcription_tab import TranscriptionTab

        try:
            tab = TranscriptionTab()
            assert tab is not None
            # Check widgets flagged by static analysis
            assert hasattr(tab, "model_combo"), "Missing model_combo widget"
            assert hasattr(tab, "device_combo"), "Missing device_combo widget"
            assert hasattr(tab, "output_text"), "Missing output_text widget"
        except AttributeError as e:
            pytest.fail(f"TranscriptionTab failed: {e}")

    def test_api_keys_tab(self, qapp):
        """Test APIKeysTab instantiation."""
        from knowledge_system.gui.tabs.api_keys_tab import APIKeysTab

        try:
            tab = APIKeysTab()
            assert tab is not None
            # Check widgets flagged by static analysis
            assert hasattr(tab, "openai_key_edit"), "Missing openai_key_edit widget"
            assert hasattr(
                tab, "anthropic_key_edit"
            ), "Missing anthropic_key_edit widget"
            assert hasattr(tab, "status_label"), "Missing status_label widget"
        except AttributeError as e:
            pytest.fail(f"APIKeysTab failed: {e}")

    def test_batch_processing_tab(self, qapp):
        """Test BatchProcessingTab instantiation."""
        from knowledge_system.gui.tabs.batch_processing_tab import BatchProcessingTab

        try:
            # BatchProcessingTab requires main_window parameter
            tab = BatchProcessingTab(main_window=None)
            assert tab is not None
            # Check widgets flagged by static analysis
            assert hasattr(tab, "start_button"), "Missing start_button widget"
            assert hasattr(tab, "url_tree"), "Missing url_tree widget"
            assert hasattr(tab, "overall_progress"), "Missing overall_progress widget"
        except AttributeError as e:
            pytest.fail(f"BatchProcessingTab failed: {e}")

    def test_claim_search_tab(self, qapp):
        """Test ClaimSearchTab instantiation."""
        from knowledge_system.gui.tabs.claim_search_tab import ClaimSearchTab

        try:
            tab = ClaimSearchTab()
            assert tab is not None
            # Check widgets flagged by static analysis
            assert hasattr(tab, "results_list"), "Missing results_list widget"
        except AttributeError as e:
            pytest.fail(f"ClaimSearchTab failed: {e}")

    def test_cloud_uploads_tab(self, qapp):
        """Test CloudUploadsTab instantiation."""
        from knowledge_system.gui.tabs.cloud_uploads_tab import CloudUploadsTab

        try:
            tab = CloudUploadsTab()
            assert tab is not None
            # Check widgets that should exist (legacy email/password removed, OAuth only)
            assert hasattr(tab, "auth_status_label"), "Missing auth_status_label widget"
            assert hasattr(tab, "db_path_edit"), "Missing db_path_edit widget"
            assert hasattr(tab, "stats_label"), "Missing stats_label widget"
            # Note: email_edit, password_edit, legacy_auth_widget intentionally removed (OAuth only)
        except AttributeError as e:
            pytest.fail(f"CloudUploadsTab failed: {e}")

    def test_introduction_tab(self, qapp):
        """Test IntroductionTab instantiation."""
        from knowledge_system.gui.tabs.introduction_tab import IntroductionTab

        try:
            tab = IntroductionTab()
            assert tab is not None
        except AttributeError as e:
            pytest.fail(f"IntroductionTab failed: {e}")

    def test_monitor_tab(self, qapp):
        """Test MonitorTab instantiation."""
        from knowledge_system.gui.tabs.monitor_tab import MonitorTab

        try:
            tab = MonitorTab()
            assert tab is not None
            # Check widgets flagged by static analysis
            assert hasattr(
                tab, "auto_process_checkbox"
            ), "Missing auto_process_checkbox widget"
            assert hasattr(tab, "recent_files_list"), "Missing recent_files_list widget"
            assert hasattr(tab, "status_label"), "Missing status_label widget"
        except AttributeError as e:
            pytest.fail(f"MonitorTab failed: {e}")

    def test_process_tab(self, qapp):
        """Test ProcessTab instantiation."""
        from knowledge_system.gui.tabs.process_tab import ProcessTab

        try:
            tab = ProcessTab()
            assert tab is not None
            # Check widgets flagged by static analysis
            assert hasattr(tab, "files_list"), "Missing files_list widget"
            assert hasattr(tab, "results_list"), "Missing results_list widget"
            assert hasattr(
                tab, "transcribe_checkbox"
            ), "Missing transcribe_checkbox widget"
        except AttributeError as e:
            pytest.fail(f"ProcessTab failed: {e}")

    def test_prompts_tab(self, qapp):
        """Test PromptsTab instantiation."""
        from knowledge_system.gui.tabs.prompts_tab import PromptsTab

        try:
            tab = PromptsTab()
            assert tab is not None
            # Check widgets flagged by static analysis
            assert hasattr(tab, "prompt_list"), "Missing prompt_list widget"
            assert hasattr(tab, "prompt_editor"), "Missing prompt_editor widget"
        except AttributeError as e:
            pytest.fail(f"PromptsTab failed: {e}")

    def test_speaker_attribution_tab(self, qapp):
        """Test SpeakerAttributionTab instantiation."""
        from knowledge_system.gui.tabs.speaker_attribution_tab import (
            SpeakerAttributionTab,
        )

        try:
            tab = SpeakerAttributionTab()
            assert tab is not None
            # Check widgets flagged by static analysis
            assert hasattr(tab, "speaker_tree"), "Missing speaker_tree widget"
            assert hasattr(tab, "channel_name_edit"), "Missing channel_name_edit widget"
            assert hasattr(tab, "status_label"), "Missing status_label widget"
        except AttributeError as e:
            pytest.fail(f"SpeakerAttributionTab failed: {e}")

    def test_summary_cleanup_tab(self, qapp):
        """Test SummaryCleanupTab instantiation."""
        from knowledge_system.gui.tabs.summary_cleanup_tab import SummaryCleanupTab

        try:
            tab = SummaryCleanupTab()
            assert tab is not None
            # Check widgets flagged by static analysis
            assert hasattr(tab, "claims_list"), "Missing claims_list widget"
            assert hasattr(tab, "summary_edit"), "Missing summary_edit widget"
            assert hasattr(tab, "file_label"), "Missing file_label widget"
        except AttributeError as e:
            pytest.fail(f"SummaryCleanupTab failed: {e}")

    def test_sync_status_tab(self, qapp):
        """Test SyncStatusTab instantiation."""
        from knowledge_system.gui.tabs.sync_status_tab import SyncStatusTab

        try:
            tab = SyncStatusTab()
            assert tab is not None
            # Check widgets flagged by static analysis
            assert hasattr(tab, "status_label"), "Missing status_label widget"
            assert hasattr(tab, "table_tree"), "Missing table_tree widget"
            assert hasattr(tab, "progress_bar"), "Missing progress_bar widget"
        except AttributeError as e:
            pytest.fail(f"SyncStatusTab failed: {e}")


class TestWidgetAccessPatterns:
    """Test that widgets can be accessed in the ways they're used in code."""

    @pytest.fixture(scope="class")
    def qapp(self):
        """Create QApplication instance for tests."""
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        yield app

    def test_summarization_tab_widget_methods(self, qapp):
        """Test that SummarizationTab widgets support expected methods."""
        from knowledge_system.gui.tabs.summarization_tab import SummarizationTab

        tab = SummarizationTab()

        # Test widgets that should have .text()
        text_widgets = ["output_edit", "template_path_edit"]
        for widget_name in text_widgets:
            if hasattr(tab, widget_name):
                widget = getattr(tab, widget_name)
                assert hasattr(
                    widget, "text"
                ), f"{widget_name} should have .text() method"

        # Test widgets that should have .value()
        value_widgets = ["max_claims_spin"]
        for widget_name in value_widgets:
            if hasattr(tab, widget_name):
                widget = getattr(tab, widget_name)
                assert hasattr(
                    widget, "value"
                ), f"{widget_name} should have .value() method"

        # Test widgets that should have .currentText()
        combo_widgets = ["content_type_combo"]
        for widget_name in combo_widgets:
            if hasattr(tab, widget_name):
                widget = getattr(tab, widget_name)
                assert hasattr(
                    widget, "currentText"
                ), f"{widget_name} should have .currentText() method"

    def test_transcription_tab_widget_methods(self, qapp):
        """Test that TranscriptionTab widgets support expected methods."""
        from knowledge_system.gui.tabs.transcription_tab import TranscriptionTab

        tab = TranscriptionTab()

        # Test combo boxes
        combo_widgets = [
            "model_combo",
            "device_combo",
            "language_combo",
            "format_combo",
        ]
        for widget_name in combo_widgets:
            if hasattr(tab, widget_name):
                widget = getattr(tab, widget_name)
                assert hasattr(
                    widget, "currentText"
                ), f"{widget_name} should have .currentText() method"

        # Test checkboxes
        checkbox_widgets = [
            "diarization_checkbox",
            "timestamps_checkbox",
            "overwrite_checkbox",
        ]
        for widget_name in checkbox_widgets:
            if hasattr(tab, widget_name):
                widget = getattr(tab, widget_name)
                assert hasattr(
                    widget, "isChecked"
                ), f"{widget_name} should have .isChecked() method"

        # Test spinboxes
        spin_widgets = [
            "min_delay_spinbox",
            "max_delay_spinbox",
            "randomization_spinbox",
        ]
        for widget_name in spin_widgets:
            if hasattr(tab, widget_name):
                widget = getattr(tab, widget_name)
                assert hasattr(
                    widget, "value"
                ), f"{widget_name} should have .value() method"


if __name__ == "__main__":
    # Allow running directly with detailed output
    pytest.main([__file__, "-v", "--tb=short"])
