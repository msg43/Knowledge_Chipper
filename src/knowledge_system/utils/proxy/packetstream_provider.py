"""
PacketStream Residential Proxy Provider

Provides rotating residential proxies with sticky sessions for YouTube data extraction.
Based on: https://github.com/packetstream/packetstream-examples
"""

import logging
import os
import random
import time
from typing import Dict, Optional, Tuple

import requests

from .base_provider import BaseProxyProvider

logger = logging.getLogger(__name__)


class PacketStreamProvider(BaseProxyProvider):
    """
    PacketStream proxy provider implementation.
    
    Manages PacketStream residential proxy connections with rotation and sticky sessions.
    """

    def __init__(self, username: Optional[str] = None, auth_key: Optional[str] = None):
        """
        Initialize PacketStream proxy provider.

        Args:
            username: PacketStream username (or from env/config)
            auth_key: PacketStream auth key (or from env/config)
        """
        # Try to get credentials from multiple sources
        self.username = username or os.getenv("PACKETSTREAM_USERNAME")
        self.auth_key = auth_key or os.getenv("PACKETSTREAM_AUTH_KEY")

        # If not found, try to load from app config
        if not self.username or not self.auth_key:
            try:
                from ...config import get_settings

                settings = get_settings()
                self.username = self.username or getattr(
                    settings.api_keys, "packetstream_username", None
                )
                self.auth_key = self.auth_key or getattr(
                    settings.api_keys, "packetstream_auth_key", None
                )
            except Exception:
                pass  # Config loading failed, use what we have

        # PacketStream proxy endpoints
        self.proxy_endpoints = [
            "proxy.packetstream.io:31112",  # HTTP proxy (working port)
            "proxy.packetstream.io:31113",  # SOCKS5 proxy
        ]

        # Session management for sticky sessions
        self.sessions: Dict[str, requests.Session] = {}
        self.current_session_id: Optional[str] = None

    # BaseProxyProvider interface implementation
    
    def get_proxy_url(self, session_id: Optional[str] = None) -> Optional[str]:
        """
        Get proxy URL string for use with yt-dlp and direct HTTP calls.
        
        Args:
            session_id: Optional session ID for sticky IP (same ID = same IP)
            
        Returns:
            Proxy URL string or None if credentials not available
        """
        if not self.is_configured():
            return None

        # Add session parameter for sticky IP per URL
        # PacketStream format: username:password_session-SESSIONID
        auth = f"{self.username}:{self.auth_key}"
        if session_id:
            auth += f"_session-{session_id}"  # Use underscore not hyphen

        # Use HTTP proxy by default (not SOCKS5)
        return f"http://{auth}@proxy.packetstream.io:31112"
    
    def get_proxy_config(self) -> Dict[str, str]:
        """
        Get proxy configuration dict for use with requests library.
        
        Returns:
            Dict with 'http' and 'https' keys, or empty dict if not configured
        """
        proxy_url = self.get_proxy_url()
        if not proxy_url:
            return {}
        
        return {"http": proxy_url, "https": proxy_url}
    
    def test_connectivity(self, timeout: int = 10) -> Tuple[bool, str]:
        """
        Test if PacketStream proxy is working.
        
        Args:
            timeout: Connection timeout in seconds
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        if not self.is_configured():
            return False, "PacketStream credentials not configured"

        proxy_config = self.get_proxy_config()
        
        try:
            # Test with a simple HTTP request
            response = requests.get(
                "http://httpbin.org/ip",
                proxies=proxy_config,
                timeout=timeout,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                },
            )

            if response.status_code == 200:
                ip_data = response.json()
                proxy_ip = ip_data.get("origin", "unknown")
                return True, f"PacketStream proxy working (IP: {proxy_ip})"
            else:
                return False, f"Proxy returned HTTP {response.status_code}"

        except requests.exceptions.ConnectTimeout:
            return False, "PacketStream proxy connection timeout"
        except requests.exceptions.ProxyError as e:
            return False, f"PacketStream proxy error: {str(e)}"
        except requests.exceptions.RequestException as e:
            return False, f"Network error: {str(e)}"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"
    
    def is_configured(self) -> bool:
        """
        Check if PacketStream credentials are configured.
        
        Returns:
            True if credentials are available, False otherwise
        """
        return bool(self.username and self.auth_key)
    
    @property
    def provider_name(self) -> str:
        """
        Get human-readable provider name.
        
        Returns:
            "PacketStream"
        """
        return "PacketStream"

    # Additional PacketStream-specific functionality
    
    def get_proxy_url_socks5(self, session_id: Optional[str] = None) -> Optional[str]:
        """
        Get SOCKS5 proxy URL (PacketStream-specific feature).
        
        Args:
            session_id: Optional session ID for sticky IP
            
        Returns:
            SOCKS5 proxy URL string or None
        """
        if not self.is_configured():
            return None

        auth = f"{self.username}:{self.auth_key}"
        if session_id:
            auth += f"_session-{session_id}"

        return f"socks5h://{auth}@proxy.packetstream.io:31113"

    def create_session(
        self, session_id: Optional[str] = None, use_socks5: bool = False
    ) -> requests.Session:
        """
        Create a new requests session with PacketStream proxy.

        Args:
            session_id: Optional session identifier for sticky sessions
            use_socks5: Whether to use SOCKS5 proxy

        Returns:
            Configured requests session
        """
        if not session_id:
            session_id = f"session_{int(time.time())}_{random.randint(1000, 9999)}"

        session = requests.Session()
        if self.is_configured():
            if use_socks5:
                proxy_url = self.get_proxy_url_socks5(session_id)
            else:
                proxy_url = self.get_proxy_url(session_id)
            if proxy_url:
                session.proxies = {"http": proxy_url, "https": proxy_url}
        # If no credentials, session will use direct connection

        # Set realistic headers to avoid detection
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )

        # Store session for reuse (sticky session)
        self.sessions[session_id] = session
        self.current_session_id = session_id

        return session

    @staticmethod
    def generate_session_id(url: str, video_id: Optional[str] = None) -> str:
        """
        Generate consistent session ID from URL or video ID.

        This ensures the same URL always gets the same session (and thus the same IP),
        while different URLs get different sessions (and different IPs).

        Args:
            url: The URL being accessed
            video_id: Optional video ID (for YouTube videos)

        Returns:
            Session identifier string
        """
        if video_id:
            # Use video ID directly for YouTube content
            return video_id
        else:
            # Hash URL for non-YouTube content (RSS feeds, other platforms)
            import hashlib

            url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
            return f"url_{url_hash}"

    def get_session(self, session_id: Optional[str] = None) -> requests.Session:
        """
        Get existing session or create new one.

        Args:
            session_id: Session identifier

        Returns:
            Configured requests session
        """
        if session_id and session_id in self.sessions:
            return self.sessions[session_id]

        return self.create_session(session_id)

    def rotate_session(self, use_socks5: Optional[bool] = None) -> requests.Session:
        """
        Create a new session with a different IP (rotation).

        Args:
            use_socks5: Whether to use SOCKS5 proxy

        Returns:
            New configured requests session
        """
        # Close current session if exists
        if self.current_session_id and self.current_session_id in self.sessions:
            try:
                self.sessions[self.current_session_id].close()
            except Exception:
                pass
            del self.sessions[self.current_session_id]

        # Create new session (will get different residential IP)
        return self.create_session(use_socks5=use_socks5 or False)

    def test_connection(self, session_id: Optional[str] = None) -> Tuple[bool, dict]:
        """
        Test proxy connection and get IP information.

        Args:
            session_id: Optional session to test

        Returns:
            Tuple of (success, ip_info)
        """
        try:
            session = self.get_session(session_id)

            # Test with httpbin to get IP info
            response = session.get("https://httpbin.org/ip", timeout=10)

            if response.status_code == 200:
                ip_info = response.json()
                return True, ip_info
            else:
                return False, {"error": f"HTTP {response.status_code}"}

        except Exception as e:
            return False, {"error": str(e)}

    def make_request(
        self,
        url: str,
        method: str = "GET",
        session_id: Optional[str] = None,
        retry_count: int = 5,
        **kwargs,
    ) -> requests.Response:
        """
        Make HTTP request through PacketStream proxy with retry logic.

        Args:
            url: URL to request
            method: HTTP method (GET, POST, etc.)
            session_id: Optional session identifier for sticky sessions
            retry_count: Number of retries on failure
            **kwargs: Additional arguments for requests

        Returns:
            Response object

        Raises:
            requests.RequestException: After all retries failed
        """
        session = self.get_session(session_id)
        last_exception = None

        for attempt in range(retry_count):
            try:
                response = session.request(method, url, timeout=30, **kwargs)

                # Check for rate limiting or blocking
                if response.status_code == 429:
                    # Rate limited, rotate IP and retry
                    logger.warning(f"Rate limited, rotating IP (attempt {attempt + 1})")
                    session = self.rotate_session()
                    continue
                elif response.status_code == 403:
                    # Potentially blocked, rotate IP and retry
                    logger.warning(f"Access forbidden, rotating IP (attempt {attempt + 1})")
                    session = self.rotate_session()
                    continue

                return response

            except requests.exceptions.RequestException as e:
                last_exception = e
                logger.warning(f"Request failed (attempt {attempt + 1}): {e}")

                if attempt < retry_count - 1:
                    # Rotate IP and retry
                    session = self.rotate_session()
                    time.sleep(2**attempt)  # Exponential backoff

        # All retries failed
        if last_exception:
            raise last_exception
        raise requests.exceptions.RequestException("All retries failed")

    def cleanup(self):
        """Close all sessions and cleanup resources."""
        for session in self.sessions.values():
            try:
                session.close()
            except Exception:
                pass
        self.sessions.clear()
        self.current_session_id = None


# Maintain backward compatibility with old class name
PacketStreamProxyManager = PacketStreamProvider

