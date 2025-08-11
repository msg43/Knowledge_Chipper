"""
Session management for GUI settings persistence
Session management for GUI settings persistence.

Handles saving and loading user preferences across application sessions.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ...logger import get_logger

logger = get_logger(__name__)

# Session file for persisting GUI state
SESSION_FILE = Path.home() / ".knowledge_system" / "gui_session.json"


class SessionManager:
    """ Manages GUI session state persistence."""

    def __init__(self) -> None:
        """ Initialize session manager."""
        self._session_data: dict[str, Any] = {}
        self._load_session()

    def _load_session(self) -> None:
        """ Load session data from file."""
        try:
            if SESSION_FILE.exists():
                with open(SESSION_FILE, encoding="utf-8") as f:
                    self._session_data = json.load(f)
                logger.debug(f"Session data loaded from {SESSION_FILE}")
            else:
                self._session_data = {}
                logger.debug(
                    "No existing session file found, starting with empty session"
                )
        except Exception as e:
            logger.error(f"Failed to load session data: {e}")
            self._session_data = {}

    def _save_session(self) -> None:
        """ Save session data to file."""
        try:
            # Create session directory if it doesn't exist
            SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)

            # Add timestamp
            self._session_data["last_saved"] = datetime.now().isoformat()

            with open(SESSION_FILE, "w", encoding="utf-8") as f:
                json.dump(self._session_data, f, indent=2, ensure_ascii=False)
            logger.debug(f"Session data saved to {SESSION_FILE}")
        except Exception as e:
            logger.error(f"Failed to save session data: {e}")

    def get_value(self, key: str, default: Any = None) -> Any:
        """ Get a value from session data."""
        return self._session_data.get(key, default)

    def set_value(self, key: str, value: Any) -> None:
        """ Set a value in session data."""
        self._session_data[key] = value

    def get_window_geometry(self) -> dict[str, int] | None:
        """ Get saved window geometry."""
        return self._session_data.get("window_geometry")

    def set_window_geometry(self, x: int, y: int, width: int, height: int) -> None:
        """ Save window geometry."""
        self._session_data["window_geometry"] = {
            "x": x,
            "y": y,
            "width": width,
            "height": height,
        }

    def get_tab_settings(self, tab_name: str) -> dict[str, Any]:
        """ Get settings for a specific tab."""
        return self._session_data.get("tab_settings", {}).get(tab_name, {})

    def set_tab_settings(self, tab_name: str, settings: dict[str, Any]) -> None:
        """ Save settings for a specific tab."""
        if "tab_settings" not in self._session_data:
            self._session_data["tab_settings"] = {}
        self._session_data["tab_settings"][tab_name] = settings

    def get_tab_setting(
        self, tab_name: str, setting_name: str, default: Any = None
    ) -> Any:
        """ Get a specific setting from a tab."""
        tab_settings = self.get_tab_settings(tab_name)
        return tab_settings.get(setting_name, default)

    def set_tab_setting(self, tab_name: str, setting_name: str, value: Any) -> None:
        """ Set a specific setting for a tab."""
        if "tab_settings" not in self._session_data:
            self._session_data["tab_settings"] = {}
        if tab_name not in self._session_data["tab_settings"]:
            self._session_data["tab_settings"][tab_name] = {}
        self._session_data["tab_settings"][tab_name][setting_name] = value

    def save(self) -> None:
        """ Save session data to file."""
        self._save_session()

    def clear(self) -> None:
        """ Clear all session data."""
        self._session_data = {}
        try:
            if SESSION_FILE.exists():
                SESSION_FILE.unlink()
            logger.info("Session data cleared")
        except Exception as e:
            logger.error(f"Failed to clear session data: {e}")


# Global session manager instance
_session_manager: SessionManager | None = None


def get_session_manager() -> SessionManager:
    """ Get the global session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


def save_session() -> None:
    """ Save the current session data."""
    get_session_manager().save()


def get_session_value(key: str, default: Any = None) -> Any:
    """ Convenience function to get a session value."""
    return get_session_manager().get_value(key, default)


def set_session_value(key: str, value: Any) -> None:
    """ Convenience function to set a session value."""
    get_session_manager().set_value(key, value)


def get_tab_setting(tab_name: str, setting_name: str, default: Any = None) -> Any:
    """ Convenience function to get a tab setting."""
    return get_session_manager().get_tab_setting(tab_name, setting_name, default)


def set_tab_setting(tab_name: str, setting_name: str, value: Any) -> None:
    """ Convenience function to set a tab setting."""
    get_session_manager().set_tab_setting(tab_name, setting_name, value)
