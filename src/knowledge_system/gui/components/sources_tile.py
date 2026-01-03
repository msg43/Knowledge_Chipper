"""Sources Tile - Droppable tile for source files.

Accepts MP3, YouTube URLs, RSS feeds, and text documents.
"""

from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QColor, QPainter, QFont, QLinearGradient, QPen, QBrush

from .droppable_tile import DroppableTile


class SourcesTile(DroppableTile):
    """
    Sources tile - step 1 in the pipeline.
    
    Simple text label: "I Have Sources to Transcribe"
    Entire tile accepts drag-drop for source files.
    """
    
    def __init__(self, color: str = '#6366F1', parent=None):
        # Initialize as droppable with all source extensions
        super().__init__(
            'sources',
            color,
            '',  # No icon - we draw step number
            'I Have Sources to Transcribe',
            accepted_extensions=[
                '.mp3', '.wav', '.m4a', '.flac', '.ogg',  # Audio
                '.mp4', '.avi', '.mov', '.mkv', '.webm',   # Video
                '.pdf', '.txt', '.docx', '.md', '.rtf'     # Documents
            ],
            parent=parent
        )
        
        self.drop_instructions = "Drag and drop source files here\n(Audio, Video, or Documents)"
    
    def paintEvent(self, event):
        """Custom paint with glassmorphism styling."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect().adjusted(1, 1, -1, -1)
        
        # === GLASSMORPHISM EFFECT ===
        gradient = QLinearGradient(0, 0, 0, self.height())
        
        if self.is_hovered or self.is_active or self.is_dragging:
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
        
        # Inner highlight (glass shine)
        highlight_rect = rect.adjusted(4, 4, -4, -int(self.height() * 0.6))
        highlight_gradient = QLinearGradient(0, highlight_rect.top(), 0, highlight_rect.bottom())
        highlight_gradient.setColorAt(0.0, QColor(255, 255, 255, 50))
        highlight_gradient.setColorAt(1.0, QColor(255, 255, 255, 0))
        
        painter.setBrush(highlight_gradient)
        painter.drawRoundedRect(highlight_rect, 8, 8)
        
        # Border effects
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(255, 255, 255, 80), 1))
        painter.drawLine(rect.left() + 12, rect.top(), rect.right() - 12, rect.top())
        
        painter.setPen(QPen(QColor(255, 255, 255, 25), 1))
        painter.drawRoundedRect(rect, 12, 12)
        
        # Draw content
        self._draw_content(painter)
        
        # Draw active indicator if processing
        if self.is_active:
            self._draw_active_indicator(painter)
        
        # Draw frosted overlay if dragging or hovering
        if self.is_dragging or self.show_frosted:
            self._draw_frosted_overlay()
    
    def _darken_color(self, hex_color: str, amount: float) -> str:
        """Darken a color by the given amount."""
        color = QColor(hex_color)
        r = max(0, int(color.red() * (1 - amount)))
        g = max(0, int(color.green() * (1 - amount)))
        b = max(0, int(color.blue() * (1 - amount)))
        return QColor(r, g, b).name()
    
    def _draw_content(self, painter: QPainter):
        """Draw step number 1 and label text."""
        # Draw step number "1" in circle on the left
        circle_x = 25
        circle_y = (self.height() - 50) // 2
        circle_size = 50
        
        # Draw circle with semi-transparent white fill
        painter.setPen(QPen(QColor(255, 255, 255, 100), 2))
        painter.setBrush(QBrush(QColor(255, 255, 255, 60)))
        painter.drawEllipse(circle_x, circle_y, circle_size, circle_size)
        
        # Draw "1"
        num_font = QFont()
        num_font.setPointSize(22)
        num_font.setBold(True)
        painter.setFont(num_font)
        painter.setPen(QColor(255, 255, 255))  # White text on dark background
        num_rect = QRect(circle_x, circle_y, circle_size, circle_size)
        painter.drawText(num_rect, Qt.AlignmentFlag.AlignCenter, "1")
        
        # Draw label text
        label_font = QFont()
        label_font.setPointSize(18)
        label_font.setBold(True)
        painter.setFont(label_font)
        painter.setPen(QColor(255, 255, 255))  # White on dark indigo
        
        label_rect = QRect(
            circle_x + circle_size + 20,
            0,
            self.width() - circle_x - circle_size - 40,
            self.height()
        )
        painter.drawText(
            label_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self.label
        )
    
    def _draw_active_indicator(self, painter: QPainter):
        """Draw pulsing border when active."""
        pen = QPen(QColor(255, 255, 255, 180), 3)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(2, 2, -2, -2), 10, 10)
