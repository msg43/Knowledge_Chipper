"""Claims Panel Content - Review and filter extracted claims.

Content for the Claims expansion panel.
"""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QCheckBox,
    QComboBox,
    QListWidget,
    QLabel,
    QPushButton,
)


class ClaimsPanelContent(QWidget):
    """
    Claims review panel with tier filters and claim list.
    """
    
    export_requested = pyqtSignal()
    
    def __init__(self, db_service, parent=None):
        super().__init__(parent)
        
        self.db_service = db_service
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup claims review UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 15)
        layout.setSpacing(12)
        
        # Make visible
        self.setVisible(True)
        
        # Tier filters - BIGGER, BLACKER
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(15)
        
        # Label
        tier_label = QLabel("Tier Filters:")
        tier_label.setStyleSheet("color: #000000; font-size: 14px; font-weight: bold;")
        filter_layout.addWidget(tier_label)
        
        self.filter_high = QCheckBox("High")
        self.filter_medium = QCheckBox("Medium")
        self.filter_low = QCheckBox("Low")
        
        # All checked by default
        self.filter_high.setChecked(True)
        self.filter_medium.setChecked(True)
        self.filter_low.setChecked(True)
        
        # Style - BLACK TEXT, BIGGER
        checkbox_style = """
            QCheckBox {
                color: #000000;
                font-size: 14px;
                font-weight: bold;
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border: 2px solid #666;
                border-radius: 4px;
                background-color: white;
            }
            QCheckBox::indicator:checked {
                background-color: #4CAF50;
                border-color: #4CAF50;
            }
        """
        self.filter_high.setStyleSheet(checkbox_style)
        self.filter_medium.setStyleSheet(checkbox_style)
        self.filter_low.setStyleSheet(checkbox_style)
        
        # Connect
        self.filter_high.toggled.connect(self._update_claim_list)
        self.filter_medium.toggled.connect(self._update_claim_list)
        self.filter_low.toggled.connect(self._update_claim_list)
        
        filter_layout.addWidget(self.filter_high)
        filter_layout.addWidget(self.filter_medium)
        filter_layout.addWidget(self.filter_low)
        filter_layout.addStretch()
        
        # Export button - STYLED
        export_btn = QPushButton("📤 Export Claims")
        export_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                border: 2px solid #bbb;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
                color: #000000;
            }
            QPushButton:hover {
                background-color: #f5f5f5;
                border-color: #888;
            }
        """)
        export_btn.clicked.connect(self.export_requested.emit)
        filter_layout.addWidget(export_btn)
        
        layout.addLayout(filter_layout)
        
        # Claim count - BLACK, BIGGER
        self.count_label = QLabel("0 claims")
        self.count_label.setStyleSheet("color: #000000; font-size: 13px; font-weight: bold;")
        layout.addWidget(self.count_label)
        
        # Claim list (compact) - STYLED
        self.claim_list = QListWidget()
        self.claim_list.setMaximumHeight(100)
        self.claim_list.setStyleSheet("""
            QListWidget {
                background-color: white;
                border: 2px solid #ccc;
                border-radius: 6px;
                font-size: 13px;
                color: #000000;
                padding: 8px;
            }
            QListWidget::item {
                padding: 4px;
            }
        """)
        layout.addWidget(self.claim_list)
    
    def _update_claim_list(self):
        """Update claim list based on filters."""
        self.claim_list.clear()
        
        # Get filter states
        show_high = self.filter_high.isChecked()
        show_medium = self.filter_medium.isChecked()
        show_low = self.filter_low.isChecked()
        
        # Build tier filter list
        tiers = []
        if show_high:
            tiers.append('high')
        if show_medium:
            tiers.append('medium')
        if show_low:
            tiers.append('low')
        
        if not tiers:
            self.count_label.setText("0 claims (no tiers selected)")
            return
        
        try:
            # Query database for recent claims
            # Using raw SQL since we don't have a specific method for this
            query = """
                SELECT claim_text, importance_tier, source_id
                FROM claims
                WHERE importance_tier IN ({})
                ORDER BY created_at DESC
                LIMIT 50
            """.format(','.join('?' * len(tiers)))
            
            with self.db_service.get_connection() as conn:
                cursor = conn.execute(query, tiers)
                claims = cursor.fetchall()
            
            # Add to list
            for claim_text, tier, source_id in claims:
                # Truncate long claims
                display_text = claim_text[:100] + "..." if len(claim_text) > 100 else claim_text
                self.claim_list.addItem(f"[{tier.upper()}] {display_text}")
            
            self.count_label.setText(f"{len(claims)} claims")
        
        except Exception as e:
            self.count_label.setText(f"Error: {str(e)}")
            self.claim_list.addItem(f"Database error: {str(e)}")
    
    def refresh_claims(self):
        """Refresh claims from database."""
        self._update_claim_list()


class SummariesPanelContent(QWidget):
    """
    Summaries review panel with regenerate button.
    """
    
    regenerate_requested = pyqtSignal(str)  # source_id to regenerate
    
    def __init__(self, db_service, parent=None):
        super().__init__(parent)
        
        self.db_service = db_service
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup summaries review UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 15)
        layout.setSpacing(12)
        
        # Make visible
        self.setVisible(True)
        
        # Info text - BLACK, BIGGER
        info = QLabel("Select a source to regenerate its summary:")
        info.setStyleSheet("color: #000000; font-size: 14px; font-weight: bold;")
        layout.addWidget(info)
        
        # Source selector - STYLED
        self.source_combo = QComboBox()
        self.source_combo.setMinimumHeight(40)
        self.source_combo.setStyleSheet("""
            QComboBox {
                background-color: white;
                border: 2px solid #ccc;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
                color: #000000;
                font-weight: 600;
            }
            QComboBox:hover {
                border-color: #999;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
        """)
        layout.addWidget(self.source_combo)
        
        # Regenerate button - BIGGER, BETTER STYLED
        self.regen_btn = QPushButton("🔄 Regenerate Summary")
        self.regen_btn.setMinimumHeight(45)
        self.regen_btn.setStyleSheet("""
            QPushButton {
                background-color: #F4A5A5;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #E49595;
            }
            QPushButton:pressed {
                background-color: #D48585;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        self.regen_btn.clicked.connect(self._handle_regenerate)
        self.regen_btn.setEnabled(False)
        layout.addWidget(self.regen_btn)
        
        # Connect combo change
        self.source_combo.currentIndexChanged.connect(self._source_selected)
        
        layout.addStretch()
        
        # Load sources
        self._load_sources()
    
    def _load_sources(self):
        """Load recent sources with summaries."""
        self.source_combo.clear()
        self.source_combo.addItem("(Select a source)", None)
        
        try:
            query = """
                SELECT DISTINCT s.source_id, s.title
                FROM sources s
                INNER JOIN summaries sum ON s.source_id = sum.source_id
                ORDER BY s.created_at DESC
                LIMIT 20
            """
            
            with self.db_service.get_connection() as conn:
                cursor = conn.execute(query)
                sources = cursor.fetchall()
            
            for source_id, title in sources:
                display = title[:40] + "..." if len(title) > 40 else title
                self.source_combo.addItem(display, source_id)
        
        except Exception as e:
            self.source_combo.addItem(f"Error: {str(e)}", None)
    
    def _source_selected(self):
        """Handle source selection."""
        source_id = self.source_combo.currentData()
        self.regen_btn.setEnabled(source_id is not None)
    
    def _handle_regenerate(self):
        """Handle regenerate button click."""
        source_id = self.source_combo.currentData()
        if source_id:
            self.regenerate_requested.emit(source_id)


class CloudPanelContent(QWidget):
    """
    Cloud upload panel with queue status and manual upload.
    """
    
    manual_upload_requested = pyqtSignal()
    cancel_upload_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup cloud upload UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(4)
        
        # Sync status
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("Status:"))
        self.status_label = QLabel("● Offline")
        self.status_label.setStyleSheet("color: #999; font-size: 11px;")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        layout.addLayout(status_layout)
        
        # Queue status
        self.queue_label = QLabel("0 items in upload queue")
        self.queue_label.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(self.queue_label)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.manual_btn = QPushButton("📤 Manual Upload")
        self.manual_btn.setStyleSheet("""
            QPushButton {
                background-color: #7EC8E3;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #6BB8D3;
            }
        """)
        self.manual_btn.clicked.connect(self.manual_upload_requested.emit)
        
        self.cancel_btn = QPushButton("Cancel")
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

