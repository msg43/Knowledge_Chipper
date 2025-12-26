"""
YouTube Video Matcher Service

Matches PDF transcripts to YouTube videos using multiple strategies:
1. Title-based YouTube search
2. Metadata-based search (author + date + title)
3. LLM-generated optimal search query
4. Fuzzy matching against existing database records
"""

import asyncio
import logging
import re
from difflib import SequenceMatcher
from typing import Any, Optional

from playwright.async_api import async_playwright, Page

from ..config import get_settings
from ..database import DatabaseService
from ..logger import get_logger
from .youtube_data_api import YouTubeDataAPI, QuotaExceededError

logger = get_logger(__name__)


class YouTubeVideoMatcher:
    """
    Match PDF transcripts to YouTube videos using multiple strategies.
    
    Strategies (tried in sequence):
    1. Title-based YouTube search
    2. Metadata-based search (author + date + title)
    3. LLM-generated optimal search query
    4. Fuzzy matching against existing database records
    """
    
    def __init__(
        self,
        llm_adapter=None,
        db_service: DatabaseService = None,
        youtube_api: YouTubeDataAPI = None,
        headless: bool = True,
        confidence_threshold: float = 0.8
    ):
        """
        Initialize YouTube video matcher.
        
        Args:
            llm_adapter: Optional LLM adapter for query generation
            db_service: Database service for fuzzy matching
            youtube_api: Optional YouTube Data API instance
            headless: Run browser in headless mode
            confidence_threshold: Minimum confidence for auto-match
        """
        self.llm = llm_adapter
        self.db_service = db_service or DatabaseService()
        self.headless = headless
        self.confidence_threshold = confidence_threshold
        
        # Initialize YouTube Data API if configured
        self.youtube_api = youtube_api
        if not self.youtube_api:
            config = get_settings()
            if config.youtube_api.enabled and config.youtube_api.api_key:
                self.youtube_api = YouTubeDataAPI(
                    api_key=config.youtube_api.api_key,
                    quota_limit=config.youtube_api.quota_limit,
                    batch_size=config.youtube_api.batch_size
                )
                logger.info("✅ YouTube Data API initialized for matching")
            else:
                logger.info("YouTube Data API not configured, will use Playwright search")

    async def find_youtube_video(
        self,
        pdf_metadata: dict[str, Any],
        pdf_text_preview: str,
        strategies: list[str] = None
    ) -> tuple[str | None, float, str]:
        """
        Find YouTube video ID for PDF transcript.
        
        Args:
            pdf_metadata: Metadata extracted from PDF (title, speakers, date, etc.)
            pdf_text_preview: First ~500 words of transcript for context
            strategies: List of strategies to try (default: all)
        
        Returns:
            (video_id, confidence_score, match_method)
            Returns (None, 0.0, "no_match") if no match found
        """
        if strategies is None:
            strategies = [
                "database_fuzzy_match",
                "title_search",
                "metadata_search",
                "llm_query_generation",
            ]
        
        logger.info(f"Attempting to match PDF: {pdf_metadata.get('title', 'Unknown')}")
        
        for strategy in strategies:
            try:
                if strategy == "database_fuzzy_match":
                    result = await self._fuzzy_match_database(pdf_metadata)
                elif strategy == "title_search":
                    result = await self._search_by_title(pdf_metadata)
                elif strategy == "metadata_search":
                    result = await self._search_by_metadata(pdf_metadata)
                elif strategy == "llm_query_generation":
                    result = await self._search_by_llm_query(pdf_metadata, pdf_text_preview)
                else:
                    logger.warning(f"Unknown strategy: {strategy}")
                    continue
                
                video_id, confidence, method = result
                
                if video_id and confidence >= self.confidence_threshold:
                    logger.info(
                        f"✅ Match found via {method}: {video_id} "
                        f"(confidence: {confidence:.2f})"
                    )
                    return (video_id, confidence, method)
                elif video_id:
                    logger.info(
                        f"⚠️ Low confidence match via {method}: {video_id} "
                        f"(confidence: {confidence:.2f})"
                    )
            
            except Exception as e:
                logger.error(f"Strategy {strategy} failed: {e}")
                continue
        
        logger.warning("No match found with any strategy")
        return (None, 0.0, "no_match")

    async def _fuzzy_match_database(
        self,
        pdf_metadata: dict[str, Any]
    ) -> tuple[str | None, float, str]:
        """
        Match against existing videos in database using fuzzy title matching.
        
        Reuses logic from podcast_rss_downloader.py
        """
        title = pdf_metadata.get("title", "")
        if not title:
            return (None, 0.0, "database_fuzzy_match")
        
        # Get all sources from database
        try:
            # Query database for YouTube sources
            session = self.db_service.Session()
            from ..database.models import MediaSource
            
            sources = session.query(MediaSource).filter(
                MediaSource.source_type == "youtube"
            ).all()
            
            best_match = None
            best_similarity = 0.0
            
            for source in sources:
                similarity = SequenceMatcher(
                    None,
                    title.lower(),
                    source.title.lower()
                ).ratio()
                
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = source.source_id
                
                # Check date proximity if available
                if pdf_metadata.get("date") and source.upload_date:
                    try:
                        from datetime import datetime
                        pdf_date = pdf_metadata["date"]
                        if isinstance(pdf_date, str):
                            pdf_date = datetime.fromisoformat(pdf_date)
                        
                        source_date = datetime.strptime(source.upload_date, "%Y%m%d")
                        date_diff = abs((pdf_date - source_date).days)
                        
                        # Boost similarity if dates are close
                        if date_diff <= 2:
                            similarity += 0.1
                            if similarity > best_similarity:
                                best_similarity = similarity
                                best_match = source.source_id
                    except Exception:
                        pass
            
            session.close()
            
            if best_match and best_similarity >= 0.7:
                return (best_match, best_similarity, "database_fuzzy_match")
            
        except Exception as e:
            logger.error(f"Database fuzzy match failed: {e}")
        
        return (None, 0.0, "database_fuzzy_match")

    async def _search_by_title(
        self,
        pdf_metadata: dict[str, Any]
    ) -> tuple[str | None, float, str]:
        """Search YouTube by title extracted from PDF."""
        title = pdf_metadata.get("title", "")
        if not title:
            return (None, 0.0, "title_search")
        
        search_query = title
        return await self._youtube_search(search_query, pdf_metadata, "title_search")

    async def _search_by_metadata(
        self,
        pdf_metadata: dict[str, Any]
    ) -> tuple[str | None, float, str]:
        """Search YouTube using author + date + title."""
        title = pdf_metadata.get("title", "")
        speakers = pdf_metadata.get("speakers", [])
        date = pdf_metadata.get("date")
        
        # Construct search query
        query_parts = []
        
        if speakers:
            # Use first speaker (usually the host)
            query_parts.append(speakers[0])
        
        if title:
            query_parts.append(title)
        
        if date:
            try:
                from datetime import datetime
                if isinstance(date, str):
                    date = datetime.fromisoformat(date)
                query_parts.append(date.strftime("%Y"))
            except Exception:
                pass
        
        search_query = " ".join(query_parts)
        return await self._youtube_search(search_query, pdf_metadata, "metadata_search")

    async def _search_by_llm_query(
        self,
        pdf_metadata: dict[str, Any],
        pdf_text_preview: str
    ) -> tuple[str | None, float, str]:
        """Use LLM to generate optimal YouTube search query."""
        if not self.llm:
            logger.warning("LLM adapter not available for query generation")
            return (None, 0.0, "llm_query_generation")
        
        # Construct prompt for LLM
        prompt = f"""Generate an optimal YouTube search query to find this video.

Transcript Metadata:
- Title: {pdf_metadata.get('title', 'Unknown')}
- Speakers: {', '.join(pdf_metadata.get('speakers', []))}
- Date: {pdf_metadata.get('date', 'Unknown')}

Transcript Preview (first 500 words):
{pdf_text_preview[:2000]}

Generate a concise YouTube search query (max 10 words) that would find this video.
Focus on unique identifiers like speaker names, episode numbers, or distinctive topics.

Search query:"""
        
        try:
            response = await self.llm.complete(prompt, max_tokens=50)
            search_query = response.strip().strip('"').strip("'")
            
            logger.info(f"LLM generated search query: {search_query}")
            
            return await self._youtube_search(
                search_query,
                pdf_metadata,
                "llm_query_generation"
            )
        
        except Exception as e:
            logger.error(f"LLM query generation failed: {e}")
            return (None, 0.0, "llm_query_generation")

    async def _youtube_search(
        self,
        search_query: str,
        pdf_metadata: dict[str, Any],
        method: str
    ) -> tuple[str | None, float, str]:
        """
        Perform YouTube search using API (preferred) or Playwright (fallback).
        
        Args:
            search_query: Search query string
            pdf_metadata: PDF metadata for matching
            method: Method name for logging
        
        Returns:
            (video_id, confidence, method)
        """
        logger.info(f"Searching YouTube: {search_query}")
        
        # Try YouTube Data API first (if available)
        if self.youtube_api:
            try:
                logger.info("Using YouTube Data API for search")
                results_metadata = self.youtube_api.search_videos(
                    query=search_query,
                    max_results=10
                )
                
                if results_metadata:
                    # Convert to format expected by _score_search_results
                    results = [
                        {
                            "video_id": m["source_id"],
                            "title": m["title"],
                            "channel": m["uploader"],
                        }
                        for m in results_metadata
                    ]
                    
                    # Score results
                    best_match = self._score_search_results(results, pdf_metadata)
                    
                    if best_match:
                        video_id, confidence = best_match
                        return (video_id, confidence, f"{method}_api")
                
            except QuotaExceededError:
                logger.warning("⚠️ YouTube API quota exceeded, falling back to Playwright")
            except Exception as e:
                logger.warning(f"YouTube API search failed, falling back to Playwright: {e}")
        
        # Fallback to Playwright search
        try:
            logger.info("Using Playwright for search")
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                context = await browser.new_context()
                page = await context.new_page()
                
                # Navigate to YouTube search
                search_url = f"https://www.youtube.com/results?search_query={search_query.replace(' ', '+')}"
                await page.goto(search_url, wait_until='networkidle', timeout=15000)
                
                # Wait for results to load
                await page.wait_for_selector('ytd-video-renderer', timeout=10000)
                
                # Extract top results
                results = await self._extract_search_results(page)
                
                await browser.close()
                
                if not results:
                    logger.warning("No search results found")
                    return (None, 0.0, method)
                
                # Score results against PDF metadata
                best_match = self._score_search_results(results, pdf_metadata)
                
                if best_match:
                    video_id, confidence = best_match
                    return (video_id, confidence, f"{method}_playwright")
                
        except Exception as e:
            logger.error(f"YouTube search failed: {e}")
        
        return (None, 0.0, method)

    async def _extract_search_results(self, page: Page) -> list[dict[str, Any]]:
        """Extract video information from YouTube search results page."""
        results = []
        
        try:
            # Get all video renderer elements
            video_elements = await page.query_selector_all('ytd-video-renderer')
            
            for element in video_elements[:10]:  # Top 10 results
                try:
                    # Extract video ID from link
                    link_element = await element.query_selector('a#video-title')
                    if not link_element:
                        continue
                    
                    href = await link_element.get_attribute('href')
                    if not href:
                        continue
                    
                    # Extract video ID
                    match = re.search(r'/watch\?v=([a-zA-Z0-9_-]{11})', href)
                    if not match:
                        continue
                    
                    video_id = match.group(1)
                    
                    # Extract title
                    title = await link_element.get_attribute('title')
                    if not title:
                        title = await link_element.inner_text()
                    
                    # Extract channel name
                    channel_element = await element.query_selector('ytd-channel-name a')
                    channel = ""
                    if channel_element:
                        channel = await channel_element.inner_text()
                    
                    results.append({
                        "video_id": video_id,
                        "title": title.strip(),
                        "channel": channel.strip(),
                    })
                
                except Exception as e:
                    logger.debug(f"Failed to extract result: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Failed to extract search results: {e}")
        
        return results

    def _score_search_results(
        self,
        results: list[dict[str, Any]],
        pdf_metadata: dict[str, Any]
    ) -> tuple[str, float] | None:
        """
        Score search results against PDF metadata.
        
        Returns:
            (video_id, confidence) or None
        """
        pdf_title = pdf_metadata.get("title", "").lower()
        pdf_speakers = [s.lower() for s in pdf_metadata.get("speakers", [])]
        
        best_match = None
        best_score = 0.0
        
        for result in results:
            score = 0.0
            
            # Title similarity
            title_similarity = SequenceMatcher(
                None,
                pdf_title,
                result["title"].lower()
            ).ratio()
            score += title_similarity * 0.7
            
            # Speaker/channel match
            channel_lower = result["channel"].lower()
            for speaker in pdf_speakers:
                if speaker in channel_lower or channel_lower in speaker:
                    score += 0.3
                    break
            
            if score > best_score:
                best_score = score
                best_match = (result["video_id"], score)
        
        return best_match if best_score >= 0.5 else None

