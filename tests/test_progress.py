"""
Tests for Progress Tracking Utilities

Tests the progress tracking, resume capabilities, and batch processing functionality.
"""

import tempfile
from pathlib import Path

import pytest

from knowledge_system.utils.progress import (
    ProgressDisplay,
    ProgressTracker,
    TaskInfo,
    TaskStatus,
)


class TestTaskStatus:
    """Test TaskStatus enum."""

    def test_task_status_values(self):
        """Test that TaskStatus has expected values."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.SKIPPED.value == "skipped"


class TestTaskInfo:
    """Test TaskInfo dataclass."""

    def test_task_info_creation(self):
        """Test creating a TaskInfo instance."""
        task = TaskInfo(
            id="test_task",
            input_path="/path/to/file.txt",
            task_type="summarize",
            status=TaskStatus.PENDING,
        )

        assert task.id == "test_task"
        assert task.input_path == "/path/to/file.txt"
        assert task.task_type == "summarize"
        assert task.status == TaskStatus.PENDING
        assert task.retry_count == 0
        assert task.max_retries == 3

    def test_task_info_with_optional_fields(self):
        """Test TaskInfo with optional fields."""
        from datetime import datetime

        start_time = datetime.now()
        end_time = datetime.now()

        task = TaskInfo(
            id="test_task",
            input_path="/path/to/file.txt",
            task_type="summarize",
            status=TaskStatus.COMPLETED,
            start_time=start_time,
            end_time=end_time,
            duration=10.0,
            error_message=None,
            result_data={"result": "success"},
            retry_count=1,
            max_retries=5,
        )

        assert task.duration == 10.0
        assert task.result_data == {"result": "success"}
        assert task.retry_count == 1
        assert task.max_retries == 5


class TestProgressTracker:
    """Test ProgressTracker class."""

    def test_progress_tracker_creation(self):
        """Test creating a ProgressTracker."""
        tracker = ProgressTracker("test_operation", 10)

        assert tracker.operation_name == "test_operation"
        assert tracker.total_tasks == 10
        assert tracker.completed_count == 0
        assert tracker.failed_count == 0
        assert tracker.skipped_count == 0
        assert len(tracker.tasks) == 0

    def test_add_task(self):
        """Test adding tasks to tracker."""
        tracker = ProgressTracker("test_operation", 5)

        tracker.add_task("task1", "/path/to/file1.txt", "summarize")
        tracker.add_task("task2", "/path/to/file2.txt", "transcribe")

        assert len(tracker.tasks) == 2
        assert "task1" in tracker.tasks
        assert "task2" in tracker.tasks
        assert tracker.tasks["task1"].status == TaskStatus.PENDING
        assert tracker.tasks["task2"].task_type == "transcribe"

    def test_start_task(self):
        """Test starting a task."""
        tracker = ProgressTracker("test_operation", 1)
        tracker.add_task("task1", "/path/to/file.txt", "summarize")

        tracker.start_task("task1")

        assert tracker.tasks["task1"].status == TaskStatus.RUNNING
        assert tracker.tasks["task1"].start_time is not None

    def test_complete_task(self):
        """Test completing a task."""
        tracker = ProgressTracker("test_operation", 1)
        tracker.add_task("task1", "/path/to/file.txt", "summarize")
        tracker.start_task("task1")

        tracker.complete_task("task1", {"result": "success"})

        assert tracker.tasks["task1"].status == TaskStatus.COMPLETED
        assert tracker.tasks["task1"].end_time is not None
        assert tracker.tasks["task1"].duration is not None
        assert tracker.tasks["task1"].result_data == {"result": "success"}
        assert tracker.completed_count == 1

    def test_fail_task(self):
        """Test failing a task."""
        tracker = ProgressTracker("test_operation", 1)
        tracker.add_task("task1", "/path/to/file.txt", "summarize")
        tracker.start_task("task1")

        tracker.fail_task("task1", "Test error")

        assert tracker.tasks["task1"].status == TaskStatus.FAILED
        assert tracker.tasks["task1"].error_message == "Test error"
        assert tracker.failed_count == 1

    def test_skip_task(self):
        """Test skipping a task."""
        tracker = ProgressTracker("test_operation", 1)
        tracker.add_task("task1", "/path/to/file.txt", "summarize")

        tracker.skip_task("task1", "Already completed")

        assert tracker.tasks["task1"].status == TaskStatus.SKIPPED
        assert tracker.tasks["task1"].error_message == "Already completed"
        assert tracker.skipped_count == 1

    def test_retry_task(self):
        """Test retrying a failed task."""
        tracker = ProgressTracker("test_operation", 1)
        tracker.add_task("task1", "/path/to/file.txt", "summarize")
        tracker.start_task("task1")
        tracker.fail_task("task1", "Test error")

        initial_failed_count = tracker.failed_count

        # Retry should succeed
        assert tracker.retry_task("task1") is True
        assert tracker.tasks["task1"].status == TaskStatus.PENDING
        assert tracker.tasks["task1"].retry_count == 1
        assert tracker.failed_count == initial_failed_count - 1

    def test_retry_task_max_retries(self):
        """Test retry fails when max retries reached."""
        tracker = ProgressTracker("test_operation", 1)
        tracker.add_task("task1", "/path/to/file.txt", "summarize")

        # Set retry count to max
        tracker.tasks["task1"].retry_count = 3

        # Retry should fail
        assert tracker.retry_task("task1") is False

    def test_get_pending_tasks(self):
        """Test getting pending tasks."""
        tracker = ProgressTracker("test_operation", 3)
        tracker.add_task("task1", "/path/to/file1.txt", "summarize")
        tracker.add_task("task2", "/path/to/file2.txt", "transcribe")
        tracker.add_task("task3", "/path/to/file3.txt", "moc")

        tracker.start_task("task1")
        tracker.complete_task("task2")

        pending_tasks = tracker.get_pending_tasks()
        assert len(pending_tasks) == 1
        assert pending_tasks[0].id == "task3"

    def test_get_failed_tasks(self):
        """Test getting failed tasks."""
        tracker = ProgressTracker("test_operation", 2)
        tracker.add_task("task1", "/path/to/file1.txt", "summarize")
        tracker.add_task("task2", "/path/to/file2.txt", "transcribe")

        tracker.start_task("task1")
        tracker.fail_task("task1", "Error 1")
        tracker.start_task("task2")
        tracker.fail_task("task2", "Error 2")

        failed_tasks = tracker.get_failed_tasks()
        assert len(failed_tasks) == 2
        assert failed_tasks[0].error_message == "Error 1"
        assert failed_tasks[1].error_message == "Error 2"

    def test_get_completed_tasks(self):
        """Test getting completed tasks."""
        tracker = ProgressTracker("test_operation", 2)
        tracker.add_task("task1", "/path/to/file1.txt", "summarize")
        tracker.add_task("task2", "/path/to/file2.txt", "transcribe")

        tracker.start_task("task1")
        tracker.complete_task("task1")
        tracker.start_task("task2")
        tracker.complete_task("task2")

        completed_tasks = tracker.get_completed_tasks()
        assert len(completed_tasks) == 2
        assert completed_tasks[0].status == TaskStatus.COMPLETED
        assert completed_tasks[1].status == TaskStatus.COMPLETED

    def test_get_progress_summary(self):
        """Test getting progress summary."""
        tracker = ProgressTracker("test_operation", 4)
        tracker.add_task("task1", "/path/to/file1.txt", "summarize")
        tracker.add_task("task2", "/path/to/file2.txt", "transcribe")
        tracker.add_task("task3", "/path/to/file3.txt", "moc")
        tracker.add_task("task4", "/path/to/file4.txt", "summarize")

        tracker.start_task("task1")
        tracker.complete_task("task1")
        tracker.start_task("task2")
        tracker.fail_task("task2", "Error")
        tracker.skip_task("task3", "Skipped")

        summary = tracker.get_progress_summary()

        assert summary["operation"] == "test_operation"
        assert summary["total_tasks"] == 4
        assert summary["completed"] == 1
        assert summary["failed"] == 1
        assert summary["skipped"] == 1
        assert summary["pending"] == 1
        assert summary["progress_percentage"] == 25.0
        assert "total_duration" in summary
        assert "start_time" in summary
        assert "checkpoint_file" in summary

    def test_save_and_load_checkpoint(self):
        """Test saving and loading checkpoint."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            checkpoint_file = Path(f.name)

        try:
            tracker = ProgressTracker("test_operation", 2, checkpoint_file)
            tracker.add_task("task1", "/path/to/file1.txt", "summarize")
            tracker.add_task("task2", "/path/to/file2.txt", "transcribe")

            tracker.start_task("task1")
            tracker.complete_task("task1")
            tracker.start_task("task2")
            tracker.fail_task("task2", "Error")

            # Create new tracker and load checkpoint
            new_tracker = ProgressTracker("new_operation", 0, checkpoint_file)

            assert new_tracker.operation_name == "test_operation"
            assert new_tracker.total_tasks == 2
            assert new_tracker.completed_count == 1
            assert new_tracker.failed_count == 1
            assert len(new_tracker.tasks) == 2
            assert new_tracker.tasks["task1"].status == TaskStatus.COMPLETED
            assert new_tracker.tasks["task2"].status == TaskStatus.FAILED

        finally:
            checkpoint_file.unlink(missing_ok=True)


