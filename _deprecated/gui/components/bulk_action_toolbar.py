"""Bulk Action Toolbar component for the review queue."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QWidget,
)


class BulkActionToolbar(QFrame):
    """
    Toolbar that appears when items are selected in the review queue.
    
    Provides bulk actions:
    - Accept selected
    - Reject selected
    - Set tier for selected
    - Deselect all
    """
    
    accept_selected = pyqtSignal()
    reject_selected = pyqtSignal()
    set_tier = pyqtSignal(str)  # Tier value
    deselect_all = pyqtSignal()
    select_all_visible = pyqtSignal()
    select_all_pending = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.selected_count = 0
        self.total_pending = 0
        
        self.setStyleSheet("""
            BulkActionToolbar {
                background-color: #e3f2fd;
                border: 1px solid #90caf9;
                border-radius: 6px;
            }
        """)
        
        self._setup_ui()
        self.hide()  # Hidden by default
    
    def _setup_ui(self):
        """Set up the toolbar UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)
        
        # Selection count
        self.count_label = QLabel("0 selected")
        self.count_label.setStyleSheet("font-weight: bold; color: #1565c0;")
        layout.addWidget(self.count_label)
        
        # Separator
        layout.addWidget(self._create_separator())
        
        # Select all visible button
        self.select_all_btn = QPushButton("Select All Visible")
        self.select_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #64b5f6;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #42a5f5;
            }
        """)
        self.select_all_btn.clicked.connect(self.select_all_visible.emit)
        layout.addWidget(self.select_all_btn)
        
        # Select all pending button
        self.select_pending_btn = QPushButton("Select All Pending")
        self.select_pending_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffc107;
                color: #333;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ffb300;
            }
        """)
        self.select_pending_btn.clicked.connect(self.select_all_pending.emit)
        layout.addWidget(self.select_pending_btn)
        
        # Separator
        layout.addWidget(self._create_separator())
        
        # Accept button
        self.accept_btn = QPushButton("✓ Accept Selected")
        self.accept_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 6px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        self.accept_btn.clicked.connect(self._on_accept_clicked)
        layout.addWidget(self.accept_btn)
        
        # Reject button
        self.reject_btn = QPushButton("✗ Reject Selected")
        self.reject_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                padding: 6px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        self.reject_btn.clicked.connect(self._on_reject_clicked)
        layout.addWidget(self.reject_btn)
        
        # Separator
        layout.addWidget(self._create_separator())
        
        # Tier selector
        tier_label = QLabel("Set Tier:")
        tier_label.setStyleSheet("color: #495057;")
        layout.addWidget(tier_label)
        
        self.tier_combo = QComboBox()
        self.tier_combo.addItems(["A", "B", "C", "D"])
        self.tier_combo.setMinimumWidth(60)
        layout.addWidget(self.tier_combo)
        
        self.apply_tier_btn = QPushButton("Apply")
        self.apply_tier_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        self.apply_tier_btn.clicked.connect(self._on_apply_tier)
        layout.addWidget(self.apply_tier_btn)
        
        layout.addStretch()
        
        # Deselect all button
        self.deselect_btn = QPushButton("Deselect All")
        self.deselect_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #1565c0;
                border: 1px solid #1565c0;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #e3f2fd;
            }
        """)
        self.deselect_btn.clicked.connect(self.deselect_all.emit)
        layout.addWidget(self.deselect_btn)
    
    def _create_separator(self) -> QFrame:
        """Create a vertical separator."""
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        sep.setStyleSheet("color: #90caf9;")
        return sep
    
    def _on_accept_clicked(self):
        """Handle accept button click with confirmation for large selections."""
        if self.selected_count > 50:
            reply = QMessageBox.question(
                self,
                "Confirm Bulk Accept",
                f"Accept {self.selected_count:,} items?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self.accept_selected.emit()
    
    def _on_reject_clicked(self):
        """Handle reject button click with confirmation."""
        if self.selected_count > 10:
            reply = QMessageBox.question(
                self,
                "Confirm Bulk Reject",
                f"Reject {self.selected_count:,} items? This action can be undone.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self.reject_selected.emit()
    
    def _on_apply_tier(self):
        """Handle apply tier button click."""
        tier = self.tier_combo.currentText()
        self.set_tier.emit(tier)
    
    # Public API
    def update_selection_count(self, count: int):
        """Update the selection count display."""
        self.selected_count = count
        self.count_label.setText(f"{count:,} selected")
        
        # Show/hide toolbar based on selection
        if count > 0:
            self.show()
        else:
            self.hide()
        
        # Enable/disable action buttons
        has_selection = count > 0
        self.accept_btn.setEnabled(has_selection)
        self.reject_btn.setEnabled(has_selection)
        self.apply_tier_btn.setEnabled(has_selection)
    
    def set_total_pending(self, count: int):
        """Set the total pending count for the select all pending button."""
        self.total_pending = count
        self.select_pending_btn.setText(f"Select All {count:,} Pending")

