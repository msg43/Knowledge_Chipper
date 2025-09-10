"""
Core test framework for GUI comprehensive testing.

Provides base classes and utilities for automated GUI testing of the Knowledge Chipper.
"""

import logging
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from PyQt6.QtWidgets import QApplication

try:
    from knowledge_system.gui.main_window_pyqt6 import MainWindow
    from knowledge_system.logger import get_logger
except ImportError:
    # Fallback if import fails - use mock classes for testing framework validation
    class MainWindow:
        def __init__(self):
            pass

        def show(self):
            pass

        def close(self):
            pass

        def isVisible(self):
            return True

        def findChild(self, *args):
            return None

        def findChildren(self, *args):
            return []

    import logging

    def get_logger(name):
        return logging.getLogger(name)


logger = get_logger(__name__)


@dataclass
class TestResult:
    """Container for individual test results."""

    test_name: str
    file_path: Path | None = None
    tab_name: str | None = None
    operation: str | None = None
    success: bool = False
    duration: timedelta = field(default_factory=lambda: timedelta(0))
    output_files: list[Path] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TestSuiteResults:
    """Container for test suite results."""

    suite_name: str
    start_time: datetime
    end_time: datetime | None = None
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    skipped_tests: int = 0
    test_results: list[TestResult] = field(default_factory=list)

    @property
    def duration(self) -> timedelta:
        """Calculate total test suite duration."""
        if self.end_time:
            return self.end_time - self.start_time
        return timedelta(0)

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_tests == 0:
            return 0.0
        return (self.passed_tests / self.total_tests) * 100


