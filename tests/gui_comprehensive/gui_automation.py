"""
GUI automation utilities for Knowledge Chipper testing.

Provides high-level automation functions for interacting with the Knowledge Chipper GUI
using PyQt6 testing capabilities.
"""

import time
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QLineEdit,
    QListWidget,
    QPushButton,
    QTabWidget,
    QWidget,
)

# Add the src directory to the Python path
try:
    from knowledge_system.logger import get_logger
except ImportError:
    import logging

    def get_logger(name):
        return logging.getLogger(name)


try:
    from .process_monitor import ProcessCleanup, get_global_monitor
except ImportError:
    # Fallback if process_monitor not available
    import logging

    logging.warning("ProcessCleanup import failed, using basic cleanup")

    class ProcessCleanup:
        @staticmethod
        def cleanup_knowledge_system_processes():
            """Basic process cleanup when full implementation unavailable."""
            import os

            import psutil

            current_pid = os.getpid()
            process_names = ["whisper", "ffmpeg", "sox"]
            killed_count = 0

            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    if proc.info["pid"] != current_pid and any(
                        name in proc.info["name"].lower() for name in process_names
                    ):
                        proc.terminate()
                        killed_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if killed_count > 0:
                logger.info(f"Basic cleanup killed {killed_count} processes")

    def get_global_monitor():
        return None


logger = get_logger(__name__)


