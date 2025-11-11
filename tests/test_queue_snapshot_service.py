"""
Unit tests for QueueSnapshotService
"""

import time
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from knowledge_system.database.models import MediaSource, SourceStageStatus
from knowledge_system.services.queue_snapshot_service import (
    QueueSnapshot,
    QueueSnapshotService,
)


class TestQueueSnapshot(unittest.TestCase):
    """Test the QueueSnapshot data class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_source = MagicMock(spec=MediaSource)
        self.mock_source.source_id = "test_123"
        self.mock_source.title = "Test Video"
        self.mock_source.url = "https://youtube.com/watch?v=test123"
        self.mock_source.created_at = datetime.utcnow()

    def test_initialization(self):
        """Test QueueSnapshot initialization."""
        snapshot = QueueSnapshot("test_123", self.mock_source)

        self.assertEqual(snapshot.source_id, "test_123")
        self.assertEqual(snapshot.title, "Test Video")
        self.assertEqual(snapshot.url, "https://youtube.com/watch?v=test123")
        self.assertEqual(snapshot.current_stage, None)
        self.assertEqual(snapshot.overall_status, "pending")
        self.assertEqual(len(snapshot.stage_statuses), 0)

    def test_add_stage_status(self):
        """Test adding stage status updates derived fields."""
        snapshot = QueueSnapshot("test_123", self.mock_source)

        # Add download stage
        download_status = MagicMock(spec=SourceStageStatus)
        download_status.stage = "download"
        download_status.status = "completed"
        download_status.progress_percent = 100.0
        download_status.started_at = datetime.utcnow() - timedelta(minutes=5)
        download_status.completed_at = datetime.utcnow() - timedelta(minutes=2)
        download_status.metadata_json = {}

        snapshot.add_stage_status(download_status)

        self.assertEqual(len(snapshot.stage_statuses), 1)
        self.assertEqual(snapshot.current_stage, None)  # Completed, so no current
        self.assertEqual(snapshot.overall_status, "completed")

    def test_current_stage_detection(self):
        """Test detection of current active stage."""
        snapshot = QueueSnapshot("test_123", self.mock_source)

        # Add completed download
        download_status = MagicMock(spec=SourceStageStatus)
        download_status.stage = "download"
        download_status.status = "completed"
        download_status.metadata_json = {}
        snapshot.add_stage_status(download_status)

        # Add in-progress transcription
        transcription_status = MagicMock(spec=SourceStageStatus)
        transcription_status.stage = "transcription"
        transcription_status.status = "in_progress"
        transcription_status.started_at = datetime.utcnow() - timedelta(minutes=1)
        transcription_status.metadata_json = {"retry_count": 1}
        snapshot.add_stage_status(transcription_status)

        self.assertEqual(snapshot.current_stage, "transcription")
        self.assertEqual(snapshot.overall_status, "in_progress")
        self.assertEqual(snapshot.retry_count, 1)

    def test_to_dict_serialization(self):
        """Test dictionary serialization."""
        snapshot = QueueSnapshot("test_123", self.mock_source)

        # Add a stage status
        status = MagicMock(spec=SourceStageStatus)
        status.stage = "download"
        status.status = "completed"
        status.progress_percent = 100.0
        status.started_at = datetime.utcnow()
        status.completed_at = datetime.utcnow()
        status.assigned_worker = "Account_1"
        status.metadata_json = {"url": "test.com"}

        snapshot.add_stage_status(status)

        result = snapshot.to_dict()

        self.assertEqual(result["source_id"], "test_123")
        self.assertEqual(result["title"], "Test Video")
        self.assertIn("download", result["stages"])
        self.assertEqual(result["stages"]["download"]["status"], "completed")
        self.assertEqual(result["stages"]["download"]["progress_percent"], 100.0)


class TestQueueSnapshotService(unittest.TestCase):
    """Test the QueueSnapshotService."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_db_service = MagicMock()
        self.service = QueueSnapshotService(self.mock_db_service)

    def test_cache_functionality(self):
        """Test cache TTL and invalidation."""
        # Initially cache should be invalid
        self.assertFalse(self.service._is_cache_valid())

        # Set cache
        self.service._cache["test_key"] = "test_value"
        self.service._cache_timestamp = time.time()

        # Should be valid immediately
        self.assertTrue(self.service._is_cache_valid())

        # Simulate time passing
        self.service._cache_timestamp = time.time() - 3  # 3 seconds ago
        self.assertFalse(self.service._is_cache_valid())

        # Clear cache
        self.service.clear_cache()
        self.assertEqual(len(self.service._cache), 0)
        self.assertEqual(self.service._cache_timestamp, 0)

    @patch("knowledge_system.services.queue_snapshot_service.logger")
    def test_get_full_queue_with_filters(self, mock_logger):
        """Test getting full queue with filters."""
        # Mock database session and query
        mock_session = MagicMock()
        self.mock_db_service.get_session.return_value.__enter__.return_value = (
            mock_session
        )

        # Mock query chain
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.distinct.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.offset.return_value = mock_query

        # Mock count
        mock_query.count.return_value = 2

        # Mock results
        mock_source1 = MagicMock(spec=MediaSource)
        mock_source1.source_id = "test_1"
        mock_source1.title = "Test 1"
        mock_source1.url = "url1"
        mock_source1.created_at = datetime.utcnow()
        mock_source1.stage_statuses = []

        mock_source2 = MagicMock(spec=MediaSource)
        mock_source2.source_id = "test_2"
        mock_source2.title = "Test 2"
        mock_source2.url = "url2"
        mock_source2.created_at = datetime.utcnow()
        mock_source2.stage_statuses = []

        mock_query.all.return_value = [mock_source1, mock_source2]

        # Test with filters
        snapshots, total = self.service.get_full_queue(
            status_filter=["in_progress"], stage_filter=["download"], limit=10, offset=0
        )

        self.assertEqual(len(snapshots), 2)
        self.assertEqual(total, 2)
        self.assertIsInstance(snapshots[0], QueueSnapshot)

    @patch("knowledge_system.services.queue_snapshot_service.logger")
    def test_get_source_timeline(self, mock_logger):
        """Test getting timeline for single source."""
        # Mock database session
        mock_session = MagicMock()
        self.mock_db_service.get_session.return_value.__enter__.return_value = (
            mock_session
        )

        # Mock source with stage statuses
        mock_source = MagicMock(spec=MediaSource)
        mock_source.source_id = "test_123"
        mock_source.title = "Test Video"
        mock_source.url = "https://test.com"
        mock_source.created_at = datetime.utcnow()

        mock_status = MagicMock(spec=SourceStageStatus)
        mock_status.stage = "download"
        mock_status.status = "completed"
        mock_status.metadata_json = {}

        mock_source.stage_statuses = [mock_status]

        # Mock query
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_source

        # Test
        snapshot = self.service.get_source_timeline("test_123")

        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.source_id, "test_123")
        self.assertEqual(len(snapshot.stage_statuses), 1)

    @patch("knowledge_system.services.queue_snapshot_service.logger")
    def test_get_stage_summary(self, mock_logger):
        """Test getting summary counts by stage and status."""
        # Mock database session
        mock_session = MagicMock()
        self.mock_db_service.get_session.return_value.__enter__.return_value = (
            mock_session
        )

        # Mock stage statuses
        statuses = [
            self._create_mock_status("download", "completed"),
            self._create_mock_status("download", "in_progress"),
            self._create_mock_status("download", "failed"),
            self._create_mock_status("transcription", "completed"),
            self._create_mock_status("transcription", "in_progress"),
        ]

        mock_session.query.return_value.all.return_value = statuses

        # Test
        summary = self.service.get_stage_summary()

        self.assertEqual(summary["download"]["completed"], 1)
        self.assertEqual(summary["download"]["in_progress"], 1)
        self.assertEqual(summary["download"]["failed"], 1)
        self.assertEqual(summary["transcription"]["completed"], 1)
        self.assertEqual(summary["transcription"]["in_progress"], 1)

    @patch("knowledge_system.services.queue_snapshot_service.logger")
    def test_get_throughput_metrics(self, mock_logger):
        """Test throughput metrics calculation."""
        # Mock database session
        mock_session = MagicMock()
        self.mock_db_service.get_session.return_value.__enter__.return_value = (
            mock_session
        )

        # Mock completed statuses in time window
        now = datetime.utcnow()
        statuses = [
            self._create_mock_status(
                "download", "completed", now - timedelta(hours=0.5)
            ),
            self._create_mock_status("download", "completed", now - timedelta(hours=1)),
            self._create_mock_status(
                "transcription", "completed", now - timedelta(hours=2)
            ),
        ]

        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = statuses

        # Test 24 hour window
        metrics = self.service.get_throughput_metrics(24)

        self.assertEqual(metrics["time_window_hours"], 24)
        self.assertEqual(metrics["total_completed"], 3)
        self.assertAlmostEqual(metrics["average_items_per_hour"], 3 / 24, places=2)
        self.assertEqual(metrics["items_per_hour_by_stage"]["download"], 2 / 24)
        self.assertEqual(metrics["items_per_hour_by_stage"]["transcription"], 1 / 24)

    def _create_mock_status(self, stage, status, completed_at=None):
        """Helper to create mock SourceStageStatus."""
        mock_status = MagicMock(spec=SourceStageStatus)
        mock_status.stage = stage
        mock_status.status = status
        mock_status.completed_at = completed_at
        return mock_status


if __name__ == "__main__":
    unittest.main()
