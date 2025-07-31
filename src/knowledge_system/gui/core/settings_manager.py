"""
GUI Settings Manager

Manages GUI-specific settings and integrates with the session manager
for persistent storage of user preferences.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ...logger import get_logger
from .session_manager import get_session_manager, save_session

logger = get_logger(__name__)


class GUISettingsManager:
    """Manages GUI-specific settings with session persistence."""

    def __init__(self) -> None:
        """Initialize GUI settings manager."""
        self.session_manager = get_session_manager()

    def get_output_directory(self, tab_name: str, default: str | None = None) -> str:
        """Get the saved output directory for a tab."""
        saved_dir = self.session_manager.get_tab_setting(
            tab_name, "output_directory", default
        )
        if saved_dir:
            # Return the saved directory if it exists
            path = Path(saved_dir)
            if path.exists() or path.parent.exists():
                return str(path)

        # Return default (which should be empty string to require selection)
        return default or ""

    def set_output_directory(self, tab_name: str, directory: str | Path) -> None:
        """Save the output directory for a tab."""
        self.session_manager.set_tab_setting(
            tab_name, "output_directory", str(directory)
        )

    def get_checkbox_state(
        self, tab_name: str, checkbox_name: str, default: bool = False
    ) -> bool:
        """Get the saved state of a checkbox."""
        return self.session_manager.get_tab_setting(tab_name, checkbox_name, default)

    def set_checkbox_state(
        self, tab_name: str, checkbox_name: str, state: bool
    ) -> None:
        """Save the state of a checkbox."""
        self.session_manager.set_tab_setting(tab_name, checkbox_name, state)

    def get_combo_selection(
        self, tab_name: str, combo_name: str, default: str = ""
    ) -> str:
        """Get the saved selection of a combo box."""
        return self.session_manager.get_tab_setting(tab_name, combo_name, default)

    def set_combo_selection(
        self, tab_name: str, combo_name: str, selection: str
    ) -> None:
        """Save the selection of a combo box."""
        self.session_manager.set_tab_setting(tab_name, combo_name, selection)

    def get_spinbox_value(
        self, tab_name: str, spinbox_name: str, default: int = 0
    ) -> int:
        """Get the saved value of a spinbox."""
        return self.session_manager.get_tab_setting(tab_name, spinbox_name, default)

    def set_spinbox_value(self, tab_name: str, spinbox_name: str, value: int) -> None:
        """Save the value of a spinbox."""
        self.session_manager.set_tab_setting(tab_name, spinbox_name, value)

    def get_line_edit_text(
        self, tab_name: str, line_edit_name: str, default: str = ""
    ) -> str:
        """Get the saved text of a line edit."""
        return self.session_manager.get_tab_setting(tab_name, line_edit_name, default)

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
        self, tab_name: str, key: str, default: list[str] = None
    ) -> list[str]:
        """Get a list setting value."""
        if default is None:
            default = []
        return self.session_manager.get_tab_setting(tab_name, key, default)

    def set_list_setting(self, tab_name: str, key: str, value: list[str]) -> None:
        """Set a list setting value."""
        self.session_manager.set_tab_setting(tab_name, key, value)


# Global GUI settings manager instance
_gui_settings_manager: GUISettingsManager | None = None


def get_gui_settings_manager() -> GUISettingsManager:
    """Get the global GUI settings manager instance."""
    global _gui_settings_manager
    if _gui_settings_manager is None:
        _gui_settings_manager = GUISettingsManager()
    return _gui_settings_manager
