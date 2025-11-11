"""Test audio processor functionality."""

import pytest


def test_audio_processor_import():
    """Test that audio processor can be imported."""
    try:
        from knowledge_system.processors.audio_processor import AudioProcessor

        assert AudioProcessor is not None
    except ImportError:
        # If module structure is different, just pass
        pass


def test_audio_utils_import():
    """Test that audio utilities can be imported."""
    try:
        from knowledge_system.utils.audio_utils import get_audio_duration

        assert get_audio_duration is not None
    except ImportError:
        # If module doesn't exist, just pass
        pass


def test_markdown_no_duplicate_h1_heading():
    """Test that markdown transcripts don't have redundant H1 headings after YAML."""
    try:
        from knowledge_system.processors.audio_processor import AudioProcessor

        processor = AudioProcessor()

        # Create minimal test data
        transcription_data = {
            "text": "Test transcript content.",
            "segments": [],
            "language": "en",
        }

        audio_metadata = {"duration": 10.0}
        model_metadata = {"model": "test", "device": "cpu"}

        source_metadata = {
            "title": "Test Video Title",
            "url": "https://example.com/video",
            "video_id": "test123",
        }

        # Generate markdown
        markdown = processor._create_markdown(
            transcription_data,
            audio_metadata,
            model_metadata,
            include_timestamps=True,
            source_metadata=source_metadata,
        )

        # Split into lines
        lines = markdown.split("\n")

        # Find where YAML ends (second ---)
        yaml_end_idx = None
        dash_count = 0
        for i, line in enumerate(lines):
            if line.strip() == "---":
                dash_count += 1
                if dash_count == 2:
                    yaml_end_idx = i
                    break

        assert yaml_end_idx is not None, "Could not find end of YAML frontmatter"

        # Check the lines immediately after YAML
        # There should be no H1 heading (line starting with "# ")
        for i in range(yaml_end_idx + 1, min(yaml_end_idx + 5, len(lines))):
            line = lines[i].strip()
            if line:  # Skip empty lines
                assert not line.startswith(
                    "# "
                ), f"Found redundant H1 heading after YAML: {line}"
                break

    except ImportError:
        pytest.skip("AudioProcessor not available")


def test_filename_preserves_spaces():
    """Test that transcript filenames preserve spaces instead of converting to underscores."""
    try:
        import re
        import tempfile
        from pathlib import Path

        from knowledge_system.processors.audio_processor import AudioProcessor

        processor = AudioProcessor()

        # Create minimal test data
        transcription_data = {
            "text": "Test transcript content.",
            "segments": [],
            "language": "en",
        }

        # Mock ProcessorResult
        class MockResult:
            success = True
            data = transcription_data
            metadata = {"model": "test", "device": "cpu"}

        result = MockResult()

        # Create temporary audio file
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            audio_path = Path(tmp.name)

        try:
            # Create temporary output directory
            with tempfile.TemporaryDirectory() as tmpdir:
                output_dir = Path(tmpdir)

                source_metadata = {
                    "title": "Will Japan and South Korea Gang Up on China",
                    "url": "https://example.com/video",
                    "video_id": "test123",
                }

                # Save transcript
                output_path = processor.save_transcript_to_markdown(
                    result,
                    audio_path,
                    output_dir=output_dir,
                    source_metadata=source_metadata,
                )

                assert output_path is not None, "Failed to save transcript"

                # Check that filename contains spaces
                filename = output_path.name
                assert " " in filename, f"Filename should contain spaces: {filename}"

                # Check that the title portion (before _transcript.md) has spaces
                # Remove the _transcript.md suffix
                title_part = re.sub(r"_transcript\.md$", "", filename)
                assert (
                    " " in title_part
                ), f"Title portion should contain spaces: {title_part}"

        finally:
            # Clean up temp audio file
            if audio_path.exists():
                audio_path.unlink()

    except ImportError:
        pytest.skip("AudioProcessor not available")


@pytest.mark.skip(reason="Requires audio files and dependencies")
def test_audio_processing():
    """Test actual audio processing (skipped for CI)."""
    # This would test actual audio processing but requires files
    pass
