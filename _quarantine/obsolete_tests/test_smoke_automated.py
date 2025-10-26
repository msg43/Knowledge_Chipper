"""
Automated smoke tests for GUI - verify basic functionality without human intervention.

All tests run with TESTING_MODE enabled to suppress dialogs.
"""

import os

import pytest

# Force testing mode before imports
os.environ["KNOWLEDGE_CHIPPER_TESTING_MODE"] = "1"
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication


@pytest.mark.gui
@pytest.mark.timeout(60)
def test_gui_launches_automated():
    """Verify GUI can launch without errors - fully automated."""
    from knowledge_system.gui.main_window_pyqt6 import MainWindow

    app = QApplication.instance() or QApplication([])

    try:
        window = MainWindow()
        assert window is not None
        assert window.tabs.count() == 7  # All 7 tabs present
        window.close()
    finally:
        app.processEvents()


@pytest.mark.gui
@pytest.mark.timeout(60)
def test_all_tabs_load_automated():
    """Verify all 7 tabs can be loaded - fully automated."""
    from knowledge_system.gui.main_window_pyqt6 import MainWindow

    app = QApplication.instance() or QApplication([])

    try:
        window = MainWindow()

        # Try switching to each tab
        for i in range(window.tabs.count()):
            window.tabs.setCurrentIndex(i)
            current_widget = window.tabs.currentWidget()
            assert current_widget is not None

            # Process events
            app.processEvents()

        window.close()
    finally:
        app.processEvents()


@pytest.mark.gui
@pytest.mark.timeout(60)
def test_no_dialogs_shown_in_testing_mode():
    """Verify TESTING_MODE suppresses all blocking dialogs - fully automated."""
    from knowledge_system.gui.main_window_pyqt6 import MainWindow

    app = QApplication.instance() or QApplication([])

    try:
        # This should NOT show any dialogs due to TESTING_MODE
        window = MainWindow()

        # If we got here without blocking, dialogs were suppressed
        assert window is not None

        window.close()
    finally:
        app.processEvents()


@pytest.mark.gui
@pytest.mark.timeout(60)
def test_tabs_have_expected_names():
    """Verify tab names are correct - fully automated."""
    from knowledge_system.gui.main_window_pyqt6 import MainWindow

    app = QApplication.instance() or QApplication([])

    try:
        window = MainWindow()

        expected_tabs = [
            "Introduction",
            "Transcribe",
            "Prompts",
            "Summarize",
            "Review",
            "Monitor",
            "Settings",
        ]

        for i, expected_name in enumerate(expected_tabs):
            actual_name = window.tabs.tabText(i)
            # Allow flexible matching
            assert (
                expected_name.lower() in actual_name.lower()
                or actual_name.lower() in expected_name.lower()
            ), f"Tab {i}: expected '{expected_name}', got '{actual_name}'"

        window.close()
    finally:
        app.processEvents()
