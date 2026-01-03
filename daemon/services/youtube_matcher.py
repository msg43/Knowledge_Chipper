"""
YouTube Matcher Service

Searches YouTube for videos matching transcript content.
Uses YouTube Data API for searching and metadata retrieval.
"""

import logging
import os
import sys
import re
from pathlib import Path
from typing import Optional
from datetime import datetime

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    YOUTUBE_API_AVAILABLE = True
except ImportError:
    YOUTUBE_API_AVAILABLE = False

from daemon.models.schemas import YouTubeSearchRequest, YouTubeMatch, YouTubeSearchResponse

logger = logging.getLogger(__name__)


class YouTubeMatcher:
    """
    Service for matching transcripts to YouTube videos.
    
    Uses YouTube Data API to search for videos based on transcript content
    and returns potential matches with metadata.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize YouTube matcher.
        
        Args:
            api_key: YouTube Data API key (if not provided, uses YOUTUBE_API_KEY env var)
        """
        if not YOUTUBE_API_AVAILABLE:
            raise RuntimeError("YouTube API client not available. Install google-api-python-client")
        
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY")
        
        if not self.api_key:
            logger.warning("YouTube API key not configured. Matching will not be available.")
            self.youtube = None
        else:
            try:
                self.youtube = build('youtube', 'v3', developerKey=self.api_key)
                logger.info("YouTube API client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize YouTube API client: {e}")
                self.youtube = None

    def extract_search_query_from_transcript(self, text: str, max_length: int = 100) -> str:
        """
        Extract a good search query from transcript text.
        
        Args:
            text: Transcript text
            max_length: Maximum query length
            
        Returns:
            Search query string
        """
        if not text:
            return ""
        
        # Take first few sentences or first paragraph
        sentences = text.split('.')[:3]  # First 3 sentences
        query = '. '.join(sentences).strip()
        
        # Clean up
        query = re.sub(r'\s+', ' ', query)  # Normalize whitespace
        query = re.sub(r'[^\w\s\.]', '', query)  # Remove special chars except periods
        
        # Truncate if too long
        if len(query) > max_length:
            query = query[:max_length].rsplit(' ', 1)[0]  # Cut at word boundary
        
        return query

    def search_youtube(self, request: YouTubeSearchRequest) -> YouTubeSearchResponse:
        """
        Search YouTube for videos matching the query.
        
        Args:
            request: YouTubeSearchRequest with query and max_results
            
        Returns:
            YouTubeSearchResponse with matches
        """
        if not self.youtube:
            logger.error("YouTube API client not initialized")
            return YouTubeSearchResponse(matches=[], query=request.query)
        
        logger.info(f"Searching YouTube for: '{request.query[:50]}...' (max {request.max_results} results)")
        
        try:
            # Search for videos
            search_response = self.youtube.search().list(
                q=request.query,
                part='id,snippet',
                maxResults=request.max_results,
                type='video',
                relevanceLanguage='en',
            ).execute()
            
            video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
            
            if not video_ids:
                logger.info("No YouTube matches found")
                return YouTubeSearchResponse(matches=[], query=request.query)
            
            # Get detailed video information (including duration)
            videos_response = self.youtube.videos().list(
                part='snippet,contentDetails',
                id=','.join(video_ids)
            ).execute()
            
            matches = []
            for video in videos_response.get('items', []):
                try:
                    video_id = video['id']
                    snippet = video['snippet']
                    content_details = video['contentDetails']
                    
                    # Parse duration (ISO 8601 format: PT1H2M10S)
                    duration_seconds = self._parse_duration(content_details.get('duration', 'PT0S'))
                    
                    # Format upload date
                    upload_date = snippet.get('publishedAt', '')
                    
                    # Get best thumbnail
                    thumbnails = snippet.get('thumbnails', {})
                    thumbnail_url = (
                        thumbnails.get('high', {}).get('url') or
                        thumbnails.get('medium', {}).get('url') or
                        thumbnails.get('default', {}).get('url') or
                        ''
                    )
                    
                    match = YouTubeMatch(
                        video_id=video_id,
                        title=snippet.get('title', ''),
                        channel_name=snippet.get('channelTitle', ''),
                        channel_id=snippet.get('channelId', ''),
                        thumbnail_url=thumbnail_url,
                        duration_seconds=duration_seconds,
                        upload_date=upload_date,
                        description=snippet.get('description', '')
                    )
                    matches.append(match)
                
                except Exception as e:
                    logger.warning(f"Failed to parse video {video.get('id')}: {e}")
                    continue
            
            logger.info(f"Found {len(matches)} YouTube matches")
            
            return YouTubeSearchResponse(
                matches=matches,
                query=request.query
            )
        
        except HttpError as e:
            logger.error(f"YouTube API error: {e}")
            if e.resp.status == 403:
                logger.error("YouTube API quota exceeded or invalid API key")
            return YouTubeSearchResponse(matches=[], query=request.query)
        
        except Exception as e:
            logger.error(f"Failed to search YouTube: {e}")
            return YouTubeSearchResponse(matches=[], query=request.query)

    def _parse_duration(self, duration_str: str) -> int:
        """
        Parse ISO 8601 duration to seconds.
        
        Args:
            duration_str: Duration string (e.g., "PT1H2M10S")
            
        Returns:
            Duration in seconds
        """
        try:
            # Parse PT1H2M10S format
            hours = 0
            minutes = 0
            seconds = 0
            
            # Extract hours
            hours_match = re.search(r'(\d+)H', duration_str)
            if hours_match:
                hours = int(hours_match.group(1))
            
            # Extract minutes
            minutes_match = re.search(r'(\d+)M', duration_str)
            if minutes_match:
                minutes = int(minutes_match.group(1))
            
            # Extract seconds
            seconds_match = re.search(r'(\d+)S', duration_str)
            if seconds_match:
                seconds = int(seconds_match.group(1))
            
            return hours * 3600 + minutes * 60 + seconds
        
        except Exception as e:
            logger.warning(f"Failed to parse duration '{duration_str}': {e}")
            return 0


# Global instance (lazy initialization)
_youtube_matcher: Optional[YouTubeMatcher] = None


def get_youtube_matcher() -> Optional[YouTubeMatcher]:
    """Get or create YouTube matcher instance."""
    global _youtube_matcher
    
    if not YOUTUBE_API_AVAILABLE:
        return None
    
    if _youtube_matcher is None:
        try:
            _youtube_matcher = YouTubeMatcher()
        except Exception as e:
            logger.error(f"Failed to create YouTube matcher: {e}")
            return None
    
    return _youtube_matcher

