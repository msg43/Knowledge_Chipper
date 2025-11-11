"""
Smoke tests for SummarizationTab to catch initialization bugs.

These tests instantiate the GUI components to catch AttributeError bugs
that only appear at runtime.
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
class TestSummarizationTabSmoke:
    """Smoke tests for SummarizationTab initialization."""

    @pytest.fixture(scope="class")
    def qapp(self):
        """Create QApplication instance for tests."""
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        yield app

    def test_tab_instantiation(self, qapp):
        """Test that SummarizationTab can be instantiated without errors."""
        from knowledge_system.gui.tabs.summarization_tab import SummarizationTab

        # This should not raise AttributeError
        try:
            tab = SummarizationTab()
            assert tab is not None
        except AttributeError as e:
            pytest.fail(
                f"SummarizationTab instantiation failed with AttributeError: {e}"
            )

    def test_widget_attributes_exist(self, qapp):
        """Test that commonly used widget attributes exist."""
        from knowledge_system.gui.tabs.summarization_tab import SummarizationTab

        tab = SummarizationTab()

        # Check for widgets that are commonly referenced
        required_widgets = [
            "file_list",
            "output_edit",
            "template_path_edit",
            "provider_combo",
            "model_combo",
            "content_type_combo",
            "max_claims_spin",
        ]

        missing = []
        for widget_name in required_widgets:
            if not hasattr(tab, widget_name):
                missing.append(widget_name)

        if missing:
            pytest.fail(
                f"SummarizationTab missing required widgets: {', '.join(missing)}"
            )

    def test_start_processing_attributes(self, qapp):
        """Test that _start_processing can access all needed attributes."""
        from knowledge_system.gui.tabs.summarization_tab import SummarizationTab

        tab = SummarizationTab()

        # Attributes accessed in _start_processing
        required_attrs = [
            "miner_provider",
            "miner_model",
            "content_type_combo",
            "template_path_edit",
            "output_edit",
        ]

        missing = []
        for attr_name in required_attrs:
            if not hasattr(tab, attr_name):
                missing.append(attr_name)

        if missing:
            pytest.fail(
                f"SummarizationTab._start_processing would fail due to missing: {', '.join(missing)}"
            )

    def test_no_value_calls_on_missing_widgets(self, qapp):
        """Test that we don't call .value() on non-existent widgets."""
        import inspect
        import re

        from knowledge_system.gui.tabs.summarization_tab import SummarizationTab

        tab = SummarizationTab()

        # Get the source code of _start_processing
        source = inspect.getsource(tab._start_processing)

        # Find all self.X.value() calls
        value_pattern = r"self\.(\w+)\.value\(\)"
        value_calls = re.findall(value_pattern, source)

        # Check that all widgets exist
        missing = []
        for widget_name in value_calls:
            if not hasattr(tab, widget_name):
                missing.append(widget_name)

        if missing:
            pytest.fail(
                f"_start_processing calls .value() on missing widgets: {', '.join(missing)}\n"
                f"This would cause AttributeError at runtime!"
            )

    def test_no_text_calls_on_missing_widgets(self, qapp):
        """Test that we don't call .text() on non-existent widgets."""
        import inspect
        import re

        from knowledge_system.gui.tabs.summarization_tab import SummarizationTab

        tab = SummarizationTab()

        # Get the source code of _start_processing
        source = inspect.getsource(tab._start_processing)

        # Find all self.X.text() calls
        text_pattern = r"self\.(\w+)\.text\(\)"
        text_calls = re.findall(text_pattern, source)

        # Check that all widgets exist
        missing = []
        for widget_name in text_calls:
            if not hasattr(tab, widget_name):
                missing.append(widget_name)

        if missing:
            pytest.fail(
                f"_start_processing calls .text() on missing widgets: {', '.join(missing)}\n"
                f"This would cause AttributeError at runtime!"
            )


if __name__ == "__main__":
    # Allow running directly
    pytest.main([__file__, "-v"])
