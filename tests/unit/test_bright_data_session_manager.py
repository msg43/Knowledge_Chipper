"""
Unit tests for Bright Data session manager.

Tests individual components of the Bright Data session management system
including URL generation, session lifecycle, and error handling.
"""

import os
import uuid
from unittest.mock import MagicMock, Mock, patch

import pytest

from knowledge_system.database import DatabaseService
from knowledge_system.database.models import BrightDataSession
from knowledge_system.utils.bright_data import BrightDataSessionManager


class TestBrightDataSessionManager:
    """Unit tests for BrightDataSessionManager."""

    @pytest.fixture
    def mock_db_service(self):
        """Create mock database service."""
        mock_db = Mock(spec=DatabaseService)
        mock_session = Mock()
        mock_db.get_session.return_value.__enter__.return_value = mock_session
        mock_db.get_session.return_value.__exit__.return_value = None
        return mock_db

    @pytest.fixture
    def session_manager(self, mock_db_service):
        """Create session manager with mocked database."""
        return BrightDataSessionManager(mock_db_service)

    def test_init(self, mock_db_service):
        """Test session manager initialization."""
        manager = BrightDataSessionManager(mock_db_service)
        assert manager.db == mock_db_service

    @patch.dict(
        os.environ,
        {"BD_CUST": "c_test", "BD_ZONE": "test_zone", "BD_PASS": "test_pass"},
    )
    def test_validate_credentials_success(self, session_manager):
        """Test successful credential validation."""
        result = session_manager._validate_credentials()
        assert result == True

    @patch.dict(os.environ, {}, clear=True)
    def test_validate_credentials_missing_all(self, session_manager):
        """Test credential validation with all missing."""
        result = session_manager._validate_credentials()
        assert result == False

    @patch.dict(os.environ, {"BD_CUST": "c_test"}, clear=True)
    def test_validate_credentials_partial(self, session_manager):
        """Test credential validation with partial credentials."""
        result = session_manager._validate_credentials()
        assert result == False

    @patch.dict(
        os.environ,
        {"BD_CUST": "c_test", "BD_ZONE": "test_zone", "BD_PASS": "test_pass"},
    )
    def test_generate_session_id_format(self, session_manager):
        """Test session ID generation format."""
        file_id = "test_video_123"
        session_id = session_manager._generate_session_id(file_id)

        assert session_id.startswith(f"file_{file_id}_")
        assert len(session_id.split("_")) >= 3  # file_videoid_uuid

        # Test uniqueness
        session_id_2 = session_manager._generate_session_id(file_id)
        assert session_id != session_id_2

    @patch.dict(
        os.environ, {"BD_CUST": "c_test123", "BD_ZONE": "zone456", "BD_PASS": "pass789"}
    )
    def test_build_proxy_url_format(self, session_manager):
        """Test proxy URL building format."""
        session_id = "test_session_xyz"
        proxy_url = session_manager._build_proxy_url(session_id)

        expected_username = f"lum-customer-c_test123-zone-zone456-session-{session_id}"
        expected_url = (
            f"http://{expected_username}:pass789@zproxy.lum-superproxy.io:22225"
        )

        assert proxy_url == expected_url

    def test_build_proxy_url_missing_credentials(self, session_manager):
        """Test proxy URL building with missing credentials."""
        with patch.dict(os.environ, {}, clear=True):
            session_id = "test_session"
            proxy_url = session_manager._build_proxy_url(session_id)
            assert proxy_url is None

    def test_create_session_for_file_new(self, session_manager, mock_db_service):
        """Test creating new session for file."""
        file_id = "new_video_123"
        session_type = "audio_download"

        # Mock database queries
        mock_session = mock_db_service.get_session.return_value.__enter__.return_value
        mock_session.query.return_value.filter.return_value.first.return_value = (
            None  # No existing session
        )

        with patch.dict(
            os.environ,
            {"BD_CUST": "c_test", "BD_ZONE": "test_zone", "BD_PASS": "test_pass"},
        ):
            session_id = session_manager.create_session_for_file(file_id, session_type)

        assert session_id is not None
        assert session_id.startswith(f"file_{file_id}_")

        # Verify database add was called
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    def test_create_session_for_file_existing(self, session_manager, mock_db_service):
        """Test reusing existing session for file."""
        file_id = "existing_video_456"
        session_type = "audio_download"
        existing_session_id = f"file_{file_id}_existing"

        # Mock existing session
        mock_existing_session = Mock()
        mock_existing_session.session_id = existing_session_id

        mock_session = mock_db_service.get_session.return_value.__enter__.return_value
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_existing_session
        )

        session_id = session_manager.create_session_for_file(file_id, session_type)

        assert session_id == existing_session_id
        # Should not create new session
        mock_session.add.assert_not_called()

    def test_get_proxy_url_for_file_success(self, session_manager, mock_db_service):
        """Test getting proxy URL for existing file session."""
        file_id = "test_video_789"
        session_type = "metadata_scrape"
        existing_session_id = f"file_{file_id}_12345"

        # Mock existing session
        mock_existing_session = Mock()
        mock_existing_session.session_id = existing_session_id

        mock_session = mock_db_service.get_session.return_value.__enter__.return_value
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_existing_session
        )

        with patch.dict(
            os.environ,
            {"BD_CUST": "c_test", "BD_ZONE": "test_zone", "BD_PASS": "test_pass"},
        ):
            proxy_url = session_manager.get_proxy_url_for_file(file_id, session_type)

        assert proxy_url is not None
        assert "lum-customer-c_test-zone-test_zone" in proxy_url
        assert existing_session_id in proxy_url

    def test_get_proxy_url_for_file_no_session(self, session_manager, mock_db_service):
        """Test getting proxy URL when no session exists."""
        file_id = "nonexistent_video"
        session_type = "audio_download"

        mock_session = mock_db_service.get_session.return_value.__enter__.return_value
        mock_session.query.return_value.filter.return_value.first.return_value = None

        proxy_url = session_manager.get_proxy_url_for_file(file_id, session_type)

        assert proxy_url is None

    def test_update_session_usage_success(self, session_manager, mock_db_service):
        """Test successful session usage update."""
        session_id = "test_session_update"

        # Mock existing session
        mock_existing_session = Mock()
        mock_existing_session.requests_count = 0
        mock_existing_session.data_downloaded_bytes = 0
        mock_existing_session.cost = 0.0

        mock_session = mock_db_service.get_session.return_value.__enter__.return_value
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_existing_session
        )

        success = session_manager.update_session_usage(
            session_id=session_id,
            requests_count=5,
            data_downloaded_bytes=1024000,
            cost=0.05,
        )

        assert success == True
        assert mock_existing_session.requests_count == 5
        assert mock_existing_session.data_downloaded_bytes == 1024000
        assert mock_existing_session.cost == 0.05
        mock_session.commit.assert_called_once()

    def test_update_session_usage_not_found(self, session_manager, mock_db_service):
        """Test session usage update for non-existent session."""
        session_id = "nonexistent_session"

        mock_session = mock_db_service.get_session.return_value.__enter__.return_value
        mock_session.query.return_value.filter.return_value.first.return_value = None

        success = session_manager.update_session_usage(
            session_id=session_id,
            requests_count=5,
            data_downloaded_bytes=1024000,
            cost=0.05,
        )

        assert success == False
        mock_session.commit.assert_not_called()

    def test_end_session_for_file_success(self, session_manager, mock_db_service):
        """Test successful session ending."""
        file_id = "test_video_end"

        # Mock existing session
        mock_existing_session = Mock()
        mock_existing_session.status = "active"

        mock_session = mock_db_service.get_session.return_value.__enter__.return_value
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_existing_session
        )

        success = session_manager.end_session_for_file(file_id)

        assert success == True
        assert mock_existing_session.status == "ended"
        mock_session.commit.assert_called_once()

    def test_end_session_for_file_not_found(self, session_manager, mock_db_service):
        """Test ending session for file with no active session."""
        file_id = "nonexistent_video"

        mock_session = mock_db_service.get_session.return_value.__enter__.return_value
        mock_session.query.return_value.filter.return_value.first.return_value = None

        success = session_manager.end_session_for_file(file_id)

        assert success == False
        mock_session.commit.assert_not_called()

    def test_error_handling_database_exception(self, session_manager, mock_db_service):
        """Test error handling when database operations fail."""
        file_id = "error_test_video"
        session_type = "audio_download"

        # Mock database exception
        mock_db_service.get_session.side_effect = Exception(
            "Database connection failed"
        )

        # Should not raise exception, should return None/False
        session_id = session_manager.create_session_for_file(file_id, session_type)
        assert session_id is None

        proxy_url = session_manager.get_proxy_url_for_file(file_id, session_type)
        assert proxy_url is None

        update_success = session_manager.update_session_usage(
            "test_session", 1, 100, 0.01
        )
        assert update_success == False

        end_success = session_manager.end_session_for_file(file_id)
        assert end_success == False

    def test_session_id_uniqueness(self, session_manager):
        """Test that session IDs are unique across multiple generations."""
        file_id = "uniqueness_test"

        session_ids = set()
        for _ in range(100):
            session_id = session_manager._generate_session_id(file_id)
            assert session_id not in session_ids
            session_ids.add(session_id)

    @patch.dict(
        os.environ,
        {
            "BD_CUST": "c_special!@#",
            "BD_ZONE": "zone-with-dashes",
            "BD_PASS": "pass with spaces",
        },
    )
    def test_special_characters_in_credentials(self, session_manager):
        """Test handling of special characters in credentials."""
        session_id = "test_session"
        proxy_url = session_manager._build_proxy_url(session_id)

        # Should still build valid URL (characters will be URL encoded if needed)
        assert proxy_url is not None
        assert "zproxy.lum-superproxy.io:22225" in proxy_url

    def test_concurrent_session_creation(self, session_manager, mock_db_service):
        """Test behavior when multiple sessions are created concurrently."""
        file_id = "concurrent_test"
        session_type = "audio_download"

        # Mock database to simulate race condition
        mock_session = mock_db_service.get_session.return_value.__enter__.return_value

        # First call returns None (no existing session)
        # Second call returns existing session (simulating concurrent creation)
        mock_existing_session = Mock()
        mock_existing_session.session_id = f"file_{file_id}_concurrent"

        mock_session.query.return_value.filter.return_value.first.side_effect = [
            None,  # First check - no session
            mock_existing_session,  # After creation attempt - session exists
        ]

        with patch.dict(
            os.environ,
            {"BD_CUST": "c_test", "BD_ZONE": "test_zone", "BD_PASS": "test_pass"},
        ):
            session_id = session_manager.create_session_for_file(file_id, session_type)

        # Should handle gracefully and return a valid session ID
        assert session_id is not None
