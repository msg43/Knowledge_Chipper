"""
PacketStream Residential Proxy Manager

Provides rotating residential proxies with sticky sessions for YouTube data extraction.
Based on: https://github.com/packetstream/packetstream-examples
"""

import os
import random
import time
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests


class PacketStreamProxyManager:
    """Manages PacketStream residential proxy connections with rotation and sticky sessions."""

    def __init__(self, username: str = None, auth_key: str = None):
        """
        Initialize PacketStream proxy manager.

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
                from ..config import KnowledgeSystemConfig

                config = KnowledgeSystemConfig()
                self.username = self.username or config.api_keys.packetstream_username
                self.auth_key = self.auth_key or config.api_keys.packetstream_auth_key
            except Exception:
                pass  # Config loading failed, use what we have

        if not self.username or not self.auth_key:
            raise ValueError(
                "PacketStream credentials required. Set via:\n"
                "1. Environment variables: PACKETSTREAM_USERNAME and PACKETSTREAM_AUTH_KEY\n"
                "2. GUI Settings tab: PacketStream Username and Auth Key\n"
                "3. Pass directly to constructor"
            )

        # PacketStream proxy endpoints
        self.proxy_endpoints = [
            "proxy.packetstream.io:31112",  # HTTP proxy (working port)
            "proxy.packetstream.io:31113",  # SOCKS5 proxy
        ]

        # Session management for sticky sessions
        self.sessions = {}
        self.current_session_id = None

    def _get_proxy_config(self, use_socks5: bool = False) -> dict[str, str]:
        """
        Get proxy configuration for requests.

        Args:
            use_socks5: Whether to use SOCKS5 proxy (default: HTTP)

        Returns:
            Dict with proxy configuration for requests library
        """
        if use_socks5:
            proxy_url = (
                f"socks5h://{self.username}:{self.auth_key}@proxy.packetstream.io:31113"
            )
            return {"http": proxy_url, "https": proxy_url}
        else:
            proxy_url = (
                f"http://{self.username}:{self.auth_key}@proxy.packetstream.io:31112"
            )
            return {"http": proxy_url, "https": proxy_url}

    def create_session(
        self, session_id: str = None, use_socks5: bool = False
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
        session.proxies = self._get_proxy_config(use_socks5=use_socks5)

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

    def get_session(self, session_id: str = None) -> requests.Session:
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

    def rotate_session(self, use_socks5: bool = None) -> requests.Session:
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
            except:
                pass
            del self.sessions[self.current_session_id]

        # Create new session (will get different residential IP)
        return self.create_session(use_socks5=use_socks5)

    def test_connection(self, session_id: str = None) -> tuple[bool, dict]:
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
        session_id: str = None,
        retry_count: int = 3,
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
                    print(f"Rate limited, rotating IP (attempt {attempt + 1})")
                    session = self.rotate_session()
                    continue
                elif response.status_code == 403:
                    # Potentially blocked, rotate IP and retry
                    print(f"Access forbidden, rotating IP (attempt {attempt + 1})")
                    session = self.rotate_session()
                    continue

                return response

            except requests.exceptions.RequestException as e:
                last_exception = e
                print(f"Request failed (attempt {attempt + 1}): {e}")

                if attempt < retry_count - 1:
                    # Rotate IP and retry
                    session = self.rotate_session()
                    time.sleep(2**attempt)  # Exponential backoff

        # All retries failed
        raise last_exception

    def get_youtube_data(self, video_url: str, session_id: str = None) -> dict | None:
        """
        Example: Extract YouTube video data using yt-dlp through PacketStream proxy.

        Args:
            video_url: YouTube video URL
            session_id: Optional session identifier

        Returns:
            Video metadata dict or None
        """
        try:
            import yt_dlp

            # Get proxy configuration
            proxy_config = self._get_proxy_config(use_socks5=False)
            proxy_url = proxy_config["https"]

            # Configure yt-dlp with PacketStream proxy
            ydl_opts = {
                "proxy": proxy_url,
                "quiet": True,
                "no_warnings": True,
                "extract_flat": False,
                "writesubtitles": False,
                "writeautomaticsub": False,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                return info

        except ImportError:
            print("yt-dlp not installed. Install with: pip install yt-dlp")
            return None
        except Exception as e:
            print(f"YouTube data extraction failed: {e}")
            return None

    def cleanup(self):
        """Close all sessions and cleanup resources."""
        for session in self.sessions.values():
            try:
                session.close()
            except:
                pass
        self.sessions.clear()
        self.current_session_id = None


def test_packetstream_proxy():
    """Test function to verify PacketStream proxy functionality."""
    try:
        # Initialize proxy manager
        proxy_manager = PacketStreamProxyManager()

        print("🔄 Testing PacketStream Proxy Connection...")

        # Test connection
        success, ip_info = proxy_manager.test_connection()

        if success:
            print(f"✅ Proxy connection successful!")
            print(f"📍 Current IP: {ip_info.get('origin', 'Unknown')}")

            # Test IP rotation
            print("\n🔄 Testing IP rotation...")
            session2 = proxy_manager.rotate_session()
            success2, ip_info2 = proxy_manager.test_connection()

            if success2:
                ip1 = ip_info.get("origin", "Unknown")
                ip2 = ip_info2.get("origin", "Unknown")
                print(f"📍 Rotated IP: {ip2}")

                if ip1 != ip2:
                    print("✅ IP rotation working!")
                else:
                    print("⚠️  Same IP returned (normal for some providers)")

            return True

        else:
            print(f"❌ Proxy connection failed: {ip_info}")
            return False

    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    finally:
        try:
            proxy_manager.cleanup()
        except:
            pass


if __name__ == "__main__":
    test_packetstream_proxy()
