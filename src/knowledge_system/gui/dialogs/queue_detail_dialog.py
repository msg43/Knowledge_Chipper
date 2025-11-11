"""Queue Detail Dialog - Shows comprehensive stage history and metadata for a source."""

from datetime import datetime
from typing import Any, Dict, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...database.service import DatabaseService
from ...services.queue_snapshot_service import QueueSnapshotService


class QueueDetailDialog(QDialog):
    """Dialog showing detailed stage history and metadata for a queue item."""

    def __init__(self, source_id: str, parent=None):
        super().__init__(parent)
        self.source_id = source_id
        self.db_service = DatabaseService()
        self.queue_service = QueueSnapshotService(self.db_service)

        self.setWindowTitle(f"Queue Details - {source_id}")
        self.setModal(True)
        self.resize(800, 600)

        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        """Initialize the UI components."""
        layout = QVBoxLayout(self)

        # Header with source info
        header_group = QGroupBox("Source Information")
        header_layout = QVBoxLayout()

        self.title_label = QLabel()
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        header_layout.addWidget(self.title_label)

        self.source_info_label = QLabel()
        header_layout.addWidget(self.source_info_label)

        header_group.setLayout(header_layout)
        layout.addWidget(header_group)

        # Main content splitter
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Stage timeline table
        timeline_group = QGroupBox("Stage Timeline")
        timeline_layout = QVBoxLayout()

        self.timeline_table = QTableWidget()
        self.timeline_table.setColumnCount(6)
        self.timeline_table.setHorizontalHeaderLabels(
            ["Stage", "Status", "Started", "Completed", "Duration", "Progress"]
        )
        self.timeline_table.horizontalHeader().setStretchLastSection(True)
        self.timeline_table.setAlternatingRowColors(True)
        self.timeline_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.timeline_table.currentItemChanged.connect(self._on_stage_selected)

        timeline_layout.addWidget(self.timeline_table)
        timeline_group.setLayout(timeline_layout)
        splitter.addWidget(timeline_group)

        # Stage metadata viewer
        metadata_group = QGroupBox("Stage Metadata")
        metadata_layout = QVBoxLayout()

        self.metadata_text = QTextEdit()
        self.metadata_text.setReadOnly(True)
        self.metadata_text.setStyleSheet("font-family: monospace;")

        metadata_layout.addWidget(self.metadata_text)
        metadata_group.setLayout(metadata_layout)
        splitter.addWidget(metadata_group)

        layout.addWidget(splitter)

        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self._load_data)
        button_layout.addWidget(self.refresh_button)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)

    def _load_data(self):
        """Load source and stage data."""
        try:
            # Get source timeline
            timeline = self.queue_service.get_source_timeline(self.source_id)

            if not timeline:
                self.title_label.setText("Source Not Found")
                self.source_info_label.setText(f"Source ID: {self.source_id}")
                return

            # Update header
            media_source = timeline.get("media_source", {})
            title = media_source.get("title", "Untitled")
            source_type = media_source.get("source_type", "Unknown")
            created = media_source.get("created_at", "")

            self.title_label.setText(title)
            self.source_info_label.setText(
                f"ID: {self.source_id} | Type: {source_type} | Created: {created}"
            )

            # Update timeline table
            stages = timeline.get("stages", [])
            self.timeline_table.setRowCount(len(stages))

            for i, stage in enumerate(stages):
                # Stage name
                stage_item = QTableWidgetItem(stage.get("stage", ""))
                self.timeline_table.setItem(i, 0, stage_item)

                # Status with color
                status = stage.get("status", "pending")
                status_item = QTableWidgetItem(status.upper())
                status_color = self._get_status_color(status)
                status_item.setForeground(status_color)
                self.timeline_table.setItem(i, 1, status_item)

                # Started time
                started = stage.get("started_at", "")
                if started:
                    started = self._format_datetime(started)
                self.timeline_table.setItem(i, 2, QTableWidgetItem(started))

                # Completed time
                completed = stage.get("completed_at", "")
                if completed:
                    completed = self._format_datetime(completed)
                self.timeline_table.setItem(i, 3, QTableWidgetItem(completed))

                # Duration
                duration = stage.get("duration_seconds")
                if duration is not None:
                    duration_str = self._format_duration(duration)
                else:
                    duration_str = "-"
                self.timeline_table.setItem(i, 4, QTableWidgetItem(duration_str))

                # Progress
                progress = stage.get("progress_percent", 0)
                progress_str = f"{progress:.0f}%" if progress > 0 else "-"
                self.timeline_table.setItem(i, 5, QTableWidgetItem(progress_str))

                # Store metadata for selection
                self.timeline_table.item(i, 0).setData(Qt.ItemDataRole.UserRole, stage)

            # Auto-select first stage
            if stages:
                self.timeline_table.selectRow(0)

        except Exception as e:
            self.title_label.setText("Error Loading Data")
            self.source_info_label.setText(str(e))

    def _on_stage_selected(self, current, previous):
        """Handle stage selection to show metadata."""
        if not current:
            return

        row = current.row()
        stage_data = self.timeline_table.item(row, 0).data(Qt.ItemDataRole.UserRole)

        if not stage_data:
            return

        # Format metadata as JSON-like text
        metadata = stage_data.get("metadata", {})
        if metadata:
            import json

            metadata_str = json.dumps(metadata, indent=2, default=str)
        else:
            metadata_str = "No metadata available"

        # Add other stage details
        details = []
        details.append(f"Stage: {stage_data.get('stage', '')}")
        details.append(f"Status: {stage_data.get('status', '')}")
        details.append(f"Priority: {stage_data.get('priority', 5)}")

        if stage_data.get("assigned_worker"):
            details.append(f"Worker: {stage_data.get('assigned_worker')}")

        if stage_data.get("error_message"):
            details.append(f"\nError: {stage_data.get('error_message')}")

        details.append(f"\nMetadata:\n{metadata_str}")

        self.metadata_text.setText("\n".join(details))

    def _get_status_color(self, status: str):
        """Get color for status display."""
        from PyQt6.QtGui import QColor

        colors = {
            "completed": QColor(34, 139, 34),  # ForestGreen
            "in_progress": QColor(30, 144, 255),  # DodgerBlue
            "failed": QColor(220, 20, 60),  # Crimson
            "blocked": QColor(255, 140, 0),  # DarkOrange
            "queued": QColor(147, 112, 219),  # MediumPurple
            "scheduled": QColor(75, 0, 130),  # Indigo
            "skipped": QColor(128, 128, 128),  # Gray
            "not_applicable": QColor(169, 169, 169),  # DarkGray
        }

        return colors.get(status, QColor(0, 0, 0))

    def _format_datetime(self, dt_str: str) -> str:
        """Format datetime string for display."""
        try:
            if isinstance(dt_str, str):
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            else:
                dt = dt_str
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            return str(dt_str)

    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to human-readable string."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"
