"""
Tests for YouTube Download Processor.

Covers audio download, error handling, output format, and fetch_audio convenience function.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from knowledge_system.errors import YouTubeAPIError
from knowledge_system.processors.youtube_download import (
    YouTubeDownloadProcessor,
    fetch_audio,
)


class TestYouTubeDownloadProcessor:
    def setup_method(self):
        self.processor = YouTubeDownloadProcessor()

    def test_supported_formats(self):
        assert ".url" in self.processor.supported_formats
        assert ".txt" in self.processor.supported_formats

    def test_validate_input_youtube_url(self):
        url = "https://youtube.com/watch?v=test123"
        assert self.processor.validate_input(url) is True

    def test_validate_input_file_with_urls(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("https://youtube.com/watch?v=test123\n")
            temp_file = f.name
        try:
            assert self.processor.validate_input(temp_file) is True
        finally:
            Path(temp_file).unlink()

    def test_validate_input_invalid(self):
        assert self.processor.validate_input("not a url") is False
        assert self.processor.validate_input(123) is False

    def test_extract_urls_direct_url(self):
        url = "https://youtube.com/watch?v=test123"
        urls = self.processor._extract_urls(url)
        assert urls == [url]

    def test_extract_urls_from_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("https://youtube.com/watch?v=test123\n")
            f.write("https://youtube.com/watch?v=test456\n")
            temp_file = f.name
        try:
            urls = self.processor._extract_urls(temp_file)
            assert len(urls) == 2
        finally:
            Path(temp_file).unlink()

    def test_extract_urls_file_error(self):
        with pytest.raises(YouTubeAPIError, match="Cannot read file"):
            self.processor._extract_urls("/nonexistent/file.txt")

    @patch("yt_dlp.YoutubeDL")
    def test_process_single_video_success(self, mock_ydl_class):
        mock_info = {
            "title": "Test Video",
        }
        mock_ydl = Mock()
        mock_ydl.extract_info.return_value = mock_info
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.processor.process(
                "https://youtube.com/watch?v=test123", output_dir=tmpdir
            )
            assert result.success is True
            assert result.data["count"] == 1
            assert result.data["downloaded_files"][0].endswith("Test Video.mp3")

    @patch("yt_dlp.YoutubeDL")
    def test_process_playlist_success(self, mock_ydl_class):
        mock_info = {
            "entries": [
                {"title": "Video1"},
                {"title": "Video2"},
            ]
        }
        mock_ydl = Mock()
        mock_ydl.extract_info.return_value = mock_info
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.processor.process(
                "https://youtube.com/playlist?list=abc", output_dir=tmpdir
            )
            assert result.success is True
            assert result.data["count"] == 2
            assert any("Video1.mp3" in f for f in result.data["downloaded_files"])
            assert any("Video2.mp3" in f for f in result.data["downloaded_files"])

    @patch("yt_dlp.YoutubeDL")
    def test_process_download_error(self, mock_ydl_class):
        mock_ydl = Mock()
        mock_ydl.extract_info.side_effect = Exception("Download failed")
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.processor.process(
                "https://youtube.com/watch?v=test123", output_dir=tmpdir
            )
            assert result.success is False
            assert "Failed to download" in result.errors[0]

    def test_process_no_urls(self):
        result = self.processor.process("not a url")
        assert result.success is False
        assert "No valid YouTube URLs found" in result.errors[0]

    @patch("yt_dlp.YoutubeDL")
    def test_output_format_wav(self, mock_ydl_class):
        mock_info = {"title": "Test Video"}
        mock_ydl = Mock()
        mock_ydl.extract_info.return_value = mock_info
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.processor.process(
                "https://youtube.com/watch?v=test123",
                output_dir=tmpdir,
                output_format="wav",
            )
            assert result.success is True
            assert result.data["downloaded_files"][0].endswith("Test Video.wav")
            assert result.data["output_format"] == "wav"


class TestFetchAudio:
    @patch("knowledge_system.processors.youtube_download.YouTubeDownloadProcessor")
    def test_fetch_audio_success(self, mock_proc_class):
        mock_proc = Mock()
        mock_result = Mock()
        mock_result.success = True
        mock_result.data = {"downloaded_files": ["/tmp/Test Video.mp3"]}
        mock_proc.process.return_value = mock_result
        mock_proc_class.return_value = mock_proc
        out = fetch_audio(
            "https://youtube.com/watch?v=test123",
            output_dir="/tmp",
            output_format="mp3",
        )
        assert out == "/tmp/Test Video.mp3"

    @patch("knowledge_system.processors.youtube_download.YouTubeDownloadProcessor")
    def test_fetch_audio_failure(self, mock_proc_class):
        mock_proc = Mock()
        mock_result = Mock()
        mock_result.success = False
        mock_result.errors = ["Network error"]
        mock_proc.process.return_value = mock_result
        mock_proc_class.return_value = mock_proc
        with pytest.raises(YouTubeAPIError, match="Failed to download audio"):
            fetch_audio(
                "https://youtube.com/watch?v=test123",
                output_dir="/tmp",
                output_format="mp3",
            )

    @patch("knowledge_system.processors.youtube_download.YouTubeDownloadProcessor")
    def test_fetch_audio_no_file(self, mock_proc_class):
        mock_proc = Mock()
        mock_result = Mock()
        mock_result.success = True
        mock_result.data = {"downloaded_files": []}
        mock_proc.process.return_value = mock_result
        mock_proc_class.return_value = mock_proc
        with pytest.raises(YouTubeAPIError, match="No audio file downloaded"):
            fetch_audio(
                "https://youtube.com/watch?v=test123",
                output_dir="/tmp",
                output_format="mp3",
            )
