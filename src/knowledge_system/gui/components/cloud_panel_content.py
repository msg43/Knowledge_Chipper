"""Cloud Panel Content - Upload queue and sync status.

Content for the Cloud expansion panel.
"""

from PyQt6.QtCore import pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
)


class CloudPanelContent(QWidget):
    """
    Cloud upload panel with queue status and manual upload.
    """
    
    manual_upload_requested = pyqtSignal()
    cancel_upload_requested = pyqtSignal()
    sync_status_check_requested = pyqtSignal()
    
    def __init__(self, auto_sync_worker=None, parent=None):
        super().__init__(parent)
        
        self.auto_sync_worker = auto_sync_worker  # Will be set by parent
        self._setup_ui()
        
        # Start periodic status check (every 2 seconds)
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._check_sync_status)
        self.status_timer.start(2000)  # 2 seconds
    
    def set_auto_sync_worker(self, worker):
        """Set auto sync worker reference."""
        self.auto_sync_worker = worker
    
    def _check_sync_status(self):
        """Check sync status from auto sync worker."""
        if self.auto_sync_worker:
            try:
                # Check if worker is online
                online = hasattr(self.auto_sync_worker, 'is_running') and self.auto_sync_worker.is_running()
                
                # Get queue count (placeholder - would query from worker)
                queue_count = 0  # TODO: Get actual queue count from worker
                
                self.update_status(online, queue_count)
            except Exception:
                self.update_status(False, 0)
        else:
            self.update_status(False, 0)
    
    def _setup_ui(self):
        """Setup cloud upload UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 15)
        layout.setSpacing(12)
        
        # Make visible
        self.setVisible(True)
        
        # Sync status - BIGGER, BLACKER
        status_layout = QHBoxLayout()
        status_layout.setSpacing(10)
        
        status_text = QLabel("Sync Status:")
        status_text.setStyleSheet("color: #000000; font-size: 14px; font-weight: bold;")
        status_layout.addWidget(status_text)
        
        self.status_label = QLabel("● Offline")
        self.status_label.setStyleSheet("color: #999; font-size: 14px; font-weight: bold;")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        layout.addLayout(status_layout)
        
        # Queue status - BLACK, BIGGER
        self.queue_label = QLabel("0 items in upload queue")
        self.queue_label.setStyleSheet("color: #000000; font-size: 13px; font-weight: bold;")
        layout.addWidget(self.queue_label)
        
        # Buttons - BIGGER, BETTER STYLED
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        self.manual_btn = QPushButton("📤 Manual Upload")
        self.manual_btn.setMinimumHeight(45)
        self.manual_btn.setStyleSheet("""
            QPushButton {
                background-color: #7EC8E3;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #6BB8D3;
            }
            QPushButton:pressed {
                background-color: #5AA8C3;
            }
        """)
        self.manual_btn.clicked.connect(self.manual_upload_requested.emit)
        
        self.cancel_btn = QPushButton("Cancel Upload")
        self.cancel_btn.setMinimumHeight(45)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #999;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #888;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_upload_requested.emit)
        
        btn_layout.addWidget(self.manual_btn)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        layout.addStretch()
    
    def update_status(self, online: bool, queue_count: int):
        """Update sync status and queue count."""
        if online:
            self.status_label.setText("● Online")
            self.status_label.setStyleSheet("color: #4CAF50; font-size: 11px;")
        else:
            self.status_label.setText("● Offline")
            self.status_label.setStyleSheet("color: #999; font-size: 11px;")
        
        self.queue_label.setText(f"{queue_count} items in upload queue")
        self.cancel_btn.setEnabled(queue_count > 0)

