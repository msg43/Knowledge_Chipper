"""Settings Panel Content - API keys, models, account info, color customization.

Content for the Settings expansion panel.
"""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
    QGroupBox,
)


class SettingsPanelContent(QWidget):
    """
    Settings panel with API keys, model selection, and color customization.
    """
    
    color_customization_requested = pyqtSignal()
    
    def __init__(self, gui_settings, parent=None):
        super().__init__(parent)
        
        self.gui_settings = gui_settings
        
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self):
        """Setup the settings UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        # Make widgets visible
        self.setVisible(True)
        
        # Row 1: Model Selection - BIGGER, BLACKER
        model_layout = QHBoxLayout()
        model_layout.setSpacing(15)
        
        # Evaluator Model
        eval_label = QLabel("Evaluator Model:")
        eval_label.setStyleSheet("color: #000000; font-weight: bold; font-size: 14px;")
        self.evaluator_combo = QComboBox()
        self.evaluator_combo.addItems([
            "claude-3-7-sonnet-20250219",
            "gpt-4o",
            "gpt-4o-mini",
            "claude-3-5-haiku-20241022"
        ])
        self.evaluator_combo.setMinimumHeight(40)
        self.evaluator_combo.setStyleSheet("""
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
        """)
        
        # Summary Model
        summary_label = QLabel("Summary Model:")
        summary_label.setStyleSheet("color: #000000; font-weight: bold; font-size: 14px;")
        self.summary_combo = QComboBox()
        self.summary_combo.addItems([
            "claude-3-7-sonnet-20250219",
            "gpt-4o",
            "gpt-4o-mini",
            "claude-3-5-haiku-20241022"
        ])
        self.summary_combo.setMinimumHeight(40)
        self.summary_combo.setStyleSheet(self.evaluator_combo.styleSheet())
        
        model_layout.addWidget(eval_label)
        model_layout.addWidget(self.evaluator_combo, 1)
        model_layout.addSpacing(20)
        model_layout.addWidget(summary_label)
        model_layout.addWidget(self.summary_combo, 1)
        
        layout.addLayout(model_layout)
        
        # Row 2: GetReceipts Account + Colors Button - BIGGER
        account_layout = QHBoxLayout()
        account_layout.setSpacing(15)
        
        account_label = QLabel("GetReceipts Account:")
        account_label.setStyleSheet("color: #000000; font-weight: bold; font-size: 14px;")
        self.account_display = QLabel("Not connected")
        self.account_display.setStyleSheet("color: #000000; font-size: 13px; font-weight: 600;")
        
        # Color customization button - BIGGER
        self.colors_button = QPushButton("🎨 Customize Colors")
        self.colors_button.setMinimumHeight(45)
        self.colors_button.setStyleSheet("""
            QPushButton {
                background-color: #7EC8E3;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #6BB8D3;
            }
            QPushButton:pressed {
                background-color: #5AA8C3;
            }
        """)
        self.colors_button.clicked.connect(self.color_customization_requested.emit)
        
        account_layout.addWidget(account_label)
        account_layout.addWidget(self.account_display, 1)
        account_layout.addSpacing(20)
        account_layout.addWidget(self.colors_button)
        
        layout.addLayout(account_layout)
        
        layout.addStretch()
    
    def _load_settings(self):
        """Load saved settings."""
        # Load evaluator model
        eval_model = self.gui_settings.get_value(
            "Models",
            "flagship_evaluator_model",
            "claude-3-7-sonnet-20250219"
        )
        index = self.evaluator_combo.findText(eval_model)
        if index >= 0:
            self.evaluator_combo.setCurrentIndex(index)
        
        # Load summary model
        summary_model = self.gui_settings.get_value(
            "Models",
            "summary_model",
            "claude-3-7-sonnet-20250219"
        )
        index = self.summary_combo.findText(summary_model)
        if index >= 0:
            self.summary_combo.setCurrentIndex(index)
        
        # Load account info (placeholder - would load from auth service)
        # TODO: Wire to actual GetReceipts auth service
        self.account_display.setText("Not connected")
        
        # Connect change handlers
        self.evaluator_combo.currentTextChanged.connect(self._save_evaluator_model)
        self.summary_combo.currentTextChanged.connect(self._save_summary_model)
    
    def _save_evaluator_model(self, model: str):
        """Save evaluator model selection."""
        self.gui_settings.set_value("Models", "flagship_evaluator_model", model)
        self.gui_settings.save()
    
    def _save_summary_model(self, model: str):
        """Save summary model selection."""
        self.gui_settings.set_value("Models", "summary_model", model)
        self.gui_settings.save()


class HelpPanelContent(QWidget):
    """
    Help panel with getting started guide.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup help UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        # Make visible
        self.setVisible(True)
        
        help_text = QLabel(
            "<b style='font-size: 14px;'>🎯 Getting Started:</b><br><br>"
            "<b>1.</b> Click <b>Settings</b> to configure models and API keys<br>"
            "<b>2.</b> Drag files onto <b>Sources</b> or <b>Transcripts</b> tiles<br>"
            "<b>3.</b> Click green <b>START</b> button<br>"
            "<b>4.</b> Review <b>Claims</b> and <b>Summaries</b><br>"
            "<b>5.</b> Upload to <b>SkipThePodcast.com</b>"
        )
        help_text.setStyleSheet("""
            QLabel {
                color: #2d2d30;
                font-size: 13px;
                background-color: rgba(255, 255, 255, 0.5);
                padding: 10px;
                border-radius: 6px;
            }
        """)
        help_text.setWordWrap(True)
        
        layout.addWidget(help_text)
        layout.addStretch()

