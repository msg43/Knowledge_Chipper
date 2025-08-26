"""
RSS Feed Processor

Processes RSS feeds by extracting article content and processing through
the standard Knowledge System pipeline for transcription and analysis.
"""

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
try:
    from bs4 import BeautifulSoup  # type: ignore
except Exception:  # pragma: no cover - optional in minimal CI installs
    BeautifulSoup = None  # type: ignore

from ..errors import ProcessingError
from ..logger import get_logger
from .base import BaseProcessor, ProcessorResult

logger = get_logger(__name__)

try:
    import feedparser
    FEEDPARSER_AVAILABLE = True
except ImportError:
    FEEDPARSER_AVAILABLE = False
    logger.warning("feedparser not available. RSS processing will not work.")


class RSSProcessor(BaseProcessor):
    """Processor for extracting content from RSS feeds."""

    def __init__(self, name: str | None = None) -> None:
        super().__init__(name or "rss_processor")
        
        if not FEEDPARSER_AVAILABLE:
            raise ProcessingError(
                "feedparser is required for RSS processing. "
                "Install it with: pip install feedparser"
            )

    @property
    def supported_formats(self) -> list[str]:
        # RSS is URL-based, not file-based
        return []

    def validate_input(self, input_data: Any) -> bool:
        """Validate that input is an RSS feed URL."""
        if not isinstance(input_data, str):
            return False
        
        # Basic URL validation
        parsed = urlparse(input_data)
        if not parsed.scheme or not parsed.netloc:
            return False
            
        return self._is_rss_url(input_data)

    def _is_rss_url(self, url: str) -> bool:
        """Check if URL appears to be an RSS feed."""
        url_lower = url.lower()
        
        # Common RSS URL patterns
        rss_patterns = [
            r'.*\.rss$',
            r'.*rss\.xml$', 
            r'.*/rss/?$',
            r'.*/feed/?$',
            r'.*feeds?\..*',
            r'.*/atom\.xml$',
            r'.*/index\.xml$',
        ]
        
        for pattern in rss_patterns:
            if re.match(pattern, url_lower):
                return True
                
        # Check for RSS-like query parameters
        if any(param in url_lower for param in ['rss', 'feed', 'atom']):
            return True
            
        return False

    def process(
        self, input_data: Any, dry_run: bool = False, **kwargs: Any
    ) -> ProcessorResult:
        """Process RSS feed and extract article content."""
        
        rss_url = str(input_data)
        
        if not self.validate_input(rss_url):
            return ProcessorResult(
                success=False,
                errors=[f"Invalid RSS URL: {rss_url}"],
                dry_run=dry_run
            )

        if dry_run:
            return ProcessorResult(
                success=True,
                data=f"[DRY RUN] Would process RSS feed: {rss_url}",
                metadata={"rss_url": rss_url, "dry_run": True},
                dry_run=True
            )

        try:
            logger.info(f"Processing RSS feed: {rss_url}")
            
            # Parse RSS feed
            feed_data = self._parse_rss_feed(rss_url)
            
            if not feed_data:
                return ProcessorResult(
                    success=False,
                    errors=[f"Failed to parse RSS feed: {rss_url}"]
                )

            # Extract articles
            articles = self._extract_articles(feed_data, **kwargs)
            
            if not articles:
                return ProcessorResult(
                    success=False,
                    errors=[f"No articles found in RSS feed: {rss_url}"]
                )

            # Format results
            result_data = {
                "feed_info": {
                    "title": feed_data.feed.get("title", "Unknown Feed"),
                    "description": feed_data.feed.get("description", ""),
                    "link": feed_data.feed.get("link", rss_url),
                    "total_articles": len(articles)
                },
                "articles": articles
            }

            logger.info(f"Successfully processed RSS feed: {len(articles)} articles extracted")

            return ProcessorResult(
                success=True,
                data=result_data,
                metadata={
                    "rss_url": rss_url,
                    "feed_title": feed_data.feed.get("title", "Unknown"),
                    "articles_count": len(articles),
                    "processed_at": datetime.now().isoformat()
                }
            )

        except Exception as e:
            logger.error(f"Error processing RSS feed {rss_url}: {e}")
            return ProcessorResult(
                success=False,
                errors=[f"RSS processing error: {str(e)}"]
            )

    def _parse_rss_feed(self, rss_url: str) -> Any:
        """Parse RSS feed using feedparser."""
        try:
            # Set user agent to avoid blocking
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            
            logger.info(f"Fetching RSS feed: {rss_url}")
            response = requests.get(rss_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Parse with feedparser
            feed_data = feedparser.parse(response.content)
            
            if feed_data.bozo and not feed_data.entries:
                logger.warning(f"RSS feed may be malformed: {rss_url}")
                return None
                
            logger.info(f"RSS feed parsed successfully: {len(feed_data.entries)} entries found")
            return feed_data
            
        except Exception as e:
            logger.error(f"Failed to parse RSS feed {rss_url}: {e}")
            return None

    def _extract_articles(self, feed_data: Any, max_articles: int = 10, **kwargs) -> list[dict]:
        """Extract article content from RSS feed entries."""
        articles = []
        
        for i, entry in enumerate(feed_data.entries[:max_articles]):
            try:
                article = self._extract_single_article(entry)
                if article:
                    articles.append(article)
                    logger.debug(f"Extracted article {i+1}: {article['title'][:50]}...")
                    
            except Exception as e:
                logger.warning(f"Failed to extract article {i+1}: {e}")
                continue
                
        return articles

    def _extract_single_article(self, entry: Any) -> dict | None:
        """Extract content from a single RSS entry."""
        try:
            # Get article metadata
            title = entry.get("title", "Untitled")
            link = entry.get("link", "")
            published = entry.get("published", "")
            
            # Get content - try multiple fields
            content = ""
            
            # Try content field first (most detailed)
            if hasattr(entry, 'content') and entry.content:
                for content_item in entry.content:
                    if content_item.get('type') == 'text/html':
                        content = content_item.get('value', '')
                        break
                    elif content_item.get('type') == 'text/plain':
                        content = content_item.get('value', '')
            
            # Fall back to summary/description
            if not content:
                content = entry.get("summary", "") or entry.get("description", "")
            
            # If still no content, try to fetch from link
            if not content and link:
                content = self._fetch_article_content(link)
            
            # Clean up HTML content
            if content:
                content = self._clean_html_content(content)
            
            if not content:
                logger.warning(f"No content found for article: {title}")
                return None
                
            return {
                "title": title,
                "link": link,
                "published": published,
                "content": content,
                "word_count": len(content.split()),
                "extracted_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error extracting article: {e}")
            return None

    def _fetch_article_content(self, article_url: str) -> str:
        """Fetch full article content from URL."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            
            response = requests.get(article_url, headers=headers, timeout=15)
            response.raise_for_status()
            
            # Parse HTML and extract main content
            if BeautifulSoup is None:
                raise ProcessingError("BeautifulSoup4 is required. Install with: pip install beautifulsoup4")
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove unwanted elements
            for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                element.decompose()
            
            # Try to find main content area
            main_content = None
            for selector in ['article', 'main', '.content', '#content', '.post', '.entry']:
                main_content = soup.select_one(selector)
                if main_content:
                    break
            
            if not main_content:
                main_content = soup.find('body') or soup
                
            return main_content.get_text(strip=True, separator='\n')
            
        except Exception as e:
            logger.warning(f"Failed to fetch article content from {article_url}: {e}")
            return ""

    def _clean_html_content(self, html_content: str) -> str:
        """Clean HTML content and extract plain text."""
        try:
            if BeautifulSoup is None:
                return html_content
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove unwanted elements
            for element in soup(['script', 'style', 'nav', 'header', 'footer']):
                element.decompose()
                
            # Get clean text
            text = soup.get_text(strip=True, separator='\n')
            
            # Clean up whitespace
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            return '\n'.join(lines)
            
        except Exception as e:
            logger.warning(f"Failed to clean HTML content: {e}")
            return html_content  # Return as-is if cleaning fails
