"""
GUI tests for Queue Tab using pytest-qt
"""

import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QApplication

from knowledge_system.database.models import MediaSource, SourceStageStatus
from knowledge_system.gui.queue_event_bus import QueueEvent, get_queue_event_bus
from knowledge_system.gui.tabs.queue_tab import QueueTab
from knowledge_system.services.queue_snapshot_service import QueueSnapshot


@pytest.fixture
def mock_db_service():
    """Mock database service."""
    with patch("knowledge_system.gui.tabs.queue_tab.DatabaseService") as mock:
        yield mock.return_value


@pytest.fixture
def mock_snapshot_service():
    """Mock queue snapshot service."""
    with patch("knowledge_system.gui.tabs.queue_tab.QueueSnapshotService") as mock:
        yield mock.return_value


@pytest.fixture
def queue_tab(qtbot, mock_db_service, mock_snapshot_service):
    """Create QueueTab instance for testing."""
    # Mock parent window
    parent = MagicMock()
    parent.log_message = MagicMock()
    parent.log_error = MagicMock()

    # Create tab
    tab = QueueTab(parent)
    tab.db_service = mock_db_service
    tab.snapshot_service = mock_snapshot_service

    # Stop auto-refresh timer for controlled testing
    tab.refresh_timer.stop()

    qtbot.addWidget(tab)
    return tab


