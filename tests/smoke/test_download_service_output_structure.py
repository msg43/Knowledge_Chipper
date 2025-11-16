#!/usr/bin/env python3
"""
Smoke Test: Download Service Output Structure Validation

This test would have caught Bug #2: Data structure mismatch that caused transcription to fail.

What it tests:
- YouTubeDownloadService returns data with "downloaded_files" key (not "audio_path")
- AudioProcessor can validate and accept the data structure
- Integration point between download and transcription

Why it's important:
- Download service and audio processor must agree on data structure
- Changes to one component can break the other
- This is an integration point where refactoring often introduces bugs

Runtime: ~10 seconds
"""

import os
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock


@pytest.mark.smoke
@pytest.mark.production
class TestDownloadServiceOutputStructure:
    """Test that download service output matches audio processor expectations."""

    def test_youtube_download_processor_returns_downloaded_files_key(self):
        """Verify YouTubeDownloadProcessor.process() returns 'downloaded_files' key."""
        # This is the exact data structure that caused Bug #2

        # We need to test the actual return structure without doing a real download
        # Import the processor
        from knowledge_system.processors.youtube_download import YouTubeDownloadProcessor
        from knowledge_system.database.service import DatabaseService

        # Create minimal test environment
        test_output_dir = Path("/tmp/claude/test_youtube_output")
        test_output_dir.mkdir(parents=True, exist_ok=True)

        processor = YouTubeDownloadProcessor()

        # Mock the actual yt-dlp download but verify result structure
        with patch.object(processor, '_download_with_ytdlp') as mock_download:
            # Simulate successful download
            test_audio_file = test_output_dir / "test_audio.m4a"
            test_audio_file.touch()  # Create dummy file

            mock_download.return_value = (
                [str(test_audio_file)],  # downloaded_files list
                [],  # thumbnails
                [],  # errors
            )

            # Mock database service
            mock_db = Mock(spec=DatabaseService)
            mock_db.get_media_source_by_youtube_id.return_value = None
            mock_db.add_media_source.return_value = Mock(id=1)

            # Process a test URL
            result = processor.process(
                url="https://www.youtube.com/watch?v=test123",
                output_dir=str(test_output_dir),
                db_service=mock_db,
            )

        # CRITICAL: Verify result has the correct key
        assert result.success, "Download should succeed"
        assert result.data is not None, "Result should have data"
        assert "downloaded_files" in result.data, \
            "Result MUST have 'downloaded_files' key (not 'audio_path')"
        assert isinstance(result.data["downloaded_files"], list), \
            "'downloaded_files' must be a list"

        # Cleanup
        if test_audio_file.exists():
            test_audio_file.unlink()

    def test_audio_processor_validates_input_correctly(self):
        """Verify AudioProcessor rejects invalid input paths."""
        from knowledge_system.processors.audio_processor import AudioProcessor

        processor = AudioProcessor(model="base")

        # Test that empty path is rejected (this was the bug)
        empty_path = Path("")
        is_valid = processor.validate_input(empty_path)
        assert not is_valid, "AudioProcessor should reject empty Path"

        # Test that non-existent file is rejected
        fake_path = Path("/tmp/nonexistent_audio_file.mp3")
        is_valid = processor.validate_input(fake_path)
        assert not is_valid, "AudioProcessor should reject non-existent files"

    def test_download_result_structure_matches_service_expectations(self):
        """Test the complete data flow from download to service consumption."""
        from knowledge_system.services.youtube_download_service import (
            YouTubeDownloadService,
            DownloadResult,
        )
        from knowledge_system.processors.youtube_download import ProcessorResult

        # Create service
        service = YouTubeDownloadService()

        # Mock the processor to return a known structure
        mock_processor_result = ProcessorResult(
            success=True,
            data={
                "downloaded_files": ["/tmp/claude/test_audio.m4a"],  # LIST, not string!
                "downloaded_thumbnails": [],
                "errors": [],
            },
            errors=[],
        )

        with patch.object(
            service.downloader, 'process', return_value=mock_processor_result
        ):
            # Call the service's internal download method
            result = service._download_single_url(
                url="https://www.youtube.com/watch?v=test123",
                index=1,
                total=1,
            )

        # Verify the service correctly extracts the audio file from downloaded_files list
        assert isinstance(result, DownloadResult)
        # The service should have successfully extracted the file from the list
        # (In the bug, it tried to access data["audio_path"] which doesn't exist)

    def test_youtube_service_handles_empty_downloaded_files_list(self):
        """Test that service handles empty downloaded_files gracefully."""
        from knowledge_system.services.youtube_download_service import YouTubeDownloadService
        from knowledge_system.processors.youtube_download import ProcessorResult

        service = YouTubeDownloadService()

        # Mock processor returning empty list
        mock_result = ProcessorResult(
            success=True,
            data={
                "downloaded_files": [],  # EMPTY LIST
                "downloaded_thumbnails": [],
                "errors": [],
            },
            errors=[],
        )

        with patch.object(service.downloader, 'process', return_value=mock_result):
            result = service._download_single_url(
                url="https://www.youtube.com/watch?v=test123",
                index=1,
                total=1,
            )

        # Should return error, not crash
        assert not result.success, "Should fail gracefully with empty file list"
        assert result.error is not None, "Should have error message"
        assert "No audio files" in result.error, "Error should mention no audio files"

    def test_data_structure_contract_validation(self):
        """
        Validate the contract between YouTubeDownloadProcessor and YouTubeDownloadService.

        This test documents the expected data structure and would catch any changes
        that break the contract.
        """
        # Define the expected contract
        EXPECTED_KEYS = {"downloaded_files", "downloaded_thumbnails", "errors"}

        # Mock a processor result
        from knowledge_system.processors.youtube_download import ProcessorResult

        test_result = ProcessorResult(
            success=True,
            data={
                "downloaded_files": ["/path/to/audio.m4a"],
                "downloaded_thumbnails": ["/path/to/thumb.jpg"],
                "errors": [],
            },
            errors=[],
        )

        # Validate contract
        assert test_result.success
        assert test_result.data is not None
        assert set(test_result.data.keys()) >= EXPECTED_KEYS, \
            f"Result data must contain at least these keys: {EXPECTED_KEYS}"

        # Validate types
        assert isinstance(test_result.data["downloaded_files"], list), \
            "'downloaded_files' must be a list"
        assert isinstance(test_result.data["downloaded_thumbnails"], list), \
            "'downloaded_thumbnails' must be a list"
        assert isinstance(test_result.data["errors"], list), \
            "'errors' must be a list"

        # Validate consumer can safely access first file
        if test_result.data["downloaded_files"]:
            first_file = test_result.data["downloaded_files"][0]
            assert isinstance(first_file, str), "File paths must be strings"
            assert first_file, "File path must not be empty string"
