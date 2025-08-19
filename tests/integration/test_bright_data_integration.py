"""
Integration tests for Bright Data functionality.

Tests the complete Bright Data integration including session management,
cost tracking, adapters, and database interactions.
"""

import os
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from knowledge_system.database import DatabaseService
from knowledge_system.database.models import BrightDataSession, VideoRecord
from knowledge_system.utils.bright_data import BrightDataSessionManager
from knowledge_system.utils.bright_data_adapters import (
    BrightDataAdapter,
    adapt_bright_data_metadata,
    adapt_bright_data_transcript,
)
from knowledge_system.utils.cost_tracking import CostTracker
from knowledge_system.utils.deduplication import (
    DuplicationPolicy,
    VideoDeduplicationService,
)


class TestBrightDataSessionManager:
    """Test Bright Data session management functionality."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        db_service = DatabaseService(database_url=f"sqlite:///{db_path}")
        db_service.create_all_tables()

        yield db_service

        # Cleanup
        os.unlink(db_path)

    @pytest.fixture
    def session_manager(self, temp_db):
        """Create session manager with temporary database."""
        return BrightDataSessionManager(temp_db)

    @pytest.fixture
    def mock_env_vars(self):
        """Mock environment variables for Bright Data."""
        with patch.dict(
            os.environ,
            {
                "BD_CUST": "c_test123",
                "BD_ZONE": "test_zone",
                "BD_PASS": "test_password",
            },
        ):
            yield

    def test_validate_credentials_success(self, session_manager, mock_env_vars):
        """Test successful credential validation."""
        assert session_manager._validate_credentials() == True

    def test_validate_credentials_missing(self, session_manager):
        """Test credential validation with missing credentials."""
        # Remove environment variables
        with patch.dict(os.environ, {}, clear=True):
            assert session_manager._validate_credentials() == False

    def test_create_session_for_file(self, session_manager, mock_env_vars):
        """Test creating a new session for a file."""
        file_id = "test_video_123"
        session_type = "audio_download"

        session_id = session_manager.create_session_for_file(file_id, session_type)

        assert session_id is not None
        assert session_id.startswith(f"file_{file_id}_")

        # Verify session is stored in database
        with session_manager.db.get_session() as db_session:
            session_record = (
                db_session.query(BrightDataSession)
                .filter(BrightDataSession.session_id == session_id)
                .first()
            )

            assert session_record is not None
            assert session_record.video_id == file_id
            assert session_record.session_type == session_type
            assert session_record.status == "active"

    def test_get_proxy_url_for_file(self, session_manager, mock_env_vars):
        """Test generating proxy URL for a file."""
        file_id = "test_video_456"
        session_type = "metadata_scrape"

        # Create session first
        session_id = session_manager.create_session_for_file(file_id, session_type)
        proxy_url = session_manager.get_proxy_url_for_file(file_id, session_type)

        assert proxy_url is not None
        assert "zproxy.lum-superproxy.io:22225" in proxy_url
        assert "c_test123" in proxy_url
        assert "test_zone" in proxy_url
        assert session_id in proxy_url
        assert "test_password" in proxy_url

    def test_update_session_usage(self, session_manager, mock_env_vars):
        """Test updating session usage statistics."""
        file_id = "test_video_789"
        session_type = "audio_download"

        # Create session
        session_id = session_manager.create_session_for_file(file_id, session_type)

        # Update usage
        success = session_manager.update_session_usage(
            session_id=session_id,
            requests_count=5,
            data_downloaded_bytes=1024000,
            cost=0.05,
        )

        assert success == True

        # Verify usage is recorded
        with session_manager.db.get_session() as db_session:
            session_record = (
                db_session.query(BrightDataSession)
                .filter(BrightDataSession.session_id == session_id)
                .first()
            )

            assert session_record.requests_count == 5
            assert session_record.data_downloaded_bytes == 1024000
            assert session_record.cost == 0.05

    def test_end_session_for_file(self, session_manager, mock_env_vars):
        """Test ending a session for a file."""
        file_id = "test_video_end"
        session_type = "audio_download"

        # Create session
        session_id = session_manager.create_session_for_file(file_id, session_type)

        # End session
        success = session_manager.end_session_for_file(file_id)
        assert success == True

        # Verify session status
        with session_manager.db.get_session() as db_session:
            session_record = (
                db_session.query(BrightDataSession)
                .filter(BrightDataSession.session_id == session_id)
                .first()
            )

            assert session_record.status == "ended"

    def test_session_reuse_same_file(self, session_manager, mock_env_vars):
        """Test that same file reuses existing active session."""
        file_id = "test_video_reuse"
        session_type = "audio_download"

        # Create first session
        session_id_1 = session_manager.create_session_for_file(file_id, session_type)

        # Try to create another session for same file
        session_id_2 = session_manager.create_session_for_file(file_id, session_type)

        # Should return the same session ID
        assert session_id_1 == session_id_2


class TestBrightDataCostTracking:
    """Test cost tracking functionality."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        db_service = DatabaseService(database_url=f"sqlite:///{db_path}")
        db_service.create_all_tables()

        yield db_service

        # Cleanup
        os.unlink(db_path)

    @pytest.fixture
    def cost_tracker(self, temp_db):
        """Create cost tracker with temporary database."""
        return CostTracker(temp_db)

    def test_track_session_cost(self, cost_tracker, temp_db):
        """Test tracking session costs."""
        # Create a test session first
        session_id = f"test_session_{uuid.uuid4().hex[:8]}"

        with temp_db.get_session() as db_session:
            session_record = BrightDataSession(
                session_id=session_id,
                video_id="test_video",
                session_type="test",
                status="active",
            )
            db_session.add(session_record)
            db_session.commit()

        # Track cost
        success = cost_tracker.track_session_cost(
            session_id=session_id,
            requests_count=10,
            data_downloaded_bytes=2048000,
            cost=0.10,
        )

        assert success == True

        # Verify cost is recorded
        with temp_db.get_session() as db_session:
            session_record = (
                db_session.query(BrightDataSession)
                .filter(BrightDataSession.session_id == session_id)
                .first()
            )

            assert session_record.requests_count == 10
            assert session_record.data_downloaded_bytes == 2048000
            assert session_record.cost == 0.10

    def test_get_usage_summary(self, cost_tracker, temp_db):
        """Test getting usage summary."""
        # Create multiple test sessions
        for i in range(3):
            session_id = f"test_session_{i}"

            with temp_db.get_session() as db_session:
                session_record = BrightDataSession(
                    session_id=session_id,
                    video_id=f"test_video_{i}",
                    session_type="test",
                    status="ended",
                    requests_count=5,
                    data_downloaded_bytes=1024000,
                    cost=0.05,
                    created_at=datetime.utcnow(),
                )
                db_session.add(session_record)
                db_session.commit()

        # Get usage summary
        summary = cost_tracker.get_usage_summary(days=7)

        assert "summary" in summary
        assert summary["summary"]["total_cost"] == 0.15
        assert summary["summary"]["total_requests"] == 15
        assert summary["summary"]["total_data_gb"] >= 0.002  # ~3MB in GB

    def test_check_budget_alerts(self, cost_tracker, temp_db):
        """Test budget alert functionality."""
        # Create session that exceeds budget
        session_id = "expensive_session"

        with temp_db.get_session() as db_session:
            session_record = BrightDataSession(
                session_id=session_id,
                video_id="expensive_video",
                session_type="test",
                status="ended",
                cost=80.0,  # High cost
                created_at=datetime.utcnow(),
            )
            db_session.add(session_record)
            db_session.commit()

        # Check budget alerts with $100 budget
        alerts = cost_tracker.check_budget_alerts(budget=100.0)

        assert "alert_level" in alerts
        assert "current_spend" in alerts
        assert alerts["current_spend"] == 80.0
        assert alerts["budget_percentage_used"] == 80.0