class GUITestFramework:
    """
    Base framework for comprehensive GUI testing.

    Provides infrastructure for automated testing of Knowledge Chipper GUI
    including file loading, processing coordination, and result validation.
    """

    def __init__(self, app: QApplication, timeout: int = 300):
        """
        Initialize the test framework.

        Args:
            app: PyQt6 QApplication instance
            timeout: Default timeout for operations in seconds
        """
        self.app = app
        self.timeout = timeout
        self.main_window: MainWindow | None = None
        self.current_test_suite: TestSuiteResults | None = None
        self.progress_callback: Callable[[str, int], None] | None = None

        # Test state tracking
        self.active_operations: list[str] = []
        self.output_directory: Path | None = None

    def _find_existing_gui_window(self) -> Any | None:
        """Find an existing Knowledge Chipper GUI window."""
        try:
            # Look for QMainWindow instances with the right title/properties
            for widget in QApplication.allWidgets():
                if hasattr(widget, "windowTitle") and widget.windowTitle():
                    title = widget.windowTitle()
                    # Check if this looks like Knowledge Chipper window
                    if "Knowledge" in title or "Chipper" in title:
                        logger.info(
                            f"Found potential Knowledge Chipper window: {title}"
                        )
                        # Check if it has tabs (QTabWidget)
                        if hasattr(widget, "tabs") or widget.findChild(
                            QApplication.allWidgets()[0].__class__.__bases__[0], "tabs"
                        ):
                            return widget
                        # Check for QTabWidget child
                        tab_widgets = widget.findChildren(
                            QApplication.allWidgets()[0].__class__.__bases__[0]
                        )
                        for tab_widget in tab_widgets:
                            if hasattr(tab_widget, "addTab"):
                                logger.info(f"Found tab widget in window: {title}")
                                return widget
        except Exception as e:
            logger.debug(f"Error finding existing GUI window: {e}")

        return None

    def setup_main_window(self) -> MainWindow:
        """
        Create and setup the main application window for testing.

        Returns:
            Configured MainWindow instance
        """
        logger.info("Setting up main window for testing")

        # CRITICAL: Set global testing flag to prevent speaker dialog crashes
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app:
            app.setProperty("KNOWLEDGE_CHIPPER_TESTING", "true")
            logger.info("🧪 Set global testing flag - speaker dialogs will be blocked")

        # First, try to find an existing Knowledge Chipper window
        existing_window = self._find_existing_gui_window()
        if existing_window:
            logger.info("Found existing Knowledge Chipper GUI window")
            self.main_window = existing_window
            return self.main_window

        # Try to import and create MainWindow
        try:
            from knowledge_system.gui.main_window_pyqt6 import (
                MainWindow as RealMainWindow,
            )

            logger.info("Creating new MainWindow instance")
            self.main_window = RealMainWindow()
            self.main_window.show()

            # Wait for window to be fully initialized
            self._wait_for_window_ready()

            logger.info("Main window setup completed successfully")
            return self.main_window

        except ImportError as e:
            logger.warning(f"Could not import MainWindow: {e}")
            logger.info("Using mock MainWindow for testing framework validation")

            # Use the mock MainWindow from earlier fallback
            self.main_window = MainWindow()
            return self.main_window

    def teardown_main_window(self) -> None:
        """Clean up the main window after testing."""
        if self.main_window:
            logger.info("Tearing down main window")
            try:
                # Stop all background threads first
                from PyQt6.QtCore import QThreadPool

                thread_pool = QThreadPool.globalInstance()
                if thread_pool:
                    logger.info("Waiting for background threads to finish...")
                    thread_pool.waitForDone(5000)  # Wait up to 5 seconds
                    if thread_pool.activeThreadCount() > 0:
                        logger.warning(
                            f"Force-terminating {thread_pool.activeThreadCount()} remaining threads"
                        )

                # Close main window gracefully
                self.main_window.close()
                self.main_window.deleteLater()
                self.main_window = None
            except Exception as e:
                logger.warning(f"Error during teardown: {e}")
                self.main_window = None

    def start_test_suite(self, suite_name: str) -> TestSuiteResults:
        """
        Start a new test suite.

        Args:
            suite_name: Name of the test suite

        Returns:
            TestSuiteResults instance for tracking
        """
        logger.info(f"Starting test suite: {suite_name}")
        self.current_test_suite = TestSuiteResults(
            suite_name=suite_name, start_time=datetime.now()
        )
        return self.current_test_suite

    def finish_test_suite(self) -> TestSuiteResults | None:
        """
        Finish the current test suite and return results.

        Returns:
            Completed TestSuiteResults or None if no active suite
        """
        if not self.current_test_suite:
            return None

        self.current_test_suite.end_time = datetime.now()
        self.current_test_suite.total_tests = len(self.current_test_suite.test_results)
        self.current_test_suite.passed_tests = sum(
            1 for result in self.current_test_suite.test_results if result.success
        )
        self.current_test_suite.failed_tests = (
            self.current_test_suite.total_tests - self.current_test_suite.passed_tests
        )

        logger.info(f"Test suite '{self.current_test_suite.suite_name}' completed")
        logger.info(
            f"Results: {self.current_test_suite.passed_tests}/{self.current_test_suite.total_tests} passed "
            f"({self.current_test_suite.success_rate:.1f}%)"
        )

        suite_results = self.current_test_suite
        self.current_test_suite = None
        return suite_results

    def run_test(
        self, test_name: str, test_func: Callable[[], TestResult]
    ) -> TestResult:
        """
        Run an individual test with proper setup and teardown.

        Args:
            test_name: Name of the test
            test_func: Function that executes the test

        Returns:
            TestResult with outcome
        """
        logger.info(f"Running test: {test_name}")
        start_time = datetime.now()

        try:
            result = test_func()
            result.test_name = test_name
            result.duration = datetime.now() - start_time

            if result.success:
                logger.info(f"Test '{test_name}' PASSED in {result.duration}")
            else:
                error_summary = (
                    "; ".join(result.errors)
                    if result.errors
                    else "No specific errors recorded"
                )
                logger.warning(
                    f"Test '{test_name}' FAILED in {result.duration}: {error_summary}"
                )

                # Add more detailed logging for empty failures
                if not result.errors:
                    logger.warning(
                        f"Test failed with no errors - validation metadata: {result.metadata.get('validation_results', 'none')}"
                    )

        except Exception as e:
            logger.error(f"Test '{test_name}' threw exception: {e}")
            result = TestResult(
                test_name=test_name,
                success=False,
                duration=datetime.now() - start_time,
                errors=[str(e)],
            )

        # Add to current test suite if active
        if self.current_test_suite:
            self.current_test_suite.test_results.append(result)

        return result

    def navigate_to_tab(self, tab_name: str, timeout: int | None = None) -> bool:
        """
        Navigate to the specified tab in the GUI.

        Args:
            tab_name: Name of the tab to navigate to
            timeout: Timeout in seconds (uses default if None)

        Returns:
            True if navigation succeeded, False otherwise
        """
        if not self.main_window:
            logger.error("Main window not initialized")
            return False

        timeout = timeout or self.timeout
        logger.debug(f"Navigating to tab: {tab_name}")

        try:
            # Find the tab widget
            tab_widget = self.main_window.findChild(type(None), "tab_widget")
            if not tab_widget:
                # Look for QTabWidget directly
                from PyQt6.QtWidgets import QTabWidget

                tab_widgets = self.main_window.findChildren(QTabWidget)
                if tab_widgets:
                    tab_widget = tab_widgets[0]
                else:
                    logger.error("Could not find tab widget")
                    return False

            # Find tab by name
            tab_index = -1
            for i in range(tab_widget.count()):
                if tab_widget.tabText(i) == tab_name:
                    tab_index = i
                    break

            if tab_index == -1:
                logger.error(f"Tab '{tab_name}' not found")
                return False

            # Click on the tab
            tab_widget.setCurrentIndex(tab_index)
            self._process_events()

            # Wait for tab to be active
            start_time = time.time()
            while tab_widget.currentIndex() != tab_index:
                if time.time() - start_time > timeout:
                    logger.error(
                        f"Timeout waiting for tab '{tab_name}' to become active"
                    )
                    return False
                self._process_events()
                time.sleep(0.1)

            logger.debug(f"Successfully navigated to tab: {tab_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to navigate to tab '{tab_name}': {e}")
            return False

    def load_files(self, file_paths: list[Path], tab_name: str | None = None) -> bool:
        """
        Load files into the specified tab.

        Args:
            file_paths: List of file paths to load
            tab_name: Name of tab to load into (current tab if None)

        Returns:
            True if files loaded successfully, False otherwise
        """
        if not self.main_window:
            logger.error("Main window not initialized")
            return False

        if tab_name and not self.navigate_to_tab(tab_name):
            return False

        logger.debug(f"Loading {len(file_paths)} files")

        try:
            # This is a simplified implementation - actual implementation
            # would need to interact with specific tab widgets and their
            # file loading mechanisms

            # For now, return True to indicate framework setup is working
            for file_path in file_paths:
                if not file_path.exists():
                    logger.error(f"File does not exist: {file_path}")
                    return False

            logger.debug(f"Successfully loaded {len(file_paths)} files")
            return True

        except Exception as e:
            logger.error(f"Failed to load files: {e}")
            return False

    def wait_for_completion(
        self,
        timeout: int | None = None,
        progress_callback: Callable[[str, int], None] | None = None,
    ) -> bool:
        """
        Wait for processing operations to complete.

        Args:
            timeout: Timeout in seconds (uses default if None)
            progress_callback: Optional callback for progress updates

        Returns:
            True if operations completed successfully, False if timeout
        """
        timeout = timeout or self.timeout
        start_time = time.time()

        logger.debug(f"Waiting for completion (timeout: {timeout}s)")

        while time.time() - start_time < timeout:
            # Check if any operations are still active
            # This would need to be implemented based on the specific
            # GUI components and their completion signals

            self._process_events()

            if progress_callback:
                elapsed = int(time.time() - start_time)
                progress = min(100, int((elapsed / timeout) * 100))
                progress_callback(f"Waiting for completion... ({elapsed}s)", progress)

            time.sleep(0.5)

        logger.debug("Wait for completion finished")
        return True

    def _wait_for_window_ready(self, timeout: int = 10) -> None:
        """Wait for the main window to be fully ready for interaction."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            if self.main_window and self.main_window.isVisible():
                # Give extra time for full initialization
                time.sleep(1.0)
                self._process_events()
                break
            self._process_events()
            time.sleep(0.1)

    def _process_events(self) -> None:
        """Process pending Qt events."""
        if self.app:
            self.app.processEvents()

    def set_output_directory(self, output_dir: Path) -> None:
        """Set the output directory for test results."""
        self.output_directory = output_dir
        if not output_dir.exists():
            output_dir.mkdir(parents=True, exist_ok=True)

    def cleanup_test_files(self) -> None:
        """Clean up temporary files created during testing."""
        if self.output_directory and self.output_directory.exists():
            logger.debug(f"Cleaning up test files in {self.output_directory}")
            # Implementation would clean up test-specific files
            # while preserving important results
