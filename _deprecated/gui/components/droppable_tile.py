"""Droppable LayerTile with drag-drop support and frosted overlay.

Used for Sources and Transcripts tiles where users can drag files directly onto the tile.
"""

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QPainter, QColor, QFont
from PyQt6.QtWidgets import QWidget

from .layer_tile import LayerTile


class DroppableTile(LayerTile):
    """
    Layer tile that accepts drag-drop files.
    
    Features:
    - All LayerTile features
    - Drag-drop file acceptance
    - Frosted overlay on hover during drag
    - File validation
    - Visual feedback
    """
    
    files_dropped = pyqtSignal(str, list)  # tile_id, file_paths
    
    def __init__(
        self,
        tile_id: str,
        color: str,
        icon: str,
        label: str,
        accepted_extensions: list[str] = None,
        parent=None
    ):
        """
        Initialize droppable tile.
        
        Args:
            tile_id: Unique identifier
            color: Base color hex string
            icon: Icon string
            label: Display label
            accepted_extensions: List of accepted file extensions (e.g. ['.mp3', '.wav'])
                                If None, accepts all files
        """
        super().__init__(tile_id, color, icon, label, parent)
        
        self.accepted_extensions = accepted_extensions or []
        self.is_dragging = False
        self.show_frosted = False  # Show frosted overlay on hover
        
        # Enable drop events and mouse tracking
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        
        # Instructions text for frosted overlay
        if tile_id == 'sources':
            self.drop_instructions = "Drag and drop or click to add sources\nwhich will be used to create transcripts"
        elif tile_id == 'transcripts':
            self.drop_instructions = "Drag and drop or click to add transcripts\nin .txt or .json format"
        else:
            self.drop_instructions = "Drag and drop files here"
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter - check if files are acceptable."""
        if event.mimeData().hasUrls():
            # Check if any files have acceptable extensions
            urls = event.mimeData().urls()
            files = [url.toLocalFile() for url in urls]
            
            if self._validate_files(files):
                event.acceptProposedAction()
                self.is_dragging = True
                self.update()  # Show frosted overlay
            else:
                event.ignore()
        else:
            event.ignore()
    
    def dragLeaveEvent(self, event):
        """Handle drag leave - hide frosted overlay."""
        self.is_dragging = False
        self.update()
        super().dragLeaveEvent(event)
    
    def dropEvent(self, event: QDropEvent):
        """Handle file drop."""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            files = [url.toLocalFile() for url in urls if url.isLocalFile()]
            
            # Validate files
            valid_files = self._get_valid_files(files)
            
            if valid_files:
                self.files_dropped.emit(self.tile_id, valid_files)
                event.acceptProposedAction()
            
            # Hide frosted overlay
            self.is_dragging = False
            self.update()
    
    def _validate_files(self, files: list[str]) -> bool:
        """Check if at least one file has acceptable extension."""
        if not self.accepted_extensions:
            return True  # Accept all files if no restrictions
        
        for file_path in files:
            path = Path(file_path)
            if path.suffix.lower() in self.accepted_extensions:
                return True
        
        return False
    
    def _get_valid_files(self, files: list[str]) -> list[str]:
        """Filter files to only valid ones."""
        if not self.accepted_extensions:
            return files  # All files valid if no restrictions
        
        valid = []
        for file_path in files:
            path = Path(file_path)
            if path.suffix.lower() in self.accepted_extensions:
                valid.append(file_path)
        
        return valid
    
    def enterEvent(self, event):
        """Handle mouse enter - show frosted overlay."""
        super().enterEvent(event)
        self.show_frosted = True
        self.update()
    
    def leaveEvent(self, event):
        """Handle mouse leave - hide frosted overlay."""
        super().leaveEvent(event)
        self.show_frosted = False
        self.update()
    
    def paintEvent(self, event):
        """Custom paint with frosted overlay when hovering or dragging."""
        # Draw base tile
        super().paintEvent(event)
        
        # Draw frosted overlay if hovering or dragging
        if self.is_dragging or self.show_frosted:
            self._draw_frosted_overlay()
    
    def _draw_frosted_overlay(self):
        """Draw semi-transparent frosted overlay with instructions."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Semi-transparent white overlay
        overlay_color = QColor(255, 255, 255, 200)  # 78% opacity
        painter.fillRect(self.rect(), overlay_color)
        
        # Draw border glow
        pen_color = QColor(self.color)
        pen_color.setAlpha(255)
        painter.setPen(pen_color)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(
            self.rect().adjusted(4, 4, -4, -4),
            10, 10
        )
        
        # Draw instructions text - BIGGER, BLACK
        painter.setPen(QColor("#000000"))
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        painter.setFont(font)
        
        # Center the text
        text_rect = self.rect().adjusted(20, 20, -20, -20)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            self.drop_instructions
        )


class FrostedOverlay(QWidget):
    """
    Standalone frosted overlay widget.
    
    Can be placed over any widget to show drag-drop instructions.
    """
    
    def __init__(self, instructions: str, color: str, parent=None):
        super().__init__(parent)
        self.instructions = instructions
        self.color = color
        
        # Make transparent to clicks
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        # Hide by default
        self.hide()
    
    def paintEvent(self, event):
        """Draw frosted overlay."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Semi-transparent white background
        painter.fillRect(self.rect(), QColor(255, 255, 255, 200))
        
        # Border glow
        pen = painter.pen()
        pen.setColor(QColor(self.color))
        pen.setWidth(3)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(
            self.rect().adjusted(4, 4, -4, -4),
            10, 10
        )
        
        # Instructions text
        painter.setPen(QColor("#2d2d30"))
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        
        text_rect = self.rect().adjusted(20, 20, -20, -20)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            self.instructions
        )

