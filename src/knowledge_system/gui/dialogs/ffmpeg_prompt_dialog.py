"""FFmpeg prompt dialog for feature-specific installation."""

from typing import Any

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QMessageBox,
)

from ...logger import get_logger
from .ffmpeg_setup_dialog import FFmpegSetupDialog

logger = get_logger(__name__)


class FFmpegPromptDialog(QDialog):
    """Dialog to prompt for FFmpeg installation when needed for specific features."""

    install_requested = pyqtSignal()
    learn_more_requested = pyqtSignal()
    
    def __init__(self, feature_name: str = "YouTube transcription", parent: Any = None) -> None:
        super().__init__(parent)
        self.feature_name = feature_name
        self._setup_ui()
        
    def _setup_ui(self) -> None:
        """Setup the prompt dialog UI."""
        self.setWindowTitle("FFmpeg Required")
        self.setModal(True)
        self.resize(450, 300)
        
        layout = QVBoxLayout(self)
        
        # Icon and title
        header_layout = QHBoxLayout()
        
        icon_label = QLabel("🎬")
        icon_label.setStyleSheet("font-size: 48px; margin-right: 15px;")
        header_layout.addWidget(icon_label)
        
        title_label = QLabel(f"FFmpeg Required for {self.feature_name}")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Description
        description = QLabel(
            f"To use {self.feature_name} features, FFmpeg needs to be installed.\n\n"
            "FFmpeg is a free, open-source tool for video and audio processing. "
            "It's safe to install and doesn't require administrator privileges."
        )
        description.setStyleSheet("font-size: 14px; margin: 15px 0; line-height: 1.4;")
        description.setWordWrap(True)
        layout.addWidget(description)
        
        # Benefits section
        benefits_frame = QFrame()
        benefits_frame.setFrameStyle(QFrame.Shape.Box)
        benefits_frame.setStyleSheet("""
            QFrame { 
                background-color: #f8f9fa; 
                border: 1px solid #e9ecef; 
                border-radius: 6px; 
                padding: 10px; 
                margin: 10px 0;
            }
        """)
        benefits_layout = QVBoxLayout(benefits_frame)
        
        benefits_title = QLabel("✨ What you'll get:")
        benefits_title.setStyleSheet("font-weight: bold; margin-bottom: 5px;")
        benefits_layout.addWidget(benefits_title)
        
        benefits_text = QLabel(
            "• Download and transcribe YouTube videos\n"
            "• Convert audio files between formats\n"
            "• Extract audio from video files\n"
            "• Full video processing capabilities"
        )
        benefits_text.setStyleSheet("margin-left: 10px; line-height: 1.3;")
        benefits_layout.addWidget(benefits_text)
        
        layout.addWidget(benefits_frame)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        not_now_button = QPushButton("Not Now")
        not_now_button.clicked.connect(self.reject)
        not_now_button.setStyleSheet("""
            QPushButton {
                padding: 8px 15px;
                font-size: 14px;
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                color: #6c757d;
            }
            QPushButton:hover {
                background-color: #e9ecef;
                color: #495057;
            }
        """)
        button_layout.addWidget(not_now_button)
        
        learn_more_button = QPushButton("Learn More")
        learn_more_button.clicked.connect(self._learn_more)
        learn_more_button.setStyleSheet("""
            QPushButton {
                padding: 8px 15px;
                font-size: 14px;
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        button_layout.addWidget(learn_more_button)
        
        install_button = QPushButton("Install Now")
        install_button.clicked.connect(self._install_now)
        install_button.setStyleSheet("""
            QPushButton {
                padding: 8px 15px;
                font-size: 14px;
                font-weight: bold;
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:pressed {
                background-color: #004085;
            }
        """)
        button_layout.addWidget(install_button)
        
        layout.addLayout(button_layout)
        
    def _learn_more(self) -> None:
        """Show learn more information."""
        QMessageBox.information(
            self,
            "About FFmpeg",
            "FFmpeg is a free, open-source software project that handles video, "
            "audio, and other multimedia files.\n\n"
            "• Used by major platforms like YouTube, Netflix, and Spotify\n"
            "• Completely safe and widely trusted\n"
            "• No administrator privileges required\n"
            "• Installs in your user directory only\n"
            "• Can be uninstalled anytime\n\n"
            "Knowledge Chipper uses FFmpeg to:\n"
            "• Download YouTube videos for transcription\n"
            "• Convert between audio formats\n"
            "• Extract audio tracks from video files\n"
            "• Analyze media file properties"
        )
        self.learn_more_requested.emit()
        
    def _install_now(self) -> None:
        """Start FFmpeg installation."""
        self.accept()
        
        # Show installation dialog
        install_dialog = FFmpegSetupDialog(self.parent())
        install_dialog.installation_completed.connect(self._installation_completed)
        install_dialog.exec()
        
    def _installation_completed(self, success: bool) -> None:
        """Handle installation completion."""
        if success:
            self.install_requested.emit()
        else:
            # Installation failed, user can try again later
            pass
