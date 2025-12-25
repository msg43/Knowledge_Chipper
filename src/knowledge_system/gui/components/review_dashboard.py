"""Review Dashboard component for displaying processing and review statistics."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ReviewDashboard(QFrame):
    """
    Compact dashboard showing real-time processing and review statistics.
    
    Displays:
    - Processing progress with dual progress bars (current file + batch)
    - Review status inline (pending, accepted, rejected counts)
    """

    collapse_toggled = pyqtSignal(bool)  # True = collapsed

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_collapsed = False
        
        self.setStyleSheet("""
            ReviewDashboard {
                background-color: #2d2d2d;
                border: 1px solid #3c3c3c;
                border-radius: 8px;
            }
        """)
        
        self._setup_ui()
        self._reset_stats()
    
    def _setup_ui(self):
        """Setup the compact dashboard UI."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 8, 12, 8)
        main_layout.setSpacing(6)
        
        # Single row with all info
        info_layout = QHBoxLayout()
        
        # Processing info
        self.header_label = QLabel("📊 Processing:")
        header_font = QFont()
        header_font.setBold(True)
        self.header_label.setFont(header_font)
        self.header_label.setStyleSheet("color: #cccccc;")
        info_layout.addWidget(self.header_label)
        
        self.videos_label = QLabel("0/0 videos")
        self.videos_label.setStyleSheet("color: #999;")
        info_layout.addWidget(self.videos_label)
        
        info_layout.addSpacing(20)
        
        self.extracted_label = QLabel("0 items extracted")
        self.extracted_label.setStyleSheet("color: #999;")
        info_layout.addWidget(self.extracted_label)
        
        info_layout.addSpacing(20)
        
        # Review status (inline, compact)
        self.status_label = QLabel("Pending: 0 | Accepted: 0 | Rejected: 0")
        self.status_label.setStyleSheet("color: #999;")
        info_layout.addWidget(self.status_label)
        
        info_layout.addSpacing(20)
        
        # Sync status indicator
        self.sync_indicator = QLabel("")
        self.sync_indicator.setStyleSheet("color: #999; font-size: 11px;")
        info_layout.addWidget(self.sync_indicator)
        
        info_layout.addStretch()
        
        main_layout.addLayout(info_layout)
        
        # Dual progress bars
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(4)
        
        # Current file progress
        current_layout = QHBoxLayout()
        current_label = QLabel("Current:")
        current_label.setStyleSheet("color: #999; font-size: 10px;")
        current_label.setFixedWidth(60)
        current_layout.addWidget(current_label)
        
        self.current_progress_bar = QProgressBar()
        self.current_progress_bar.setFixedHeight(8)
        self.current_progress_bar.setTextVisible(False)
        self.current_progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #3c3c3c;
                border: none;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 4px;
            }
        """)
        current_layout.addWidget(self.current_progress_bar)
        
        self.current_status_label = QLabel("")
        self.current_status_label.setStyleSheet("color: #999; font-size: 10px;")
        self.current_status_label.setFixedWidth(100)
        current_layout.addWidget(self.current_status_label)
        
        progress_layout.addLayout(current_layout)
        
        # Batch progress
        batch_layout = QHBoxLayout()
        batch_label = QLabel("Batch:")
        batch_label.setStyleSheet("color: #999; font-size: 10px;")
        batch_label.setFixedWidth(60)
        batch_layout.addWidget(batch_label)
        
        self.batch_progress_bar = QProgressBar()
        self.batch_progress_bar.setFixedHeight(8)
        self.batch_progress_bar.setTextVisible(False)
        self.batch_progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #3c3c3c;
                border: none;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #28a745;
                border-radius: 4px;
            }
        """)
        batch_layout.addWidget(self.batch_progress_bar)
        
        self.batch_status_label = QLabel("")
        self.batch_status_label.setStyleSheet("color: #999; font-size: 10px;")
        self.batch_status_label.setFixedWidth(100)
        batch_layout.addWidget(self.batch_status_label)
        
        progress_layout.addLayout(batch_layout)
        
        main_layout.addLayout(progress_layout)
    
    def _reset_stats(self):
        """Reset all statistics to zero."""
        self.total_videos = 0
        self.processed_videos = 0
        self.total_extracted = 0
        self.pending_count = 0
        self.accepted_count = 0
        self.rejected_count = 0
        self.current_file_progress = 0
        self.current_file_name = ""
        self._update_display()
    
    def _update_display(self):
        """Update all display elements."""
        self.videos_label.setText(f"{self.processed_videos}/{self.total_videos} videos")
        self.extracted_label.setText(f"{self.total_extracted:,} items extracted")
        
        # Update review status inline
        self.status_label.setText(
            f"<span style='color: #ffc107;'>Pending: {self.pending_count}</span> | "
            f"<span style='color: #28a745;'>Accepted: {self.accepted_count}</span> | "
            f"<span style='color: #dc3545;'>Rejected: {self.rejected_count}</span>"
        )
        
        # Update batch progress
        if self.total_videos > 0:
            progress = int((self.processed_videos / self.total_videos) * 100)
            self.batch_progress_bar.setValue(progress)
            self.batch_status_label.setText(f"{progress}%")
        else:
            self.batch_progress_bar.setValue(0)
            self.batch_status_label.setText("")
        
        # Update current file progress
        self.current_progress_bar.setValue(self.current_file_progress)
        if self.current_file_progress > 0:
            status_text = f"{self.current_file_progress}%"
            if self.current_file_name:
                status_text = f"{self.current_file_name[:15]}..."
            self.current_status_label.setText(status_text)
        else:
            self.current_status_label.setText("")
    
    # Public API
    def set_total_videos(self, total: int):
        """Set total number of videos to process."""
        self.total_videos = total
        self._update_display()
    
    def set_processed_videos(self, count: int):
        """Set number of videos processed so far."""
        self.processed_videos = count
        self._update_display()
    
    def increment_processed(self):
        """Increment processed video count by 1."""
        self.processed_videos += 1
        self._update_display()
    
    def set_extracted_count(self, count: int):
        """Set total extracted items count."""
        self.total_extracted = count
        self._update_display()
    
    def add_extracted(self, count: int):
        """Add to extracted items count."""
        self.total_extracted += count
        self._update_display()
    
    def set_review_counts(self, pending: int, accepted: int, rejected: int):
        """Set all review status counts at once."""
        self.pending_count = pending
        self.accepted_count = accepted
        self.rejected_count = rejected
        self._update_display()
    
    def update_pending(self, count: int):
        """Update pending count."""
        self.pending_count = count
        self._update_display()
    
    def update_accepted(self, count: int):
        """Update accepted count."""
        self.accepted_count = count
        self._update_display()
    
    def update_rejected(self, count: int):
        """Update rejected count."""
        self.rejected_count = count
        self._update_display()
    
    def accept_items(self, count: int):
        """Move items from pending to accepted."""
        self.pending_count = max(0, self.pending_count - count)
        self.accepted_count += count
        self._update_display()
    
    def reject_items(self, count: int):
        """Move items from pending to rejected."""
        self.pending_count = max(0, self.pending_count - count)
        self.rejected_count += count
        self._update_display()
    
    def set_current_file_progress(self, progress: int, file_name: str = ""):
        """
        Set current file processing progress.
        
        Args:
            progress: Progress percentage (0-100)
            file_name: Optional file name to display
        """
        self.current_file_progress = progress
        self.current_file_name = file_name
        self._update_display()
    
    def set_current_stage(self, stage: str):
        """
        Set current processing stage (Extracting/Synthesizing).
        
        Args:
            stage: Stage name to display
        """
        self.current_status_label.setText(stage)
    
    def set_sync_status(self, status: str):
        """
        Set sync status indicator.
        
        Args:
            status: Status text (e.g., "Syncing...", "Synced ✓", "Queued for sync")
        """
        if status:
            if "Syncing" in status:
                self.sync_indicator.setStyleSheet("color: #3498db; font-size: 11px;")
            elif "✓" in status or "Synced" in status:
                self.sync_indicator.setStyleSheet("color: #28a745; font-size: 11px;")
            elif "Queued" in status or "Failed" in status:
                self.sync_indicator.setStyleSheet("color: #ffc107; font-size: 11px;")
            else:
                self.sync_indicator.setStyleSheet("color: #999; font-size: 11px;")
        self.sync_indicator.setText(status)
    
    def set_unsynced_count(self, count: int):
        """
        Show count of unsynced accepted items.
        
        Args:
            count: Number of unsynced items
        """
        if count > 0:
            self.sync_indicator.setText(f"⚠️ {count} item(s) queued for sync")
            self.sync_indicator.setStyleSheet("color: #ffc107; font-size: 11px;")
        else:
            self.sync_indicator.setText("")
    
    def reset(self):
        """Reset all stats to zero."""
        self._reset_stats()

