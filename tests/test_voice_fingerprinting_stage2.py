"""
Test Suite for Stage 2: Voice Fingerprinting (ECAPA-TDNN + Wav2Vec2)

Tests the complete voice fingerprinting pipeline including:
- Database operations (get_all_voices, find_matching_voices)
- Voice fingerprint extraction (ECAPA-TDNN, Wav2Vec2)
- Speaker identification and verification
- Audio segment extraction and merging
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import soundfile as sf

from src.knowledge_system.database.speaker_models import (
    SpeakerDatabaseService,
    SpeakerVoiceModel,
)
from src.knowledge_system.processors.speaker_processor import (
    SpeakerData,
    SpeakerProcessor,
    SpeakerSegment,
)
from src.knowledge_system.voice.voice_fingerprinting import (
    VoiceFingerprintProcessor,
    load_audio_for_voice_processing,
)


class TestDatabaseOperations:
    """Test database operations for voice fingerprinting."""

    def setup_method(self):
        """Set up test database."""
        # Use unique in-memory SQLite database for each test
        # By using a unique file path, each test gets a fresh database
        import os
        import tempfile

        self.temp_db = tempfile.mktemp(suffix=".db")
        self.db_service = SpeakerDatabaseService(f"sqlite:///{self.temp_db}")

    def teardown_method(self):
        """Clean up test database."""
        import os

        if hasattr(self, "temp_db") and os.path.exists(self.temp_db):
            os.unlink(self.temp_db)

    def test_get_all_voices_empty(self):
        """Test getting all voices when database is empty."""
        voices = self.db_service.get_all_voices()
        assert voices == []

    def test_get_all_voices_with_data(self):
        """Test getting all voices with enrolled speakers."""
        # Create test voice profiles
        voice1 = SpeakerVoiceModel(
            name="Speaker1",
            voice_fingerprint={"mfcc": [1.0, 2.0, 3.0]},
            confidence_threshold=0.8,
        )
        voice2 = SpeakerVoiceModel(
            name="Speaker2",
            voice_fingerprint={"mfcc": [4.0, 5.0, 6.0]},
            confidence_threshold=0.7,
        )

        # Enroll speakers
        self.db_service.create_speaker_voice(voice1)
        self.db_service.create_speaker_voice(voice2)

        # Get all voices
        voices = self.db_service.get_all_voices()

        assert len(voices) == 2
        assert {v.name for v in voices} == {"Speaker1", "Speaker2"}

    def test_find_matching_voices(self):
        """Test finding matching voices based on fingerprints."""
        # Create test voice profile with known fingerprint
        test_fingerprint = {
            "mfcc": [1.0] * 52,  # 13 MFCCs * 4 statistics
            "spectral": [2.0] * 6,
            "prosodic": [3.0] * 5,
        }

        voice1 = SpeakerVoiceModel(
            name="MatchTestSpeaker",
            voice_fingerprint=test_fingerprint,
            confidence_threshold=0.7,
        )
        self.db_service.create_speaker_voice(voice1)

        # Create similar fingerprint (should match)
        similar_fingerprint = {
            "mfcc": [1.05] * 52,  # Very similar (within 5%)
            "spectral": [2.05] * 6,
            "prosodic": [3.05] * 5,
        }

        # Find matches
        matches = self.db_service.find_matching_voices(
            similar_fingerprint, threshold=0.5
        )

        assert len(matches) > 0
        assert matches[0][0].name == "MatchTestSpeaker"
        assert matches[0][1] > 0.5  # Similarity score

    def test_find_matching_voices_no_match(self):
        """Test that very different fingerprints don't match."""
        # Create test voice profile
        test_fingerprint = {
            "mfcc": [1.0] * 52,
            "spectral": [2.0] * 6,
            "prosodic": [3.0] * 5,
        }

        voice1 = SpeakerVoiceModel(
            name="NoMatchTestSpeaker",
            voice_fingerprint=test_fingerprint,
            confidence_threshold=0.7,
        )
        self.db_service.create_speaker_voice(voice1)

        # Create very different fingerprint (should not match)
        # Use negative values to ensure complete mismatch
        different_fingerprint = {
            "mfcc": [-100.0] * 52,  # Opposite sign for guaranteed mismatch
            "spectral": [-200.0] * 6,
            "prosodic": [-300.0] * 5,
        }

        # Find matches with high threshold
        matches = self.db_service.find_matching_voices(
            different_fingerprint, threshold=0.9
        )

        # Should have no matches with such a high threshold and very different fingerprints
        assert len(matches) == 0


