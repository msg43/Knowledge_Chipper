"""Custom dialog components for the knowledge system GUI."""

from typing import Any

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QCloseEvent, QFont
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from knowledge_system.logger import get_logger
from knowledge_system.utils.ollama_manager import (
    DownloadProgress,
    InstallationProgress,
    get_ollama_manager,
)
from knowledge_system.utils.progress import (
    CancellationToken,
    ExtractionProgress,
    MOCProgress,
    SummarizationProgress,
    TranscriptionProgress,
)

from .assets.icons import get_app_icon

logger = get_logger(__name__)


class OllamaInstallDialog(QDialog):
    """Dialog for installing Ollama with progress tracking."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Install Ollama")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setMinimumHeight(300)

        # Set custom icon
        custom_icon = get_app_icon()
        if custom_icon:
            self.setWindowIcon(custom_icon)

        self.install_worker: OllamaInstallWorker | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Header
        header_label = QLabel("🤖 Install Ollama")
        header_font = QFont()
        header_font.setPointSize(16)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header_label)

        # Description
        desc_label = QLabel(
            "Ollama is not installed on your system. Ollama is required to run local AI models.\n\n"
            "This will download and install Ollama from the official source (ollama.com).\n"
            "Installation size: ~50MB\n\n"
            "Would you like to install Ollama now?"
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("QLabel { padding: 10px; }")
        layout.addWidget(desc_label)

        # Progress section (initially hidden)
        self.progress_widget = QVBoxLayout()

        self.progress_label = QLabel("Ready to install...")
        self.progress_widget.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_widget.addWidget(self.progress_bar)

        self.step_label = QLabel("")
        self.step_label.setVisible(False)
        self.progress_widget.addWidget(self.step_label)

        layout.addLayout(self.progress_widget)

        # Buttons
        self.button_layout = QHBoxLayout()

        self.install_btn = QPushButton("📥 Install Ollama")
        self.install_btn.clicked.connect(self._start_installation)
        self.button_layout.addWidget(self.install_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.button_layout.addWidget(self.cancel_btn)

        layout.addLayout(self.button_layout)

    def _start_installation(self):
        """Start the Ollama installation process."""
        self.install_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.step_label.setVisible(True)

        # Start installation worker
        self.install_worker = OllamaInstallWorker()
        self.install_worker.progress_updated.connect(self._update_progress)
        self.install_worker.install_finished.connect(self._install_finished)
        self.install_worker.install_error.connect(self._install_error)
        self.install_worker.start()

    def _update_progress(self, progress: InstallationProgress):
        """Update the installation progress display."""
        self.progress_bar.setValue(int(progress.percent))
        self.step_label.setText(progress.current_step)

        if progress.status == "downloading" and progress.total > 0:
            mb_completed = progress.completed // (1024 * 1024)
            mb_total = progress.total // (1024 * 1024)
            self.progress_label.setText(
                f"📥 Downloading: {mb_completed}MB / {mb_total}MB"
            )
        elif progress.status == "extracting":
            self.progress_label.setText("📦 Extracting installer...")
        elif progress.status == "installing":
            self.progress_label.setText("⚙️ Installing Ollama...")
        elif progress.status == "completed":
            self.progress_label.setText("✅ Installation completed!")

    def _install_finished(self):
        """Handle successful installation completion."""
        self.progress_bar.setValue(100)
        self.progress_label.setText("✅ Ollama installed successfully!")
        self.step_label.setText("You can now use local AI models.")

        self.install_btn.setText("✅ Installed")
        self.cancel_btn.setText("Close")

        # Auto-close after 3 seconds
        QTimer.singleShot(3000, self.accept)

    def _install_error(self, error_msg: str):
        """Handle installation error."""
        self.progress_label.setText(f"❌ Installation failed: {error_msg}")
        self.step_label.setText("You can try again or install manually from ollama.com")
        self.install_btn.setText("Retry Installation")
        self.install_btn.setEnabled(True)
        self.cancel_btn.setText("Close")

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle dialog close event."""
        if self.install_worker and self.install_worker.isRunning():
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Icon.Question)
            msg_box.setWindowTitle("Cancel Installation")
            msg_box.setText(
                "Installation is in progress. Are you sure you want to cancel?"
            )
            msg_box.setStandardButtons(
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            # Set custom window icon
            custom_icon = get_app_icon()
            if custom_icon:
                msg_box.setWindowIcon(custom_icon)

            reply = msg_box.exec()
            if reply == QMessageBox.StandardButton.Yes:
                self.install_worker.terminate()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


class OllamaInstallWorker(QThread):
    """Worker thread for installing Ollama."""

    progress_updated = pyqtSignal(object)  # InstallationProgress
    install_finished = pyqtSignal()
    install_error = pyqtSignal(str)

    def run(self):
        """Run the installation process."""
        try:
            manager = get_ollama_manager()

            def progress_callback(progress: InstallationProgress):
                """Progress callback."""
                self.progress_updated.emit(progress)

            success, message = manager.install_ollama_macos(progress_callback)

            if success:
                self.install_finished.emit()
            else:
                self.install_error.emit(message)

        except Exception as e:
            logger.error(f"Install worker error: {e}")
            self.install_error.emit(str(e))


class ModelDownloadDialogLegacy(QDialog):
    """Dialog for downloading Ollama models with progress tracking.

    Note: Renamed to avoid name collision with the newer ModelDownloadDialog below.
    """

    def __init__(self, model_name: str, model_info, parent=None) -> None:
        super().__init__(parent)
        self.model_name = model_name
        self.model_info = model_info
        self.download_worker: ModelDownloadWorker | None = None

        self.setWindowTitle("Download AI Model")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Header
        header_label = QLabel("🤖 AI Model Download")
        header_font = QFont()
        header_font.setPointSize(16)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header_label)

        # Model info
        info_text = f"""
<h3>{self.model_name}</h3>
<p><b>Size:</b> {self.model_info.size_display}</p>
<p><b>Format:</b> {self.model_info.format}</p>
<p><b>Quantization:</b> {self.model_info.quantization}</p>

<p>This model is not currently downloaded on your system.
Would you like to download it now?</p>

<p><i>Note: This is a one-time download. The model will be stored locally
and available for future use.</i></p>
        """

        info_label = QLabel(info_text)
        info_label.setWordWrap(True)
        info_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(info_label)

        # Progress section (initially hidden)
        self.progress_widget = QVBoxLayout()

        self.progress_label = QLabel("Preparing download...")
        self.progress_widget.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_widget.addWidget(self.progress_bar)

        self.speed_label = QLabel("")
        self.progress_widget.addWidget(self.speed_label)

        layout.addLayout(self.progress_widget)

        # Hide progress initially
        self._set_progress_visible(False)

        # Buttons
        button_layout = QHBoxLayout()

        self.download_btn = QPushButton("📥 Download Model")
        self.download_btn.setStyleSheet(
            "background-color: #4caf50; font-weight: bold; padding: 8px;"
        )
        self.download_btn.clicked.connect(self._start_download)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)

        button_layout.addWidget(self.download_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)

    def _set_progress_visible(self, visible: bool):
        """Show/hide progress widgets."""
        self.progress_label.setVisible(visible)
        self.progress_bar.setVisible(visible)
        self.speed_label.setVisible(visible)

    def _start_download(self):
        """Start the model download process."""
        self.download_btn.setText("Downloading...")
        self.download_btn.setEnabled(False)
        self.cancel_btn.setText("Cancel Download")

        self._set_progress_visible(True)

        # Start download worker
        self.download_worker = ModelDownloadWorker(self.model_name)
        self.download_worker.progress_updated.connect(self._update_progress)
        self.download_worker.download_finished.connect(self._download_finished)
        self.download_worker.download_error.connect(self._download_error)
        self.download_worker.start()

    def _update_progress(self, progress: DownloadProgress):
        """Update progress display."""
        self.progress_label.setText(f"Status: {progress.status}")

        if progress.total > 0:
            self.progress_bar.setValue(int(progress.percent))

            if progress.speed_mbps > 0:
                speed_text = f"Speed: {progress.speed_mbps:.1f} MB/s"
                if progress.eta_seconds:
                    minutes = progress.eta_seconds // 60
                    seconds = progress.eta_seconds % 60
                    speed_text += f" | ETA: {minutes}m {seconds}s"
                self.speed_label.setText(speed_text)

    def _download_finished(self):
        """Handle successful download completion."""
        self.progress_bar.setValue(100)
        self.progress_label.setText("✅ Download completed successfully!")
        self.speed_label.setText("")

        self.download_btn.setText("✅ Downloaded")
        self.cancel_btn.setText("Close")

        # Auto-close after 2 seconds
        QTimer.singleShot(2000, self.accept)

    def _download_error(self, error_msg: str):
        """Handle download error."""
        self.progress_label.setText(f"❌ Download failed: {error_msg}")
        self.download_btn.setText("Retry Download")
        self.download_btn.setEnabled(True)
        self.cancel_btn.setText("Close")

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle dialog close event."""
        if self.download_worker and self.download_worker.isRunning():
            reply = QMessageBox.question(
                self,
                "Cancel Download",
                "Download is in progress. Are you sure you want to cancel?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.download_worker.terminate()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


class OllamaServiceDialog(QDialog):
    """Dialog for starting Ollama service with progress tracking."""

    service_started = pyqtSignal(bool, str)  # success, message

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Start Ollama Service")
        self.setModal(True)
        self.setMinimumWidth(450)
        self.setMinimumHeight(200)

        self.ollama_manager = get_ollama_manager()
        self.start_worker: OllamaStartWorker | None = None

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Header
        header_label = QLabel("🚀 Start Ollama Service")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header_label)

        # Message
        self.message_label = QLabel(
            "Ollama service is not running. The service is required to use local AI models.\n\n"
            "Would you like to start the Ollama service now?"
        )
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label)

        # Progress section (initially hidden)
        self.progress_label = QLabel("Starting Ollama service...")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_label.hide()
        layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        # Buttons
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No
        )
        self.buttons.accepted.connect(self._start_ollama)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _start_ollama(self):
        """Start the Ollama service in a separate thread."""
        # Update UI to show progress
        self.message_label.setText("Starting Ollama service, please wait...")
        self.progress_label.show()
        self.progress_bar.show()

        # Disable buttons during startup
        self.buttons.button(QDialogButtonBox.StandardButton.Yes).setEnabled(False)
        self.buttons.button(QDialogButtonBox.StandardButton.No).setText("Cancel")

        # Start the service
        self.start_worker = OllamaStartWorker(self.ollama_manager, self)
        self.start_worker.service_started.connect(self._on_service_started)
        self.start_worker.start()

    def _on_service_started(self, success: bool, message: str):
        """Handle service start completion."""
        self.progress_bar.hide()

        if success:
            self.progress_label.setText("✅ Ollama service started successfully!")
            self.message_label.setText(message)

            # Change buttons
            self.buttons.clear()
            self.buttons.addButton("Continue", QDialogButtonBox.ButtonRole.AcceptRole)
            self.buttons.accepted.connect(self.accept)

            # Emit success signal
            self.service_started.emit(True, message)

            # Auto-close after 2 seconds
            QTimer.singleShot(2000, self.accept)
        else:
            self.progress_label.setText("❌ Failed to start Ollama service")
            self.message_label.setText(
                f"Error: {message}\n\nYou may need to start Ollama manually."
            )

            # Re-enable buttons
            self.buttons.button(QDialogButtonBox.StandardButton.Yes).setEnabled(True)
            self.buttons.button(QDialogButtonBox.StandardButton.No).setText("Cancel")

            # Emit failure signal
            self.service_started.emit(False, message)


class OllamaStartWorker(QThread):
    """Worker thread for starting Ollama service."""

    service_started = pyqtSignal(bool, str)  # success, message

    def __init__(self, ollama_manager, parent=None) -> None:
        super().__init__(parent)
        self.ollama_manager = ollama_manager

    def run(self):
        """Start the Ollama service."""
        try:
            success, message = self.ollama_manager.start_service()
            self.service_started.emit(success, message)
        except Exception as e:
            self.service_started.emit(False, f"Unexpected error: {str(e)}")


# ============================================================================
# ENHANCED PROCESSING PROGRESS DIALOGS
# ============================================================================


class ProcessingProgressDialog(QDialog):
    """Base class for processing progress dialogs with real-time updates."""

    def __init__(self, operation_name: str, file_count: int, parent=None) -> None:
        super().__init__(parent)
        self.operation_name = operation_name
        self.file_count = file_count
        self.current_file = 0
        self.processing_worker: None | (
            Any
        ) = None  # Will be set to actual worker thread
        self.cancellation_token = CancellationToken()  # Create cancellation token

        self.setWindowTitle(f"{operation_name} Progress")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

        # Prevent dialog from being closed with X button without confirmation
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.CustomizeWindowHint
        )

        self._setup_ui()

        # Start paused timer to enable pause button once processing starts
        self._enable_pause_timer = QTimer()
        self._enable_pause_timer.timeout.connect(self._enable_pause_button)
        self._enable_pause_timer.setSingleShot(True)
        self._enable_pause_timer.start(1000)  # Enable after 1 second

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Header
        icon_map = {
            "Local Transcription": "🎵",
            "Summarization": "📝",
            "Cloud Transcription": "📄",
            "MOC Generation": "🗺️",
        }
        icon = icon_map.get(self.operation_name, "⚙️")

        header_label = QLabel(f"{icon} {self.operation_name} Progress")
        header_font = QFont()
        header_font.setPointSize(16)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header_label)

        # Overall progress
        overall_group = QVBoxLayout()

        self.overall_label = QLabel(f"Processing {self.file_count} files...")
        overall_group.addWidget(self.overall_label)

        self.overall_progress = QProgressBar()
        self.overall_progress.setMinimum(0)
        self.overall_progress.setMaximum(self.file_count)
        overall_group.addWidget(self.overall_progress)

        layout.addLayout(overall_group)

        # Current file progress
        file_group = QVBoxLayout()

        self.file_label = QLabel("Preparing...")
        file_group.addWidget(self.file_label)

        self.file_progress = QProgressBar()
        self.file_progress.setMinimum(0)
        self.file_progress.setMaximum(100)
        file_group.addWidget(self.file_progress)

        self.details_label = QLabel("")
        self.details_label.setWordWrap(True)
        self.details_label.setStyleSheet("color: #666; font-size: 11px;")
        file_group.addWidget(self.details_label)

        layout.addLayout(file_group)

        # Speed and ETA
        stats_layout = QHBoxLayout()

        self.speed_label = QLabel("")
        stats_layout.addWidget(self.speed_label)

        stats_layout.addStretch()

        self.eta_label = QLabel("")
        stats_layout.addWidget(self.eta_label)

        layout.addLayout(stats_layout)

        # Buttons
        button_layout = QHBoxLayout()

        self.pause_btn = QPushButton("⏸️ Pause")
        self.pause_btn.clicked.connect(self._toggle_pause)
        self.pause_btn.setEnabled(False)  # Enable when processing starts
        self.pause_btn.setStyleSheet(
            "background-color: #ff9800; font-weight: bold; padding: 8px;"
        )

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._cancel_processing)
        self.cancel_btn.setStyleSheet(
            "background-color: #f44336; color: white; font-weight: bold; padding: 8px;"
        )

        button_layout.addWidget(self.pause_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)

    def _enable_pause_button(self):
        """Enable the pause button once processing starts."""
        if self.processing_worker and self.processing_worker.isRunning():
            self.pause_btn.setEnabled(True)

    def _toggle_pause(self):
        """Toggle pause/resume processing."""
        if not self.cancellation_token:
            return

        if self.cancellation_token.is_paused():
            # Currently paused, so resume
            self.cancellation_token.resume()
            self.pause_btn.setText("⏸️ Pause")
            self.pause_btn.setStyleSheet(
                "background-color: #ff9800; font-weight: bold; padding: 8px;"
            )
            self.details_label.setText("Resuming processing...")
            logger.info(f"{self.operation_name} resumed by user")
        else:
            # Currently running, so pause
            self.cancellation_token.pause()
            self.pause_btn.setText("▶️ Resume")
            self.pause_btn.setStyleSheet(
                "background-color: #4caf50; font-weight: bold; padding: 8px;"
            )
            self.details_label.setText("Processing paused... Click Resume to continue.")
            logger.info(f"{self.operation_name} paused by user")

    def _cancel_processing(self):
        """Cancel the processing operation gracefully."""
        if self.processing_worker and self.processing_worker.isRunning():
            reply = QMessageBox.question(
                self,
                "Cancel Processing",
                f"Are you sure you want to cancel {self.operation_name.lower()}?\n\n"
                f"This will stop processing and may leave some files incomplete.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,  # Default to No for safety
            )
            if reply == QMessageBox.StandardButton.Yes:
                # First try graceful cancellation
                if self.cancellation_token:
                    self.cancellation_token.cancel("User requested cancellation")
                    self.details_label.setText(
                        "Cancelling... Please wait for graceful shutdown."
                    )
                    self.cancel_btn.setText("Force Stop")
                    self.cancel_btn.setStyleSheet(
                        "background-color: #d32f2f; color: white; font-weight: bold; padding: 8px;"
                    )
                    self.pause_btn.setEnabled(False)

                    # Give 10 seconds for graceful shutdown
                    self._force_stop_timer = QTimer()
                    self._force_stop_timer.timeout.connect(self._force_stop)
                    self._force_stop_timer.setSingleShot(True)
                    self._force_stop_timer.start(10000)  # 10 seconds

                    logger.info(f"{self.operation_name} cancellation requested by user")
                else:
                    # Fallback to force stop
                    self._force_stop()
        else:
            self.reject()

    def _force_stop(self):
        """Force stop the processing if graceful cancellation fails."""
        if self.processing_worker and self.processing_worker.isRunning():
            logger.warning(f"Force stopping {self.operation_name} worker thread")
            self.processing_worker.terminate()
            self.processing_worker.wait(2000)  # Wait up to 2 seconds
        self.reject()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle dialog close event with improved UX."""
        if self.processing_worker and self.processing_worker.isRunning():
            reply = QMessageBox.question(
                self,
                "Close Progress Dialog",
                f"{self.operation_name} is still in progress. What would you like to do?",
                QMessageBox.StandardButton.Ignore | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Ignore:
                # Let processing continue in background
                logger.info(f"{self.operation_name} continuing in background")
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def update_overall_progress(self, completed: int, total: int):
        """Update overall progress across all files."""
        self.overall_progress.setValue(completed)
        self.overall_label.setText(f"Processing {completed}/{total} files...")

        if completed == total:
            self.overall_label.setText(f"✅ Completed {total} files!")
            self.pause_btn.setEnabled(False)
            self.cancel_btn.setText("Close")
            self.cancel_btn.setStyleSheet(
                "background-color: #4caf50; color: white; font-weight: bold; padding: 8px;"
            )

            # Auto-close after 3 seconds, but give user time to see results
            QTimer.singleShot(3000, self.accept)


class TranscriptionProgressDialog(ProcessingProgressDialog):
    """Enhanced progress dialog for transcription operations."""

    def __init__(self, file_count: int, parent=None) -> None:
        super().__init__("Local Transcription", file_count, parent)

    def update_transcription_progress(self, progress: TranscriptionProgress):
        """Update transcription-specific progress."""
        self.file_progress.setValue(int(progress.percent))

        # Update status
        status_text = f"Status: {progress.status.replace('_', ' ').title()}"
        if progress.current_step:
            status_text = f"{status_text} - {progress.current_step}"
        self.file_label.setText(status_text)

        # Update details
        details = []
        if progress.current_segment and progress.total_segments:
            details.append(
                f"Segment {progress.current_segment}/{progress.total_segments}"
            )
        if progress.model_name:
            details.append(f"Model: {progress.model_name}")
        if progress.device:
            details.append(f"Device: {progress.device}")

        self.details_label.setText(" | ".join(details))

        # Update speed and ETA
        if progress.speed_factor and progress.audio_duration:
            speed_text = f"Speed: {progress.speed_factor:.1f}x real-time"
            self.speed_label.setText(speed_text)

        if progress.eta_seconds:
            minutes = progress.eta_seconds // 60
            seconds = progress.eta_seconds % 60
            self.eta_label.setText(f"ETA: {minutes}m {seconds}s")


class SummarizationProgressDialog(ProcessingProgressDialog):
    """Enhanced progress dialog for summarization operations."""

    def __init__(self, file_count: int, parent=None) -> None:
        super().__init__("Summarization", file_count, parent)

    def update_summarization_progress(self, progress: SummarizationProgress):
        """Update summarization-specific progress."""
        self.file_progress.setValue(int(progress.percent))

        # Update status
        status_text = f"Status: {progress.status.replace('_', ' ').title()}"
        if progress.current_step:
            status_text = f"{status_text} - {progress.current_step}"
        self.file_label.setText(status_text)

        # Update details
        details = []
        if progress.tokens_processed:
            details.append(f"Tokens processed: {progress.tokens_processed:,}")
        if progress.tokens_generated:
            details.append(f"Generated: {progress.tokens_generated:,}")
        if progress.model_name:
            details.append(f"Model: {progress.model_name}")
        if progress.provider:
            details.append(f"Provider: {progress.provider}")

        self.details_label.setText(" | ".join(details))

        # Update speed and ETA
        if progress.speed_tokens_per_sec:
            speed_text = f"Speed: {progress.speed_tokens_per_sec:.1f} tokens/sec"
            self.speed_label.setText(speed_text)

        if progress.eta_seconds:
            minutes = progress.eta_seconds // 60
            seconds = progress.eta_seconds % 60
            self.eta_label.setText(f"ETA: {minutes}m {seconds}s")


class ExtractionProgressDialog(ProcessingProgressDialog):
    """Enhanced progress dialog for extraction operations."""

    def __init__(self, file_count: int, parent=None) -> None:
        super().__init__("Cloud Transcription", file_count, parent)

    def update_extraction_progress(self, progress: ExtractionProgress):
        """Update extraction-specific progress."""
        self.file_progress.setValue(int(progress.percent))

        # Update status
        status_text = f"Status: {progress.status.replace('_', ' ').title()}"
        if progress.current_step:
            status_text = f"{status_text} - {progress.current_step}"
        self.file_label.setText(status_text)

        # Update details
        details = []
        if progress.pages_processed and progress.total_pages:
            details.append(f"Pages: {progress.pages_processed}/{progress.total_pages}")
        if progress.elements_found:
            details.append(f"Elements: {progress.elements_found}")
        if progress.file_type:
            details.append(f"Type: {progress.file_type}")
        if progress.file_size_mb:
            details.append(f"Size: {progress.file_size_mb:.1f}MB")

        self.details_label.setText(" | ".join(details))

        # Update speed and ETA
        if progress.processing_speed_mb_per_sec:
            speed_text = f"Speed: {progress.processing_speed_mb_per_sec:.1f} MB/sec"
            self.speed_label.setText(speed_text)

        if progress.eta_seconds:
            minutes = progress.eta_seconds // 60
            seconds = progress.eta_seconds % 60
            self.eta_label.setText(f"ETA: {minutes}m {seconds}s")


class MOCProgressDialog(ProcessingProgressDialog):
    """Enhanced progress dialog for MOC generation operations."""

    def __init__(self, file_count: int, parent=None) -> None:
        super().__init__("MOC Generation", file_count, parent)

    def update_moc_progress(self, progress: MOCProgress):
        """Update MOC generation-specific progress."""
        self.file_progress.setValue(int(progress.percent))

        # Update status
        status_text = f"Status: {progress.status.replace('_', ' ').title()}"
        if progress.current_step:
            status_text = f"{status_text} - {progress.current_step}"
        self.file_label.setText(status_text)

        # Update details
        details = []
        if progress.files_analyzed and progress.total_files:
            details.append(f"Files: {progress.files_analyzed}/{progress.total_files}")
        if progress.entities_found:
            details.append(f"Entities: {progress.entities_found}")
        if progress.connections_made:
            details.append(f"Connections: {progress.connections_made}")
        if progress.moc_type:
            details.append(f"Type: {progress.moc_type}")

        self.details_label.setText(" | ".join(details))

        # Update ETA
        if progress.eta_seconds:
            minutes = progress.eta_seconds // 60
            seconds = progress.eta_seconds % 60
            self.eta_label.setText(f"ETA: {minutes}m {seconds}s")


class ModelDownloadWorker(QThread):
    """Worker thread for downloading models."""

    progress_updated = pyqtSignal(object)  # DownloadProgress
    download_finished = pyqtSignal(bool, str)  # success, message

    def __init__(self, model_name: str, parent=None) -> None:
        super().__init__(parent)
        self.model_name = model_name
        self.ollama_manager = get_ollama_manager()

    def run(self):
        """Download the model."""
        try:
            success = self.ollama_manager.download_model(
                self.model_name, progress_callback=self.progress_updated.emit
            )
            if success:
                self.download_finished.emit(
                    True, f"Model '{self.model_name}' downloaded successfully!"
                )
            else:
                self.download_finished.emit(
                    False, f"Failed to download model '{self.model_name}'"
                )
        except Exception as e:
            self.download_finished.emit(False, f"Error downloading model: {str(e)}")


class ModelDownloadDialog(QDialog):
    """Dialog for downloading missing models with progress tracking."""

    download_completed = pyqtSignal(bool)  # success
    download_progress = pyqtSignal(
        object
    )  # DownloadProgress - expose progress externally

    def __init__(self, model_name: str, parent=None) -> None:
        super().__init__(parent)
        self.model_name = model_name
        self.download_worker: ModelDownloadWorker | None = None
        self.setWindowTitle("Download Model")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setMinimumHeight(250)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Header
        header_label = QLabel("🤖 Model Not Found")
        header_font = QFont()
        header_font.setPointSize(16)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header_label)

        # Description
        desc_label = QLabel(
            f"The model '{self.model_name}' is not available locally.\n\n"
            f"Would you like to download it now? This may take several minutes depending on the model size.\n\n"
            f"Note: Summarization will be disabled until the download completes."
        )
        desc_label.setWordWrap(True)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc_label)

        # Progress section (initially hidden)
        self.progress_widget = QVBoxLayout()

        self.status_label = QLabel("Preparing download...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_widget.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_widget.addWidget(self.progress_bar)

        self.details_label = QLabel("")
        self.details_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.details_label.setStyleSheet("color: #666; font-size: 10px;")
        self.progress_widget.addWidget(self.details_label)

        # Add progress widgets to layout but hide them initially
        progress_container = QVBoxLayout()
        for i in range(self.progress_widget.count()):
            widget = self.progress_widget.itemAt(i).widget()
            if widget:
                widget.hide()
                progress_container.addWidget(widget)
        layout.addLayout(progress_container)

        # Buttons
        button_layout = QHBoxLayout()

        self.download_btn = QPushButton("📥 Yes, Download Model")
        self.download_btn.clicked.connect(self._start_download)
        self.download_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;"
        )

        self.cancel_btn = QPushButton("❌ No, Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.cancel_btn.setStyleSheet(
            "background-color: #f44336; color: white; font-weight: bold; padding: 8px;"
        )

        button_layout.addWidget(self.download_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)

    def _start_download(self):
        """Start the model download."""
        # Hide description and show progress
        self.download_btn.hide()
        self.cancel_btn.setText("Cancel Download")
        self.cancel_btn.clicked.disconnect()
        self.cancel_btn.clicked.connect(self._cancel_download)

        # Show progress widgets
        for i in range(self.progress_widget.count()):
            widget = self.progress_widget.itemAt(i).widget()
            if widget:
                widget.show()

        # Start download worker
        self.download_worker = ModelDownloadWorker(self.model_name, self)
        self.download_worker.progress_updated.connect(self._update_progress)
        self.download_worker.progress_updated.connect(
            self.download_progress.emit
        )  # Emit externally
        self.download_worker.download_finished.connect(self._on_download_finished)
        self.download_worker.start()

    def _update_progress(self, progress: DownloadProgress):
        """Update the progress display."""
        self.status_label.setText(progress.status or "Downloading...")

        if progress.percent > 0:
            self.progress_bar.setValue(int(progress.percent))

        # Build details string
        details = []
        if progress.completed > 0 and progress.total > 0:
            completed_mb = progress.completed / (1024 * 1024)
            total_mb = progress.total / (1024 * 1024)
            details.append(f"{completed_mb:.1f} MB / {total_mb:.1f} MB")

        if progress.speed_mbps > 0:
            details.append(f"{progress.speed_mbps:.1f} MB/s")

        if progress.eta_seconds:
            minutes = progress.eta_seconds // 60
            seconds = progress.eta_seconds % 60
            details.append(f"ETA: {minutes}m {seconds}s")

        self.details_label.setText(" | ".join(details))

    def _cancel_download(self):
        """Cancel the download."""
        if self.download_worker and self.download_worker.isRunning():
            self.download_worker.terminate()
            self.download_worker.wait()
        self.reject()

    def _on_download_finished(self, success: bool, message: str):
        """Handle download completion."""
        if success:
            self.status_label.setText("✅ Download completed!")
            self.progress_bar.setValue(100)
            self.details_label.setText(message)

            # Change cancel button to close
            self.cancel_btn.setText("Close")
            self.cancel_btn.clicked.disconnect()
            self.cancel_btn.clicked.connect(self.accept)

            # Emit success signal
            self.download_completed.emit(True)

            # Auto-close after 2 seconds
            QTimer.singleShot(2000, self.accept)
        else:
            self.status_label.setText("❌ Download failed!")
            self.details_label.setText(message)
            self.progress_bar.setStyleSheet(
                "QProgressBar::chunk { background-color: #f44336; }"
            )

            # Change cancel button to close
            self.cancel_btn.setText("Close")
            self.cancel_btn.clicked.disconnect()
            self.cancel_btn.clicked.connect(self.reject)

            # Emit failure signal
            self.download_completed.emit(False)
