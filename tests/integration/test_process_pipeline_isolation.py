"""
Integration tests for ProcessPipelineWorker crash isolation and recovery.

These tests verify that the process isolation system works correctly and
that the GUI remains responsive even when worker processes crash.
"""

import json
import os
import signal
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import psutil
import pytest
from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from knowledge_system.gui.tabs.process_tab import ProcessPipelineWorker
from knowledge_system.utils.ipc_communication import (
    IPCCommunicator,
    ProcessCommunicationManager,
)
from knowledge_system.utils.memory_monitor import MemoryMonitor
from knowledge_system.utils.tracking import ProgressTracker


class ProcessIsolationTestCase(unittest.TestCase):
    """Base test case for process isolation tests."""

    def setUp(self):
        """Set up test environment."""
        # Ensure QApplication exists
        if not QApplication.instance():
            self.app = QApplication([])
        else:
            self.app = QApplication.instance()

        # Create temporary directories
        self.temp_dir = Path(tempfile.mkdtemp())
        self.output_dir = self.temp_dir / "output"
        self.output_dir.mkdir(exist_ok=True)

        # Create test files
        self.test_files = []
        for i in range(3):
            test_file = self.temp_dir / f"test_audio_{i}.mp3"
            test_file.write_text(f"dummy audio content {i}")
            self.test_files.append(str(test_file))

        # Test configuration
        self.test_config = {
            "transcribe": True,
            "summarize": False,
            "create_moc": False,
            "device": "cpu",
            "transcription_model": "base",
        }

    def tearDown(self):
        """Clean up test environment."""
        # Clean up temporary files
        import shutil

        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def wait_for_condition(self, condition_func, timeout=10, check_interval=0.1):
        """Wait for a condition to be true with timeout."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if condition_func():
                return True
            time.sleep(check_interval)
            self.app.processEvents()  # Keep Qt responsive
        return False


class TestProcessIsolation(ProcessIsolationTestCase):
    """Test process isolation functionality."""

    def test_worker_process_creation(self):
        """Test that worker process is created correctly."""
        worker = ProcessPipelineWorker(self.test_files, self.test_config)
        worker.set_output_directory(self.output_dir)

        # Mock the actual process to avoid running real processing
        with patch.object(worker, "start") as mock_start:
            worker.start_processing()

            # Verify process start was called
            mock_start.assert_called_once()

            # Verify command construction
            cmd = worker._build_command()
            self.assertIn("batch_processor_main", " ".join(cmd))
            self.assertIn("--files", cmd)
            self.assertIn("--config", cmd)
            self.assertIn("--output-dir", cmd)

    def test_ipc_communication(self):
        """Test IPC message parsing and handling."""
        comm_manager = ProcessCommunicationManager()

        # Test message handlers
        progress_received = Mock()
        error_received = Mock()
        comm_manager.register_progress_callback(progress_received)
        comm_manager.register_error_callback(error_received)

        # Test progress message
        progress_msg = json.dumps(
            {
                "type": "PROGRESS",
                "current_file": 1,
                "total_files": 3,
                "message": "Processing file 1",
                "progress_percent": 50,
                "stage": "transcription",
            }
        )

        comm_manager.process_output_line(progress_msg)
        progress_received.assert_called_once_with(
            1, 3, "Processing file 1", 50, "transcription"
        )

        # Test error message
        error_msg = json.dumps({"type": "ERROR", "message": "Test error message"})

        comm_manager.process_output_line(error_msg)
        error_received.assert_called_once_with("Test error message")

    def test_memory_pressure_detection(self):
        """Test memory monitoring and pressure detection."""
        monitor = MemoryMonitor(memory_threshold=50.0)  # Low threshold for testing

        # Test normal operation
        is_pressure, message = monitor.check_memory_pressure()
        self.assertIsInstance(is_pressure, bool)
        self.assertIsInstance(message, str)

        # Test memory statistics
        stats = monitor.get_memory_stats()
        self.assertIn("system_memory_percent", stats)
        self.assertIn("process_memory_mb", stats)

        # Test adaptive batch size
        base_size = 10
        adaptive_size = monitor.get_adaptive_batch_size(base_size, 100.0)
        self.assertIsInstance(adaptive_size, int)
        self.assertGreater(adaptive_size, 0)

    def test_checkpoint_creation_and_loading(self):
        """Test checkpoint creation and loading functionality."""
        # Use the correct API - this is testing the old tracking.py ProgressTracker
        from knowledge_system.utils.tracking import ProgressTracker

        tracker = ProgressTracker(
            operation_name="test_operation",
            total_tasks=5,
            checkpoint_file=self.output_dir / "test_checkpoint.json",
        )

        # Test checkpoint creation
        test_result = {
            "file_path": str(self.test_files[0]),
            "success": True,
            "output_path": str(self.output_dir / "output.txt"),
        }

        # First add the task before completing it
        tracker.add_task(str(self.test_files[0]), str(self.test_files[0]), "test_task")
        tracker.complete_task(str(self.test_files[0]), test_result)

        # Verify checkpoint was created (check if checkpoint file exists)
        self.assertTrue(tracker.checkpoint_file.exists())

        # Test checkpoint loading by creating a new tracker
        new_tracker = ProgressTracker(
            operation_name="test_operation",
            total_tasks=5,
            checkpoint_file=tracker.checkpoint_file,
        )
        # The new tracker should have loaded the checkpoint automatically
        self.assertGreater(new_tracker.completed_count, 0)


class TestErrorHandling(ProcessIsolationTestCase):
    """Test error handling and recovery mechanisms."""

    def test_process_restart_mechanism(self):
        """Test automatic process restart on failure."""
        worker = ProcessPipelineWorker(self.test_files, self.test_config)
        worker.set_output_directory(self.output_dir)

        # Mock process failure
        with patch.object(worker, "start") as mock_start:
            # Simulate process failure
            worker._handle_process_finished(1, None)  # Exit code 1 = failure

            # Wait for restart timer
            self.wait_for_condition(lambda: worker.restart_attempts > 0, timeout=5)

            # Verify restart attempt was made
            self.assertGreater(worker.restart_attempts, 0)
            self.assertLessEqual(worker.restart_attempts, worker.max_restart_attempts)

    def test_memory_cleanup_procedures(self):
        """Test memory cleanup and garbage collection."""
        monitor = MemoryMonitor()

        # Register some mock objects for cleanup
        mock_cache = Mock()
        mock_cache.clear = Mock()
        monitor.register_model_cache(mock_cache)

        # Create temporary files for cleanup testing
        temp_file = self.temp_dir / "temp_test_file.tmp"
        temp_file.write_text("test content")
        monitor.register_temp_file(temp_file)

        # Test emergency cleanup
        monitor.emergency_cleanup()

        # Verify cache was cleared
        mock_cache.clear.assert_called_once()

        # Verify temp file was removed
        self.assertFalse(temp_file.exists())

    def test_graceful_shutdown(self):
        """Test graceful shutdown handling."""
        worker = ProcessPipelineWorker(self.test_files, self.test_config)
        worker.set_output_directory(self.output_dir)

        # Mock QProcess methods
        with patch.object(worker, "state") as mock_state, patch.object(
            worker, "terminate"
        ) as mock_terminate, patch.object(
            worker, "waitForFinished"
        ) as mock_wait, patch.object(
            worker, "kill"
        ) as mock_kill:
            # Simulate running process
            mock_state.return_value = worker.ProcessState.Running
            mock_wait.return_value = True  # Terminates gracefully

            worker.stop_processing()

            # Verify graceful termination was attempted
            mock_terminate.assert_called_once()
            mock_wait.assert_called()
            mock_kill.assert_not_called()


class TestCrashRecovery(ProcessIsolationTestCase):
    """Test crash recovery and checkpoint restoration."""

    def test_checkpoint_detection(self):
        """Test detection of existing checkpoint files."""
        from knowledge_system.gui.dialogs.crash_recovery_dialog import (
            CrashRecoveryDialog,
        )

        # Create a mock checkpoint file in current directory (one of the search locations)
        checkpoint_file = Path.cwd() / "kc_checkpoint_test.json"
        checkpoint_data = {
            "total_files": 5,
            "completed_files": ["file1.mp3", "file2.mp3"],
            "files": ["file1.mp3", "file2.mp3", "file3.mp3", "file4.mp3", "file5.mp3"],
            "config": self.test_config,
            "job_name": "Test Job",
        }

        try:
            with open(checkpoint_file, "w") as f:
                json.dump(checkpoint_data, f)

            # Test checkpoint detection
            self.assertTrue(CrashRecoveryDialog.check_for_checkpoints())
        finally:
            # Cleanup the test checkpoint file
            if checkpoint_file.exists():
                checkpoint_file.unlink()

    def test_checkpoint_analysis(self):
        """Test checkpoint file analysis."""
        from knowledge_system.gui.dialogs.crash_recovery_dialog import (
            CrashRecoveryDialog,
        )

        # Create test checkpoint
        checkpoint_file = self.temp_dir / "test_checkpoint.json"
        checkpoint_data = {
            "total_files": 3,
            "completed_files": ["file1.mp3"],
            "files": ["file1.mp3", "file2.mp3", "file3.mp3"],
            "config": self.test_config,
            "job_name": "Test Analysis Job",
        }

        with open(checkpoint_file, "w") as f:
            json.dump(checkpoint_data, f)

        # Create dialog and analyze
        dialog = CrashRecoveryDialog()
        job_info = dialog._analyze_checkpoint(checkpoint_file)

        self.assertIsNotNone(job_info)
        self.assertEqual(job_info["total_files"], 3)
        self.assertEqual(job_info["completed_files"], 1)
        self.assertAlmostEqual(job_info["progress_percent"], 33.33, places=1)
        self.assertEqual(job_info["job_name"], "Test Analysis Job")


class TestPerformanceImpact(ProcessIsolationTestCase):
    """Test performance impact of process isolation."""

    def test_startup_overhead(self):
        """Test startup time overhead of process isolation."""
        worker = ProcessPipelineWorker(self.test_files, self.test_config)
        worker.set_output_directory(self.output_dir)

        # Measure command building time
        start_time = time.time()
        cmd = worker._build_command()
        build_time = time.time() - start_time

        # Should be very fast (< 1 second)
        self.assertLess(build_time, 1.0)
        self.assertIsInstance(cmd, list)
        self.assertGreater(len(cmd), 5)  # Should have multiple arguments

    def test_memory_monitoring_overhead(self):
        """Test memory monitoring performance overhead."""
        monitor = MemoryMonitor()

        # Measure memory check time
        start_time = time.time()
        for _ in range(100):  # Run 100 checks
            monitor.check_memory_pressure()
        check_time = time.time() - start_time

        # Should be fast even for many checks (< 1 second for 100 checks)
        self.assertLess(check_time, 1.0)

    def test_ipc_message_throughput(self):
        """Test IPC message processing throughput."""
        comm_manager = ProcessCommunicationManager()

        # Register a mock callback
        callback = Mock()
        comm_manager.register_progress_callback(callback)

        # Generate test messages
        test_messages = []
        for i in range(1000):
            msg = json.dumps(
                {
                    "type": "PROGRESS",
                    "current_file": i % 10,
                    "total_files": 10,
                    "message": f"Processing {i}",
                    "stage": "test",
                }
            )
            test_messages.append(msg)

        # Measure processing time
        start_time = time.time()
        for msg in test_messages:
            comm_manager.process_output_line(msg)
        process_time = time.time() - start_time

        # Should process 1000 messages quickly (< 2 seconds)
        self.assertLess(process_time, 2.0)
        self.assertEqual(callback.call_count, 1000)


class TestIntegrationScenarios(ProcessIsolationTestCase):
    """Test real-world integration scenarios."""

    def test_simulated_memory_exhaustion(self):
        """Test behavior under simulated memory pressure."""
        # Create a memory monitor with very low thresholds
        monitor = MemoryMonitor(memory_threshold=1.0)  # 1% threshold

        # This should always trigger pressure
        is_pressure, message = monitor.check_memory_pressure()
        self.assertTrue(is_pressure)
        self.assertIn("High", message)

        # Test adaptive behavior under pressure
        batch_size = monitor.get_adaptive_batch_size(10, 100.0)
        self.assertLessEqual(batch_size, 10)  # Should reduce batch size

    def test_checkpoint_corruption_handling(self):
        """Test handling of corrupted checkpoint files."""
        from knowledge_system.gui.dialogs.crash_recovery_dialog import (
            CrashRecoveryDialog,
        )

        # Create corrupted checkpoint file
        checkpoint_file = self.temp_dir / "corrupted_checkpoint.json"
        checkpoint_file.write_text("{ invalid json content")

        # Should handle corruption gracefully
        dialog = CrashRecoveryDialog()
        job_info = dialog._analyze_checkpoint(checkpoint_file)
        self.assertIsNone(job_info)  # Should return None for corrupted file

    def test_concurrent_checkpoint_access(self):
        """Test concurrent access to checkpoint files."""
        from knowledge_system.utils.tracking import ProgressTracker

        tracker1 = ProgressTracker(
            operation_name="test_operation_1",
            total_tasks=5,
            checkpoint_file=self.output_dir / "test_checkpoint_1.json",
        )
        tracker2 = ProgressTracker(
            operation_name="test_operation_2",
            total_tasks=5,
            checkpoint_file=self.output_dir / "test_checkpoint_2.json",
        )

        # Both trackers should be able to work with same directory
        test_result = {"success": True, "output_path": "test.txt"}

        # Add tasks first
        tracker1.add_task("file1.mp3", "file1.mp3", "test_task")
        tracker2.add_task("file2.mp3", "file2.mp3", "test_task")

        tracker1.complete_task("file1.mp3", test_result)
        tracker2.complete_task("file2.mp3", test_result)

        # Both should have valid checkpoints (files exist)
        self.assertTrue(tracker1.checkpoint_file.exists())
        self.assertTrue(tracker2.checkpoint_file.exists())


def run_process_isolation_tests():
    """Run all process isolation tests."""
    # Create test suite
    suite = unittest.TestSuite()

    # Add test classes
    test_classes = [
        TestProcessIsolation,
        TestErrorHandling,
        TestCrashRecovery,
        TestPerformanceImpact,
        TestIntegrationScenarios,
    ]

    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    # Run tests when script is executed directly
    success = run_process_isolation_tests()
    exit(0 if success else 1)
