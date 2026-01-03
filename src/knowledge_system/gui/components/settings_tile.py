"""SettingsTile - Simple settings bar that spans full width.

Just shows "Settings" text with matching font style.
"""

from PyQt6.QtCore import Qt, pyqtSignal, QRect
from PyQt6.QtGui import QColor, QPainter, QFont, QLinearGradient, QPen, QBrush
from PyQt6.QtWidgets import QFrame


class SettingsHelpContactTile(QFrame):
    """
    Simple settings tile - just shows "Settings" text.
    
    Features:
    - Fixed 50px height (half of other tiles)
    - Single clickable area
    - Glassmorphism styling
    """
    
    # Signals
    settings_clicked = pyqtSignal()
    help_clicked = pyqtSignal()  # Kept for compatibility but not used
    contact_clicked = pyqtSignal()  # Kept for compatibility but not used
    
    def __init__(self, color: str = '#4A4A4A', parent=None):
        """
        Initialize settings tile.
        
        Args:
            color: Base color (default charcoal gray)
        """
        super().__init__(parent)
        
        self.color = color
        self.lighter_color = self._lighten_color(color, 0.15)
        self.is_hovered = False
        
        # Fixed height - half of other tiles
        self.setFixedHeight(50)
        
        # Enable mouse tracking
        self.setMouseTracking(True)
        
        # Set cursor
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    
    def _lighten_color(self, hex_color: str, amount: float) -> str:
        """Lighten a color by blending with white."""
        color = QColor(hex_color)
        white = QColor(255, 255, 255)
        r = int(color.red() + (white.red() - color.red()) * amount)
        g = int(color.green() + (white.green() - color.green()) * amount)
        b = int(color.blue() + (white.blue() - color.blue()) * amount)
        return QColor(r, g, b).name()
    
    def enterEvent(self, event):
        """Handle mouse enter."""
        self.is_hovered = True
        self.update()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Handle mouse leave."""
        self.is_hovered = False
        self.update()
        super().leaveEvent(event)
    
    def mousePressEvent(self, event):
        """Handle mouse click - emit settings_clicked."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.settings_clicked.emit()
        super().mousePressEvent(event)
    
    def paintEvent(self, event):
        """Custom paint with glassmorphism effect."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect().adjusted(1, 1, -1, -1)
        
        # === GLASSMORPHISM EFFECT ===
        gradient = QLinearGradient(0, 0, 0, self.height())
        
        if self.is_hovered:
            top_color = self._lighten_color(self.color, 0.30)
            mid_color = self._lighten_color(self.color, 0.12)
            bot_color = self._darken_color(self.color, 0.05)
        else:
            top_color = self._lighten_color(self.color, 0.20)
            mid_color = self.color
            bot_color = self._darken_color(self.color, 0.08)
        
        gradient.setColorAt(0.0, QColor(top_color))
        gradient.setColorAt(0.5, QColor(mid_color))
        gradient.setColorAt(1.0, QColor(bot_color))
        
        # Draw main shape
        painter.setBrush(gradient)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 8, 8)
        
        # Inner highlight (glass shine)
        highlight_rect = rect.adjusted(3, 2, -3, -int(self.height() * 0.5))
        highlight_gradient = QLinearGradient(0, highlight_rect.top(), 0, highlight_rect.bottom())
        highlight_gradient.setColorAt(0.0, QColor(255, 255, 255, 40))
        highlight_gradient.setColorAt(1.0, QColor(255, 255, 255, 0))
        
        painter.setBrush(highlight_gradient)
        painter.drawRoundedRect(highlight_rect, 6, 6)
        
        # Border effects
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(255, 255, 255, 60), 1))
        painter.drawLine(rect.left() + 8, rect.top(), rect.right() - 8, rect.top())
        
        painter.setPen(QPen(QColor(255, 255, 255, 20), 1))
        painter.drawRoundedRect(rect, 8, 8)
        
        # Draw "Settings" label - centered
        font = QFont()
        font.setPointSize(18)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))
        
        painter.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignCenter,
            "Settings"
        )
    
    def _darken_color(self, hex_color: str, amount: float) -> str:
        """Darken a color by the given amount."""
        color = QColor(hex_color)
        r = max(0, int(color.red() * (1 - amount)))
        g = max(0, int(color.green() * (1 - amount)))
        b = max(0, int(color.blue() * (1 - amount)))
        return QColor(r, g, b).name()
    
    def set_color(self, color: str):
        """Update tile color."""
        self.color = color
        self.lighter_color = self._lighten_color(color, 0.15)
        self.update()
