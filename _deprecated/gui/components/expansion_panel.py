"""Expansion Panel that unrolls below clicked tiles.

Like a movie screen or paper scroll that smoothly unfolds.
"""

from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen, QFont
from PyQt6.QtWidgets import QFrame, QVBoxLayout


class ExpansionPanel(QFrame):
    """
    Expansion panel that unrolls below a tile.
    
    Features:
    - Starts at 0px height (rolled up)
    - Animates to 180px (unrolled)
    - Lighter color than parent tile (25% opacity)
    - Narrower than tile (95% width, indented)
    - Dashed line at top (perforation effect)
    - Smooth 300ms animation
    """
    
    start_processing = pyqtSignal(str, dict)  # tile_id, options
    expansion_changed = pyqtSignal(str, int)  # tile_id, height (0 or 300)
    
    def __init__(self, tile_id: str, base_color: str, parent=None):
        """
        Initialize expansion panel.
        
        Args:
            tile_id: ID of parent tile
            base_color: Parent tile's base color
        """
        super().__init__(parent)
        
        self.tile_id = tile_id
        self.base_color = base_color
        
        # Calculate lighter color (25% opacity effect)
        self.panel_color = self._lighten_color(base_color, 0.75)
        
        # Start rolled up (height = 0)
        self.setFixedHeight(0)
        
        # Set minimum and maximum sizes for animation
        self.rolled_height = 0
        self.unrolled_height = 300  # Increased to 300px to show all content properly
        
        # Apply styling
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {self.panel_color};
                border-radius: 0px 0px 8px 8px;
            }}
        """)
        
        # Content layout with better spacing
        self.content_layout = QVBoxLayout(self)
        self.content_layout.setContentsMargins(20, 20, 20, 15)  # More padding
        self.content_layout.setSpacing(12)  # More spacing
        
        # Animation for unrolling/rolling
        self.animation = QPropertyAnimation(self, b"maximumHeight")
        self.animation.setDuration(300)  # 300ms
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    
    def _lighten_color(self, hex_color: str, amount: float) -> str:
        """Lighten a hex color to simulate opacity."""
        color = QColor(hex_color)
        
        # Blend with white to simulate transparency
        white = QColor(255, 255, 255)
        r = int(color.red() * (1 - amount) + white.red() * amount)
        g = int(color.green() * (1 - amount) + white.green() * amount)
        b = int(color.blue() * (1 - amount) + white.blue() * amount)
        
        result = QColor(r, g, b)
        return result.name()
    
    def set_color(self, color: str):
        """Update panel color when parent tile color changes."""
        self.base_color = color
        self.panel_color = self._lighten_color(color, 0.75)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {self.panel_color};
                border-radius: 0px 0px 8px 8px;
            }}
        """)
        self.update()
    
    def unroll(self):
        """Animate panel unrolling (0 → 300px)."""
        self.animation.stop()
        self.animation.setStartValue(0)
        self.animation.setEndValue(self.unrolled_height)
        
        # Make sure content is visible
        for i in range(self.content_layout.count()):
            widget = self.content_layout.itemAt(i).widget()
            if widget:
                widget.show()
        
        self.animation.start()
        self.show()
        
        # Emit expansion changed signal
        self.expansion_changed.emit(self.tile_id, self.unrolled_height)
    
    def roll_up(self):
        """Animate panel rolling up (300px → 0)."""
        self.animation.stop()
        self.animation.setStartValue(self.unrolled_height)
        self.animation.setEndValue(0)
        
        # Emit expansion changed signal immediately
        self.expansion_changed.emit(self.tile_id, 0)
        
        # Hide after animation completes
        def on_finished():
            self.hide()
            # Disconnect to avoid multiple connections
            try:
                self.animation.finished.disconnect()
            except:
                pass
        
        self.animation.finished.connect(on_finished)
        self.animation.start()
    
    def is_unrolled(self) -> bool:
        """Check if panel is currently unrolled."""
        return self.height() > 0
    
    def paintEvent(self, event):
        """Custom paint to add dashed perforation line at top."""
        super().paintEvent(event)
        
        # Only draw if visible
        if self.height() > 0:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # Draw dashed line at top (perforation effect)
            pen = QPen(QColor(self.base_color))
            pen.setWidth(2)
            pen.setStyle(Qt.PenStyle.DashLine)
            pen.setColor(QColor(self.base_color))
            painter.setPen(pen)
            
            # Draw horizontal line near top
            painter.drawLine(10, 5, self.width() - 10, 5)


