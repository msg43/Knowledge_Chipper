"""GUI components for the knowledge system."""

# Import dialog classes from legacy_dialogs.py (renamed to avoid conflict with dialogs/ directory)
# Lightweight preflight on import (do not crash GUI if it fails)
import os as _os

# Import from new dialogs directory
from .dialogs.ffmpeg_prompt_dialog import FFmpegPromptDialog
from .dialogs.ffmpeg_setup_dialog import FFmpegSetupDialog
from .dialogs.first_run_setup_dialog import FirstRunSetupDialog
from .legacy_dialogs import (
    ExtractionProgressDialog,
    MOCProgressDialog,
    ModelDownloadDialog,
    OllamaInstallDialog,
    OllamaServiceDialog,
    ProcessingProgressDialog,
    SummarizationProgressDialog,
    TranscriptionProgressDialog,
)
from .main_window_pyqt6 import MainWindow, launch_gui

if _os.getenv("KC_SKIP_PREFLIGHT", "0").lower() not in ("1", "true", "yes"):
    try:  # pragma: no cover - environment specific
        from ..utils.preflight import quick_preflight as _qp

        _qp()
    except Exception as e:
        # Don't silently swallow preflight failures - they indicate real problems!
        import sys
        import traceback

        print("\n" + "=" * 70)
        print("❌ PREFLIGHT CHECK FAILED - APP CANNOT START")
        print("=" * 70)
        print(f"\nError: {e}")
        print("\nThis check verifies critical dependencies are available.")
        print("The app cannot function without these components.\n")
        traceback.print_exc()
        print("\n" + "=" * 70)

        # Re-raise to prevent broken app from launching
        raise

# Use the proper GUI launcher instead of the deprecated redirect
main = launch_gui

__all__ = [
    "MainWindow",
    "ModelDownloadDialog",
    "OllamaServiceDialog",
    "OllamaInstallDialog",
    "ProcessingProgressDialog",
    "TranscriptionProgressDialog",
    "SummarizationProgressDialog",
    "ExtractionProgressDialog",
    "MOCProgressDialog",
    "FFmpegPromptDialog",
    "FFmpegSetupDialog",
    "FirstRunSetupDialog",
    "main",
    "launch_gui",
]
