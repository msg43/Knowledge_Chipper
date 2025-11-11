"""
Shared pytest fixtures for all tests.
"""
import os
import sys
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from knowledge_system.database import DatabaseService


@pytest.fixture
def test_database() -> Generator[DatabaseService, None, None]:
    """
    Provide a test database service using an in-memory SQLite database.

    This fixture creates a fresh database for each test and cleans it up afterward.
    """
    # Use in-memory database for speed
    db_service = DatabaseService("sqlite:///:memory:")

    yield db_service

    # Cleanup
    db_service.close()


@pytest.fixture
def temp_db_file() -> Generator[Path, None, None]:
    """
    Provide a temporary database file path.

    The file is created in a temp directory and cleaned up after the test.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    yield db_path

    # Cleanup
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """
    Provide a temporary directory for test files.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def cookie_file(temp_dir: Path) -> str:
    """
    Create a test cookie file with valid Netscape format.

    Returns the path to the cookie file as a string.
    """
    cookie_content = """# Netscape HTTP Cookie File
# This is a generated file! Do not edit.

.youtube.com	TRUE	/	TRUE	1234567890	CONSENT	YES+1
.youtube.com	TRUE	/	FALSE	1234567890	VISITOR_INFO1_LIVE	test_visitor_id
.youtube.com	TRUE	/	TRUE	1234567890	__Secure-3PSID	test_session_id
"""

    cookie_path = temp_dir / "test_cookies.txt"
    cookie_path.write_text(cookie_content)

    return str(cookie_path)


@pytest.fixture
def cookie_files(temp_dir: Path) -> list[str]:
    """
    Create multiple test cookie files.

    Returns a list of paths to cookie files as strings.
    """
    cookie_files = []

    for i in range(3):
        cookie_content = f"""# Netscape HTTP Cookie File
# This is a generated file! Do not edit.

.youtube.com	TRUE	/	TRUE	1234567890	CONSENT	YES+{i}
.youtube.com	TRUE	/	FALSE	1234567890	VISITOR_INFO1_LIVE	test_visitor_{i}
.youtube.com	TRUE	/	TRUE	1234567890	__Secure-3PSID	test_session_{i}
"""

        cookie_path = temp_dir / f"test_cookies_{i}.txt"
        cookie_path.write_text(cookie_content)
        cookie_files.append(str(cookie_path))

    return cookie_files


@pytest.fixture
def sample_transcript_file(temp_dir: Path) -> Path:
    """
    Create a sample transcript markdown file for testing.
    """
    transcript_content = """---
source_id: "test_video_123"
title: "Test Video Title"
source: "YouTube"
uploader: "Test Channel"
---

# Test Video Title

## Transcript

**Speaker 1** [00:00:00]
This is a test transcript segment.

**Speaker 2** [00:00:05]
This is another test segment.
"""

    transcript_path = temp_dir / "test_transcript.md"
    transcript_path.write_text(transcript_content)

    return transcript_path


@pytest.fixture
def sample_audio_file(temp_dir: Path) -> Path:
    """
    Create a minimal valid audio file for testing.

    Note: This creates a very small WAV file. For real audio processing tests,
    you may need actual audio samples.
    """
    import struct
    import wave

    audio_path = temp_dir / "test_audio.wav"

    # Create a 1-second silent WAV file
    with wave.open(str(audio_path), "w") as wav_file:
        # Set parameters: 1 channel, 2 bytes per sample, 16000 Hz sample rate
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16000)

        # Write 1 second of silence
        for _ in range(16000):
            wav_file.writeframes(struct.pack("h", 0))

    return audio_path


@pytest.fixture(autouse=True)
def reset_singletons():
    """
    Reset singleton instances between tests to avoid state leakage.

    This fixture runs automatically for every test.
    """
    # Import here to avoid circular dependencies
    from knowledge_system.core import llm_adapter

    # Reset LLM adapter singleton
    if hasattr(llm_adapter, "_instance"):
        llm_adapter._instance = None

    yield

    # Cleanup after test
    if hasattr(llm_adapter, "_instance"):
        llm_adapter._instance = None


@pytest.fixture
def mock_llm_response():
    """
    Provide a mock LLM response for testing.
    """
    return {
        "content": "This is a test response from the LLM.",
        "usage": {
            "prompt_tokens": 50,
            "completion_tokens": 100,
            "total_tokens": 150,
        },
        "model": "test-model",
        "finish_reason": "stop",
    }


@pytest.fixture
def sample_claims_v2():
    """
    Provide sample claims in v2 schema format for testing.
    """
    return {
        "claims": [
            {
                "claim_text": "The Earth orbits around the Sun",
                "claim_type": "factual",
                "domain": "astronomy",
                "stance": "asserts",
                "evidence_spans": [
                    {
                        "segment_id": "seg_001",
                        "quote": "The Earth orbits around the Sun",
                        "t0": "00:01:23",
                        "t1": "00:01:28",
                        "context_text": "In our solar system, the Earth orbits around the Sun in an elliptical path.",
                        "context_type": "extended",
                    }
                ],
            }
        ],
        "jargon": [
            {
                "term": "elliptical path",
                "definition": "An oval-shaped orbital trajectory",
                "domain": "astronomy",
                "evidence_spans": [
                    {
                        "segment_id": "seg_001",
                        "quote": "elliptical path",
                        "t0": "00:01:28",
                        "t1": "00:01:30",
                        "context_text": "The Earth orbits in an elliptical path around the Sun.",
                    }
                ],
            }
        ],
        "people": [
            {
                "name": "Johannes Kepler",
                "role": "astronomer",
                "domain": "astronomy",
                "evidence_spans": [
                    {
                        "segment_id": "seg_002",
                        "quote": "Johannes Kepler discovered the laws of planetary motion",
                        "t0": "00:02:00",
                        "t1": "00:02:05",
                        "context_text": "The famous astronomer Johannes Kepler discovered the laws of planetary motion.",
                    }
                ],
            }
        ],
        "concepts": [
            {
                "concept": "orbital mechanics",
                "description": "The study of how objects move in space under gravitational forces",
                "domain": "physics",
                "evidence_spans": [
                    {
                        "segment_id": "seg_003",
                        "quote": "orbital mechanics explains planetary motion",
                        "t0": "00:03:00",
                        "t1": "00:03:05",
                        "context_text": "The field of orbital mechanics explains how planets move around stars.",
                    }
                ],
            }
        ],
    }
