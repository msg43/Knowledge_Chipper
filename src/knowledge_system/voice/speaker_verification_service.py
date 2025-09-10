"""
Speaker Verification Service

High-level service that integrates voice fingerprinting with the existing
speaker identification system for enhanced accuracy.
"""

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..database.speaker_models import SpeakerDatabaseService
from ..logger import get_logger
from .voice_fingerprinting import (
    VoiceFingerprintProcessor,
    load_audio_for_voice_processing,
)

logger = get_logger(__name__)


class SpeakerVerificationService:
    """High-level service for advanced speaker verification and enrollment."""

    def __init__(self, confidence_threshold: float = 0.85):
        self.confidence_threshold = confidence_threshold
        self.voice_processor = VoiceFingerprintProcessor()
        self.db_service = SpeakerDatabaseService()

    def enroll_speaker_from_file(
        self, speaker_name: str, audio_file: Path, segment_length: float = 10.0
    ) -> bool:
        """
        Enroll a speaker from an audio file by extracting multiple segments.

        Args:
            speaker_name: Name of the speaker to enroll
            audio_file: Path to the audio file
            segment_length: Length of each segment in seconds for enrollment

        Returns:
            True if enrollment successful, False otherwise
        """
        try:
            logger.info(f"Enrolling speaker '{speaker_name}' from {audio_file}")

            # Load audio
            audio = load_audio_for_voice_processing(audio_file)
            sample_rate = 16000  # Our target sample rate

            # Split into segments for robust enrollment
            segments = self._split_audio_into_segments(
                audio, sample_rate, segment_length
            )

            if len(segments) < 2:
                logger.warning(
                    f"Audio too short for robust enrollment (need at least {segment_length*2}s)"
                )
                # Still try with what we have
                segments = [audio]

            # Enroll with the voice processor
            success = self.voice_processor.enroll_speaker(speaker_name, segments)

            if success:
                logger.info(
                    f"✅ Successfully enrolled speaker '{speaker_name}' with {len(segments)} segments"
                )
            else:
                logger.error(f"❌ Failed to enroll speaker '{speaker_name}'")

            return success

        except Exception as e:
            logger.error(f"Error enrolling speaker from file: {e}")
            return False

    def verify_speaker_from_segments(
        self,
        candidate_name: str,
        diarization_segments: list[dict[str, Any]],
        audio_file: Path,
    ) -> tuple[bool, float, dict[str, Any]]:
        """
        Verify a speaker using diarization segments from an audio file.

        Args:
            candidate_name: Name of the candidate speaker
            diarization_segments: List of diarization segments with start/end times
            audio_file: Path to the audio file

        Returns:
            Tuple of (is_match, confidence, verification_details)
        """
        try:
            logger.info(
                f"Verifying speaker '{candidate_name}' using {len(diarization_segments)} segments"
            )

            # Load full audio
            full_audio = load_audio_for_voice_processing(audio_file)
            sample_rate = 16000

            # Extract audio segments based on diarization timestamps
            audio_segments = []
            for seg in diarization_segments:
                start_time = float(seg.get("start", 0))
                end_time = float(seg.get("end", 0))

                start_sample = int(start_time * sample_rate)
                end_sample = int(end_time * sample_rate)

                if start_sample < len(full_audio) and end_sample <= len(full_audio):
                    segment_audio = full_audio[start_sample:end_sample]
                    if len(segment_audio) > sample_rate * 0.5:  # At least 0.5 seconds
                        audio_segments.append(segment_audio)

            if not audio_segments:
                logger.warning("No valid audio segments extracted for verification")
                return False, 0.0, {"error": "no_valid_segments"}

            # Verify against each segment and get average confidence
            confidences = []
            verifications = []

            for i, segment in enumerate(audio_segments):
                is_match, confidence = self.voice_processor.verify_speaker(
                    segment, candidate_name, self.confidence_threshold
                )
                confidences.append(confidence)
                verifications.append(is_match)

                logger.debug(
                    f"Segment {i+1}: confidence={confidence:.3f}, match={is_match}"
                )

            # Calculate overall results
            avg_confidence = np.mean(confidences) if confidences else 0.0
            max_confidence = np.max(confidences) if confidences else 0.0
            match_ratio = (
                sum(verifications) / len(verifications) if verifications else 0.0
            )

            # Overall verification decision
            is_overall_match = (
                avg_confidence >= self.confidence_threshold and match_ratio >= 0.6
            )

            verification_details = {
                "segments_processed": len(audio_segments),
                "average_confidence": avg_confidence,
                "max_confidence": max_confidence,
                "match_ratio": match_ratio,
                "individual_confidences": confidences,
                "individual_matches": verifications,
                "threshold_used": self.confidence_threshold,
            }

            logger.info(
                f"Speaker verification result: {is_overall_match} (avg confidence: {avg_confidence:.3f})"
            )
            return is_overall_match, avg_confidence, verification_details

        except Exception as e:
            logger.error(f"Error during speaker verification: {e}")
            return False, 0.0, {"error": str(e)}

    def batch_verify_speakers(
        self, candidates: dict[str, list[dict[str, Any]]], audio_file: Path
    ) -> dict[str, tuple[bool, float, dict[str, Any]]]:
        """
        Verify multiple speakers in batch from their diarization segments.

        Args:
            candidates: Dict mapping speaker names to their diarization segments
            audio_file: Path to the audio file

        Returns:
            Dict mapping speaker names to verification results
        """
        results = {}

        for speaker_name, segments in candidates.items():
            logger.info(f"Batch verifying speaker: {speaker_name}")
            results[speaker_name] = self.verify_speaker_from_segments(
                speaker_name, segments, audio_file
            )

        return results

    def suggest_speaker_matches(
        self,
        diarization_segments: list[dict[str, Any]],
        audio_file: Path,
        top_k: int = 3,
    ) -> list[tuple[str, float]]:
        """
        Suggest the most likely speaker matches from enrolled speakers.

        Args:
            diarization_segments: List of diarization segments
            audio_file: Path to the audio file
            top_k: Number of top suggestions to return

        Returns:
            List of (speaker_name, confidence) tuples sorted by confidence
        """
        try:
            # TODO: This requires implementing get_all_speakers in database service
            logger.warning("Speaker suggestion requires database service enhancement")
            return []

        except Exception as e:
            logger.error(f"Error suggesting speaker matches: {e}")
            return []

    def _split_audio_into_segments(
        self, audio: np.ndarray, sample_rate: int, segment_length: float
    ) -> list[np.ndarray]:
        """Split audio into segments of specified length."""
        segment_samples = int(segment_length * sample_rate)
        segments = []

        for start in range(0, len(audio), segment_samples):
            end = min(start + segment_samples, len(audio))
            segment = audio[start:end]

            # Only keep segments that are at least half the target length
            if len(segment) >= segment_samples // 2:
                segments.append(segment)

        return segments

    async def enroll_speaker_async(self, speaker_name: str, audio_file: Path) -> bool:
        """Async version of speaker enrollment."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.enroll_speaker_from_file, speaker_name, audio_file
        )

    async def verify_speaker_async(
        self,
        candidate_name: str,
        diarization_segments: list[dict[str, Any]],
        audio_file: Path,
    ) -> tuple[bool, float, dict[str, Any]]:
        """Async version of speaker verification."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.verify_speaker_from_segments,
            candidate_name,
            diarization_segments,
            audio_file,
        )


# Factory function
def create_speaker_verification_service(
    confidence_threshold: float = 0.85,
) -> SpeakerVerificationService:
    """Create a speaker verification service with specified confidence threshold."""
    return SpeakerVerificationService(confidence_threshold=confidence_threshold)
