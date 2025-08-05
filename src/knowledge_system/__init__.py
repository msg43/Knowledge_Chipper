"""
Knowledge_Chipper - A comprehensive knowledge management system for macOS.

This package provides AI-powered tools for transcribing, summarizing, and organizing
videos, audio files, and documents into searchable knowledge.
"""

__version__ = "0.1.0"
__author__ = "Knowledge_Chipper"
__email__ = "dev@knowledge-system.local"

# Core imports
from .config import Settings, get_settings
from .logger import get_logger


def gui_main() -> None:
    """Launch the GUI application from the main package."""
    import sys

    # Smart cache clearing - clear only if needed
    try:
        from .utils.cache_management import clear_cache_if_needed

        was_cleared, message = clear_cache_if_needed()
        if was_cleared:
            print(f"🧹 {message}")
    except Exception as e:
        # Don't let cache clearing errors prevent startup
        print(f"⚠️  Cache clearing check failed: {e}")

    try:
        # Import PyQt6 first to check availability
        from PyQt6.QtWidgets import QApplication

        # Create the QApplication
        app = QApplication(sys.argv)

        # Set application properties
        app.setApplicationName("Knowledge_Chipper")
        app.setApplicationDisplayName("Knowledge_Chipper")
        app.setApplicationVersion("1.0")

        # Import and create main window (no circular import since we're in the parent package)
        from .gui.main_window_pyqt6 import MainWindow

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


__all__ = ["Settings", "get_settings", "get_logger", "gui_main", "__version__"]
