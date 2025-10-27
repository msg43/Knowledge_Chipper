"""
UI interaction helpers for real GUI testing.

Provides functions to interact with GUI widgets programmatically.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QCheckBox, QComboBox, QLineEdit, QPushButton, QWidget

from .test_utils import process_events_for


def get_transcribe_tab(main_window: QObject) -> QWidget | None:
    """Get the Transcribe tab widget."""
    tabs = getattr(main_window, "tabs", None)
    if not tabs:
        return None
    for i in range(tabs.count()):
        if tabs.tabText(i).lower() == "transcribe":
            return tabs.widget(i)
    return None


def get_summarize_tab(main_window: QObject) -> QWidget | None:
    """Get the Summarize tab widget."""
    tabs = getattr(main_window, "tabs", None)
    if not tabs:
        return None
    for i in range(tabs.count()):
        if tabs.tabText(i).lower() == "summarize":
            return tabs.widget(i)
    return None


def find_combo_by_label(parent: QWidget, label_text: str) -> QComboBox | None:
    """Find a combobox near a label containing text."""
    # Search for all comboboxes in the parent
    for combo in parent.findChildren(QComboBox):
        # Check if combo has an object name containing the label
        if label_text.lower() in combo.objectName().lower():
            return combo
        # Check parent widget labels
        combo_parent = combo.parent()
        if combo_parent:
            # Look for nearby labels or group box titles
            if (
                hasattr(combo_parent, "title")
                and label_text.lower() in combo_parent.title().lower()
            ):
                return combo
    return None


def find_checkbox_by_label(parent: QWidget, label_text: str) -> QCheckBox | None:
    """Find a checkbox with or near a label containing text."""
    for checkbox in parent.findChildren(QCheckBox):
        if label_text.lower() in checkbox.text().lower():
            return checkbox
        if label_text.lower() in checkbox.objectName().lower():
            return checkbox
    return None


def set_provider(tab: QWidget, provider_name: str) -> bool:
    """Set the provider dropdown to specified value."""
    # Look for provider combobox
    provider_combo = find_combo_by_label(tab, "provider")
    if not provider_combo:
        # Try finding by common naming patterns
        for combo in tab.findChildren(QComboBox):
            if "provider" in combo.objectName().lower():
                provider_combo = combo
                break

    if not provider_combo:
        raise ValueError("Provider combobox not found")

    # Find and set the provider
    for i in range(provider_combo.count()):
        if provider_name.lower() in provider_combo.itemText(i).lower():
            provider_combo.setCurrentIndex(i)
            process_events_for(200)
            return True

    raise ValueError(f"Provider '{provider_name}' not found in dropdown")


def set_model(tab: QWidget, model_name: str) -> bool:
    """Set the model dropdown to specified value."""
    model_combo = find_combo_by_label(tab, "model")
    if not model_combo:
        # Try finding by common naming patterns
        for combo in tab.findChildren(QComboBox):
            if "model" in combo.objectName().lower():
                model_combo = combo
                break

    if not model_combo:
        raise ValueError("Model combobox not found")

    # Find and set the model
    for i in range(model_combo.count()):
        if model_name.lower() in model_combo.itemText(i).lower():
            model_combo.setCurrentIndex(i)
            process_events_for(200)
            return True

    raise ValueError(f"Model '{model_name}' not found in dropdown")


def set_language(tab: QWidget, language: str) -> bool:
    """Set the language dropdown to specified value."""
    lang_combo = find_combo_by_label(tab, "language")
    if not lang_combo:
        for combo in tab.findChildren(QComboBox):
            if (
                "language" in combo.objectName().lower()
                or "lang" in combo.objectName().lower()
            ):
                lang_combo = combo
                break

    if not lang_combo:
        # Language might not be a required setting
        return False

    for i in range(lang_combo.count()):
        if language.lower() in lang_combo.itemText(i).lower():
            lang_combo.setCurrentIndex(i)
            process_events_for(200)
            return True

    return False


def enable_diarization(tab: QWidget, sensitivity: str = "conservative") -> bool:
    """Enable diarization checkbox and set sensitivity if available."""
    diarization_checkbox = find_checkbox_by_label(tab, "diarization")
    if not diarization_checkbox:
        diarization_checkbox = find_checkbox_by_label(tab, "speaker")

    if not diarization_checkbox:
        raise ValueError("Diarization checkbox not found")

    if not diarization_checkbox.isChecked():
        diarization_checkbox.setChecked(True)
        process_events_for(100)

    # Try to set sensitivity if there's a combo for it
    sensitivity_combo = find_combo_by_label(tab, "sensitivity")
    if sensitivity_combo:
        for i in range(sensitivity_combo.count()):
            if sensitivity.lower() in sensitivity_combo.itemText(i).lower():
                sensitivity_combo.setCurrentIndex(i)
                process_events_for(100)
                break

    return True


def add_file_to_transcribe(tab: QWidget, file_path: Path) -> bool:
    """Add a file to the transcription queue programmatically."""
    # The TranscriptionTab uses a QListWidget called transcription_files
    if hasattr(tab, "transcription_files"):
        tab.transcription_files.addItem(str(file_path))
        process_events_for(100)
        return True

    return False


def add_file_to_summarize(tab: QWidget, file_path: Path) -> bool:
    """Add a file to the summarization queue programmatically."""
    # The SummarizationTab uses a QListWidget called file_list
    if hasattr(tab, "file_list"):
        tab.file_list.addItem(str(file_path))
        process_events_for(100)
        return True

    return False


def wait_for_completion(
    tab: QWidget, timeout_seconds: int = 120, check_interval: float = 1.0
) -> bool:
    """
    Wait for processing to complete by monitoring UI state.

    Returns True if processing completed, False if timeout.
    """
    start = time.time()
    while time.time() - start < timeout_seconds:
        process_events_for(int(check_interval * 1000))

        # Check if processing is complete
        if is_processing_complete(tab):
            # Give extra time for database writes to complete after UI updates
            # The worker may update UI before finishing DB transactions
            process_events_for(2000)  # 2 second buffer
            return True

        # Check for error state
        if is_processing_error(tab):
            return False

    return False


def is_processing_complete(tab: QWidget) -> bool:
    """Check if processing has completed by inspecting tab state."""
    # Look for completion indicators
    # This depends on the tab implementation

    # Check for a progress bar at 100%
    from PyQt6.QtWidgets import QProgressBar

    for progress_bar in tab.findChildren(QProgressBar):
        if (
            progress_bar.maximum() > 0
            and progress_bar.value() >= progress_bar.maximum()
        ):
            return True

    # Check for status labels
    from PyQt6.QtWidgets import QLabel

    for label in tab.findChildren(QLabel):
        label_text = label.text().lower()
        if any(
            word in label_text for word in ["complete", "finished", "done", "success"]
        ):
            return True

    # Check for worker thread state if accessible
    if hasattr(tab, "worker") and tab.worker:
        if not tab.worker.isRunning():
            return True

    return False


def is_processing_error(tab: QWidget) -> bool:
    """Check if processing encountered an error."""
    from PyQt6.QtWidgets import QLabel

    for label in tab.findChildren(QLabel):
        label_text = label.text().lower()
        if any(word in label_text for word in ["error", "failed", "failure"]):
            return True
    return False


def check_ollama_running() -> bool:
    """Check if Ollama service is running and accessible."""
    try:
        import requests

        resp = requests.get("http://localhost:11434/api/version", timeout=2)
        return resp.status_code == 200
    except Exception:
        return False


def check_whisper_cpp_installed() -> bool:
    """Check if whisper.cpp is installed and accessible."""
    import shutil

    return (
        shutil.which("whisper-cli") is not None or shutil.which("whisper") is not None
    )
