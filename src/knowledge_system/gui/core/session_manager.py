"""
Session Manager - QSettings-based Implementation

This module provides session management using Qt's QSettings for persistent storage.
Replaces the deprecated JSON-based session management.
"""

from typing import Any

from PyQt6.QtCore import QSettings

from ...logger import get_logger

logger = get_logger(__name__)


class SessionManager:
    """Manages GUI session state using QSettings."""

    def __init__(self) -> None:
        """Initialize session manager with QSettings."""
        self.settings = QSettings("SkipThePodcast", "SkipThePodcast")

    def get_value(self, key: str, default: Any = None) -> Any:
        """Get a value from session state."""
        return self.settings.value(key, default)

    def set_value(self, key: str, value: Any) -> None:
        """Set a value in session state."""
        self.settings.setValue(key, value)
        self.settings.sync()

    def get_tab_setting(self, tab_name: str, setting_name: str, default: Any = None) -> Any:
        """Get a tab-specific setting."""
        key = f"tabs/{tab_name}/{setting_name}"
        return self.settings.value(key, default)

    def set_tab_setting(self, tab_name: str, setting_name: str, value: Any) -> None:
        """Set a tab-specific setting."""
        key = f"tabs/{tab_name}/{setting_name}"
        self.settings.setValue(key, value)
        self.settings.sync()


# Global session manager instance
_session_manager: SessionManager | None = None


def get_session_manager() -> SessionManager:
    """Get the global session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


def save_session() -> None:
    """Explicitly save session state (sync QSettings)."""
    if _session_manager is not None:
        _session_manager.settings.sync()
