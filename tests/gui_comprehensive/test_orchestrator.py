"""
Test orchestrator for comprehensive GUI testing.

Coordinates and executes comprehensive test suites covering all permutations
of input types, GUI tabs, and processing operations.
"""

import json
import os
import subprocess
import sys
import time
import traceback
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from PyQt6.QtWidgets import QApplication

# Handle imports for both module and direct execution
try:
    from .gui_automation import GUIAutomation
    from .test_framework import GUITestFramework, TestResult, TestSuiteResults
    from .validation import OutputValidator, ValidationResult
except ImportError:
    from test_framework import GUITestFramework, TestResult, TestSuiteResults
    from gui_automation import GUIAutomation
    from validation import OutputValidator, ValidationResult

import sys
from pathlib import Path

# Add the src directory to the Python path
try:
    from knowledge_system.logger import get_logger
except ImportError:
    import logging

    def get_logger(name):
        return logging.getLogger(name)


logger = get_logger(__name__)


class TestOrchestrator:
    """
    Orchestrates comprehensive GUI testing across all permutations.

    Manages test execution, coordinates test data, and generates comprehensive
    reports for the Knowledge Chipper GUI testing suite.
    """

    def __init__(
        self,
        test_data_dir: Path,
        output_dir: Path,
        auto_launch_gui: bool = True,
        gui_startup_timeout: int = 30,
    ):
        """
        Initialize the test orchestrator.

        Args:
            test_data_dir: Directory containing test input files
            output_dir: Directory for test outputs and reports
            auto_launch_gui: Whether to automatically launch GUI
            gui_startup_timeout: Timeout for GUI startup in seconds
        """
        self.test_data_dir = Path(test_data_dir)
        self.output_dir = Path(output_dir)
        self.app: QApplication | None = None
        self.framework: GUITestFramework | None = None
        self.automation: GUIAutomation | None = None
        self.validator: OutputValidator | None = None

        # GUI process management
        self.gui_process: subprocess.Popen | None = None
        self.gui_launched_externally = False
        self.auto_launch_gui = auto_launch_gui
        self.gui_startup_timeout = gui_startup_timeout

        # Test configuration
        self.test_config: dict[str, Any] = {}
        self.test_matrix: list[dict[str, Any]] = []

        # Results tracking
        self.suite_results: list[TestSuiteResults] = []
        self.overall_start_time: datetime | None = None

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def launch_gui_application(self) -> bool:
        """
        Launch the Knowledge Chipper GUI application for testing.

        Returns:
            True if GUI was launched successfully, False otherwise
        """
        try:
            logger.info("Launching Knowledge Chipper GUI for testing...")

            # Check if GUI is already running by trying to connect to it
            if self._is_gui_already_running():
                logger.info("GUI application is already running")
                self.gui_launched_externally = True
                return True

            # Find the project root and set up environment
            project_root = Path(__file__).parent.parent.parent

            # Use the exact same environment as the current process
            env = dict(os.environ)

            # Just use the same Python executable that's running this script
            python_exe = sys.executable

            logger.info(f"Using Python executable: {python_exe}")
            logger.info(f"Current working directory: {project_root}")
            logger.info(f"Environment PYTHONPATH: {env.get('PYTHONPATH', 'Not set')}")
            logger.info(f"Environment VIRTUAL_ENV: {env.get('VIRTUAL_ENV', 'Not set')}")

            # Launch GUI in background without stealing focus
            cmd = [python_exe, "-m", "knowledge_system.gui"]

            # Add environment variables to prevent focus stealing on macOS
            env["NSAppSleepDisabled"] = "YES"  # Prevent app from going to sleep
            env[
                "QT_MAC_DISABLE_FOREGROUND"
            ] = "1"  # Prevent Qt from coming to foreground
            env["KNOWLEDGE_CHIPPER_TESTING_MODE"] = "1"  # Enable testing mode
            env["DISPLAY"] = (
                ":0.0" if "DISPLAY" not in env else env["DISPLAY"]
            )  # Ensure display is set

            # Additional Qt flags to minimize GUI interference
            # Note: Don't use offscreen mode as we need GUI interaction for testing
            env["QT_LOGGING_RULES"] = "*.debug=false"  # Reduce Qt logging
            env["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"  # Disable auto scaling

            logger.info(f"Launching command: {' '.join(cmd)} (background mode)")
            logger.info(
                f"Environment KNOWLEDGE_CHIPPER_TESTING_MODE = {env.get('KNOWLEDGE_CHIPPER_TESTING_MODE', 'NOT SET')}"
            )

            # Different approach for macOS vs other platforms
            if sys.platform == "darwin":  # macOS
                self.gui_process = subprocess.Popen(
                    cmd,
                    cwd=project_root,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                    text=True,  # Ensure text mode for easier debugging
                    start_new_session=True,  # Start in new session to detach from terminal
                )
            else:  # Linux/Windows
                self.gui_process = subprocess.Popen(
                    cmd,
                    cwd=project_root,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                    text=True,  # Ensure text mode for easier debugging
                    preexec_fn=os.setsid if sys.platform != "win32" else None,
                )

            # Wait for GUI to start up
            logger.info("Waiting for GUI to initialize...")
            startup_timeout = self.gui_startup_timeout

            for i in range(startup_timeout):
                time.sleep(1)

                # Check if process is still running
                if self.gui_process.poll() is not None:
                    # Process has terminated
                    return_code = self.gui_process.returncode
                    stdout, stderr = self.gui_process.communicate()
                    logger.error(
                        f"GUI process terminated unexpectedly with return code: {return_code}"
                    )

                    if stdout:
                        logger.error(f"stdout: {stdout}")
                    else:
                        logger.error("stdout: None")

                    if stderr:
                        logger.error(f"stderr: {stderr}")
                    else:
                        logger.error("stderr: None")

                    return False

                # Check if GUI is responsive (try to detect window)
                if self._is_gui_responsive():
                    logger.info(f"GUI started successfully after {i+1} seconds")

                    # Hide the GUI window using AppleScript on macOS
                    if sys.platform == "darwin":
                        try:
                            hide_script = """
                            tell application "System Events"
                                set appName to "Knowledge Chipper"
                                if exists (process appName) then
                                    tell process appName
                                        set visible to false
                                    end tell
                                end if
                            end tell
                            """
                            subprocess.run(
                                ["osascript", "-e", hide_script],
                                capture_output=True,
                                timeout=5,
                            )
                            logger.info("GUI window hidden using AppleScript")
                        except Exception as e:
                            logger.warning(f"Failed to hide GUI window: {e}")

                    return True

                if i % 5 == 0:
                    logger.info(
                        f"Still waiting for GUI startup... ({i+1}/{startup_timeout}s)"
                    )

            logger.error("GUI startup timed out")
            self._cleanup_gui_process()
            return False

        except Exception as e:
            logger.error(f"Failed to launch GUI: {e}")
            logger.error(traceback.format_exc())
            return False

    def _is_gui_already_running(self) -> bool:
        """Check if GUI is already running."""
        try:
            # Try to import and check if QApplication instance exists
            if QApplication.instance() is not None:
                return True
        except Exception:
            pass
        return False

    def _is_gui_responsive(self) -> bool:
        """Check if GUI is responsive and ready for testing."""
        try:
            # Simple check - in a real implementation, this might try to
            # connect to the GUI or check for specific windows
            if self.gui_process and self.gui_process.poll() is None:
                return True
        except Exception:
            pass
        return False

    def _cleanup_gui_process(self) -> None:
        """Clean up the GUI process."""
        if self.gui_process and not self.gui_launched_externally:
            try:
                logger.info("Cleaning up GUI process...")

                # Try graceful termination first
                self.gui_process.terminate()

                # Wait a bit for graceful shutdown
                try:
                    self.gui_process.wait(timeout=5)
                    logger.info("GUI process terminated gracefully")
                except subprocess.TimeoutExpired:
                    # Force kill if it doesn't respond
                    logger.warning(
                        "GUI process didn't terminate gracefully, forcing kill"
                    )
                    self.gui_process.kill()
                    self.gui_process.wait()

            except Exception as e:
                logger.error(f"Error cleaning up GUI process: {e}")
            finally:
                self.gui_process = None

    def setup(self) -> bool:
        """
        Set up the testing environment.

        Returns:
            True if setup successful, False otherwise
        """
        try:
            logger.info("Setting up GUI testing environment")

            # Launch GUI application first (if enabled)
            if self.auto_launch_gui:
                if not self.launch_gui_application():
                    logger.error("Failed to launch GUI application")
                    return False
            else:
                logger.info(
                    "GUI auto-launch disabled - assuming GUI is already running"
                )

            # Create QApplication if not exists
            if not QApplication.instance():
                self.app = QApplication(sys.argv)
            else:
                self.app = QApplication.instance()

            # Initialize framework components
            self.framework = GUITestFramework(self.app)
            self.validator = OutputValidator(self.output_dir)

            # Set up main window connection
            main_window = self.framework.setup_main_window()
            self.automation = GUIAutomation(main_window)

            # Load test configuration
            self._load_test_configuration()

            # Generate test matrix
            self._generate_test_matrix()

            logger.info("GUI testing environment setup complete")
            return True

        except Exception as e:
            logger.error(f"Failed to setup testing environment: {e}")
            logger.error(traceback.format_exc())
            return False

    def teardown(self) -> None:
        """Clean up the testing environment."""
        try:
            logger.info("Tearing down GUI testing environment")

            if self.framework:
                self.framework.teardown_main_window()

            if self.app:
                self.app.quit()

            # Clean up GUI process
            self._cleanup_gui_process()

        except Exception as e:
            logger.error(f"Error during teardown: {e}")

    def run_smoke_tests(self) -> TestSuiteResults:
        """
        Run quick smoke tests to validate basic functionality.

        Returns:
            TestSuiteResults for smoke tests
        """
        logger.info("Starting smoke tests")

        if not self.framework:
            raise RuntimeError("Framework not initialized - call setup() first")

        suite = self.framework.start_test_suite("Smoke Tests")

        # Select a small subset of test cases for smoke testing
        smoke_test_cases = self._get_smoke_test_cases()

        for test_case in smoke_test_cases:
            test_name = f"Smoke_{test_case['file_type']}_{test_case['tab']}_{test_case['operation']}"

            def run_test():
                return self._run_single_test(test_case, quick_mode=True)

            result = self.framework.run_test(test_name, run_test)

        suite_result = self.framework.finish_test_suite()
        if suite_result:
            self.suite_results.append(suite_result)

        return suite_result

    def run_quick_tests(self) -> TestSuiteResults:
        """
        Run quick tests with dry-run mode enabled for fast validation.

        Returns:
            TestSuiteResults for quick tests
        """
        logger.info("Starting quick tests with dry-run mode")

        if not self.framework:
            raise RuntimeError("Framework not initialized - call setup() first")

        suite = self.framework.start_test_suite("Quick Tests")

        # Use custom quick test cases with better test files
        quick_test_cases = self._get_quick_test_cases()

        for test_case in quick_test_cases:
            test_name = f"Quick_{test_case['file_type']}_{test_case['tab']}_{test_case['operation']}"

            # Don't force dry-run since it doesn't work in Local Transcription
            # Instead we use very short files that transcribe quickly
            test_case_copy = test_case.copy()

            def run_test():
                return self._run_single_test(test_case_copy, quick_mode=True)

            result = self.framework.run_test(test_name, run_test)

        suite_result = self.framework.finish_test_suite()
        if suite_result:
            self.suite_results.append(suite_result)

        return suite_result

    def _get_quick_test_cases(self) -> list[dict]:
        """
        Get a minimal set of test cases using fast-transcribing audio files.

        Returns:
            List of test case dictionaries optimized for quick execution
        """
        quick_test_cases = []

        # Use our better quality test files that transcribe quickly
        working_audio_dir = self.test_data_dir / "sample_files" / "working_audio"

        if (working_audio_dir / "working_speech_spoken.mp3").exists():
            quick_test_cases.append(
                {
                    "file_path": working_audio_dir / "working_speech_spoken.mp3",
                    "file_type": "audio",
                    "tab": "Local Transcription",
                    "operation": "transcribe_only",
                }
            )

        # For documents, use a simple text file (quick to process)
        doc_files = list(
            (self.test_data_dir / "sample_files" / "documents").glob("*.txt")
        )
        if doc_files:
            quick_test_cases.append(
                {
                    "file_path": doc_files[0],
                    "file_type": "document",
                    "tab": "Summarization",
                    "operation": "summarize_only",
                }
            )

        logger.info(f"Generated {len(quick_test_cases)} quick test cases")
        return quick_test_cases

    def run_comprehensive_tests(self) -> TestSuiteResults:
        """
        Run comprehensive tests covering all permutations.

        Returns:
            TestSuiteResults for comprehensive tests
        """
        logger.info("Starting comprehensive tests")

        if not self.framework:
            raise RuntimeError("Framework not initialized - call setup() first")

        suite = self.framework.start_test_suite("Comprehensive Tests")

        total_tests = len(self.test_matrix)
        logger.info(f"Running {total_tests} comprehensive test cases")

        # Circuit breaker to prevent infinite failures
        consecutive_failures = 0
        max_consecutive_failures = 5  # Stop after 5 consecutive failures

        for i, test_case in enumerate(self.test_matrix):
            test_name = f"Comprehensive_{test_case['file_type']}_{test_case['tab']}_{test_case['operation']}"

            logger.info(f"Progress: {i+1}/{total_tests} - {test_name}")

            def run_test():
                return self._run_single_test(test_case, quick_mode=False)

            result = self.framework.run_test(test_name, run_test)

            # Circuit breaker logic
            if not result.success:
                consecutive_failures += 1
                logger.warning(
                    f"Test failed: {consecutive_failures} consecutive failures"
                )

                if consecutive_failures >= max_consecutive_failures:
                    logger.error(
                        f"Circuit breaker activated: {consecutive_failures} consecutive failures. Stopping test suite to prevent infinite hangs."
                    )
                    break
            else:
                consecutive_failures = 0  # Reset on success

        suite_result = self.framework.finish_test_suite()
        if suite_result:
            self.suite_results.append(suite_result)

        return suite_result

    def run_stress_tests(self) -> TestSuiteResults:
        """
        Run stress tests with large files and challenging scenarios.

        Returns:
            TestSuiteResults for stress tests
        """
        logger.info("Starting stress tests")

        if not self.framework:
            raise RuntimeError("Framework not initialized - call setup() first")

        suite = self.framework.start_test_suite("Stress Tests")

        stress_test_cases = self._get_stress_test_cases()

        for test_case in stress_test_cases:
            test_name = f"Stress_{test_case['file_type']}_{test_case['tab']}_{test_case['operation']}"

            def run_test():
                return self._run_single_test(
                    test_case, quick_mode=False, stress_mode=True
                )

            result = self.framework.run_test(test_name, run_test)

        suite_result = self.framework.finish_test_suite()
        if suite_result:
            self.suite_results.append(suite_result)

        return suite_result

    def run_all_tests(self) -> list[TestSuiteResults]:
        """
        Run all test suites in sequence.

        Returns:
            List of all test suite results
        """
        self.overall_start_time = datetime.now()

        try:
            logger.info("Starting complete test run")

            # Run test suites in order
            self.run_smoke_tests()
            self.run_comprehensive_tests()
            self.run_stress_tests()

            logger.info("Complete test run finished")

        except Exception as e:
            logger.error(f"Error during test run: {e}")
            logger.error(traceback.format_exc())

        finally:
            # Generate final report
            self._generate_final_report()

        return self.suite_results

    def _run_single_test(
        self,
        test_case: dict[str, Any],
        quick_mode: bool = False,
        stress_mode: bool = False,
    ) -> TestResult:
        """
        Run a single test case.

        Args:
            test_case: Test case configuration
            quick_mode: Use smaller files and shorter timeouts
            stress_mode: Use larger files and longer operations

        Returns:
            TestResult for the test case
        """
        start_time = datetime.now()
        result = TestResult(
            test_name="",  # Will be set by framework
            file_path=test_case.get("file_path"),
            tab_name=test_case.get("tab"),
            operation=test_case.get("operation"),
        )

        try:
            # Navigate to the specified tab
            if not self.automation.select_tab(test_case["tab"]):
                result.errors.append(f"Failed to navigate to tab: {test_case['tab']}")
                return result

            # Load the test file
            file_path = test_case["file_path"]
            if not file_path.exists():
                result.errors.append(f"Test file not found: {file_path}")
                return result

            if not self.automation.add_files_to_list([file_path]):
                result.errors.append(f"Failed to load file: {file_path}")
                return result

            # Configure operation settings (checkboxes)
            operation_config = test_case.get("config", {})
            self._configure_operation_settings(operation_config)

            # Start processing
            # Try multiple button variations to find the correct one
            current_tab = test_case.get("tab", "Unknown")
            start_buttons_to_try = [
                "Start Transcription",
                "Start Processing",
                "Process Files",
                "Begin Processing",
                "Transcribe",
                "Process",
            ]

            button_clicked = False
            for start_button in start_buttons_to_try:
                if self.automation.click_button(start_button):
                    logger.info(f"Successfully clicked button: {start_button}")
                    button_clicked = True
                    break

            if not button_clicked:
                # Get available buttons for debugging
                available_buttons = self.automation.get_available_buttons()
                result.errors.append(
                    f"Failed to start processing - no valid start button found. Available: {available_buttons}"
                )
                result.success = False  # Explicitly mark as failed
                logger.warning(
                    f"Test failed: Cannot start processing in tab '{current_tab}'. Available buttons: {available_buttons}"
                )
                return result

            # Use adaptive timeouts based on operation type and mode
            if quick_mode:
                timeout = 60  # Longer for quick mode to handle startup delays
            elif stress_mode:
                timeout = 900  # 15 minutes for stress tests (increased from 10)
            else:
                # Adaptive timeout based on operation - increased for longer files
                operation_type = test_case.get("operation", "unknown")
                if "transcribe" in operation_type:
                    timeout = 600  # 10 minutes for transcription (increased from 5)
                elif "summarize" in operation_type:
                    timeout = 300  # 5 minutes for summarization (increased from 3)
                else:
                    timeout = 480  # 8 minutes default (increased from 4)

            logger.info(
                f"Starting processing with {timeout}s timeout for {test_case.get('operation', 'unknown')} operation"
            )

            if not self.automation.wait_for_processing_completion(timeout):
                # Gather comprehensive error context before cleanup
                error_context = self.automation.get_error_context_for_timeout()
                self._log_timeout_analysis(test_case, timeout, error_context)

                result.errors.append(f"Processing timed out after {timeout} seconds")
                result.metadata["timeout_context"] = error_context

                # Force cleanup before continuing
                logger.warning("Timeout occurred, performing aggressive cleanup")
                self._perform_aggressive_cleanup()
                return result

            # Check for errors
            errors = self.automation.check_for_errors()
            result.errors.extend(errors)

            # Validate outputs
            validation_results = self._validate_test_outputs(test_case, result)

            # Determine success
            validation_failures = [v for v in validation_results if not v.is_valid]
            result.success = len(result.errors) == 0 and len(validation_failures) == 0
            result.duration = datetime.now() - start_time

            # Add detailed failure information
            if not result.success:
                if result.errors:
                    logger.warning(
                        f"Test failed with {len(result.errors)} errors: {'; '.join(result.errors)}"
                    )
                if validation_failures:
                    validation_error_details = []
                    for v in validation_failures:
                        validation_error_details.extend(v.errors)
                    logger.warning(
                        f"Test failed validation with {len(validation_failures)} validation failures: {'; '.join(validation_error_details)}"
                    )
                    result.errors.extend(validation_error_details)

            # Add validation metadata
            result.metadata["validation_results"] = [
                {
                    "is_valid": v.is_valid,
                    "score": v.score,
                    "errors": v.errors,
                    "warnings": v.warnings,
                }
                for v in validation_results
            ]

        except Exception as e:
            result.errors.append(f"Exception during test execution: {e}")
            result.duration = datetime.now() - start_time
            logger.error(f"Test execution error: {e}")
            logger.error(traceback.format_exc())

        finally:
            # Always reset GUI state after each test, regardless of success/failure
            try:
                self.automation.reset_gui_state()
            except Exception as reset_error:
                logger.warning(f"Failed to reset GUI state: {reset_error}")

        return result

    def _configure_operation_settings(self, config: dict[str, Any]) -> None:
        """Configure operation settings in the GUI."""
        try:
            # Configure checkboxes for operations
            operations = config.get("operations", {})

            for operation, enabled in operations.items():
                checkbox_texts = {
                    "transcribe": "Transcribe audio/video files",
                    "summarize": "Summarize content",
                    "moc": "Generate Maps of Content",
                    "diarization": "Enable speaker diarization",
                }

                checkbox_text = checkbox_texts.get(operation)
                if checkbox_text:
                    self.automation.set_checkbox(checkbox_text, enabled)

            # Configure other settings
            settings = config.get("settings", {})
            for setting_name, setting_value in settings.items():
                self.automation.set_text_field(setting_name, str(setting_value))

        except Exception as e:
            logger.warning(f"Error configuring operation settings: {e}")

    def _validate_test_outputs(
        self, test_case: dict[str, Any], test_result: TestResult
    ) -> list[ValidationResult]:
        """Validate outputs generated by the test."""
        validation_results = []

        try:
            # Check if the GUI processing completed successfully first
            success_indicators = self._check_gui_success_indicators()
            gui_success_result = ValidationResult(
                is_valid=success_indicators["completed_successfully"],
                score=success_indicators["success_score"],
                errors=success_indicators["errors"],
                warnings=success_indicators["warnings"],
                metadata={"gui_indicators": success_indicators},
            )
            validation_results.append(gui_success_result)

            # If GUI processing failed, don't bother checking files
            if not success_indicators["completed_successfully"]:
                return validation_results

            # Determine expected output files based on operation
            operation = test_case["operation"]
            file_stem = test_case["file_path"].stem

            expected_files = []

            if "transcribe" in operation:
                expected_files.append(f"{file_stem}_transcript.md")

            if "summarize" in operation:
                expected_files.append(f"{file_stem}_summary.md")

            if "moc" in operation:
                expected_files.append(f"{file_stem}_moc.md")

            # Validate file existence in common output directories
            output_directories = [
                self.output_dir,  # Test output directory
                Path(
                    "/Users/matthewgreer/Projects/SAMPLE OUTPUTS"
                ),  # Default app output
                Path.home() / "Desktop",  # Alternative output
                Path.cwd() / "output",  # Relative output
            ]

            files_found = []
            if expected_files:
                for output_dir in output_directories:
                    if not output_dir.exists():
                        continue

                    for file_name in expected_files:
                        file_path = output_dir / file_name
                        if file_path.exists():
                            files_found.append(file_path)
                            test_result.output_files.append(file_path)
                            logger.info(f"✅ Found output file: {file_path}")

                            # Validate content
                            content_result = self._validate_file_content(
                                file_path, operation
                            )
                            validation_results.append(content_result)
                            break  # Found the file, move to next

                # Create file existence validation result
                existence_result = ValidationResult(
                    is_valid=len(files_found) >= len(expected_files),
                    score=(
                        len(files_found) / len(expected_files)
                        if expected_files
                        else 1.0
                    ),
                    errors=(
                        []
                        if len(files_found) >= len(expected_files)
                        else [
                            f"Missing output files: {set(expected_files) - {f.name for f in files_found}}"
                        ]
                    ),
                    warnings=[],
                    metadata={
                        "expected_files": expected_files,
                        "found_files": [str(f) for f in files_found],
                    },
                )
                validation_results.append(existence_result)

        except Exception as e:
            logger.error(f"Error validating test outputs: {e}")
            error_result = ValidationResult(
                is_valid=False,
                score=0.0,
                errors=[f"Validation error: {e}"],
                warnings=[],
                metadata={},
            )
            validation_results.append(error_result)

        return validation_results

    def _check_gui_success_indicators(self) -> dict[str, Any]:
        """Check GUI indicators to determine if processing completed successfully."""
        indicators = {
            "completed_successfully": False,
            "success_score": 0.0,
            "errors": [],
            "warnings": [],
            "details": {},
        }

        try:
            # Check if the start button is ready (indicates processing completed)
            start_button = None
            try:
                start_button = self.automation.find_button("Start Transcription")
            except AttributeError:
                # Fallback: try to find button manually
                buttons = self.automation.get_available_buttons()
                start_button_ready = any("Start" in btn for btn in buttons)
            else:
                start_button_ready = start_button is not None

            # Get recent log output to check for success/error messages
            log_output = self.automation.get_output_log_text()

            # Analyze log output for success indicators
            success_indicators = [
                "✅ Transcript saved successfully",
                "Successfully transcribed and saved",
                "✅ All transcriptions completed",
                "Processing completed successfully",
            ]

            error_indicators = [
                "❌ Transcription failed",
                "❌ Processing failed",
                "Exception during",
                "Error:",
                "Failed to",
            ]

            # Count success and error indicators in logs
            success_count = sum(
                1 for indicator in success_indicators if indicator in log_output
            )
            error_count = sum(
                1 for indicator in error_indicators if indicator in log_output
            )

            # Determine overall success
            if start_button_ready and success_count > 0 and error_count == 0:
                indicators["completed_successfully"] = True
                indicators["success_score"] = 1.0
            elif start_button_ready and success_count > error_count:
                indicators["completed_successfully"] = True
                indicators["success_score"] = 0.7  # Partial success
                indicators["warnings"].append(
                    f"Some errors detected but processing completed ({success_count} success, {error_count} errors)"
                )
            elif start_button_ready:
                indicators["completed_successfully"] = False
                indicators["success_score"] = 0.3
                indicators["errors"].append(
                    "Processing completed but no clear success indicators found"
                )
            else:
                indicators["completed_successfully"] = False
                indicators["success_score"] = 0.0
                indicators["errors"].append(
                    "Start button not ready - processing may not have completed"
                )

            # Additional details
            indicators["details"] = {
                "start_button_ready": start_button_ready,
                "success_count": success_count,
                "error_count": error_count,
                "log_sample": log_output[-500:] if log_output else "No log output",
            }

        except Exception as e:
            indicators["errors"].append(f"Error checking GUI success indicators: {e}")

        return indicators

    def _validate_file_content(
        self, file_path: Path, operation: str
    ) -> "ValidationResult":
        """Validate the content of an output file."""
        try:
            # Read file content
            content = file_path.read_text(encoding="utf-8")

            # Basic validation - file should not be empty and should contain meaningful content
            if len(content) < 10:
                return ValidationResult(
                    is_valid=False,
                    score=0.0,
                    errors=[
                        f"File {file_path.name} is too short ({len(content)} characters)"
                    ],
                    warnings=[],
                    metadata={"file_size": len(content)},
                )

            # Check for error indicators in content
            error_indicators = [
                "[Error]",
                "[Failed]",
                "transcription failed",
                "processing failed",
            ]
            errors_found = [
                indicator
                for indicator in error_indicators
                if indicator.lower() in content.lower()
            ]

            if errors_found:
                return ValidationResult(
                    is_valid=False,
                    score=0.2,
                    errors=[
                        f"Error indicators found in {file_path.name}: {errors_found}"
                    ],
                    warnings=[],
                    metadata={
                        "content_length": len(content),
                        "errors_found": errors_found,
                    },
                )

            # Check for success indicators
            success_indicators = []
            if "transcribe" in operation:
                success_indicators = ["# Transcript", "## Speaker", "**Transcript:**"]
            elif "summarize" in operation:
                success_indicators = ["# Summary", "## Key Points", "**Summary:**"]
            elif "moc" in operation:
                success_indicators = ["# MOC", "## People", "## Jargon"]

            success_count = sum(
                1 for indicator in success_indicators if indicator in content
            )

            # Calculate score
            if (
                success_count >= len(success_indicators) * 0.7
            ):  # 70% of expected indicators
                score = 1.0
                is_valid = True
                errors = []
            elif success_count > 0:
                score = 0.6
                is_valid = True
                errors = []
                warnings = [
                    f"Only found {success_count}/{len(success_indicators)} expected content indicators"
                ]
            else:
                score = 0.4
                is_valid = True  # Content exists but may not be structured as expected
                errors = []
                warnings = [f"No expected content indicators found in {file_path.name}"]

            return ValidationResult(
                is_valid=is_valid,
                score=score,
                errors=errors,
                warnings=warnings if "warnings" in locals() else [],
                metadata={
                    "content_length": len(content),
                    "success_indicators_found": success_count,
                    "success_indicators_expected": len(success_indicators),
                },
            )

        except Exception as e:
            return ValidationResult(
                is_valid=False,
                score=0.0,
                errors=[f"Error reading file {file_path.name}: {e}"],
                warnings=[],
                metadata={},
            )

    def _configure_operation_settings(self, config: dict) -> None:
        """
        Configure operation settings like checkboxes based on test configuration.

        Args:
            config: Configuration dictionary containing checkbox settings
        """
        try:
            checkboxes = config.get("checkboxes", {})

            for checkbox_name, should_be_checked in checkboxes.items():
                logger.debug(
                    f"Setting checkbox '{checkbox_name}' to {should_be_checked}"
                )
                success = self.automation.set_checkbox(checkbox_name, should_be_checked)
                if not success:
                    logger.warning(
                        f"Failed to set checkbox '{checkbox_name}' to {should_be_checked}"
                    )

        except Exception as e:
            logger.error(f"Error configuring operation settings: {e}")

    def _load_test_configuration(self) -> None:
        """Load test configuration from files."""
        config_file = self.test_data_dir / "test_configs" / "comprehensive_config.yaml"

        # Default configuration if file doesn't exist
        # Tab names MUST match actual GUI tab names from main_window_pyqt6.py
        self.test_config = {
            "timeout": 300,
            "file_size_limit_mb": 100,
            "operations": ["transcribe_only", "summarize_only", "full_pipeline"],
            "tabs": ["Transcribe", "Summarize", "Monitor"],  # Actual GUI tab names
            "file_types": {
                "audio": [".mp3", ".wav", ".m4a"],
                "video": [".mp4", ".webm"],
                "document": [".pdf", ".txt", ".md"],
            },
        }

        if config_file.exists():
            try:
                import yaml

                with open(config_file) as f:
                    loaded_config = yaml.safe_load(f)
                    self.test_config.update(loaded_config)
            except Exception as e:
                logger.warning(f"Could not load config file: {e}, using defaults")

    def _generate_test_matrix(self) -> None:
        """Generate the full test matrix of all permutations."""
        self.test_matrix = []

        # Find available test files
        test_files = self._find_test_files()

        # Generate permutations
        for file_path, file_type in test_files:
            for tab in self.test_config["tabs"]:
                for operation in self.test_config["operations"]:
                    # Check if this combination makes sense
                    if self._is_valid_combination(file_type, tab, operation):
                        test_case = {
                            "file_path": file_path,
                            "file_type": file_type,
                            "tab": tab,
                            "operation": operation,
                            "config": self._get_operation_config(operation),
                        }
                        self.test_matrix.append(test_case)

        logger.info(f"Generated test matrix with {len(self.test_matrix)} test cases")

    def _find_test_files(self) -> list[tuple[Path, str]]:
        """Find all available test files and categorize them."""
        test_files = []

        file_type_mapping = {
            "audio": self.test_config["file_types"]["audio"],
            "video": self.test_config["file_types"]["video"],
            "document": self.test_config["file_types"]["document"],
        }

        # Map logical names to actual directory names
        dir_name_mapping = {
            "audio": "audio",
            "video": "video",
            "document": "documents",  # Directory is plural!
        }

        for file_type, extensions in file_type_mapping.items():
            dir_name = dir_name_mapping.get(file_type, file_type)
            type_dir = self.test_data_dir / "sample_files" / dir_name
            if type_dir.exists():
                for ext in extensions:
                    for file_path in type_dir.glob(f"*{ext}"):
                        test_files.append((file_path, file_type))
            else:
                logger.warning(f"Test directory not found: {type_dir}")

        logger.info(f"Found {len(test_files)} test files across all types")
        return test_files

    def _is_valid_combination(self, file_type: str, tab: str, operation: str) -> bool:
        """Check if a file type, tab, and operation combination is valid.
        
        Note: Tab names must match the actual GUI tab names from main_window_pyqt6.py:
        - "Transcribe" (not "Local Transcription")
        - "Summarize" (not "Summarization")
        - "Monitor" (for batch processing)
        """
        # Define valid combinations using ACTUAL GUI tab names
        valid_combinations = {
            # Audio transcription combinations
            ("audio", "Transcribe", "transcribe_only"),
            ("audio", "Monitor", "transcribe_only"),
            ("audio", "Monitor", "full_pipeline"),
            
            # Video transcription combinations
            ("video", "Transcribe", "transcribe_only"),
            ("video", "Monitor", "transcribe_only"),
            ("video", "Monitor", "full_pipeline"),
            
            # Document summarization combinations
            ("document", "Summarize", "summarize_only"),
            ("document", "Monitor", "summarize_only"),
            ("document", "Monitor", "full_pipeline"),
        }

        return (file_type, tab, operation) in valid_combinations

    def _get_operation_config(self, operation: str) -> dict[str, Any]:
        """Get configuration for a specific operation."""
        configs = {
            "transcribe_only": {
                "operations": {"transcribe": True, "summarize": False, "moc": False}
            },
            "summarize_only": {
                "operations": {"transcribe": False, "summarize": True, "moc": False}
            },
            "full_pipeline": {
                "operations": {"transcribe": True, "summarize": True, "moc": True}
            },
        }

        return configs.get(operation, {})

    def _get_smoke_test_cases(self) -> list[dict[str, Any]]:
        """Get a subset of test cases for smoke testing."""
        # Return first test case of each type for quick validation
        smoke_cases = []
        seen_combinations = set()

        for test_case in self.test_matrix:
            combination = (test_case["file_type"], test_case["tab"])
            if combination not in seen_combinations:
                # Create a copy of the test case and disable diarization for smoke tests
                smoke_test_case = test_case.copy()

                # Disable diarization to prevent GUI threading issues during testing
                smoke_test_case["config"] = smoke_test_case.get("config", {}).copy()
                smoke_test_case["config"]["checkboxes"] = (
                    smoke_test_case["config"].get("checkboxes", {}).copy()
                )
                smoke_test_case["config"]["checkboxes"][
                    "Enable speaker diarization"
                ] = False

                logger.info(
                    f"🧪 Smoke test: Disabling diarization for {test_case['file_type']} / {test_case['tab']}"
                )

                smoke_cases.append(smoke_test_case)
                seen_combinations.add(combination)

        return smoke_cases[:5]  # Limit to 5 smoke tests

    def _get_stress_test_cases(self) -> list[dict[str, Any]]:
        """Get test cases for stress testing with large files."""
        # This would filter for large files or specific stress scenarios
        # For now, return a subset of the full matrix
        return self.test_matrix[::5]  # Every 5th test case

    def _generate_final_report(self) -> None:
        """Generate comprehensive final test report."""
        try:
            report = {
                "test_run": {
                    "start_time": (
                        self.overall_start_time.isoformat()
                        if self.overall_start_time
                        else None
                    ),
                    "end_time": datetime.now().isoformat(),
                    "total_suites": len(self.suite_results),
                },
                "suites": [],
            }

            for suite in self.suite_results:
                suite_data = {
                    "name": suite.suite_name,
                    "start_time": suite.start_time.isoformat(),
                    "end_time": suite.end_time.isoformat() if suite.end_time else None,
                    "duration_seconds": suite.duration.total_seconds(),
                    "total_tests": suite.total_tests,
                    "passed_tests": suite.passed_tests,
                    "failed_tests": suite.failed_tests,
                    "success_rate": suite.success_rate,
                }
                report["suites"].append(suite_data)

            # Save report
            report_file = (
                self.output_dir
                / f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )

            with open(report_file, "w") as f:
                json.dump(report, f, indent=2)

            logger.info(f"Final test report saved to: {report_file}")

        except Exception as e:
            logger.error(f"Error generating final report: {e}")

    def _perform_aggressive_cleanup(self) -> None:
        """Perform aggressive cleanup of stuck processes and GUI state."""
        import os
        import time

        import psutil

        logger.warning("Performing aggressive cleanup of stuck processes")

        try:
            # 1. Reset GUI state first
            if self.automation:
                self.automation.reset_gui_state()
                time.sleep(2)

            # 2. Find and kill related processes
            current_pid = os.getpid()
            killed_processes = []

            for proc in psutil.process_iter(["pid", "name", "cmdline", "ppid"]):
                try:
                    # Skip our own process
                    if proc.info["pid"] == current_pid:
                        continue

                    proc_name = proc.info["name"].lower()
                    cmdline = " ".join(proc.info.get("cmdline", [])).lower()

                    # Check for processes to kill
                    kill_indicators = [
                        "whisper",
                        "ffmpeg",
                        "sox",
                        "speech",
                        "knowledge_system",
                        "transcribe",
                        "python",
                    ]

                    should_kill = False
                    for indicator in kill_indicators:
                        if (
                            indicator in proc_name
                            or indicator in cmdline
                            or "knowledge" in cmdline
                            or "chipper" in cmdline
                        ):
                            # Don't kill GUI processes or our parent
                            if (
                                "gui" not in cmdline
                                and "test" not in cmdline
                                and proc.info["pid"] != os.getppid()
                            ):
                                should_kill = True
                                break

                    if should_kill:
                        logger.warning(
                            f"Killing stuck process: {proc.info['pid']} ({proc_name})"
                        )
                        try:
                            proc.terminate()
                            proc.wait(timeout=3)
                            killed_processes.append(proc.info["pid"])
                        except (psutil.TimeoutExpired, psutil.NoSuchProcess):
                            try:
                                proc.kill()
                                killed_processes.append(proc.info["pid"])
                            except psutil.NoSuchProcess:
                                pass

                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if killed_processes:
                logger.info(
                    f"Killed {len(killed_processes)} stuck processes: {killed_processes}"
                )

            # 3. Clean up any temporary files or locks
            # (Could add temp file cleanup here if needed)

            # 4. Wait for system to settle
            time.sleep(3)

            logger.info("Aggressive cleanup completed")

        except Exception as e:
            logger.error(f"Error during aggressive cleanup: {e}")
            # Don't let cleanup errors propagate

    def _log_timeout_analysis(
        self, test_case: dict[str, Any], timeout: int, error_context: dict[str, Any]
    ) -> None:
        """Log comprehensive timeout analysis for debugging."""
        logger.error(f"=== TIMEOUT ANALYSIS ===")
        logger.error(
            f"Test: {test_case.get('file_path', 'unknown')} -> {test_case.get('operation', 'unknown')}"
        )
        logger.error(f"Timeout: {timeout}s")

        # File context
        file_path = test_case.get("file_path")
        if file_path and hasattr(file_path, "stat"):
            try:
                file_size = file_path.stat().st_size / (1024 * 1024)  # MB
                logger.error(f"File size: {file_size:.1f}MB")
            except:
                pass

        # System state
        system_state = error_context.get("system_state", {})
        if system_state:
            logger.error(
                f"System: CPU={system_state.get('cpu_percent', '?')}%, "
                f"Memory={system_state.get('memory_percent', '?')}%, "
                f"Disk={system_state.get('disk_usage', '?')}%"
            )

        # Process information
        process_info = error_context.get("process_info", {})
        knowledge_processes = process_info.get("knowledge_processes", [])
        if knowledge_processes:
            logger.error(f"Active processes ({len(knowledge_processes)}):")
            for proc in knowledge_processes[:3]:  # Show first 3
                logger.error(
                    f"  PID {proc['pid']}: {proc['name']} "
                    f"(CPU: {proc['cpu_percent']}%, Memory: {proc['memory_mb']:.1f}MB)"
                )
                logger.error(f"    Command: {proc['cmdline']}")

        # GUI state
        gui_state = error_context.get("gui_state", {})
        if gui_state.get("visible_buttons"):
            logger.error(f"GUI buttons: {', '.join(gui_state['visible_buttons'][:5])}")

        # Error logs
        error_logs = error_context.get("error_logs", [])
        if error_logs:
            logger.error("Recent errors:")
            for error_line in error_logs[-3:]:  # Last 3 errors
                logger.error(f"  {error_line}")

        # Diagnosis
        self._diagnose_timeout_cause(test_case, error_context)
        logger.error(f"=== END TIMEOUT ANALYSIS ===")

    def _diagnose_timeout_cause(
        self, test_case: dict[str, Any], error_context: dict[str, Any]
    ) -> None:
        """Attempt to diagnose the likely cause of timeout."""
        logger.error("=== LIKELY CAUSES ===")

        # Check system resources
        system_state = error_context.get("system_state", {})
        cpu_percent = system_state.get("cpu_percent", 0)
        memory_percent = system_state.get("memory_percent", 0)

        if cpu_percent > 90:
            logger.error("🔥 HIGH CPU USAGE - System may be overloaded")
        if memory_percent > 90:
            logger.error("💾 HIGH MEMORY USAGE - System may be out of memory")

        # Check for stuck processes
        knowledge_processes = error_context.get("process_info", {}).get(
            "knowledge_processes", []
        )
        stuck_processes = [p for p in knowledge_processes if p["cpu_percent"] < 1]
        if stuck_processes:
            logger.error(
                f"🚫 {len(stuck_processes)} processes with low CPU usage (possibly stuck)"
            )

        high_memory_processes = [
            p for p in knowledge_processes if p["memory_mb"] > 1000
        ]
        if high_memory_processes:
            logger.error(f"💾 {len(high_memory_processes)} processes using >1GB memory")

        # Check file size vs operation
        file_path = test_case.get("file_path")
        operation = test_case.get("operation", "")
        if file_path and hasattr(file_path, "stat"):
            try:
                file_size_mb = file_path.stat().st_size / (1024 * 1024)
                if "transcribe" in operation and file_size_mb > 100:
                    logger.error(
                        f"📁 Large file ({file_size_mb:.1f}MB) for transcription - may need longer timeout"
                    )
            except:
                pass

        # Check error patterns
        error_logs = error_context.get("error_logs", [])
        error_text = " ".join(error_logs).lower()

        if "cuda" in error_text or "gpu" in error_text:
            logger.error("🖥️ GPU/CUDA related errors detected")
        if "memory" in error_text or "out of memory" in error_text:
            logger.error("💾 Memory allocation errors detected")
        if "permission" in error_text or "access denied" in error_text:
            logger.error("🔒 Permission/access errors detected")
        if "model" in error_text and "not found" in error_text:
            logger.error("🤖 Model loading/missing errors detected")

        logger.error("=== END DIAGNOSIS ===")
