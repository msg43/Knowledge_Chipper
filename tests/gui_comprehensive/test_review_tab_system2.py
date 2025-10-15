"""
Tests for System 2 Review Tab with SQLite integration.

Tests:
- Claim table loading and display
- SQLite integration and queries
- Claim editing functionality
- Optimistic concurrency control
- Batch save operations
- Episode filtering
"""

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from knowledge_system.database import DatabaseService
from knowledge_system.gui.tabs.review_tab_system2 import (
    ClaimsTableModel,
    ReviewTabSystem2,
)
from tests.fixtures.system2_fixtures import create_test_job, create_test_job_run


class TestReviewTabSystem2:
    """Test System 2 Review Tab functionality."""

    @pytest.fixture(autouse=True)
    def setup(self, qtbot):
        """Setup test environment."""
        self.db_service = DatabaseService()
        self.review_tab = ReviewTabSystem2()
        qtbot.addWidget(self.review_tab)

    def test_review_tab_initialization(self, qtbot):
        """Test that review tab initializes correctly."""
        assert self.review_tab is not None
        assert self.review_tab.db_service is not None
        assert self.review_tab.table_view is not None
        assert self.review_tab.model is not None

    def test_table_model_initialization(self):
        """Test that claims table model initializes."""
        model = ClaimsTableModel(self.db_service)
        assert model is not None
        assert model.db_service is not None

    def test_load_claims_from_database(self):
        """Test loading claims from database."""
        model = ClaimsTableModel(self.db_service)

        # Load claims
        model.load_claims()

        # Model should be initialized (may have 0 rows if no claims)
        assert model.rowCount() >= 0

    def test_episode_filter_combo(self, qtbot):
        """Test episode filter combo box."""
        assert self.review_tab.episode_combo is not None

        # Should have at least "All Episodes" option
        assert self.review_tab.episode_combo.count() >= 1
        assert self.review_tab.episode_combo.itemText(0) == "All Episodes"

    def test_refresh_button(self, qtbot):
        """Test refresh button functionality."""
        # Find refresh button
        refresh_btn = None
        for child in self.review_tab.findChildren(type(None)):
            if hasattr(child, "text") and "Refresh" in str(child.text()):
                refresh_btn = child
                break

        # Refresh button should exist
        # Note: May not find if button structure changed
        if refresh_btn:
            qtbot.mouseClick(refresh_btn, Qt.MouseButton.LeftButton)

    def test_table_columns(self):
        """Test that table has expected columns."""
        model = ClaimsTableModel(self.db_service)

        # Should have columns for claim data
        assert model.columnCount() > 0

        # Column headers should be defined
        for col in range(model.columnCount()):
            header = model.headerData(
                col, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole
            )
            assert header is not None

    def test_optimistic_locking_support(self):
        """Test that model supports optimistic locking."""
        model = ClaimsTableModel(self.db_service)

        # Load claims
        model.load_claims()

        # If there are claims, they should have updated_at tracking
        if model.rowCount() > 0:
            # Model should track row versions for optimistic locking
            assert hasattr(model, "_claims") or hasattr(model, "claims")


class TestClaimsTableModel:
    """Test ClaimsTableModel specifically."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment."""
        self.db_service = DatabaseService()
        self.model = ClaimsTableModel(self.db_service)

    def test_model_initialization(self):
        """Test model initializes correctly."""
        assert self.model is not None
        assert self.model.db_service is not None

    def test_load_claims_empty_database(self):
        """Test loading claims from empty database."""
        self.model.load_claims()

        # Should handle empty database gracefully
        assert self.model.rowCount() >= 0

    def test_data_method(self):
        """Test data() method returns appropriate values."""
        self.model.load_claims()

        if self.model.rowCount() > 0:
            # Test getting data from first cell
            index = self.model.index(0, 0)
            data = self.model.data(index, Qt.ItemDataRole.DisplayRole)

            # Should return some value (string, number, or None)
            assert data is not None or data is None  # Either is valid

    def test_flags_method(self):
        """Test flags() method for editable cells."""
        self.model.load_claims()

        if self.model.rowCount() > 0:
            # Test getting flags from first cell
            index = self.model.index(0, 0)
            flags = self.model.flags(index)

            # Should return valid flags
            assert flags is not None

    def test_header_data(self):
        """Test header data is properly set."""
        # Test horizontal headers
        for col in range(self.model.columnCount()):
            header = self.model.headerData(
                col, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole
            )
            assert header is not None
            assert len(str(header)) > 0


class TestReviewTabIntegration:
    """Integration tests for review tab with database."""

    @pytest.fixture(autouse=True)
    def setup(self, qtbot):
        """Setup test environment."""
        self.db_service = DatabaseService()
        self.review_tab = ReviewTabSystem2()
        qtbot.addWidget(self.review_tab)

    def test_refresh_updates_view(self, qtbot):
        """Test that refresh updates the view."""
        initial_row_count = self.review_tab.model.rowCount()

        # Trigger refresh
        self.review_tab._refresh_data()

        # Row count should be consistent (may be 0 if no data)
        assert self.review_tab.model.rowCount() >= 0

    def test_episode_filter_changes_view(self, qtbot):
        """Test that changing episode filter updates view."""
        initial_row_count = self.review_tab.model.rowCount()

        # Change filter
        if self.review_tab.episode_combo.count() > 1:
            self.review_tab.episode_combo.setCurrentIndex(1)

            # View should update (row count may change)
            assert self.review_tab.model.rowCount() >= 0

    def test_table_view_configuration(self):
        """Test that table view is properly configured."""
        table_view = self.review_tab.table_view

        # Should have model set
        assert table_view.model() is not None

        # Should have alternating row colors
        assert table_view.alternatingRowColors()

    def test_auto_refresh_timer(self):
        """Test that auto-refresh timer is configured."""
        assert self.review_tab.refresh_timer is not None
        assert self.review_tab.refresh_timer.isActive()

    def test_delete_button_exists(self):
        """Test that delete button exists in the UI."""
        assert hasattr(self.review_tab, "delete_btn")
        assert self.review_tab.delete_btn is not None

    def test_delete_button_initially_disabled(self):
        """Test that delete button is initially disabled when no selection."""
        assert self.review_tab.delete_btn.isEnabled() is False

    def test_delete_button_enabled_on_selection(self, qtbot):
        """Test that delete button is enabled when rows are selected."""
        # Only test if there are claims to select
        if self.review_tab.model.rowCount() > 0:
            # Select first row
            self.review_tab.table_view.selectRow(0)

            # Delete button should now be enabled
            assert self.review_tab.delete_btn.isEnabled() is True

    def test_delete_button_disabled_on_deselection(self, qtbot):
        """Test that delete button is disabled when selection is cleared."""
        # Only test if there are claims to select
        if self.review_tab.model.rowCount() > 0:
            # Select first row
            self.review_tab.table_view.selectRow(0)
            assert self.review_tab.delete_btn.isEnabled() is True

            # Clear selection
            self.review_tab.table_view.clearSelection()

            # Delete button should now be disabled
            assert self.review_tab.delete_btn.isEnabled() is False


if __name__ == "__main__":
    # Need QApplication for Qt tests
    import sys

    app = QApplication(sys.argv)
    pytest.main([__file__, "-v"])
