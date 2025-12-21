"""
Playwright-based YouTube AI Summary Scraper
Works for end users without Cursor IDE.
"""
import asyncio
import logging
import time
from typing import Dict, Any, Optional

from playwright.async_api import async_playwright, Page, Browser, BrowserContext

from .browser_cookie_manager import BrowserCookieManager

logger = logging.getLogger(__name__)


class PlaywrightYouTubeScraper:
    """
    Scrapes YouTube AI-generated summaries using Playwright.
    Handles authentication via browser cookies.
    """
    
    def __init__(self, headless: bool = True, timeout: int = 30):
        self.headless = headless
        self.timeout = timeout
        self.cookie_manager = BrowserCookieManager()
        
    async def scrape_summary(self, url: str, progress_callback=None) -> Dict[str, Any]:
        """
        Scrape YouTube AI summary for a video.
        
        Args:
            url: YouTube video URL
            progress_callback: Optional callback for progress updates
            
        Returns:
            {
                'success': bool,
                'summary': str or None,
                'duration': float,
                'error': str or None,
                'method': 'youtube_ai'
            }
        """
        start_time = time.time()
        
        if progress_callback:
            progress_callback("🌐 Launching browser...")
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                context = await browser.new_context()
                
                # Inject cookies
                if progress_callback:
                    progress_callback("🔐 Loading authentication cookies...")
                
                cookies = self.cookie_manager.get_youtube_cookies_for_playwright()
                if cookies:
                    await context.add_cookies(cookies)
                    logger.info(f"Injected {len(cookies)} cookies")
                else:
                    logger.warning("No cookies available - may not be authenticated")
                
                page = await context.new_page()
                
                try:
                    # Navigate to video
                    if progress_callback:
                        progress_callback("📺 Navigating to video...")
                    
                    await page.goto(url, wait_until='networkidle', timeout=10000)
                    
                    # Find and click Ask button
                    if progress_callback:
                        progress_callback("🔍 Looking for Ask button...")
                    
                    ask_button = await self._find_ask_button(page)
                    if not ask_button:
                        return {
                            'success': False,
                            'summary': None,
                            'duration': time.time() - start_time,
                            'error': 'Ask button not found (may require YouTube Premium)',
                            'method': 'youtube_ai'
                        }
                    
                    # Click Ask button
                    if progress_callback:
                        progress_callback("👆 Clicking Ask button...")
                    
                    await ask_button.click()
                    await page.wait_for_timeout(2000)  # Wait for panel to open
                    
                    # Find and click Summarize option
                    if progress_callback:
                        progress_callback("📝 Clicking Summarize...")
                    
                    summarize_button = await self._find_summarize_button(page)
                    if not summarize_button:
                        return {
                            'success': False,
                            'summary': None,
                            'duration': time.time() - start_time,
                            'error': 'Summarize option not found',
                            'method': 'youtube_ai'
                        }
                    
                    await summarize_button.click()
                    
                    # Wait for summary generation
                    if progress_callback:
                        progress_callback("⏳ Waiting for YouTube to generate summary...")
                    
                    summary_text = await self._wait_for_summary(page, progress_callback)
                    
                    if summary_text:
                        duration = time.time() - start_time
                        if progress_callback:
                            progress_callback(f"✅ YouTube summary complete ({duration:.1f}s)")
                        
                        return {
                            'success': True,
                            'summary': summary_text,
                            'duration': duration,
                            'error': None,
                            'method': 'youtube_ai'
                        }
                    else:
                        return {
                            'success': False,
                            'summary': None,
                            'duration': time.time() - start_time,
                            'error': 'Summary generation timeout (waited 30 seconds)',
                            'method': 'youtube_ai'
                        }
                        
                finally:
                    await browser.close()
                    
        except Exception as e:
            logger.error(f"Playwright scraping failed: {e}", exc_info=True)
            return {
                'success': False,
                'summary': None,
                'duration': time.time() - start_time,
                'error': f'Scraping error: {str(e)}',
                'method': 'youtube_ai'
            }
    
    async def _find_ask_button(self, page: Page) -> Optional[Any]:
        """Find the Ask button using multiple selectors."""
        selectors = [
            "button[aria-label*='Ask']",
            "button:has-text('Ask')",
            "ytd-button-renderer:has-text('Ask')",
            "#ask-button",
        ]
        
        for selector in selectors:
            try:
                button = await page.query_selector(selector)
                if button and await button.is_visible():
                    logger.info(f"Found Ask button with selector: {selector}")
                    return button
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")
                continue
        
        return None
    
    async def _find_summarize_button(self, page: Page) -> Optional[Any]:
        """Find the Summarize option using multiple selectors."""
        selectors = [
            "button:has-text('Summarize')",
            "ytd-menu-item:has-text('Summarize')",
            "[data-action='summarize']",
            "tp-yt-paper-item:has-text('Summarize')",
        ]
        
        for selector in selectors:
            try:
                button = await page.query_selector(selector)
                if button and await button.is_visible():
                    logger.info(f"Found Summarize button with selector: {selector}")
                    return button
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")
                continue
        
        return None
    
    async def _wait_for_summary(self, page: Page, progress_callback=None, max_wait: int = 30) -> Optional[str]:
        """
        Wait for summary to be generated with progressive polling.
        
        YouTube needs 5-10 seconds to generate the summary after clicking.
        We poll every second to detect when it appears.
        """
        # Initial wait - YouTube needs time to start generation
        await page.wait_for_timeout(5000)  # 5 seconds
        
        start = time.time()
        check_count = 0
        
        while (time.time() - start) < max_wait:
            check_count += 1
            
            # Try multiple selectors for summary content
            selectors = [
                '.summary-text',
                '[role="article"] p',
                '.response-content',
                'div[class*="summary"] p',
                'ytd-engagement-panel-section-list-renderer p',
            ]
            
            for selector in selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        text = await element.inner_text()
                        if len(text) > 50:  # Has meaningful content
                            # Wait 2 more seconds to ensure it's complete
                            await page.wait_for_timeout(2000)
                            
                            # Re-fetch to get complete text
                            final_text = await element.inner_text()
                            logger.info(f"Summary found after {time.time() - start:.1f}s")
                            return final_text
                except Exception as e:
                    logger.debug(f"Selector {selector} check failed: {e}")
                    continue
            
            # Update progress
            if progress_callback and check_count % 5 == 0:
                elapsed = int(time.time() - start)
                progress_callback(f"⏳ Still waiting... ({elapsed}s)")
            
            # Check every second
            await page.wait_for_timeout(1000)
        
        logger.warning(f"Summary not found after {max_wait} seconds")
        return None

