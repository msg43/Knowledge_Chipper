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
        skipped_count = 0
        
        for cookie in cookiejar:
            # Only include YouTube cookies
            if 'youtube.com' not in cookie.domain and 'google.com' not in cookie.domain:
                continue
            
            try:
                playwright_cookie = {
                    'name': cookie.name,
                    'value': cookie.value,
                    'domain': cookie.domain,
                    'path': cookie.path,
                    'secure': bool(cookie.secure),  # Ensure boolean, not int
                    'httpOnly': bool(cookie.has_nonstandard_attr('HttpOnly')) if hasattr(cookie, 'has_nonstandard_attr') else False,
                }
                
                # Handle expires field carefully - Playwright is very strict
                # Valid values: -1 (session cookie) or positive unix timestamp
                # Invalid: None, 0, negative numbers (except -1), non-numeric
                if hasattr(cookie, 'expires') and cookie.expires is not None:
                    try:
                        expires_value = int(cookie.expires)
                        
                        # Validate the value
                        if expires_value == -1:
                            # Session cookie
                            playwright_cookie['expires'] = -1
                        elif expires_value > 0:
                            # Valid timestamp
                            playwright_cookie['expires'] = expires_value
                        else:
                            # Invalid (0 or negative except -1) - skip expires field
                            # Playwright will treat as session cookie
                            logger.debug(f"Cookie {cookie.name} has invalid expires={expires_value}, treating as session")
                    except (ValueError, TypeError) as e:
                        # Non-numeric expires - skip it
                        logger.debug(f"Cookie {cookie.name} has non-numeric expires: {cookie.expires}")
                # If no expires field, Playwright treats it as session cookie (which is fine)
                
                # Add sameSite if present
                if hasattr(cookie, 'has_nonstandard_attr') and cookie.has_nonstandard_attr('SameSite'):
                    samsite_value = cookie.get_nonstandard_attr('SameSite')
                    # Validate sameSite value
                    if samsite_value in ['Strict', 'Lax', 'None']:
                        playwright_cookie['sameSite'] = samsite_value
                    else:
                        playwright_cookie['sameSite'] = 'Lax'  # Safe default
                else:
                    playwright_cookie['sameSite'] = 'Lax'  # Default
                
                playwright_cookies.append(playwright_cookie)
                
            except Exception as e:
                # Skip problematic cookies
                skipped_count += 1
                logger.debug(f"Skipping cookie {cookie.name}: {e}")
                continue
        
        if skipped_count > 0:
            logger.info(f"Converted {len(playwright_cookies)} cookies for Playwright (skipped {skipped_count} invalid cookies)")
        else:
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

