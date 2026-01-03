"""Color Customization Dialog - Choose colors for each tile.

8 presets + custom color picker with live preview.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QColorDialog,
    QGridLayout,
    QGroupBox,
)
from PyQt6.QtGui import QColor


# 8 Color Presets
COLOR_PRESETS = {
    "Default": {
        'settings': '#9E9E9E',
        'sources': '#B39DDB',
        'transcripts': '#FFB74D',
        'claims': '#A5D6A7',
        'summaries': '#F4A5A5',
        'cloud': '#7EC8E3',
    },
    "Ocean": {
        'settings': '#78909C',
        'sources': '#4DB6AC',
        'transcripts': '#4FC3F7',
        'claims': '#81C784',
        'summaries': '#64B5F6',
        'cloud': '#0277BD',
    },
    "Forest": {
        'settings': '#A1887F',
        'sources': '#AED581',
        'transcripts': '#DCE775',
        'claims': '#66BB6A',
        'summaries': '#9CCC65',
        'cloud': '#7CB342',
    },
    "Sunset": {
        'settings': '#90A4AE',
        'sources': '#FFCA28',
        'transcripts': '#FFA726',
        'claims': '#FF7043',
        'summaries': '#EF5350',
        'cloud': '#EC407A',
    },
    "Monochrome": {
        'settings': '#BDBDBD',
        'sources': '#9E9E9E',
        'transcripts': '#757575',
        'claims': '#616161',
        'summaries': '#424242',
        'cloud': '#212121',
    },
    "High Contrast": {
        'settings': '#000000',
        'sources': '#E91E63',
        'transcripts': '#FF9800',
        'claims': '#4CAF50',
        'summaries': '#2196F3',
        'cloud': '#9C27B0',
    },
    "Pastel": {
        'settings': '#D7CCC8',
        'sources': '#E1BEE7',
        'transcripts': '#FFCCBC',
        'claims': '#C5E1A5',
        'summaries': '#F8BBD0',
        'cloud': '#B2EBF2',
    },
    "Waterfall": {
        'settings': '#B0BEC5',
        'sources': '#7986CB',
        'transcripts': '#64B5F6',
        'claims': '#4FC3F7',
        'summaries': '#4DD0E1',
        'cloud': '#26C6DA',
    },
}


class ColorButton(QPushButton):
    """Button that shows and selects a color."""
    
    color_changed = pyqtSignal(str)  # hex color
    
    def __init__(self, initial_color: str, label: str, parent=None):
        super().__init__(parent)
        
        self.label = label
        self.current_color = initial_color
        
        self.setFixedSize(100, 40)
        self._update_style()
        
        self.clicked.connect(self._choose_color)
    
    def _update_style(self):
        """Update button style to show current color."""
        # Calculate text color (dark or light based on background)
        color = QColor(self.current_color)
        luminance = (0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()) / 255
        text_color = "#2d2d30" if luminance > 0.5 else "#E0E0E0"
        
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.current_color};
                color: {text_color};
                border: 2px solid #ccc;
                border-radius: 6px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                border: 2px solid #666;
            }}
        """)
        
        self.setText(self.label)
    
    def set_color(self, color: str):
        """Set button color."""
        self.current_color = color
        self._update_style()
    
    def get_color(self) -> str:
        """Get current color."""
        return self.current_color
    
    def _choose_color(self):
        """Open color picker dialog."""
        color = QColorDialog.getColor(
            QColor(self.current_color),
            self,
            f"Choose {self.label} Color"
        )
        
        if color.isValid():
            self.current_color = color.name()
            self._update_style()
            self.color_changed.emit(self.current_color)


class ColorCustomizationDialog(QDialog):
    """
    Dialog for customizing tile colors.
    
    Features:
    - 8 preset themes
    - Individual color pickers for each tile
    - Live preview (if parent supports it)
    - Save/Cancel
    """
    
    colors_updated = pyqtSignal(dict)  # {tile_id: color}
    
    def __init__(self, current_colors: dict, parent=None):
        super().__init__(parent)
        
        self.current_colors = current_colors.copy()
        self.original_colors = current_colors.copy()
        
        self.setWindowTitle("Customize Tile Colors")
        self.setModal(True)
        self.setMinimumWidth(500)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Presets section
        presets_group = QGroupBox("Color Presets")
        presets_layout = QGridLayout()
        
        preset_names = list(COLOR_PRESETS.keys())
        for i, name in enumerate(preset_names):
            row = i // 4
            col = i % 4
            
            btn = QPushButton(name)
            btn.setFixedSize(110, 35)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #f5f5f5;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                }
            """)
            btn.clicked.connect(lambda checked, n=name: self._apply_preset(n))
            presets_layout.addWidget(btn, row, col)
        
        presets_group.setLayout(presets_layout)
        layout.addWidget(presets_group)
        
        # Custom colors section
        custom_group = QGroupBox("Custom Colors (Click to Change)")
        custom_layout = QGridLayout()
        custom_layout.setSpacing(10)
        
        # Create color buttons for each tile
        self.color_buttons = {}
        
        tiles = [
            ('settings', 'Settings'),
            ('sources', 'Sources'),
            ('transcripts', 'Transcripts'),
            ('claims', 'Claims'),
            ('summaries', 'Summaries'),
            ('cloud', 'Cloud'),
        ]
        
        for i, (tile_id, label) in enumerate(tiles):
            row = i // 3
            col = i % 3
            
            color = self.current_colors.get(tile_id, '#9E9E9E')
            btn = ColorButton(color, label)
            btn.color_changed.connect(lambda c, tid=tile_id: self._color_changed(tid, c))
            
            self.color_buttons[tile_id] = btn
            custom_layout.addWidget(btn, row, col)
        
        custom_group.setLayout(custom_layout)
        layout.addWidget(custom_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(100, 35)
        cancel_btn.clicked.connect(self.reject)
        
        save_btn = QPushButton("Apply")
        save_btn.setFixedSize(100, 35)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45A049;
            }
        """)
        save_btn.clicked.connect(self.accept)
        
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
    
    def _apply_preset(self, preset_name: str):
        """Apply a color preset."""
        preset = COLOR_PRESETS[preset_name]
        
        for tile_id, color in preset.items():
            self.current_colors[tile_id] = color
            if tile_id in self.color_buttons:
                self.color_buttons[tile_id].set_color(color)
        
        # Emit for live preview
        self.colors_updated.emit(self.current_colors)
    
    def _color_changed(self, tile_id: str, color: str):
        """Handle individual color change."""
        self.current_colors[tile_id] = color
        
        # Emit for live preview
        self.colors_updated.emit(self.current_colors)
    
    def get_colors(self) -> dict:
        """Get selected colors."""
        return self.current_colors.copy()
    
    def reject(self):
        """Cancel - restore original colors."""
        self.colors_updated.emit(self.original_colors)
        super().reject()

