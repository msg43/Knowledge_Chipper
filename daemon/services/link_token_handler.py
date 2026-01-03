"""
Link Token Handler

Handles automatic device linking via download token.
This runs on daemon first launch to check for link tokens.
"""

import json
import logging
import requests
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)


class LinkTokenHandler:
    """Handles automatic device linking via download tokens."""
    
    def __init__(self, daemon_url: str = "http://127.0.0.1:8765"):
        self.daemon_url = daemon_url
        self.token_cache_path = Path.home() / ".skip_the_podcast" / "link_token_cache.json"
        self.token_cache_path.parent.mkdir(parents=True, exist_ok=True)
    
    def extract_token_from_url(self, url: str) -> Optional[str]:
        """
        Extract link token from download URL.
        
        Example URL:
        https://github.com/.../Skip_the_Podcast_Desktop.pkg?link_token=abc123...
        """
        try:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            token = params.get('link_token', [None])[0]
            return token
        except Exception as e:
            logger.error(f"Failed to extract token from URL: {e}")
            return None
    
    def check_for_cached_token(self) -> Optional[str]:
        """
        Check if there's a cached link token from installation.
        
        The installer can write the token to this cache file during installation.
        """
        try:
            if not self.token_cache_path.exists():
                return None
            
            cache = json.loads(self.token_cache_path.read_text())
            token = cache.get('link_token')
            
            if token:
                logger.info("Found cached link token from installation")
            
            return token
        except Exception as e:
            logger.error(f"Failed to read cached link token: {e}")
            return None
    
    def link_device_with_token(self, token: str) -> bool:
        """
        Link device using the provided token.
        
        Calls daemon API endpoint which verifies token with GetReceipts.
        """
        try:
            logger.info("Attempting to auto-link device with download token...")
            
            response = requests.post(
                f"{self.daemon_url}/api/config/link-device",
                params={"token": token},
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ Device successfully auto-linked: {data.get('message')}")
                
                # Clean up the cached token after successful use
                self.clear_cached_token()
                
                return True
            else:
                error = response.json().get('detail', 'Unknown error')
                logger.warning(f"Failed to link device with token: {error}")
                
                # Clear invalid token from cache
                self.clear_cached_token()
                
                return False
        
        except requests.RequestException as e:
            logger.error(f"Network error during device linking: {e}")
            return False
        except Exception as e:
            logger.exception("Unexpected error during device linking")
            return False
    
    def clear_cached_token(self):
        """Remove cached token after use or if invalid."""
        try:
            if self.token_cache_path.exists():
                self.token_cache_path.unlink()
                logger.debug("Cleared cached link token")
        except Exception as e:
            logger.error(f"Failed to clear cached token: {e}")
    
    def check_and_link(self) -> bool:
        """
        Check for link token and attempt auto-linking.
        
        This is called on daemon first run.
        Returns True if device was linked, False otherwise.
        """
        # Check for cached token from installer
        token = self.check_for_cached_token()
        
        if not token:
            logger.debug("No cached link token found - manual device claiming will be required")
            return False
        
        # Attempt to link with the token
        success = self.link_device_with_token(token)
        
        if success:
            logger.info("🎉 Device auto-linked successfully!")
        else:
            logger.info("Auto-linking failed - user can manually claim device later")
        
        return success


# Global instance
_link_token_handler = None


def get_link_token_handler() -> LinkTokenHandler:
    """Get or create the global link token handler instance."""
    global _link_token_handler
    if _link_token_handler is None:
        _link_token_handler = LinkTokenHandler()
    return _link_token_handler

