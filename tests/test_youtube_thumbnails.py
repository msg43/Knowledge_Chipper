"""
Tests for YouTube thumbnail downloading functionality.
"""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from knowledge_system.processors.youtube_download import YouTubeDownloadProcessor
from knowledge_system.services.transcription_service import TranscriptionService


class TestYouTubeThumbnails:
    """Test YouTube thumbnail downloading functionality."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @patch("knowledge_system.processors.youtube_download.yt_dlp.YoutubeDL")
    @patch("knowledge_system.processors.youtube_download.requests.get")
    def test_download_thumbnails_enabled(self, mock_requests, mock_ydl, temp_dir):
        """Test that thumbnails are downloaded when enabled."""
        # Mock yt-dlp response
        mock_ydl_instance = MagicMock()
        mock_ydl.return_value.__enter__.return_value = mock_ydl_instance

        mock_info = {
            "title": "Test Video",
            "thumbnail": "https://example.com/thumbnail.jpg",
            "id": "test123",
        }
        mock_ydl_instance.extract_info.return_value = mock_info

        # Mock requests response for thumbnail download
        mock_response = MagicMock()
        mock_response.content = b"fake_thumbnail_data"
        mock_response.raise_for_status.return_value = None
        mock_requests.return_value = mock_response

        # Create processor with thumbnails enabled
        processor = YouTubeDownloadProcessor(download_thumbnails=True)

        # Process a YouTube URL
        result = processor.process(
            "https://youtube.com/watch?v=test123", output_dir=temp_dir
        )

        # Verify thumbnail was downloaded
        assert result.success
        assert "downloaded_thumbnails" in result.data
        assert len(result.data["downloaded_thumbnails"]) > 0

        # Verify thumbnail file exists
        thumbnail_path = Path(result.data["downloaded_thumbnails"][0])
        assert thumbnail_path.exists()
        assert thumbnail_path.name.startswith("test123_thumbnail")

    @patch("knowledge_system.processors.youtube_download.yt_dlp.YoutubeDL")
    def test_download_thumbnails_disabled(self, mock_ydl, temp_dir):
        """Test that thumbnails are not downloaded when disabled."""
        # Mock yt-dlp response
        mock_ydl_instance = MagicMock()
        mock_ydl.return_value.__enter__.return_value = mock_ydl_instance

        mock_info = {
            "title": "Test Video",
            "thumbnail": "https://example.com/thumbnail.jpg",
            "id": "test123",
        }
        mock_ydl_instance.extract_info.return_value = mock_info

        # Create processor with thumbnails disabled
        processor = YouTubeDownloadProcessor(download_thumbnails=False)

        # Process a YouTube URL
        result = processor.process(
            "https://youtube.com/watch?v=test123", output_dir=temp_dir
        )

        # Verify no thumbnails were downloaded
        assert result.success
        assert "downloaded_thumbnails" in result.data
        assert len(result.data["downloaded_thumbnails"]) == 0

    @patch("knowledge_system.processors.youtube_download.yt_dlp.YoutubeDL")
    @patch("knowledge_system.processors.youtube_download.requests.get")
    @patch("pathlib.Path.exists")
    def test_transcription_service_with_thumbnails(
        self, mock_exists, mock_requests, mock_ydl, temp_dir
    ):
        """Test that transcription service includes thumbnail information."""
        # Mock file existence check
        mock_exists.return_value = True

        # Mock yt-dlp response
        mock_ydl_instance = MagicMock()
        mock_ydl.return_value.__enter__.return_value = mock_ydl_instance

        mock_info = {
            "title": "Test Video",
            "thumbnail": "https://example.com/thumbnail.jpg",
            "id": "test123",
        }
        mock_ydl_instance.extract_info.return_value = mock_info

        # Mock requests response for thumbnail download
        mock_response = MagicMock()
        mock_response.content = b"fake_thumbnail_data"
        mock_response.raise_for_status.return_value = None
        mock_requests.return_value = mock_response

        # Mock audio processor response
        with patch(
            "knowledge_system.processors.audio_processor.AudioProcessor.process"
        ) as mock_audio:
            mock_audio.return_value = MagicMock(
                success=True, data="Test transcript content", metadata={"duration": 120}
            )

            # Create transcription service with thumbnails enabled
            service = TranscriptionService(download_thumbnails=True)

            # Transcribe a YouTube URL
            result = service.transcribe_youtube_url(
                "https://youtube.com/watch?v=test123"
            )

            # Verify result includes thumbnail information
            assert result["success"]
            assert "thumbnails" in result
            assert len(result["thumbnails"]) > 0
            assert "download_metadata" in result

    def test_extract_video_id(self, temp_dir):
        """Test video ID extraction from various YouTube URL formats."""
        processor = YouTubeDownloadProcessor()

        # Test standard YouTube URL
        video_id = processor._extract_video_id(
            "https://youtube.com/watch?v=dQw4w9WgXcQ"
        )
        assert video_id == "dQw4w9WgXcQ"

        # Test shortened YouTube URL
        video_id = processor._extract_video_id("https://youtu.be/dQw4w9WgXcQ")
        assert video_id == "dQw4w9WgXcQ"

        # Test playlist URL
        video_id = processor._extract_video_id(
            "https://youtube.com/playlist?list=PL123456789"
        )
        assert video_id == "PL123456789"

        # Test invalid URL (should return hash)
        video_id = processor._extract_video_id("https://example.com/invalid")
        assert len(video_id) == 8  # MD5 hash truncated to 8 characters
