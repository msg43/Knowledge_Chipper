"""StatusBox component for right pane log display.

Colored box that shows logs for a specific processing stage and can expand/collapse.
"""

from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtSignal
from PyQt6.QtGui import QColor, QTextCursor, QFont
from PyQt6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QScrollArea,
    QTextEdit,
    QProgressBar,
    QWidget,
)


class StatusBox(QFrame):
    """
    Colored status box showing logs for one processing stage.
    
    Features:
    - Default height: 100px
    - Collapsed height: 30px (when another box is expanded)
    - Expanded height: Takes remaining space (~450px)
    - Individual scrollbar
    - Click to expand/collapse
    - Shows progress bar when active
    - Displays timestamped logs
    - Auto-scrolls to bottom
    """
    
    clicked = pyqtSignal(str)  # box_id
    
    # Height constants
    DEFAULT_HEIGHT = 100
    COLLAPSED_HEIGHT = 30
    EXPANDED_HEIGHT = 450
    
    def __init__(self, box_id: str, color: str, parent=None):
        """
        Initialize status box.
        
        Args:
            box_id: Unique identifier matching tile_id
            color: Box color (matches tile color)
        """
        super().__init__(parent)
        
        self.box_id = box_id
        self.color = color
        self.state = 'default'  # default | collapsed | expanded
        
        # Set initial size
        self.setFixedHeight(self.DEFAULT_HEIGHT)
        
        # Glassmorphism styling
        lighter = self._lighten_color(color, 0.25)
        darker = self._darken_color(color, 0.1)
        self.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 {lighter},
                    stop:0.5 {color},
                    stop:1 {darker}
                );
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 25);
            }}
        """)
        
        # Enable click detection
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Setup UI
        self._setup_ui()
        
        # Animation for expand/collapse
        self.animation = QPropertyAnimation(self, b"minimumHeight")
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
    
    def _lighten_color(self, hex_color: str, amount: float) -> str:
        """Lighten a hex color."""
        color = QColor(hex_color)
        h, s, v, a = color.getHsv()
        v = min(255, int(v * (1 + amount)))
        color.setHsv(h, s, v, a)
        return color.name()
    
    def _darken_color(self, hex_color: str, amount: float) -> str:
        """Darken a color by the given amount."""
        color = QColor(hex_color)
        r = max(0, int(color.red() * (1 - amount)))
        g = max(0, int(color.green() * (1 - amount)))
        b = max(0, int(color.blue() * (1 - amount)))
        return QColor(r, g, b).name()
    
    def _setup_ui(self):
        """Setup the status box UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        
        # Progress bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumHeight(20)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 3px;
                background-color: rgba(255, 255, 255, 0.3);
                text-align: center;
                color: #2d2d30;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: rgba(255, 255, 255, 0.7);
                border-radius: 3px;
            }
        """)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        
        # Scroll area for logs
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                width: 8px;
                background: rgba(255, 255, 255, 0.2);
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.5);
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(255, 255, 255, 0.7);
            }
        """)
        
        # Text edit for log content
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFrameShape(QFrame.Shape.NoFrame)
        
        # Monospace font for logs
        font = QFont("Menlo, Consolas, Monaco, monospace")
        font.setPointSize(11)
        self.log_text.setFont(font)
        
        # Dark text on light background
        self.log_text.setStyleSheet("""
            QTextEdit {
                background: transparent;
                color: #2d2d30;
                border: none;
            }
        """)
        
        scroll_area.setWidget(self.log_text)
        layout.addWidget(scroll_area)
        
        # Add initial "Ready..." message
        self.append_log("Ready...")
    
    def set_color(self, color: str):
        """Update box color dynamically."""
        self.color = color
        self.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 {self._lighten_color(color, 0.1)},
                    stop:1 {color}
                );
                border-radius: 10px;
            }}
        """)
    
    def append_log(self, message: str):
        """Append a log message with timestamp."""
        from datetime import datetime
        
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        formatted = f"{timestamp} {message}"
        
        self.log_text.append(formatted)
        
        # Auto-scroll to bottom
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)
    
    def clear_logs(self):
        """Clear all log messages."""
        self.log_text.clear()
    
    def set_progress(self, percent: int):
        """Set progress bar value."""
        if not self.progress_bar.isVisible():
            self.progress_bar.show()
        
        self.progress_bar.setValue(percent)
        
        # Hide when complete
        if percent >= 100:
            self.progress_bar.hide()
    
    def expand(self):
        """Expand this box, taking most vertical space."""
        if self.state == 'expanded':
            return
        
        self.state = 'expanded'
        self._animate_to_height(self.EXPANDED_HEIGHT)
    
    def collapse(self):
        """Collapse this box to one line."""
        if self.state == 'collapsed':
            return
        
        self.state = 'collapsed'
        self._animate_to_height(self.COLLAPSED_HEIGHT)
    
    def restore(self):
        """Restore to default height."""
        if self.state == 'default':
            return
        
        self.state = 'default'
        self._animate_to_height(self.DEFAULT_HEIGHT)
    
    def _animate_to_height(self, target_height: int):
        """Animate to target height."""
        self.animation.stop()
        self.animation.setStartValue(self.height())
        self.animation.setEndValue(target_height)
        
        # Also animate maximum height to allow growth
        self.animation.setTargetObject(self)
        self.animation.setPropertyName(b"minimumHeight")
        
        # For expand, also set maximum height
        if target_height > self.DEFAULT_HEIGHT:
            self.setMaximumHeight(target_height)
        else:
            self.setMaximumHeight(target_height)
        
        self.animation.start()
    
    def mousePressEvent(self, event):
        """Handle mouse click to expand/collapse."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.box_id)
        super().mousePressEvent(event)