class FileListExpansionPanel(ExpansionPanel):
    """
    Expansion panel with file list and Start button.
    
    Used for Sources and Transcripts tiles.
    """
    
    def __init__(self, tile_id: str, base_color: str, parent=None):
        super().__init__(tile_id, base_color, parent)
        
        from PyQt6.QtWidgets import (
            QPushButton,
            QCheckBox,
            QHBoxLayout,
            QListWidget,
            QLabel,
            QFileDialog,
            QLineEdit,
        )
        
        # Top section: Browse button or URL input
        top_layout = QHBoxLayout()
        
        if tile_id == 'sources':
            # Browse files button - BOLD BLACK TEXT
            self.browse_button = QPushButton("📁 Choose Files")
            self.browse_button.setStyleSheet("""
                QPushButton {
                    background-color: white;
                    border: 2px solid #bbb;
                    border-radius: 8px;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: bold;
                    color: #000000;
                }
                QPushButton:hover {
                    background-color: #f5f5f5;
                    border-color: #888;
                }
            """)
            self.browse_button.clicked.connect(self._browse_files)
            top_layout.addWidget(self.browse_button)
            
            # "or drag and drop here" label - BLACK
            drag_label = QLabel("or drag and drop here")
            drag_label.setStyleSheet("color: #000000; font-size: 13px; font-weight: 600;")
            top_layout.addWidget(drag_label)
            top_layout.addStretch()
        elif tile_id == 'transcripts':
            # Top row: Two buttons side by side
            btn_style = """
                QPushButton {
                    background-color: white;
                    border: 2px solid #bbb;
                    border-radius: 8px;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: bold;
                    color: #000000;
                }
                QPushButton:hover {
                    background-color: #f5f5f5;
                    border-color: #888;
                }
            """
            
            # Choose Transcript Files button
            self.browse_button = QPushButton("📁 Choose Files")
            self.browse_button.setStyleSheet(btn_style)
            self.browse_button.clicked.connect(self._browse_transcripts)
            top_layout.addWidget(self.browse_button)
            
            # Import from Database button
            self.import_db_button = QPushButton("📥 Import from Database")
            self.import_db_button.setStyleSheet(btn_style)
            self.import_db_button.clicked.connect(self._import_from_database)
            top_layout.addWidget(self.import_db_button)
            
            # "or drag and drop here" label
            drag_label = QLabel("or drag and drop here")
            drag_label.setStyleSheet("color: #000000; font-size: 13px; font-weight: 600;")
            top_layout.addWidget(drag_label)
            
            top_layout.addStretch()
        
        self.content_layout.addLayout(top_layout)
        
        # Add URL input for Sources
        if tile_id == 'sources':
            self.url_input = QLineEdit()
            self.url_input.setPlaceholderText("Paste transcript URL...")
            self.url_input.setStyleSheet("""
                QLineEdit {
                    background-color: white;
                    border: 2px solid #ccc;
                    border-radius: 6px;
                    padding: 10px;
                    font-size: 14px;
                    color: #000000;
                }
                QLineEdit::placeholder {
                    color: #999;
                }
            """)
            self.content_layout.addWidget(self.url_input)
        
        # File list widget - "Recent Files" section
        if tile_id in ['sources', 'transcripts']:
            recent_label = QLabel("Recent Files")
            recent_label.setStyleSheet("color: #000000; font-size: 13px; font-weight: bold; margin-top: 5px;")
            self.content_layout.addWidget(recent_label)
        
        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(90)
        self.file_list.setStyleSheet("""
            QListWidget {
                background-color: white;
                border: 2px solid #ccc;
                border-radius: 6px;
                padding: 8px;
                font-size: 13px;
                color: #000000;
                font-weight: 600;
            }
            QListWidget::item {
                padding: 4px;
            }
        """)
        self.content_layout.addWidget(self.file_list)
        
        # YouTube matching checkbox (only for transcripts)
        if tile_id == 'transcripts':
            self.match_youtube_checkbox = QCheckBox("Try to Match with YouTube Metadata")
            self.match_youtube_checkbox.setChecked(True)  # Default is yes
            self.match_youtube_checkbox.setStyleSheet("""
                QCheckBox {
                    color: #000000;
                    font-size: 14px;
                    font-weight: bold;
                    spacing: 8px;
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
            """)
            self.content_layout.addWidget(self.match_youtube_checkbox)
        
        # Bottom section: Start Processing button + Cancel button + checkboxes
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(12)
        
        # Start Processing button (ORANGE like in mockup, bigger)
        self.start_button = QPushButton("Start Processing")
        self.start_button.setFixedHeight(50)
        self.start_button.setMinimumWidth(160)
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #FF8C00;
                color: white;
                font-size: 15px;
                font-weight: bold;
                border: none;
                border-radius: 10px;
                padding: 0 20px;
            }
            QPushButton:hover {
                background-color: #FF7700;
            }
            QPushButton:pressed {
                background-color: #FF6600;
            }
        """)
        self.start_button.clicked.connect(self._handle_start)
        bottom_layout.addWidget(self.start_button)
        
        # Cancel button (gray, same size)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setFixedHeight(50)
        self.cancel_button.setMinimumWidth(100)
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #999;
                color: white;
                font-size: 15px;
                font-weight: bold;
                border: none;
                border-radius: 10px;
                padding: 0 20px;
            }
            QPushButton:hover {
                background-color: #888;
            }
            QPushButton:pressed {
                background-color: #777;
            }
        """)
        bottom_layout.addWidget(self.cancel_button)
        
        # Checkboxes (stacked vertically to the right) - BIGGER AND BLACKER
        checkbox_layout = QVBoxLayout()
        checkbox_layout.setSpacing(6)
        
        self.checkbox_claims = QCheckBox("Create Claims")
        self.checkbox_summary = QCheckBox("Create Summary")
        self.checkbox_upload = QCheckBox("Upload")
        
        # All checked by default
        self.checkbox_claims.setChecked(True)
        self.checkbox_summary.setChecked(True)
        self.checkbox_upload.setChecked(True)
        
        # Style checkboxes - BLACK TEXT, BIGGER
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
        self.checkbox_claims.setStyleSheet(checkbox_style)
        self.checkbox_summary.setStyleSheet(checkbox_style)
        self.checkbox_upload.setStyleSheet(checkbox_style)
        
        checkbox_layout.addWidget(self.checkbox_claims)
        checkbox_layout.addWidget(self.checkbox_summary)
        checkbox_layout.addWidget(self.checkbox_upload)
        
        bottom_layout.addLayout(checkbox_layout)
        bottom_layout.addStretch()
        
        self.content_layout.addLayout(bottom_layout)
    
    def add_file(self, file_path: str):
        """Add a file to the list."""
        self.file_list.addItem(file_path)
    
    def clear_files(self):
        """Clear all files from the list."""
        self.file_list.clear()
    
    def get_files(self) -> list[str]:
        """Get list of files."""
        return [
            self.file_list.item(i).text()
            for i in range(self.file_list.count())
        ]
    
    def _browse_files(self):
        """Open file browser for source files."""
        from PyQt6.QtWidgets import QFileDialog
        
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Choose Source Files",
            "",
            "Media Files (*.mp3 *.mp4 *.wav *.m4a *.avi *.mov);;Documents (*.pdf *.txt *.docx);;All Files (*.*)"
        )
        
        for file in files:
            self.add_file(file)
    
    def _browse_transcripts(self):
        """Open file browser for transcript files."""
        from PyQt6.QtWidgets import QFileDialog
        
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Choose Transcript Files",
            "",
            "Transcript Files (*.txt *.json *.srt *.vtt);;All Files (*.*)"
        )
        
        for file in files:
            self.add_file(file)
    
    def _import_from_database(self):
        """Import existing transcripts from database."""
        # TODO: Show dialog to select existing transcripts from DB
        pass
    
    def _handle_start(self):
        """Emit start processing signal with options."""
        options = {
            'create_claims': self.checkbox_claims.isChecked(),
            'create_summary': self.checkbox_summary.isChecked(),
            'upload': self.checkbox_upload.isChecked(),
        }
        self.start_processing.emit(self.tile_id, options)


class SimpleExpansionPanel(ExpansionPanel):
    """
    Simple expansion panel with just buttons/controls.
    
    Used for Settings, Claims, Summaries, Cloud tiles.
    """
    
    def __init__(self, tile_id: str, base_color: str, parent=None):
        super().__init__(tile_id, base_color, parent)
        
        # Subclasses will add their own content via content_layout

