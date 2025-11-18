"""
Device Authentication - Simple Auto-Auth (Happy-style)

Automatically generates and stores device credentials for seamless
GetReceipts.org integration without user intervention.

Similar to Happy's approach:
- Auto-generate UUID device_id + secret key on first use
- Store in QSettings (platform-native, secure)
- Silent authentication, user can disable in Settings
"""

import secrets
import uuid

from PyQt6.QtCore import QSettings

from ..logger import get_logger

logger = get_logger(__name__)


class DeviceAuth:
    """Manages automatic device authentication credentials."""

    def __init__(self) -> None:
        """Initialize with QSettings storage."""
        self.settings = QSettings("SkipThePodcast", "SkipThePodcast")

    def get_credentials(self) -> dict[str, str]:
        """
        Get or auto-generate device credentials.

        Returns device_id and device_key. On first call, automatically
        generates new credentials silently (no user interaction).

        Returns:
            dict with 'device_id' and 'device_key'
        """
        device_id = self.settings.value("device/id")
        device_key = self.settings.value("device/key")

        if not device_id or not device_key:
            # Auto-generate on first use (silent, like Happy)
            device_id = str(uuid.uuid4())
            device_key = secrets.token_urlsafe(32)  # Cryptographically secure

            self.settings.setValue("device/id", device_id)
            self.settings.setValue("device/key", device_key)
            self.settings.sync()

            logger.info(f"Generated new device credentials: {device_id[:8]}...")

        return {"device_id": device_id, "device_key": device_key}

    def is_enabled(self) -> bool:
        """
        Check if auto-upload is enabled.

        Returns:
            True if auto-upload is enabled (default), False otherwise
        """
        # Default to True (enabled by default, like Happy)
        return self.settings.value("device/auto_upload", True, type=bool)

    def set_enabled(self, enabled: bool) -> None:
        """
        Enable or disable auto-upload to GetReceipts.

        Args:
            enabled: True to enable auto-upload, False to disable
        """
        self.settings.setValue("device/auto_upload", enabled)
        self.settings.sync()
        logger.info(f"Auto-upload {'enabled' if enabled else 'disabled'}")

    def reset_credentials(self) -> dict[str, str]:
        """
        Reset device credentials (generate new ones).

        Useful if credentials are compromised or user wants a fresh start.

        Returns:
            dict with new 'device_id' and 'device_key'
        """
        device_id = str(uuid.uuid4())
        device_key = secrets.token_urlsafe(32)

        self.settings.setValue("device/id", device_id)
        self.settings.setValue("device/key", device_key)
        self.settings.sync()

        logger.warning(f"Reset device credentials: {device_id[:8]}...")
        return {"device_id": device_id, "device_key": device_key}


# Global instance (singleton pattern)
_device_auth: DeviceAuth | None = None


def get_device_auth() -> DeviceAuth:
    """Get the global DeviceAuth instance."""
    global _device_auth
    if _device_auth is None:
        _device_auth = DeviceAuth()
    return _device_auth
