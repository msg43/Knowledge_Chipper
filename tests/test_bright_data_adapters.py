"""
Tests for Bright Data JSON response adapters.

Tests compatibility between Bright Data responses and existing YouTubeMetadata/YouTubeTranscript models.
"""

from datetime import datetime

import pytest

from knowledge_system.processors.youtube_metadata import YouTubeMetadata
from knowledge_system.processors.youtube_transcript import YouTubeTranscript
from knowledge_system.utils.bright_data_adapters import (
    BrightDataAdapter,
    adapt_bright_data_metadata,
    adapt_bright_data_transcript,
    validate_bright_data_response,
)


class TestBrightDataAdapter:
    """Test BrightDataAdapter class."""

    def test_adapt_metadata_response_complete(self):
        """Test complete metadata adaptation."""
        # Mock Bright Data YouTube API response
        bright_data_response = {
            "id": "dQw4w9WgXcQ",
            "title": "Rick Astley - Never Gonna Give You Up (Official Video)",
            "description": "The official video for Rick Astley's hit song",
            "videoDetails": {
                "lengthSeconds": "212",
                "viewCount": "1234567890",
                "author": "Rick Astley",
                "channelId": "UCuAXFkgsw1L7xaCfnd5JJOw",
            },
            "statistics": {
                "viewCount": "1234567890",
                "likeCount": "9876543",
                "commentCount": "123456",
            },
            "snippet": {
                "publishedAt": "2009-10-25T00:00:00Z",
                "channelTitle": "Rick Astley",
                "tags": ["rick astley", "never gonna give you up", "80s"],
                "categoryId": "10",
                "thumbnails": {
                    "high": {"url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg"}
                },
            },
        }

        url = "https://youtube.com/watch?v=dQw4w9WgXcQ"

        # Adapt the response
        metadata = BrightDataAdapter.adapt_metadata_response(bright_data_response, url)

        # Verify adaptation
        assert isinstance(metadata, YouTubeMetadata)
        assert metadata.video_id == "dQw4w9WgXcQ"
        assert (
            metadata.title == "Rick Astley - Never Gonna Give You Up (Official Video)"
        )
        assert metadata.url == url
        assert metadata.description == "The official video for Rick Astley's hit song"
        assert metadata.duration == 212
        assert metadata.view_count == 1234567890
        assert metadata.like_count == 9876543
        assert metadata.comment_count == 123456
        assert metadata.uploader == "Rick Astley"
        assert metadata.uploader_id == "UCuAXFkgsw1L7xaCfnd5JJOw"
        assert metadata.upload_date == "20091025"
        assert "rick astley" in metadata.tags
        assert (
            metadata.thumbnail_url == "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg"
        )
        assert metadata.extraction_method == "bright_data_api_scraper"

    def test_adapt_metadata_response_minimal(self):
        """Test metadata adaptation with minimal data."""
        bright_data_response = {"title": "Test Video"}

        url = "https://youtube.com/watch?v=test123"

        metadata = BrightDataAdapter.adapt_metadata_response(bright_data_response, url)

        assert isinstance(metadata, YouTubeMetadata)
        assert metadata.video_id == "test123"
        assert metadata.title == "Test Video"
        assert metadata.url == url
        assert metadata.extraction_method == "bright_data_api_scraper"

    def test_adapt_transcript_response_complete(self):
        """Test complete transcript adaptation."""
        bright_data_response = {
            "id": "dQw4w9WgXcQ",
            "title": "Rick Astley - Never Gonna Give You Up",
            "transcript": [
                {"start": 0.0, "text": "We're no strangers to love"},
                {"start": 3.2, "text": "You know the rules and so do I"},
                {"start": 6.1, "text": "A full commitment's what I'm thinking of"},
            ],
            "videoDetails": {"lengthSeconds": "212", "author": "Rick Astley"},
            "snippet": {"publishedAt": "2009-10-25T00:00:00Z"},
            "is_manual": True,
        }

        url = "https://youtube.com/watch?v=dQw4w9WgXcQ"

        transcript = BrightDataAdapter.adapt_transcript_response(
            bright_data_response, url, "en"
        )

        assert isinstance(transcript, YouTubeTranscript)
        assert transcript.video_id == "dQw4w9WgXcQ"
        assert transcript.title == "Rick Astley - Never Gonna Give You Up"
        assert transcript.url == url
        assert transcript.language == "en"
        assert transcript.is_manual == True
        assert "We're no strangers to love" in transcript.transcript_text
        assert len(transcript.transcript_data) == 3
        assert transcript.duration == 212
        assert transcript.uploader == "Rick Astley"
        assert transcript.upload_date == "20091025"

    def test_adapt_transcript_response_minimal(self):
        """Test transcript adaptation with minimal data."""
        bright_data_response = {"title": "Test Video", "transcript": []}

        url = "https://youtube.com/watch?v=test123"

        transcript = BrightDataAdapter.adapt_transcript_response(
            bright_data_response, url
        )

        assert isinstance(transcript, YouTubeTranscript)
        assert transcript.video_id == "test123"
        assert transcript.title == "Test Video"
        assert transcript.url == url
        assert transcript.language == "en"
        assert transcript.transcript_text == ""
        assert transcript.transcript_data == []

    def test_validate_bright_data_response_valid(self):
        """Test validation of valid Bright Data response."""
        valid_responses = [
            {"title": "Test Video", "id": "test123"},
            {"videoId": "test123", "snippet": {"title": "Test"}},
            {"brightdata": True, "data": {}},
            {"scraper": "youtube", "result": {}},
        ]

        for response in valid_responses:
            assert BrightDataAdapter.validate_bright_data_response(response) == True

    def test_validate_bright_data_response_invalid(self):
        """Test validation of invalid responses."""
        invalid_responses = [{}, {"random": "data"}, None, "not a dict", []]

        for response in invalid_responses:
            assert BrightDataAdapter.validate_bright_data_response(response) == False

    def test_extract_video_id_from_url(self):
        """Test video ID extraction from various URL formats."""
        test_cases = [
            ("https://youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://youtube.com/watch?v=dQw4w9WgXcQ&t=10s", "dQw4w9WgXcQ"),
            ("https://youtu.be/dQw4w9WgXcQ?t=10", "dQw4w9WgXcQ"),
        ]

        for url, expected_id in test_cases:
            video_id = BrightDataAdapter._extract_video_id(url, {})
            assert video_id == expected_id

    def test_extract_video_id_from_response(self):
        """Test video ID extraction from response data."""
        test_cases = [
            ({"id": "test123"}, "test123"),
            ({"videoId": "test456"}, "test456"),
            ({"video_id": "test789"}, "test789"),
        ]

        for response, expected_id in test_cases:
            video_id = BrightDataAdapter._extract_video_id(
                "https://youtube.com/watch?v=fallback", response
            )
            assert video_id == expected_id

    def test_parse_duration_string(self):
        """Test duration string parsing."""
        test_cases = [
            ("212", 212),
            ("PT3M32S", 212),
            ("PT1H2M3S", 3723),
            ("PT45S", 45),
            ("PT2M", 120),
            ("PT1H", 3600),
            ("invalid", None),
        ]

        for duration_str, expected in test_cases:
            result = BrightDataAdapter._parse_duration_string(duration_str)
            assert result == expected

    def test_parse_date_string(self):
        """Test date string parsing."""
        test_cases = [
            ("2009-10-25T00:00:00Z", "20091025"),
            ("2009-10-25", "20091025"),
            ("2009/10/25", "20091025"),
            ("20091025", "20091025"),
            ("invalid", None),
        ]

        for date_str, expected in test_cases:
            result = BrightDataAdapter._parse_date_string(date_str)
            assert result == expected

    def test_get_nested_field(self):
        """Test nested field extraction."""
        data = {"level1": {"level2": {"value": "found"}}, "simple": "value"}

        assert BrightDataAdapter._get_nested_field(data, "simple") == "value"
        assert (
            BrightDataAdapter._get_nested_field(data, "level1.level2.value") == "found"
        )
        assert BrightDataAdapter._get_nested_field(data, "nonexistent") is None
        assert BrightDataAdapter._get_nested_field(data, "level1.nonexistent") is None

    def test_fallback_creation(self):
        """Test fallback metadata and transcript creation."""
        url = "https://youtube.com/watch?v=test123"
        response = {"title": "Test Title"}

        # Test fallback metadata
        metadata = BrightDataAdapter._create_fallback_metadata(url, response)
        assert isinstance(metadata, YouTubeMetadata)
        assert metadata.video_id == "test123"
        assert metadata.title == "Test Title"
        assert metadata.extraction_method == "bright_data_api_scraper_fallback"

        # Test fallback transcript
        transcript = BrightDataAdapter._create_fallback_transcript(url, response)
        assert isinstance(transcript, YouTubeTranscript)
        assert transcript.video_id == "test123"
        assert transcript.title == "Test Title"
        assert transcript.transcript_text == ""

    def test_convenience_functions(self):
        """Test convenience functions."""
        response = {"title": "Test Video"}
        url = "https://youtube.com/watch?v=test123"

        # Test convenience functions work
        metadata = adapt_bright_data_metadata(response, url)
        assert isinstance(metadata, YouTubeMetadata)

        transcript = adapt_bright_data_transcript(response, url)
        assert isinstance(transcript, YouTubeTranscript)

        valid = validate_bright_data_response(response)
        assert valid == True

    def test_error_handling(self):
        """Test error handling with malformed data."""
        # Test with completely invalid data
        invalid_response = {"corrupted": None}
        url = "invalid_url"

        # Should not raise exceptions, should return fallback objects
        metadata = BrightDataAdapter.adapt_metadata_response(
            invalid_response, "https://youtube.com/watch?v=test123"
        )
        assert isinstance(metadata, YouTubeMetadata)

        transcript = BrightDataAdapter.adapt_transcript_response(
            invalid_response, "https://youtube.com/watch?v=test123"
        )
        assert isinstance(transcript, YouTubeTranscript)
