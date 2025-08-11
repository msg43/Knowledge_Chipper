from pathlib import Path
from unittest.mock import MagicMock, patch

from knowledge_system.services.transcription_service import (
    TranscriptionService,
    transcribe_file,
    transcribe_youtube,
)


class TestTranscriptionService:
    def test_transcribe_audio_file_success(self):
        service = TranscriptionService()

        with patch.object(service.audio_processor, "process") as mock_process:
            mock_process.return_value = MagicMock(
                success=True,
                data="This is a test transcript",
                metadata={"original_format": ".mp3", "processed_format": "wav"},
            )

            result = service.transcribe_audio_file("test.mp3")

            assert result["success"] is True
            assert result["transcript"] == "This is a test transcript"
            assert result["source"] == "test.mp3"
            assert result["metadata"]["original_format"] == ".mp3"

    def test_transcribe_audio_file_failure(self):
        service = TranscriptionService()

        with patch.object(service.audio_processor, "process") as mock_process:
            mock_process.return_value = MagicMock(
                success=False, errors=["File not found"]
            )

            result = service.transcribe_audio_file("nonexistent.mp3")

            assert result["success"] is False
            assert result["error"] == "File not found"
            assert result["source"] == "nonexistent.mp3"

    def test_transcribe_youtube_url_success(self):
        service = TranscriptionService()

        with patch.object(service.youtube_downloader, "process") as mock_download:
            mock_download.return_value = MagicMock(
                success=True, data="/tmp/downloaded_audio.mp3"
            )

            with patch.object(Path, "exists", return_value=True):
                with patch.object(service, "transcribe_audio_file") as mock_transcribe:
                    mock_transcribe.return_value = {
                        "success": True,
                        "transcript": "YouTube transcript",
                        "source": "/tmp/downloaded_audio.mp3",
                    }

                    result = service.transcribe_youtube_url(
                        "https://youtube.com/watch?v=test"
                    )

                    assert result["success"] is True
                    assert result["transcript"] == "YouTube transcript"

    def test_transcribe_youtube_url_download_failure(self):
        service = TranscriptionService()

        with patch.object(service.youtube_downloader, "process") as mock_download:
            mock_download.return_value = MagicMock(
                success=False, errors=["Download failed"]
            )

            result = service.transcribe_youtube_url("https://youtube.com/watch?v=test")

            assert result["success"] is False
            assert result["error"] == "Download failed"

    def test_transcribe_input_audio_file(self):
        service = TranscriptionService()

        with patch.object(service, "transcribe_audio_file") as mock_transcribe:
            mock_transcribe.return_value = {"success": True, "transcript": "audio"}

            result = service.transcribe_input("audio.mp3")

            mock_transcribe.assert_called_once_with("audio.mp3")
            assert result["success"] is True

    def test_transcribe_input_youtube_url(self):
        service = TranscriptionService()

        with patch.object(service, "transcribe_youtube_url") as mock_transcribe:
            mock_transcribe.return_value = {"success": True, "transcript": "youtube"}

            result = service.transcribe_input("https://youtube.com/watch?v=test")

            mock_transcribe.assert_called_once_with("https://youtube.com/watch?v=test")
            assert result["success"] is True

    def test_transcribe_batch(self):
        service = TranscriptionService()

        with patch.object(service, "transcribe_input") as mock_transcribe:
            mock_transcribe.side_effect = [
                {"success": True, "transcript": "file1"},
                {"success": True, "transcript": "file2"},
            ]

            results = service.transcribe_batch(["file1.mp3", "file2.wav"])

            assert len(results) == 2
            assert results[0]["success"] is True
            assert results[0]["transcript"] == "file1"
            assert results[0]["index"] == 1
            assert results[0]["total"] == 2
            assert results[1]["success"] is True
            assert results[1]["transcript"] == "file2"
            assert results[1]["index"] == 2
            assert results[1]["total"] == 2

    def test_get_supported_formats(self):
        service = TranscriptionService()

        formats = service.get_supported_formats()

        assert "audio_formats" in formats
        assert "youtube_urls" in formats
        assert "whisper_model" in formats
        assert formats["whisper_model"] == "base"


class TestConvenienceFunctions:
    def test_transcribe_file_success(self):
        with patch(
            "knowledge_system.services.transcription_service.TranscriptionService"
        ) as mock_service_class:
            mock_service = MagicMock()
            mock_service.transcribe_input.return_value = {
                "success": True,
                "transcript": "test",
            }
            mock_service_class.return_value = mock_service

            result = transcribe_file("test.mp3", normalize=True)

            assert result == "test"
            mock_service_class.assert_called_once_with(normalize_audio=True)
            mock_service.transcribe_input.assert_called_once_with("test.mp3")

    def test_transcribe_file_failure(self):
        with patch(
            "knowledge_system.services.transcription_service.TranscriptionService"
        ) as mock_service_class:
            mock_service = MagicMock()
            mock_service.transcribe_input.return_value = {
                "success": False,
                "error": "failed",
            }
            mock_service_class.return_value = mock_service

            result = transcribe_file("test.mp3")

            assert result is None

    def test_transcribe_youtube_success(self):
        with patch(
            "knowledge_system.services.transcription_service.TranscriptionService"
        ) as mock_service_class:
            mock_service = MagicMock()
            mock_service.transcribe_youtube_url.return_value = {
                "success": True,
                "transcript": "youtube",
            }
            mock_service_class.return_value = mock_service

            result = transcribe_youtube(
                "https://youtube.com/watch?v=test", normalize=False
            )

            assert result == "youtube"
            mock_service_class.assert_called_once_with(normalize_audio=False)
            mock_service.transcribe_youtube_url.assert_called_once_with(
                "https://youtube.com/watch?v=test"
            )

    def test_transcribe_youtube_failure(self):
        with patch(
            "knowledge_system.services.transcription_service.TranscriptionService"
        ) as mock_service_class:
            mock_service = MagicMock()
            mock_service.transcribe_youtube_url.return_value = {
                "success": False,
                "error": "failed",
            }
            mock_service_class.return_value = mock_service

            result = transcribe_youtube("https://youtube.com/watch?v=test")

            assert result is None
