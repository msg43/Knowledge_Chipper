"""
Browser Cookie Manager
Loads YouTube authentication cookies from user's installed browsers
and converts them to Playwright format.
"""
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from ..utils.youtube_utils import get_single_working_strategy

logger = logging.getLogger(__name__)


class BrowserCookieManager:
    """
    Manages loading and converting browser cookies for Playwright.
    Reuses existing yt-dlp cookie loading infrastructure.
    """
    
    def __init__(self):
        self._cached_cookies = None
        self._cache_timestamp = None
        
    def get_youtube_cookies_for_playwright(self) -> List[Dict[str, Any]]:
        """
        Get YouTube cookies in Playwright format.
        
        Returns:
            List of cookie dicts compatible with playwright's add_cookies():
            [
                {
                    'name': 'CONSENT',
                    'value': 'YES+...',
                    'domain': '.youtube.com',
                    'path': '/',
                    'expires': 1234567890,
                    'httpOnly': False,
                    'secure': True,
                    'sameSite': 'Lax'
                },
                ...
            ]
        """
        # Get cookies using existing yt-dlp infrastructure
        strategy = get_single_working_strategy()
        
        if 'cookiejar' in strategy:
            # Convert cookiejar to Playwright format
            return self._convert_cookiejar_to_playwright(strategy['cookiejar'])
        elif 'cookiefile' in strategy:
            # Load from file and convert
            return self._load_cookie_file_for_playwright(strategy['cookiefile'])
        else:
            logger.warning("No cookies available - YouTube scraping may fail")
            return []
    
    def _convert_cookiejar_to_playwright(self, cookiejar) -> List[Dict[str, Any]]:
        """Convert http.cookiejar to Playwright cookie format."""
        playwright_cookies = []
        
        for cookie in cookiejar:
            # Only include YouTube cookies
            if 'youtube.com' not in cookie.domain and 'google.com' not in cookie.domain:
                continue
                
            playwright_cookie = {
                'name': cookie.name,
                'value': cookie.value,
                'domain': cookie.domain,
                'path': cookie.path,
                'secure': bool(cookie.secure),  # Ensure boolean, not int
                'httpOnly': bool(cookie.has_nonstandard_attr('HttpOnly')) if hasattr(cookie, 'has_nonstandard_attr') else False,
            }
            
            # Add expiry if present and valid
            if cookie.expires and cookie.expires > 0:
                playwright_cookie['expires'] = int(cookie.expires)
            elif cookie.expires == 0:
                # Session cookie - use -1
                playwright_cookie['expires'] = -1
            
            # Add sameSite if present
            if hasattr(cookie, 'has_nonstandard_attr') and cookie.has_nonstandard_attr('SameSite'):
                playwright_cookie['sameSite'] = cookie.get_nonstandard_attr('SameSite')
            else:
                playwright_cookie['sameSite'] = 'Lax'  # Default
            
            playwright_cookies.append(playwright_cookie)
        
        logger.info(f"Converted {len(playwright_cookies)} cookies for Playwright")
        return playwright_cookies
    
    def _load_cookie_file_for_playwright(self, cookie_file: str) -> List[Dict[str, Any]]:
        """Load cookies from Netscape format file and convert to Playwright."""
        # For now, just log that we got a cookie file
        # This would need full Netscape cookie file parsing
        logger.info(f"Cookie file provided: {cookie_file}")
        # TODO: Implement Netscape cookie file parsing if needed
        return []
    
    def has_valid_cookies(self) -> bool:
        """Check if we have valid YouTube authentication cookies."""
        cookies = self.get_youtube_cookies_for_playwright()
        
        # Check for essential YouTube auth cookies
        essential_cookies = {'SID', 'HSID', 'SSID', 'APISID', 'SAPISID'}
        found_cookies = {c['name'] for c in cookies}
        
        has_auth = bool(essential_cookies & found_cookies)
        
        if has_auth:
            logger.info("✅ Valid YouTube authentication cookies found")
        else:
            logger.warning("⚠️  No YouTube authentication cookies found")
        
        return has_auth

