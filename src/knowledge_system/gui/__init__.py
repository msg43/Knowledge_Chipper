"""GUI components for the knowledge system."""

# Import dialog classes from legacy_dialogs.py (renamed to avoid conflict with dialogs/ directory)
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

# Import from new dialogs directory 
from .dialogs.ffmpeg_prompt_dialog import FFmpegPromptDialog
from .dialogs.ffmpeg_setup_dialog import FFmpegSetupDialog
from .dialogs.first_run_setup_dialog import FirstRunSetupDialog
from .main_window_pyqt6 import MainWindow, launch_gui

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