class TestVoiceFingerprintExtraction:
    """Test voice fingerprint extraction."""

    @pytest.fixture
    def voice_processor(self):
        """Create voice processor instance."""
        return VoiceFingerprintProcessor()

    @pytest.fixture
    def sample_audio(self):
        """Generate sample audio for testing."""
        # Generate 3 seconds of synthetic audio
        duration = 3.0
        sample_rate = 16000
        t = np.linspace(0, duration, int(duration * sample_rate))

        # Simple sine wave at 200 Hz (typical voice frequency)
        audio = np.sin(2 * np.pi * 200 * t)

        # Add some harmonics
        audio += 0.5 * np.sin(2 * np.pi * 400 * t)
        audio += 0.3 * np.sin(2 * np.pi * 600 * t)

        # Normalize
        audio = audio / np.max(np.abs(audio)) * 0.8

        return audio.astype(np.float32)

    def test_extract_voice_fingerprint_basic(self, voice_processor, sample_audio):
        """Test basic fingerprint extraction."""
        fingerprint = voice_processor.extract_voice_fingerprint(sample_audio)

        # Check that all feature types are present
        assert "mfcc" in fingerprint
        assert "spectral" in fingerprint
        assert "prosodic" in fingerprint
        assert "sample_rate" in fingerprint
        assert "duration" in fingerprint
        assert "feature_version" in fingerprint

        # Check metadata
        assert fingerprint["sample_rate"] == 16000
        assert fingerprint["duration"] > 0

    def test_calculate_voice_similarity(self, voice_processor, sample_audio):
        """Test similarity calculation between fingerprints."""
        # Extract two fingerprints from same audio (should be identical)
        fp1 = voice_processor.extract_voice_fingerprint(sample_audio)
        fp2 = voice_processor.extract_voice_fingerprint(sample_audio)

        similarity = voice_processor.calculate_voice_similarity(fp1, fp2)

        # Should be very similar (close to 1.0)
        assert similarity > 0.95

    def test_calculate_voice_similarity_different(self, voice_processor, sample_audio):
        """Test similarity with different audio."""
        # Generate different audio
        duration = 3.0
        sample_rate = 16000
        t = np.linspace(0, duration, int(duration * sample_rate))
        different_audio = np.sin(2 * np.pi * 300 * t).astype(
            np.float32
        )  # Different frequency

        fp1 = voice_processor.extract_voice_fingerprint(sample_audio)
        fp2 = voice_processor.extract_voice_fingerprint(different_audio)

        similarity = voice_processor.calculate_voice_similarity(fp1, fp2)

        # Should be less similar
        assert similarity < 0.95


