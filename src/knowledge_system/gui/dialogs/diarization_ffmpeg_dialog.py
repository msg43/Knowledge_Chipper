"""FFMPEG installation dialog specifically for diarization requirements."""

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


class DiarizationFFmpegDialog(QDialog):
    """Dialog for FFMPEG installation required for cloud transcription with diarization."""

    installation_completed = pyqtSignal(bool)  # success/failure

    def __init__(self, parent: Any = None) -> None:
        # CRITICAL: Testing safety check - prevent dialog creation during testing
        import os

        if os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE"):
            logger.error(
                "🧪 CRITICAL: Attempted to create DiarizationFFmpegDialog during testing mode - BLOCKED!"
            )
            raise RuntimeError(
                "DiarizationFFmpegDialog cannot be created during testing mode"
            )

        super().__init__(parent)
        self.ffmpeg_worker: FFmpegInstaller | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the dialog UI."""
        self.setWindowTitle("Required Setup - FFmpeg for Diarization")
        self.setModal(True)
        self.resize(550, 420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # Header
        title = QLabel("🎙️ FFmpeg Required for Cloud Transcription with Diarization")
        title.setStyleSheet(
            "font-size: 18px; font-weight: bold; margin: 6px 0; color: #1976D2;"
        )
        title.setWordWrap(True)
        layout.addWidget(title)

        # Description
        description = QLabel(
            "You've selected diarization (speaker identification) for cloud transcription. "
            "This requires FFmpeg to process audio from YouTube videos.\n\n"
            "FFmpeg is not currently installed on your system."
        )
        description.setStyleSheet(
            "font-size: 14px; margin: 6px 0; color: #333; line-height: 1.4;"
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        # What happens section
        what_happens_title = QLabel("🔄 What happens with FFmpeg:")
        what_happens_title.setStyleSheet(
            "font-weight: bold; margin: 12px 0 4px 0; color: #2196F3;"
        )
        layout.addWidget(what_happens_title)

        what_happens_list = QLabel(
            "• Downloads YouTube video audio for speaker analysis\n"
            "• Converts audio to optimal format for diarization\n"
            "• Enables high-quality speaker identification\n"
            "• Required for cloud transcription with speaker separation"
        )
        what_happens_list.setStyleSheet(
            "margin-left: 12px; line-height: 1.4; color: #555;"
        )
        layout.addWidget(what_happens_list)

        # Options section
        options_title = QLabel("⚙️ Your options:")
        options_title.setStyleSheet(
            "font-weight: bold; margin: 12px 0 4px 0; color: #FF9800;"
        )
        layout.addWidget(options_title)

        options_list = QLabel(
            "• Install FFmpeg now (recommended) - enables full functionality\n"
            "• Cancel and disable diarization - proceed without speaker identification\n"
            "• Cancel and install FFmpeg later from Settings → Install/Update FFmpeg"
        )
        options_list.setStyleSheet("margin-left: 12px; line-height: 1.4; color: #555;")
        layout.addWidget(options_list)

        # Note section
        note = QLabel(
            "💡 Note: All your current selections will be preserved regardless of your choice."
        )
        note.setStyleSheet(
            "font-style: italic; margin: 8px 0; color: #666; padding: 8px; background-color: #f5f5f5; border-radius: 4px;"
        )
        note.setWordWrap(True)
        layout.addWidget(note)

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
        self.progress_text.setMaximumHeight(80)
        self.progress_text.setStyleSheet(
            "font-family: 'Courier New', monospace; font-size: 11px;"
        )
        progress_layout.addWidget(self.progress_text)

        layout.addWidget(self.progress_frame)

        # Buttons
        button_layout = QHBoxLayout()

        self.cancel_button = QPushButton("❌ Cancel Transcription")
        self.cancel_button.clicked.connect(self._cancel_transcription)
        self.cancel_button.setStyleSheet(
            """
            QPushButton {
                padding: 12px 20px;
                font-size: 14px;
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 6px;
                color: #333;
            }
            QPushButton:hover {
                background-color: #e5e5e5;
                color: #000;
            }
        """
        )
        button_layout.addWidget(self.cancel_button)

        self.install_button = QPushButton("📥 Install FFmpeg & Continue")
        self.install_button.clicked.connect(self._start_installation)
        self.install_button.setStyleSheet(
            """
            QPushButton {
                padding: 12px 20px;
                font-size: 14px;
                font-weight: bold;
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 6px;
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

    def _cancel_transcription(self) -> None:
        """User chose to cancel transcription."""
        self.reject()

    def _start_installation(self) -> None:
        """Start FFmpeg installation."""
        self.progress_frame.setVisible(True)
        self.install_button.setEnabled(False)
        self.cancel_button.setText("Cancel Installation")
        self.cancel_button.clicked.disconnect()
        self.cancel_button.clicked.connect(self._cancel_installation)

        # Resize dialog to accommodate progress section
        self.resize(550, 500)

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
                self.progress_label.setText(
                    "✅ FFmpeg already installed - configuring…"
                )
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
        self.progress_text.append(message)
        self.progress_text.verticalScrollBar().setValue(
            self.progress_text.verticalScrollBar().maximum()
        )

    def _installation_finished(self, success: bool, message: str) -> None:
        """Handle installation completion."""
        if success:
            self.progress_label.setText("✅ FFmpeg installed successfully!")
            self.progress_bar.setValue(100)
            # Best-effort: expose installed paths for this app session
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
                "Continuing with cloud transcription and diarization...",
            )
            self.installation_completed.emit(True)
            self.accept()
        else:
            self.progress_label.setText("❌ Installation failed")
            QMessageBox.warning(
                self,
                "Installation Failed",
                f"FFmpeg installation failed:\n\n{message}\n\n"
                "You can:\n"
                "• Try again later from Settings → Install/Update FFmpeg\n"
                "• Continue without diarization\n"
                "• Cancel this transcription",
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
        self.cancel_button.setText("❌ Cancel Transcription")
        self.cancel_button.clicked.disconnect()
        self.cancel_button.clicked.connect(self._cancel_transcription)
        self.resize(550, 420)
