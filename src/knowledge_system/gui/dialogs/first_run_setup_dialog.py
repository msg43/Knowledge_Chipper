"""
First-run setup dialog for downloading essential models and dependencies.
"""

import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject, QThread, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...logger import get_logger
from ...processors.whisper_cpp_transcribe import WhisperCppTranscribeProcessor

logger = get_logger(__name__)


class ModelDownloadWorker(QObject):
    """Worker for downloading models in background."""
    
    progress_updated = pyqtSignal(dict)  # progress info
    download_completed = pyqtSignal(str, bool)  # model_name, success
    all_downloads_completed = pyqtSignal(bool)  # success
    
    def __init__(self, models_to_download: list[str]):
        super().__init__()
        self.models_to_download = models_to_download
        self.cancelled = False
    
    def cancel(self):
        """Cancel the download operation."""
        self.cancelled = True
    
    def download_models(self):
        """Download the selected models."""
        try:
            success_count = 0
            total_models = len(self.models_to_download)
            
            for i, model_name in enumerate(self.models_to_download):
                if self.cancelled:
                    break
                    
                logger.info(f"Downloading Whisper model: {model_name}")
                
                # Create processor for this model
                processor = WhisperCppTranscribeProcessor(model=model_name)
                
                # Download with progress callback
                def progress_callback(progress_info):
                    if not self.cancelled:
                        progress_info['current_model'] = i + 1
                        progress_info['total_models'] = total_models
                        self.progress_updated.emit(progress_info)
                
                try:
                    model_path = processor._download_model(model_name, progress_callback)
                    if model_path and model_path.exists():
                        self.download_completed.emit(model_name, True)
                        success_count += 1
                        logger.info(f"Successfully downloaded {model_name} model")
                    else:
                        self.download_completed.emit(model_name, False)
                        logger.error(f"Failed to download {model_name} model")
                        
                except Exception as e:
                    self.download_completed.emit(model_name, False)
                    logger.error(f"Error downloading {model_name} model: {e}")
            
            # Emit completion signal
            all_success = success_count == total_models and not self.cancelled
            self.all_downloads_completed.emit(all_success)
            
        except Exception as e:
            logger.error(f"Critical error in model download worker: {e}")
            self.all_downloads_completed.emit(False)