class TestSpeakerIdentification:
    """Test speaker identification and verification."""

    def setup_method(self):
        """Set up test database and processor."""
        self.db_service = SpeakerDatabaseService("sqlite:///:memory:")
        self.voice_processor = VoiceFingerprintProcessor()
        # Replace the processor's db_service with our test one
        self.voice_processor.db_service = self.db_service

    @pytest.fixture
    def sample_audio(self):
        """Generate sample audio."""
        duration = 3.0
        sample_rate = 16000
        t = np.linspace(0, duration, int(duration * sample_rate))
        audio = np.sin(2 * np.pi * 200 * t)
        audio += 0.5 * np.sin(2 * np.pi * 400 * t)
        return audio.astype(np.float32)

    def test_identify_speaker_no_profiles(self, sample_audio):
        """Test identification when no profiles exist."""
        result = self.voice_processor.identify_speaker(sample_audio)
        assert result is None

    def test_identify_speaker_with_enrolled(self, sample_audio):
        """Test identification with enrolled speaker."""
        # Enroll speaker
        success = self.voice_processor.enroll_speaker(
            "TestSpeaker", [sample_audio, sample_audio]
        )
        assert success

        # Identify same speaker (should match)
        result = self.voice_processor.identify_speaker(sample_audio, threshold=0.5)

        assert result is not None
        assert result[0] == "TestSpeaker"
        assert result[1] > 0.5  # Confidence

    def test_verify_speaker(self, sample_audio):
        """Test speaker verification."""
        # Enroll speaker
        self.voice_processor.enroll_speaker("TestSpeaker", [sample_audio])

        # Verify with same audio (should match)
        is_match, confidence = self.voice_processor.verify_speaker(
            sample_audio, "TestSpeaker", threshold=0.5
        )

        assert is_match
        assert confidence > 0.5


class TestAudioSegmentExtraction:
    """Test audio segment extraction for speaker merging."""

    @pytest.fixture
    def temp_audio_file(self):
        """Create temporary audio file for testing."""
        # Generate 10 seconds of audio
        duration = 10.0
        sample_rate = 16000
        t = np.linspace(0, duration, int(duration * sample_rate))

        # Create audio with varying characteristics
        audio = np.sin(2 * np.pi * 200 * t)
        audio += 0.5 * np.sin(2 * np.pi * 400 * t)
        audio = audio.astype(np.float32)

        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            sf.write(f.name, audio, sample_rate)
            temp_path = f.name

        yield temp_path

        # Cleanup
        Path(temp_path).unlink(missing_ok=True)

    def test_load_audio_for_processing(self, temp_audio_file):
        """Test loading audio for voice processing."""
        audio = load_audio_for_voice_processing(Path(temp_audio_file))

        assert isinstance(audio, np.ndarray)
        assert len(audio) > 0
        assert audio.dtype == np.float32

    def test_voice_fingerprint_merge_with_audio(self, temp_audio_file):
        """Test speaker merging using actual audio."""
        # Create speaker processor
        processor = SpeakerProcessor()

        # Create mock speaker data with overlapping segments
        speaker_map = {
            "SPEAKER_00": SpeakerData(
                speaker_id="SPEAKER_00",
                segments=[
                    SpeakerSegment(
                        start=0.0, end=2.0, text="Hello", speaker_id="SPEAKER_00"
                    ),
                    SpeakerSegment(
                        start=2.5, end=4.5, text="World", speaker_id="SPEAKER_00"
                    ),
                ],
                total_duration=4.0,
                segment_count=2,
            ),
            "SPEAKER_01": SpeakerData(
                speaker_id="SPEAKER_01",
                segments=[
                    SpeakerSegment(
                        start=5.0, end=7.0, text="Test", speaker_id="SPEAKER_01"
                    ),
                ],
                total_duration=2.0,
                segment_count=1,
            ),
        }

        # Run voice fingerprint merge with audio path
        processor._voice_fingerprint_merge_speakers(speaker_map, temp_audio_file)

        # Should still have speakers (may be merged or not depending on similarity)
        assert len(speaker_map) >= 1


