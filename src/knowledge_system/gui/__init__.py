"""GUI components for the knowledge system."""

from .main_window_pyqt6 import MainWindow, launch_gui
from .dialogs import (
    ModelDownloadDialog, OllamaServiceDialog, OllamaInstallDialog,
    ProcessingProgressDialog, TranscriptionProgressDialog, SummarizationProgressDialog,
    ExtractionProgressDialog, MOCProgressDialog
)

# Use the proper GUI launcher instead of the deprecated redirect
main = launch_gui

__all__ = [
    "MainWindow", "ModelDownloadDialog", "OllamaServiceDialog", "OllamaInstallDialog",
    "ProcessingProgressDialog", "TranscriptionProgressDialog", "SummarizationProgressDialog",
    "ExtractionProgressDialog", "MOCProgressDialog", "main", "launch_gui"
]
