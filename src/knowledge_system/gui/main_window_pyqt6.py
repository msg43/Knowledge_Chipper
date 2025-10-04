"""Main GUI Window for Knowledge System - PyQt6 Implementation.

Streamlined main window that focuses on window setup and coordination.
All business logic has been moved to modular tab classes.
"""

import os
import queue
import sys
from typing import Any

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import (
    QLabel,
    QMainWindow,
    QSizePolicy,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..config import get_settings
from ..logger import get_logger
from .assets.icons import get_app_icon, get_icon_path


def _get_build_date() -> str:
    """Get build date from current date (when running) or app bundle info."""
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%d")


# Import workers and components
from .components.progress_tracking import EnhancedProgressBar

# Import core GUI components
from .core.session_manager import get_session_manager
from .core.settings_manager import get_gui_settings_manager

# Import dialogs
from .dialogs.first_run_setup_dialog import FirstRunSetupDialog

# Import modular tabs
from .tabs import (
    APIKeysTab,
    ClaimSearchTab,
    IntroductionTab,
    ProcessTab,
    SpeakerAttributionTab,
    SummarizationTab,
    SummaryCleanupTab,
    TranscriptionTab,
    WatcherTab,
    YouTubeTab,
)

logger = get_logger(__name__)


def _update_state_version(version: str) -> None:
    """Write the current version into state/application_state.json if present."""
    try:
        import json
        from pathlib import Path

        state_path = (
            Path(__file__).resolve().parents[3] / "state" / "application_state.json"
        )
        if not state_path.exists():
            return
        data = json.loads(state_path.read_text(encoding="utf-8"))
        # Update top-level version
        data["version"] = version
        # Update nested session version if present
        if isinstance(data.get("session"), dict):
            data["session"]["version"] = version
        state_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        logger.debug(f"State version update skipped: {e}")


class MainWindow(QMainWindow):
    """Streamlined main application window for Knowledge System using PyQt6."""

    # Thread-safe signals for dialog creation
    show_ffmpeg_dialog_signal = pyqtSignal()
    show_model_dialog_signal = pyqtSignal()

    def __init__(self) -> None:
        """Initialize the main window."""
        super().__init__()

        # Force window to be active (unless in testing mode)
        if not os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE"):
            self.setWindowState(Qt.WindowState.WindowActive)
        else:
            # In testing mode, start minimized and hidden
            self.setWindowState(Qt.WindowState.WindowMinimized)
            self.hide()  # Start hidden

        # Initialize settings FIRST before any UI creation
        self.settings = get_settings()

        # Initialize session and GUI settings managers
        self.session_manager = get_session_manager()
        self.gui_settings = get_gui_settings_manager()

        # Load API keys into environment variables immediately
        self._load_api_keys_to_environment()

        # Ensure state file reflects current version
        _update_state_version(__version__)

        # Initialize other attributes
        self.message_queue: queue.Queue[Any] = queue.Queue()
        self.active_threads: list[Any] = []

        # Setup UI
        self._setup_ui()

        # Set custom icon for the window
        self._set_window_icon()

        # Connect thread-safe dialog signals
        self.show_ffmpeg_dialog_signal.connect(self._show_first_run_ffmpeg_dialog)
        self.show_model_dialog_signal.connect(self._show_first_run_model_dialog)

        # Start message processor
        self.message_timer = QTimer()
        self.message_timer.timeout.connect(self._process_messages)
        self.message_timer.start(100)  # Check every 100ms

        # Load session state after UI is set up
        self._load_session()

        # Check for first-time Ollama setup (skip during testing)
        if not os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE"):
            QTimer.singleShot(2000, self._check_first_time_ollama_setup)

        # Check for updates if enabled (skip during testing)
        # Note: Update check disabled to prevent 404 errors during testing
        # Defer update check to prevent thread safety issues during initialization
        QTimer.singleShot(3000, self._check_for_updates_on_launch)

        # Monthly FFmpeg check (lightweight)
        self._ffmpeg_monthly_check()

        # Delay first-run setup to ensure GUI is fully ready and avoid thread violations
        QTimer.singleShot(500, self._delayed_first_run_setup)

    def _delayed_first_run_setup(self) -> None:
        """Delayed first-run setup to ensure GUI is fully initialized before creating dialogs."""
        try:
            # First-run FFmpeg setup (if needed)
            self._check_first_run_ffmpeg_setup()

            # First-run model setup (if needed)
            self._check_first_run_model_setup()
        except Exception as e:
            logger.warning(f"Delayed first-run setup failed: {e}")

    def _set_window_icon(self) -> None:
        """Set the custom window icon."""
        icon = get_app_icon()
        if icon:
            try:
                self.setWindowIcon(icon)
                icon_path = get_icon_path()
                logger.info(f"Window icon set from: {icon_path}")
            except Exception as e:
                logger.warning(f"Failed to set window icon: {e}")
        else:
            logger.warning("No custom icon found, using default")

    def _setup_ui(self) -> None:
        """Set up the streamlined main UI."""
        self.setWindowTitle("Skip the Podcast")
        # Make window resizable with reasonable default size and minimum size
        self.resize(1200, 800)  # Default size
        self.setMinimumSize(800, 600)  # Minimum size to ensure usability

        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Create model notification widget first
        from .widgets.model_notification_widget import ModelNotificationWidget
        self.model_notification = ModelNotificationWidget(self)
        self.model_notification.hide()
        self.model_notification.retry_requested.connect(self._retry_model_download)
        
        # Add notification widget at the top (initially hidden)
        main_layout.addWidget(self.model_notification)

        # Create tab widget with proper size policies
        self.tabs = QTabWidget()
        # Ensure tab widget can expand properly
        self.tabs.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        # Configure tabs to expand and fill available width
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setExpanding(True)
        main_layout.addWidget(self.tabs)

        # Settings tab will be added last to appear on the far right

        # Create progress widget (kept for compatibility but not added to layout to prevent overlap)
        self.progress_widget = EnhancedProgressBar()
        self.progress_widget.cancellation_requested.connect(
            self._handle_progress_cancellation
        )
        # NOTE: Intentionally NOT adding to layout to prevent overlapping with tab-specific progress displays
        # main_layout.addWidget(self.progress_widget)  # Commented out to fix blue box overlap issue

        # Create status bar with version info
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Add version label to the right side (show semantic version, not commit hash)
        version_msg = f"Skip the Podcast v{__version__} • Built: {_get_build_date()}"

        version_label = QLabel(version_msg)
        version_label.setStyleSheet("color: #666;")
        self.status_bar.addPermanentWidget(version_label)

        # Show ready message on the left side
        self.status_bar.showMessage("Ready")

        # Create modular tabs - all business logic is in the tab classes
        self._create_tabs()

        # Apply dark theme
        self._apply_dark_theme()

    def _create_tabs(self) -> None:
        """Create all modular tabs."""
        # Each tab handles its own business logic

        # Introduction tab - first tab for new users
        introduction_tab = IntroductionTab(self)
        introduction_tab.navigate_to_tab.connect(self._navigate_to_tab)
        self.tabs.addTab(introduction_tab, "Introduction")

        youtube_tab = YouTubeTab(self)
        self.tabs.addTab(youtube_tab, "Cloud Transcription")

        transcription_tab = TranscriptionTab(self)
        transcription_tab.navigate_to_tab.connect(self._navigate_to_tab)
        self.tabs.addTab(transcription_tab, "Local Transcription")

        # Speaker attribution tab for managing speaker identification
        speaker_attribution_tab = SpeakerAttributionTab(self)
        self.tabs.addTab(speaker_attribution_tab, "🎙️ Speaker Attribution")

        summarization_tab = SummarizationTab(self)
        self.tabs.addTab(summarization_tab, "Summarization")

        # Claim search tab for exploring extracted claims
        claim_search_tab = ClaimSearchTab(self)
        self.tabs.addTab(claim_search_tab, "🔍 Claim Search")

        # Summary cleanup tab for post-processing review
        summary_cleanup_tab = SummaryCleanupTab(self)
        self.tabs.addTab(summary_cleanup_tab, "✏️ Summary Cleanup")

        # Only add Process Management tab if enabled in settings
        settings = get_settings()
        if settings.gui_features.show_process_management_tab:
            process_tab = ProcessTab(self)
            self.tabs.addTab(process_tab, "Process Management")

        # Add Batch Processing tab (always available for advanced users)
        try:
            from .tabs.batch_processing_tab import BatchProcessingTab

            batch_processing_tab = BatchProcessingTab(self)
            self.tabs.addTab(batch_processing_tab, "🚀 Batch Processing")
        except ImportError as e:
            logger.warning(f"Batch processing tab not available: {e}")

        # Only add File Watcher tab if enabled in settings
        if settings.gui_features.show_file_watcher_tab:
            watcher_tab = WatcherTab(self)
            self.tabs.addTab(watcher_tab, "File Watcher")

        # Cloud uploads (manual) tab
        try:
            from .tabs import CloudUploadsTab

            if CloudUploadsTab is not None:
                cloud_uploads_tab = CloudUploadsTab(self)
                self.tabs.addTab(cloud_uploads_tab, "☁️ Cloud Uploads")
        except Exception as e:
            logger.warning(f"Cloud Uploads tab disabled: {e}")

        # Settings tab (far right)
        self.api_keys_tab = APIKeysTab(self)
        self.tabs.addTab(self.api_keys_tab, "⚙️ Settings")

        # Cloud sync status tab - DISABLED for redesign (saved for future re-tooling)
        # TODO: Re-enable when bidirectional sync is needed
        # if SyncStatusTab is not None:
        #     try:
        #         sync_status_tab = SyncStatusTab(self)
        #         self.tabs.addTab(sync_status_tab, "☁️ Sync Status")
        #     except Exception as e:
        #         logger.warning(f"Sync Status tab disabled: {e}")

    def _navigate_to_tab(self, tab_name: str) -> None:
        """Navigate to a specific tab by name."""
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == tab_name:
                self.tabs.setCurrentIndex(i)
                break

    def _apply_dark_theme(self) -> None:
        """Apply dark theme styling."""
        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #1e1e1e;
                font-family: 'Arial', sans-serif;
            }
            QTabWidget::pane {
                background-color: #2d2d2d;
                border: 1px solid #3c3c3c;
                font-family: 'Arial', sans-serif;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #cccccc;
                padding: 8px 16px;
                margin-right: 2px;
                font-family: 'Arial', sans-serif;
            }
            QTabBar::tab:selected {
                background-color: #007acc;
                color: white;
                font-family: 'Arial', sans-serif;
            }
            QGroupBox {
                background-color: #2d2d2d;
                border: 1px solid #3c3c3c;
                border-radius: 5px;
                margin-top: 10px;
                font-weight: bold;
                font-family: 'Arial', sans-serif;
            }
            QGroupBox::title {
                color: #ffffff;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                font-family: 'Arial', sans-serif;
            }
            QLabel {
                color: #cccccc;
                font-family: 'Arial', sans-serif;
            }
            QPushButton {
                background-color: #007acc;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 3px;
                font-family: 'Arial', sans-serif;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
            QPushButton:pressed {
                background-color: #004578;
            }
            QListWidget {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #4c4c4c;
                border-radius: 3px;
                font-family: 'Arial', sans-serif;
            }
            QTextEdit {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #4c4c4c;
                border-radius: 3px;
                font-family: 'Arial', sans-serif;
            }
            QLineEdit {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #4c4c4c;
                border-radius: 3px;
                padding: 4px;
                font-family: 'Arial', sans-serif;
            }
            QComboBox {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #4c4c4c;
                border-radius: 3px;
                padding: 4px;
                font-family: 'Arial', sans-serif;
            }
            QCheckBox {
                color: #cccccc;
                font-family: 'Arial', sans-serif;
            }
            QProgressBar {
                background-color: #3c3c3c;
                border: 1px solid #4c4c4c;
                border-radius: 3px;
                text-align: center;
                font-family: 'Arial', sans-serif;
            }
            QProgressBar::chunk {
                background-color: #007acc;
                border-radius: 2px;
            }
        """
        )

    def _handle_progress_cancellation(self, reason: str) -> None:
        """Handle progress bar cancellation requests."""
        logger.info(f"Progress cancellation requested: {reason}")

        # Cancel any active threads
        for thread in self.active_threads:
            if hasattr(thread, "request_cancellation"):
                thread.request_cancellation(reason)

        # Reset progress widget if it has reset capability
        try:
            if hasattr(self.progress_widget, "reset"):
                self.progress_widget.reset()
        except AttributeError:
            pass

        self.status_bar.showMessage(f"Operation cancelled: {reason}")

    def _load_api_keys_to_environment(self) -> None:
        """Load API keys to environment variables for processors to use."""
        try:
            # Set OpenAI API key
            if self.settings.api_keys.openai_api_key:
                os.environ["OPENAI_API_KEY"] = self.settings.api_keys.openai_api_key

            # Set Anthropic API key
            if self.settings.api_keys.anthropic_api_key:
                os.environ[
                    "ANTHROPIC_API_KEY"
                ] = self.settings.api_keys.anthropic_api_key

            logger.debug("API keys loaded to environment variables")

        except Exception as e:
            logger.error(f"Failed to load API keys to environment: {e}")

    def _process_messages(self) -> None:
        """Process messages from the message queue."""
        try:
            while not self.message_queue.empty():
                message = self.message_queue.get_nowait()
                # Process message types as needed
                logger.debug(f"Processing message: {message}")
        except Exception as e:
            logger.debug(f"Message processing error: {e}")

    def _load_session(self) -> None:
        """Load session state."""
        try:
            # Restore window geometry if available
            geometry = self.gui_settings.get_window_geometry()
            if geometry:
                self.setGeometry(
                    geometry["x"], geometry["y"], geometry["width"], geometry["height"]
                )

            logger.debug("Session state loaded successfully")
        except Exception as e:
            logger.error(f"Could not load session state: {e}")

    def _save_session(self) -> None:
        """Save session state."""
        try:
            # Save window geometry
            self.gui_settings.set_window_geometry(
                self.x(), self.y(), self.width(), self.height()
            )

            # Save all settings
            self.gui_settings.save()

            logger.debug("Session state saved successfully")
        except Exception as e:
            logger.error(f"Could not save session state: {e}")

    def _check_for_updates_on_launch(self) -> None:
        """Check for updates on application launch if enabled."""
        if hasattr(self, "api_keys_tab"):
            self.api_keys_tab.check_for_updates_on_launch()

    def _ffmpeg_monthly_check(self) -> None:
        """Run a monthly FFmpeg presence check and prompt to install if missing."""
        try:
            import shutil
            from datetime import datetime, timedelta

            from .core.settings_manager import get_gui_settings_manager

            gui = get_gui_settings_manager()
            last_check_iso = gui.get_value("⚙️ Settings", "ffmpeg_last_check", "")
            now = datetime.now()
            do_check = True
            if last_check_iso:
                try:
                    last = datetime.fromisoformat(last_check_iso)
                    if now - last < timedelta(days=30):
                        do_check = False
                except (ValueError, TypeError):
                    pass  # Invalid datetime format

            if not do_check:
                return

            # Record check time early to avoid repeated prompts
            gui.set_value("⚙️ Settings", "ffmpeg_last_check", now.isoformat())
            gui.save()

            # Quick presence check
            if shutil.which("ffmpeg"):
                return

            # Prompt via status bar
            self.status_bar.showMessage(
                "FFmpeg not found. You can install it from Settings → Install/Update FFmpeg."
            )
        except (ImportError, AttributeError):
            pass  # FFmpeg check failed

    def _check_first_run_ffmpeg_setup(self) -> None:
        """Check if this is first run and offer FFmpeg setup."""
        try:
            # CRITICAL: Skip first-run dialogs during testing
            if os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE"):
                logger.info("🧪 Testing mode: Skipping first-run FFmpeg setup dialog")
                return

            import shutil

            from .core.settings_manager import get_gui_settings_manager

            gui = get_gui_settings_manager()

            # Check if we've already shown the first-run dialog
            first_run_shown = gui.get_value(
                "⚙️ Settings", "ffmpeg_first_run_shown", False
            )

            if first_run_shown:
                return  # Already shown, don't show again

            # Check if FFmpeg is already available
            if shutil.which("ffmpeg"):
                # FFmpeg already available, mark first-run as shown and skip
                gui.set_value("⚙️ Settings", "ffmpeg_first_run_shown", True)
                gui.save()
                return

            # Show first-run setup dialog
            # Use an in-memory guard to prevent duplicate dialogs during startup
            if getattr(self, "_ffmpeg_first_run_dialog_open", False):
                return
            setattr(self, "_ffmpeg_first_run_dialog_open", True)

            # Use QTimer to emit signal after main window is fully loaded (thread-safe)
            from PyQt6.QtCore import QTimer

            QTimer.singleShot(1000, self.show_ffmpeg_dialog_signal.emit)

        except (ImportError, AttributeError) as e:
            logger.warning(f"First-run FFmpeg setup failed: {e}")

    def _show_first_run_ffmpeg_dialog(self) -> None:
        """Show the first-run FFmpeg setup dialog."""
        try:
            # CRITICAL: Additional safety check for testing mode
            if os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE"):
                logger.info(
                    "🧪 Testing mode: Blocked FFmpeg dialog creation (safety check)"
                )
                return

            from .dialogs.ffmpeg_setup_dialog import FFmpegSetupDialog

            dialog = FFmpegSetupDialog(self)
            dialog.exec()
            # Persist the flag after the user has seen the dialog once
            try:
                from .core.settings_manager import get_gui_settings_manager

                gui = get_gui_settings_manager()
                gui.set_value("⚙️ Settings", "ffmpeg_first_run_shown", True)
                gui.save()
            except Exception as e:
                logger.debug(f"Could not save FFmpeg first run flag: {e}")
            # Clear the guard regardless of result
            setattr(self, "_ffmpeg_first_run_dialog_open", False)
        except Exception as e:
            logger.warning(f"Failed to show first-run FFmpeg dialog: {e}")

    def _check_first_time_ollama_setup(self) -> None:
        """Check if this is a first-time install and force Ollama setup."""
        try:
            from pathlib import Path

            from ..utils.ollama_manager import get_ollama_manager
            from .core.settings_manager import get_gui_settings_manager

            gui = get_gui_settings_manager()
            ollama_manager = get_ollama_manager()

            # Check if we've already set up Ollama
            ollama_setup_done = gui.get_value("⚙️ Settings", "ollama_setup_done", False)

            # Check for fresh install markers that indicate this is a new installation
            fresh_install_markers = [
                Path.home() / ".skip_the_podcast_desktop_installed",
                Path.home() / ".skip_the_podcast_desktop_authorized",
            ]

            is_fresh_install = any(marker.exists() for marker in fresh_install_markers)

            if ollama_setup_done and not is_fresh_install:
                return  # Already set up and not a fresh install

            # Check if Ollama is already installed and running
            is_installed, _ = ollama_manager.is_installed()
            is_running = ollama_manager.is_service_running()

            if is_installed and is_running:
                # Ollama is working, just mark as set up
                gui.set_value("⚙️ Settings", "ollama_setup_done", True)
                gui.save()
                logger.info("✅ Ollama already working - setup marked complete")
                return

            # Force Ollama installation/setup for new installations
            if is_fresh_install or not is_installed:
                logger.info("🦙 Fresh install detected - forcing Ollama setup")
                self._force_ollama_installation()
            elif is_installed and not is_running:
                logger.info("🦙 Ollama installed but not running - starting service")
                self._start_ollama_service()

        except Exception as e:
            logger.warning(f"Failed to check first-time Ollama setup: {e}")

    def _force_ollama_installation(self) -> None:
        """Force Ollama installation on fresh installs."""
        try:
            from ..utils.ollama_manager import get_ollama_manager
            from .legacy_dialogs import OllamaInstallDialog

            ollama_manager = get_ollama_manager()

            # Check if already installed
            is_installed, _ = ollama_manager.is_installed()
            if is_installed:
                self._start_ollama_service()
                return

            # Show installation dialog
            dialog = OllamaInstallDialog(self)
            dialog.setWindowTitle("Welcome - Setting up AI Engine")

            # Make it clear this is required for the app to work
            if hasattr(dialog, "description_label"):
                dialog.description_label.setText(
                    "Skip the Podcast Desktop requires Ollama for AI-powered features.\n"
                    "This will download and install Ollama (~200MB) for local AI processing."
                )

            result = dialog.exec()

            if result == dialog.DialogCode.Accepted:
                logger.info("✅ Ollama installation completed")
                # Mark setup as done
                from .core.settings_manager import get_gui_settings_manager

                gui = get_gui_settings_manager()
                gui.set_value("⚙️ Settings", "ollama_setup_done", True)
                gui.save()
            else:
                logger.warning("⚠️ User declined Ollama installation")

        except Exception as e:
            logger.error(f"Failed to force Ollama installation: {e}")

    def _start_ollama_service(self) -> None:
        """Start Ollama service if installed but not running."""
        try:
            from ..utils.ollama_manager import get_ollama_manager

            ollama_manager = get_ollama_manager()
            success, message = ollama_manager.start_service()

            if success:
                logger.info("✅ Ollama service started successfully")
                # Mark setup as done
                from .core.settings_manager import get_gui_settings_manager

                gui = get_gui_settings_manager()
                gui.set_value("⚙️ Settings", "ollama_setup_done", True)
                gui.save()
            else:
                logger.warning(f"Failed to start Ollama service: {message}")

        except Exception as e:
            logger.error(f"Failed to start Ollama service: {e}")

    def _start_background_model_download(self, missing_models: dict) -> None:
        """Start downloading missing models in background."""
        try:
            from PyQt6.QtCore import QThread, QObject, pyqtSignal
            from ..processors.whisper_cpp_transcribe import WhisperCppTranscribeProcessor
            from ..utils.ollama_manager import get_ollama_manager
            
            class BackgroundModelDownloader(QObject):
                progress = pyqtSignal(str)
                finished = pyqtSignal(bool)
                
                def __init__(self, models_to_download):
                    super().__init__()
                    self.models = models_to_download
                    
                def download(self):
                    try:
                        # Download Whisper model if needed
                        if "whisper" in self.models:
                            self.progress.emit("📥 Downloading Whisper model...")
                            processor = WhisperCppTranscribeProcessor(model=self.models["whisper"])
                            
                            def whisper_progress(info):
                                if isinstance(info, dict):
                                    percent = info.get('percent', 0)
                                    message = info.get('message', '')
                                    self.progress.emit(f"whisper|{percent}|{message}")
                            
                            model_path = processor._download_model(self.models["whisper"], whisper_progress)
                            if model_path and model_path.exists():
                                self.progress.emit("whisper|100|✅ Whisper model downloaded")
                            else:
                                self.progress.emit("whisper|-1|⚠️ Failed to download Whisper model")
                        
                        # Download LLM model if needed
                        if "llm" in self.models:
                            self.progress.emit(f"📥 Downloading LLM model: {self.models['llm']}...")
                            ollama = get_ollama_manager()
                            if ollama.is_service_running():
                                success = ollama.download_model(self.models["llm"])
                                if success:
                                    self.progress.emit(f"✅ LLM model {self.models['llm']} downloaded")
                                else:
                                    self.progress.emit(f"⚠️ Failed to download LLM model")
                            else:
                                self.progress.emit("⚠️ Ollama not running - skipping LLM download")
                        
                        self.finished.emit(True)
                    except Exception as e:
                        logger.error(f"Background model download failed: {e}")
                        self.finished.emit(False)
            
            # Create and start background thread
            self.model_download_thread = QThread()
            self.model_downloader = BackgroundModelDownloader(missing_models)
            self.model_downloader.moveToThread(self.model_download_thread)
            
            # Connect signals
            self.model_download_thread.started.connect(self.model_downloader.download)
            self.model_downloader.progress.connect(self._handle_model_download_progress)
            self.model_downloader.finished.connect(self.model_download_thread.quit)
            self.model_downloader.finished.connect(
                lambda success: logger.info("✅ Background model downloads completed" if success else "⚠️ Some model downloads failed")
            )
            
            # Clean up thread when done
            self.model_download_thread.finished.connect(self.model_download_thread.deleteLater)
            
            # Start download
            self.model_download_thread.start()
            
        except Exception as e:
            logger.error(f"Failed to start background model download: {e}")
    
    def _handle_model_download_progress(self, message: str) -> None:
        """Handle progress updates from model downloads."""
        try:
            # Parse progress message format: "model_type|percent|message" or plain message
            if '|' in message:
                parts = message.split('|', 2)
                if len(parts) == 3:
                    model_type, percent_str, status_msg = parts
                    try:
                        percent = int(percent_str)
                        if percent == -1:
                            # Download failed
                            self.model_notification.show_completion(model_type, False, status_msg)
                        elif percent == 100:
                            # Download completed
                            self.model_notification.show_completion(model_type, True, status_msg)
                        else:
                            # Download in progress
                            self.model_notification.update_progress(model_type, percent, status_msg)
                    except ValueError:
                        pass
            else:
                # Plain message - show in status bar
                self.status_bar.showMessage(message, 5000)
                
                # Also show in notification if it's a start message
                if "Downloading" in message:
                    model_type = "whisper" if "Whisper" in message else "llm"
                    self.model_notification.show_model_download(model_type, message)
                    
        except Exception as e:
            logger.error(f"Error handling model download progress: {e}")
    
    def _retry_model_download(self, model_type: str) -> None:
        """Retry downloading a specific model."""
        try:
            from ..utils.model_validator import get_model_validator
            
            validator = get_model_validator()
            missing = validator.get_missing_models()
            
            if model_type in missing:
                logger.info(f"Retrying download of {model_type} model...")
                self._start_background_model_download({model_type: missing[model_type]})
            else:
                logger.info(f"Model {model_type} is already installed")
                self.model_notification.show_completion(model_type, True, "Model is already installed")
                
        except Exception as e:
            logger.error(f"Failed to retry model download: {e}")

    def _check_first_run_model_setup(self) -> None:
        """Check models and download missing ones automatically."""
        try:
            # CRITICAL: Skip first-run dialogs during testing
            if os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE"):
                logger.info("🧪 Testing mode: Skipping first-run model setup dialog")
                return

            from pathlib import Path

            from .core.settings_manager import get_gui_settings_manager
            from ..utils.model_validator import get_model_validator

            gui = get_gui_settings_manager()
            validator = get_model_validator()

            # Check if post-install setup was completed
            post_install_marker = Path.home() / ".knowledge_chipper" / "settings" / "post_install_complete.json"
            
            # Always validate models on startup
            logger.info("🔍 Validating installed models...")
            
            # Log detailed validation info
            whisper_models = validator.check_whisper_models()
            llm_models = validator.check_llm_models()
            logger.info(f"Whisper models found: {whisper_models}")
            logger.info(f"LLM models found: {llm_models}")
            
            missing_models = validator.get_missing_models()
            
            if missing_models:
                logger.info(f"📥 Missing essential models: {missing_models}")
                
                # Check if we should show dialog or download automatically
                auto_download = gui.get_value("⚙️ Settings", "auto_download_models", True)
                model_first_run = gui.get_value("⚙️ Settings", "model_first_run_shown", False)
                
                logger.info(f"Auto download: {auto_download}, First run shown: {model_first_run}, Post-install marker: {post_install_marker.exists()}")
                
                if auto_download and not post_install_marker.exists() and not model_first_run:
                    # First run after install - show dialog
                    gui.set_value("⚙️ Settings", "model_first_run_shown", True)
                    gui.save()
                    
                    # Use QTimer to emit signal after main window is fully loaded
                    from PyQt6.QtCore import QTimer
                    QTimer.singleShot(2000, self.show_model_dialog_signal.emit)
                else:
                    # Background download missing models
                    logger.info("🚀 Starting background model downloads...")
                    self._start_background_model_download(missing_models)
            else:
                logger.info("✅ All essential models are installed")
                
                # Log detailed status
                status_report = validator.get_model_status_report()
                for line in status_report.split('\n'):
                    logger.debug(line)

        except (ImportError, AttributeError) as e:
            logger.warning(f"Model validation failed: {e}")

    def _show_first_run_model_dialog(self) -> None:
        """Show the first-run model setup dialog."""
        try:
            # CRITICAL: Additional safety check for testing mode
            if os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE"):
                logger.info(
                    "🧪 Testing mode: Blocked model setup dialog creation (safety check)"
                )
                return

            dialog = FirstRunSetupDialog(self)

            def on_setup_completed(success: bool):
                if success:
                    logger.info("First-run model setup completed successfully")
                    self.status_bar.showMessage(
                        "Model setup complete - ready to transcribe!", 5000
                    )
                else:
                    logger.info("First-run model setup skipped or cancelled")
                    self.status_bar.showMessage(
                        "Model setup skipped - you can download models later", 3000
                    )

            dialog.setup_completed.connect(on_setup_completed)
            dialog.exec()

        except Exception as e:
            logger.warning(f"Failed to show first-run model dialog: {e}")

    def closeEvent(self, event: QCloseEvent | None) -> None:
        """Handle window close event."""
        try:
            # Save session before closing
            self._save_session()

            # Cancel any active threads
            for thread in self.active_threads:
                if hasattr(thread, "request_cancellation"):
                    thread.request_cancellation("Application closing")

            # Accept the close event
            if event:
                event.accept()

        except Exception as e:
            logger.error(f"Error during close: {e}")
            if event:
                event.accept()


def launch_gui() -> None:
    """Launch the Knowledge System GUI application."""
    try:
        # Import PyQt6 first to check availability
        import os

        from PyQt6.QtCore import QLoggingCategory
        from PyQt6.QtGui import QIcon  # noqa: F401
        from PyQt6.QtWidgets import QApplication

        # Suppress Qt CSS warnings about unknown properties like "transform"
        # Qt's CSS parser doesn't support all CSS3 properties and generates warnings
        QLoggingCategory.setFilterRules("qt.qss.debug=false")

        # For macOS: Set environment variables to avoid Python rocket ship icon
        if sys.platform == "darwin":
            os.environ["PYQT_MACOS_BUNDLE_IDENTIFIER"] = "com.skipthepodcast.desktop"
            # Try to use app bundle path if available
            bundle_path = os.environ.get("RESOURCEPATH")
            if not bundle_path and hasattr(sys, "_MEIPASS"):
                bundle_path = sys._MEIPASS

        # Create the QApplication
        app = QApplication(sys.argv)

        # For macOS: Additional setup to avoid rocket ship icon and thread safety
        # CRITICAL: Ensure Qt initializes properly on macOS main thread
        if sys.platform == "darwin":
            # Force Qt to use the main thread for all window operations
            try:
                app.setAttribute(
                    Qt.ApplicationAttribute.AA_DontCreateNativeWidgetSiblings, True
                )
            except Exception:
                pass
        if sys.platform == "darwin":
            try:
                # Set the activation policy to regular application
                from AppKit import NSApplication, NSApplicationActivationPolicyRegular

                ns_app = NSApplication.sharedApplication()
                ns_app.setActivationPolicy_(NSApplicationActivationPolicyRegular)

                # Ensure we're on the main thread for macOS operations
                import threading

                if not threading.current_thread() is threading.main_thread():
                    logger.warning(
                        "GUI launch not on main thread - this may cause issues on macOS"
                    )

            except ImportError:
                # AppKit not available, use alternative approach
                # Set process name to help with icon association
                try:
                    import ctypes
                    from ctypes import c_char_p

                    libc = ctypes.CDLL("libc.dylib")
                    libc.setproctitle(c_char_p(b"Skipthepodcast.com"))
                except (OSError, AttributeError, ImportError):
                    pass  # Process title setting failed

        # Set application properties
        app.setApplicationName("Skip the Podcast Desktop")
        app.setApplicationDisplayName("Skip the Podcast Desktop")
        app.setApplicationVersion(__version__)
        app.setOrganizationName("Skip the Podcast Desktop")
        app.setOrganizationDomain("knowledge-chipper.local")

        # Set custom application icon (both window and app icon)
        app_icon = get_app_icon()
        if app_icon:
            try:
                app.setWindowIcon(app_icon)
                icon_path = get_icon_path()
                logger.info(f"Application icon set from: {icon_path}")
            except Exception as e:
                logger.warning(f"Failed to set application icon: {e}")
        else:
            logger.warning("No custom icon found for application")

        # Check and request macOS permissions if needed
        if sys.platform == "darwin":
            try:
                # Log comprehensive security status for debugging
                from knowledge_system.utils.security_verification import (
                    log_security_status,
                )

                log_security_status()

                # First check if we need Full Disk Access for better functionality
                from knowledge_system.utils.macos_fda_helper import (
                    ensure_fda_on_startup,
                )

                # This provides the Disk Drill-like FDA request experience
                ensure_fda_on_startup()

                # Also do basic permission checks
                from knowledge_system.utils.macos_permissions import (
                    ensure_permissions_on_startup,
                )

                ensure_permissions_on_startup()
            except Exception as e:
                logger.debug(f"Permission check failed (non-critical): {e}")

        # Check if we're in testing mode and set environment variable for subprocess
        testing_mode = os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE") == "1"
        if testing_mode:
            logger.info(
                "🧪 GUI subprocess detected testing mode - setting environment for child processes"
            )
            # Ensure all child processes know we're in testing mode
            os.environ["KNOWLEDGE_CHIPPER_TESTING_MODE"] = "1"

        # Create the main window
        window = MainWindow()

        # Show and focus behavior depends on testing mode
        if not os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE"):
            # Normal mode: show and focus
            window.show()
            window.raise_()
            window.activateWindow()
        else:
            # Testing mode: show hidden without focus stealing
            window.show()  # This is needed for GUI automation to work
            window.setWindowState(Qt.WindowState.WindowMinimized)
            logger.info("GUI launched in testing mode - minimized and hidden")

        # Start the event loop
        sys.exit(app.exec())

    except ImportError as e:
        print("\n" + "=" * 60)
        print("ERROR: PyQt6 is not installed!")
        print("Knowledge_Chipper GUI requires PyQt6.")
        print("Please install it with:")
        print("  pip install PyQt6")
        print("=" * 60 + "\n")
        print(f"Error details: {e}")
        sys.exit(1)


# The main() function has been moved to __main__.py to avoid sys.modules warnings
# when launching with python -m knowledge_system.gui
