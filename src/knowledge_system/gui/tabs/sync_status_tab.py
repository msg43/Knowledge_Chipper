"""
Sync Status Tab for Knowledge System GUI (PyQt6).

Provides interface for monitoring and managing cloud synchronization
with Supabase, including conflict resolution and sync history.
"""

import json
from typing import Dict, List, Optional
from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QThread
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QTreeWidget, QTreeWidgetItem,
    QTableWidget, QTableWidgetItem, QMessageBox,
    QProgressBar, QTextEdit, QComboBox
)
from PyQt6.QtGui import QColor, QFont

from ...services.supabase_sync import (
    SupabaseSyncService, SyncStatus, ConflictResolution,
    SyncResult, SyncConflict
)
from ...logger import get_logger
from ...config import get_settings

logger = get_logger(__name__)


class SyncWorker(QThread):
    """Worker thread for sync operations."""
    
    progress = pyqtSignal(str, int)  # message, percentage
    finished = pyqtSignal(SyncResult)
    error = pyqtSignal(str)
    
    def __init__(self, sync_service: SupabaseSyncService, 
                 table: Optional[str] = None,
                 conflict_resolution: ConflictResolution = ConflictResolution.MANUAL):
        super().__init__()
        self.sync_service = sync_service
        self.table = table
        self.conflict_resolution = conflict_resolution
    
    def run(self):
        """Run the sync operation."""
        try:
            if self.table:
                self.progress.emit(f"Syncing {self.table}...", 0)
                result = self.sync_service.sync_table(self.table, self.conflict_resolution)
            else:
                self.progress.emit("Starting full sync...", 0)
                result = self.sync_service.sync_all(self.conflict_resolution)
            
            self.finished.emit(result)
            
        except Exception as e:
            logger.error(f"Sync error: {e}")
            self.error.emit(str(e))


