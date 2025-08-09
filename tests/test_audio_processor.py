from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from knowledge_system.processors.audio_processor import AudioProcessor
from knowledge_system.processors.base import ProcessorResult


@pytest.fixture
def audio_processor():
    return AudioProcessor()


@pytest.fixture
def sample_audio_file(tmp_path):
    # Create a mock audio file
    audio_file = tmp_path / "test_audio.wav"
    audio_file.write_bytes(b"mock audio data")
    return audio_file


@patch("knowledge_system.processors.audio_processor.FFMPEG_AVAILABLE", True)
def test_audio_processor_initialization():
    """Test AudioProcessor initialization."""
    processor = AudioProcessor()
    assert processor.normalize_audio is True
    assert processor.target_format == "wav"
    assert processor.model == "base"


@patch("knowledge_system.processors.audio_processor.FFMPEG_AVAILABLE", True)
def test_supported_formats():
    """Test supported audio formats."""
    processor = AudioProcessor()
    formats = processor.supported_formats
    assert ".mp3" in formats
    assert ".wav" in formats
    assert ".m4a" in formats
    assert ".flac" in formats


@patch("knowledge_system.processors.audio_processor.FFMPEG_AVAILABLE", True)
def test_validate_input_valid_file(sample_audio_file):
    """Test input validation with valid audio file."""
    processor = AudioProcessor()
    assert processor.validate_input(sample_audio_file) is True


@patch("knowledge_system.processors.audio_processor.FFMPEG_AVAILABLE", True)
def test_validate_input_invalid_file(tmp_path):
    """Test input validation with invalid file."""
    processor = AudioProcessor()
    invalid_file = tmp_path / "test.txt"
    invalid_file.write_text("not audio")
    assert processor.validate_input(invalid_file) is False


@patch("knowledge_system.processors.audio_processor.FFMPEG_AVAILABLE", False)
def test_ffmpeg_not_available():
    """Test behavior when FFmpeg is not available."""
    processor = AudioProcessor()
    # Should still initialize without errors
    assert processor is not None


@patch("knowledge_system.processors.audio_processor.FFMPEG_AVAILABLE", True)
@patch("knowledge_system.processors.audio_processor.convert_audio_file")
def test_convert_audio_success(mock_convert, sample_audio_file, tmp_path):
    """Test successful audio conversion."""
    mock_convert.return_value = True
    processor = AudioProcessor()
    output_file = tmp_path / "output.wav"

    result = processor._convert_audio(sample_audio_file, output_file)
    assert result is True
    mock_convert.assert_called_once()


@patch("knowledge_system.processors.audio_processor.FFMPEG_AVAILABLE", True)
@patch("knowledge_system.processors.audio_processor.convert_audio_file")
def test_convert_audio_failure(mock_convert, sample_audio_file, tmp_path):
    """Test failed audio conversion."""
    mock_convert.return_value = False
    processor = AudioProcessor()
    output_file = tmp_path / "output.wav"

    result = processor._convert_audio(sample_audio_file, output_file)
    assert result is False


@patch("knowledge_system.processors.audio_processor.FFMPEG_AVAILABLE", False)
def test_convert_audio_no_ffmpeg(sample_audio_file, tmp_path):
    """Test audio conversion when FFmpeg is not available."""
    processor = AudioProcessor()
    output_file = tmp_path / "output.wav"

    # Should return True if input format matches target format
    result = processor._convert_audio(sample_audio_file, output_file)
    assert result is True  # Because input is .wav and target is .wav


@patch("knowledge_system.processors.audio_processor.FFMPEG_AVAILABLE", True)
@patch("knowledge_system.processors.audio_processor.get_audio_duration")
def test_get_audio_metadata_success(mock_duration, sample_audio_file):
    """Test successful metadata extraction."""
    mock_duration.return_value = 120.5
    processor = AudioProcessor()

    metadata = processor._get_audio_metadata(sample_audio_file)
    assert "filename" in metadata
    assert "file_size_mb" in metadata
    assert "duration_seconds" in metadata
    assert metadata["duration_seconds"] == 120.5


@patch("knowledge_system.processors.audio_processor.FFMPEG_AVAILABLE", False)
def test_get_audio_metadata_no_ffmpeg(sample_audio_file):
    """Test metadata extraction when FFmpeg is not available."""
    processor = AudioProcessor()

    metadata = processor._get_audio_metadata(sample_audio_file)
    assert "filename" in metadata
    assert "file_size_mb" in metadata
    # Should not have duration info when FFmpeg is not available
    assert "duration_seconds" not in metadata


def test_format_duration():
    """Test duration formatting."""
    processor = AudioProcessor()

    # Test seconds only
    assert processor._format_duration(65.5) == "01:05"

    # Test hours
    assert processor._format_duration(3665.5) == "01:01:05"

    # Test None
    assert processor._format_duration(None) == "Unknown"