class LayerLogWidget(QWidget):
    """
    Widget containing all 6 status boxes for the right pane.
    
    Handles expand/collapse coordination and maintains vertical alignment with left tiles.
    """
    
    def __init__(self, tile_colors: dict[str, str], parent=None):
        """
        Initialize layer log widget.
        
        Args:
            tile_colors: Dict mapping tile_id to color hex
        """
        super().__init__(parent)
        
        self.tile_colors = tile_colors
        self.expanded_box = None  # Track which box is expanded
        
        # Create layout - MUST MATCH LEFT PANE EXACTLY
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)  # No margins
        self.main_layout.setSpacing(0)  # NO spacing - we'll use margins on boxes
        
        # Create status boxes for each tile (order matters)
        self.boxes = {}
        self.spacers = {}  # Track spacers for alignment
        
        # Only create boxes for tiles that have colors passed in
        box_order = [
            'sources', 
            'transcripts',
            'claims',
            'summaries',
            'cloud',
        ]
        
        for i, box_id in enumerate(box_order):
            if box_id in tile_colors:
                color = tile_colors[box_id]
                box = StatusBox(box_id, color)
                box.clicked.connect(self._handle_box_click)
                self.boxes[box_id] = box
                
                # Add 8px top margin to all except first box (matches left pane gap)
                if i > 0:
                    box.setContentsMargins(0, 8, 0, 0)
                
                self.main_layout.addWidget(box)
                
                # Add spacer widget after each box (starts at 0 height)
                spacer = QWidget()
                spacer.setFixedHeight(0)
                spacer.setStyleSheet("background: transparent;")
                self.spacers[box_id] = spacer
                self.main_layout.addWidget(spacer)
        
        # CRITICAL: Add stretch at bottom to push boxes to TOP
        self.main_layout.addStretch()
    
    def _handle_box_click(self, box_id: str):
        """Handle box click - expand clicked box, collapse others."""
        # If clicking the expanded box, restore all
        if self.expanded_box == box_id:
            self.restore_all()
            return
        
        # Expand clicked box, collapse others
        for bid, box in self.boxes.items():
            if bid == box_id:
                box.expand()
            else:
                box.collapse()
        
        self.expanded_box = box_id
    
    def restore_all(self):
        """Restore all boxes to default height."""
        for box in self.boxes.values():
            box.restore()
        self.expanded_box = None
    
    def update_colors(self, new_colors: dict[str, str]):
        """Update all box colors."""
        for box_id, box in self.boxes.items():
            if box_id in new_colors:
                box.set_color(new_colors[box_id])
    
    def append_log(self, box_id: str, message: str):
        """Append log to specific box."""
        if box_id in self.boxes:
            self.boxes[box_id].append_log(message)
    
    def set_progress(self, box_id: str, percent: int):
        """Set progress for specific box."""
        if box_id in self.boxes:
            self.boxes[box_id].set_progress(percent)
    
    def set_expansion_spacer(self, box_id: str, height: int):
        """
        Adjust spacer height to align with expanded tile on left.
        
        When a tile expands on the left, we expand the corresponding
        spacer on the right to push lower boxes down in sync.
        
        Args:
            box_id: ID of box whose spacer to adjust
            height: Height in pixels (0 to collapse, 300 to expand)
        """
        if box_id in self.spacers:
            spacer = self.spacers[box_id]
            spacer.setFixedHeight(height)
            spacer.updateGeometry()
            self.main_layout.update()