class TestBrightDataDeduplication:
    """Test deduplication functionality."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        db_service = DatabaseService(database_url=f"sqlite:///{db_path}")
        db_service.create_all_tables()

        yield db_service

        # Cleanup
        os.unlink(db_path)

    @pytest.fixture
    def dedup_service(self, temp_db):
        """Create deduplication service."""
        return VideoDeduplicationService(temp_db, DuplicationPolicy.SKIP_ALL)

    def test_check_duplicate_new_video(self, dedup_service):
        """Test checking duplicate for new video."""
        url = "https://youtube.com/watch?v=new_video_123"

        result = dedup_service.check_duplicate(url)

        assert result.is_duplicate == False
        assert result.video_id == "new_video_123"
        assert result.action == "process"

    def test_check_duplicate_existing_video(self, dedup_service, temp_db):
        """Test checking duplicate for existing video."""
        video_id = "existing_video_456"
        url = f"https://youtube.com/watch?v={video_id}"

        # Create existing video record
        temp_db.create_video(
            video_id=video_id, title="Existing Video", url=url, status="completed"
        )

        # Check duplicate
        result = dedup_service.check_duplicate(url)

        assert result.is_duplicate == True
        assert result.video_id == video_id
        assert result.action == "skip"

    def test_check_batch_duplicates(self, dedup_service, temp_db):
        """Test batch duplicate checking."""
        # Create one existing video
        existing_id = "existing_batch_video"
        temp_db.create_video(
            video_id=existing_id,
            title="Existing Video",
            url=f"https://youtube.com/watch?v={existing_id}",
            status="completed",
        )

        # Test URLs
        urls = [
            f"https://youtube.com/watch?v={existing_id}",  # Duplicate
            "https://youtube.com/watch?v=new_video_1",  # New
            "https://youtube.com/watch?v=new_video_2",  # New
        ]

        unique_urls, duplicates = dedup_service.check_batch_duplicates(urls)

        assert len(unique_urls) == 2
        assert len(duplicates) == 1
        assert duplicates[0].video_id == existing_id


class TestBrightDataAdapters:
    """Test Bright Data JSON response adapters."""

    def test_adapter_with_complete_response(self):
        """Test adapter with complete Bright Data response."""
        response = {
            "id": "test_video_complete",
            "title": "Complete Test Video",
            "description": "A complete test video description",
            "videoDetails": {
                "lengthSeconds": "300",
                "viewCount": "1000000",
                "author": "Test Channel",
                "channelId": "UC_test_channel",
            },
            "statistics": {"likeCount": "50000", "commentCount": "5000"},
            "snippet": {
                "publishedAt": "2023-01-01T00:00:00Z",
                "tags": ["test", "video", "example"],
                "thumbnails": {"high": {"url": "https://example.com/thumbnail.jpg"}},
            },
            "transcript": [
                {"start": 0.0, "text": "Hello world"},
                {"start": 5.0, "text": "This is a test"},
            ],
        }

        url = "https://youtube.com/watch?v=test_video_complete"

        # Test metadata adaptation
        metadata = adapt_bright_data_metadata(response, url)

        assert metadata.video_id == "test_video_complete"
        assert metadata.title == "Complete Test Video"
        assert metadata.duration == 300
        assert metadata.view_count == 1000000
        assert metadata.like_count == 50000
        assert metadata.uploader == "Test Channel"
        assert "test" in metadata.tags
        assert metadata.extraction_method == "bright_data_api_scraper"

        # Test transcript adaptation
        transcript = adapt_bright_data_transcript(response, url)

        assert transcript.video_id == "test_video_complete"
        assert transcript.title == "Complete Test Video"
        assert "Hello world" in transcript.transcript_text
        assert len(transcript.transcript_data) == 2

    def test_adapter_with_minimal_response(self):
        """Test adapter with minimal Bright Data response."""
        response = {"title": "Minimal Test Video"}

        url = "https://youtube.com/watch?v=minimal_test"

        # Should not fail with minimal data
        metadata = adapt_bright_data_metadata(response, url)
        transcript = adapt_bright_data_transcript(response, url)

        assert metadata.video_id == "minimal_test"
        assert metadata.title == "Minimal Test Video"
        assert transcript.video_id == "minimal_test"
        assert transcript.title == "Minimal Test Video"

    def test_adapter_error_handling(self):
        """Test adapter error handling with malformed responses."""
        malformed_responses = [
            {},  # Empty
            {"corrupted": None},  # Invalid data
            {"videoDetails": {"invalid": True}},  # Malformed structure
        ]

        url = "https://youtube.com/watch?v=error_test"

        for response in malformed_responses:
            # Should not raise exceptions
            metadata = adapt_bright_data_metadata(response, url)
            transcript = adapt_bright_data_transcript(response, url)

            # Should create fallback objects
            assert metadata.video_id == "error_test"
            assert transcript.video_id == "error_test"


class TestBrightDataIntegrationWorkflow:
    """Test complete Bright Data integration workflow."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        db_service = DatabaseService(database_url=f"sqlite:///{db_path}")
        db_service.create_all_tables()

        yield db_service

        # Cleanup
        os.unlink(db_path)

    @pytest.fixture
    def mock_env_vars(self):
        """Mock environment variables for Bright Data."""
        with patch.dict(
            os.environ,
            {
                "BD_CUST": "c_workflow_test",
                "BD_ZONE": "workflow_zone",
                "BD_PASS": "workflow_password",
            },
        ):
            yield

    def test_complete_workflow(self, temp_db, mock_env_vars):
        """Test complete end-to-end workflow."""
        # Setup components
        session_manager = BrightDataSessionManager(temp_db)
        cost_tracker = CostTracker(temp_db)
        dedup_service = VideoDeduplicationService(temp_db, DuplicationPolicy.SKIP_ALL)

        video_id = "workflow_test_video"
        url = f"https://youtube.com/watch?v={video_id}"

        # Step 1: Check for duplicates
        duplicate_result = dedup_service.check_duplicate(url)
        assert duplicate_result.is_duplicate == False

        # Step 2: Create Bright Data session
        session_id = session_manager.create_session_for_file(video_id, "audio_download")
        assert session_id is not None

        # Step 3: Get proxy URL
        proxy_url = session_manager.get_proxy_url_for_file(video_id, "audio_download")
        assert proxy_url is not None
        assert "workflow_zone" in proxy_url

        # Step 4: Simulate processing (update usage)
        session_manager.update_session_usage(
            session_id=session_id,
            requests_count=3,
            data_downloaded_bytes=5120000,
            cost=0.08,
        )

        # Step 5: Process Bright Data response
        bright_data_response = {
            "id": video_id,
            "title": "Workflow Test Video",
            "videoDetails": {"lengthSeconds": "180", "author": "Test Channel"},
        }

        metadata = adapt_bright_data_metadata(bright_data_response, url)
        assert metadata.video_id == video_id

        # Step 6: Store in database
        video_record = temp_db.create_video(
            video_id=metadata.video_id,
            title=metadata.title,
            url=metadata.url,
            status="completed",
            extraction_method="bright_data_api_scraper",
        )
        assert video_record is not None

        # Step 7: End session
        session_manager.end_session_for_file(video_id)

        # Step 8: Verify final state
        usage_summary = cost_tracker.get_usage_summary(days=1)
        assert usage_summary["summary"]["total_cost"] == 0.08

        # Step 9: Test deduplication on second attempt
        duplicate_result_2 = dedup_service.check_duplicate(url)
        assert duplicate_result_2.is_duplicate == True

    @patch("knowledge_system.utils.bright_data.requests.get")
    def test_workflow_with_mocked_requests(self, mock_requests, temp_db, mock_env_vars):
        """Test workflow with mocked HTTP requests."""
        # Mock successful proxy test
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"origin": "192.168.1.100"}
        mock_requests.return_value = mock_response

        session_manager = BrightDataSessionManager(temp_db)

        # Test that session creation works with mocked environment
        session_id = session_manager.create_session_for_file("mock_test_video", "test")
        assert session_id is not None

        proxy_url = session_manager.get_proxy_url_for_file("mock_test_video", "test")
        assert "c_workflow_test" in proxy_url


if __name__ == "__main__":
    """Run integration tests directly."""
    pytest.main([__file__, "-v", "-s"])
