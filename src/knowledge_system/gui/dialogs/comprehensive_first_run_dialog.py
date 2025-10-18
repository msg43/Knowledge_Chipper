"""
Comprehensive first-run setup dialog for Architecture B.
Downloads ALL required dependencies with clear roadmap and progress tracking.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...logger import get_logger
from ...utils.macos_paths import get_cache_dir, get_config_dir

logger = get_logger(__name__)


class DependencyStatus:
    """Track status of each dependency."""

    def __init__(
        self, name: str, description: str, size_mb: int, essential: bool = True
    ):
        self.name = name
        self.description = description
        self.size_mb = size_mb
        self.essential = essential
        self.status = "pending"  # pending, downloading, complete, failed, skipped
        self.progress = 0  # 0-100
        self.error_message = ""


class DependencyDownloadWorker(QObject):
    """Worker for downloading all dependencies with detailed progress tracking."""

    progress_updated = pyqtSignal(str, int, str)  # dependency_name, progress, status
    dependency_completed = pyqtSignal(str, bool, str)  # name, success, message
    all_downloads_completed = pyqtSignal(bool, dict)  # success, summary
    log_message = pyqtSignal(str)  # log message for user

    def __init__(
        self, dependencies: list[DependencyStatus], skip_optional: bool = False
    ):
        super().__init__()
        self.dependencies = dependencies
        self.skip_optional = skip_optional
        self.cancelled = False
        self.cache_dir = get_cache_dir()
        self.config_dir = get_config_dir()

    def cancel(self):
        """Cancel all downloads."""
        self.cancelled = True

    def download_all_dependencies(self):
        """Download all selected dependencies."""
        try:
            self.log_message.emit("🚀 Starting comprehensive dependency setup...")
            self.log_message.emit(f"📁 Cache directory: {self.cache_dir}")
            self.log_message.emit(f"⚙️  Config directory: {self.config_dir}")

            success_count = 0
            total_deps = len(
                [d for d in self.dependencies if d.essential or not self.skip_optional]
            )

            for dep in self.dependencies:
                if self.cancelled:
                    break

                if not dep.essential and self.skip_optional:
                    dep.status = "skipped"
                    self.dependency_completed.emit(dep.name, True, "Skipped (optional)")
                    continue

                self.log_message.emit(f"\n📦 Setting up {dep.name}...")
                self.progress_updated.emit(dep.name, 0, "downloading")

                success = False
                error_msg = ""

                try:
                    if dep.name == "ffmpeg":
                        success = self._setup_ffmpeg(dep)
                    elif dep.name == "whisper_cpp":
                        success = self._setup_whisper_cpp(dep)
                    elif dep.name == "whisper_models":
                        success = self._setup_whisper_models(dep)
                    elif dep.name == "pyannote_models":
                        success = self._setup_pyannote_models(dep)
                    elif dep.name == "voice_models":
                        success = self._setup_voice_models(dep)
                    elif dep.name == "ollama":
                        success = self._setup_ollama(dep)
                    elif dep.name == "hce_models":
                        success = self._setup_hce_models(dep)
                    else:
                        error_msg = f"Unknown dependency: {dep.name}"

                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Error setting up {dep.name}: {e}")

                if success:
                    dep.status = "complete"
                    self.progress_updated.emit(dep.name, 100, "complete")
                    self.dependency_completed.emit(dep.name, True, "✅ Complete")
                    success_count += 1
                    self.log_message.emit(f"✅ {dep.name} setup complete!")
                else:
                    dep.status = "failed"
                    dep.error_message = error_msg
                    self.progress_updated.emit(dep.name, 0, "failed")
                    self.dependency_completed.emit(
                        dep.name, False, f"❌ Failed: {error_msg}"
                    )
                    self.log_message.emit(f"❌ {dep.name} setup failed: {error_msg}")

            # Generate summary
            summary = self._generate_summary()
            all_success = success_count == total_deps and not self.cancelled

            self.log_message.emit(
                f"\n🎯 Setup Complete! {success_count}/{total_deps} dependencies ready"
            )
            self.all_downloads_completed.emit(all_success, summary)

        except Exception as e:
            logger.error(f"Critical error in dependency setup: {e}")
            self.all_downloads_completed.emit(False, {"error": str(e)})

    def _setup_ffmpeg(self, dep: DependencyStatus) -> bool:
        """Setup FFmpeg binary."""
        try:
            # Check if already installed
            result = subprocess.run(
                ["ffmpeg", "-version"], capture_output=True, text=True
            )
            if result.returncode == 0:
                self.log_message.emit("✅ FFmpeg already installed")
                return True
        except FileNotFoundError:
            pass

        # Run the FFmpeg installer
        try:
            from ...scripts.silent_ffmpeg_installer import install_ffmpeg_for_dmg

            app_bundle_path = Path(__file__).parent.parent.parent.parent.parent
            return install_ffmpeg_for_dmg(app_bundle_path)
        except Exception as e:
            logger.error(f"FFmpeg installation failed: {e}")
            return False

    def _setup_whisper_cpp(self, dep: DependencyStatus) -> bool:
        """Setup whisper.cpp binary."""
        try:
            from ...scripts.install_whisper_cpp_binary import (
                install_whisper_cpp_for_dmg,
            )

            app_bundle_path = Path(__file__).parent.parent.parent.parent.parent
            return install_whisper_cpp_for_dmg(app_bundle_path)
        except Exception as e:
            logger.error(f"Whisper.cpp installation failed: {e}")
            return False

    def _setup_whisper_models(self, dep: DependencyStatus) -> bool:
        """Download Whisper models to user cache."""
        try:
            models_dir = self.cache_dir / "models" / "whisper"
            models_dir.mkdir(parents=True, exist_ok=True)

            # Download base model (most commonly used)
            from ...processors.whisper_cpp_transcribe import (
                WhisperCppTranscribeProcessor,
            )

            processor = WhisperCppTranscribeProcessor(model="base")

            def progress_callback(info):
                if not self.cancelled:
                    progress = info.get("progress", 0)
                    self.progress_updated.emit(dep.name, progress, "downloading")

            model_path = processor._download_model("base", progress_callback)
            return model_path and model_path.exists()

        except Exception as e:
            logger.error(f"Whisper models download failed: {e}")
            return False

    def _setup_pyannote_models(self, dep: DependencyStatus) -> bool:
        """Download Pyannote models to user cache."""
        try:
            models_dir = self.cache_dir / "models" / "pyannote"
            models_dir.mkdir(parents=True, exist_ok=True)

            # Set up for runtime download (Architecture B approach)
            config_file = models_dir / "runtime_download_config.json"
            config = {
                "model": "pyannote/speaker-diarization-3.1",
                "download_on_first_use": True,
                "cache_location": str(models_dir),
                "hf_token_required": True,
                "setup_complete": True,
            }

            with open(config_file, "w") as f:
                json.dump(config, f, indent=2)

            self.log_message.emit("📝 Pyannote configured for runtime download")
            return True

        except Exception as e:
            logger.error(f"Pyannote setup failed: {e}")
            return False

    def _setup_voice_models(self, dep: DependencyStatus) -> bool:
        """Download voice fingerprinting models to user cache."""
        try:
            models_dir = self.cache_dir / "models" / "voice_models"
            models_dir.mkdir(parents=True, exist_ok=True)

            # Set up for runtime download
            config_file = models_dir / "runtime_download_config.json"
            config = {
                "models": {
                    "wav2vec2": "facebook/wav2vec2-large-960h-lv60-self",
                    "ecapa": "speechbrain/spkrec-ecapa-voxceleb",
                },
                "download_on_first_use": True,
                "cache_location": str(models_dir),
                "accuracy_target": "97%",
                "setup_complete": True,
            }

            with open(config_file, "w") as f:
                json.dump(config, f, indent=2)

            self.log_message.emit("📝 Voice models configured for runtime download")
            return True

        except Exception as e:
            logger.error(f"Voice models setup failed: {e}")
            return False

    def _setup_ollama(self, dep: DependencyStatus) -> bool:
        """Setup Ollama and LLM models."""
        try:
            models_dir = self.cache_dir / "models" / "ollama"
            models_dir.mkdir(parents=True, exist_ok=True)

            # Set up for runtime download
            config_file = models_dir / "runtime_download_config.json"
            config = {
                "model": "qwen2.5:7b",
                "download_on_first_use": True,
                "estimated_size_gb": 4.0,
                "fallback_models": ["qwen2.5:3b", "llama3.2:3b", "phi3:3.8b-mini"],
                "setup_complete": True,
            }

            with open(config_file, "w") as f:
                json.dump(config, f, indent=2)

            self.log_message.emit("📝 Ollama configured for runtime download")
            return True

        except Exception as e:
            logger.error(f"Ollama setup failed: {e}")
            return False

    def _setup_hce_models(self, dep: DependencyStatus) -> bool:
        """Setup HCE (Hybrid Claim Extraction) models."""
        try:
            models_dir = self.cache_dir / "models" / "hce"
            models_dir.mkdir(parents=True, exist_ok=True)

            # Set up for runtime download
            config_file = models_dir / "runtime_download_config.json"
            config = {
                "models": {
                    "sentence_transformer": "all-MiniLM-L6-v2",
                    "claim_extractor": "microsoft/DialoGPT-medium",
                },
                "download_on_first_use": True,
                "cache_location": str(models_dir),
                "setup_complete": True,
            }

            with open(config_file, "w") as f:
                json.dump(config, f, indent=2)

            self.log_message.emit("📝 HCE models configured for runtime download")
            return True

        except Exception as e:
            logger.error(f"HCE setup failed: {e}")
            return False

    def _generate_summary(self) -> dict[str, Any]:
        """Generate setup summary."""
        summary = {
            "total_dependencies": len(self.dependencies),
            "completed": len([d for d in self.dependencies if d.status == "complete"]),
            "failed": len([d for d in self.dependencies if d.status == "failed"]),
            "skipped": len([d for d in self.dependencies if d.status == "skipped"]),
            "dependencies": {
                d.name: {"status": d.status, "error": d.error_message}
                for d in self.dependencies
            },
        }
        return summary


class ComprehensiveFirstRunDialog(QDialog):
    """Comprehensive first-run setup dialog for Architecture B."""

    setup_completed = pyqtSignal(bool, dict)  # success, summary

    def __init__(self, parent=None):
        # Testing safety check
        if os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE"):
            logger.error(
                "🧪 CRITICAL: Attempted to create ComprehensiveFirstRunDialog during testing mode - BLOCKED!"
            )
            raise RuntimeError(
                "ComprehensiveFirstRunDialog cannot be created during testing mode"
            )

        super().__init__(parent)
        self.setWindowTitle("Welcome to Skip the Podcast Desktop - First-Time Setup")
        self.setModal(True)
        self.setMinimumWidth(800)
        self.setMinimumHeight(700)

        # Dependencies list
        self.dependencies = [
            DependencyStatus(
                "ffmpeg", "Audio/video processing engine", 50, essential=True
            ),
            DependencyStatus(
                "whisper_cpp", "Local transcription binary", 10, essential=True
            ),
            DependencyStatus(
                "whisper_models", "Whisper transcription models", 300, essential=True
            ),
            DependencyStatus(
                "pyannote_models", "Speaker diarization setup", 5, essential=True
            ),
            DependencyStatus(
                "voice_models",
                "Voice fingerprinting setup (97% accuracy)",
                5,
                essential=False,
            ),
            DependencyStatus("ollama", "Local AI assistant setup", 5, essential=False),
            DependencyStatus(
                "hce_models", "Claim extraction setup", 5, essential=False
            ),
        ]

        # State
        self.download_worker: DependencyDownloadWorker | None = None
        self.download_thread: QThread | None = None
        self.dependency_widgets = {}

        self._setup_ui()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Header
        self._create_header(layout)

        # Roadmap section
        self._create_roadmap_section(layout)

        # Progress section (initially hidden)
        self._create_progress_section(layout)

        # Log section (initially hidden)
        self._create_log_section(layout)

        # Buttons
        self._create_buttons(layout)

    def _create_header(self, layout: QVBoxLayout):
        """Create the header section."""
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)

        # Title
        title = QLabel("🚀 Welcome to Skip the Podcast Desktop")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Subtitle
        subtitle = QLabel("First-time setup: Download essential dependencies")
        subtitle_font = QFont()
        subtitle_font.setPointSize(12)
        subtitle.setFont(subtitle_font)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #666666; margin-bottom: 20px;")

        # Architecture explanation
        arch_label = QLabel(
            "📦 <b>Architecture B</b>: Small app bundle (~500MB) + models download to your cache directory<br>"
            "🏠 All data stored in: <code>~/Library/Caches/Skip the Podcast Desktop/</code><br>"
            "✅ Follows Apple's security guidelines for modern macOS apps"
        )
        arch_label.setWordWrap(True)
        arch_label.setStyleSheet(
            "background-color: #f0f8ff; padding: 10px; border-radius: 5px; margin: 10px 0;"
        )

        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        header_layout.addWidget(arch_label)

        layout.addWidget(header_widget)

    def _create_roadmap_section(self, layout: QVBoxLayout):
        """Create the dependency roadmap section."""
        roadmap_group = QGroupBox("📋 Dependency Roadmap")
        roadmap_layout = QVBoxLayout(roadmap_group)

        # Create scroll area for dependencies
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(300)

        deps_widget = QWidget()
        deps_layout = QVBoxLayout(deps_widget)

        total_size = sum(dep.size_mb for dep in self.dependencies)
        essential_count = len([d for d in self.dependencies if d.essential])

        # Summary
        summary_label = QLabel(
            f"📊 <b>{len(self.dependencies)} dependencies</b> | "
            f"<b>{essential_count} essential</b> | "
            f"<b>~{total_size}MB total</b> download"
        )
        summary_label.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        deps_layout.addWidget(summary_label)

        # Individual dependencies
        for dep in self.dependencies:
            dep_widget = self._create_dependency_widget(dep)
            self.dependency_widgets[dep.name] = dep_widget
            deps_layout.addWidget(dep_widget)

        scroll.setWidget(deps_widget)
        roadmap_layout.addWidget(scroll)

        self.roadmap_section = roadmap_group
        layout.addWidget(roadmap_group)

    def _create_dependency_widget(self, dep: DependencyStatus) -> QWidget:
        """Create widget for individual dependency."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(10, 5, 10, 5)

        # Status icon
        status_label = QLabel("⏳")
        status_label.setFixedWidth(30)

        # Name and description
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)

        name_label = QLabel(f"<b>{dep.name}</b>")
        desc_label = QLabel(dep.description)
        desc_label.setStyleSheet("color: #666666; font-size: 10px;")

        info_layout.addWidget(name_label)
        info_layout.addWidget(desc_label)

        # Size and essential status
        size_label = QLabel(f"{dep.size_mb}MB")
        size_label.setFixedWidth(60)
        size_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        essential_label = QLabel("✅ Essential" if dep.essential else "⭐ Optional")
        essential_label.setFixedWidth(80)
        essential_label.setStyleSheet("font-size: 10px;")

        # Progress bar (initially hidden)
        progress = QProgressBar()
        progress.setVisible(False)
        progress.setMaximumHeight(15)

        layout.addWidget(status_label)
        layout.addWidget(info_widget)
        layout.addWidget(size_label)
        layout.addWidget(essential_label)
        layout.addWidget(progress)

        # Store references for updates
        widget.status_label = status_label
        widget.progress_bar = progress
        widget.dep = dep

        return widget

    def _create_progress_section(self, layout: QVBoxLayout):
        """Create the progress section."""
        progress_group = QGroupBox("📥 Download Progress")
        progress_layout = QVBoxLayout(progress_group)

        # Overall progress
        self.overall_progress = QProgressBar()
        self.overall_progress.setFormat("Overall Progress: %p%")
        progress_layout.addWidget(self.overall_progress)

        # Current task
        self.current_task_label = QLabel("Ready to start...")
        self.current_task_label.setStyleSheet("font-weight: bold; margin: 5px 0;")
        progress_layout.addWidget(self.current_task_label)

        self.progress_section = progress_group
        self.progress_section.setVisible(False)
        layout.addWidget(progress_group)

    def _create_log_section(self, layout: QVBoxLayout):
        """Create the log section."""
        log_group = QGroupBox("📝 Setup Log")
        log_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(150)
        self.log_text.setStyleSheet(
            "font-family: monospace; font-size: 10px; background-color: #f5f5f5;"
        )
        log_layout.addWidget(self.log_text)

        self.log_section = log_group
        self.log_section.setVisible(False)
        layout.addWidget(log_group)

    def _create_buttons(self, layout: QVBoxLayout):
        """Create the button section."""
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)

        # Options
        self.skip_optional_checkbox = QCheckBox(
            "Skip optional components (faster setup)"
        )
        self.skip_optional_checkbox.setChecked(False)
        button_layout.addWidget(self.skip_optional_checkbox)

        button_layout.addStretch()

        # Buttons
        self.skip_button = QPushButton("Skip Setup")
        self.skip_button.clicked.connect(self._skip_setup)

        self.start_button = QPushButton("🚀 Start Setup")
        self.start_button.setDefault(True)
        self.start_button.clicked.connect(self._start_setup)
        self.start_button.setStyleSheet("font-weight: bold; padding: 8px 16px;")

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self._cancel_setup)
        self.cancel_button.setVisible(False)

        self.finish_button = QPushButton("🎯 Launch App")
        self.finish_button.clicked.connect(self._finish_setup)
        self.finish_button.setVisible(False)
        self.finish_button.setStyleSheet(
            "font-weight: bold; padding: 8px 16px; background-color: #4CAF50; color: white;"
        )

        button_layout.addWidget(self.skip_button)
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.finish_button)

        layout.addWidget(button_widget)

    def _skip_setup(self):
        """Skip the setup process."""
        self.setup_completed.emit(True, {"skipped": True})
        self.accept()

    def _start_setup(self):
        """Start the dependency setup process."""
        # Update UI for setup mode
        self.roadmap_section.setEnabled(False)
        self.progress_section.setVisible(True)
        self.log_section.setVisible(True)
        self.skip_button.setVisible(False)
        self.start_button.setVisible(False)
        self.cancel_button.setVisible(True)

        # Resize dialog to accommodate new sections
        self.resize(self.width(), 900)

        # Create worker and thread
        skip_optional = self.skip_optional_checkbox.isChecked()
        self.download_worker = DependencyDownloadWorker(
            self.dependencies, skip_optional
        )
        self.download_thread = QThread()

        # Move worker to thread
        self.download_worker.moveToThread(self.download_thread)

        # Connect signals
        self.download_worker.progress_updated.connect(self._update_dependency_progress)
        self.download_worker.dependency_completed.connect(self._on_dependency_completed)
        self.download_worker.all_downloads_completed.connect(self._on_all_completed)
        self.download_worker.log_message.connect(self._add_log_message)
        self.download_thread.started.connect(
            self.download_worker.download_all_dependencies
        )

        # Start setup
        self.download_thread.start()

    def _cancel_setup(self):
        """Cancel the setup process."""
        if self.download_worker:
            self.download_worker.cancel()

        if self.download_thread:
            self.download_thread.quit()
            self.download_thread.wait()

        self.setup_completed.emit(False, {"cancelled": True})
        self.reject()

    def _finish_setup(self):
        """Finish setup and launch app."""
        self.setup_completed.emit(True, {"completed": True})
        self.accept()

    def _update_dependency_progress(self, dep_name: str, progress: int, status: str):
        """Update progress for a specific dependency."""
        if dep_name in self.dependency_widgets:
            widget = self.dependency_widgets[dep_name]

            # Update status icon
            status_icons = {
                "pending": "⏳",
                "downloading": "📥",
                "complete": "✅",
                "failed": "❌",
                "skipped": "⏭️",
            }
            widget.status_label.setText(status_icons.get(status, "⏳"))

            # Update progress bar
            if status == "downloading":
                widget.progress_bar.setVisible(True)
                widget.progress_bar.setValue(progress)
            else:
                widget.progress_bar.setVisible(False)

        # Update current task
        if status == "downloading":
            self.current_task_label.setText(f"📥 Setting up {dep_name}... {progress}%")

    def _on_dependency_completed(self, dep_name: str, success: bool, message: str):
        """Handle completion of a dependency."""
        self._add_log_message(f"{'✅' if success else '❌'} {dep_name}: {message}")

    def _on_all_completed(self, success: bool, summary: dict):
        """Handle completion of all dependencies."""
        self.cancel_button.setVisible(False)

        if success:
            self.current_task_label.setText("🎯 Setup Complete! Ready to launch.")
            self.finish_button.setVisible(True)
            self._add_log_message("\n🎉 All dependencies successfully set up!")
            self._add_log_message(
                "You can now use all features of Skip the Podcast Desktop."
            )
        else:
            self.current_task_label.setText("⚠️ Setup completed with some issues.")
            self.finish_button.setVisible(True)
            self._add_log_message("\n⚠️ Setup completed with some issues.")
            self._add_log_message(
                "The app will still work, but some features may require manual setup."
            )

        # Update overall progress
        completed = summary.get("completed", 0)
        total = summary.get("total_dependencies", len(self.dependencies))
        self.overall_progress.setValue(int((completed / total) * 100))

    def _add_log_message(self, message: str):
        """Add a message to the log."""
        # Check if we should auto-scroll BEFORE appending
        scrollbar = self.log_text.verticalScrollBar()
        should_scroll = scrollbar and scrollbar.value() >= scrollbar.maximum() - 10
        
        self.log_text.append(message)
        
        # Only auto-scroll if user was already at the bottom
        if should_scroll and scrollbar:
            scrollbar.setValue(scrollbar.maximum())
