"""
GUI Settings Manager

Manages GUI-specific settings and integrates with the session manager
for persistent storage of user preferences.

Settings Hierarchy:
1. settings.yaml (source of truth for defaults)
2. Session state (overrides for "last used" preferences)
"""

from pathlib import Path
from typing import Any

from ...config import get_settings
from ...logger import get_logger
from .session_manager import get_session_manager, save_session

logger = get_logger(__name__)


class GUISettingsManager:
    """Manages GUI-specific settings with session persistence."""

    def __init__(self) -> None:
        """Initialize GUI settings manager."""
        self.session_manager = get_session_manager()
        # Load system settings as source of truth for defaults
        try:
            self.system_settings = get_settings()
        except Exception as e:
            logger.warning(f"Could not load system settings: {e}")
            self.system_settings = None

    def get_output_directory(self, tab_name: str, default: str | None = None) -> str:
        """
        Get the saved output directory for a tab.

        Priority:
        1. Tab-specific session state
        2. Global "last used" session state
        3. settings.yaml paths
        4. Provided default parameter
        """
        # Try tab-specific directory first
        saved_dir = self.session_manager.get_tab_setting(
            tab_name, "output_directory", None
        )

        # Fallback to global last used output directory
        if not saved_dir:
            saved_dir = self.session_manager.get_value("last_output_directory", None)
        if saved_dir:
            # Return the saved directory if it exists
            path = Path(saved_dir)
            if path.exists() or path.parent.exists():
                return str(path)

        # Fall back to settings.yaml paths
        if not saved_dir and self.system_settings is not None:
            if hasattr(self.system_settings, "paths"):
                saved_dir = str(self.system_settings.paths.output_dir)
                # Expand ~ and check if path exists or is creatable
                expanded = Path(saved_dir).expanduser()
                if expanded.exists() or expanded.parent.exists():
                    return str(expanded)

        # Return default (which should be empty string to require selection)
        return default or ""

    def set_output_directory(self, tab_name: str, directory: str | Path) -> None:
        """Save the output directory for a tab."""
        self.session_manager.set_tab_setting(
            tab_name, "output_directory", str(directory)
        )
        # Also update global last used directory for cross-tab defaulting
        self.session_manager.set_value("last_output_directory", str(directory))

    def get_checkbox_state(
        self, tab_name: str, checkbox_name: str, default: bool = False
    ) -> bool:
        """
        Get the saved state of a checkbox.

        Priority:
        1. Session state (last used value)
        2. settings.yaml (system default)
        3. Provided default parameter
        """
        # Check session state first
        saved_value = self.session_manager.get_tab_setting(
            tab_name, checkbox_name, None
        )
        if saved_value is not None:
            return saved_value

        # Fall back to settings.yaml
        if self.system_settings is not None:
            # Support both "Transcription", "Local Transcription", and "Audio Transcription" tab names
            if tab_name in ("Transcription", "Local Transcription", "Audio Transcription"):
                if checkbox_name == "diarization" or checkbox_name == "enable_diarization":
                    return self.system_settings.transcription.diarization
                elif checkbox_name == "use_gpu":
                    return self.system_settings.transcription.use_gpu
            
            # Process tab checkboxes
            elif tab_name == "Process":
                if checkbox_name == "transcribe":
                    return self.system_settings.processing.default_transcribe
                elif checkbox_name == "summarize":
                    return self.system_settings.processing.default_summarize
            
            # Monitor tab checkboxes
            elif tab_name == "Monitor":
                if checkbox_name == "recursive":
                    return self.system_settings.file_watcher.default_recursive
                elif checkbox_name == "auto_process":
                    return self.system_settings.file_watcher.default_auto_process
                elif checkbox_name == "system2_pipeline":
                    return self.system_settings.file_watcher.default_system2_pipeline

        return default

    def set_checkbox_state(
        self, tab_name: str, checkbox_name: str, state: bool
    ) -> None:
        """Save the state of a checkbox."""
        self.session_manager.set_tab_setting(tab_name, checkbox_name, state)

    def get_combo_selection(
        self, tab_name: str, combo_name: str, default: str = ""
    ) -> str:
        """
        Get the saved selection of a combo box.

        Priority:
        1. Session state (last used value)
        2. settings.yaml (system default)
        3. Provided default parameter
        """
        # First check session state
        saved_value = self.session_manager.get_tab_setting(tab_name, combo_name, None)
        if saved_value is not None:
            return saved_value

        # Fall back to settings.yaml for defaults
        if self.system_settings is not None:
            # Transcription-specific settings (check first to avoid ambiguity)
            # Support both "Transcription", "Local Transcription", and "Audio Transcription" tab names
            if tab_name in ("Transcription", "Local Transcription", "Audio Transcription"):
                if combo_name == "model":
                    return self.system_settings.transcription.whisper_model
                elif combo_name == "device":
                    # Use the device field directly (auto, cpu, cuda, mps)
                    return self.system_settings.transcription.device
                elif combo_name == "language":
                    return "en"  # Default to English

            # Summarization tab - LLM Provider/Model settings
            elif tab_name == "Summarization":
                if combo_name == "provider":
                    return self.system_settings.llm.provider
                elif combo_name == "model":
                    if hasattr(self.system_settings.llm, "local_model"):
                        return self.system_settings.llm.local_model
                    return self.system_settings.llm.model
                # Advanced per-stage provider/model settings
                elif combo_name.endswith("_provider"):
                    return self.system_settings.llm.provider
                elif combo_name.endswith("_model"):
                    if hasattr(self.system_settings.llm, "local_model"):
                        return self.system_settings.llm.local_model
                    return self.system_settings.llm.model

            # Generic LLM Provider/Model settings (for other tabs)
            elif combo_name == "provider":
                return self.system_settings.llm.provider
            elif combo_name == "model":
                # Return local_model if available, otherwise cloud model
                if hasattr(self.system_settings.llm, "local_model"):
                    return self.system_settings.llm.local_model
                return self.system_settings.llm.model

            # HCE-specific provider/model settings (miner, evaluator, judge, etc.)
            elif combo_name.endswith("_provider"):
                return self.system_settings.llm.provider
            elif combo_name.endswith("_model"):
                if hasattr(self.system_settings.llm, "local_model"):
                    return self.system_settings.llm.local_model
                return self.system_settings.llm.model

        # Final fallback to provided default
        return default

    def set_combo_selection(
        self, tab_name: str, combo_name: str, selection: str
    ) -> None:
        """Save the selection of a combo box."""
        self.session_manager.set_tab_setting(tab_name, combo_name, selection)

    def get_spinbox_value(
        self, tab_name: str, spinbox_name: str, default: int = 0
    ) -> int:
        """
        Get the saved value of a spinbox.

        Priority:
        1. Session state (last used value)
        2. settings.yaml (system default)
        3. Provided default parameter
        """
        saved_value = self.session_manager.get_tab_setting(tab_name, spinbox_name, None)
        if saved_value is not None:
            return saved_value

        # Fall back to settings.yaml
        if self.system_settings is not None:
            # Thread management settings
            if spinbox_name == "max_concurrent_files":
                if hasattr(self.system_settings, "thread_management"):
                    return self.system_settings.thread_management.max_concurrent_files
            # Processing settings
            elif spinbox_name == "concurrent_jobs":
                if hasattr(self.system_settings, "processing"):
                    return self.system_settings.processing.concurrent_jobs
            elif spinbox_name == "batch_size":
                if hasattr(self.system_settings, "processing"):
                    return self.system_settings.processing.batch_size
            # LLM settings
            elif spinbox_name == "max_tokens":
                return self.system_settings.llm.max_tokens
            # Monitor tab debounce delay
            elif tab_name == "Monitor" and spinbox_name == "debounce_delay":
                return self.system_settings.file_watcher.default_debounce_delay

        return default

    def set_spinbox_value(self, tab_name: str, spinbox_name: str, value: int) -> None:
        """Save the value of a spinbox."""
        self.session_manager.set_tab_setting(tab_name, spinbox_name, value)

    def get_line_edit_text(
        self, tab_name: str, line_edit_name: str, default: str = ""
    ) -> str:
        """
        Get the saved text of a line edit.

        Priority:
        1. Session state (last used value)
        2. settings.yaml (system default)
        3. Provided default parameter
        """
        saved_value = self.session_manager.get_tab_setting(
            tab_name, line_edit_name, None
        )
        if saved_value is not None:
            return saved_value

        # Fall back to settings.yaml
        if self.system_settings is not None:
            # Cookie file path for YouTube authentication
            if line_edit_name == "cookie_file_path":
                if hasattr(self.system_settings, "youtube_processing"):
                    cookie_path = (
                        self.system_settings.youtube_processing.cookie_file_path
                    )
                    return cookie_path if cookie_path else ""
            
            # Monitor tab file patterns
            elif tab_name == "Monitor" and line_edit_name == "file_patterns":
                return self.system_settings.file_watcher.default_file_patterns

        return default

    def set_line_edit_text(self, tab_name: str, line_edit_name: str, text: str) -> None:
        """Save the text of a line edit."""
        self.session_manager.set_tab_setting(tab_name, line_edit_name, text)

    def get_tab_settings(self, tab_name: str) -> dict[str, Any]:
        """Get all settings for a tab."""
        return self.session_manager.get_tab_settings(tab_name)

    def set_tab_settings(self, tab_name: str, settings: dict[str, Any]) -> None:
        """Set all settings for a tab."""
        self.session_manager.set_tab_settings(tab_name, settings)

    def get_window_geometry(self) -> dict[str, int] | None:
        """Get saved window geometry."""
        return self.session_manager.get_window_geometry()

    def set_window_geometry(self, x: int, y: int, width: int, height: int) -> None:
        """Save window geometry."""
        self.session_manager.set_window_geometry(x, y, width, height)

    def get_recent_files(self, tab_name: str, max_files: int = 10) -> list:
        """Get recently used files for a tab."""
        recent = self.session_manager.get_tab_setting(tab_name, "recent_files", [])
        return recent[:max_files]  # Limit to max_files

    def add_recent_file(
        self, tab_name: str, file_path: str | Path, max_files: int = 10
    ) -> None:
        """Add a file to the recent files list."""
        recent = self.get_recent_files(tab_name, max_files)
        file_str = str(file_path)

        # Remove if already exists
        if file_str in recent:
            recent.remove(file_str)

        # Add to beginning
        recent.insert(0, file_str)

        # Limit size
        recent = recent[:max_files]

        self.session_manager.set_tab_setting(tab_name, "recent_files", recent)

    def save(self) -> None:
        """Save all settings to persistent storage."""
        save_session()
        logger.debug("GUI settings saved")

    def clear_tab_settings(self, tab_name: str) -> None:
        """Clear all settings for a specific tab."""
        self.session_manager.set_tab_settings(tab_name, {})
        logger.info(f"Cleared settings for tab: {tab_name}")

    def clear_all_settings(self) -> None:
        """Clear all GUI settings."""
        self.session_manager.clear()
        logger.info("Cleared all GUI settings")

    def get_list_setting(
        self, tab_name: str, key: str, default: list[str] | None = None
    ) -> list[str]:
        """Get a list setting value."""
        if default is None:
            default = []
        return self.session_manager.get_tab_setting(tab_name, key, default)

    def set_list_setting(self, tab_name: str, key: str, value: list[str]) -> None:
        """Set a list setting value."""
        self.session_manager.set_tab_setting(tab_name, key, value)

    def get_value(self, tab_name: str, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        return self.session_manager.get_tab_setting(tab_name, key, default)

    def set_value(self, tab_name: str, key: str, value: Any) -> None:
        """Set a setting value."""
        self.session_manager.set_tab_setting(tab_name, key, value)


# Global GUI settings manager instance
_gui_settings_manager: GUISettingsManager | None = None


def get_gui_settings_manager() -> GUISettingsManager:
    """Get the global GUI settings manager instance."""
    global _gui_settings_manager
    if _gui_settings_manager is None:
        _gui_settings_manager = GUISettingsManager()
    return _gui_settings_manager
