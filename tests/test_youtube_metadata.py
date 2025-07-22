"""
Tests for YouTube Metadata Processor.

Tests metadata extraction, error handling, and integration with yt-dlp.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from knowledge_system.errors import YouTubeAPIError
from knowledge_system.processors.youtube_metadata import (
    YouTubeMetadata,
    YouTubeMetadataProcessor,
    fetch_metadata,
)


class TestYouTubeMetadata:
    """Test YouTubeMetadata model."""

    def test_init_basic(self) -> None:
        """Test basic metadata initialization."""
        metadata = YouTubeMetadata(
            video_id="test123",
            title="Test Video",
            url="https://youtube.com/watch?v=test123",
        )

        assert metadata.video_id == "test123"
        assert metadata.title == "Test Video"
        assert metadata.url == "https://youtube.com/watch?v=test123"
        assert metadata.description == ""
        assert metadata.uploader == ""
        assert metadata.tags == []
        assert metadata.has_transcript is False

    def test_init_full(self) -> None:
        """Test full metadata initialization."""
        metadata = YouTubeMetadata(
            video_id="test123",
            title="Test Video",
            url="https://youtube.com/watch?v=test123",
            description="Test description",
            duration=120,
            view_count=1000,
            like_count=50,
            uploader="Test Channel",
            uploader_id="UC123",
            upload_date="20240101",
            tags=["test", "video"],
            categories=["Education"],
            thumbnail_url="https://example.com/thumb.jpg",
            resolution="1080p",
            has_transcript=True,
            transcript_languages=["en", "es"],
        )

        assert metadata.duration == 120
        assert metadata.view_count == 1000
        assert metadata.uploader == "Test Channel"
        assert metadata.tags == ["test", "video"]
        assert metadata.has_transcript is True
        assert metadata.transcript_languages == ["en", "es"]

    def test_to_dict(self) -> None:
        """Test dictionary conversion."""
        metadata = YouTubeMetadata(
            video_id="test123",
            title="Test Video",
            url="https://youtube.com/watch?v=test123",
        )

        data = metadata.to_dict()
        assert data["video_id"] == "test123"
        assert data["title"] == "Test Video"
        assert "fetched_at" in data

    def test_to_markdown_metadata(self) -> None:
        """Test markdown metadata generation."""
        metadata = YouTubeMetadata(
            video_id="test123",
            title="Test Video",
            url="https://youtube.com/watch?v=test123",
            description="Test description",
            duration=125,
            view_count=1000,
            like_count=50,
            uploader="Test Channel",
            upload_date="20240101",
            tags=["test", "video"],
            has_transcript=True,
            transcript_languages=["en"],
        )

        markdown = metadata.to_markdown_metadata()

        assert "# Metadata" in markdown
        assert "**Title**: Test Video" in markdown
        assert "**Video ID**: test123" in markdown
        assert "**Uploader**: Test Channel" in markdown
        assert "**Duration**: 2:05" in markdown
        assert "**Views**: 1,000" in markdown
        assert "**Likes**: 50" in markdown
        assert "**Has Transcript**: True" in markdown
        assert "**Transcript Languages**: en" in markdown
        assert "**Tags**: test, video" in markdown

    def test_to_markdown_metadata_minimal(self) -> None:
        """Test markdown generation with minimal data."""
        metadata = YouTubeMetadata(
            video_id="test123",
            title="Test Video",
            url="https://youtube.com/watch?v=test123",
        )

        markdown = metadata.to_markdown_metadata()

        assert "# Metadata" in markdown
        assert "**Title**: Test Video" in markdown
        assert "**Has Transcript**: False" in markdown
        assert "**Metadata Fetched**: " in markdown

    def test_description_truncation(self) -> None:
        """Test description truncation in markdown."""
        long_desc = "A" * 600
        metadata = YouTubeMetadata(
            video_id="test123",
            title="Test Video",
            url="https://youtube.com/watch?v=test123",
            description=long_desc,
        )

        markdown = metadata.to_markdown_metadata()
        assert "**Description**: " + "A" * 500 + "..." in markdown


class TestYouTubeMetadataProcessor:
    """Test YouTubeMetadataProcessor class."""

    def setup_method(self) -> None:
        """Setup for each test method."""
        self.processor = YouTubeMetadataProcessor()

    def test_init(self) -> None:
        """Test processor initialization."""
        assert self.processor.name == "youtube_metadata"
        assert ".url" in self.processor.supported_formats
        assert ".txt" in self.processor.supported_formats

    def test_supported_formats(self) -> None:
        """Test supported formats property."""
        formats = self.processor.supported_formats
        assert isinstance(formats, list)
        assert ".url" in formats
        assert ".txt" in formats

    def test_validate_input_youtube_url(self) -> None:
        """Test input validation with YouTube URL."""
        url = "https://youtube.com/watch?v=test123"
        assert self.processor.validate_input(url) is True

    def test_validate_input_youtube_playlist(self) -> None:
        """Test input validation with YouTube playlist URL."""
        url = "https://youtube.com/playlist?list=test123"
        assert self.processor.validate_input(url) is True

    def test_validate_input_youtu_be(self) -> None:
        """Test input validation with youtu.be URL."""
        url = "https://youtu.be/test123"
        assert self.processor.validate_input(url) is True

    def test_validate_input_invalid_url(self) -> None:
        """Test input validation with invalid URL."""
        url = "https://example.com/video"
        assert self.processor.validate_input(url) is False

    def test_validate_input_file_with_urls(self) -> None:
        """Test input validation with file containing URLs."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("https://youtube.com/watch?v=test123\n")
            f.write("https://youtube.com/playlist?list=test456\n")
            temp_file = f.name

        try:
            assert self.processor.validate_input(temp_file) is True
        finally:
            Path(temp_file).unlink()

    def test_validate_input_file_without_urls(self) -> None:
        """Test input validation with file without URLs."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("This is not a YouTube URL\n")
            f.write("https://example.com/video\n")
            temp_file = f.name

        try:
            assert self.processor.validate_input(temp_file) is False
        finally:
            Path(temp_file).unlink()

    def test_validate_input_nonexistent_file(self) -> None:
        """Test input validation with nonexistent file."""
        assert self.processor.validate_input("/nonexistent/file.txt") is False

    def test_validate_input_invalid_type(self) -> None:
        """Test input validation with invalid type."""
        assert self.processor.validate_input(123) is False
        assert self.processor.validate_input(None) is False

    def test_extract_urls_direct_url(self) -> None:
        """Test URL extraction from direct URL."""
        url = "https://youtube.com/watch?v=test123"
        urls = self.processor._extract_urls(url)
        assert urls == [url]

    def test_extract_urls_from_file(self) -> None:
        """Test URL extraction from file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("https://youtube.com/watch?v=test123\n")
            f.write("https://youtube.com/playlist?list=test456\n")
            f.write("https://example.com/video\n")  # Should be ignored
            temp_file = f.name

        try:
            urls = self.processor._extract_urls(temp_file)
            assert len(urls) == 2
            assert "https://youtube.com/watch?v=test123" in urls
            assert "https://youtube.com/playlist?list=test456" in urls
        finally:
            Path(temp_file).unlink()

    def test_extract_urls_file_error(self) -> None:
        """Test URL extraction with file error."""
        with pytest.raises(YouTubeAPIError, match="Cannot read file"):
            self.processor._extract_urls("/nonexistent/file.txt")

    @patch("yt_dlp.YoutubeDL")
    def test_fetch_video_metadata_success(self, mock_ydl_class) -> None:
        """Test successful video metadata fetching."""
        # Mock yt-dlp response
        mock_info = {
            "id": "test123",
            "title": "Test Video",
            "webpage_url": "https://youtube.com/watch?v=test123",
            "description": "Test description",
            "duration": 120,
            "view_count": 1000,
            "like_count": 50,
            "uploader": "Test Channel",
            "uploader_id": "UC123",
            "upload_date": "20240101",
            "tags": ["test", "video"],
            "categories": ["Education"],
            "thumbnail": "https://example.com/thumb.jpg",
            "resolution": "1080p",
            "subtitles": {"en": [{"url": "test"}]},
        }

        mock_ydl = Mock()
        mock_ydl.extract_info.return_value = mock_info
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl

        metadata = self.processor._fetch_video_metadata(
            "https://youtube.com/watch?v=test123"
        )

        assert metadata.video_id == "test123"
        assert metadata.title == "Test Video"
        assert metadata.has_transcript is True
        assert metadata.transcript_languages == ["en"]

    @patch("yt_dlp.YoutubeDL")
    def test_fetch_video_metadata_no_transcript(self, mock_ydl_class) -> None:
        """Test video metadata fetching without transcript."""
        mock_info = {
            "id": "test123",
            "title": "Test Video",
            "webpage_url": "https://youtube.com/watch?v=test123",
            "description": "",
            "uploader": "",
            "uploader_id": "",
            "tags": [],
            "categories": [],
        }

        mock_ydl = Mock()
        mock_ydl.extract_info.return_value = mock_info
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl

        metadata = self.processor._fetch_video_metadata(
            "https://youtube.com/watch?v=test123"
        )

        assert metadata.has_transcript is False
        assert metadata.transcript_languages == []

    @patch("yt_dlp.YoutubeDL")
    def test_fetch_video_metadata_automatic_captions(
        self, mock_ydl_class) -> None:
        """Test video metadata with automatic captions."""
        mock_info = {
            "id": "test123",
            "title": "Test Video",
            "webpage_url": "https://youtube.com/watch?v=test123",
            "description": "",
            "uploader": "",
            "uploader_id": "",
            "tags": [],
            "categories": [],
            "automatic_captions": {"en": [{"url": "test"}]},
        }

        mock_ydl = Mock()
        mock_ydl.extract_info.return_value = mock_info
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl

        metadata = self.processor._fetch_video_metadata(
            "https://youtube.com/watch?v=test123"
        )

        assert metadata.has_transcript is True
        assert metadata.transcript_languages == ["en"]

    @patch("yt_dlp.YoutubeDL")
    def test_fetch_video_metadata_error(self, mock_ydl_class) -> None:
        """Test video metadata fetching error."""
        mock_ydl = Mock()
        mock_ydl.extract_info.return_value = None
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl

        with pytest.raises(YouTubeAPIError, match="Could not extract info"):
            self.processor._fetch_video_metadata(
                "https://youtube.com/watch?v=test123")

    @patch("yt_dlp.YoutubeDL")
    def test_fetch_playlist_metadata_success(self, mock_ydl_class) -> None:
        """Test successful playlist metadata fetching."""
        mock_info = {
            "entries": [
                {
                    "id": "test123",
                    "title": "Test Video 1",
                    "webpage_url": "https://youtube.com/watch?v=test123",
                    "description": "",
                    "uploader": "Test Channel",
                    "uploader_id": "UC123",
                    "tags": [],
                    "categories": [],
                },
                {
                    "id": "test456",
                    "title": "Test Video 2",
                    "webpage_url": "https://youtube.com/watch?v=test456",
                    "description": "",
                    "uploader": "Test Channel",
                    "uploader_id": "UC123",
                    "tags": [],
                    "categories": [],
                },
            ]
        }

        mock_ydl = Mock()
        mock_ydl.extract_info.return_value = mock_info
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl

        metadata_list = self.processor._fetch_playlist_metadata(
            "https://youtube.com/playlist?list=test"
        )

        assert len(metadata_list) == 2
        assert metadata_list[0].video_id == "test123"
        assert metadata_list[1].video_id == "test456"

    @patch("yt_dlp.YoutubeDL")
    def test_fetch_playlist_metadata_with_failures(
        self, mock_ydl_class) -> None:
        """Test playlist metadata fetching with some failed entries."""
        mock_info = {
            "entries": [
                {
                    "id": "test123",
                    "title": "Test Video 1",
                    "webpage_url": "https://youtube.com/watch?v=test123",
                    "description": "",
                    "uploader": "Test Channel",
                    "uploader_id": "UC123",
                    "tags": [],
                    "categories": [],
                },
                None,  # Failed entry
                {
                    "id": "test456",
                    "title": "Test Video 2",
                    "webpage_url": "https://youtube.com/watch?v=test456",
                    "description": "",
                    "uploader": "Test Channel",
                    "uploader_id": "UC123",
                    "tags": [],
                    "categories": [],
                },
            ]
        }

        mock_ydl = Mock()
        mock_ydl.extract_info.return_value = mock_info
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl

        metadata_list = self.processor._fetch_playlist_metadata(
            "https://youtube.com/playlist?list=test"
        )

        assert len(metadata_list) == 2  # Should skip the None entry
        assert metadata_list[0].video_id == "test123"
        assert metadata_list[1].video_id == "test456"

    @patch("yt_dlp.YoutubeDL")
    def test_fetch_playlist_metadata_error(self, mock_ydl_class) -> None:
        """Test playlist metadata fetching error."""
        mock_ydl = Mock()
        mock_ydl.extract_info.return_value = None
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl

        with pytest.raises(YouTubeAPIError, match="Could not extract playlist info"):
            self.processor._fetch_playlist_metadata(
                "https://youtube.com/playlist?list=test"
            )

    @patch.object(YouTubeMetadataProcessor, "_fetch_video_metadata")
    def test_process_single_video(self, mock_fetch_video) -> None:
        """Test processing single video URL."""
        mock_metadata = YouTubeMetadata(
            video_id="test123",
            title="Test Video",
            url="https://youtube.com/watch?v=test123",
        )
        mock_fetch_video.return_value = mock_metadata

        result = self.processor.process("https://youtube.com/watch?v=test123")

        assert result.success is True
        assert result.data["count"] == 1
        assert result.data["processed_urls"] == 1
        assert len(result.data["metadata"]) == 1
        assert result.data["metadata"][0]["video_id"] == "test123"

    @patch.object(YouTubeMetadataProcessor, "_fetch_playlist_metadata")
    def test_process_playlist(self, mock_fetch_playlist) -> None:
        """Test processing playlist URL."""
        mock_metadata_list = [
            YouTubeMetadata(
                video_id="test123",
                title="Test Video 1",
                url="https://youtube.com/watch?v=test123",
            ),
            YouTubeMetadata(
                video_id="test456",
                title="Test Video 2",
                url="https://youtube.com/watch?v=test456",
            ),
        ]
        mock_fetch_playlist.return_value = mock_metadata_list

        result = self.processor.process(
            "https://youtube.com/playlist?list=test")

        assert result.success is True
        assert result.data["count"] == 2
        assert result.data["processed_urls"] == 1
        assert len(result.data["metadata"]) == 2

    def test_process_no_urls(self) -> None:
        """Test processing with no valid URLs."""
        result = self.processor.process("https://example.com/video")

        assert result.success is False
        assert "No valid YouTube URLs found" in result.errors[0]

    @patch.object(YouTubeMetadataProcessor, "_fetch_video_metadata")
    def test_process_with_errors(self, mock_fetch_video) -> None:
        """Test processing with some errors."""
        mock_fetch_video.side_effect = Exception("Network error")

        result = self.processor.process("https://youtube.com/watch?v=test123")

        assert result.success is False
        assert len(result.errors) == 1
        assert "Failed to process" in result.errors[0]
        assert result.data["count"] == 0

    def test_process_file_with_urls(self) -> None:
        """Test processing file containing URLs."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("https://youtube.com/watch?v=test123\n")
            f.write("https://youtube.com/playlist?list=test456\n")
            temp_file = f.name

        try:
            with patch.object(
                self.processor, "_fetch_video_metadata"
            ) as mock_fetch_video:
                mock_metadata = YouTubeMetadata(
                    video_id="test123",
                    title="Test Video",
                    url="https://youtube.com/watch?v=test123",
                )
                mock_fetch_video.return_value = mock_metadata

                with patch.object(
                    self.processor, "_fetch_playlist_metadata"
                ) as mock_fetch_playlist:
                    mock_playlist_metadata = [
                        YouTubeMetadata(
                            video_id="test456",
                            title="Test Video 2",
                            url="https://youtube.com/watch?v=test456",
                        )
                    ]
                    mock_fetch_playlist.return_value = mock_playlist_metadata

                    result = self.processor.process(temp_file)

                    assert result.success is True
                    assert result.data["count"] == 2
                    assert result.data["processed_urls"] == 2
        finally:
            Path(temp_file).unlink()


class TestFetchMetadataFunction:
    """Test fetch_metadata convenience function."""

    @patch("knowledge_system.processors.youtube_metadata.YouTubeMetadataProcessor")
    def test_fetch_metadata_success(self, mock_processor_class) -> None:
        """Test successful metadata fetching."""
        mock_processor = Mock()
        mock_result = Mock()
        mock_result.success = True
        mock_result.data = {
            "metadata": [
                {
                    "video_id": "test123",
                    "title": "Test Video",
                    "url": "https://youtube.com/watch?v=test123",
                }
            ]
        }
        mock_processor.process.return_value = mock_result
        mock_processor_class.return_value = mock_processor

        metadata = fetch_metadata("https://youtube.com/watch?v=test123")

        assert metadata.video_id == "test123"
        assert metadata.title == "Test Video"

    @patch("knowledge_system.processors.youtube_metadata.YouTubeMetadataProcessor")
    def test_fetch_metadata_failure(self, mock_processor_class) -> None:
        """Test metadata fetching failure."""
        mock_processor = Mock()
        mock_result = Mock()
        mock_result.success = False
        mock_result.errors = ["Network error"]
        mock_processor.process.return_value = mock_result
        mock_processor_class.return_value = mock_processor

        with pytest.raises(YouTubeAPIError, match="Failed to fetch metadata"):
            fetch_metadata("https://youtube.com/watch?v=test123")

    @patch("knowledge_system.processors.youtube_metadata.YouTubeMetadataProcessor")
    def test_fetch_metadata_no_data(self, mock_processor_class) -> None:
        """Test metadata fetching with no data returned."""
        mock_processor = Mock()
        mock_result = Mock()
        mock_result.success = True
        mock_result.data = {}
        mock_processor.process.return_value = mock_result
        mock_processor_class.return_value = mock_processor

        with pytest.raises(YouTubeAPIError, match="No metadata returned"):
            fetch_metadata("https://youtube.com/watch?v=test123")


class TestIntegration:
    """Integration tests for YouTube metadata processing."""

    def test_processor_registration(self) -> None:
        """Test that processor can be registered."""
        from knowledge_system.processors.base import register_processor

        processor = YouTubeMetadataProcessor()
        register_processor(processor)

        # Verify it's registered
        from knowledge_system.processors.base import get_processor

        registered = get_processor("youtube_metadata")
        assert registered is not None
        assert isinstance(registered, YouTubeMetadataProcessor)

    def test_markdown_output_structure(self) -> None:
        """Test that markdown output is properly structured."""
        metadata = YouTubeMetadata(
            video_id="test123",
            title="Test Video",
            url="https://youtube.com/watch?v=test123",
            description="Test description",
            duration=125,
            uploader="Test Channel",
            has_transcript=True,
        )

        markdown = metadata.to_markdown_metadata()

        # Check structure
        lines = markdown.split("\n")
        assert lines[0] == "# Metadata"
        assert lines[1] == ""

        # Check required fields
        assert any("**Title**: Test Video" in line for line in lines)
        assert any("**Video ID**: test123" in line for line in lines)
        assert any(
            "**URL**: https://youtube.com/watch?v=test123" in line for line in lines
        )
        assert any("**Uploader**: Test Channel" in line for line in lines)
        assert any("**Has Transcript**: True" in line for line in lines)

    def test_metadata_serialization(self) -> None:
        """Test metadata serialization to JSON."""
        metadata = YouTubeMetadata(
            video_id="test123",
            title="Test Video",
            url="https://youtube.com/watch?v=test123",
        )

        # Test to_dict
        data = metadata.to_dict()
        assert isinstance(data, dict)
        assert data["video_id"] == "test123"
        assert data["title"] == "Test Video"

        # Test JSON serialization
        json_str = json.dumps(data)
        assert "test123" in json_str
        assert "Test Video" in json_str

        # Test reconstruction
        reconstructed = YouTubeMetadata(**data)
        assert reconstructed.video_id == metadata.video_id
        assert reconstructed.title == metadata.title
