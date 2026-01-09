"""Filter Bar component for the review queue."""

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
)

from .review_queue import EntityType, ReviewStatus


class FilterBar(QFrame):
    """
    Horizontal filter bar for filtering the review queue.
    
    Provides filters for:
    - Entity type (Claim, Jargon, Person, Concept)
    - Source (video/audio/document)
    - Review status (Pending, Accepted, Rejected)
    - Text search
    """
    
    filters_changed = pyqtSignal()  # Emitted when any filter changes
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setStyleSheet("""
            FilterBar {
                background-color: #2d2d2d;
                border: 1px solid #3c3c3c;
                border-radius: 6px;
                padding: 4px;
            }
        """)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the filter bar UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(12)
        
        # Type filter
        type_label = QLabel("Type:")
        type_label.setStyleSheet("color: #cccccc; font-weight: bold;")
        layout.addWidget(type_label)
        
        self.type_combo = QComboBox()
        self.type_combo.addItem("All Types", None)
        self.type_combo.addItem("📝 Claims", EntityType.CLAIM)
        self.type_combo.addItem("📖 Jargon", EntityType.JARGON)
        self.type_combo.addItem("👤 People", EntityType.PERSON)
        self.type_combo.addItem("💡 Concepts", EntityType.CONCEPT)
        self.type_combo.setMinimumWidth(120)
        self.type_combo.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(self.type_combo)
        
        # Separator
        layout.addWidget(self._create_separator())
        
        # Source filter
        source_label = QLabel("Source:")
        source_label.setStyleSheet("color: #cccccc; font-weight: bold;")
        layout.addWidget(source_label)
        
        self.source_combo = QComboBox()
        self.source_combo.addItem("All Sources", "")
        self.source_combo.setMinimumWidth(200)
        self.source_combo.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(self.source_combo)
        
        # Separator
        layout.addWidget(self._create_separator())
        
        # Status filter
        status_label = QLabel("Status:")
        status_label.setStyleSheet("color: #cccccc; font-weight: bold;")
        layout.addWidget(status_label)
        
        self.status_combo = QComboBox()
        self.status_combo.addItem("All", None)
        self.status_combo.addItem("⏳ Pending", ReviewStatus.PENDING)
        self.status_combo.addItem("✓ Accepted", ReviewStatus.ACCEPTED)
        self.status_combo.addItem("✗ Rejected", ReviewStatus.REJECTED)
        self.status_combo.setMinimumWidth(100)
        self.status_combo.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(self.status_combo)
        
        # Separator
        layout.addWidget(self._create_separator())
        
        # Search box
        search_label = QLabel("🔍")
        layout.addWidget(search_label)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search content...")
        self.search_input.setMinimumWidth(150)
        self.search_input.textChanged.connect(self._on_filter_changed)
        self.search_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QLineEdit:focus {
                border-color: #80bdff;
            }
        """)
        layout.addWidget(self.search_input)
        
        # Clear button
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 4px 12px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        self.clear_btn.clicked.connect(self.clear_filters)
        layout.addWidget(self.clear_btn)
        
        layout.addStretch()
    
    def _create_separator(self) -> QFrame:
        """Create a vertical separator."""
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        sep.setStyleSheet("color: #dee2e6;")
        return sep
    
    def _on_filter_changed(self):
        """Handle filter change."""
        self.filters_changed.emit()
    
    # Public API
    def get_type_filter(self) -> Optional[EntityType]:
        """Get current type filter."""
        return self.type_combo.currentData()
    
    def get_status_filter(self) -> Optional[ReviewStatus]:
        """Get current status filter."""
        return self.status_combo.currentData()
    
    def get_source_filter(self) -> str:
        """Get current source filter."""
        return self.source_combo.currentData() or ""
    
    def get_tier_filter(self) -> str:
        """Get current tier filter (removed, returns empty string for compatibility)."""
        return ""
    
    def get_search_text(self) -> str:
        """Get current search text."""
        return self.search_input.text()
    
    def set_sources(self, sources: list[tuple[str, str]]):
        """
        Set available sources for the source filter.
        
        Args:
            sources: List of (display_name, source_id) tuples
        """
        self.source_combo.blockSignals(True)
        current = self.source_combo.currentData()
        self.source_combo.clear()
        self.source_combo.addItem("All Sources", "")
        for name, source_id in sources:
            display = name[:50] + "..." if len(name) > 50 else name
            self.source_combo.addItem(display, source_id)
        # Restore selection if possible
        for i in range(self.source_combo.count()):
            if self.source_combo.itemData(i) == current:
                self.source_combo.setCurrentIndex(i)
                break
        self.source_combo.blockSignals(False)
    
    def clear_filters(self):
        """Clear all filters."""
        self.type_combo.setCurrentIndex(0)
        self.source_combo.setCurrentIndex(0)
        self.status_combo.setCurrentIndex(0)
        self.search_input.clear()
        self.filters_changed.emit()
    
    def set_pending_only(self):
        """Quick filter: Show only pending items."""
        self.status_combo.setCurrentIndex(1)  # Pending

