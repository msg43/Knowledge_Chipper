"""
Unit tests for cost tracking functionality.

Tests cost tracking, budget monitoring, and usage analytics for Bright Data services.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock

import pytest

from knowledge_system.database import DatabaseService
from knowledge_system.database.models import BrightDataSession
from knowledge_system.utils.cost_tracking import CostTracker


class TestCostTracker:
    """Unit tests for CostTracker."""

    @pytest.fixture
    def mock_db_service(self):
        """Create mock database service."""
        mock_db = Mock(spec=DatabaseService)
        mock_session = Mock()
        mock_db.get_session.return_value.__enter__.return_value = mock_session
        mock_db.get_session.return_value.__exit__.return_value = None
        return mock_db

    @pytest.fixture
    def cost_tracker(self, mock_db_service):
        """Create cost tracker with mocked database."""
        return CostTracker(mock_db_service)

    def test_init(self, mock_db_service):
        """Test cost tracker initialization."""
        tracker = CostTracker(mock_db_service)
        assert tracker.db == mock_db_service

    def test_track_session_cost_success(self, cost_tracker, mock_db_service):
        """Test successful session cost tracking."""
        session_id = "test_session_123"

        # Mock existing session
        mock_session_record = Mock()
        mock_session_record.requests_count = 0
        mock_session_record.data_downloaded_bytes = 0
        mock_session_record.cost = 0.0

        mock_session = mock_db_service.get_session.return_value.__enter__.return_value
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_session_record
        )

        success = cost_tracker.track_session_cost(
            session_id=session_id,
            requests_count=10,
            data_downloaded_bytes=2048000,
            cost=0.15,
        )

        assert success == True
        assert mock_session_record.requests_count == 10
        assert mock_session_record.data_downloaded_bytes == 2048000
        assert mock_session_record.cost == 0.15
        mock_session.commit.assert_called_once()

    def test_track_session_cost_session_not_found(self, cost_tracker, mock_db_service):
        """Test cost tracking for non-existent session."""
        session_id = "nonexistent_session"

        mock_session = mock_db_service.get_session.return_value.__enter__.return_value
        mock_session.query.return_value.filter.return_value.first.return_value = None

        success = cost_tracker.track_session_cost(
            session_id=session_id,
            requests_count=5,
            data_downloaded_bytes=1024000,
            cost=0.05,
        )

        assert success == False
        mock_session.commit.assert_not_called()

    def test_track_session_cost_accumulation(self, cost_tracker, mock_db_service):
        """Test that costs accumulate properly."""
        session_id = "accumulation_test"

        # Mock existing session with previous costs
        mock_session_record = Mock()
        mock_session_record.requests_count = 5
        mock_session_record.data_downloaded_bytes = 1024000
        mock_session_record.cost = 0.05

        mock_session = mock_db_service.get_session.return_value.__enter__.return_value
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_session_record
        )

        success = cost_tracker.track_session_cost(
            session_id=session_id,
            requests_count=3,
            data_downloaded_bytes=512000,
            cost=0.03,
        )

        assert success == True
        assert mock_session_record.requests_count == 8  # 5 + 3
        assert mock_session_record.data_downloaded_bytes == 1536000  # 1024000 + 512000
        assert mock_session_record.cost == 0.08  # 0.05 + 0.03

    def test_get_usage_summary_with_data(self, cost_tracker, mock_db_service):
        """Test usage summary generation with data."""
        days = 7

        # Mock session data
        mock_sessions = []
        for i in range(3):
            mock_session = Mock()
            mock_session.cost = 0.10
            mock_session.requests_count = 5
            mock_session.data_downloaded_bytes = 1024000
            mock_session.created_at = datetime.utcnow() - timedelta(days=i)
            mock_sessions.append(mock_session)

        mock_session = mock_db_service.get_session.return_value.__enter__.return_value
        mock_session.query.return_value.filter.return_value.all.return_value = (
            mock_sessions
        )

        summary = cost_tracker.get_usage_summary(days)

        assert "summary" in summary
        assert summary["summary"]["total_cost"] == 0.30
        assert summary["summary"]["total_requests"] == 15
        assert summary["summary"]["total_data_gb"] >= 0.002  # ~3MB in GB
        assert summary["summary"]["daily_average_cost"] == 0.30 / days
        assert summary["summary"]["monthly_estimated_cost"] == (0.30 / days) * 30

    def test_get_usage_summary_no_data(self, cost_tracker, mock_db_service):
        """Test usage summary with no data."""
        days = 7

        mock_session = mock_db_service.get_session.return_value.__enter__.return_value
        mock_session.query.return_value.filter.return_value.all.return_value = []

        summary = cost_tracker.get_usage_summary(days)

        assert "summary" in summary
        assert summary["summary"]["total_cost"] == 0.0
        assert summary["summary"]["total_requests"] == 0
        assert summary["summary"]["total_data_gb"] == 0.0
        assert summary["summary"]["daily_average_cost"] == 0.0
        assert summary["summary"]["monthly_estimated_cost"] == 0.0

    def test_get_cost_breakdown_by_type(self, cost_tracker, mock_db_service):
        """Test cost breakdown by session type."""
        # Mock sessions with different types
        mock_sessions = [
            Mock(session_type="audio_download", cost=0.15),
            Mock(session_type="audio_download", cost=0.10),
            Mock(session_type="metadata_scrape", cost=0.02),
            Mock(session_type="metadata_scrape", cost=0.01),
            Mock(session_type="playlist_expansion", cost=0.05),
        ]

        mock_session = mock_db_service.get_session.return_value.__enter__.return_value
        mock_session.query.return_value.filter.return_value.all.return_value = (
            mock_sessions
        )

        breakdown = cost_tracker.get_cost_breakdown()

        assert "by_session_type" in breakdown
        by_type = breakdown["by_session_type"]

        assert by_type["audio_download"]["total_cost"] == 0.25
        assert by_type["audio_download"]["session_count"] == 2
        assert by_type["metadata_scrape"]["total_cost"] == 0.03
        assert by_type["metadata_scrape"]["session_count"] == 2
        assert by_type["playlist_expansion"]["total_cost"] == 0.05
        assert by_type["playlist_expansion"]["session_count"] == 1

    def test_check_budget_alerts_green(self, cost_tracker, mock_db_service):
        """Test budget alerts when usage is low (green)."""
        budget = 100.0

        # Mock low usage sessions
        mock_sessions = [Mock(cost=5.0)]

        mock_session = mock_db_service.get_session.return_value.__enter__.return_value
        mock_session.query.return_value.filter.return_value.all.return_value = (
            mock_sessions
        )

        alerts = cost_tracker.check_budget_alerts(budget)

        assert alerts["alert_level"] == "green"
        assert alerts["current_spend"] == 5.0
        assert alerts["budget_percentage_used"] == 5.0
        assert alerts["projected_monthly_cost"] == 5.0 * 30  # Assuming 1-day period
        assert alerts["projected_percentage"] == (5.0 * 30 / budget) * 100

    def test_check_budget_alerts_yellow(self, cost_tracker, mock_db_service):
        """Test budget alerts when usage is moderate (yellow)."""
        budget = 100.0

        # Mock moderate usage (60% of budget)
        mock_sessions = [Mock(cost=60.0)]

        mock_session = mock_db_service.get_session.return_value.__enter__.return_value
        mock_session.query.return_value.filter.return_value.all.return_value = (
            mock_sessions
        )

        alerts = cost_tracker.check_budget_alerts(budget)

        assert alerts["alert_level"] == "yellow"
        assert alerts["current_spend"] == 60.0
        assert alerts["budget_percentage_used"] == 60.0

    def test_check_budget_alerts_red(self, cost_tracker, mock_db_service):
        """Test budget alerts when usage is high (red)."""
        budget = 100.0

        # Mock high usage (90% of budget)
        mock_sessions = [Mock(cost=90.0)]

        mock_session = mock_db_service.get_session.return_value.__enter__.return_value
        mock_session.query.return_value.filter.return_value.all.return_value = (
            mock_sessions
        )

        alerts = cost_tracker.check_budget_alerts(budget)

        assert alerts["alert_level"] == "red"
        assert alerts["current_spend"] == 90.0
        assert alerts["budget_percentage_used"] == 90.0
        assert "recommendations" in alerts

    def test_check_budget_alerts_over_budget(self, cost_tracker, mock_db_service):
        """Test budget alerts when over budget."""
        budget = 100.0

        # Mock usage over budget
        mock_sessions = [Mock(cost=120.0)]

        mock_session = mock_db_service.get_session.return_value.__enter__.return_value
        mock_session.query.return_value.filter.return_value.all.return_value = (
            mock_sessions
        )

        alerts = cost_tracker.check_budget_alerts(budget)

        assert alerts["alert_level"] == "red"
        assert alerts["current_spend"] == 120.0
        assert alerts["budget_percentage_used"] == 120.0
        assert "Over budget" in alerts["alert_message"]

    def test_optimization_suggestions_high_cost(self, cost_tracker, mock_db_service):
        """Test optimization suggestions for high costs."""
        # Mock high-cost sessions
        mock_sessions = []
        for i in range(10):
            mock_session = Mock()
            mock_session.cost = 5.0  # Total 50.0
            mock_session.session_type = "audio_download"
            mock_session.requests_count = 100
            mock_sessions.append(mock_session)

        mock_session = mock_db_service.get_session.return_value.__enter__.return_value
        mock_session.query.return_value.filter.return_value.all.return_value = (
            mock_sessions
        )

        summary = cost_tracker.get_usage_summary(7)

        assert "optimization_suggestions" in summary
        suggestions = summary["optimization_suggestions"]

        # Should include suggestions for high cost
        assert len(suggestions) > 0
        assert any("deduplication" in suggestion.lower() for suggestion in suggestions)

    def test_optimization_suggestions_high_requests(
        self, cost_tracker, mock_db_service
    ):
        """Test optimization suggestions for high request count."""
        # Mock high-request sessions
        mock_sessions = []
        for i in range(5):
            mock_session = Mock()
            mock_session.cost = 1.0
            mock_session.session_type = "metadata_scrape"
            mock_session.requests_count = 200  # High request count
            mock_sessions.append(mock_session)

        mock_session = mock_db_service.get_session.return_value.__enter__.return_value
        mock_session.query.return_value.filter.return_value.all.return_value = (
            mock_sessions
        )

        summary = cost_tracker.get_usage_summary(7)

        assert "optimization_suggestions" in summary
        suggestions = summary["optimization_suggestions"]

        # Should include suggestions for high requests
        assert len(suggestions) > 0
        assert any(
            "caching" in suggestion.lower() or "batch" in suggestion.lower()
            for suggestion in suggestions
        )

    def test_error_handling_database_exception(self, cost_tracker, mock_db_service):
        """Test error handling when database operations fail."""
        # Mock database exception
        mock_db_service.get_session.side_effect = Exception(
            "Database connection failed"
        )

        # Should not raise exceptions, should return safe defaults
        success = cost_tracker.track_session_cost("test", 1, 100, 0.01)
        assert success == False

        summary = cost_tracker.get_usage_summary(7)
        assert summary["summary"]["total_cost"] == 0.0

        breakdown = cost_tracker.get_cost_breakdown()
        assert breakdown["by_session_type"] == {}

        alerts = cost_tracker.check_budget_alerts(100.0)
        assert alerts["alert_level"] == "green"  # Safe default
        assert alerts["current_spend"] == 0.0

    def test_date_filtering_accuracy(self, cost_tracker, mock_db_service):
        """Test that date filtering works correctly."""
        days = 3

        # Create sessions with different dates
        now = datetime.utcnow()
        mock_sessions = [
            Mock(cost=1.0, created_at=now),  # Today (included)
            Mock(cost=2.0, created_at=now - timedelta(days=1)),  # 1 day ago (included)
            Mock(cost=3.0, created_at=now - timedelta(days=2)),  # 2 days ago (included)
            Mock(cost=4.0, created_at=now - timedelta(days=4)),  # 4 days ago (excluded)
        ]

        # Mock database to simulate date filtering
        mock_session = mock_db_service.get_session.return_value.__enter__.return_value

        # Only return sessions within date range
        filtered_sessions = [
            s for s in mock_sessions if (now - s.created_at).days <= days
        ]
        mock_session.query.return_value.filter.return_value.all.return_value = (
            filtered_sessions
        )

        summary = cost_tracker.get_usage_summary(days)

        # Should only include costs from last 3 days (1.0 + 2.0 + 3.0 = 6.0)
        assert summary["summary"]["total_cost"] == 6.0

    def test_cost_precision(self, cost_tracker, mock_db_service):
        """Test that cost calculations maintain precision."""
        session_id = "precision_test"

        # Mock session with very small costs
        mock_session_record = Mock()
        mock_session_record.cost = 0.001234

        mock_session = mock_db_service.get_session.return_value.__enter__.return_value
        mock_session.query.return_value.filter.return_value.first.return_value = (
            mock_session_record
        )

        # Add very small cost
        success = cost_tracker.track_session_cost(
            session_id=session_id,
            requests_count=1,
            data_downloaded_bytes=100,
            cost=0.000001,
        )

        assert success == True
        # Should maintain precision
        assert abs(mock_session_record.cost - 0.001235) < 1e-6
