"""
Bright Data session management and proxy configuration utilities.

Provides session management for Bright Data residential proxies with sticky sessions,
cost tracking, and integration with the SQLite database for analytics.
"""

import os
import uuid
from urllib.parse import quote

from ..config import get_settings
from ..database import DatabaseService
from ..logger import get_logger

logger = get_logger(__name__)


class BrightDataSessionManager:
    """
    Manages Bright Data residential proxy sessions with sticky IPs per file.

    Implements the session management pattern required by Bright Data:
    - One unique session ID per file for sticky IP
    - Session embedded in proxy username
    - Automatic session rotation between files
    - Cost tracking and database integration
    """

    def __init__(self, database_service: DatabaseService | None = None):
        """Initialize session manager with database service."""
        self.settings = get_settings()
        self.db = database_service or DatabaseService()

        # Bright Data credentials from config or environment
        self.customer_id = self._get_credential("BD_CUST", "bright_data_customer_id")
        self.zone_id = self._get_credential("BD_ZONE", "bright_data_zone_id")
        self.password = self._get_credential("BD_PASS", "bright_data_password")
        self.api_key = getattr(self.settings.api_keys, "bright_data_api_key", None)

        # Bright Data configuration
        self.proxy_endpoint = "zproxy.lum-superproxy.io:22225"
        self.session_cache = {}  # Cache active sessions per video

        logger.info("Bright Data session manager initialized")

    def _get_credential(self, env_var: str, config_attr: str) -> str | None:
        """Get credential from environment variable or config with fallback."""
        # First try environment variable
        value = os.environ.get(env_var)
        if value:
            return value

        # Then try config (if attribute exists)
        try:
            return getattr(self.settings.api_keys, config_attr, None)
        except AttributeError:
            return None

    def _validate_credentials(self) -> bool:
        """Validate that required Bright Data credentials are available."""
        missing = []

        if not self.customer_id:
            missing.append("BD_CUST (customer ID)")
        if not self.zone_id:
            missing.append("BD_ZONE (zone ID)")
        if not self.password:
            missing.append("BD_PASS (password)")

        if missing:
            logger.error(f"Missing Bright Data credentials: {', '.join(missing)}")
            return False

        return True

    def create_session_for_file(
        self, file_id: str, session_type: str = "audio_download"
    ) -> str | None:
        """
        Create a new Bright Data session for a specific file.

        Args:
            file_id: Unique identifier for the file (typically video_id)
            session_type: Type of session ('audio_download', 'metadata_scrape', 'transcript_scrape')

        Returns:
            Session ID if successful, None if failed
        """
        if not self._validate_credentials():
            return None

        try:
            # Generate unique session ID per file
            session_uuid = uuid.uuid4().hex[:8]
            session_id = f"{file_id}-{session_uuid}"

            # Store session in database for tracking
            self.db.create_bright_data_session(
                session_id=session_id,
                video_id=file_id,
                session_type=session_type,
                proxy_endpoint=self.proxy_endpoint,
                customer_id=self.customer_id,
                zone_id=self.zone_id,
            )

            # Cache session for this file
            self.session_cache[file_id] = {
                "session_id": session_id,
                "session_type": session_type,
                "created_at": uuid.uuid4().hex,
            }

            logger.info(f"Created Bright Data session {session_id} for file {file_id}")
            return session_id

        except Exception as e:
            logger.error(f"Failed to create Bright Data session for {file_id}: {e}")
            return None

    def get_proxy_url_for_file(
        self, file_id: str, session_type: str = "audio_download"
    ) -> str | None:
        """
        Get complete proxy URL for a specific file with embedded session.

        Args:
            file_id: Unique identifier for the file
            session_type: Type of session needed

        Returns:
            Complete proxy URL with embedded session ID, or None if failed
        """
        if not self._validate_credentials():
            return None

        try:
            # Get or create session for this file
            session_id = self.session_cache.get(file_id, {}).get("session_id")
            if not session_id:
                session_id = self.create_session_for_file(file_id, session_type)
                if not session_id:
                    return None

            # Build proxy username with embedded session
            # Format: lum-customer-{customer_id}-zone-{zone_id}-session-{session_id}
            username = f"lum-customer-{self.customer_id}-zone-{self.zone_id}-session-{session_id}"

            # URL encode credentials for safety
            encoded_username = quote(username)
            encoded_password = quote(self.password)

            # Build complete proxy URL
            proxy_url = (
                f"http://{encoded_username}:{encoded_password}@{self.proxy_endpoint}"
            )

            logger.debug(
                f"Generated proxy URL for file {file_id} with session {session_id}"
            )
            return proxy_url

        except Exception as e:
            logger.error(f"Failed to generate proxy URL for {file_id}: {e}")
            return None

    def get_proxy_dict_for_file(
        self, file_id: str, session_type: str = "audio_download"
    ) -> dict[str, str] | None:
        """
        Get proxy dictionary for requests/urllib usage.

        Args:
            file_id: Unique identifier for the file
            session_type: Type of session needed

        Returns:
            Dictionary with 'http' and 'https' proxy URLs, or None if failed
        """
        proxy_url = self.get_proxy_url_for_file(file_id, session_type)
        if not proxy_url:
            return None

        return {"http": proxy_url, "https": proxy_url}

    def update_session_usage(
        self,
        session_id: str,
        requests_count: int = 0,
        data_downloaded_bytes: int = 0,
        cost: float = 0.0,
    ) -> bool:
        """
        Update session usage and cost tracking.

        Args:
            session_id: Bright Data session ID
            requests_count: Number of requests made
            data_downloaded_bytes: Bytes downloaded
            cost: Cost incurred for this usage

        Returns:
            True if successful, False otherwise
        """
        try:
            return self.db.update_bright_data_session_cost(
                session_id=session_id,
                requests_count=requests_count,
                data_downloaded_bytes=data_downloaded_bytes,
                cost=cost,
            )
        except Exception as e:
            logger.error(f"Failed to update session usage for {session_id}: {e}")
            return False

    def end_session_for_file(self, file_id: str) -> bool:
        """
        End session for a specific file and clean up.

        Args:
            file_id: Unique identifier for the file

        Returns:
            True if successful, False otherwise
        """
        try:
            if file_id in self.session_cache:
                session_info = self.session_cache[file_id]
                session_id = session_info["session_id"]

                # Update session end time in database
                # Note: This would need a database method to update ended_at
                # For now, we'll just remove from cache
                del self.session_cache[file_id]

                logger.info(f"Ended session {session_id} for file {file_id}")
                return True
            return False

        except Exception as e:
            logger.error(f"Failed to end session for {file_id}: {e}")
            return False

    def get_session_stats(self) -> dict[str, any]:
        """Get comprehensive session statistics from database."""
        try:
            stats = self.db.get_cost_breakdown()
            return stats.get("bright_data_costs", [])
        except Exception as e:
            logger.error(f"Failed to get session stats: {e}")
            return {}

    def cleanup_old_sessions(self, days_old: int = 7) -> int:
        """Clean up old session records from database."""
        try:
            return self.db.cleanup_old_sessions(days_old)
        except Exception as e:
            logger.error(f"Failed to cleanup old sessions: {e}")
            return 0


