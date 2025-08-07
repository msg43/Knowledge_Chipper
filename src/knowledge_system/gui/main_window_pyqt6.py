"""
Main GUI Window for Knowledge System - PyQt6 Implementation

Streamlined main window that focuses on window setup and coordination.
All business logic has been moved to modular tab classes.
"""

import json
import os
import queue
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QCloseEvent, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..config import get_settings
from ..logger import get_logger
from ..version import VERSION, BRANCH, BUILD_DATE
from .assets.icons import get_app_icon, get_icon_path

# Import workers and components
from .components.progress_tracking import EnhancedProgressBar

# Import core GUI components
from .core.session_manager import get_session_manager
from .core.settings_manager import get_gui_settings_manager

# Import modular tabs
from .tabs import (
    APIKeysTab,
    IntroductionTab,
    ProcessTab,
    SummarizationTab,
    TranscriptionTab,
    WatcherTab,
    YouTubeTab,
)

logger = get_logger(__name__)


class MainWindow(QMainWindow):
    """Streamlined main application window for Knowledge System using PyQt6."""

    def __init__(self) -> None:
        super().__init__()

        # Force window to be active
        self.setWindowState(Qt.WindowState.WindowActive)

        # Initialize settings FIRST before any UI creation
        self.settings = get_settings()

        # Initialize session and GUI settings managers
        self.session_manager = get_session_manager()
        self.gui_settings = get_gui_settings_manager()

        # Load API keys into environment variables immediately
        self._load_api_keys_to_environment()

        # Initialize other attributes
        self.message_queue: queue.Queue[Any] = queue.Queue()
        self.active_threads: list[Any] = []

        # Setup UI
        self._setup_ui()

        # Set custom icon for the window
        self._set_window_icon()

        # Start message processor
        self.message_timer = QTimer()
        self.message_timer.timeout.connect(self._process_messages)
        self.message_timer.start(100)  # Check every 100ms

        # Load session state after UI is set up
        self._load_session()

        # Check for updates if enabled
        self._check_for_updates_on_launch()

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
        self.setWindowTitle(f"Knowledge Chipper v{VERSION} - Your Personal Knowledge Assistant")
        # Make window resizable with reasonable default size and minimum size
        self.resize(1200, 800)  # Default size
        self.setMinimumSize(800, 600)  # Minimum size to ensure usability

        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Create tab widget with proper size policies
        self.tabs = QTabWidget()
        # Ensure tab widget can expand properly
        self.tabs.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        main_layout.addWidget(self.tabs)

        # Create API Keys tab first (needed for update checks)
        self.api_keys_tab = APIKeysTab(self)
        self.tabs.addTab(self.api_keys_tab, "⚙️ Settings")

        # Create progress widget
        self.progress_widget = EnhancedProgressBar()
        self.progress_widget.cancellation_requested.connect(
            self._handle_progress_cancellation
        )
        main_layout.addWidget(self.progress_widget)

        # Create status bar with version info
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Add version label to the right side
        version_msg = f"Knowledge Chipper v{VERSION} ({BRANCH}) • Built: {BUILD_DATE}"
        
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
        self.tabs.addTab(youtube_tab, "YouTube")

        transcription_tab = TranscriptionTab(self)
        self.tabs.addTab(transcription_tab, "Transcription")

        summarization_tab = SummarizationTab(self)
        self.tabs.addTab(summarization_tab, "Summarization")

        process_tab = ProcessTab(self)
        self.tabs.addTab(process_tab, "Process Management")

        watcher_tab = WatcherTab(self)
        self.tabs.addTab(watcher_tab, "File Watcher")

        api_keys_tab = APIKeysTab(self)
        self.tabs.addTab(api_keys_tab, "API Keys")

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
            }
            QTabWidget::pane {
                background-color: #2d2d2d;
                border: 1px solid #3c3c3c;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #cccccc;
                padding: 8px 16px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #007acc;
                color: white;
            }
            QGroupBox {
                background-color: #2d2d2d;
                border: 1px solid #3c3c3c;
                border-radius: 5px;
                margin-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title {
                color: #ffffff;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QLabel {
                color: #cccccc;
            }
            QPushButton {
                background-color: #007acc;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 3px;
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
            }
            QTextEdit {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #4c4c4c;
                border-radius: 3px;
            }
            QLineEdit {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #4c4c4c;
                border-radius: 3px;
                padding: 4px;
            }
            QComboBox {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #4c4c4c;
                border-radius: 3px;
                padding: 4px;
            }
            QCheckBox {
                color: #cccccc;
            }
            QProgressBar {
                background-color: #3c3c3c;
                border: 1px solid #4c4c4c;
                border-radius: 3px;
                text-align: center;
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
    import sys

    try:
        # Import PyQt6 first to check availability
        from PyQt6.QtGui import QIcon
        from PyQt6.QtWidgets import QApplication

        # Create the QApplication
        app = QApplication(sys.argv)

        # Set application properties
        app.setApplicationName("Knowledge_Chipper")
        app.setApplicationDisplayName("Knowledge_Chipper")
        app.setApplicationVersion("1.0")
        app.setOrganizationName("Knowledge_Chipper")
        app.setOrganizationDomain("knowledge-chipper.local")

        # Set custom application icon
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

        # Create and show the main window
        window = MainWindow()
        window.show()

        # Ensure the window is raised and gets focus
        window.raise_()
        window.activateWindow()

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
