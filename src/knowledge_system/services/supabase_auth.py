"""
Supabase Authentication Service

Provides login, logout, and session management for end users so uploads
are performed as authenticated users (not anon).
"""

from __future__ import annotations

import webbrowser

from ..config import get_settings
from ..logger import get_logger
from ..utils.optional_deps import add_vendor_to_sys_path, ensure_module
from .oauth_callback_server import start_oauth_callback_server

logger = get_logger(__name__)


class SupabaseAuthService:
    """Lightweight wrapper around supabase-py auth for desktop GUI use."""

    def __init__(
        self, supabase_url: str | None = None, supabase_key: str | None = None
    ) -> None:
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

        url = url or getattr(settings.cloud, "supabase_url", None)
        key = key or getattr(settings.cloud, "supabase_key", None)

        self.supabase_url: str | None = url
        self.supabase_key: str | None = key
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

    def get_user_email(self) -> str | None:
        if not self.client:
            return None
        try:
            session = self.client.auth.get_session()
            return getattr(getattr(session, "user", None), "email", None)
        except Exception:
            return None

    def get_user_id(self) -> str | None:
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
        """Direct email/password sign-up (legacy method)."""
        if not self.client:
            return False, "Auth client not available"
        try:
            self.client.auth.sign_up({"email": email, "password": password})
            return (
                True,
                "Sign-up initiated. Check your email if confirmations are enabled.",
            )
        except Exception as e:
            logger.error(f"Sign-up failed: {e}")
            return False, str(e)

    def sign_up_with_oauth(self, timeout: float = 300.0) -> tuple[bool, str]:
        """
        Sign up using GetReceipts OAuth flow.

        Args:
            timeout: Maximum time to wait for OAuth callback (seconds)

        Returns:
            Tuple of (success, message)
        """
        if not self.client:
            return False, "Auth client not available"

        try:
            logger.info("Starting GetReceipts OAuth sign-up flow")

            # Start local callback server
            logger.info("Starting OAuth callback server on localhost:8080")

            # Construct OAuth URL with callback (updated to match current implementation)
            oauth_url = "https://www.skipthepodcast.com/auth/signin?redirect_to=knowledge_chipper&return_url=http://localhost:8080/auth/callback"

            # Open browser to OAuth URL
            logger.info(f"Opening browser to: {oauth_url}")
            webbrowser.open(oauth_url)

            # Wait for OAuth callback
            logger.info(f"Waiting for OAuth callback (timeout: {timeout}s)")
            tokens = start_oauth_callback_server(timeout)

            if not tokens:
                return False, "OAuth authentication failed or timed out"

            # Set up Supabase session with received tokens
            success, message = self.set_session_from_tokens(tokens)
            if success:
                logger.info("OAuth sign-up completed successfully")
                return True, "Successfully signed in via GetReceipts"
            else:
                logger.error(f"Failed to set session: {message}")
                return False, f"Failed to establish session: {message}"

        except Exception as e:
            logger.error(f"OAuth sign-up failed: {e}")
            return False, f"OAuth authentication error: {str(e)}"

    def sign_in(self, email: str, password: str) -> tuple[bool, str]:
        if not self.client:
            return False, "Auth client not available"
        try:
            self.client.auth.sign_in_with_password(
                {"email": email, "password": password}
            )
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

    def set_session_from_tokens(self, tokens: dict[str, str]) -> tuple[bool, str]:
        """
        Set Supabase session using OAuth tokens received from GetReceipts.

        Args:
            tokens: Dictionary containing access_token, refresh_token, and user_id

        Returns:
            Tuple of (success, message)
        """
        if not self.client:
            return False, "Auth client not available"

        try:
            access_token = tokens.get("access_token")

            if not access_token:
                return False, "Missing access token"

            # Set session in Supabase client (SkipThePodcast format - no refresh token)
            self.client.auth.set_session(access_token, None)

            # Verify session is working
            session = self.client.auth.get_session()
            if session and session.user:
                logger.info(f"Session established for user: {session.user.email}")
                return True, "Session established successfully"
            else:
                return False, "Failed to verify session"

        except Exception as e:
            logger.error(f"Failed to set session from tokens: {e}")
            return False, f"Session setup error: {str(e)}"

    def refresh_session(self) -> tuple[bool, str]:
        """
        Refresh the current session.

        Returns:
            Tuple of (success, message)
        """
        if not self.client:
            return False, "Auth client not available"

        try:
            session = self.client.auth.refresh_session()
            if session and session.user:
                logger.info("Session refreshed successfully")
                return True, "Session refreshed"
            else:
                return False, "Failed to refresh session"

        except Exception as e:
            logger.error(f"Session refresh failed: {e}")
            return False, f"Refresh error: {str(e)}"
