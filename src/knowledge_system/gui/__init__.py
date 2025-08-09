""" GUI components for the knowledge system.""".

from .dialogs import (
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
    "main",
    "launch_gui",
]
