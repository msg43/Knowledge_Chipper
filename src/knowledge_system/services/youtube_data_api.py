"""
YouTube Data API v3 Service

Official YouTube API wrapper for fetching video metadata.
Provides clean, validated metadata with quota tracking and batch optimization.
"""

import re
import time
from datetime import datetime, timedelta
from typing import Any, Optional
from urllib.parse import urlencode

import requests

from ..logger import get_logger

logger = get_logger(__name__)


class YouTubeDataAPIError(Exception):
    """YouTube Data API error."""
    pass


class QuotaExceededError(YouTubeDataAPIError):
    """API quota exceeded error."""
    pass


class YouTubeDataAPI:
    """
    YouTube Data API v3 wrapper.
    
    Features:
    - Single and batch video metadata fetching
    - Quota tracking and management
    - Automatic retry with exponential backoff
    - Clean, validated output matching database schema
    - Category ID to name mapping
    """
    
    BASE_URL = "https://www.googleapis.com/youtube/v3"
    
    # YouTube category ID to name mapping (common categories)
    CATEGORY_MAP = {
        "1": "Film & Animation",
        "2": "Autos & Vehicles",
        "10": "Music",
        "15": "Pets & Animals",
        "17": "Sports",
        "19": "Travel & Events",
        "20": "Gaming",
        "22": "People & Blogs",
        "23": "Comedy",
        "24": "Entertainment",
        "25": "News & Politics",
        "26": "Howto & Style",
        "27": "Education",
        "28": "Science & Technology",
        "29": "Nonprofits & Activism",
    }
    
    def __init__(
        self,
        api_key: str,
        quota_limit: int = 10000,
        batch_size: int = 50
    ):
        """
        Initialize YouTube Data API service.
        
        Args:
            api_key: YouTube Data API v3 key
            quota_limit: Daily quota limit (default: 10,000)
            batch_size: Videos per batch request (max: 50)
        """
        self.api_key = api_key
        self.quota_limit = quota_limit
        self.batch_size = min(batch_size, 50)  # API max is 50
        
        # Quota tracking
        self.quota_used = 0
        self.quota_reset_time = datetime.now() + timedelta(days=1)
        
        # Validate API key on initialization
        if not self.validate_api_key():
            logger.warning("YouTube Data API key validation failed")
    
    def validate_api_key(self) -> bool:
        """
        Validate that API key is working.
        
        Returns:
            True if key is valid, False otherwise
        """
        try:
            # Try a simple request
            url = f"{self.BASE_URL}/videos"
            params = {
                "key": self.api_key,
                "part": "id",
                "id": "dQw4w9WgXcQ",  # Test with a known video
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                logger.info("✅ YouTube Data API key validated successfully")
                return True
            elif response.status_code == 403:
                logger.error("❌ YouTube Data API key is invalid or disabled")
                return False
            else:
                logger.warning(f"⚠️ API validation returned status {response.status_code}")
                return False
        
        except Exception as e:
            logger.error(f"Failed to validate API key: {e}")
            return False
    
    def fetch_video_metadata(self, video_id: str) -> dict[str, Any] | None:
        """
        Fetch metadata for a single video.
        
        Costs: 1 quota unit
        
        Args:
            video_id: YouTube video ID (11 characters)
        
        Returns:
            Metadata dict or None if not found
        """
        if not video_id or len(video_id) != 11:
            logger.error(f"Invalid video ID: {video_id}")
            return None
        
        try:
            # Check quota
            if not self._check_quota(1):
                raise QuotaExceededError("Daily quota limit exceeded")
            
            # Make API request
            url = f"{self.BASE_URL}/videos"
            params = {
                "key": self.api_key,
                "part": "snippet,contentDetails,statistics",
                "id": video_id,
            }
            
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code == 403:
                error_data = response.json()
                if "quotaExceeded" in str(error_data):
                    raise QuotaExceededError("API quota exceeded")
                else:
                    raise YouTubeDataAPIError(f"API error: {error_data}")
            
            response.raise_for_status()
            data = response.json()
            
            # Update quota
            self._increment_quota(1)
            
            # Parse response
            if not data.get("items"):
                logger.warning(f"Video not found: {video_id}")
                return None
            
            item = data["items"][0]
            metadata = self._convert_to_database_format(item)
            
            logger.info(f"✅ Fetched metadata for: {metadata['title'][:50]}...")
            
            return metadata
        
        except QuotaExceededError:
            raise
        except Exception as e:
            logger.error(f"Failed to fetch metadata for {video_id}: {e}")
            return None
    
    def fetch_videos_batch(self, video_ids: list[str]) -> dict[str, dict[str, Any]]:
        """
        Fetch metadata for multiple videos in batch.
        
        Costs: 1 quota unit per batch (up to 50 videos)
        
        Args:
            video_ids: List of video IDs (up to 50)
        
        Returns:
            Dict mapping video_id → metadata
        """
        if not video_ids:
            return {}
        
        # Validate video IDs
        valid_ids = [vid for vid in video_ids if vid and len(vid) == 11]
        if len(valid_ids) != len(video_ids):
            logger.warning(f"Filtered out {len(video_ids) - len(valid_ids)} invalid video IDs")
        
        results = {}
        
        # Process in batches of batch_size
        for i in range(0, len(valid_ids), self.batch_size):
            batch = valid_ids[i:i + self.batch_size]
            batch_results = self._fetch_batch(batch)
            results.update(batch_results)
        
        return results
    
    def _fetch_batch(self, video_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Fetch a single batch of videos."""
        try:
            # Check quota
            if not self._check_quota(1):
                raise QuotaExceededError("Daily quota limit exceeded")
            
            # Make API request
            url = f"{self.BASE_URL}/videos"
            params = {
                "key": self.api_key,
                "part": "snippet,contentDetails,statistics",
                "id": ",".join(video_ids),
            }
            
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code == 403:
                error_data = response.json()
                if "quotaExceeded" in str(error_data):
                    raise QuotaExceededError("API quota exceeded")
                else:
                    raise YouTubeDataAPIError(f"API error: {error_data}")
            
            response.raise_for_status()
            data = response.json()
            
            # Update quota
            self._increment_quota(1)
            
            # Parse response
            results = {}
            for item in data.get("items", []):
                video_id = item["id"]
                metadata = self._convert_to_database_format(item)
                results[video_id] = metadata
            
            logger.info(f"✅ Fetched metadata for {len(results)} videos (batch)")
            
            return results
        
        except QuotaExceededError:
            raise
        except Exception as e:
            logger.error(f"Failed to fetch batch metadata: {e}")
            return {}
    
    def _convert_to_database_format(self, item: dict) -> dict[str, Any]:
        """
        Convert API response to database schema format.
        
        Args:
            item: Single video item from API response
        
        Returns:
            Dict matching MediaSource schema
        """
        snippet = item.get("snippet", {})
        content_details = item.get("contentDetails", {})
        statistics = item.get("statistics", {})
        
        # Extract and convert fields
        metadata = {
            "source_id": item["id"],
            "title": snippet.get("title", "Unknown Title"),
            "description": snippet.get("description", ""),
            "uploader": snippet.get("channelTitle", ""),
            "uploader_id": snippet.get("channelId", ""),
            "upload_date": self._convert_date(snippet.get("publishedAt", "")),
            "duration_seconds": self._convert_duration(content_details.get("duration", "")),
            "view_count": self._safe_int(statistics.get("viewCount")),
            "like_count": self._safe_int(statistics.get("likeCount")),
            "comment_count": self._safe_int(statistics.get("commentCount")),
            "tags_json": snippet.get("tags", []),
            "categories_json": self._convert_categories(snippet.get("categoryId")),
            "thumbnail_url": self._get_best_thumbnail(snippet.get("thumbnails", {})),
            "language": snippet.get("defaultAudioLanguage") or snippet.get("defaultLanguage", "en"),
            "caption_availability": content_details.get("caption", "false") == "true",
            "privacy_status": item.get("status", {}).get("privacyStatus", "public"),
        }
        
        return metadata
    
    def _convert_duration(self, iso_duration: str) -> int | None:
        """
        Convert ISO 8601 duration to seconds.
        
        Examples:
            PT4M33S → 273
            PT1H2M10S → 3730
            PT15S → 15
        """
        if not iso_duration:
            return None
        
        try:
            # Parse ISO 8601 duration (PT#H#M#S)
            pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
            match = re.match(pattern, iso_duration)
            
            if not match:
                return None
            
            hours = int(match.group(1) or 0)
            minutes = int(match.group(2) or 0)
            seconds = int(match.group(3) or 0)
            
            return hours * 3600 + minutes * 60 + seconds
        
        except Exception as e:
            logger.warning(f"Failed to parse duration '{iso_duration}': {e}")
            return None
    
    def _convert_date(self, iso_date: str) -> str:
        """
        Convert ISO 8601 date to YYYYMMDD format for database.
        
        Args:
            iso_date: ISO 8601 date (2024-01-15T10:30:00Z)
        
        Returns:
            YYYYMMDD format (20240115)
        """
        if not iso_date:
            return ""
        
        try:
            # Parse ISO 8601 and convert to YYYYMMDD
            dt = datetime.fromisoformat(iso_date.replace('Z', '+00:00'))
            return dt.strftime("%Y%m%d")
        except Exception as e:
            logger.warning(f"Failed to parse date '{iso_date}': {e}")
            return ""
    
    def _convert_categories(self, category_id: str) -> list[str]:
        """Convert category ID to category name."""
        if not category_id:
            return []
        
        category_name = self.CATEGORY_MAP.get(category_id, f"Category {category_id}")
        return [category_name]
    
    def _get_best_thumbnail(self, thumbnails: dict) -> str:
        """Get best quality thumbnail URL."""
        # Try in order of quality
        for quality in ["maxres", "standard", "high", "medium", "default"]:
            if quality in thumbnails:
                return thumbnails[quality].get("url", "")
        return ""
    
    def _safe_int(self, value: Any) -> int | None:
        """Safely convert value to integer."""
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
    
    def _check_quota(self, units: int) -> bool:
        """
        Check if we have enough quota remaining.
        
        Args:
            units: Quota units needed
        
        Returns:
            True if quota available, False otherwise
        """
        # Reset quota if new day
        if datetime.now() >= self.quota_reset_time:
            self.quota_used = 0
            self.quota_reset_time = datetime.now() + timedelta(days=1)
            logger.info("📊 Quota reset for new day")
        
        if self.quota_used + units > self.quota_limit:
            logger.warning(
                f"⚠️ Quota limit reached: {self.quota_used}/{self.quota_limit} units used"
            )
            return False
        
        return True
    
    def _increment_quota(self, units: int) -> None:
        """Increment quota usage counter."""
        self.quota_used += units
        remaining = self.quota_limit - self.quota_used
        
        if remaining < 1000:
            logger.warning(
                f"⚠️ Low quota remaining: {remaining}/{self.quota_limit} units"
            )
        else:
            logger.debug(f"📊 Quota used: {self.quota_used}/{self.quota_limit} units")
    
    def get_quota_usage(self) -> dict[str, Any]:
        """
        Get current quota usage statistics.
        
        Returns:
            Dict with used, remaining, limit, reset_time
        """
        remaining = self.quota_limit - self.quota_used
        
        return {
            "used": self.quota_used,
            "remaining": remaining,
            "limit": self.quota_limit,
            "reset_time": self.quota_reset_time.isoformat(),
            "percentage_used": (self.quota_used / self.quota_limit) * 100,
        }
    
    def search_videos(
        self,
        query: str,
        max_results: int = 10
    ) -> list[dict[str, Any]]:
        """
        Search for videos by query.
        
        Costs: 100 quota units per request
        
        Args:
            query: Search query
            max_results: Maximum results to return (default: 10)
        
        Returns:
            List of video metadata dicts
        """
        try:
            # Check quota (search is expensive: 100 units)
            if not self._check_quota(100):
                raise QuotaExceededError("Not enough quota for search (requires 100 units)")
            
            # Make search request
            url = f"{self.BASE_URL}/search"
            params = {
                "key": self.api_key,
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": min(max_results, 50),
            }
            
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            # Update quota
            self._increment_quota(100)
            
            # Extract video IDs
            video_ids = [item["id"]["videoId"] for item in data.get("items", [])]
            
            if not video_ids:
                return []
            
            # Fetch full metadata for these videos (1 more quota unit)
            metadata_dict = self.fetch_videos_batch(video_ids)
            
            return list(metadata_dict.values())
        
        except QuotaExceededError:
            raise
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