class TestQueueTab:
    """Test suite for Queue Tab functionality."""

    def test_tab_initialization(self, queue_tab):
        """Test Queue tab initializes correctly."""
        assert queue_tab is not None
        assert queue_tab.queue_table.columnCount() == 8
        assert queue_tab.stats_label.text() == "Loading queue statistics..."
        assert queue_tab.current_page == 0
        assert queue_tab.page_size == 50

    def test_empty_queue_display(self, queue_tab, mock_snapshot_service):
        """Test empty queue displays correctly."""
        # Mock empty queue
        mock_snapshot_service.get_full_queue.return_value = ([], 0)
        mock_snapshot_service.get_stage_summary.return_value = {}
        mock_snapshot_service.get_throughput_metrics.return_value = {
            "average_items_per_hour": 0
        }

        # Refresh queue
        queue_tab._refresh_queue()

        # Check display
        assert queue_tab.queue_table.rowCount() == 0
        assert "Total: 0" in queue_tab.stats_label.text()

    def test_queue_with_items(self, queue_tab, mock_snapshot_service):
        """Test queue displays items correctly."""
        # Create mock snapshots
        mock_source1 = MagicMock(spec=MediaSource)
        mock_source1.title = "Test Video 1"
        mock_source1.url = "https://youtube.com/watch?v=test1"

        snapshot1 = QueueSnapshot("test_1", mock_source1)
        snapshot1.current_stage = "download"
        snapshot1.overall_status = "in_progress"

        # Mock stage status
        mock_status = MagicMock()
        mock_status.progress_percent = 45.0
        mock_status.assigned_worker = "Account_1"
        snapshot1.stage_statuses = {"download": mock_status}

        # Mock service returns
        mock_snapshot_service.get_full_queue.return_value = ([snapshot1], 1)
        mock_snapshot_service.get_stage_summary.return_value = {
            "download": {"in_progress": 1}
        }
        mock_snapshot_service.get_throughput_metrics.return_value = {
            "average_items_per_hour": 5.0
        }

        # Refresh
        queue_tab._refresh_queue()

        # Check table
        assert queue_tab.queue_table.rowCount() == 1
        assert queue_tab.queue_table.item(0, 0).text() == "Test Video 1"
        assert "youtube.com/watch?v=test1" in queue_tab.queue_table.item(0, 1).text()
        assert queue_tab.queue_table.item(0, 2).text() == "Download"
        assert queue_tab.queue_table.item(0, 3).text() == "In_progress"
        assert queue_tab.queue_table.item(0, 4).text() == "45%"

    def test_filter_by_stage(self, qtbot, queue_tab, mock_snapshot_service):
        """Test filtering by stage works correctly."""
        # Set filter
        queue_tab.stage_combo.setCurrentIndex(1)  # First stage after "All"

        # Verify filter was applied
        qtbot.wait(100)  # Wait for event processing

        # Check that service was called with stage filter
        mock_snapshot_service.get_full_queue.assert_called()
        call_args = mock_snapshot_service.get_full_queue.call_args
        assert "stage_filter" in call_args[1]

    def test_filter_by_status(self, qtbot, queue_tab, mock_snapshot_service):
        """Test filtering by status works correctly."""
        # Set filter
        queue_tab.status_combo.setCurrentIndex(2)  # Some status

        # Verify filter was applied
        qtbot.wait(100)

        # Check service call
        mock_snapshot_service.get_full_queue.assert_called()
        call_args = mock_snapshot_service.get_full_queue.call_args
        assert "status_filter" in call_args[1]

    def test_pagination(self, qtbot, queue_tab, mock_snapshot_service):
        """Test pagination controls work correctly."""
        # Mock multi-page results
        mock_snapshot_service.get_full_queue.return_value = ([], 100)  # 100 total items

        # Initial refresh
        queue_tab._refresh_queue()

        # Check pagination state
        assert queue_tab.page_label.text() == "Page 1 of 2"
        assert queue_tab.prev_button.isEnabled() is False
        assert queue_tab.next_button.isEnabled() is True

        # Go to next page
        qtbot.mouseClick(queue_tab.next_button, Qt.MouseButton.LeftButton)

        # Check updated state
        assert queue_tab.current_page == 1
        assert queue_tab.prev_button.isEnabled() is True
        assert queue_tab.next_button.isEnabled() is False

    def test_real_time_event_updates(self, qtbot, queue_tab, mock_snapshot_service):
        """Test real-time event updates via event bus."""
        # Get event bus
        event_bus = get_queue_event_bus()

        # Connect to refresh tracking
        refresh_called = []
        original_refresh = queue_tab._refresh_queue
        queue_tab._refresh_queue = (
            lambda: refresh_called.append(True) or original_refresh()
        )

        # Emit event
        event = QueueEvent(
            source_id="test_123",
            stage="transcription",
            status="in_progress",
            progress_percent=50.0,
        )

        event_bus.stage_status_changed.emit(event)

        # Wait for signal processing
        qtbot.wait(100)

        # Check refresh was triggered
        assert len(refresh_called) > 0

    def test_auto_refresh_timer(self, qtbot, queue_tab, mock_snapshot_service):
        """Test auto-refresh timer functionality."""
        # Track refresh calls
        refresh_count = []
        original_refresh = queue_tab._refresh_queue
        queue_tab._refresh_queue = (
            lambda: refresh_count.append(time.time()) or original_refresh()
        )

        # Start timer with short interval for testing
        queue_tab.refresh_timer.setInterval(100)  # 100ms for testing
        queue_tab.refresh_timer.start()

        # Wait for multiple refreshes
        qtbot.wait(250)

        # Stop timer
        queue_tab.refresh_timer.stop()

        # Should have at least 2 refreshes
        assert len(refresh_count) >= 2

    def test_row_double_click(self, qtbot, queue_tab):
        """Test double-clicking row shows details."""
        # Add a row
        queue_tab.queue_table.setRowCount(1)

        # Add source_id to actions column
        from PyQt6.QtWidgets import QTableWidgetItem

        if not queue_tab.queue_table.item(0, 7):
            queue_tab.queue_table.setItem(0, 7, QTableWidgetItem())
        action_item = queue_tab.queue_table.item(0, 7)
        action_item.setData(Qt.ItemDataRole.UserRole, "test_source_123")

        # Track log messages
        log_messages = []
        queue_tab.log_message = lambda msg: log_messages.append(msg)

        # Double click
        queue_tab._on_row_double_clicked(0, 0)

        # Check log
        assert len(log_messages) == 1
        assert "test_source_123" in log_messages[0]

    def test_search_functionality(self, qtbot, queue_tab, mock_snapshot_service):
        """Test search box filters results."""
        # Type in search box
        queue_tab.search_box.setText("test search")

        # Wait for debounce
        qtbot.wait(100)

        # Check state updated
        assert queue_tab.search_text == "test search"
        assert queue_tab.current_page == 0  # Reset to first page

    def test_stats_display(self, queue_tab, mock_snapshot_service):
        """Test statistics display in header."""
        # Mock stage summary
        mock_snapshot_service.get_stage_summary.return_value = {
            "download": {"in_progress": 2, "completed": 5, "failed": 1},
            "transcription": {"in_progress": 1, "completed": 3},
        }
        mock_snapshot_service.get_throughput_metrics.return_value = {
            "average_items_per_hour": 12.5
        }

        # Update stats
        queue_tab._update_stats()

        stats_text = queue_tab.stats_label.text()
        assert "Total: 12" in stats_text  # 2+5+1+1+3
        assert "In Progress: 3" in stats_text  # 2+1
        assert "Completed: 8" in stats_text  # 5+3
        assert "Failed: 1" in stats_text
        assert "Rate: 12.5/hr" in stats_text

    def test_cleanup(self, queue_tab):
        """Test cleanup stops timer."""
        # Start timer
        queue_tab.refresh_timer.start()
        assert queue_tab.refresh_timer.isActive()

        # Cleanup
        queue_tab.cleanup()

        # Timer should be stopped
        assert not queue_tab.refresh_timer.isActive()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