class SyncStatusTab(QWidget):
    """Tab for managing cloud synchronization."""
    
    status_update = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.sync_service = SupabaseSyncService()
        self.sync_worker: Optional[SyncWorker] = None
        self.conflicts: List[SyncConflict] = []
        
        self.setup_ui()
        self.refresh_status()
        
        # Auto-refresh timer
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_status)
        self.refresh_timer.start(30000)  # Refresh every 30 seconds
    
    def setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        
        # Header with sync controls
        header_layout = QHBoxLayout()
        
        title_label = QLabel("Cloud Sync Status")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Sync configuration status
        if self.sync_service.is_configured():
            config_label = QLabel("✅ Supabase Configured")
            config_label.setStyleSheet("color: #4CAF50;")
        else:
            config_label = QLabel("❌ Supabase Not Configured")
            config_label.setStyleSheet("color: #F44336;")
        header_layout.addWidget(config_label)
        
        # Sync buttons
        self.sync_all_btn = QPushButton("Sync All")
        self.sync_all_btn.clicked.connect(self.sync_all)
        self.sync_all_btn.setEnabled(self.sync_service.is_configured())
        header_layout.addWidget(self.sync_all_btn)
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_status)
        header_layout.addWidget(self.refresh_btn)
        
        layout.addLayout(header_layout)
        
        # Main content area
        content_layout = QHBoxLayout()
        
        # Left: Table sync status
        self.create_table_status_panel(content_layout)
        
        # Right: Sync details and conflicts
        self.create_details_panel(content_layout)
        
        layout.addLayout(content_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Status message
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)
    
    def create_table_status_panel(self, parent_layout):
        """Create panel showing sync status for each table."""
        group = QGroupBox("Table Sync Status")
        layout = QVBoxLayout(group)
        
        # Table status tree
        self.table_tree = QTreeWidget()
        self.table_tree.setHeaderLabels([
            "Table", "Total", "Synced", "Pending", "Conflicts", "Errors"
        ])
        
        # Set column widths
        for i in range(6):
            self.table_tree.setColumnWidth(i, 100)
        
        layout.addWidget(self.table_tree)
        
        # Table controls
        controls_layout = QHBoxLayout()
        
        self.sync_table_btn = QPushButton("Sync Selected Table")
        self.sync_table_btn.clicked.connect(self.sync_selected_table)
        self.sync_table_btn.setEnabled(False)
        controls_layout.addWidget(self.sync_table_btn)
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        parent_layout.addWidget(group, stretch=1)
        
        # Connect selection change
        self.table_tree.itemSelectionChanged.connect(self.on_table_selected)
    
    def create_details_panel(self, parent_layout):
        """Create panel showing sync details and conflicts."""
        right_layout = QVBoxLayout()
        
        # Conflict resolution settings
        settings_group = QGroupBox("Conflict Resolution")
        settings_layout = QVBoxLayout(settings_group)
        
        resolution_layout = QHBoxLayout()
        resolution_layout.addWidget(QLabel("Default Resolution:"))
        
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems([
            "Manual", "Local Wins", "Remote Wins", "Merge"
        ])
        resolution_layout.addWidget(self.resolution_combo)
        
        settings_layout.addLayout(resolution_layout)
        right_layout.addWidget(settings_group)
        
        # Conflicts panel
        conflicts_group = QGroupBox("Sync Conflicts")
        conflicts_layout = QVBoxLayout(conflicts_group)
        
        self.conflicts_table = QTableWidget()
        self.conflicts_table.setColumnCount(5)
        self.conflicts_table.setHorizontalHeaderLabels([
            "Table", "Record", "Type", "Local Updated", "Remote Updated"
        ])
        self.conflicts_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        conflicts_layout.addWidget(self.conflicts_table)
        
        # Conflict resolution buttons
        conflict_buttons = QHBoxLayout()
        
        self.use_local_btn = QPushButton("Use Local")
        self.use_local_btn.clicked.connect(lambda: self.resolve_conflict("local"))
        self.use_local_btn.setEnabled(False)
        conflict_buttons.addWidget(self.use_local_btn)
        
        self.use_remote_btn = QPushButton("Use Remote")
        self.use_remote_btn.clicked.connect(lambda: self.resolve_conflict("remote"))
        self.use_remote_btn.setEnabled(False)
        conflict_buttons.addWidget(self.use_remote_btn)
        
        self.view_diff_btn = QPushButton("View Diff")
        self.view_diff_btn.clicked.connect(self.view_conflict_diff)
        self.view_diff_btn.setEnabled(False)
        conflict_buttons.addWidget(self.view_diff_btn)
        
        conflicts_layout.addLayout(conflict_buttons)
        right_layout.addWidget(conflicts_group)
        
        # Sync log
        log_group = QGroupBox("Sync Log")
        log_layout = QVBoxLayout(log_group)
        
        self.sync_log = QTextEdit()
        self.sync_log.setReadOnly(True)
        self.sync_log.setMaximumHeight(150)
        log_layout.addWidget(self.sync_log)
        
        right_layout.addWidget(log_group)
        
        parent_layout.addLayout(right_layout, stretch=1)
        
        # Connect conflict selection
        self.conflicts_table.itemSelectionChanged.connect(self.on_conflict_selected)
    
    def refresh_status(self):
        """Refresh sync status for all tables."""
        if not self.sync_service.is_configured():
            self.status_label.setText("Supabase not configured")
            return
        
        try:
            status = self.sync_service.get_sync_status()
            self.update_table_tree(status)
            self.status_label.setText(f"Last refreshed: {datetime.now().strftime('%H:%M:%S')}")
            
        except Exception as e:
            logger.error(f"Failed to refresh status: {e}")
            self.status_label.setText(f"Error: {str(e)}")
    
    def update_table_tree(self, status: Dict[str, Dict[str, int]]):
        """Update the table tree with sync status."""
        self.table_tree.clear()
        
        total_synced = 0
        total_pending = 0
        total_conflicts = 0
        total_errors = 0
        
        for table, counts in status.items():
            item = QTreeWidgetItem([
                table,
                str(counts.get("total", 0)),
                str(counts.get("synced", 0)),
                str(counts.get("pending", 0)),
                str(counts.get("conflict", 0)),
                str(counts.get("error", 0))
            ])
            
            # Color code based on status
            if counts.get("conflict", 0) > 0:
                item.setForeground(0, QColor("#FF9800"))  # Orange for conflicts
            elif counts.get("error", 0) > 0:
                item.setForeground(0, QColor("#F44336"))  # Red for errors
            elif counts.get("pending", 0) > 0:
                item.setForeground(0, QColor("#2196F3"))  # Blue for pending
            else:
                item.setForeground(0, QColor("#4CAF50"))  # Green for synced
            
            self.table_tree.addTopLevelItem(item)
            
            # Accumulate totals
            total_synced += counts.get("synced", 0)
            total_pending += counts.get("pending", 0)
            total_conflicts += counts.get("conflict", 0)
            total_errors += counts.get("error", 0)
        
        # Update summary
        summary = f"Total: {total_synced} synced, {total_pending} pending"
        if total_conflicts > 0:
            summary += f", {total_conflicts} conflicts"
        if total_errors > 0:
            summary += f", {total_errors} errors"
        
        self.status_label.setText(summary)
    
    def on_table_selected(self):
        """Handle table selection."""
        selected = self.table_tree.selectedItems()
        self.sync_table_btn.setEnabled(bool(selected))
    
    def on_conflict_selected(self):
        """Handle conflict selection."""
        has_selection = bool(self.conflicts_table.selectedItems())
        self.use_local_btn.setEnabled(has_selection)
        self.use_remote_btn.setEnabled(has_selection)
        self.view_diff_btn.setEnabled(has_selection)
    
    def sync_all(self):
        """Start full sync operation."""
        if self.sync_worker and self.sync_worker.isRunning():
            QMessageBox.warning(self, "Sync in Progress", 
                              "A sync operation is already running")
            return
        
        # Get conflict resolution strategy
        resolution_map = {
            "Manual": ConflictResolution.MANUAL,
            "Local Wins": ConflictResolution.LOCAL_WINS,
            "Remote Wins": ConflictResolution.REMOTE_WINS,
            "Merge": ConflictResolution.MERGE
        }
        resolution = resolution_map.get(
            self.resolution_combo.currentText(),
            ConflictResolution.MANUAL
        )
        
        # Start sync worker
        self.sync_worker = SyncWorker(self.sync_service, None, resolution)
        self.sync_worker.progress.connect(self.on_sync_progress)
        self.sync_worker.finished.connect(self.on_sync_finished)
        self.sync_worker.error.connect(self.on_sync_error)
        
        self.sync_all_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.sync_worker.start()
    
    def sync_selected_table(self):
        """Sync the selected table."""
        selected = self.table_tree.selectedItems()
        if not selected:
            return
        
        table_name = selected[0].text(0)
        
        if self.sync_worker and self.sync_worker.isRunning():
            QMessageBox.warning(self, "Sync in Progress",
                              "A sync operation is already running")
            return
        
        # Get conflict resolution
        resolution_map = {
            "Manual": ConflictResolution.MANUAL,
            "Local Wins": ConflictResolution.LOCAL_WINS,
            "Remote Wins": ConflictResolution.REMOTE_WINS,
            "Merge": ConflictResolution.MERGE
        }
        resolution = resolution_map.get(
            self.resolution_combo.currentText(),
            ConflictResolution.MANUAL
        )
        
        # Start sync worker
        self.sync_worker = SyncWorker(self.sync_service, table_name, resolution)
        self.sync_worker.progress.connect(self.on_sync_progress)
        self.sync_worker.finished.connect(self.on_sync_finished)
        self.sync_worker.error.connect(self.on_sync_error)
        
        self.sync_table_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.sync_worker.start()
    
    def on_sync_progress(self, message: str, percentage: int):
        """Handle sync progress updates."""
        self.status_label.setText(message)
        if percentage >= 0:
            self.progress_bar.setValue(percentage)
    
    def on_sync_finished(self, result: SyncResult):
        """Handle sync completion."""
        self.progress_bar.setVisible(False)
        self.sync_all_btn.setEnabled(True)
        self.sync_table_btn.setEnabled(True)
        
        # Log results
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] Sync completed: "
        log_entry += f"{result.synced_count} synced"
        
        if result.conflict_count > 0:
            log_entry += f", {result.conflict_count} conflicts"
            self.conflicts = result.conflicts
            self.update_conflicts_table()
        
        if result.error_count > 0:
            log_entry += f", {result.error_count} errors"
        
        self.sync_log.append(log_entry)
        
        # Show summary
        if result.success:
            self.status_label.setText(f"Sync completed: {log_entry}")
            if result.conflict_count > 0:
                QMessageBox.information(
                    self, "Sync Completed",
                    f"Sync completed with {result.conflict_count} conflicts. "
                    "Please review and resolve conflicts."
                )
        else:
            self.status_label.setText("Sync failed - check log for details")
            QMessageBox.warning(
                self, "Sync Failed",
                "Sync operation failed. Check the log for details."
            )
        
        # Refresh status
        self.refresh_status()
    
    def on_sync_error(self, error: str):
        """Handle sync error."""
        self.progress_bar.setVisible(False)
        self.sync_all_btn.setEnabled(True)
        self.sync_table_btn.setEnabled(True)
        
        self.status_label.setText(f"Sync error: {error}")
        self.sync_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: {error}")
        
        QMessageBox.critical(self, "Sync Error", f"Sync failed: {error}")
    
    def update_conflicts_table(self):
        """Update the conflicts table with current conflicts."""
        self.conflicts_table.setRowCount(len(self.conflicts))
        
        for i, conflict in enumerate(self.conflicts):
            self.conflicts_table.setItem(i, 0, QTableWidgetItem(conflict.table_name))
            self.conflicts_table.setItem(i, 1, QTableWidgetItem(conflict.record_id))
            self.conflicts_table.setItem(i, 2, QTableWidgetItem(conflict.conflict_type))
            self.conflicts_table.setItem(i, 3, QTableWidgetItem(
                conflict.local_updated.strftime("%Y-%m-%d %H:%M")
            ))
            self.conflicts_table.setItem(i, 4, QTableWidgetItem(
                conflict.remote_updated.strftime("%Y-%m-%d %H:%M")
            ))
    
    def resolve_conflict(self, resolution: str):
        """Resolve selected conflict."""
        selected_row = self.conflicts_table.currentRow()
        if selected_row < 0 or selected_row >= len(self.conflicts):
            return
        
        conflict = self.conflicts[selected_row]
        
        # Map resolution string to enum
        if resolution == "local":
            resolution_type = ConflictResolution.LOCAL_WINS
        elif resolution == "remote":
            resolution_type = ConflictResolution.REMOTE_WINS
        else:
            return
        
        # Resolve conflict
        success = self.sync_service.resolve_conflict(conflict, resolution_type)
        
        if success:
            # Remove from conflicts list
            self.conflicts.pop(selected_row)
            self.update_conflicts_table()
            
            self.sync_log.append(
                f"[{datetime.now().strftime('%H:%M:%S')}] "
                f"Resolved conflict in {conflict.table_name}:{conflict.record_id} "
                f"using {resolution} version"
            )
            
            # Refresh status
            self.refresh_status()
        else:
            QMessageBox.warning(
                self, "Resolution Failed",
                "Failed to resolve conflict. Check log for details."
            )
    
    def view_conflict_diff(self):
        """View differences between local and remote versions."""
        selected_row = self.conflicts_table.currentRow()
        if selected_row < 0 or selected_row >= len(self.conflicts):
            return
        
        conflict = self.conflicts[selected_row]
        
        # Create diff dialog
        diff_dialog = QMessageBox(self)
        diff_dialog.setWindowTitle(f"Conflict: {conflict.table_name}:{conflict.record_id}")
        diff_dialog.setTextFormat(Qt.TextFormat.RichText)
        
        # Format diff text
        diff_text = "<h3>Local Version:</h3><pre>"
        diff_text += json.dumps(conflict.local_data, indent=2, default=str)
        diff_text += "</pre><h3>Remote Version:</h3><pre>"
        diff_text += json.dumps(conflict.remote_data, indent=2, default=str)
        diff_text += "</pre>"
        
        diff_dialog.setText(diff_text)
        diff_dialog.exec()