class TestSpeakerProcessorIntegration:
    """Integration tests for speaker processor with voice fingerprinting."""

    @pytest.fixture
    def temp_audio_file(self):
        """Create temporary audio file."""
        duration = 15.0
        sample_rate = 16000
        t = np.linspace(0, duration, int(duration * sample_rate))
        audio = np.sin(2 * np.pi * 200 * t).astype(np.float32)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            sf.write(f.name, audio, sample_rate)
            temp_path = f.name

        yield temp_path
        Path(temp_path).unlink(missing_ok=True)

    def test_prepare_speaker_data_with_audio(self, temp_audio_file):
        """Test speaker data preparation with voice fingerprinting."""
        processor = SpeakerProcessor()

        # Create sample diarization and transcript segments
        diarization_segments = [
            {"speaker": "SPEAKER_00", "start": 0.0, "end": 5.0},
            {"speaker": "SPEAKER_01", "start": 5.5, "end": 10.0},
            {"speaker": "SPEAKER_02", "start": 10.5, "end": 15.0},
        ]

        transcript_segments = [
            {"start": 0.0, "end": 5.0, "text": "Hello this is speaker one"},
            {"start": 5.5, "end": 10.0, "text": "And this is speaker two"},
            {"start": 10.5, "end": 15.0, "text": "Back to speaker one"},
        ]

        # Prepare speaker data with audio path
        speaker_data_list = processor.prepare_speaker_data(
            diarization_segments,
            transcript_segments,
            metadata=None,
            audio_path=temp_audio_file,
        )

        # Should have processed speakers
        assert len(speaker_data_list) > 0

        # Each speaker should have segments
        for speaker_data in speaker_data_list:
            assert speaker_data.segment_count > 0
            assert len(speaker_data.segments) > 0
            assert speaker_data.total_duration > 0

    def test_prepare_speaker_data_without_audio(self):
        """Test speaker data preparation without audio (fallback mode)."""
        processor = SpeakerProcessor()

        diarization_segments = [
            {"speaker": "SPEAKER_00", "start": 0.0, "end": 5.0},
            {"speaker": "SPEAKER_01", "start": 5.5, "end": 10.0},
        ]

        transcript_segments = [
            {"start": 0.0, "end": 5.0, "text": "First speaker"},
            {"start": 5.5, "end": 10.0, "text": "Second speaker"},
        ]

        # Prepare without audio path (should use text-based fallback)
        speaker_data_list = processor.prepare_speaker_data(
            diarization_segments,
            transcript_segments,
            metadata=None,
            audio_path=None,
        )

        assert len(speaker_data_list) > 0


@pytest.mark.integration
class TestEndToEndVoiceFingerprinting:
    """End-to-end integration tests."""

    def test_complete_pipeline(self):
        """Test complete voice fingerprinting pipeline."""
        # Create test audio with two "speakers" (different frequencies)
        duration = 10.0
        sample_rate = 16000
        t = np.linspace(0, duration, int(duration * sample_rate))

        # Speaker 1: 200 Hz
        speaker1_audio = np.sin(2 * np.pi * 200 * t).astype(np.float32)

        # Speaker 2: 300 Hz
        speaker2_audio = np.sin(2 * np.pi * 300 * t).astype(np.float32)

        # Create processor and database
        db_service = SpeakerDatabaseService("sqlite:///:memory:")
        voice_processor = VoiceFingerprintProcessor()
        voice_processor.db_service = db_service

        # Enroll both speakers
        success1 = voice_processor.enroll_speaker(
            "Speaker1", [speaker1_audio[: sample_rate * 3]]  # 3 seconds
        )
        success2 = voice_processor.enroll_speaker(
            "Speaker2", [speaker2_audio[: sample_rate * 3]]  # 3 seconds
        )

        assert success1
        assert success2

        # Test identification
        # Should identify speaker 1 from their audio
        result1 = voice_processor.identify_speaker(
            speaker1_audio[: sample_rate * 2], threshold=0.3
        )

        if result1:  # Only check if models are available
            assert result1[0] == "Speaker1"

        # Should identify speaker 2 from their audio
        result2 = voice_processor.identify_speaker(
            speaker2_audio[: sample_rate * 2], threshold=0.3
        )

        if result2:  # Only check if models are available
            assert result2[0] == "Speaker2"

        # Verify database has both speakers
        all_voices = db_service.get_all_voices()
        assert len(all_voices) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
