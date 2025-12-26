"""
Tests for YouTube Data API v3 service.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.knowledge_system.services.youtube_data_api import (
    YouTubeDataAPI,
    QuotaExceededError,
    YouTubeDataAPIError
)


class TestYouTubeDataAPI:
    """Test YouTube Data API service."""
    
    def test_init(self):
        """Test API initialization."""
        api = YouTubeDataAPI(api_key="test_key", quota_limit=10000)
        
        assert api.api_key == "test_key"
        assert api.quota_limit == 10000
        assert api.batch_size == 50
        assert api.quota_used == 0
    
    def test_convert_duration_simple(self):
        """Test ISO 8601 duration conversion."""
        api = YouTubeDataAPI(api_key="test_key")
        
        # PT4M33S → 273 seconds
        assert api._convert_duration("PT4M33S") == 273
        
        # PT15S → 15 seconds
        assert api._convert_duration("PT15S") == 15
        
        # PT1H2M10S → 3730 seconds
        assert api._convert_duration("PT1H2M10S") == 3730
    
    def test_convert_duration_edge_cases(self):
        """Test duration conversion edge cases."""
        api = YouTubeDataAPI(api_key="test_key")
        
        # Empty string
        assert api._convert_duration("") is None
        
        # Invalid format
        assert api._convert_duration("invalid") is None
        
        # Only hours
        assert api._convert_duration("PT2H") == 7200
        
        # Only minutes
        assert api._convert_duration("PT30M") == 1800
    
    def test_convert_date(self):
        """Test ISO 8601 date conversion to YYYYMMDD."""
        api = YouTubeDataAPI(api_key="test_key")
        
        # ISO 8601 with time
        assert api._convert_date("2024-01-15T10:30:00Z") == "20240115"
        
        # ISO 8601 without time
        assert api._convert_date("2024-01-15") == "20240115"
        
        # Empty string
        assert api._convert_date("") == ""
    
    def test_convert_categories(self):
        """Test category ID to name conversion."""
        api = YouTubeDataAPI(api_key="test_key")
        
        # Known category
        assert api._convert_categories("28") == ["Science & Technology"]
        
        # Unknown category
        assert api._convert_categories("999") == ["Category 999"]
        
        # Empty
        assert api._convert_categories("") == []
    
    def test_safe_int(self):
        """Test safe integer conversion."""
        api = YouTubeDataAPI(api_key="test_key")
        
        # String number
        assert api._safe_int("12345") == 12345
        
        # Integer
        assert api._safe_int(12345) == 12345
        
        # None
        assert api._safe_int(None) is None
        
        # Invalid
        assert api._safe_int("invalid") is None
    
    def test_check_quota(self):
        """Test quota checking."""
        api = YouTubeDataAPI(api_key="test_key", quota_limit=100)
        
        # Should have quota
        assert api._check_quota(50) is True
        
        # Use some quota
        api.quota_used = 90
        
        # Should not have enough
        assert api._check_quota(20) is False
        
        # Should have enough for smaller request
        assert api._check_quota(5) is True
    
    def test_get_quota_usage(self):
        """Test quota usage reporting."""
        api = YouTubeDataAPI(api_key="test_key", quota_limit=10000)
        api.quota_used = 2500
        
        usage = api.get_quota_usage()
        
        assert usage["used"] == 2500
        assert usage["remaining"] == 7500
        assert usage["limit"] == 10000
        assert usage["percentage_used"] == 25.0
    
    @patch('src.knowledge_system.services.youtube_data_api.requests.get')
    def test_fetch_video_metadata_success(self, mock_get):
        """Test successful video metadata fetch."""
        # Mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [{
                "id": "dQw4w9WgXcQ",
                "snippet": {
                    "title": "Test Video",
                    "description": "Test description",
                    "channelTitle": "Test Channel",
                    "channelId": "UC123",
                    "publishedAt": "2024-01-15T10:30:00Z",
                    "tags": ["test", "video"],
                    "categoryId": "28",
                    "thumbnails": {
                        "high": {"url": "https://example.com/thumb.jpg"}
                    }
                },
                "contentDetails": {
                    "duration": "PT4M33S",
                    "caption": "true"
                },
                "statistics": {
                    "viewCount": "1000000",
                    "likeCount": "50000",
                    "commentCount": "1000"
                },
                "status": {
                    "privacyStatus": "public"
                }
            }]
        }
        mock_get.return_value = mock_response
        
        api = YouTubeDataAPI(api_key="test_key")
        metadata = api.fetch_video_metadata("dQw4w9WgXcQ")
        
        assert metadata is not None
        assert metadata["title"] == "Test Video"
        assert metadata["duration_seconds"] == 273
        assert metadata["view_count"] == 1000000
        assert metadata["tags_json"] == ["test", "video"]
        assert metadata["categories_json"] == ["Science & Technology"]
    
    @patch('src.knowledge_system.services.youtube_data_api.requests.get')
    def test_fetch_video_metadata_not_found(self, mock_get):
        """Test video not found."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"items": []}
        mock_get.return_value = mock_response
        
        api = YouTubeDataAPI(api_key="test_key")
        metadata = api.fetch_video_metadata("invalid_id")
        
        assert metadata is None
    
    @patch('src.knowledge_system.services.youtube_data_api.requests.get')
    def test_fetch_video_metadata_quota_exceeded(self, mock_get):
        """Test quota exceeded error."""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.json.return_value = {
            "error": {"errors": [{"reason": "quotaExceeded"}]}
        }
        mock_get.return_value = mock_response
        
        api = YouTubeDataAPI(api_key="test_key")
        
        with pytest.raises(QuotaExceededError):
            api.fetch_video_metadata("dQw4w9WgXcQ")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

