"""FFmpeg setup dialog for enhanced user experience."""

from pathlib import Path
from typing import Any

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from ...logger import get_logger
from ..workers.ffmpeg_installer import FFmpegInstaller

logger = get_logger(__name__)


class FFmpegSetupDialog(QDialog):
    """Friendly first-run FFmpeg setup dialog."""

    installation_completed = pyqtSignal(bool)  # success/failure

    def __init__(self, parent: Any = None) -> None:
        # CRITICAL: Testing safety check - prevent dialog creation during testing
        import os

        if os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE"):
            logger.error(
                "🧪 CRITICAL: Attempted to create FFmpegSetupDialog during testing mode - BLOCKED!"
            )
            raise RuntimeError(
                "FFmpegSetupDialog cannot be created during testing mode"
            )

        super().__init__(parent)
        self.ffmpeg_worker: FFmpegInstaller | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the dialog UI."""
        self.setWindowTitle("Optional Setup - FFmpeg")
        self.setModal(True)
        self.resize(500, 360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        # Header
        title = QLabel("🎬 Enable YouTube Transcription Features")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 4px 0;")
        layout.addWidget(title)

        # Description
        description = QLabel(
            "FFmpeg enables powerful YouTube video processing capabilities.\n"
            "Install now for the best experience, or skip and install later from Settings."
        )
        description.setStyleSheet("font-size: 14px; margin: 4px 0; color: #666;")
        description.setWordWrap(True)
        layout.addWidget(description)

        # Features section (compact, no white box)
        features_title = QLabel("✅ Features enabled with FFmpeg:")
        features_title.setStyleSheet("font-weight: bold; margin: 6px 0 2px 0;")
        layout.addWidget(features_title)

        features_list = QLabel(
            "• YouTube video downloads and transcription\n"
            "• Audio format conversions (MP3, WAV, etc.)\n"
            "• Video file audio extraction\n"
            "• Audio metadata and duration detection"
        )
        features_list.setStyleSheet("margin-left: 10px; line-height: 1.3;")
        layout.addWidget(features_list)

        without_title = QLabel("⚠️ Available without FFmpeg:")
        without_title.setStyleSheet("font-weight: bold; margin: 8px 0 2px 0;")
        layout.addWidget(without_title)

        without_list = QLabel(
            "• PDF processing and summarization\n"
            "• Text file processing\n"
            "• Local audio transcription (compatible formats)\n"
            "• All MOC generation features"
        )
        without_list.setStyleSheet("margin-left: 10px; line-height: 1.3; color: #666;")
        layout.addWidget(without_list)

        # Progress section (initially hidden)
        self.progress_frame = QFrame()
        self.progress_frame.setVisible(False)
        progress_layout = QVBoxLayout(self.progress_frame)

        self.progress_label = QLabel("Installing FFmpeg...")
        self.progress_label.setStyleSheet("font-weight: bold;")
        progress_layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_bar)

        self.progress_text = QTextEdit()
        self.progress_text.setMaximumHeight(100)
        self.progress_text.setStyleSheet(
            "font-family: 'Courier New', monospace; font-size: 11px;"
        )
        progress_layout.addWidget(self.progress_text)

        layout.addWidget(self.progress_frame)

        # Buttons
        button_layout = QHBoxLayout()

        self.skip_button = QPushButton("⏭️ Skip for Now")
        self.skip_button.clicked.connect(self._skip_setup)
        self.skip_button.setStyleSheet(
            """
            QPushButton {
                padding: 10px 20px;
                font-size: 14px;
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 4px;
                color: #000000;
            }
            QPushButton:hover {
                background-color: #e5e5e5;
                color: #000000;
            }
        """
        )
        button_layout.addWidget(self.skip_button)

        self.install_button = QPushButton("📥 Install FFmpeg Now")
        self.install_button.clicked.connect(self._start_installation)
        self.install_button.setStyleSheet(
            """
            QPushButton {
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
        """
        )
        button_layout.addWidget(self.install_button)

        layout.addLayout(button_layout)

    def _skip_setup(self) -> None:
        """User chose to skip FFmpeg setup."""
        self.reject()

    def _start_installation(self) -> None:
        """Start FFmpeg installation."""
        self.progress_frame.setVisible(True)
        self.install_button.setEnabled(False)
        self.skip_button.setText("Cancel")
        self.skip_button.clicked.disconnect()
        self.skip_button.clicked.connect(self._cancel_installation)

        # If ffmpeg already available, just set env and return quickly
        try:
            import os as _os
            import shutil as _shutil

            existing = _shutil.which("ffmpeg")
            if existing:
                _os.environ["FFMPEG_PATH"] = existing
                ffprobe_existing = _shutil.which("ffprobe")
                if ffprobe_existing:
                    _os.environ["FFPROBE_PATH"] = ffprobe_existing
                self.progress_label.setText("✅ FFmpeg already installed - configuring…")
                self.progress_bar.setValue(100)
                self.installation_completed.emit(True)
                self.accept()
                return
        except Exception:
            pass

        # Start installation
        self.ffmpeg_worker = FFmpegInstaller()
        self.ffmpeg_worker.progress_updated.connect(self._update_progress)
        self.ffmpeg_worker.installation_finished.connect(self._installation_finished)
        self.ffmpeg_worker.start()

    def _update_progress(self, message: str, percentage: int = -1) -> None:
        """Update installation progress."""
        self.progress_label.setText(message)
        if percentage >= 0:
            self.progress_bar.setValue(percentage)
        else:
            self.progress_bar.setRange(0, 0)  # Indeterminate

        # Add to progress text
        scrollbar = self.progress_text.verticalScrollBar()
        # Check if we should auto-scroll BEFORE appending
        should_scroll = scrollbar and scrollbar.value() >= scrollbar.maximum() - 10

        self.progress_text.append(message)

        # Only auto-scroll if user was already at the bottom
        if should_scroll and scrollbar:
            scrollbar.setValue(scrollbar.maximum())

    def _installation_finished(self, success: bool, message: str) -> None:
        """Handle installation completion."""
        if success:
            self.progress_label.setText("✅ FFmpeg installed successfully!")
            self.progress_bar.setValue(100)
            # Best-effort: expose installed paths for this app session so
            # components that rely on environment variables can discover FFmpeg
            try:
                import os

                bin_dir = (
                    Path.home()
                    / "Library"
                    / "Application Support"
                    / "Knowledge_Chipper"
                    / "bin"
                )
                ffmpeg_path = bin_dir / "ffmpeg"
                ffprobe_path = bin_dir / "ffprobe"
                if ffmpeg_path.exists():
                    os.environ["FFMPEG_PATH"] = str(ffmpeg_path)
                if ffprobe_path.exists():
                    os.environ["FFPROBE_PATH"] = str(ffprobe_path)
                # Also prepend to PATH for subprocess-based which() checks
                current_path = os.environ.get("PATH", "")
                if str(bin_dir) not in current_path:
                    os.environ["PATH"] = (
                        f"{bin_dir}:{current_path}" if current_path else str(bin_dir)
                    )
            except Exception:
                pass
            QMessageBox.information(
                self,
                "Installation Complete",
                "FFmpeg has been installed successfully!\n\n"
                "You can now use all YouTube transcription features.",
            )
            self.installation_completed.emit(True)
            self.accept()
        else:
            self.progress_label.setText("❌ Installation failed")
            QMessageBox.warning(
                self,
                "Installation Failed",
                f"FFmpeg installation failed:\n\n{message}\n\n"
                "You can try again later from Settings → Install/Update FFmpeg.",
            )
            self.installation_completed.emit(False)
            self._reset_ui()

    def _cancel_installation(self) -> None:
        """Cancel ongoing installation."""
        if self.ffmpeg_worker and self.ffmpeg_worker.isRunning():
            self.ffmpeg_worker.terminate()
            self.ffmpeg_worker.wait()
        self._reset_ui()

    def _reset_ui(self) -> None:
        """Reset UI to initial state."""
        self.progress_frame.setVisible(False)
        self.install_button.setEnabled(True)
        self.skip_button.setText("⏭️ Skip for Now")
        self.skip_button.clicked.disconnect()
        self.skip_button.clicked.connect(self._skip_setup)