class FirstRunSetupDialog(QDialog):
    """First-run setup dialog for downloading essential models and dependencies."""
    
    setup_completed = pyqtSignal(bool)  # success
    
    def __init__(self, parent=None):
        # CRITICAL: Testing safety check - prevent dialog creation during testing
        import os
        if os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE"):
            from ...logger import get_logger
            logger = get_logger(__name__)
            logger.error("🧪 CRITICAL: Attempted to create FirstRunSetupDialog during testing mode - BLOCKED!")
            raise RuntimeError("FirstRunSetupDialog cannot be created during testing mode")
            
        super().__init__(parent)
        self.setWindowTitle("Welcome to Knowledge Chipper")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        
        # State
        self.download_worker: Optional[ModelDownloadWorker] = None
        self.download_thread: Optional[QThread] = None
        self.selected_models: list[str] = []
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        
        # Header
        self._create_header(layout)
        
        # Welcome message
        self._create_welcome_message(layout)
        
        # Model selection
        self._create_model_selection(layout)
        
        # Progress section (initially hidden)
        self._create_progress_section(layout)
        
        # Buttons
        self._create_buttons(layout)
        
    def _create_header(self, layout: QVBoxLayout):
        """Create the header section."""
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        
        # Title
        title_label = QLabel("🚀 Welcome to Knowledge Chipper")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        layout.addWidget(header_widget)
        
    def _create_welcome_message(self, layout: QVBoxLayout):
        """Create the welcome message."""
        message = QLabel(
            "Thanks for installing Knowledge Chipper! 🎉\n\n"
            "To get started, we'll download some essential AI models for transcription. "
            "This is a one-time setup that will enable you to transcribe audio and video files.\n\n"
            "📦 App Size Optimization: We've made the initial download 83% smaller by downloading "
            "models only when needed. Choose which models to download now:"
        )
        message.setWordWrap(True)
        message.setStyleSheet("color: #333; padding: 10px; background: #f8f9fa; border-radius: 8px;")
        layout.addWidget(message)
        
    def _create_model_selection(self, layout: QVBoxLayout):
        """Create the model selection section."""
        models_widget = QWidget()
        models_layout = QVBoxLayout(models_widget)
        
        # Models section header
        models_header = QLabel("🧠 AI Models (Choose what to download now)")
        models_header.setFont(QFont("", 12, QFont.Weight.Bold))
        models_layout.addWidget(models_header)
        
        # Model checkboxes with descriptions
        self.model_checkboxes = {}
        
        models_info = [
            ("base", "Base Model (~142 MB) - Recommended", "Good balance of speed and accuracy", True),
            ("tiny", "Tiny Model (~75 MB) - Fastest", "Fastest transcription, lower accuracy", False),
            ("small", "Small Model (~466 MB) - Better accuracy", "Slower but more accurate", False),
        ]
        
        for model_name, title, description, default_checked in models_info:
            checkbox_widget = QWidget()
            checkbox_layout = QVBoxLayout(checkbox_widget)
            checkbox_layout.setContentsMargins(20, 5, 5, 5)
            
            # Main checkbox
            checkbox = QCheckBox(title)
            checkbox.setFont(QFont("", 10, QFont.Weight.Bold))
            checkbox.setChecked(default_checked)
            checkbox.stateChanged.connect(self._update_selected_models)
            self.model_checkboxes[model_name] = checkbox
            checkbox_layout.addWidget(checkbox)
            
            # Description
            desc_label = QLabel(f"   {description}")
            desc_label.setStyleSheet("color: #666; margin-left: 20px;")
            checkbox_layout.addWidget(desc_label)
            
            models_layout.addWidget(checkbox_widget)
        
        # Note about other models
        note_label = QLabel(
            "💡 Note: You can download additional models (medium ~1.5GB, large ~3.1GB) later from the settings."
        )
        note_label.setWordWrap(True)
        note_label.setStyleSheet("color: #666; font-style: italic; padding: 10px;")
        models_layout.addWidget(note_label)
        
        layout.addWidget(models_widget)
        
        # Update initial selection
        self._update_selected_models()
        
    def _create_progress_section(self, layout: QVBoxLayout):
        """Create the progress section."""
        self.progress_widget = QWidget()
        progress_layout = QVBoxLayout(self.progress_widget)
        
        self.progress_label = QLabel("Downloading models...")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progress_layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        progress_layout.addWidget(self.progress_bar)
        
        self.download_status = QLabel("")
        self.download_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.download_status.setStyleSheet("color: #666;")
        progress_layout.addWidget(self.download_status)
        
        # Initially hide progress section
        self.progress_widget.hide()
        layout.addWidget(self.progress_widget)
        
    def _create_buttons(self, layout: QVBoxLayout):
        """Create the button section."""
        self.buttons = QDialogButtonBox()
        
        # Skip button
        self.skip_button = QPushButton("Skip for Now")
        self.skip_button.clicked.connect(self._skip_setup)
        self.buttons.addButton(self.skip_button, QDialogButtonBox.ButtonRole.RejectRole)
        
        # Download button
        self.download_button = QPushButton("Download Selected Models")
        self.download_button.clicked.connect(self._start_download)
        self.download_button.setDefault(True)
        self.buttons.addButton(self.download_button, QDialogButtonBox.ButtonRole.AcceptRole)
        
        # Cancel button (hidden initially)
        self.cancel_button = QPushButton("Cancel Download")
        self.cancel_button.clicked.connect(self._cancel_download)
        self.cancel_button.hide()
        self.buttons.addButton(self.cancel_button, QDialogButtonBox.ButtonRole.RejectRole)
        
        layout.addWidget(self.buttons)
        
    def _update_selected_models(self):
        """Update the list of selected models."""
        self.selected_models = [
            model_name for model_name, checkbox in self.model_checkboxes.items()
            if checkbox.isChecked()
        ]
        
        # Update download button text
        if self.selected_models:
            total_size = self._calculate_total_size()
            self.download_button.setText(f"Download {len(self.selected_models)} Models ({total_size})")
            self.download_button.setEnabled(True)
        else:
            self.download_button.setText("Select Models to Download")
            self.download_button.setEnabled(False)
            
    def _calculate_total_size(self) -> str:
        """Calculate the total download size."""
        sizes = {"tiny": 75, "base": 142, "small": 466}
        total_mb = sum(sizes.get(model, 0) for model in self.selected_models)
        
        if total_mb >= 1000:
            return f"~{total_mb/1000:.1f} GB"
        else:
            return f"~{total_mb} MB"
            
    def _skip_setup(self):
        """Skip the setup."""
        self.setup_completed.emit(True)
        self.accept()
        
    def _start_download(self):
        """Start downloading the selected models."""
        if not self.selected_models:
            return
            
        # Update UI for download mode
        self.progress_widget.show()
        self.skip_button.hide()
        self.download_button.hide()
        self.cancel_button.show()
        
        # Disable model selection
        for checkbox in self.model_checkboxes.values():
            checkbox.setEnabled(False)
            
        # Create worker and thread
        self.download_worker = ModelDownloadWorker(self.selected_models)
        self.download_thread = QThread()
        
        # Move worker to thread
        self.download_worker.moveToThread(self.download_thread)
        
        # Connect signals
        self.download_worker.progress_updated.connect(self._update_progress)
        self.download_worker.download_completed.connect(self._on_model_downloaded)
        self.download_worker.all_downloads_completed.connect(self._on_all_downloads_completed)
        self.download_thread.started.connect(self.download_worker.download_models)
        
        # Start download
        self.download_thread.start()
        
    def _cancel_download(self):
        """Cancel the download."""
        if self.download_worker:
            self.download_worker.cancel()
            
        if self.download_thread:
            self.download_thread.quit()
            self.download_thread.wait()
            
        self.setup_completed.emit(False)
        self.reject()
        
    def _update_progress(self, progress_info: dict):
        """Update the progress display."""
        current_model = progress_info.get('current_model', 1)
        total_models = progress_info.get('total_models', 1)
        percent = progress_info.get('percent', 0)
        model_name = progress_info.get('model', 'unknown')
        speed = progress_info.get('speed_mbps', 0)
        
        # Update progress bar
        overall_progress = ((current_model - 1) / total_models) * 100 + (percent / total_models)
        self.progress_bar.setValue(int(overall_progress))
        
        # Update labels
        self.progress_label.setText(f"Downloading {model_name} model... ({current_model}/{total_models})")
        self.download_status.setText(f"{percent:.1f}% • {speed:.1f} MB/s")
        
    def _on_model_downloaded(self, model_name: str, success: bool):
        """Handle completion of a single model download."""
        if success:
            logger.info(f"Successfully downloaded {model_name} model")
        else:
            logger.error(f"Failed to download {model_name} model")
            
    def _on_all_downloads_completed(self, success: bool):
        """Handle completion of all downloads."""
        # Clean up thread
        if self.download_thread:
            self.download_thread.quit()
            self.download_thread.wait()
            
        if success:
            self.progress_label.setText("✅ All models downloaded successfully!")
            self.download_status.setText("Setup complete - ready to transcribe!")
            self.progress_bar.setValue(100)
            
            # Show completion message for a moment
            QTimer.singleShot(2000, lambda: self._complete_setup(True))
        else:
            self.progress_label.setText("❌ Some downloads failed")
            self.download_status.setText("You can retry downloading models later from settings")
            
            # Show completion with partial success
            QTimer.singleShot(3000, lambda: self._complete_setup(False))
            
    def _complete_setup(self, success: bool):
        """Complete the setup process."""
        self.setup_completed.emit(success)
        self.accept()
        
    def closeEvent(self, event):
        """Handle dialog close event."""
        if self.download_thread and self.download_thread.isRunning():
            self._cancel_download()
        event.accept()
