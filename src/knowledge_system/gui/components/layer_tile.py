"""Base LayerTile component for layer cake GUI.

Fixed-height tile with custom gradient painting, rounded corners, and click detection.
"""

from PyQt6.QtCore import Qt, pyqtSignal, QRect
from PyQt6.QtGui import (
    QColor,
    QLinearGradient,
    QPainter,
    QPaintEvent,
    QFont,
    QMouseEvent,
)
from PyQt6.QtWidgets import QFrame, QGraphicsDropShadowEffect


class LayerTile(QFrame):
    """
    Fixed-height tile with gradient background and click detection.
    
    Features:
    - Fixed 100px height (never changes)
    - Vertical gradient (lighter at top)
    - Rounded corners (10px)
    - Drop shadow for depth
    - Click detection
    - Hover state with glow
    - Dynamic color support
    """
    
    clicked = pyqtSignal(str)  # tile_id
    
    def __init__(
        self,
        tile_id: str,
        color: str,
        icon: str,
        label: str,
        parent=None
    ):
        """
        Initialize layer tile.
        
        Args:
            tile_id: Unique identifier (e.g. 'settings', 'sources')
            color: Base color hex string (e.g. '#7EC8E3')
            icon: Icon string (emoji or text)
            label: Display label
        """
        super().__init__(parent)
        
        self.tile_id = tile_id
        self.color = color
        self.icon = icon
        self.label = label
        self.is_hovered = False
        self.is_active = False
        
        # Fixed height - NEVER CHANGES
        self.setFixedHeight(100)
        
        # Enable mouse tracking for hover effects
        self.setMouseTracking(True)
        
        # Calculate lighter color for gradient top
        self.lighter_color = self._lighten_color(color, 0.2)
        
        # Add drop shadow for depth
        self._add_shadow()
        
        # Set cursor to pointer on hover
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    
    def _lighten_color(self, hex_color: str, amount: float) -> str:
        """Lighten a hex color by a percentage."""
        color = QColor(hex_color)
        h, s, v, a = color.getHsv()
        v = min(255, int(v * (1 + amount)))
        color.setHsv(h, s, v, a)
        return color.name()
    
    def _darken_color(self, hex_color: str, amount: float) -> str:
        """Darken a hex color by a percentage."""
        color = QColor(hex_color)
        h, s, v, a = color.getHsv()
        v = max(0, int(v * (1 - amount)))
        color.setHsv(h, s, v, a)
        return color.name()
    
    def _add_shadow(self):
        """Add drop shadow effect for depth."""
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)
    
    def set_color(self, color: str):
        """Update tile color dynamically."""
        self.color = color
        self.lighter_color = self._lighten_color(color, 0.2)
        self.update()  # Trigger repaint
    
    def set_active(self, active: bool):
        """Set tile active state (for visual feedback during processing)."""
        self.is_active = active
        self.update()
    
    def paintEvent(self, event: QPaintEvent):
        """Custom paint event with glassmorphism styling."""
        from PyQt6.QtGui import QPen
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect().adjusted(1, 1, -1, -1)
        
        # === GLASSMORPHISM EFFECT ===
        
        # 1. Main gradient - subtle color shift
        gradient = QLinearGradient(0, 0, 0, self.height())
        
        base = QColor(self.color)
        
        if self.is_hovered or self.is_active:
            # Brighten on hover
            top_color = self._lighten_color(self.color, 0.35)
            mid_color = self._lighten_color(self.color, 0.15)
            bot_color = self._darken_color(self.color, 0.05)
        else:
            top_color = self._lighten_color(self.color, 0.25)
            mid_color = self.color
            bot_color = self._darken_color(self.color, 0.1)
        
        gradient.setColorAt(0.0, QColor(top_color))
        gradient.setColorAt(0.5, QColor(mid_color))
        gradient.setColorAt(1.0, QColor(bot_color))
        
        # Draw main shape
        painter.setBrush(gradient)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 12, 12)
        
        # 2. Inner highlight (glass shine at top)
        highlight_rect = rect.adjusted(4, 4, -4, -int(self.height() * 0.6))
        highlight_gradient = QLinearGradient(0, highlight_rect.top(), 0, highlight_rect.bottom())
        highlight_gradient.setColorAt(0.0, QColor(255, 255, 255, 50))
        highlight_gradient.setColorAt(1.0, QColor(255, 255, 255, 0))
        
        painter.setBrush(highlight_gradient)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(highlight_rect, 8, 8)
        
        # 3. Border - light top edge, subtle overall
        painter.setBrush(Qt.BrushStyle.NoBrush)
        
        # Top highlight border
        painter.setPen(QPen(QColor(255, 255, 255, 80), 1))
        painter.drawLine(rect.left() + 12, rect.top(), rect.right() - 12, rect.top())
        
        # Full border (subtle)
        painter.setPen(QPen(QColor(255, 255, 255, 25), 1))
        painter.drawRoundedRect(rect, 12, 12)
        
        # Draw content
        self._draw_content(painter)
        
        # Draw active indicator if processing
        if self.is_active:
            self._draw_active_indicator(painter)
    
    def _darken_color(self, hex_color: str, amount: float) -> str:
        """Darken a color by the given amount."""
        color = QColor(hex_color)
        r = max(0, int(color.red() * (1 - amount)))
        g = max(0, int(color.green() * (1 - amount)))
        b = max(0, int(color.blue() * (1 - amount)))
        return QColor(r, g, b).name()
    
    def _draw_content(self, painter: QPainter):
        """Draw step number circle and label text."""
        from PyQt6.QtGui import QPen, QBrush
        
        # Get step number based on tile_id
        step_numbers = {
            'sources': '1',
            'transcripts': '2', 
            'claims': '3',
            'summaries': '4',
            'cloud': '5',
        }
        step_num = step_numbers.get(self.tile_id, '')
        
        # Use WHITE text for modern dark colors
        text_color = QColor(255, 255, 255)
        
        # Draw step number in subtle circle (if applicable)
        if step_num:
            # Circle position and size
            circle_x = 25
            circle_y = (self.height() - 50) // 2
            circle_size = 50
            
            # Draw circle with semi-transparent white fill
            painter.setPen(QPen(QColor(255, 255, 255, 100), 2))
            painter.setBrush(QBrush(QColor(255, 255, 255, 60)))
            painter.drawEllipse(circle_x, circle_y, circle_size, circle_size)
            
            # Draw step number
            num_font = QFont()
            num_font.setPointSize(22)
            num_font.setBold(True)
            painter.setFont(num_font)
            painter.setPen(text_color)
            
            num_rect = QRect(circle_x, circle_y, circle_size, circle_size)
            painter.drawText(num_rect, Qt.AlignmentFlag.AlignCenter, step_num)
            
            label_start_x = circle_x + circle_size + 20
        else:
            label_start_x = 25
        
        # Label font - clean and bold
        label_font = QFont()
        label_font.setPointSize(18)
        label_font.setBold(True)
        
        # Use WHITE for modern dark tiles
        painter.setPen(text_color)
        painter.setFont(label_font)
        
        # Draw label
        label_rect = QRect(label_start_x, 0, self.width() - label_start_x - 20, self.height())
        painter.drawText(
            label_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self.label
        )
    
    def _get_text_color(self) -> QColor:
        """Determine text color based on background brightness."""
        color = QColor(self.color)
        # Calculate relative luminance
        r, g, b = color.red(), color.green(), color.blue()
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        
        # Use dark text for light backgrounds, light text for dark backgrounds
        if luminance > 0.5:
            return QColor("#2d2d30")  # Dark text
        else:
            return QColor("#E0E0E0")  # Light text
    
    def _draw_active_indicator(self, painter: QPainter):
        """Draw subtle pulsing indicator when tile is active."""
        # Draw thin border glow
        painter.setPen(QColor(255, 255, 255, 150))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(
            self.rect().adjusted(2, 2, -2, -2),
            10, 10
        )
    
    def enterEvent(self, event):
        """Mouse entered tile - show hover state."""
        self.is_hovered = True
        self.update()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Mouse left tile - hide hover state."""
        self.is_hovered = False
        self.update()
        super().leaveEvent(event)
    
    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse click."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.tile_id)
        super().mousePressEvent(event)

