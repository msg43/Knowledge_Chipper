from unittest.mock import patch, MagicMock, Mock
from pathlib import Path
from knowledge_system.processors.audio_processor import (
    AudioProcessor,
    process_audio_for_transcription,
)


@patch("knowledge_system.processors.audio_processor.PYDUB_AVAILABLE", True)
def test_single_audio_processing():
    processor = AudioProcessor(normalize_audio=True)

    with (
        patch.object(Path, "exists", return_value=True),
        patch.object(Path, "is_file", return_value=True),
    ):
        with patch("tempfile.NamedTemporaryFile") as mock_temp:
            mock_temp.return_value.__enter__.return_value.name = "/tmp/test.wav"
            mock_temp.return_value.__exit__.return_value = None

            with patch.object(processor, "_convert_audio", return_value=True):
                with patch.object(processor.transcriber, "process") as mock_transcribe:
                    mock_transcribe.return_value = MagicMock(
                        success=True, data="transcribed text"
                    )

                    result = processor.process("audio.mp3")

                    assert result.success
                    assert result.data == "transcribed text"
                    assert result.metadata["original_format"] == ".mp3"
                    assert result.metadata["processed_format"] == "wav"
                    assert result.metadata["normalized"] is True


@patch("knowledge_system.processors.audio_processor.PYDUB_AVAILABLE", True)
def test_batch_audio_processing():
    processor = AudioProcessor()

    with patch.object(processor, "process") as mock_process:
        mock_process.side_effect = [
            MagicMock(success=True, data="text1"),
            MagicMock(success=True, data="text2"),
        ]

        results = processor.process_batch(["audio1.mp3", "audio2.wav"])

        assert len(results) == 2
        assert all(r.success for r in results)
        assert results[0].data == "text1"
        assert results[1].data == "text2"


@patch("knowledge_system.processors.audio_processor.PYDUB_AVAILABLE", True)
def test_audio_conversion_failure():
    processor = AudioProcessor()

    with (
        patch.object(Path, "exists", return_value=True),
        patch.object(Path, "is_file", return_value=True),
    ):
        with patch("tempfile.NamedTemporaryFile") as mock_temp:
            mock_temp.return_value.__enter__.return_value.name = "/tmp/test.wav"
            mock_temp.return_value.__exit__.return_value = None

            with patch.object(processor, "_convert_audio", return_value=False):
                result = processor.process("audio.mp3")

                assert not result.success
                assert "Audio conversion failed" in result.errors


@patch("knowledge_system.processors.audio_processor.PYDUB_AVAILABLE", False)
def test_pydub_not_available():
    processor = AudioProcessor()

    with (
        patch.object(Path, "exists", return_value=True),
        patch.object(Path, "is_file", return_value=True),
    ):
        result = processor.process("audio.mp3")

        assert not result.success
        assert "Audio conversion failed" in result.errors


def test_invalid_input():
    processor = AudioProcessor()

    with patch.object(Path, "exists", return_value=False):
        result = processor.process("nonexistent.mp3")

        assert not result.success
        assert "Invalid input" in result.errors[0]


def test_unsupported_format():
    processor = AudioProcessor()

    with (
        patch.object(Path, "exists", return_value=True),
        patch.object(Path, "is_file", return_value=True),
    ):
        result = processor.process("file.txt")

        assert not result.success
        assert "Invalid input" in result.errors[0]


def test_process_audio_for_transcription_success():
    with patch(
        "knowledge_system.processors.audio_processor.AudioProcessor"
    ) as mock_processor_class:
        mock_processor = Mock()
        mock_processor.process.return_value = MagicMock(
            success=True, data="transcribed"
        )
        mock_processor_class.return_value = mock_processor

        result = process_audio_for_transcription("audio.mp3", normalize=True)

        assert result == "transcribed"
        mock_processor_class.assert_called_once_with(normalize_audio=True)
        mock_processor.process.assert_called_once_with("audio.mp3")


def test_process_audio_for_transcription_failure():
    with patch(
        "knowledge_system.processors.audio_processor.AudioProcessor"
    ) as mock_processor_class:
        mock_processor = Mock()
        mock_processor.process.return_value = MagicMock(
            success=False, data=None)
        mock_processor_class.return_value = mock_processor

        result = process_audio_for_transcription("audio.mp3")

        assert result is None