class BrightDataProxyConfig:
    """
    Configuration helper for Bright Data proxy settings.

    Provides utilities for managing proxy configurations, connection limits,
    and session parameters for different use cases.
    """

    # Recommended connection limits per file
    AUDIO_DOWNLOAD_CONNECTIONS = 4  # 2-4 connections for audio downloads
    METADATA_SCRAPE_CONNECTIONS = 1  # Single connection for API scraping

    # Session timeout settings
    DEFAULT_TIMEOUT = 30  # seconds
    DOWNLOAD_TIMEOUT = 300  # 5 minutes for large downloads

    @classmethod
    def get_yt_dlp_args(
        cls, proxy_url: str, connection_limit: int = AUDIO_DOWNLOAD_CONNECTIONS
    ) -> dict[str, str]:
        """
        Get yt-dlp arguments for Bright Data proxy with aria2c downloader.

        Args:
            proxy_url: Complete proxy URL with embedded session
            connection_limit: Maximum connections per download

        Returns:
            Dictionary of yt-dlp arguments
        """
        return {
            "proxy": proxy_url,
            "downloader": "aria2c",
            "downloader_args": f"aria2c:-x {connection_limit} -k 2M --async-dns=false --allow-overwrite=true --all-proxy={proxy_url}",
            "socket_timeout": cls.DOWNLOAD_TIMEOUT,
            "retries": 3,
            "extractor_retries": 3,
        }

    @classmethod
    def get_requests_config(
        cls, proxy_dict: dict[str, str], timeout: int = DEFAULT_TIMEOUT
    ) -> dict[str, any]:
        """
        Get requests library configuration for Bright Data proxy.

        Args:
            proxy_dict: Proxy dictionary from session manager
            timeout: Request timeout in seconds

        Returns:
            Dictionary of requests configuration
        """
        return {
            "proxies": proxy_dict,
            "timeout": timeout,
            "verify": True,  # Keep SSL verification enabled
            "headers": {"User-Agent": "Knowledge-System/1.0 (Bright-Data-Integration)"},
        }

    @classmethod
    def estimate_cost(
        cls,
        requests_count: int = 0,
        data_gb: float = 0.0,
        cost_per_request: float = 0.001,  # $0.001 per request (example)
        cost_per_gb: float = 0.50,  # $0.50 per GB (example)
    ) -> float:
        """
        Estimate cost for Bright Data usage.

        Args:
            requests_count: Number of requests
            data_gb: Data downloaded in GB
            cost_per_request: Cost per request
            cost_per_gb: Cost per GB downloaded

        Returns:
            Estimated total cost
        """
        request_cost = requests_count * cost_per_request
        data_cost = data_gb * cost_per_gb
        return request_cost + data_cost


# Convenience functions for easy usage
def get_proxy_for_video(
    video_id: str, session_type: str = "audio_download"
) -> str | None:
    """Convenience function to get proxy URL for a video."""
    manager = BrightDataSessionManager()
    return manager.get_proxy_url_for_file(video_id, session_type)


def get_proxy_dict_for_video(
    video_id: str, session_type: str = "audio_download"
) -> dict[str, str] | None:
    """Convenience function to get proxy dictionary for a video."""
    manager = BrightDataSessionManager()
    return manager.get_proxy_dict_for_file(video_id, session_type)


def track_usage(
    session_id: str, requests: int = 0, bytes_downloaded: int = 0, cost: float = 0.0
) -> bool:
    """Convenience function to track session usage."""
    manager = BrightDataSessionManager()
    return manager.update_session_usage(session_id, requests, bytes_downloaded, cost)