class TestProgressDisplay:
    """Test ProgressDisplay class."""

    def test_progress_display_creation(self):
        """Test creating a ProgressDisplay."""
        tracker = ProgressTracker("test_operation", 5)
        display = ProgressDisplay(tracker)

        assert display.tracker == tracker
        assert display.show_details is True

    def test_progress_display_without_details(self):
        """Test creating ProgressDisplay without details."""
        tracker = ProgressTracker("test_operation", 5)
        display = ProgressDisplay(tracker, show_details=False)

        assert display.show_details is False


class TestBatchProcessing:
    """Test batch processing functionality."""

    def test_batch_process_with_progress_success(self):
        """Test successful batch processing."""
        items = ["file1.txt", "file2.txt", "file3.txt"]

        def mock_processor(item):
            return f"processed_{item}"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            checkpoint_file = Path(f.name)

        try:
            result = batch_process_with_progress(
                items=items,
                processor_func=mock_processor,
                operation_name="test_batch",
                task_type="process",
                checkpoint_file=checkpoint_file,
                resume=True,
                show_progress=False,
            )

            assert len(result["results"]) == 3
            assert result["summary"]["completed"] == 3
            assert result["summary"]["failed"] == 0
            assert result["summary"]["progress_percentage"] == 100.0

            # Check results
            for i, item_result in enumerate(result["results"]):
                assert item_result["success"] is True
                assert item_result["result"] == f"processed_{items[i]}"

        finally:
            checkpoint_file.unlink(missing_ok=True)

    def test_batch_process_with_progress_failures(self):
        """Test batch processing with failures."""
        items = ["file1.txt", "file2.txt", "file3.txt"]

        def mock_processor(item):
            if "file2" in item:
                raise ValueError("Processing failed")
            return f"processed_{item}"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            checkpoint_file = Path(f.name)

        try:
            result = batch_process_with_progress(
                items=items,
                processor_func=mock_processor,
                operation_name="test_batch",
                task_type="process",
                checkpoint_file=checkpoint_file,
                resume=True,
                show_progress=False,
            )

            assert len(result["results"]) == 3
            assert result["summary"]["completed"] == 2
            assert result["summary"]["failed"] == 1
            assert abs(result["summary"]["progress_percentage"] - 66.7) < 0.1

            # Check results
            assert result["results"][0]["success"] is True
            assert result["results"][1]["success"] is False
            assert result["results"][2]["success"] is True

        finally:
            checkpoint_file.unlink(missing_ok=True)

    def test_batch_process_resume(self):
        """Test batch processing with resume functionality."""
        items = ["file1.txt", "file2.txt", "file3.txt"]

        def mock_processor(item):
            return f"processed_{item}"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            checkpoint_file = Path(f.name)

        try:
            # First run - process all items
            result1 = batch_process_with_progress(
                items=items,
                processor_func=mock_processor,
                operation_name="test_batch",
                task_type="process",
                checkpoint_file=checkpoint_file,
                resume=True,
                show_progress=False,
            )

            assert result1["summary"]["completed"] == 3

            # Second run - should skip all items
            result2 = batch_process_with_progress(
                items=items,
                processor_func=mock_processor,
                operation_name="test_batch",
                task_type="process",
                checkpoint_file=checkpoint_file,
                resume=True,
                show_progress=False,
            )

            assert result2["summary"]["completed"] == 0
            assert result2["summary"]["skipped"] == 3

        finally:
            checkpoint_file.unlink(missing_ok=True)


class TestResumeFromCheckpoint:
    """Test resume from checkpoint functionality."""

    def test_resume_from_checkpoint(self):
        """Test resuming from checkpoint."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            checkpoint_file = Path(f.name)

        try:
            # Create initial tracker and save checkpoint
            tracker = ProgressTracker("test_operation", 3, checkpoint_file)
            tracker.add_task("task1", "/path/to/file1.txt", "summarize")
            tracker.add_task("task2", "/path/to/file2.txt", "transcribe")
            tracker.add_task("task3", "/path/to/file3.txt", "moc")

            tracker.start_task("task1")
            tracker.complete_task("task1")
            tracker.start_task("task2")
            tracker.fail_task("task2", "Error")

            # Resume from checkpoint
            resumed_tracker = resume_from_checkpoint(checkpoint_file)

            assert resumed_tracker.operation_name == "test_operation"
            assert resumed_tracker.total_tasks == 3
            assert resumed_tracker.completed_count == 1
            assert resumed_tracker.failed_count == 1
            assert len(resumed_tracker.tasks) == 3

        finally:
            checkpoint_file.unlink(missing_ok=True)


if __name__ == "__main__":
    pytest.main([__file__])