class GUIAutomation:
    """
    High-level GUI automation for Knowledge Chipper testing with System 2 support.

    Provides methods for interacting with specific GUI components
    and workflows in the Knowledge Chipper application, including
    System 2 job tracking and orchestration features.
    """

    def __init__(self, main_window: Any, default_delay: int = 100):
        """
        Initialize GUI automation.

        Args:
            main_window: MainWindow instance to automate
            default_delay: Default delay between actions in milliseconds
        """
        self.main_window = main_window
        self.default_delay = default_delay

        # System 2 support
        self.db_service = None
        try:
            from knowledge_system.database import DatabaseService

            self.db_service = DatabaseService()
        except ImportError:
            logger.warning("System 2 DatabaseService not available")

    def get_current_jobs(self) -> list:
        """
        Get current System 2 jobs from database.

        Returns:
            List of active jobs
        """
        if not self.db_service:
            return []

        try:
            from knowledge_system.database.system2_models import Job

            with self.db_service.get_session() as session:
                jobs = session.query(Job).all()
                return [
                    {
                        "job_id": job.job_id,
                        "job_type": job.job_type,
                        "input_id": job.input_id,
                        "auto_process": job.auto_process,
                    }
                    for job in jobs
                ]
        except Exception as e:
            logger.error(f"Error getting jobs: {e}")
            return []

    def wait_for_job_completion(self, job_id: str, timeout: int = 300) -> bool:
        """
        Wait for a System 2 job to complete.

        Args:
            job_id: Job ID to wait for
            timeout: Maximum time to wait in seconds

        Returns:
            True if job completed successfully, False otherwise
        """
        if not self.db_service:
            return False

        try:
            from knowledge_system.database.system2_models import JobRun

            start_time = time.time()
            while time.time() - start_time < timeout:
                with self.db_service.get_session() as session:
                    job_runs = session.query(JobRun).filter_by(job_id=job_id).all()

                    if not job_runs:
                        time.sleep(1)
                        continue

                    latest_run = job_runs[-1]
                    if latest_run.status in ["succeeded", "failed", "cancelled"]:
                        return latest_run.status == "succeeded"

                time.sleep(1)

            return False
        except Exception as e:
            logger.error(f"Error waiting for job: {e}")
            return False

    def get_job_status(self, job_id: str) -> dict | None:
        """
        Get status of a System 2 job.

        Args:
            job_id: Job ID to check

        Returns:
            Dict with job status information
        """
        if not self.db_service:
            return None

        try:
            from knowledge_system.database.system2_models import Job, JobRun

            with self.db_service.get_session() as session:
                job = session.query(Job).filter_by(job_id=job_id).first()
                if not job:
                    return None

                job_runs = session.query(JobRun).filter_by(job_id=job_id).all()

                latest_run = job_runs[-1] if job_runs else None

                return {
                    "job_id": job.job_id,
                    "job_type": job.job_type,
                    "input_id": job.input_id,
                    "latest_status": latest_run.status if latest_run else "pending",
                    "attempt_count": len(job_runs),
                }
        except Exception as e:
            logger.error(f"Error getting job status: {e}")
            return None

    def click_button(self, button_text: str, parent: QWidget | None = None) -> bool:
        """
        Click a button by its text.

        Args:
            button_text: Text displayed on the button
            parent: Parent widget to search in (main window if None)

        Returns:
            True if button was found and clicked, False otherwise
        """
        search_widget = parent or self.main_window

        try:
            # First try to find buttons in the search widget
            buttons = search_widget.findChildren(QPushButton)

            # If no buttons found, search globally
            if not buttons:
                logger.debug("No buttons found in search widget, searching globally")
                app = QApplication.instance()
                if app:
                    for widget in app.allWidgets():
                        if isinstance(widget, QPushButton):
                            buttons.append(widget)

            logger.debug(f"Found {len(buttons)} QPushButton instances")
            for i, button in enumerate(buttons):
                logger.debug(
                    f"  Button {i}: text='{button.text()}', enabled={button.isEnabled()}, visible={button.isVisible()}"
                )

            # Look for exact text match first
            for button in buttons:
                if (
                    button.text() == button_text
                    and button.isEnabled()
                    and button.isVisible()
                ):
                    logger.info(f"Clicking button: {button_text}")
                    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
                    QTest.qWait(self.default_delay)
                    return True

            # If no exact match, try partial match
            for button in buttons:
                if (
                    button_text.lower() in button.text().lower()
                    and button.isEnabled()
                    and button.isVisible()
                ):
                    logger.info(
                        f"Clicking button (partial match): '{button.text()}' for '{button_text}'"
                    )
                    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
                    QTest.qWait(self.default_delay)
                    return True

            logger.warning(f"Button not found or not enabled: {button_text}")
            available_buttons = [btn.text() for btn in buttons if btn.isVisible()]
            logger.warning(f"Available visible buttons: {available_buttons}")
            return False

        except Exception as e:
            logger.error(f"Error clicking button '{button_text}': {e}")
            return False

    def get_available_buttons(self) -> list[str]:
        """
        Get a list of all available button texts in the GUI.

        Returns:
            List of button text strings
        """
        try:
            buttons = self.main_window.findChildren(QPushButton)

            # If no buttons found, search globally
            if not buttons:
                app = QApplication.instance()
                if app:
                    for widget in app.allWidgets():
                        if isinstance(widget, QPushButton):
                            buttons.append(widget)

            # Return only visible button texts
            return [
                btn.text() for btn in buttons if btn.isVisible() and btn.text().strip()
            ]

        except Exception as e:
            logger.error(f"Error getting available buttons: {e}")
            return []

    def find_button(
        self, button_text: str, parent: QWidget | None = None
    ) -> QPushButton | None:
        """
        Find a button by its text.

        Args:
            button_text: Text to search for in button labels
            parent: Optional parent widget to search within

        Returns:
            QPushButton if found, None otherwise
        """
        try:
            search_parent = parent or self.main_window
            buttons = search_parent.findChildren(QPushButton)

            # If no buttons found in main window, search globally
            if not buttons:
                app = QApplication.instance()
                if app:
                    for widget in app.allWidgets():
                        if isinstance(widget, QPushButton):
                            buttons.append(widget)

            for button in buttons:
                if button.isVisible() and button_text.lower() in button.text().lower():
                    return button

            return None
        except Exception as e:
            logger.error(f"Error finding button '{button_text}': {e}")
            return None

    def set_checkbox(
        self, checkbox_text: str, checked: bool, parent: QWidget | None = None
    ) -> bool:
        """
        Set a checkbox state by its text.

        Args:
            checkbox_text: Text associated with the checkbox
            checked: Desired checkbox state
            parent: Parent widget to search in (main window if None)

        Returns:
            True if checkbox was found and set, False otherwise
        """
        search_widget = parent or self.main_window

        try:
            # First try to find checkboxes in the search widget
            checkboxes = search_widget.findChildren(QCheckBox)

            # If no checkboxes found, search globally
            if not checkboxes:
                logger.debug("No checkboxes found in search widget, searching globally")
                app = QApplication.instance()
                if app:
                    for widget in app.allWidgets():
                        if isinstance(widget, QCheckBox):
                            checkboxes.append(widget)

            logger.debug(f"Found {len(checkboxes)} QCheckBox instances")
            for i, checkbox in enumerate(checkboxes):
                logger.debug(
                    f"  Checkbox {i}: text='{checkbox.text()}', enabled={checkbox.isEnabled()}, visible={checkbox.isVisible()}"
                )

            # Look for exact text match first
            for checkbox in checkboxes:
                if (
                    checkbox.text() == checkbox_text
                    and checkbox.isEnabled()
                    and checkbox.isVisible()
                ):
                    if checkbox.isChecked() != checked:
                        logger.info(f"Setting checkbox '{checkbox_text}' to {checked}")
                        QTest.mouseClick(checkbox, Qt.MouseButton.LeftButton)
                        QTest.qWait(self.default_delay)
                    return True

            # If no exact match, try partial match
            for checkbox in checkboxes:
                if (
                    checkbox_text.lower() in checkbox.text().lower()
                    and checkbox.isEnabled()
                    and checkbox.isVisible()
                ):
                    if checkbox.isChecked() != checked:
                        logger.info(
                            f"Setting checkbox (partial match): '{checkbox.text()}' to {checked} for '{checkbox_text}'"
                        )
                        QTest.mouseClick(checkbox, Qt.MouseButton.LeftButton)
                        QTest.qWait(self.default_delay)
                    return True

            logger.warning(f"Checkbox not found or not enabled: {checkbox_text}")
            available_checkboxes = [cb.text() for cb in checkboxes if cb.isVisible()]
            logger.warning(f"Available visible checkboxes: {available_checkboxes}")
            return False

        except Exception as e:
            logger.error(f"Error setting checkbox '{checkbox_text}': {e}")
            return False

    def set_text_field(
        self, field_name: str, text: str, parent: QWidget | None = None
    ) -> bool:
        """
        Set text in a text field.

        Args:
            field_name: Name or placeholder text of the field
            text: Text to enter
            parent: Parent widget to search in (main window if None)

        Returns:
            True if field was found and text was set, False otherwise
        """
        search_widget = parent or self.main_window

        try:
            text_fields = search_widget.findChildren(QLineEdit)
            for field in text_fields:
                if (
                    field.objectName() == field_name
                    or field.placeholderText() == field_name
                ) and field.isEnabled():
                    logger.debug(f"Setting text field '{field_name}' to: {text}")
                    field.clear()
                    field.setText(text)
                    QTest.qWait(self.default_delay)
                    return True

            logger.warning(f"Text field not found or not enabled: {field_name}")
            return False

        except Exception as e:
            logger.error(f"Error setting text field '{field_name}': {e}")
            return False

    def select_tab(self, tab_name: str) -> bool:
        """
        Select a tab by its name.

        Args:
            tab_name: Name of the tab to select

        Returns:
            True if tab was found and selected, False otherwise
        """
        try:
            # First try to find tabs in the main window
            tab_widgets = self.main_window.findChildren(QTabWidget)

            # If no tabs found in main window, search globally
            if not tab_widgets:
                logger.debug("No tabs found in main window, searching globally")
                app = QApplication.instance()
                if app:
                    # Find all QTabWidget instances in all top-level windows
                    for widget in app.allWidgets():
                        if isinstance(widget, QTabWidget):
                            tab_widgets.append(widget)
                            logger.debug(f"Found QTabWidget with {widget.count()} tabs")

            # Search through all found tab widgets
            for tab_widget in tab_widgets:
                for i in range(tab_widget.count()):
                    tab_text = tab_widget.tabText(i)
                    logger.debug(f"Checking tab {i}: '{tab_text}'")
                    if tab_text == tab_name:
                        logger.info(f"Selecting tab: {tab_name}")
                        tab_widget.setCurrentIndex(i)
                        QTest.qWait(
                            self.default_delay * 2
                        )  # Extra time for tab switching
                        return True

            # Log all available tabs for debugging
            available_tabs = []
            for tab_widget in tab_widgets:
                for i in range(tab_widget.count()):
                    available_tabs.append(tab_widget.tabText(i))
            logger.warning(
                f"Tab '{tab_name}' not found. Available tabs: {available_tabs}"
            )
            return False

        except Exception as e:
            logger.error(f"Error selecting tab '{tab_name}': {e}")
            return False

    def add_files_to_list(
        self, file_paths: list[Path], list_widget_name: str = None
    ) -> bool:
        """
        Add files to a file list widget.

        Args:
            file_paths: List of file paths to add
            list_widget_name: Name of the list widget (finds first if None)

        Returns:
            True if files were added successfully, False otherwise
        """
        try:
            # First try to find in main window
            list_widgets = self.main_window.findChildren(QListWidget)

            # If no widgets found in main window, search globally
            if not list_widgets:
                logger.debug("No list widgets found in main window, searching globally")
                app = QApplication.instance()
                if app:
                    for widget in app.allWidgets():
                        if isinstance(widget, QListWidget):
                            list_widgets.append(widget)

            logger.info(f"Found {len(list_widgets)} QListWidget instances")
            for i, widget in enumerate(list_widgets):
                logger.info(
                    f"  Widget {i}: objectName='{widget.objectName()}', visible={widget.isVisible()}, enabled={widget.isEnabled()}, parent={type(widget.parent()).__name__ if widget.parent() else 'None'}"
                )

            target_widget = None
            if list_widget_name:
                for widget in list_widgets:
                    if widget.objectName() == list_widget_name:
                        target_widget = widget
                        break
            else:
                # Simple approach: just use Widget 8 (the visible one)
                if len(list_widgets) >= 9:
                    target_widget = list_widgets[8]  # Widget 8 is visible
                    logger.info("Using Widget 8 (the visible one)")
                elif list_widgets:
                    target_widget = list_widgets[-1]  # Last available widget
                    logger.info("Using last available widget")
                else:
                    logger.warning("No QListWidget instances found at all")

            if target_widget is None:
                logger.warning(
                    f"File list widget not found - no widgets available (had {len(list_widgets)} total widgets)"
                )
                return False

            logger.info(
                f"✅ Successfully selected widget: objectName='{target_widget.objectName()}', visible={target_widget.isVisible()}, enabled={target_widget.isEnabled()}"
            )

            logger.info(
                f"Adding {len(file_paths)} files to list widget: {target_widget.objectName()}"
            )

            # Add files to the QListWidget
            files_added = 0
            for file_path in file_paths:
                if file_path.exists():
                    try:
                        # Add file path as string to the list widget
                        target_widget.addItem(str(file_path))
                        files_added += 1
                        logger.debug(f"Added file: {file_path}")
                    except Exception as e:
                        logger.warning(f"Failed to add file {file_path}: {e}")
                else:
                    logger.warning(f"File does not exist: {file_path}")

            QTest.qWait(self.default_delay)
            logger.info(
                f"Successfully added {files_added}/{len(file_paths)} files to list"
            )
            return files_added > 0

        except Exception as e:
            logger.error(f"Error adding files to list: {e}")
            return False

    def wait_for_processing_completion(self, timeout: int = 300) -> bool:
        """
        Wait for processing operations to complete with improved timeout handling.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if processing completed, False if timed out
        """
        start_time = time.time()

        logger.info(f"Waiting for processing completion (timeout: {timeout}s)")

        # First, wait a moment for processing to actually start
        QTest.qWait(2000)

        consecutive_no_change_count = 0
        last_button_state = None
        force_stop_attempted = False

        while time.time() - start_time < timeout:
            # Get all buttons and check their states
            buttons = self._get_all_buttons()

            processing_active = False
            start_button_ready = False
            stop_button_available = False

            # Log all visible buttons for debugging
            visible_buttons = []
            current_button_state = []

            for button in buttons:
                if button.isVisible():
                    button_text = button.text()
                    visible_buttons.append(
                        f"'{button_text}' ({'enabled' if button.isEnabled() else 'disabled'})"
                    )
                    current_button_state.append(
                        (button_text.lower(), button.isEnabled())
                    )

                    # Check for processing indicators
                    button_text_lower = button_text.lower()
                    if "processing" in button_text_lower:
                        # Processing buttons are usually disabled when actually processing
                        if not button.isEnabled():
                            processing_active = True
                    elif "stop processing" in button_text_lower:
                        if button.isEnabled():
                            stop_button_available = True
                            # If stop button is enabled, processing might be active
                        # Note: Don't set processing_active based on stop button alone
                    elif "stop transcription" in button_text_lower:
                        if button.isEnabled():
                            stop_button_available = True
                    elif (
                        "start transcription" in button_text_lower
                        or "start processing" in button_text_lower
                    ):
                        if button.isEnabled():
                            start_button_ready = True

            # Check for stuck state (same button configuration for too long)
            if current_button_state == last_button_state:
                consecutive_no_change_count += 1
            else:
                consecutive_no_change_count = 0
                last_button_state = current_button_state

            elapsed = time.time() - start_time
            logger.debug(
                f"Buttons at {elapsed:.1f}s: {', '.join(visible_buttons[:3])}..."
            )  # Limit log spam

            # Log detailed state every 30 seconds for long-running processes
            if elapsed > 60 and int(elapsed) % 30 == 0:
                self._log_detailed_gui_state(
                    elapsed, visible_buttons, processing_active, start_button_ready
                )

            # Processing is complete when:
            # 1. No processing indicators are active AND
            # 2. Start button is available again
            if not processing_active and start_button_ready:
                # Additional verification: check log output for completion messages
                log_output = self.get_output_log_text()
                completion_indicators = [
                    "✅ All transcriptions completed!",
                    "✅ Transcript saved successfully",
                    "Successfully transcribed and saved",
                ]

                has_completion_message = any(
                    indicator in log_output for indicator in completion_indicators
                )

                if has_completion_message:
                    logger.info("Processing completed - start button is ready again")
                    return True
                else:
                    logger.debug(
                        "Start button ready but no completion message found yet - waiting..."
                    )
                    QTest.qWait(1000)  # Wait a bit more for completion messages
            elif not processing_active and not start_button_ready:
                # If no processing active but start button not ready,
                # processing might be done but UI not updated yet
                logger.debug("No processing active, waiting for UI to update...")

            # Detect stuck state and force intervention
            # Make stuck detection much more conservative for longer files
            stuck_threshold = max(
                30, timeout * 0.2
            )  # At least 30 checks or 20% of timeout
            if (
                consecutive_no_change_count > stuck_threshold or elapsed > timeout * 0.9
            ) and not force_stop_attempted:
                # Before declaring stuck, do one final comprehensive check
                log_output = self.get_output_log_text()
                completion_indicators = [
                    "✅ All transcriptions completed!",
                    "✅ Transcript saved successfully",
                    "Successfully transcribed and saved",
                ]

                # Check for active processing indicators that suggest work is still happening
                active_indicators = [
                    "FFmpeg conversion",
                    "Running command: whisper-cli",
                    "Converting to .wav format",
                    "Audio conversion",
                    "Processing audio",
                    "speed=",  # FFmpeg progress indicator
                    "time=",  # FFmpeg time indicator
                    "size=",  # FFmpeg size indicator
                ]

                has_completion = any(
                    indicator in log_output for indicator in completion_indicators
                )
                has_active_processing = any(
                    indicator in log_output[-2000:] for indicator in active_indicators
                )  # Check recent logs
                current_start_ready = self._is_start_button_ready()

                if has_completion and current_start_ready:
                    logger.info(
                        "Processing actually completed - found completion message in logs"
                    )
                    return True
                elif has_active_processing:
                    logger.info(
                        f"Processing still active - found recent activity indicators, continuing to wait"
                    )
                    consecutive_no_change_count = (
                        0  # Reset counter since we found activity
                    )
                    continue

                logger.warning(
                    f"Processing appears stuck after {elapsed:.1f}s (no UI changes for {consecutive_no_change_count} cycles)"
                )

                if stop_button_available:
                    logger.info("Attempting graceful stop via stop button")
                    success = self._attempt_graceful_stop()
                    if success:
                        force_stop_attempted = True
                        QTest.qWait(5000)  # Wait longer for graceful stop
                        continue

                # If graceful stop not available or failed, try force methods
                logger.warning("Attempting force stop of stuck processes")
                self._attempt_force_stop()
                force_stop_attempted = True
                QTest.qWait(3000)  # Wait for force stop

                # After force stop, assume processing is done
                return True

            # Regular timeout check
            if elapsed > timeout * 0.95:  # At 95% of timeout
                logger.error(f"Final timeout reached at {elapsed:.1f}s, forcing stop")
                self._attempt_force_stop()
                return False

            logger.debug(
                f"Still processing... ({elapsed:.1f}s elapsed, no-change: {consecutive_no_change_count})"
            )
            QTest.qWait(2000)  # Wait 2 seconds before checking again

        logger.warning(f"Timeout waiting for processing completion ({timeout}s)")
        return False

    def _attempt_graceful_stop(self) -> bool:
        """Attempt graceful stop via GUI buttons."""
        stop_texts = ["Stop Processing", "Stop Transcription", "Cancel", "Abort"]

        for stop_text in stop_texts:
            if self.click_button(stop_text):
                logger.info(f"Successfully clicked stop button: {stop_text}")
                return True

        return False

    def _attempt_force_stop(self) -> None:
        """Force stop any running processes using multiple methods."""
        try:
            # Method 1: Use our process cleanup utility
            logger.info("Attempting process cleanup via ProcessCleanup")
            ProcessCleanup.cleanup_knowledge_system_processes()

            # Method 2: Try to force click any visible stop buttons (even disabled ones)
            buttons = self._get_all_buttons()
            for button in buttons:
                if "stop" in button.text().lower() and button.isVisible():
                    logger.warning(f"Force-clicking button: {button.text()}")
                    try:
                        button.click()  # Direct click, bypass enabled check
                    except Exception as e:
                        logger.debug(f"Force click failed: {e}")

            # Method 3: Additional manual process cleanup as fallback
            import os

            import psutil

            current_pid = os.getpid()
            process_names = ["whisper", "ffmpeg", "sox", "speech"]

            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    # Skip our own process and parent processes
                    if proc.info["pid"] == current_pid:
                        continue

                    proc_name = proc.info["name"].lower()
                    cmdline = " ".join(proc.info.get("cmdline", [])).lower()

                    # Check if this is a process we might need to kill
                    should_kill = False
                    for name in process_names:
                        if name in proc_name or name in cmdline:
                            # Extra safety check - don't kill GUI or test processes
                            if "gui" not in cmdline and "test" not in cmdline:
                                should_kill = True
                                break

                    if should_kill and proc.info["pid"] != current_pid:
                        logger.warning(
                            f"Force killing process: {proc.info['pid']} ({proc_name})"
                        )
                        try:
                            proc.terminate()  # SIGTERM first
                            proc.wait(timeout=3)
                        except (psutil.TimeoutExpired, psutil.NoSuchProcess):
                            try:
                                proc.kill()  # SIGKILL if SIGTERM didn't work
                            except psutil.NoSuchProcess:
                                pass  # Process already gone

                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            logger.info("Force stop procedures completed")

        except Exception as e:
            logger.error(f"Error during force stop: {e}")
            # Continue anyway - don't let cleanup errors stop the testing

    def _log_detailed_gui_state(
        self,
        elapsed: float,
        visible_buttons: list[str],
        processing_active: bool,
        start_button_ready: bool,
    ) -> None:
        """Log detailed GUI state for debugging long-running processes."""
        logger.info(f"=== GUI State at {elapsed:.0f}s ===")
        logger.info(f"Processing Active: {processing_active}")
        logger.info(f"Start Button Ready: {start_button_ready}")
        logger.info(
            f"Visible Buttons ({len(visible_buttons)}): {', '.join(visible_buttons)}"
        )

        # Check for error messages in GUI
        try:
            error_log = self.get_output_log_text()
            if error_log:
                error_lines = [
                    line for line in error_log.split("\n")[-10:] if line.strip()
                ]
                if error_lines:
                    logger.info(f"Recent log output: {'; '.join(error_lines[-3:])}")
        except Exception as e:
            logger.debug(f"Could not get output log: {e}")

        logger.info(f"=== End GUI State ===")

    def get_error_context_for_timeout(self) -> dict[str, Any]:
        """Get comprehensive error context when a timeout occurs."""
        context = {
            "timestamp": time.time(),
            "gui_state": {},
            "system_state": {},
            "process_info": {},
            "error_logs": [],
        }

        try:
            # GUI State
            buttons = self._get_all_buttons()
            context["gui_state"] = {
                "visible_buttons": [
                    f"{btn.text()} ({'enabled' if btn.isEnabled() else 'disabled'})"
                    for btn in buttons
                    if btn.isVisible()
                ],
                "total_buttons": len(buttons),
                "window_title": (
                    self.main_window.windowTitle()
                    if hasattr(self.main_window, "windowTitle")
                    else "Unknown"
                ),
            }

            # System State
            import psutil

            context["system_state"] = {
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_usage": psutil.disk_usage("/").percent,
            }

            # Process Information
            knowledge_processes = []
            for proc in psutil.process_iter(
                ["pid", "name", "cmdline", "cpu_percent", "memory_info"]
            ):
                try:
                    proc_name = proc.info["name"].lower()
                    cmdline = " ".join(proc.info.get("cmdline", [])).lower()

                    if any(
                        term in proc_name or term in cmdline
                        for term in ["whisper", "ffmpeg", "knowledge", "transcribe"]
                    ):
                        knowledge_processes.append(
                            {
                                "pid": proc.info["pid"],
                                "name": proc.info["name"],
                                "cpu_percent": proc.info["cpu_percent"],
                                "memory_mb": (
                                    proc.info["memory_info"].rss / (1024 * 1024)
                                    if proc.info["memory_info"]
                                    else 0
                                ),
                                "cmdline": " ".join(proc.info.get("cmdline", []))[:100]
                                + "...",
                            }
                        )
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            context["process_info"] = {
                "knowledge_processes": knowledge_processes,
                "total_processes": len(knowledge_processes),
            }

            # Error Logs
            try:
                output_text = self.get_output_log_text()
                if output_text:
                    lines = output_text.split("\n")
                    error_indicators = [
                        "error",
                        "failed",
                        "exception",
                        "timeout",
                        "killed",
                    ]
                    error_lines = [
                        line
                        for line in lines
                        if any(
                            indicator in line.lower() for indicator in error_indicators
                        )
                    ]
                    context["error_logs"] = error_lines[-10:]  # Last 10 error lines
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Error gathering timeout context: {e}")

        return context

    def reset_gui_state(self) -> bool:
        """
        Reset the GUI to a clean state for the next test.
        Clears file lists and stops any ongoing processing.

        Returns:
            True if reset successful, False otherwise
        """
        try:
            logger.info("Resetting GUI state for next test")

            # First, ensure we're on the right tab
            self.select_tab("Local Transcription")

            # Force stop any ongoing processing - try multiple approaches
            stop_attempts = ["Stop Processing", "Stop Transcription", "Cancel", "Abort"]

            # First try to click enabled stop buttons
            for stop_text in stop_attempts:
                if self.click_button(stop_text):
                    logger.info(f"Successfully stopped processing with: {stop_text}")
                    QTest.qWait(2000)  # Wait longer for stop to take effect
                    break

            # If no enabled button found, try to force-click any visible stop button
            buttons = self._get_all_buttons()
            for button in buttons:
                if (
                    "stop" in button.text().lower()
                    and "processing" in button.text().lower()
                    and button.isVisible()
                ):
                    logger.warning(f"Force-clicking stop button: {button.text()}")
                    button.click()
                    QTest.qWait(2000)
                    break

            # Wait longer for any background processes to complete
            QTest.qWait(5000)

            # Force GUI refresh - multiple attempts
            for _ in range(3):
                QApplication.processEvents()
                QTest.qWait(1000)

            # Clear any file lists
            app = QApplication.instance()
            if app:
                for widget in app.allWidgets():
                    if isinstance(widget, QListWidget) and widget.isVisible():
                        old_count = widget.count()
                        widget.clear()
                        logger.debug(f"Cleared list widget with {old_count} items")

            # Force a complete GUI repaint
            if self.main_window:
                self.main_window.repaint()
                self.main_window.update()
                QApplication.processEvents()
                QTest.qWait(2000)

            # Verify the start button is back
            available_buttons = self.get_available_buttons()
            start_button_ready = any("Start" in btn for btn in available_buttons)

            if start_button_ready:
                logger.info("✅ Start button is ready after reset")
            else:
                logger.warning(
                    f"⚠️ Start button not ready. Available: {available_buttons}"
                )

                # AGGRESSIVE RESET: Manually fix stuck buttons
                self._force_reset_button_states()

                # Try one more aggressive reset
                QApplication.processEvents()
                QTest.qWait(3000)

            logger.info("GUI state reset completed")
            return True

        except Exception as e:
            logger.error(f"Error resetting GUI state: {e}")
            return False

    def _force_reset_button_states(self) -> None:
        """
        Aggressively reset button states when normal methods fail.
        This directly manipulates button text and enabled state.
        """
        try:
            logger.info("🔧 Force-resetting button states...")

            app = QApplication.instance()
            if not app:
                return

            # Find all buttons and reset any that look stuck
            for widget in app.allWidgets():
                if isinstance(widget, QPushButton) and widget.isVisible():
                    button_text = widget.text()

                    # Reset "Processing..." buttons back to their start state
                    if "Processing" in button_text and not widget.isEnabled():
                        logger.warning(
                            f"Resetting stuck button: '{button_text}' -> enabled"
                        )
                        widget.setEnabled(True)

                        # Try to restore original text based on context
                        if (
                            "transcription" in button_text.lower()
                            or "Transcription" in button_text
                        ):
                            widget.setText("Start Transcription")
                        elif "processing" in button_text.lower():
                            widget.setText("Start Processing")
                        else:
                            # Generic fallback
                            widget.setText("Start")

                        QApplication.processEvents()
                        QTest.qWait(100)

                    # Enable any disabled "Stop" buttons
                    elif "Stop" in button_text and not widget.isEnabled():
                        logger.warning(f"Re-enabling stop button: '{button_text}'")
                        widget.setEnabled(True)
                        QApplication.processEvents()
                        QTest.qWait(100)

            logger.info("🔧 Button state reset completed")

        except Exception as e:
            logger.error(f"Error in force button reset: {e}")

    def _get_all_buttons(self) -> list:
        """Get all QPushButton instances in the application."""
        buttons = []

        # First try main window
        if hasattr(self, "main_window") and self.main_window:
            buttons.extend(self.main_window.findChildren(QPushButton))

        # Then search globally
        app = QApplication.instance()
        if app:
            for widget in app.allWidgets():
                if isinstance(widget, QPushButton):
                    buttons.append(widget)

        return list(set(buttons))  # Remove duplicates

    def _is_start_button_ready(self) -> bool:
        """Check if the start button is ready (visible and enabled)."""
        try:
            buttons = self.main_window.findChildren(QPushButton)

            for button in buttons:
                if button.isVisible():
                    button_text_lower = button.text().lower()
                    if (
                        "start transcription" in button_text_lower
                        or "start processing" in button_text_lower
                    ):
                        return button.isEnabled()

            return False
        except Exception as e:
            logger.error(f"Error checking start button ready state: {e}")
            return False

    def get_output_log_text(self) -> str:
        """
        Get text from the output log area.

        Returns:
            Text content from the output log
        """
        try:
            # Look for output text areas - this would need to be customized
            # based on the actual GUI implementation
            from PyQt6.QtWidgets import QPlainTextEdit, QTextEdit

            text_widgets = self.main_window.findChildren(
                QTextEdit
            ) + self.main_window.findChildren(QPlainTextEdit)

            for widget in text_widgets:
                if (
                    "output" in widget.objectName().lower()
                    or "log" in widget.objectName().lower()
                ):
                    return widget.toPlainText()

            # If no specific output widget found, return text from the largest text widget
            if text_widgets:
                return max(
                    text_widgets, key=lambda w: len(w.toPlainText())
                ).toPlainText()

            return ""

        except Exception as e:
            logger.error(f"Error getting output log text: {e}")
            return ""

    def check_for_errors(self) -> list[str]:
        """
        Check for error messages in the GUI.

        Returns:
            List of error messages found
        """
        errors = []

        try:
            # Get output log text and scan for error indicators
            log_text = self.get_output_log_text()

            error_indicators = ["error", "failed", "exception", "❌"]

            for line in log_text.split("\n"):
                line_lower = line.lower()
                if any(indicator in line_lower for indicator in error_indicators):
                    errors.append(line.strip())

            return errors

        except Exception as e:
            logger.error(f"Error checking for errors: {e}")
            return [f"Error checking for errors: {e}"]

    def get_progress_info(self) -> dict[str, Any]:
        """
        Get current progress information from progress bars/indicators.

        Returns:
            Dictionary with progress information
        """
        progress_info = {
            "current": 0,
            "total": 100,
            "percentage": 0,
            "status": "unknown",
        }

        try:
            from PyQt6.QtWidgets import QProgressBar

            progress_bars = self.main_window.findChildren(QProgressBar)

            if progress_bars:
                # Use the first visible progress bar
                for progress_bar in progress_bars:
                    if progress_bar.isVisible():
                        progress_info["current"] = progress_bar.value()
                        progress_info["total"] = progress_bar.maximum()
                        if progress_info["total"] > 0:
                            progress_info["percentage"] = (
                                progress_info["current"] / progress_info["total"]
                            ) * 100
                        break

            return progress_info

        except Exception as e:
            logger.error(f"Error getting progress info: {e}")
            return progress_info

    def find_widget_by_text(
        self, text: str, widget_type: type = None
    ) -> QWidget | None:
        """
        Find a widget by its displayed text.

        Args:
            text: Text to search for
            widget_type: Specific widget type to search for (any if None)

        Returns:
            Found widget or None
        """
        try:
            if widget_type:
                widgets = self.main_window.findChildren(widget_type)
            else:
                widgets = self.main_window.findChildren(QWidget)

            for widget in widgets:
                # Check various text properties
                widget_text = ""

                if hasattr(widget, "text"):
                    widget_text = widget.text()
                elif hasattr(widget, "title"):
                    widget_text = widget.title()
                elif hasattr(widget, "windowTitle"):
                    widget_text = widget.windowTitle()

                if text in widget_text:
                    return widget

            return None

        except Exception as e:
            logger.error(f"Error finding widget by text '{text}': {e}")
            return None
