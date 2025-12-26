"""
Tests for YouTube metadata validator.
"""

import pytest

from src.knowledge_system.utils.youtube_metadata_validator import (
    validate_and_clean_metadata,
    validate_source_id,
    MetadataValidationError,
    _sanitize_string,
    _safe_int,
    _convert_date_to_yyyymmdd,
)


class TestMetadataValidator:
    """Test metadata validation."""
    
    def test_validate_api_metadata(self):
        """Test validation of YouTube API metadata."""
        api_metadata = {
            "source_id": "dQw4w9WgXcQ",
            "title": "Test Video",
            "description": "Test description",
            "uploader": "Test Channel",
            "uploader_id": "UC123",
            "upload_date": "20240115",
            "duration_seconds": 273,
            "view_count": 1000000,
            "like_count": 50000,
            "comment_count": 1000,
            "tags_json": ["test", "video"],
            "categories_json": ["Science & Technology"],
            "thumbnail_url": "https://example.com/thumb.jpg",
            "language": "en",
            "caption_availability": True,
            "privacy_status": "public",
        }
        
        cleaned = validate_and_clean_metadata(api_metadata, source="youtube_api")
        
        assert cleaned["source_id"] == "dQw4w9WgXcQ"
        assert cleaned["title"] == "Test Video"
        assert cleaned["duration_seconds"] == 273
        assert cleaned["view_count"] == 1000000
        assert isinstance(cleaned["tags_json"], list)
    
    def test_validate_ytdlp_metadata(self):
        """Test validation of yt-dlp metadata."""
        ytdlp_metadata = {
            "title": "Test Video",
            "description": "Test description",
            "uploader": "Test Channel",
            "channel_id": "UC123",
            "upload_date": "20240115",
            "duration": 273,
            "view_count": 1000000,
            "like_count": 50000,
            "comment_count": 1000,
            "tags": ["test", "video"],
            "categories": ["Science & Technology"],
            "thumbnail": "https://example.com/thumb.jpg",
        }
        
        cleaned = validate_and_clean_metadata(ytdlp_metadata, source="ytdlp")
        
        assert cleaned["title"] == "Test Video"
        assert cleaned["duration_seconds"] == 273
        assert cleaned["view_count"] == 1000000
        assert isinstance(cleaned["tags_json"], list)
        assert cleaned["uploader_id"] == "UC123"  # Mapped from channel_id
    
    def test_validate_ytdlp_with_missing_fields(self):
        """Test yt-dlp validation with missing fields."""
        ytdlp_metadata = {
            "title": "Test Video",
            # Missing most fields
        }
        
        cleaned = validate_and_clean_metadata(ytdlp_metadata, source="ytdlp")
        
        # Should have defaults
        assert cleaned["title"] == "Test Video"
        assert cleaned["description"] == ""
        assert cleaned["uploader"] == ""
        assert cleaned["duration_seconds"] is None
        assert cleaned["tags_json"] == []
        assert cleaned["categories_json"] == []
    
    def test_validate_api_metadata_missing_source_id(self):
        """Test API validation with missing source_id."""
        api_metadata = {
            "title": "Test Video",
            # Missing source_id
        }
        
        with pytest.raises(MetadataValidationError):
            validate_and_clean_metadata(api_metadata, source="youtube_api")
    
    def test_sanitize_string(self):
        """Test string sanitization."""
        # Long string
        long_str = "a" * 1000
        result = _sanitize_string(long_str, max_length=100)
        assert len(result) == 100
        assert result.endswith("...")
        
        # Control characters
        dirty_str = "Test\x00\x01\x02Video"
        result = _sanitize_string(dirty_str)
        assert result == "TestVideo"
        
        # Whitespace
        result = _sanitize_string("  Test  ")
        assert result == "Test"
    
    def test_safe_int(self):
        """Test safe integer conversion."""
        assert _safe_int("12345") == 12345
        assert _safe_int(12345) == 12345
        assert _safe_int(None) is None
        assert _safe_int("invalid") is None
        assert _safe_int(12.7) == 12
    
    def test_convert_date_to_yyyymmdd(self):
        """Test date format conversion."""
        # ISO 8601
        assert _convert_date_to_yyyymmdd("2024-01-15T10:30:00Z") == "20240115"
        
        # YYYY-MM-DD
        assert _convert_date_to_yyyymmdd("2024-01-15") == "20240115"
        
        # Already YYYYMMDD
        assert _convert_date_to_yyyymmdd("20240115") == "20240115"
        
        # Empty
        assert _convert_date_to_yyyymmdd("") == ""
    
    def test_validate_source_id(self):
        """Test video ID validation."""
        # Valid IDs
        assert validate_source_id("dQw4w9WgXcQ") is True
        assert validate_source_id("_-aAbBcC123") is True
        
        # Invalid IDs
        assert validate_source_id("") is False
        assert validate_source_id("short") is False
        assert validate_source_id("toolongvideoid") is False
        assert validate_source_id("invalid@char") is False


class TestAudioLinking:
    """Test audio linking functionality."""
    
    @patch('src.knowledge_system.database.service.DatabaseService')
    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.stat')
    def test_link_audio_to_source_success(self, mock_stat, mock_exists, mock_db):
        """Test successful audio linking."""
        from src.knowledge_system.database.service import DatabaseService
        
        # Setup mocks
        mock_exists.return_value = True
        mock_stat.return_value = Mock(st_size=1024 * 1024)  # 1 MB
        
        mock_source = Mock()
        mock_source.source_id = "test_id"
        
        mock_db_instance = mock_db.return_value
        mock_db_instance.get_source.return_value = mock_source
        mock_db_instance.update_audio_status.return_value = True
        
        # Test
        db = DatabaseService()
        result = db.link_audio_to_source(
            source_id="test_id",
            audio_file_path="/path/to/audio.mp3"
        )
        
        # Should succeed
        assert result is True
    
    @patch('src.knowledge_system.database.service.DatabaseService')
    @patch('pathlib.Path.exists')
    def test_link_audio_file_not_found(self, mock_exists, mock_db):
        """Test audio linking when file doesn't exist."""
        from src.knowledge_system.database.service import DatabaseService
        
        mock_exists.return_value = False
        
        db = DatabaseService()
        result = db.link_audio_to_source(
            source_id="test_id",
            audio_file_path="/path/to/missing.mp3"
        )
        
        # Should fail
        assert result is False
    
    @patch('src.knowledge_system.database.service.DatabaseService')
    def test_verify_audio_metadata_link_valid(self, mock_db):
        """Test audio link verification when valid."""
        from src.knowledge_system.database.service import DatabaseService
        from pathlib import Path
        
        # Create temp file for testing
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
            f.write(b"0" * (1024 * 1024))  # 1 MB
            temp_path = f.name
        
        try:
            mock_source = Mock()
            mock_source.source_id = "test_id"
            mock_source.audio_file_path = temp_path
            mock_source.audio_downloaded = True
            mock_source.audio_file_size_bytes = 1024 * 1024
            mock_source.audio_format = "mp3"
            mock_source.metadata_complete = True
            
            mock_db_instance = mock_db.return_value
            mock_db_instance.get_source.return_value = mock_source
            
            db = DatabaseService()
            result = db.verify_audio_metadata_link("test_id")
            
            assert result["valid"] is True
            assert len(result["issues"]) == 0
        
        finally:
            Path(temp_path).unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

