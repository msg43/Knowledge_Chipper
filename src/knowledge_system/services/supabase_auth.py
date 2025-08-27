"""
Supabase Authentication Service

Provides login, logout, and session management for end users so uploads
are performed as authenticated users (not anon).
"""

from __future__ import annotations

from typing import Optional

from ..config import get_settings
from ..logger import get_logger
from ..utils.optional_deps import ensure_module, add_vendor_to_sys_path


logger = get_logger(__name__)


class SupabaseAuthService:
    """Lightweight wrapper around supabase-py auth for desktop GUI use."""

    def __init__(self, supabase_url: Optional[str] = None, supabase_key: Optional[str] = None) -> None:
        settings = get_settings()

        url = supabase_url
        key = supabase_key

        try:
            cloud = getattr(settings, "cloud", None)
            if cloud is not None:
                url = url or getattr(cloud, "supabase_url", None)
                key = key or getattr(cloud, "supabase_key", None)
        except Exception:
            pass

        url = url or getattr(settings, "supabase_url", None)
        key = key or getattr(settings, "supabase_key", None)

        self.supabase_url: Optional[str] = url
        self.supabase_key: Optional[str] = key
        self.client = None

        if not self.supabase_url or not self.supabase_key:
            logger.info("Supabase credentials not configured for auth")
            return

        try:
            add_vendor_to_sys_path()
            supabase_mod = ensure_module("supabase", "supabase")
            create_client = getattr(supabase_mod, "create_client")
            self.client = create_client(self.supabase_url, self.supabase_key)
        except Exception as e:
            logger.warning(f"Supabase auth client unavailable: {e}")
            self.client = None

    def is_available(self) -> bool:
        return self.client is not None

    def is_authenticated(self) -> bool:
        if not self.client:
            return False
        try:
            session = self.client.auth.get_session()
            return bool(session and session.user)
        except Exception:
            return False

    def get_user_email(self) -> Optional[str]:
        if not self.client:
            return None
        try:
            session = self.client.auth.get_session()
            return getattr(getattr(session, "user", None), "email", None)
        except Exception:
            return None

    def get_user_id(self) -> Optional[str]:
        if not self.client:
            return None
        try:
            session = self.client.auth.get_session()
            return getattr(getattr(session, "user", None), "id", None)
        except Exception:
            return None

    def get_client(self):  # pragma: no cover - simple getter
        return self.client

    # Authentication APIs
    def sign_up(self, email: str, password: str) -> tuple[bool, str]:
        if not self.client:
            return False, "Auth client not available"
        try:
            self.client.auth.sign_up({"email": email, "password": password})
            return True, "Sign-up initiated. Check your email if confirmations are enabled."
        except Exception as e:
            logger.error(f"Sign-up failed: {e}")
            return False, str(e)

    def sign_in(self, email: str, password: str) -> tuple[bool, str]:
        if not self.client:
            return False, "Auth client not available"
        try:
            self.client.auth.sign_in_with_password({"email": email, "password": password})
            return True, "Signed in"
        except Exception as e:
            logger.error(f"Sign-in failed: {e}")
            return False, str(e)

    def sign_out(self) -> tuple[bool, str]:
        if not self.client:
            return False, "Auth client not available"
        try:
            self.client.auth.sign_out()
            return True, "Signed out"
        except Exception as e:
            logger.error(f"Sign-out failed: {e}")
            return False, str(e)


