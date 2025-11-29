"""
Queue Tab

Displays real-time status of all input documents in the processing pipeline.
"""

from datetime import datetime
from typing import Any, Optional

from PyQt6.QtCore import QModelIndex, Qt, QTimer, QUrl, pyqtSlot
from PyQt6.QtGui import QColor, QDesktopServices
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...database.service import DatabaseService
from ...services.queue_snapshot_service import QueueSnapshot, QueueSnapshotService
from ..components.base_tab import BaseTab
from ..queue_event_bus import QueueEvent, get_queue_event_bus

# Status colors
STATUS_COLORS = {
    "pending": QColor(200, 200, 200),
    "queued": QColor(255, 230, 150),
    "scheduled": QColor(150, 200, 255),
    "in_progress": QColor(150, 255, 150),
    "completed": QColor(100, 200, 100),
    "failed": QColor(255, 150, 150),
    "blocked": QColor(255, 180, 100),
    "not_applicable": QColor(220, 220, 220),
    "skipped": QColor(240, 240, 240),
}

# Stage display names
STAGE_NAMES = {
    "download": "Download",
    "transcription": "Transcription",
    "summarization": "Summarization",
    "hce_mining": "HCE Mining",
    "flagship_evaluation": "Flagship Eval",
}


class QueueTab(BaseTab):
    """Tab for displaying and managing the processing queue."""

    def __init__(self, *args, **kwargs):
        # Initialize attributes BEFORE calling parent constructor
        # Services
        self.db_service = DatabaseService()
        self.snapshot_service = QueueSnapshotService(self.db_service)
        self.event_bus = get_queue_event_bus()

        # Get settings manager
        from ..core.settings_manager import get_gui_settings_manager

        self.gui_settings = get_gui_settings_manager()

        # State
        self.current_page = 0
        self.page_size = 50
        self.status_filter = []
        self.stage_filter = []
        self.search_text = ""
        self._last_refresh_interval = None  # Track refresh interval changes

        # Initialize UI elements that might be accessed by _connect_signals
        self.queue_table = None
        self.status_combo = None
        self.stage_combo = None
        self.search_box = None
        self.refresh_timer = None

        # Call parent constructor (which calls _setup_ui and _connect_signals)
        super().__init__(*args, **kwargs)

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout()

        # Header with summary stats
        header_layout = QHBoxLayout()

        self.stats_label = QLabel("Loading queue statistics...")
        header_layout.addWidget(self.stats_label)
        header_layout.addStretch()

        # Refresh button
        self.refresh_button = QPushButton("🔄 Refresh")
        self.refresh_button.clicked.connect(self._refresh_queue)
        header_layout.addWidget(self.refresh_button)

        layout.addLayout(header_layout)

        # Filter controls
        filter_layout = QHBoxLayout()

        # Stage filter
        filter_layout.addWidget(QLabel("Stage:"))
        self.stage_combo = QComboBox()
        self.stage_combo.addItem("All Stages", None)
        for stage, name in STAGE_NAMES.items():
            self.stage_combo.addItem(name, stage)
        self.stage_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.stage_combo)

        # Status filter
        filter_layout.addWidget(QLabel("Status:"))
        self.status_combo = QComboBox()
        self.status_combo.addItem("All Statuses", None)
        self.status_combo.addItem("Active Only", "active_only")  # Special filter
        for status in STATUS_COLORS:
            self.status_combo.addItem(status.title(), status)
        self.status_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.status_combo)

        # Search box
        filter_layout.addWidget(QLabel("Search:"))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Filter by title or URL...")
        self.search_box.textChanged.connect(self._on_search_changed)
        filter_layout.addWidget(self.search_box)

        # Queue refresh interval
        filter_layout.addWidget(QLabel("Refresh:"))
        self.refresh_interval_spin = QSpinBox()
        self.refresh_interval_spin.setRange(1, 60)
        self.refresh_interval_spin.setSuffix("s")
        self.refresh_interval_spin.setToolTip(
            "How often the queue refreshes automatically.\n"
            "• Lower values: More responsive but higher CPU usage\n"
            "• Higher values: Less CPU usage but delayed updates\n"
            "• Recommended: 5-10 seconds"
        )
        # Load saved value
        saved_interval = self.gui_settings.get_value(
            "Processing", "queue_refresh_interval", 5
        )
        self.refresh_interval_spin.setValue(saved_interval)
        # Connect to update timer when changed
        self.refresh_interval_spin.valueChanged.connect(self._on_refresh_interval_changed)
        filter_layout.addWidget(self.refresh_interval_spin)

        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Queue table
        self.queue_table = QTableWidget()
        self._setup_table()
        layout.addWidget(self.queue_table)

        # Pagination controls
        pagination_layout = QHBoxLayout()

        self.prev_button = QPushButton("← Previous")
        self.prev_button.clicked.connect(self._previous_page)
        pagination_layout.addWidget(self.prev_button)

        self.page_label = QLabel("Page 1 of 1")
        pagination_layout.addWidget(self.page_label)

        self.next_button = QPushButton("Next →")
        self.next_button.clicked.connect(self._next_page)
        pagination_layout.addWidget(self.next_button)

        pagination_layout.addStretch()
        layout.addLayout(pagination_layout)

        self.setLayout(layout)

        # Additional setup after UI is created
        self._load_preferences()
        self._setup_refresh_timer()

        # Initial load
        QTimer.singleShot(
            100, self._refresh_queue
        )  # Slight delay to ensure UI is ready

    def _setup_table(self):
        """Configure the queue table."""
        # Column setup
        columns = [
            "Title",
            "URL",
            "Current Stage",
            "Status",
            "Progress",
            "Duration",
            "Worker",
            "Actions",
        ]
        self.queue_table.setColumnCount(len(columns))
        self.queue_table.setHorizontalHeaderLabels(columns)

        # Table settings
        self.queue_table.setAlternatingRowColors(True)
        self.queue_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.queue_table.horizontalHeader().setStretchLastSection(True)

        # Column widths
        self.queue_table.setColumnWidth(0, 300)  # Title
        self.queue_table.setColumnWidth(1, 200)  # URL
        self.queue_table.setColumnWidth(2, 120)  # Stage
        self.queue_table.setColumnWidth(3, 100)  # Status
        self.queue_table.setColumnWidth(4, 80)  # Progress
        self.queue_table.setColumnWidth(5, 100)  # Duration
        self.queue_table.setColumnWidth(6, 100)  # Worker

    def _connect_signals(self):
        """Connect to event bus signals."""
        # Connect to event bus
        if hasattr(self, "event_bus") and self.event_bus:
            self.event_bus.stage_status_changed.connect(self._on_stage_status_changed)
            self.event_bus.batch_progress.connect(self._on_batch_progress)
            self.event_bus.error_occurred.connect(self._on_error_occurred)

        # Connect row double-click to show details
        if hasattr(self, "queue_table") and self.queue_table:
            self.queue_table.cellDoubleClicked.connect(self._on_row_double_clicked)

    def _setup_refresh_timer(self):
        """Set up automatic refresh timer."""
        from ..core.settings_manager import get_gui_settings_manager

        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._refresh_queue)

        # Get refresh interval from settings
        gui_settings = get_gui_settings_manager()
        refresh_interval = gui_settings.get_value(
            "Processing", "queue_refresh_interval", 5
        )
        self.refresh_timer.start(refresh_interval * 1000)  # Convert to milliseconds

        # Update timer when settings change
        self._last_refresh_interval = refresh_interval

    def _on_refresh_interval_changed(self, value: int):
        """Handle refresh interval change from the spinbox."""
        # Save to settings
        self.gui_settings.set_value("Processing", "queue_refresh_interval", value)
        
        # Update timer immediately
        if hasattr(self, "refresh_timer") and self.refresh_timer is not None:
            self.refresh_timer.stop()
            self.refresh_timer.start(value * 1000)
            self._last_refresh_interval = value
            self.log_message(
                f"Queue refresh interval updated to {value} seconds"
            )

    def _check_refresh_interval(self):
        """Check if refresh interval has changed in settings."""
        # Skip if timer not yet initialized
        if not hasattr(self, "refresh_timer") or self.refresh_timer is None:
            return

        from ..core.settings_manager import get_gui_settings_manager

        gui_settings = get_gui_settings_manager()
        current_interval = gui_settings.get_value(
            "Processing", "queue_refresh_interval", 5
        )

        if current_interval != self._last_refresh_interval:
            # Restart timer with new interval
            self.refresh_timer.stop()
            self.refresh_timer.start(current_interval * 1000)
            self._last_refresh_interval = current_interval
            # Update spinbox if it exists
            if hasattr(self, "refresh_interval_spin") and self.refresh_interval_spin:
                self.refresh_interval_spin.blockSignals(True)
                self.refresh_interval_spin.setValue(current_interval)
                self.refresh_interval_spin.blockSignals(False)
            self.log_message(
                f"Queue refresh interval updated to {current_interval} seconds"
            )

    def _refresh_queue(self):
        """Refresh the queue display."""
        # Check if refresh interval changed
        self._check_refresh_interval()

        try:
            # Apply filters
            status_filter = []
            current_status = self.status_combo.currentData()

            if current_status == "active_only":
                # Special filter: exclude completed and old failed items
                status_filter = [
                    "pending",
                    "queued",
                    "scheduled",
                    "in_progress",
                    "blocked",
                ]
            elif current_status:
                status_filter.append(current_status)

            stage_filter = []
            if self.stage_combo.currentData():
                stage_filter.append(self.stage_combo.currentData())

            # Get queue data
            snapshots, total = self.snapshot_service.get_full_queue(
                status_filter=status_filter,
                stage_filter=stage_filter,
                limit=self.page_size,
                offset=self.current_page * self.page_size,
            )

            # Update table
            self._update_table(snapshots)

            # Update pagination
            total_pages = (total + self.page_size - 1) // self.page_size
            self.page_label.setText(f"Page {self.current_page + 1} of {total_pages}")
            self.prev_button.setEnabled(self.current_page > 0)
            self.next_button.setEnabled(self.current_page < total_pages - 1)

            # Update statistics
            self._update_stats()

        except Exception as e:
            self.append_log(f"❌ Failed to refresh queue: {e}")

    def _update_table(self, snapshots: list[QueueSnapshot]):
        """Update table with snapshot data."""
        self.queue_table.setRowCount(len(snapshots))

        for row, snapshot in enumerate(snapshots):
            # Title
            title_item = QTableWidgetItem(snapshot.title or "")
            self.queue_table.setItem(row, 0, title_item)

            # URL (truncated)
            url_text = snapshot.url or ""
            if len(url_text) > 50:
                url_text = url_text[:47] + "..."
            url_item = QTableWidgetItem(url_text)
            self.queue_table.setItem(row, 1, url_item)

            # Current stage
            stage_text = STAGE_NAMES.get(
                snapshot.current_stage, snapshot.current_stage or "—"
            )
            stage_item = QTableWidgetItem(stage_text)
            self.queue_table.setItem(row, 2, stage_item)

            # Status
            status_item = QTableWidgetItem(snapshot.overall_status.title())
            if snapshot.overall_status in STATUS_COLORS:
                status_item.setBackground(STATUS_COLORS[snapshot.overall_status])
            self.queue_table.setItem(row, 3, status_item)

            # Progress
            if (
                snapshot.current_stage
                and snapshot.current_stage in snapshot.stage_statuses
            ):
                progress = snapshot.stage_statuses[
                    snapshot.current_stage
                ].progress_percent
                progress_text = f"{progress:.0f}%"
            else:
                progress_text = "—"
            progress_item = QTableWidgetItem(progress_text)
            self.queue_table.setItem(row, 4, progress_item)

            # Duration
            if snapshot.elapsed_time:
                duration_text = str(snapshot.elapsed_time).split(".")[0]
            else:
                duration_text = "—"
            duration_item = QTableWidgetItem(duration_text)
            self.queue_table.setItem(row, 5, duration_item)

            # Worker
            worker_text = "—"
            if (
                snapshot.current_stage
                and snapshot.current_stage in snapshot.stage_statuses
            ):
                worker = snapshot.stage_statuses[snapshot.current_stage].assigned_worker
                if worker:
                    worker_text = worker
            worker_item = QTableWidgetItem(worker_text)
            self.queue_table.setItem(row, 6, worker_item)

            # Actions - show link to file if completed, otherwise "View Details"
            actions_text = "View Details"
            file_path = None

            # Check if there's a completed summary file
            if snapshot.overall_status == "completed":
                file_path = self._get_output_file_path(snapshot.source_id)
                if file_path:
                    actions_text = "📄 Open File"

            actions_item = QTableWidgetItem(actions_text)
            actions_item.setData(Qt.ItemDataRole.UserRole, snapshot.source_id)
            actions_item.setData(
                Qt.ItemDataRole.UserRole + 1, file_path
            )  # Store file path

            # Make it look clickable if there's a file
            if file_path:
                actions_item.setForeground(QColor(0, 100, 200))  # Blue color

            self.queue_table.setItem(row, 7, actions_item)

    def _update_stats(self):
        """Update summary statistics."""
        try:
            summary = self.snapshot_service.get_stage_summary()
            metrics = self.snapshot_service.get_throughput_metrics()

            # Count items by status
            total_items = 0
            in_progress = 0
            completed = 0
            failed = 0

            for stage_stats in summary.values():
                for status, count in stage_stats.items():
                    total_items += count
                    if status == "in_progress":
                        in_progress += count
                    elif status == "completed":
                        completed += count
                    elif status == "failed":
                        failed += count

            # Format stats text
            stats_text = (
                f"Total: {total_items} | "
                f"In Progress: {in_progress} | "
                f"Completed: {completed} | "
                f"Failed: {failed} | "
                f"Rate: {metrics.get('average_items_per_hour', 0):.1f}/hr"
            )

            self.stats_label.setText(stats_text)

        except Exception as e:
            self.append_log(f"❌ Failed to update stats: {e}")

    @pyqtSlot(QueueEvent)
    def _on_stage_status_changed(self, event: QueueEvent):
        """Handle stage status change event."""
        # Refresh the table to show the update
        # For efficiency, we could update just the affected row
        self._refresh_queue()

    @pyqtSlot(int, int)
    def _on_batch_progress(self, completed: int, total: int):
        """Handle batch progress update."""
        # Could show a progress bar or update stats
        pass

    @pyqtSlot(str, str, str)
    def _on_error_occurred(self, source_id: str, stage: str, error: str):
        """Handle error notification."""
        self.append_log(f"❌ Error in {stage} for {source_id}: {error}")

    def _on_filter_changed(self):
        """Handle filter change."""
        self.current_page = 0  # Reset to first page
        self._refresh_queue()

        # Save filter preferences
        self._save_preferences()

    def _on_search_changed(self, text: str):
        """Handle search text change."""
        self.search_text = text
        self.current_page = 0  # Reset to first page
        # TODO: Implement search filtering
        self._refresh_queue()

    def _on_row_double_clicked(self, row: int, column: int):
        """Handle row double-click."""
        # Get source_id and file_path from the actions column
        actions_item = self.queue_table.item(row, 7)
        if actions_item:
            source_id = actions_item.data(Qt.ItemDataRole.UserRole)
            file_path = actions_item.data(Qt.ItemDataRole.UserRole + 1)

            # If there's a file path and user clicked actions column, open the file
            if file_path and column == 7:
                self._open_file(file_path)
            elif source_id:
                self._show_source_details(source_id)

    def _show_source_details(self, source_id: str):
        """Show detailed information for a source."""
        from ..dialogs.queue_detail_dialog import QueueDetailDialog

        dialog = QueueDetailDialog(source_id, self)
        dialog.exec()

    def _get_output_file_path(self, source_id: str) -> str | None:
        """Get the path to the output markdown file for a completed source."""
        try:
            from pathlib import Path

            with self.db_service.get_session() as session:
                from ...database.models import GeneratedFile

                # Look for summary markdown file
                generated_file = (
                    session.query(GeneratedFile)
                    .filter(
                        GeneratedFile.source_id == source_id,
                        GeneratedFile.file_type == "summary_md",
                    )
                    .order_by(GeneratedFile.created_at.desc())
                    .first()
                )

                if generated_file and generated_file.file_path:
                    file_path = Path(generated_file.file_path)
                    if file_path.exists():
                        return str(file_path)

            return None

        except Exception as e:
            self.append_log(f"❌ Failed to get output file path: {e}")
            return None

    def _open_file(self, file_path: str):
        """Open a file with the system default application."""
        try:
            from pathlib import Path

            path = Path(file_path)
            if not path.exists():
                self.append_log(f"❌ File not found: {file_path}")
                return

            # Open with system default application
            url = QUrl.fromLocalFile(str(path.absolute()))
            QDesktopServices.openUrl(url)
            self.append_log(f"✅ Opened file: {path.name}")

        except Exception as e:
            self.append_log(f"❌ Failed to open file: {e}")

    def _previous_page(self):
        """Go to previous page."""
        if self.current_page > 0:
            self.current_page -= 1
            self._refresh_queue()

    def _next_page(self):
        """Go to next page."""
        self.current_page += 1
        self._refresh_queue()

    def _load_preferences(self):
        """Load saved preferences from settings."""
        # Load filter preferences
        saved_status = self.gui_settings.get_value(
            "QueueTab", "status_filter", "active_only"
        )  # Default to "Active Only"
        if saved_status and hasattr(self, "status_combo"):
            index = self.status_combo.findData(saved_status)
            if index >= 0:
                self.status_combo.setCurrentIndex(index)

        saved_stage = self.gui_settings.get_value("QueueTab", "stage_filter", "")
        if saved_stage and hasattr(self, "stage_combo"):
            index = self.stage_combo.findData(saved_stage)
            if index >= 0:
                self.stage_combo.setCurrentIndex(index)

        # Load page size preference
        saved_page_size = self.gui_settings.get_value("QueueTab", "page_size", 50)
        self.page_size = saved_page_size

    def _save_preferences(self):
        """Save current preferences to settings."""
        # Save filter preferences
        if hasattr(self, "status_combo"):
            status_value = self.status_combo.currentData()
            self.gui_settings.set_value("QueueTab", "status_filter", status_value or "")

        if hasattr(self, "stage_combo"):
            stage_value = self.stage_combo.currentData()
            self.gui_settings.set_value("QueueTab", "stage_filter", stage_value or "")

        # Save page size
        self.gui_settings.set_value("QueueTab", "page_size", self.page_size)

        # Persist to disk
        self.gui_settings.save()

    def cleanup(self):
        """Clean up resources."""
        self.refresh_timer.stop()

        # Save preferences on cleanup
        self._save_preferences()

        super().cleanup()
