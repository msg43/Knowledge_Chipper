"""
Device Authentication - Simple Auto-Auth (Happy-style)

Automatically generates and stores device credentials for seamless
GetReceipts.org integration without user intervention.

Similar to Happy's approach:
- Auto-generate UUID device_id + secret key on first use
- Store in JSON file (platform-independent, no GUI dependency)
- Silent authentication, user can disable in Settings
- Device claiming flow for linking to user accounts
"""

import json
import random
import secrets
import string
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from ..logger import get_logger

logger = get_logger(__name__)


class DeviceAuth:
    """Manages automatic device authentication credentials."""

    def __init__(self) -> None:
        """Initialize with JSON file storage (no GUI dependency)."""
        # Use platform-appropriate config directory
        if Path.home().joinpath("Library").exists():
            # macOS
            config_dir = Path.home() / "Library" / "Application Support" / "SkipThePodcast"
        else:
            # Linux/Windows fallback
            config_dir = Path.home() / ".skip_the_podcast"
        
        config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = config_dir / "device_auth.json"
        
        # Load existing settings or create empty dict
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    self.settings = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load device auth config: {e}")
                self.settings = {}
        else:
            self.settings = {}
    
    def _save(self) -> None:
        """Save settings to JSON file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save device auth config: {e}")
    
    def _get_value(self, key: str, default=None):
        """Get a value from settings."""
        return self.settings.get(key, default)
    
    def _set_value(self, key: str, value) -> None:
        """Set a value in settings and save."""
        self.settings[key] = value
        self._save()

    def get_credentials(self) -> dict[str, str]:
        """
        Get or auto-generate device credentials.

        Returns device_id and device_key. On first call, automatically
        generates new credentials silently (no user interaction).

        Returns:
            dict with 'device_id' and 'device_key'
        """
        device_id = self._get_value("device_id")
        device_key = self._get_value("device_key")

        if not device_id or not device_key:
            # Auto-generate on first use (silent, like Happy)
            device_id = str(uuid.uuid4())
            device_key = secrets.token_urlsafe(32)  # Cryptographically secure

            self._set_value("device_id", device_id)
            self._set_value("device_key", device_key)

            logger.info(f"Generated new device credentials: {device_id[:8]}...")

        return {"device_id": device_id, "device_key": device_key}

    def is_enabled(self) -> bool:
        """
        Check if auto-upload is enabled.

        Returns:
            True if auto-upload is enabled (default), False otherwise
        """
        # Default to True (enabled by default, like Happy)
        return self._get_value("auto_upload", True)

    def set_enabled(self, enabled: bool) -> None:
        """
        Enable or disable auto-upload to GetReceipts.

        Args:
            enabled: True to enable auto-upload, False to disable
        """
        self._set_value("auto_upload", enabled)
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

        self._set_value("device_id", device_id)
        self._set_value("device_key", device_key)

        logger.warning(f"Reset device credentials: {device_id[:8]}...")
        return {"device_id": device_id, "device_key": device_key}

    # =========================================================================
    # Device Claiming (Link to User Account)
    # =========================================================================

    def generate_claim_code(self) -> str:
        """
        Generate a readable 6-character claim code.

        Uses characters that avoid confusion:
        - No O/0, I/1, L confusion
        - Uppercase letters + numbers
        - Formatted as XXXX-XX for readability

        Returns:
            Claim code like "ABCD-12"
        """
        # Readable characters (avoid O/0, I/1 confusion)
        chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        code = ''.join(random.choice(chars) for _ in range(6))

        # Format as XXXX-XX for readability
        return f"{code[:4]}-{code[4:]}"

    def get_claim_code(self) -> str:
        """
        Get or generate claim code for device linking.

        The claim code is:
        - Generated once and persisted
        - Shown in Settings UI for user to enter on web
        - Used to link device to user account

        Returns:
            Claim code (e.g., "ABCD-12")
        """
        claim_code = self._get_value("claim_code")

        if not claim_code:
            claim_code = self.generate_claim_code()
            self._set_value("claim_code", claim_code)
            logger.info(f"Generated claim code: {claim_code}")

            # Register claim code with Supabase (non-blocking)
            self._register_claim_code(claim_code)

        return claim_code

    def regenerate_claim_code(self) -> str:
        """
        Generate a new claim code (e.g., if old one expired).

        Returns:
            New claim code
        """
        claim_code = self.generate_claim_code()
        self._set_value("claim_code", claim_code)
        logger.info(f"Regenerated claim code: {claim_code}")

        # Register new claim code with Supabase
        self._register_claim_code(claim_code)

        return claim_code

    def get_user_id(self) -> str | None:
        """
        Get the linked Supabase user ID.

        Returns:
            User UUID if device is linked, None otherwise
        """
        return self._get_value("user_id")

    def set_user_id(self, user_id: str) -> None:
        """
        Set the linked Supabase user ID.

        This is called when the device is successfully claimed
        via the web dashboard.

        Args:
            user_id: Supabase user UUID
        """
        self._set_value("user_id", user_id)
        logger.info(f"✅ Device linked to user: {user_id[:8]}...")

    def is_linked(self) -> bool:
        """
        Check if device is linked to a user account.

        Returns:
            True if linked, False otherwise
        """
        return self.get_user_id() is not None

    def unlink_device(self) -> None:
        """
        Unlink device from user account.

        Clears the stored user_id. Device can be re-linked
        with a new claim code.
        """
        if "user_id" in self.settings:
            del self.settings["user_id"]
            self._save()
        logger.warning("Device unlinked from user account")

    def _register_claim_code(self, claim_code: str) -> None:
        """
        Register claim code with Supabase (non-blocking).

        Creates a device_claims record so the web can look up the device
        when the user enters the claim code.

        Args:
            claim_code: The claim code to register (e.g., "ABCD-12")
        """
        try:
            import requests
            from knowledge_chipper_oauth.getreceipts_config import get_config

            config = get_config()
            credentials = self.get_credentials()
            device_id = credentials["device_id"]

            # Calculate expiration (24 hours from now)
            expires_at = (datetime.now() + timedelta(hours=24)).isoformat()

            # Prepare data for device_claims table
            claim_data = {
                "claim_code": claim_code,
                "device_id": device_id,
                "expires_at": expires_at,
            }

            # Insert into device_claims table via Supabase REST API
            headers = {
                "apikey": config["supabase_anon_key"],
                "Authorization": f"Bearer {config['supabase_anon_key']}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",  # Don't need response data
            }

            url = f"{config['supabase_url']}/rest/v1/device_claims"

            response = requests.post(url, json=claim_data, headers=headers, timeout=10)

            if response.status_code in (201, 200):
                logger.info(f"Registered claim code {claim_code} with Supabase")
            else:
                logger.warning(
                    f"Failed to register claim code: {response.status_code} - {response.text}"
                )

        except Exception as e:
            # Non-fatal - claim code still works locally, just won't be in database
            logger.warning(f"Could not register claim code with Supabase: {e}")

    def check_if_claimed(self) -> dict[str, any]:
        """
        Check if device has been claimed by querying Supabase.

        Returns:
            dict with 'linked' (bool) and optional 'user_id' (str)
        """
        try:
            import requests
            from knowledge_chipper_oauth.getreceipts_config import get_config

            config = get_config()
            credentials = self.get_credentials()
            device_id = credentials["device_id"]

            # Query the GET endpoint at /api/devices/claim
            url = f"{config['base_url']}/api/devices/claim"
            params = {"device_id": device_id}

            # Use shorter timeout to avoid blocking UI (2 seconds instead of 10)
            # This prevents the spinning beachball when the server is not responding
            response = requests.get(url, params=params, timeout=2)

            if response.status_code == 200:
                data = response.json()
                if data.get("linked"):
                    logger.info(f"Device is linked to user: {data.get('user_id', 'unknown')[:8]}...")
                    return {
                        "linked": True,
                        "user_id": data.get("user_id"),
                        "device_name": data.get("device_name"),
                    }

            return {"linked": False}

        except requests.exceptions.Timeout:
            # Timeout is expected if server is not running - don't log as warning
            logger.debug("Device claim check timed out (server may not be running)")
            return {"linked": False}
        except requests.exceptions.ConnectionError:
            # Connection error is expected if server is not running - don't log as warning
            logger.debug("Device claim check failed (server may not be running)")
            return {"linked": False}
        except Exception as e:
            logger.warning(f"Could not check device claim status: {e}")
            return {"linked": False}


# Global instance (singleton pattern)
_device_auth: DeviceAuth | None = None


def get_device_auth() -> DeviceAuth:
    """Get the global DeviceAuth instance."""
    global _device_auth
    if _device_auth is None:
        _device_auth = DeviceAuth()
    return _device_auth
