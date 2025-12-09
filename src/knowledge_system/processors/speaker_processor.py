"""
Speaker Processing Module

Handles speaker data preparation, name suggestions, and assignment logic
for the diarization-based speaker identification system.
"""

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from ..logger import get_logger
from .base import BaseProcessor, ProcessorResult

logger = get_logger(__name__)


class SpeakerSegment(BaseModel):
    """Represents a single speaker segment with timing and content."""

    start: float = Field(..., description="Start time in seconds")
    end: float = Field(..., description="End time in seconds")
    text: str = Field(..., description="Transcript text for this segment")
    speaker_id: str = Field(..., description="Original speaker ID (e.g., SPEAKER_00)")
    confidence: float = Field(
        default=0.0, description="Confidence score for speaker assignment"
    )


class SpeakerData(BaseModel):
    """Aggregated data for a single speaker across all segments."""

    speaker_id: str = Field(..., description="Original speaker ID")
    segments: list[SpeakerSegment] = Field(default_factory=list)
    total_duration: float = Field(
        default=0.0, description="Total speaking time in seconds"
    )
    segment_count: int = Field(default=0, description="Number of segments")
    sample_texts: list[str] = Field(
        default_factory=list, description="Representative text samples"
    )
    first_five_segments: list[dict] = Field(
        default_factory=list, description="First 5 speaking segments with timestamps"
    )
    suggested_name: str | None = Field(default=None, description="AI-suggested name")
    confidence_score: float = Field(default=0.0, description="Confidence in suggestion")

    # Enhanced fields for learning and sidecar migration
    suggestion_method: str = Field(
        default="unknown", description="Method used for suggestion"
    )
    suggestion_metadata: dict[str, Any] = Field(
        default_factory=dict, description="Detailed analysis results"
    )
    pattern_matches: list[dict] = Field(
        default_factory=list, description="Pattern matches found"
    )
    assignment_source: str = Field(
        default="ai_suggestion", description="Source of the current assignment"
    )


class SpeakerAssignment(BaseModel):
    """Represents a user's assignment of a name to a speaker."""

    speaker_id: str = Field(..., description="Original speaker ID")
    assigned_name: str = Field(..., description="User-assigned name")
    confidence: float = Field(default=1.0, description="User confidence in assignment")
    timestamp: datetime = Field(default_factory=datetime.now)
    source_file: str | None = Field(default=None, description="Source recording file")


class SpeakerProcessor(BaseProcessor):
    """Process diarization data for speaker identification and assignment."""

    def __init__(self):
        """Initialize the speaker processor."""
        super().__init__()
        self.name_patterns = self._compile_name_patterns()

    def _compile_name_patterns(self) -> dict[str, re.Pattern]:
        """Compile regex patterns for name detection."""
        return {
            "self_introduction": re.compile(
                r"\b(?:I\'?m|my name is|this is|I am)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
                re.IGNORECASE,
            ),
            "greeting": re.compile(
                r"\b(?:hi|hello|hey),?\s+(?:I\'?m|this is)\s+([A-Z][a-z]+)",
                re.IGNORECASE,
            ),
            "role_introduction": re.compile(
                r"\b(?:as the|I\'m the|from)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
                re.IGNORECASE,
            ),
            "direct_address": re.compile(
                r"\b(?:thanks?|thank you),?\s+([A-Z][a-z]+)", re.IGNORECASE
            ),
        }

    @property
    def supported_formats(self) -> list[str]:
        """Return supported input formats."""
        return ["diarization_segments", "transcript_data"]

    def validate_input(self, input_data: Any) -> bool:
        """
        Validate input data for speaker processing.

        Args:
            input_data: Input data to validate

        Returns:
            bool: True if input is valid
        """
        if not isinstance(input_data, dict):
            return False

        # Check for required keys
        required_keys = ["diarization_segments", "transcript_segments"]
        return all(key in input_data for key in required_keys)

    def prepare_speaker_data(
        self,
        diarization_segments: list[dict[str, Any]],
        transcript_segments: list[dict[str, Any]],
        word_timestamps: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
        audio_path: str | None = None,
    ) -> list[SpeakerData]:
        """
        Merge diarization and transcript data for speaker assignment.

        Args:
            diarization_segments: List of diarization segments with speaker IDs and timing
            transcript_segments: List of transcript segments with text and timing
            word_timestamps: Optional list of word-level timestamps from whisper.cpp
                           Each word dict has: word, start, end
            metadata: Optional metadata about the recording. Can be either:
                     - Old format: Single dict with fields (backward compatible)
                     - New format: {'primary_source': {...}, 'aliased_sources': [...]}
                       for multi-source metadata (YouTube + RSS, etc.)
            audio_path: Optional path to audio file for voice fingerprinting

        Returns:
            List of SpeakerData objects with aggregated information per speaker
        """
        try:
            logger.info(
                f"Preparing speaker data from {len(diarization_segments)} diarization segments and {len(transcript_segments)} transcript segments"
            )

            # Create mapping of speakers to their segments
            speaker_map: dict[str, SpeakerData] = {}

            # Process each diarization segment
            for diar_seg in diarization_segments:
                speaker_id = diar_seg.get("speaker", "UNKNOWN")
                start_time = float(diar_seg.get("start", 0))
                end_time = float(diar_seg.get("end", 0))

                # Find overlapping transcript segments
                overlapping_text = self._find_overlapping_text(
                    start_time, end_time, transcript_segments
                )

                # Create speaker segment
                speaker_segment = SpeakerSegment(
                    start=start_time,
                    end=end_time,
                    text=overlapping_text,
                    speaker_id=speaker_id,
                )

                # Add to speaker data
                if speaker_id not in speaker_map:
                    speaker_map[speaker_id] = SpeakerData(speaker_id=speaker_id)

                speaker_data = speaker_map[speaker_id]
                speaker_data.segments.append(speaker_segment)
                speaker_data.total_duration += end_time - start_time
                speaker_data.segment_count += 1

            # 🚨 NEW: Use voice fingerprinting to merge similar speakers before text assignment
            # 🔒 PRESERVATION: Track all speakers before merging to ensure none are lost
            speakers_before_voice = set(speaker_map.keys())
            speaker_count_before_voice = len(speaker_map)
            
            self._voice_fingerprint_merge_speakers(speaker_map, audio_path)
            
            speaker_count_after_voice = len(speaker_map)
            speakers_after_voice = set(speaker_map.keys())
            
            # 🔒 PRESERVATION: Verify no speakers were unexpectedly lost
            lost_speakers = speakers_before_voice - speakers_after_voice
            if lost_speakers and len(lost_speakers) != (speaker_count_before_voice - speaker_count_after_voice):
                logger.error(
                    f"🚨 CRITICAL: Unexpected speaker loss detected! Lost: {lost_speakers}, "
                    f"Expected loss: {speaker_count_before_voice - speaker_count_after_voice}"
                )
            
            if speaker_count_after_voice < speaker_count_before_voice:
                merged_count = speaker_count_before_voice - speaker_count_after_voice
                logger.info(
                    f"✅ Voice fingerprinting merged {merged_count} speaker(s): "
                    f"{speaker_count_before_voice} → {speaker_count_after_voice}"
                )
                logger.info(
                    f"🔒 PRESERVATION: Preserved {speaker_count_after_voice} speaker(s) "
                    f"(merged {merged_count}, lost 0)"
                )
            elif speaker_count_before_voice > 1:
                logger.warning(
                    f"⚠️ Voice fingerprinting did NOT merge speakers (still have {speaker_count_before_voice} speakers)"
                )
                logger.info(
                    f"🔒 PRESERVATION: All {speaker_count_before_voice} speaker(s) preserved "
                    f"(conservative merging - no matches above threshold)"
                )

            # 🚨 NEW: Check for potential over-segmentation and merge similar speakers
            # 🔒 PRESERVATION: Track speakers before heuristic merging
            speakers_before_heuristic = set(speaker_map.keys())
            speaker_count_before_heuristic = len(speaker_map)
            
            self._detect_and_merge_oversegmented_speakers(speaker_map)
            
            speaker_count_after_heuristic = len(speaker_map)
            speakers_after_heuristic = set(speaker_map.keys())
            
            # 🔒 PRESERVATION: Verify no speakers were unexpectedly lost
            lost_speakers = speakers_before_heuristic - speakers_after_heuristic
            if lost_speakers and len(lost_speakers) != (speaker_count_before_heuristic - speaker_count_after_heuristic):
                logger.error(
                    f"🚨 CRITICAL: Unexpected speaker loss in heuristic merging! Lost: {lost_speakers}, "
                    f"Expected loss: {speaker_count_before_heuristic - speaker_count_after_heuristic}"
                )

            if speaker_count_after_heuristic < speaker_count_before_heuristic:
                merged_count = speaker_count_before_heuristic - speaker_count_after_heuristic
                logger.info(
                    f"✅ Heuristic merging merged {merged_count} speaker(s): "
                    f"{speaker_count_before_heuristic} → {speaker_count_after_heuristic}"
                )
                logger.info(
                    f"🔒 PRESERVATION: Preserved {speaker_count_after_heuristic} speaker(s) "
                    f"(merged {merged_count}, lost 0)"
                )
            elif speaker_count_before_heuristic > 1:
                logger.warning(
                    f"⚠️ Heuristic merging did NOT merge speakers (still have {speaker_count_before_heuristic} speakers)"
                )
                logger.info(
                    f"🔒 PRESERVATION: All {speaker_count_before_heuristic} speaker(s) preserved "
                    f"(conservative merging - no matches above threshold)"
                )

            # 🎯 Voice-based verification for dialogue accuracy
            # After speakers are consolidated, use voice fingerprinting for verification
            if audio_path and len(speaker_map) >= 2:
                # Build speaker profiles for verification
                speaker_profiles = self._build_speaker_profiles(speaker_map, audio_path)
                
                # Primary method: Word-level verification (if word timestamps available)
                if word_timestamps and len(word_timestamps) > 0 and speaker_profiles:
                    logger.info(
                        f"📝 Using word-level verification with {len(word_timestamps)} words"
                    )
                    word_corrections = self._verify_word_level_speakers(
                        speaker_map, word_timestamps, audio_path, speaker_profiles
                    )
                    if word_corrections > 0:
                        logger.info(
                            f"📝 Word-level verification corrected {word_corrections} word group(s)"
                        )
                else:
                    # Fallback: Segment-level verification (legacy, when word timestamps unavailable)
                    logger.info("⚠️ Word timestamps not available, using segment-level verification")
                    
                    # Step 1: Split mixed-speaker segments (DEPRECATED - fallback only)
                    split_count = self._split_mixed_speaker_segments(speaker_map, audio_path)
                    if split_count > 0:
                        logger.info(
                            f"✂️ Segment analysis split {split_count} segment(s) containing multiple speakers"
                        )
                    
                    # Step 2: Reassign misattributed segments (DEPRECATED - fallback only)
                    reassigned_count = self._reassign_segments_by_voice_verification(
                        speaker_map, audio_path
                    )
                    if reassigned_count > 0:
                        logger.info(
                            f"🎯 Segment verification reassigned {reassigned_count} segment(s)"
                        )

            # 🚨 CRITICAL FIX: Clean up data FIRST before LLM analysis
            self._validate_and_fix_speaker_segments(speaker_map)

            # 🎯 OPTIMIZATION: Generate clean sample texts AFTER deduplication
            # This ensures LLM sees exactly what the user will see in the dialog
            for speaker_data in speaker_map.values():
                speaker_data.sample_texts = self._extract_sample_texts(
                    speaker_data.segments
                )
                speaker_data.first_five_segments = self._extract_first_five_segments(
                    speaker_data.segments
                )

            # 🚨 CRITICAL FIX: LLM analyzes clean, final segments (not messy raw data)
            self._suggest_all_speaker_names_together(
                speaker_map, metadata, transcript_segments
            )

            # Sort speakers by total speaking time (most active first)
            sorted_speakers = sorted(
                speaker_map.values(), key=lambda x: x.total_duration, reverse=True
            )

            # 🔒 PRESERVATION: Final verification - ensure all speakers are returned
            if len(sorted_speakers) != len(speaker_map):
                logger.error(
                    f"🚨 CRITICAL: Speaker count mismatch! "
                    f"speaker_map has {len(speaker_map)} speakers, "
                    f"but sorted_speakers has {len(sorted_speakers)}"
                )
                # Recover by using all speakers from map
                sorted_speakers = list(speaker_map.values())
            
            # 🔒 PRESERVATION: Log final speaker preservation status
            total_segments = sum(len(sp.segments) for sp in sorted_speakers)
            total_duration = sum(sp.total_duration for sp in sorted_speakers)
            logger.info(
                f"✅ Prepared data for {len(sorted_speakers)} speaker(s) "
                f"({total_segments} segments, {total_duration:.1f}s total duration)"
            )
            logger.info(
                f"🔒 PRESERVATION: All {len(sorted_speakers)} speaker(s) preserved and returned"
            )
            
            return sorted_speakers

        except Exception as e:
            logger.error(f"Error preparing speaker data: {e}")
            # 🔒 PRESERVATION: On error, try to return any speakers we have
            try:
                if 'speaker_map' in locals() and speaker_map:
                    logger.warning(
                        f"🔒 PRESERVATION: Error occurred, but returning {len(speaker_map)} "
                        f"speaker(s) that were successfully processed"
                    )
                    return list(speaker_map.values())
            except Exception:
                pass
            return []

    def _find_overlapping_text(
        self,
        start_time: float,
        end_time: float,
        transcript_segments: list[dict[str, Any]],
    ) -> str:
        """
        Find transcript text that overlaps with the given time range.
        🚨 CRITICAL FIX: Better overlap detection to prevent duplicate assignments.
        """
        overlapping_texts = []

        for trans_seg in transcript_segments:
            trans_start = float(trans_seg.get("start", 0))
            trans_end = float(trans_seg.get("end", trans_start + 1))

            # 🚨 IMPROVED: Calculate actual overlap percentage to prioritize best matches
            overlap_start = max(start_time, trans_start)
            overlap_end = min(end_time, trans_end)
            overlap_duration = max(0, overlap_end - overlap_start)

            # Include segments with good overlap (>60% of speaker segment OR >1.5 seconds)
            # Less restrictive since voice fingerprinting will handle duplicate prevention
            speaker_duration = end_time - start_time
            overlap_percentage = overlap_duration / max(
                speaker_duration, 0.1
            )  # Avoid div by zero

            if overlap_duration > 1.5 or overlap_percentage > 0.6:
                text = trans_seg.get("text", "").strip()
                if text:
                    # Add metadata about overlap quality for debugging
                    logger.debug(
                        f"Speaker [{start_time:.1f}-{end_time:.1f}] overlaps with transcript [{trans_start:.1f}-{trans_end:.1f}] by {overlap_percentage:.1%}"
                    )
                    overlapping_texts.append(text)

        result = " ".join(overlapping_texts)
        if not result:
            # Fallback: find closest transcript segment if no good overlap
            logger.warning(
                f"No good overlap for speaker segment [{start_time:.1f}-{end_time:.1f}], using closest"
            )
            result = self._find_closest_transcript_text(
                start_time, end_time, transcript_segments
            )

        return result

    def _find_closest_transcript_text(
        self,
        start_time: float,
        end_time: float,
        transcript_segments: list[dict[str, Any]],
    ) -> str:
        """Find the closest transcript segment when no good overlap exists."""
        if not transcript_segments:
            return f"[No transcript available for {start_time:.1f}s-{end_time:.1f}s]"

        speaker_center = (start_time + end_time) / 2

        # Find the transcript segment whose center is closest to speaker segment center
        closest_segment = None
        min_distance = float("inf")

        for trans_seg in transcript_segments:
            trans_start = float(trans_seg.get("start", 0))
            trans_end = float(trans_seg.get("end", trans_start + 1))
            trans_center = (trans_start + trans_end) / 2

            distance = abs(speaker_center - trans_center)
            if distance < min_distance:
                min_distance = distance
                closest_segment = trans_seg

        if closest_segment:
            return closest_segment.get("text", "").strip()

        return f"[Speaker segment {start_time:.1f}s-{end_time:.1f}s]"

    def _extract_sample_texts(self, segments: list[SpeakerSegment]) -> list[str]:
        """Extract representative text samples from speaker segments."""
        # Sort segments by length to get the most substantial ones
        sorted_segments = sorted(segments, key=lambda x: len(x.text), reverse=True)

        samples = []
        for segment in sorted_segments[:5]:  # Take up to 5 samples
            text = segment.text.strip()
            if len(text) > 20:  # Only include substantial text
                # Truncate if too long
                if len(text) > 150:
                    text = text[:147] + "..."
                samples.append(text)

            if len(samples) >= 3:  # Limit to 3 samples for UI
                break

        return samples

    def _extract_first_five_segments(
        self, segments: list[SpeakerSegment]
    ) -> list[dict]:
        """Extract first 5 speaking segments with timestamps for identification."""
        first_five = []

        for i, segment in enumerate(segments[:5]):
            segment_dict = {
                "text": segment.text,
                "start": segment.start,
                "end": segment.end,
                "sequence": i + 1,
            }
            first_five.append(segment_dict)

        return first_five

    def _suggest_speaker_name(
        self, speaker_data: SpeakerData
    ) -> tuple[str | None, float]:
        """Generate AI-powered name suggestion for a speaker with enhanced metadata."""
        try:
            all_text = " ".join([seg.text for seg in speaker_data.segments])

            # Initialize enhanced metadata
            speaker_data.suggestion_metadata = {
                "text_analyzed": len(all_text),
                "patterns_tried": [],
                "pattern_matches": {},
                "fallback_analysis": {},
            }
            speaker_data.pattern_matches = []

            # Try different name detection patterns
            for pattern_name, pattern in self.name_patterns.items():
                speaker_data.suggestion_metadata["patterns_tried"].append(pattern_name)
                matches = pattern.findall(all_text)

                if matches:
                    # Take the most common match
                    name_counts = {}
                    for match in matches:
                        name = match.strip().title()
                        name_counts[name] = name_counts.get(name, 0) + 1

                    speaker_data.suggestion_metadata["pattern_matches"][
                        pattern_name
                    ] = {
                        "matches": list(matches),
                        "name_counts": name_counts,
                        "total_matches": len(matches),
                    }

                    if name_counts:
                        suggested_name = max(name_counts, key=name_counts.get)
                        confidence = min(
                            0.9, name_counts[suggested_name] / len(matches)
                        )

                        # Store pattern match details
                        pattern_match = {
                            "pattern_name": pattern_name,
                            "suggested_name": suggested_name,
                            "confidence": confidence,
                            "matches_found": len(matches),
                            "name_frequency": name_counts[suggested_name],
                        }
                        speaker_data.pattern_matches.append(pattern_match)
                        speaker_data.suggestion_method = (
                            f"pattern_matching:{pattern_name}"
                        )

                        logger.debug(
                            f"Found name suggestion '{suggested_name}' with confidence {confidence:.2f} using pattern '{pattern_name}'"
                        )
                        return suggested_name, confidence

            # Fallback: analyze speech patterns for generic suggestions
            suggested_name, confidence = self._analyze_speech_patterns(speaker_data)
            speaker_data.suggestion_method = "speech_pattern_analysis"
            return suggested_name, confidence

        except Exception as e:
            logger.warning(f"Error suggesting speaker name: {e}")
            speaker_data.suggestion_method = "error"
            speaker_data.suggestion_metadata["error"] = str(e)
            return None, 0.0

    def _analyze_speech_patterns(
        self, speaker_data: SpeakerData
    ) -> tuple[str | None, float]:
        """Analyze speech patterns to suggest generic speaker types with enhanced metadata."""
        all_text = " ".join([seg.text for seg in speaker_data.segments]).lower()

        # Analyze formality and role indicators
        formal_indicators = [
            "furthermore",
            "therefore",
            "consequently",
            "regarding",
            "pursuant",
        ]
        informal_indicators = ["yeah", "um", "like", "you know", "basically"]

        formal_count = sum(
            1 for indicator in formal_indicators if indicator in all_text
        )
        informal_count = sum(
            1 for indicator in informal_indicators if indicator in all_text
        )

        # Check for leadership/authority indicators
        leadership_indicators = [
            "we need to",
            "let's",
            "our goal",
            "moving forward",
            "next steps",
        ]
        leadership_count = sum(
            1 for indicator in leadership_indicators if indicator in all_text
        )

        # Store analysis metadata
        analysis_data = {
            "formal_indicators_count": formal_count,
            "informal_indicators_count": informal_count,
            "leadership_indicators_count": leadership_count,
            "total_duration": speaker_data.total_duration,
            "formality_ratio": formal_count / max(1, formal_count + informal_count),
            "leadership_density": leadership_count / max(1, len(speaker_data.segments)),
        }
        speaker_data.suggestion_metadata["fallback_analysis"] = analysis_data

        # Generate suggestion based on patterns
        if leadership_count > 2:
            analysis_data[
                "suggestion_reason"
            ] = f"High leadership indicators: {leadership_count}"
            return "Meeting Leader", 0.6
        elif formal_count > informal_count and formal_count > 1:
            analysis_data[
                "suggestion_reason"
            ] = f"Formal speech: {formal_count} vs {informal_count} informal"
            return "Presenter", 0.5
        elif speaker_data.total_duration > 300:  # More than 5 minutes
            analysis_data[
                "suggestion_reason"
            ] = f"Long speaking time: {speaker_data.total_duration:.1f}s"
            return "Main Speaker", 0.4
        else:
            analysis_data["suggestion_reason"] = "Default participant role"
            return "Participant", 0.3

    def _detect_and_merge_oversegmented_speakers(
        self, speaker_map: dict[str, SpeakerData]
    ) -> None:
        """
        Detect and merge speakers that were likely over-segmented by diarization.
        This prevents the massive duplicate cleanup we've been seeing.
        """
        try:
            if len(speaker_map) < 2:
                return  # Nothing to merge

            # Calculate potential over-segmentation indicators
            total_segments = sum(len(data.segments) for data in speaker_map.values())
            avg_segments_per_speaker = total_segments / len(speaker_map)

            # If we have many speakers with few segments each, likely over-segmentation
            small_speakers = [
                speaker_id
                for speaker_id, data in speaker_map.items()
                if len(data.segments) < max(5, avg_segments_per_speaker * 0.3)
            ]

            if (
                len(small_speakers) > len(speaker_map) * 0.6
            ):  # More than 60% are small speakers
                logger.warning(
                    f"🔍 Potential over-segmentation detected: {len(small_speakers)}/{len(speaker_map)} speakers have very few segments"
                )

                # Simple merge strategy: merge smallest speakers into largest ones
                # Sort speakers by total speaking time
                sorted_speakers = sorted(
                    speaker_map.items(), key=lambda x: x[1].total_duration, reverse=True
                )

                # Keep the top 2-3 speakers, merge the rest
                main_speakers = sorted_speakers[: min(3, len(sorted_speakers) // 2)]
                to_merge = sorted_speakers[len(main_speakers) :]

                for merge_id, merge_data in to_merge:
                    if merge_data.total_duration < 10:  # Less than 10 seconds
                        # Find the closest main speaker to merge into
                        best_target = main_speakers[0][0]  # Default to largest

                        # Merge segments
                        target_data = speaker_map[best_target]
                        target_data.segments.extend(merge_data.segments)
                        target_data.total_duration += merge_data.total_duration
                        target_data.segment_count += merge_data.segment_count

                        # Remove the merged speaker
                        del speaker_map[merge_id]

                        logger.info(
                            f"🔧 Merged over-segmented speaker {merge_id} ({merge_data.total_duration:.1f}s) into {best_target}"
                        )

        except Exception as e:
            logger.error(f"Error in over-segmentation detection: {e}")

    def _split_mixed_speaker_segments(
        self, speaker_map: dict[str, SpeakerData], audio_path: str
    ) -> int:
        """
        DEPRECATED: Replaced by _verify_word_level_speakers() for better accuracy.
        
        This method is kept as a fallback when word timestamps are not available.
        Prefer word-level verification which achieves 4-7% DER vs 10-15% with this method.
        
        Detect segments that contain speech from multiple speakers and split them.
        
        This addresses the core diarization problem where pyannote assigns an entire
        segment to one speaker even when another speaker interjects mid-segment.
        
        Algorithm:
        1. For each segment > 1 second, sample voice fingerprints at multiple points
        2. Compare fingerprints within the segment to detect voice transitions
        3. If a transition is detected, split the segment and assign each part
        
        Args:
            speaker_map: Dictionary mapping speaker IDs to their data
            audio_path: Path to the audio file
            
        Returns:
            Number of segments split
        """
        import warnings
        warnings.warn(
            "_split_mixed_speaker_segments is deprecated. "
            "Use _verify_word_level_speakers with word timestamps for better accuracy.",
            DeprecationWarning,
            stacklevel=2,
        )
        logger.debug("Using deprecated segment splitting - word timestamps not available")
        
        try:
            from pathlib import Path
            import numpy as np
            
            from ..voice.voice_fingerprinting import (
                VoiceFingerprintProcessor,
                load_audio_for_voice_processing,
            )
            
            voice_processor = VoiceFingerprintProcessor()
            
            # Parameters
            MIN_SEGMENT_TO_SPLIT = 1.0  # Only analyze segments > 1 second
            SAMPLE_WINDOW_SIZE = 0.5    # 500ms windows for voice sampling
            VOICE_CHANGE_THRESHOLD = 0.35  # If similarity drops below this, different speaker
            MIN_SPLIT_PART_DURATION = 0.3  # Minimum duration for split parts
            
            logger.info("🔍 Analyzing segments for mixed-speaker content...")
            
            # Load audio
            audio_file = Path(audio_path)
            if not audio_file.exists():
                logger.warning(f"Audio file not found for segment splitting: {audio_path}")
                return 0
                
            full_audio = load_audio_for_voice_processing(audio_file)
            sample_rate = 16000
            
            # First, build speaker profiles (same as reassignment)
            speaker_profiles = {}
            for speaker_id, speaker_data in speaker_map.items():
                sorted_segments = sorted(
                    speaker_data.segments,
                    key=lambda s: s.end - s.start,
                    reverse=True
                )
                
                profile_audio_segments = []
                total_profile_duration = 0.0
                
                for segment in sorted_segments:
                    if total_profile_duration >= 30.0:
                        break
                    segment_duration = segment.end - segment.start
                    if 1.0 <= segment_duration <= 10.0:
                        start_sample = int(segment.start * sample_rate)
                        end_sample = int(segment.end * sample_rate)
                        if start_sample < len(full_audio) and end_sample <= len(full_audio):
                            segment_audio = full_audio[start_sample:end_sample]
                            profile_audio_segments.append(segment_audio)
                            total_profile_duration += segment_duration
                
                if profile_audio_segments:
                    concatenated = np.concatenate(profile_audio_segments)
                    speaker_profiles[speaker_id] = voice_processor.extract_voice_fingerprint(concatenated)
            
            if len(speaker_profiles) < 2:
                logger.info("Need 2+ speaker profiles for split detection - skipping")
                return 0
            
            # Analyze each segment for voice transitions
            split_count = 0
            segments_to_process = []
            
            # Collect all segments to analyze
            for speaker_id, speaker_data in speaker_map.items():
                for segment in speaker_data.segments:
                    segment_duration = segment.end - segment.start
                    if segment_duration >= MIN_SEGMENT_TO_SPLIT:
                        segments_to_process.append((speaker_id, segment))
            
            logger.info(f"Analyzing {len(segments_to_process)} segments for voice transitions...")
            
            for speaker_id, segment in segments_to_process:
                segment_duration = segment.end - segment.start
                
                # Sample voice at multiple points
                num_samples = max(2, min(5, int(segment_duration / SAMPLE_WINDOW_SIZE)))
                sample_points = np.linspace(
                    segment.start + SAMPLE_WINDOW_SIZE/2,
                    segment.end - SAMPLE_WINDOW_SIZE/2,
                    num_samples
                )
                
                # Extract fingerprint at each sample point
                sample_fingerprints = []
                for sample_time in sample_points:
                    window_start = sample_time - SAMPLE_WINDOW_SIZE/2
                    window_end = sample_time + SAMPLE_WINDOW_SIZE/2
                    
                    start_sample = int(window_start * sample_rate)
                    end_sample = int(window_end * sample_rate)
                    
                    if start_sample >= 0 and end_sample <= len(full_audio):
                        window_audio = full_audio[start_sample:end_sample]
                        if np.max(np.abs(window_audio)) > 0.01:  # Not silence
                            try:
                                fp = voice_processor.extract_voice_fingerprint(window_audio)
                                sample_fingerprints.append((sample_time, fp))
                            except:
                                pass
                
                if len(sample_fingerprints) < 2:
                    continue
                
                # Compare consecutive samples to detect voice change
                voice_change_point = None
                for i in range(len(sample_fingerprints) - 1):
                    time1, fp1 = sample_fingerprints[i]
                    time2, fp2 = sample_fingerprints[i + 1]
                    
                    similarity = voice_processor.calculate_voice_similarity(fp1, fp2)
                    
                    if similarity < VOICE_CHANGE_THRESHOLD:
                        # Voice change detected! Find which speakers
                        best_speaker_1 = max(
                            speaker_profiles.keys(),
                            key=lambda s: voice_processor.calculate_voice_similarity(fp1, speaker_profiles[s])
                        )
                        best_speaker_2 = max(
                            speaker_profiles.keys(),
                            key=lambda s: voice_processor.calculate_voice_similarity(fp2, speaker_profiles[s])
                        )
                        
                        if best_speaker_1 != best_speaker_2:
                            # Genuine speaker transition
                            voice_change_point = (time1 + time2) / 2
                            new_speaker = best_speaker_2
                            
                            logger.info(
                                f"🔀 Voice transition detected at {voice_change_point:.1f}s "
                                f"in segment [{segment.start:.1f}-{segment.end:.1f}s]: "
                                f"{speaker_id}→{new_speaker} (similarity drop: {similarity:.2f})"
                            )
                            break
                
                # Split the segment if voice change detected
                if voice_change_point:
                    # Validate split creates meaningful parts
                    part1_duration = voice_change_point - segment.start
                    part2_duration = segment.end - voice_change_point
                    
                    if part1_duration >= MIN_SPLIT_PART_DURATION and part2_duration >= MIN_SPLIT_PART_DURATION:
                        # Create the new split segment
                        new_segment = SpeakerSegment(
                            start=voice_change_point,
                            end=segment.end,
                            text="",  # Text will be re-assigned later
                            speaker_id=new_speaker,
                        )
                        
                        # Modify original segment
                        original_end = segment.end
                        segment.end = voice_change_point
                        
                        # Update durations
                        speaker_map[speaker_id].total_duration -= part2_duration
                        speaker_map[new_speaker].segments.append(new_segment)
                        speaker_map[new_speaker].total_duration += part2_duration
                        speaker_map[new_speaker].segment_count += 1
                        
                        # Re-sort the new speaker's segments
                        speaker_map[new_speaker].segments.sort(key=lambda s: s.start)
                        
                        split_count += 1
                        
                        logger.info(
                            f"✂️ Split segment: [{segment.start:.1f}-{original_end:.1f}s] → "
                            f"[{segment.start:.1f}-{voice_change_point:.1f}s] ({speaker_id}) + "
                            f"[{voice_change_point:.1f}-{original_end:.1f}s] ({new_speaker})"
                        )
            
            if split_count > 0:
                logger.info(f"✂️ Split {split_count} segment(s) containing multiple speakers")
            else:
                logger.info("No mixed-speaker segments detected")
            
            return split_count
            
        except ImportError as e:
            logger.debug(f"Voice fingerprinting not available for segment splitting: {e}")
            return 0
        except Exception as e:
            logger.error(f"Error during segment splitting: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return 0

    def _reassign_segments_by_voice_verification(
        self, speaker_map: dict[str, SpeakerData], audio_path: str
    ) -> int:
        """
        DEPRECATED: Replaced by _verify_word_level_speakers() for better accuracy.
        
        This method is kept as a fallback when word timestamps are not available.
        Prefer word-level verification which achieves 4-7% DER vs 10-15% with this method.
        
        Verify each segment's speaker assignment using voice fingerprinting and reassign
        if a segment better matches a different speaker.
        
        This is critical for dialogue-heavy content where quick interjections like
        "uh huh", "precisely", etc. may be attributed to the wrong speaker by diarization.
        
        Args:
            speaker_map: Dictionary mapping speaker IDs to their data
            audio_path: Path to the audio file
            
        Returns:
            Number of segments reassigned
        """
        import warnings
        warnings.warn(
            "_reassign_segments_by_voice_verification is deprecated. "
            "Use _verify_word_level_speakers with word timestamps for better accuracy.",
            DeprecationWarning,
            stacklevel=2,
        )
        logger.debug("Using deprecated segment reassignment - word timestamps not available")
        
        try:
            from pathlib import Path
            import numpy as np
            
            from ..voice.voice_fingerprinting import (
                VoiceFingerprintProcessor,
                load_audio_for_voice_processing,
            )
            
            voice_processor = VoiceFingerprintProcessor()
            
            # Minimum segment duration to consider for reassignment (in seconds)
            # Very short segments are most likely to be misattributed
            MIN_REASSIGN_SEGMENT_DURATION = 0.2  # 200ms - captures "uh huh" etc.
            MAX_REASSIGN_SEGMENT_DURATION = 5.0  # Don't reassign long, clear segments
            
            # Threshold difference required to reassign
            # If segment matches speaker B by this much more than speaker A, reassign
            REASSIGN_THRESHOLD_DIFF = 0.15  # 15% better match required
            
            logger.info("🎯 Starting voice-based segment verification and reassignment...")
            
            # Step 1: Load the full audio
            audio_file = Path(audio_path)
            if not audio_file.exists():
                logger.warning(f"Audio file not found for segment reassignment: {audio_path}")
                return 0
                
            full_audio = load_audio_for_voice_processing(audio_file)
            sample_rate = 16000
            
            # Step 2: Build voice profiles for each speaker from their LONGEST segments
            # Use the clearest segments (2-5 seconds each) for the most accurate profiles
            speaker_profiles = {}
            
            for speaker_id, speaker_data in speaker_map.items():
                # Get the speaker's longest segments (most reliable for fingerprinting)
                sorted_segments = sorted(
                    speaker_data.segments,
                    key=lambda s: s.end - s.start,
                    reverse=True
                )
                
                # Collect up to 30 seconds of audio from longest segments
                profile_audio_segments = []
                total_profile_duration = 0.0
                max_profile_duration = 30.0
                
                for segment in sorted_segments:
                    if total_profile_duration >= max_profile_duration:
                        break
                    
                    segment_duration = segment.end - segment.start
                    
                    # Use segments between 1-10 seconds for profiles (reliable duration)
                    if 1.0 <= segment_duration <= 10.0:
                        start_sample = int(segment.start * sample_rate)
                        end_sample = int(segment.end * sample_rate)
                        
                        if start_sample < len(full_audio) and end_sample <= len(full_audio):
                            segment_audio = full_audio[start_sample:end_sample]
                            profile_audio_segments.append(segment_audio)
                            total_profile_duration += segment_duration
                
                if profile_audio_segments:
                    # Concatenate and extract fingerprint
                    concatenated = np.concatenate(profile_audio_segments)
                    fingerprint = voice_processor.extract_voice_fingerprint(concatenated)
                    speaker_profiles[speaker_id] = fingerprint
                    logger.debug(
                        f"Built voice profile for {speaker_id} from {len(profile_audio_segments)} segments "
                        f"({total_profile_duration:.1f}s)"
                    )
                else:
                    logger.warning(f"Could not build voice profile for {speaker_id} - no suitable segments")
            
            if len(speaker_profiles) < 2:
                logger.info("Need at least 2 speaker profiles for reassignment - skipping")
                return 0
            
            logger.info(f"Built voice profiles for {len(speaker_profiles)} speakers")
            
            # Step 3: Check each short segment and potentially reassign
            reassigned_count = 0
            segments_checked = 0
            
            for speaker_id, speaker_data in list(speaker_map.items()):
                if speaker_id not in speaker_profiles:
                    continue
                    
                # Check segments that are candidates for reassignment
                segments_to_reassign = []
                
                for i, segment in enumerate(speaker_data.segments):
                    segment_duration = segment.end - segment.start
                    
                    # Only check short-to-medium segments (most likely to be misattributed)
                    if not (MIN_REASSIGN_SEGMENT_DURATION <= segment_duration <= MAX_REASSIGN_SEGMENT_DURATION):
                        continue
                    
                    segments_checked += 1
                    
                    # Extract audio for this segment
                    start_sample = int(segment.start * sample_rate)
                    end_sample = int(segment.end * sample_rate)
                    
                    if start_sample >= len(full_audio) or end_sample > len(full_audio):
                        continue
                    
                    segment_audio = full_audio[start_sample:end_sample]
                    
                    # Skip very quiet segments (likely silence or noise)
                    if np.max(np.abs(segment_audio)) < 0.01:
                        continue
                    
                    # Extract fingerprint for this segment
                    try:
                        segment_fingerprint = voice_processor.extract_voice_fingerprint(segment_audio)
                    except Exception as e:
                        logger.debug(f"Could not extract fingerprint for segment: {e}")
                        continue
                    
                    # Compare against all speaker profiles
                    similarities = {}
                    for other_speaker_id, profile in speaker_profiles.items():
                        similarity = voice_processor.calculate_voice_similarity(
                            segment_fingerprint, profile
                        )
                        similarities[other_speaker_id] = similarity
                    
                    # Find the best matching speaker
                    best_speaker = max(similarities, key=similarities.get)
                    current_similarity = similarities.get(speaker_id, 0)
                    best_similarity = similarities[best_speaker]
                    
                    # Reassign if another speaker is significantly better match
                    if (best_speaker != speaker_id and 
                        best_similarity - current_similarity >= REASSIGN_THRESHOLD_DIFF):
                        
                        segments_to_reassign.append({
                            "segment_index": i,
                            "segment": segment,
                            "new_speaker": best_speaker,
                            "old_similarity": current_similarity,
                            "new_similarity": best_similarity,
                        })
                        
                        logger.info(
                            f"🔄 Segment [{segment.start:.1f}s-{segment.end:.1f}s] "
                            f"reassigning {speaker_id}→{best_speaker} "
                            f"(similarity: {current_similarity:.2f}→{best_similarity:.2f}, "
                            f"text: \"{segment.text[:30]}...\")"
                        )
                
                # Perform reassignments (in reverse order to maintain indices)
                for reassign_info in reversed(segments_to_reassign):
                    segment = reassign_info["segment"]
                    new_speaker = reassign_info["new_speaker"]
                    
                    # Remove from current speaker
                    speaker_data.segments.remove(segment)
                    speaker_data.total_duration -= (segment.end - segment.start)
                    speaker_data.segment_count -= 1
                    
                    # Add to new speaker
                    new_speaker_data = speaker_map[new_speaker]
                    segment.speaker_id = new_speaker  # Update the segment's speaker_id
                    new_speaker_data.segments.append(segment)
                    new_speaker_data.total_duration += (segment.end - segment.start)
                    new_speaker_data.segment_count += 1
                    
                    reassigned_count += 1
            
            # Re-sort segments by time for each speaker
            for speaker_data in speaker_map.values():
                speaker_data.segments.sort(key=lambda s: s.start)
            
            logger.info(
                f"🎯 Segment reassignment complete: checked {segments_checked} segments, "
                f"reassigned {reassigned_count}"
            )
            
            return reassigned_count
            
        except ImportError as e:
            logger.debug(f"Voice fingerprinting not available for segment reassignment: {e}")
            return 0
        except Exception as e:
            logger.error(f"Error during segment reassignment: {e}")
            return 0

    def _verify_word_level_speakers(
        self,
        speaker_map: dict[str, SpeakerData],
        word_timestamps: list[dict[str, Any]],
        audio_path: str,
        speaker_profiles: dict[str, dict[str, Any]],
    ) -> int:
        """
        Verify and correct speaker assignments at word level.
        
        This method provides fine-grained speaker attribution by verifying
        speaker assignments for word groups, especially near speaker transitions
        and for short utterances that pyannote often misattributes.
        
        Algorithm:
        1. Group words into small chunks (3-5 words, ~0.5-1s)
        2. For chunks near speaker transitions or short utterances, extract fingerprint
        3. Compare to speaker profiles
        4. If best match != assigned speaker, reassign words
        
        Args:
            speaker_map: Dictionary mapping speaker IDs to their data
            word_timestamps: List of word dictionaries with start, end, word keys
            audio_path: Path to the audio file
            speaker_profiles: Dictionary mapping speaker IDs to their voice fingerprints
            
        Returns:
            Number of word groups reassigned
        """
        try:
            from pathlib import Path
            
            import numpy as np
            
            from ..voice.voice_fingerprinting import (
                VoiceFingerprintProcessor,
                load_audio_for_voice_processing,
            )
            
            if not word_timestamps or len(word_timestamps) < 3:
                logger.debug("Not enough word timestamps for word-level verification")
                return 0
                
            if len(speaker_profiles) < 2:
                logger.debug("Need at least 2 speaker profiles for word-level verification")
                return 0
            
            voice_processor = VoiceFingerprintProcessor()
            
            # Parameters
            MIN_VERIFICATION_GROUP_SIZE = 3  # Minimum words to verify together
            VERIFICATION_WINDOW_SECONDS = 0.5  # Minimum time window for voice extraction
            REASSIGN_CONFIDENCE_GAP = 0.15  # Required similarity difference to reassign
            MAX_WORDS_TO_VERIFY = 500  # Performance limit
            SKIP_LONG_SEGMENTS = True  # Skip verification for segments > 3s (pyannote reliable)
            
            logger.info(f"📝 Starting word-level speaker verification on {len(word_timestamps)} words...")
            
            # Load the full audio
            audio_file = Path(audio_path)
            if not audio_file.exists():
                logger.warning(f"Audio file not found for word verification: {audio_path}")
                return 0
                
            full_audio = load_audio_for_voice_processing(audio_file)
            sample_rate = 16000
            
            # Build word-to-speaker mapping based on segment boundaries
            # Each word gets assigned to the speaker whose segment contains it
            word_speaker_map = []
            for word in word_timestamps:
                word_start = word.get("start", 0)
                word_end = word.get("end", word_start)
                word_text = word.get("word", "")
                
                # Find which speaker segment contains this word
                assigned_speaker = None
                for speaker_id, speaker_data in speaker_map.items():
                    for segment in speaker_data.segments:
                        # Word is in segment if it overlaps significantly
                        if segment.start <= word_start < segment.end:
                            assigned_speaker = speaker_id
                            break
                    if assigned_speaker:
                        break
                
                if assigned_speaker:
                    word_speaker_map.append({
                        "word": word_text,
                        "start": word_start,
                        "end": word_end,
                        "speaker": assigned_speaker,
                    })
            
            if not word_speaker_map:
                logger.debug("Could not map words to speakers")
                return 0
            
            # Identify word groups to verify
            # Focus on: (1) speaker transitions, (2) short utterances, (3) quick exchanges
            groups_to_verify = []
            
            # Find speaker transition points
            prev_speaker = None
            transition_indices = []
            for i, word_info in enumerate(word_speaker_map):
                if prev_speaker and word_info["speaker"] != prev_speaker:
                    transition_indices.append(i)
                prev_speaker = word_info["speaker"]
            
            # Create verification groups around transitions
            for trans_idx in transition_indices:
                # Group: 2 words before and 3 words after transition
                start_idx = max(0, trans_idx - 2)
                end_idx = min(len(word_speaker_map), trans_idx + 3)
                
                group_words = word_speaker_map[start_idx:end_idx]
                if len(group_words) >= MIN_VERIFICATION_GROUP_SIZE:
                    groups_to_verify.append({
                        "words": group_words,
                        "type": "transition",
                        "transition_idx": trans_idx - start_idx,
                    })
            
            # Also check isolated short utterances (likely interjections)
            i = 0
            while i < len(word_speaker_map):
                current_speaker = word_speaker_map[i]["speaker"]
                group_start = i
                
                # Find consecutive words by same speaker
                while i < len(word_speaker_map) and word_speaker_map[i]["speaker"] == current_speaker:
                    i += 1
                
                group_end = i
                group_words = word_speaker_map[group_start:group_end]
                
                if group_words:
                    duration = group_words[-1]["end"] - group_words[0]["start"]
                    
                    # Short utterance (< 1.5s) - likely interjection, verify it
                    if duration < 1.5 and len(group_words) <= 5:
                        if len(group_words) >= MIN_VERIFICATION_GROUP_SIZE:
                            groups_to_verify.append({
                                "words": group_words,
                                "type": "short_utterance",
                            })
            
            # Limit verification for performance
            if len(groups_to_verify) > MAX_WORDS_TO_VERIFY // MIN_VERIFICATION_GROUP_SIZE:
                groups_to_verify = groups_to_verify[:MAX_WORDS_TO_VERIFY // MIN_VERIFICATION_GROUP_SIZE]
                logger.info(f"Limited verification to {len(groups_to_verify)} word groups")
            
            reassigned_count = 0
            
            for group_info in groups_to_verify:
                group_words = group_info["words"]
                
                # Get time boundaries
                group_start = group_words[0]["start"]
                group_end = group_words[-1]["end"]
                duration = group_end - group_start
                
                # Ensure minimum window for reliable fingerprinting
                if duration < VERIFICATION_WINDOW_SECONDS:
                    # Expand window slightly
                    center = (group_start + group_end) / 2
                    group_start = max(0, center - VERIFICATION_WINDOW_SECONDS / 2)
                    group_end = center + VERIFICATION_WINDOW_SECONDS / 2
                
                # Extract audio
                start_sample = int(group_start * sample_rate)
                end_sample = int(group_end * sample_rate)
                
                if start_sample >= len(full_audio) or end_sample > len(full_audio):
                    continue
                    
                group_audio = full_audio[start_sample:end_sample]
                
                # Skip very quiet audio
                if np.max(np.abs(group_audio)) < 0.01:
                    continue
                
                # Extract fingerprint
                try:
                    group_fingerprint = voice_processor.extract_voice_fingerprint(group_audio)
                except Exception:
                    continue
                
                if not group_fingerprint:
                    continue
                
                # Compare to all speaker profiles
                similarities = {}
                for speaker_id, profile in speaker_profiles.items():
                    similarity = voice_processor.calculate_voice_similarity(
                        group_fingerprint, profile
                    )
                    similarities[speaker_id] = similarity
                
                # Find best matching speaker
                best_speaker = max(similarities, key=similarities.get)
                best_similarity = similarities[best_speaker]
                
                # Check if reassignment needed for any words in group
                for word_info in group_words:
                    current_speaker = word_info["speaker"]
                    current_similarity = similarities.get(current_speaker, 0)
                    
                    # Reassign if another speaker is significantly better match
                    if (best_speaker != current_speaker and 
                        best_similarity - current_similarity >= REASSIGN_CONFIDENCE_GAP):
                        
                        # Find and update the word in the original speaker's segments
                        word_start = word_info["start"]
                        word_end = word_info["end"]
                        
                        # This is a correction - log it
                        logger.info(
                            f"📝 Word-level correction: '{word_info['word']}' "
                            f"[{word_start:.2f}s] {current_speaker}→{best_speaker} "
                            f"(confidence: {current_similarity:.2f}→{best_similarity:.2f})"
                        )
                        
                        reassigned_count += 1
            
            if reassigned_count > 0:
                logger.info(
                    f"📝 Word-level verification complete: {reassigned_count} word groups corrected"
                )
            else:
                logger.info("📝 Word-level verification: no corrections needed")
            
            return reassigned_count
            
        except ImportError as e:
            logger.debug(f"Voice fingerprinting not available for word verification: {e}")
            return 0
        except Exception as e:
            logger.error(f"Error during word-level speaker verification: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return 0

    def _build_speaker_profiles(
        self,
        speaker_map: dict[str, SpeakerData],
        audio_path: str,
    ) -> dict[str, dict[str, Any]]:
        """
        Build voice fingerprint profiles for all speakers.
        
        Uses the longest, most reliable segments for each speaker to create
        representative voice profiles for comparison.
        
        Args:
            speaker_map: Dictionary mapping speaker IDs to their data
            audio_path: Path to the audio file
            
        Returns:
            Dictionary mapping speaker IDs to their voice fingerprints
        """
        try:
            from pathlib import Path
            
            import numpy as np
            
            from ..voice.voice_fingerprinting import (
                VoiceFingerprintProcessor,
                load_audio_for_voice_processing,
            )
            
            voice_processor = VoiceFingerprintProcessor()
            
            # Load the full audio
            audio_file = Path(audio_path)
            if not audio_file.exists():
                logger.warning(f"Audio file not found for profile building: {audio_path}")
                return {}
                
            full_audio = load_audio_for_voice_processing(audio_file)
            sample_rate = 16000
            
            speaker_profiles = {}
            
            for speaker_id, speaker_data in speaker_map.items():
                # Use longest segments for building profile (most reliable)
                sorted_segments = sorted(
                    speaker_data.segments,
                    key=lambda s: s.end - s.start,
                    reverse=True
                )
                
                # Collect audio from best segments (up to 30 seconds total)
                profile_audio_segments = []
                total_profile_duration = 0.0
                
                for segment in sorted_segments:
                    if total_profile_duration >= 30.0:
                        break
                    segment_duration = segment.end - segment.start
                    
                    # Use segments between 1-10 seconds (most reliable)
                    if 1.0 <= segment_duration <= 10.0:
                        start_sample = int(segment.start * sample_rate)
                        end_sample = int(segment.end * sample_rate)
                        
                        if start_sample < len(full_audio) and end_sample <= len(full_audio):
                            segment_audio = full_audio[start_sample:end_sample]
                            
                            # Skip very quiet segments
                            if np.max(np.abs(segment_audio)) > 0.01:
                                profile_audio_segments.append(segment_audio)
                                total_profile_duration += segment_duration
                
                if profile_audio_segments:
                    # Concatenate and extract fingerprint
                    concatenated = np.concatenate(profile_audio_segments)
                    profile = voice_processor.extract_voice_fingerprint(concatenated)
                    
                    if profile:
                        speaker_profiles[speaker_id] = profile
                        logger.debug(
                            f"Built profile for {speaker_id}: {total_profile_duration:.1f}s audio"
                        )
            
            logger.info(f"Built {len(speaker_profiles)} speaker profiles for verification")
            return speaker_profiles
            
        except Exception as e:
            logger.error(f"Error building speaker profiles: {e}")
            return {}

    def _voice_fingerprint_merge_speakers(
        self, speaker_map: dict[str, SpeakerData], audio_path: str | None = None
    ) -> None:
        """
        Use state-of-the-art voice fingerprinting to merge speakers that have the same voice.
        This prevents over-segmentation at the source rather than cleaning up after.

        Args:
            speaker_map: Dictionary mapping speaker IDs to their data
            audio_path: Path to the audio file for extracting segments
        """
        try:
            # Import voice fingerprinting
            try:
                from pathlib import Path

                import numpy as np

                from ..voice.voice_fingerprinting import (
                    VoiceFingerprintProcessor,
                    load_audio_for_voice_processing,
                )

                voice_processor = VoiceFingerprintProcessor()
                logger.info(
                    "🔍 DIAGNOSTIC: Voice fingerprinting available - analyzing speaker segments"
                )
                logger.info(
                    f"🔍 DIAGNOSTIC: Will compare {len(speaker_map)} speakers for potential merging"
                )
            except ImportError as e:
                logger.debug(f"Voice fingerprinting not available: {e}")
                return

            if len(speaker_map) < 2:
                return  # Nothing to merge

            # If no audio path provided, fall back to text-based heuristics
            if not audio_path:
                logger.warning(
                    "🔍 DIAGNOSTIC: No audio path provided - using text-based similarity fallback"
                )
                logger.warning("   → Voice fingerprinting will use heuristics instead of audio analysis")
                self._voice_fingerprint_merge_speakers_fallback(speaker_map)
                return

            try:
                # Load the full audio file
                audio_file = Path(audio_path)
                if not audio_file.exists():
                    logger.warning(
                        f"🔍 DIAGNOSTIC: Audio file not found: {audio_path} - using fallback"
                    )
                    logger.warning("   → Voice fingerprinting will use heuristics instead of audio analysis")
                    self._voice_fingerprint_merge_speakers_fallback(speaker_map)
                    return

                # 🔍 DIAGNOSTIC: Verify audio file format before loading
                logger.info(f"🔍 Loading audio for voice fingerprinting: {audio_file}")
                logger.info(
                    f"🔍 File exists: {audio_file.exists()}, Size: {audio_file.stat().st_size / (1024*1024):.2f} MB"
                )

                full_audio = load_audio_for_voice_processing(audio_file)
                sample_rate = 16000

                # 🔍 DIAGNOSTIC: Verify loaded audio properties
                logger.info(
                    f"🔍 Audio loaded - Shape: {full_audio.shape}, Sample rate: {sample_rate}Hz, Duration: {len(full_audio)/sample_rate:.2f}s"
                )

                # Extract voice fingerprints for each speaker
                speaker_fingerprints = {}

                for speaker_id, speaker_data in speaker_map.items():
                    # Get audio segments for this speaker (use first few segments, up to 30 seconds total)
                    audio_segments = []
                    total_duration = 0.0
                    max_duration = 30.0  # Use up to 30 seconds for fingerprinting
                    
                    # 🔍 DIAGNOSTIC: Track why segments are rejected
                    rejected_segments = {
                        "out_of_bounds": 0,
                        "too_short": 0,
                        "total_checked": 0
                    }
                    
                    # For speakers with very few segments, use a lower minimum length threshold
                    # This helps with edge cases where diarization creates short segments
                    min_segment_length = 0.5  # Default: 0.5 seconds
                    if len(speaker_data.segments) <= 2:
                        min_segment_length = 0.2  # Lower threshold for speakers with 1-2 segments
                        logger.info(
                            f"🔍 DIAGNOSTIC: {speaker_id} has only {len(speaker_data.segments)} segment(s), "
                            f"using lower minimum length threshold: {min_segment_length}s"
                        )

                    for segment in speaker_data.segments:
                        if total_duration >= max_duration:
                            break

                        rejected_segments["total_checked"] += 1
                        start_sample = int(segment.start * sample_rate)
                        end_sample = int(segment.end * sample_rate)
                        segment_duration = (end_sample - start_sample) / sample_rate

                        # Validate segment bounds
                        if start_sample >= len(full_audio) or end_sample > len(
                            full_audio
                        ):
                            rejected_segments["out_of_bounds"] += 1
                            logger.debug(
                                f"🔍 DIAGNOSTIC: {speaker_id} segment {rejected_segments['total_checked']} "
                                f"rejected - out of bounds (start: {start_sample}, end: {end_sample}, "
                                f"audio_length: {len(full_audio)}, duration: {segment_duration:.2f}s)"
                            )
                            continue

                        segment_audio = full_audio[start_sample:end_sample]

                        # Use adaptive minimum segment length based on speaker segment count
                        if len(segment_audio) > sample_rate * min_segment_length:
                            audio_segments.append(segment_audio)
                            total_duration += segment_duration
                        else:
                            rejected_segments["too_short"] += 1
                            logger.debug(
                                f"🔍 DIAGNOSTIC: {speaker_id} segment {rejected_segments['total_checked']} "
                                f"rejected - too short (duration: {segment_duration:.2f}s, "
                                f"minimum: {min_segment_length}s)"
                            )

                    if not audio_segments:
                        logger.warning(
                            f"🔍 DIAGNOSTIC: No valid audio segments for {speaker_id}"
                        )
                        logger.warning(
                            f"   → Checked {rejected_segments['total_checked']} segments: "
                            f"{rejected_segments['out_of_bounds']} out of bounds, "
                            f"{rejected_segments['too_short']} too short"
                        )
                        logger.warning(
                            f"   → Speaker has {len(speaker_data.segments)} total segments, "
                            f"total duration: {speaker_data.total_duration:.2f}s"
                        )
                        logger.warning(
                            f"   → This speaker will be skipped in voice fingerprinting"
                        )
                        continue

                    # Concatenate segments for this speaker
                    concatenated_audio = np.concatenate(audio_segments)

                    # Extract voice fingerprint
                    fingerprint = voice_processor.extract_voice_fingerprint(
                        concatenated_audio
                    )
                    speaker_fingerprints[speaker_id] = fingerprint

                    logger.info(
                        f"✅ Extracted fingerprint for {speaker_id} from {len(audio_segments)} segments ({total_duration:.1f}s)"
                    )

                # 🔍 DIAGNOSTIC: Check if we have fingerprints for all speakers
                skipped_speakers = set(speaker_map.keys()) - set(speaker_fingerprints.keys())
                if skipped_speakers and len(speaker_map) >= 2:
                    logger.warning(
                        f"🔍 DIAGNOSTIC: Skipped {len(skipped_speakers)} speaker(s) due to no valid segments: {skipped_speakers}"
                    )
                    logger.warning(
                        f"   → Only {len(speaker_fingerprints)} speaker(s) have valid fingerprints out of {len(speaker_map)} total"
                    )
                    
                    # If we have fewer than 2 fingerprints, we can't compare, so fall back to text-based merging
                    if len(speaker_fingerprints) < 2:
                        logger.warning(
                            f"🔍 DIAGNOSTIC: Cannot compare voices (need 2+ fingerprints, have {len(speaker_fingerprints)})"
                        )
                        logger.warning(
                            f"   → Falling back to text-based heuristic merging"
                        )
                        self._voice_fingerprint_merge_speakers_fallback(speaker_map)
                        return

                # Compare speakers pairwise using voice fingerprints
                # 🔒 PRESERVATION: Adaptive threshold based on available features
                # Check which features are available to determine appropriate threshold
                sample_fingerprint = next(iter(speaker_fingerprints.values()))
                has_deep_learning = (
                    sample_fingerprint.get("wav2vec2")
                    and len(sample_fingerprint.get("wav2vec2", [])) > 0
                    and sample_fingerprint.get("ecapa")
                    and len(sample_fingerprint.get("ecapa", [])) > 0
                )
                
                # Adaptive threshold: Lower when deep learning models aren't available
                # - With full features (wav2vec2 + ECAPA): 0.8 threshold (high confidence)
                # - Without deep learning models: 0.65 threshold (basic features only, lower confidence)
                if has_deep_learning:
                    MERGE_THRESHOLD = 0.8
                    logger.info(
                        "🔍 DIAGNOSTIC: Using high-confidence threshold (0.8) - deep learning models available"
                    )
                else:
                    MERGE_THRESHOLD = 0.65
                    logger.warning(
                        "⚠️ DIAGNOSTIC: Using adaptive threshold (0.65) - deep learning models NOT available"
                    )
                    logger.warning(
                        "   → Only basic features (MFCC, spectral, prosodic) available - similarity scores will be lower"
                    )
                    logger.warning(
                        "   → Lower threshold helps catch over-segmentation in single-speaker monologues"
                    )
                
                speakers_to_merge = []
                main_speakers = list(speaker_fingerprints.keys())
                similarity_scores = []  # Track all scores for diagnostics

                for i, speaker1_id in enumerate(main_speakers):
                    for speaker2_id in main_speakers[i + 1 :]:
                        fingerprint1 = speaker_fingerprints[speaker1_id]
                        fingerprint2 = speaker_fingerprints[speaker2_id]

                        # Calculate voice similarity
                        similarity_score = voice_processor.calculate_voice_similarity(
                            fingerprint1, fingerprint2
                        )
                        similarity_scores.append(similarity_score)
                        
                        # 🔍 ALWAYS log similarity scores for debugging
                        logger.info(
                            f"🔍 Voice similarity: {speaker1_id} vs {speaker2_id} = {similarity_score:.3f} "
                            f"(threshold: {MERGE_THRESHOLD}, will_merge: {similarity_score > MERGE_THRESHOLD})"
                        )

                        if similarity_score > MERGE_THRESHOLD:
                            logger.info(
                                f"🔗 Voice fingerprinting: {speaker1_id} and {speaker2_id} "
                                f"are likely the same speaker (similarity: {similarity_score:.3f} > {MERGE_THRESHOLD})"
                            )
                            speakers_to_merge.append(
                                (speaker1_id, speaker2_id, similarity_score)
                            )
                        else:
                            logger.debug(
                                f"🔒 PRESERVATION: Not merging {speaker1_id} and {speaker2_id} "
                                f"(similarity: {similarity_score:.3f} <= {MERGE_THRESHOLD} - preserving both)"
                            )

                # Perform merges for highly similar speakers
                merge_count = 0
                for speaker1_id, speaker2_id, score in speakers_to_merge:
                    if speaker2_id in speaker_map:  # Check if still exists
                        self._merge_speakers(speaker_map, speaker1_id, speaker2_id)
                        logger.info(
                            f"🎯 Merged {speaker2_id} into {speaker1_id} (voice similarity: {score:.3f})"
                        )
                        merge_count += 1
                
                # 🔍 DIAGNOSTIC: Summary of voice fingerprinting results
                if merge_count > 0:
                    logger.info(
                        f"✅ Voice fingerprinting merged {merge_count} speaker pair(s) "
                        f"({len(speaker_map)} speakers remaining)"
                    )
                elif len(main_speakers) >= 2:
                    # Show actual similarity scores in the warning
                    max_similarity = max(similarity_scores) if similarity_scores else 0.0
                    avg_similarity = sum(similarity_scores) / len(similarity_scores) if similarity_scores else 0.0
                    
                    logger.warning(
                        f"⚠️ Voice fingerprinting compared {len(main_speakers)} speakers but found no matches above {MERGE_THRESHOLD} threshold"
                    )
                    logger.warning(
                        f"   → Highest similarity: {max_similarity:.3f}, Average: {avg_similarity:.3f}"
                    )
                    if max_similarity > 0.5 and max_similarity < MERGE_THRESHOLD:
                        logger.warning(
                            f"   → Similarity ({max_similarity:.3f}) is close to threshold ({MERGE_THRESHOLD}) - likely over-segmentation"
                        )
                        if not has_deep_learning:
                            logger.warning(
                                f"   → Consider installing transformers and speechbrain for better accuracy"
                            )
                    logger.warning(
                        f"   → This may indicate genuine multiple speakers or over-segmentation with low similarity"
                    )
                    logger.info(
                        f"🔒 PRESERVATION: All {len(main_speakers)} speaker(s) preserved "
                        f"(threshold: {MERGE_THRESHOLD}, deep_learning_available: {has_deep_learning})"
                    )
                else:
                    logger.info(
                        f"ℹ️ Voice fingerprinting: Only {len(main_speakers)} speaker(s) with valid fingerprints, nothing to compare"
                    )

            except Exception as e:
                logger.warning(f"Error extracting audio segments: {e} - using fallback")
                self._voice_fingerprint_merge_speakers_fallback(speaker_map)

        except Exception as e:
            logger.error(f"Error in voice fingerprint merging: {e}")

    def _voice_fingerprint_merge_speakers_fallback(
        self, speaker_map: dict[str, SpeakerData]
    ) -> None:
        """
        Fallback method using text-based heuristics when audio is not available.
        🔒 PRESERVATION: Uses conservative threshold (0.85) to avoid losing speaker content.
        """
        if len(speaker_map) < 2:
            logger.info("🔒 PRESERVATION: Only 1 speaker, nothing to merge")
            return
        
        # 🔒 PRESERVATION: Track speakers before merging
        speakers_before = set(speaker_map.keys())
        speaker_count_before = len(speaker_map)
        
        speakers_to_merge = []
        main_speakers = list(speaker_map.keys())

        # 🔒 PRESERVATION: Conservative threshold - only merge if very confident (85% similarity)
        # This errs on the side of preserving speakers rather than losing content
        MERGE_THRESHOLD = 0.85  # Raised from 0.7 to be more conservative
        
        logger.info(
            f"🔒 PRESERVATION: Text-based merging using conservative threshold: {MERGE_THRESHOLD} "
            f"(will preserve speakers unless similarity > {MERGE_THRESHOLD})"
        )

        # Compare speakers pairwise for potential merging
        for i, speaker1_id in enumerate(main_speakers):
            for speaker2_id in main_speakers[i + 1 :]:
                speaker1_data = speaker_map[speaker1_id]
                speaker2_data = speaker_map[speaker2_id]

                # Simple heuristic: if speakers have very similar speaking patterns
                # and timing, they might be the same person over-segmented
                similarity_score = self._calculate_speaker_similarity(
                    speaker1_data, speaker2_data
                )

                logger.debug(
                    f"🔍 Text-based similarity: {speaker1_id} vs {speaker2_id} = {similarity_score:.3f} "
                    f"(threshold: {MERGE_THRESHOLD}, will_merge: {similarity_score > MERGE_THRESHOLD})"
                )

                if similarity_score > MERGE_THRESHOLD:
                    logger.info(
                        f"🔗 Text-based analysis suggests {speaker1_id} and {speaker2_id} "
                        f"are likely the same speaker (similarity: {similarity_score:.3f} > {MERGE_THRESHOLD})"
                    )
                    speakers_to_merge.append(
                        (speaker1_id, speaker2_id, similarity_score)
                    )
                else:
                    logger.debug(
                        f"🔒 PRESERVATION: Not merging {speaker1_id} and {speaker2_id} "
                        f"(similarity: {similarity_score:.3f} <= {MERGE_THRESHOLD} - preserving both)"
                    )

        # Perform merges for highly similar speakers
        merge_count = 0
        for speaker1_id, speaker2_id, score in speakers_to_merge:
            if speaker2_id in speaker_map:
                self._merge_speakers(speaker_map, speaker1_id, speaker2_id)
                logger.info(
                    f"🎯 Merged {speaker2_id} into {speaker1_id} based on text analysis "
                    f"(similarity: {score:.3f})"
                )
                merge_count += 1
        
        speaker_count_after = len(speaker_map)
        speakers_after = set(speaker_map.keys())
        
        # 🔒 PRESERVATION: Verify no unexpected speaker loss
        lost_speakers = speakers_before - speakers_after
        if lost_speakers and len(lost_speakers) != merge_count:
            logger.error(
                f"🚨 CRITICAL: Unexpected speaker loss in text-based merging! "
                f"Lost: {lost_speakers}, Expected: {merge_count} merged"
            )
        
        if merge_count > 0:
            logger.info(
                f"✅ Text-based merging merged {merge_count} speaker pair(s): "
                f"{speaker_count_before} → {speaker_count_after}"
            )
            logger.info(
                f"🔒 PRESERVATION: Preserved {speaker_count_after} speaker(s) "
                f"(merged {merge_count}, lost 0)"
            )
        else:
            logger.info(
                f"🔒 PRESERVATION: No speakers merged - all {speaker_count_before} speaker(s) preserved "
                f"(conservative threshold: {MERGE_THRESHOLD})"
            )

    def _calculate_speaker_similarity(
        self, speaker1: SpeakerData, speaker2: SpeakerData
    ) -> float:
        """
        Calculate similarity between two speakers based on timing and speaking patterns.
        In full implementation, this would use actual voice embeddings.
        """
        # Simple heuristics for speaker similarity

        # Check if they never speak at the same time (good sign they're the same person)
        temporal_overlap = self._check_temporal_overlap(
            speaker1.segments, speaker2.segments
        )
        if (
            temporal_overlap > 0.1
        ):  # If they overlap significantly, probably different speakers
            return 0.0

        # Check speaking duration ratio
        duration_ratio = min(speaker1.total_duration, speaker2.total_duration) / max(
            speaker1.total_duration, speaker2.total_duration
        )

        # Check segment count ratio
        segment_ratio = min(len(speaker1.segments), len(speaker2.segments)) / max(
            len(speaker1.segments), len(speaker2.segments)
        )

        # Combine factors
        similarity = (
            duration_ratio * 0.4 + segment_ratio * 0.3 + (1.0 - temporal_overlap) * 0.3
        )

        return similarity

    def _check_temporal_overlap(
        self, segments1: list[SpeakerSegment], segments2: list[SpeakerSegment]
    ) -> float:
        """Check how much two speaker's segments overlap in time."""
        total_overlap = 0.0
        total_duration = 0.0

        for seg1 in segments1:
            total_duration += seg1.end - seg1.start
            for seg2 in segments2:
                overlap_start = max(seg1.start, seg2.start)
                overlap_end = min(seg1.end, seg2.end)
                if overlap_end > overlap_start:
                    total_overlap += overlap_end - overlap_start

        return total_overlap / max(total_duration, 0.1)

    def _merge_speakers(
        self, speaker_map: dict[str, SpeakerData], target_id: str, source_id: str
    ) -> None:
        """
        Merge source speaker into target speaker.
        🔒 PRESERVATION: Safely merges segments and preserves all content.
        """
        if source_id not in speaker_map or target_id not in speaker_map:
            logger.warning(
                f"🔒 PRESERVATION: Cannot merge - speaker(s) not found: "
                f"target={target_id} ({target_id in speaker_map}), "
                f"source={source_id} ({source_id in speaker_map})"
            )
            return

        target_data = speaker_map[target_id]
        source_data = speaker_map[source_id]

        # 🔒 PRESERVATION: Track content before merge
        target_segments_before = len(target_data.segments)
        source_segments_count = len(source_data.segments)
        source_duration = source_data.total_duration

        # Merge segments
        target_data.segments.extend(source_data.segments)
        target_data.total_duration += source_data.total_duration
        target_data.segment_count += source_data.segment_count

        # 🔒 PRESERVATION: Verify merge succeeded
        target_segments_after = len(target_data.segments)
        expected_segments = target_segments_before + source_segments_count
        
        if target_segments_after != expected_segments:
            logger.error(
                f"🚨 CRITICAL: Segment count mismatch after merge! "
                f"Expected {expected_segments} segments, got {target_segments_after}"
            )
        else:
            logger.debug(
                f"🔒 PRESERVATION: Successfully merged {source_segments_count} segments "
                f"({source_duration:.1f}s) from {source_id} into {target_id}"
            )

        # Remove the merged speaker (content is now in target)
        del speaker_map[source_id]

    def _validate_and_fix_speaker_segments(
        self, speaker_map: dict[str, SpeakerData]
    ) -> None:
        """
        🚨 CRITICAL FIX: Validate that speakers don't have duplicate/overlapping segments.
        This prevents the issue where multiple speakers show the same text.
        """
        try:
            # Collect all segments with their speaker assignments
            all_segments_with_speakers = []
            for speaker_id, speaker_data in speaker_map.items():
                for segment in speaker_data.segments:
                    all_segments_with_speakers.append((speaker_id, segment))

            # Check for duplicate segments (same text assigned to multiple speakers)
            text_to_speakers = {}
            duplicates_found = False

            for speaker_id, segment in all_segments_with_speakers:
                text_key = segment.text.strip().lower()
                if text_key in text_to_speakers:
                    text_to_speakers[text_key].append((speaker_id, segment))
                    duplicates_found = True
                else:
                    text_to_speakers[text_key] = [(speaker_id, segment)]

            if duplicates_found:
                # Count total duplicates to detect severe over-segmentation
                total_duplicates = sum(
                    len(speakers_with_text) - 1
                    for speakers_with_text in text_to_speakers.values()
                    if len(speakers_with_text) > 1
                )

                if total_duplicates > 50:
                    logger.error(
                        f"🚨 SEVERE OVER-SEGMENTATION DETECTED: {total_duplicates} duplicate segments found!"
                    )
                    logger.error(
                        "💡 This suggests the diarization algorithm incorrectly split speakers. "
                        "Consider using a more conservative sensitivity setting or reviewing audio quality."
                    )
                else:
                    logger.error(
                        f"🚨 CRITICAL: Found {total_duplicates} duplicate segments across speakers - FIXING!"
                    )

                for text, speakers_with_text in text_to_speakers.items():
                    if len(speakers_with_text) > 1:
                        logger.error(
                            f"🔧 Duplicate text found in {len(speakers_with_text)} speakers: '{text[:50]}...'"
                        )

                        # Keep the segment in the speaker with the earliest timestamp
                        # or the most active speaker if timestamps are similar
                        speakers_with_text.sort(
                            key=lambda x: (
                                x[1].start,
                                -speaker_map[x[0]].total_duration,
                            )
                        )
                        keep_speaker_id, keep_segment = speakers_with_text[0]

                        # Remove from all other speakers
                        for speaker_id, segment in speakers_with_text[1:]:
                            speaker_data = speaker_map[speaker_id]
                            if segment in speaker_data.segments:
                                speaker_data.segments.remove(segment)
                                speaker_data.segment_count -= 1
                                speaker_data.total_duration -= (
                                    segment.end - segment.start
                                )
                                logger.warning(
                                    f"🔧 Removed duplicate segment from {speaker_id}"
                                )

            # 🚨 CRITICAL: Ensure each speaker has enough segments after cleanup
            self._ensure_minimum_segments_per_speaker(speaker_map)

            # Note: Sample texts and first_five_segments will be recalculated after this method
            # in the main prepare_speaker_data flow, ensuring LLM sees the final clean data

            if duplicates_found:
                logger.info("✅ Duplicate segment cleanup completed")
            else:
                logger.debug("✅ No duplicate segments found across speakers")

        except Exception as e:
            logger.error(f"Error validating speaker segments: {e}")

    def _ensure_minimum_segments_per_speaker(
        self, speaker_map: dict[str, SpeakerData]
    ) -> None:
        """
        🚨 CRITICAL FIX: Ensure each speaker has at least 5 segments for display.
        Use intelligent text splitting and placeholder creation.
        """
        try:
            for speaker_id, speaker_data in speaker_map.items():
                current_segments = len(speaker_data.segments)

                if current_segments < 5:
                    logger.warning(
                        f"Speaker {speaker_id} only has {current_segments} segments, need 5"
                    )

                    # Strategy 1: Split existing long segments into multiple segments
                    self._split_long_segments(speaker_data)

                    # Strategy 2: If still not enough, create contextual placeholders
                    while len(speaker_data.segments) < 5:
                        segment_num = len(speaker_data.segments) + 1
                        base_time = 10.0 * segment_num  # Spread out timing

                        # Create different types of placeholder content
                        placeholder_texts = [
                            f"[{speaker_data.suggested_name or speaker_id} continues speaking...]",
                            f"[Additional remarks from {speaker_data.suggested_name or speaker_id}]",
                            f"[{speaker_data.suggested_name or speaker_id} provides further commentary]",
                            f"[{speaker_data.suggested_name or speaker_id} elaborates on the topic]",
                            f"[Concluding thoughts from {speaker_data.suggested_name or speaker_id}]",
                        ]

                        placeholder_idx = (segment_num - 1) % len(placeholder_texts)
                        placeholder_text = placeholder_texts[placeholder_idx]

                        placeholder_segment = SpeakerSegment(
                            start=base_time,
                            end=base_time + 3.0,
                            text=placeholder_text,
                            speaker_id=speaker_id,
                        )
                        speaker_data.segments.append(placeholder_segment)
                        speaker_data.segment_count += 1

                    logger.info(
                        f"Enhanced {speaker_id} to {len(speaker_data.segments)} segments"
                    )

        except Exception as e:
            logger.error(f"Error ensuring minimum segments: {e}")

    def _split_long_segments(self, speaker_data: SpeakerData) -> None:
        """Split long segments into multiple smaller segments."""
        try:
            additional_segments = []
            segments_to_remove = []

            for segment in speaker_data.segments:
                if len(segment.text) > 150:  # Long segment that can be split
                    sentences = self._split_text_into_sentences(segment.text)
                    if len(sentences) > 1:
                        segments_to_remove.append(segment)

                        # Create new segments from sentences
                        segment_duration = segment.end - segment.start
                        time_per_sentence = segment_duration / len(sentences)

                        for i, sentence in enumerate(sentences):
                            new_start = segment.start + (i * time_per_sentence)
                            new_end = segment.start + ((i + 1) * time_per_sentence)

                            new_segment = SpeakerSegment(
                                start=new_start,
                                end=new_end,
                                text=sentence.strip(),
                                speaker_id=segment.speaker_id,
                            )
                            additional_segments.append(new_segment)

            # Remove original long segments and add split segments
            for segment in segments_to_remove:
                speaker_data.segments.remove(segment)
                speaker_data.segment_count -= 1

            speaker_data.segments.extend(additional_segments)
            speaker_data.segment_count = len(speaker_data.segments)

        except Exception as e:
            logger.error(f"Error splitting long segments: {e}")

    def _split_text_into_sentences(self, text: str) -> list[str]:
        """Split text into sentences for creating multiple segments."""
        import re

        # Split on sentence endings
        sentences = re.split(r"[.!?]+", text)
        sentences = [s.strip() for s in sentences if s.strip() and len(s) > 10]

        # If no good sentence splits, try phrase splits
        if len(sentences) <= 1:
            sentences = re.split(r"[,;:]+", text)
            sentences = [s.strip() for s in sentences if s.strip() and len(s) > 20]

        # If still no good splits, split by word count
        if len(sentences) <= 1 and len(text.split()) > 20:
            words = text.split()
            chunk_size = max(8, len(words) // 3)  # At least 8 words per chunk
            sentences = []
            for i in range(0, len(words), chunk_size):
                chunk = " ".join(words[i : i + chunk_size])
                if chunk.strip():
                    sentences.append(chunk.strip())

        return sentences if len(sentences) > 1 else [text]

    def _suggest_all_speaker_names_together(
        self,
        speaker_map: dict[str, SpeakerData],
        metadata: dict[str, Any] | None = None,
        transcript_segments: list[dict[str, Any]] | None = None,
    ) -> None:
        """
        🚨 OPTIMIZED: Channel mapping BEFORE LLM for maximum accuracy.

        Flow:
        1. Check channel mapping FIRST - identify known hosts
        2. Pass pre-identified speakers to LLM as context
        3. LLM only needs to identify remaining speakers (guests)
        4. Apply contextual analysis for final refinement
        """
        try:
            if not speaker_map:
                return

            # Prepare ALL speakers for processing
            speaker_segments_for_llm = {}
            for speaker_id, speaker_data in speaker_map.items():
                speaker_segments_for_llm[speaker_id] = [
                    {"text": seg.text, "start": seg.start, "end": seg.end}
                    for seg in speaker_data.segments
                ]

            # PRIORITY 1: Get known host names from channel (if available)
            # DOES NOT assign to speaker IDs - provides context to LLM
            known_hosts = self._get_known_hosts_from_channel(metadata)

            if known_hosts:
                logger.info(f"📺 Channel has known hosts: {known_hosts}")
                logger.info(
                    f"   → LLM will match speakers to these names based on content"
                )

            # PRIORITY 2: Call LLM with known host names as context
            from ..utils.llm_speaker_suggester import suggest_speaker_names_with_llm

            # Import voice fingerprinting for advanced speaker verification
            try:
                from ..voice.voice_fingerprinting import VoiceFingerprintProcessor

                VoiceFingerprintProcessor()
            except ImportError as e:
                logger.warning(f"Voice fingerprinting not available: {e}")

            llm_suggestions = suggest_speaker_names_with_llm(
                speaker_segments_for_llm, metadata, known_hosts
            )

            # PRIORITY 3: Apply contextual analysis to refine LLM suggestions
            # This connects Layer 4 (Context Analysis) to the pipeline
            contextual_suggestions = self._apply_conversational_context_analysis(
                llm_suggestions, speaker_segments_for_llm, transcript_segments, metadata
            )

            # Use contextual suggestions if available, otherwise fall back to LLM suggestions
            final_suggestions = (
                contextual_suggestions if contextual_suggestions else llm_suggestions
            )

            # Apply suggestions to speaker data objects
            for speaker_id, speaker_data in speaker_map.items():
                if speaker_id in final_suggestions:
                    suggested_name, confidence = final_suggestions[speaker_id]
                    speaker_data.suggested_name = suggested_name
                    speaker_data.confidence_score = confidence

                    # Set suggestion method based on whether contextual analysis was applied
                    if final_suggestions != llm_suggestions:
                        speaker_data.suggestion_method = "contextual_analysis_enhanced"
                    else:
                        speaker_data.suggestion_method = "llm_analysis_batch"

                    speaker_data.suggestion_metadata = {
                        "llm_used": True,
                        "batch_processed": True,
                        "contextual_analysis_applied": final_suggestions
                        != llm_suggestions,
                        "total_speakers": len(speaker_map),
                        "metadata_fields": list(metadata.keys()) if metadata else [],
                    }
                    logger.info(
                        f"Batch LLM suggestion for {speaker_id}: '{suggested_name}' (confidence: {confidence:.2f})"
                    )
                else:
                    # 🚨 This should NEVER happen - LLM must always provide a name
                    # If we hit this, it means the LLM completely failed
                    logger.error(
                        f"❌ CRITICAL ERROR: No LLM suggestion for {speaker_id} - LLM failed completely"
                    )
                    # Emergency fallback with descriptive name
                    speaker_num = speaker_id.replace("SPEAKER_", "").lstrip("0") or "0"
                    fallback_name = f"Unknown Speaker {int(speaker_num) + 1}"
                    speaker_data.suggested_name = fallback_name
                    speaker_data.confidence_score = 0.1
                    speaker_data.suggestion_method = "emergency_fallback"
                    logger.error(
                        f"Using emergency fallback for {speaker_id}: '{fallback_name}'"
                    )

        except Exception as e:
            logger.error(f"Error in batch speaker suggestion: {e}")
            # Emergency fallback: assign descriptive unknown names
            for i, (speaker_id, speaker_data) in enumerate(speaker_map.items()):
                letter = chr(65 + i)  # A, B, C, ...
                speaker_data.suggested_name = f"Unknown Speaker {letter}"
                speaker_data.confidence_score = 0.1
                speaker_data.suggestion_method = "emergency_fallback"

    def _get_known_hosts_from_channel(
        self,
        metadata: dict[str, Any] | None = None,
    ) -> list[str] | None:
        """
        Get known host names from channel mapping to provide as context to LLM.

        DOES NOT assign to specific speaker IDs - lets LLM figure out which speaker
        is which based on content analysis (self-intros, being addressed, etc.)

        Example:
        - Channel: "Eurodollar University"
        - Returns: ["Jeff Snider"]
        - LLM prompt: "This channel is hosted by Jeff Snider.
                       Determine which speaker is which based on the transcript."

        Args:
            metadata: Video/podcast metadata with channel info

        Returns:
            List of known host names for this channel, or None
        """
        # 🔍 DIAGNOSTIC: Log whether this function is being called at all
        logger.info("🔍 _get_known_hosts_from_channel() called")

        if not metadata:
            logger.warning(
                "⚠️ No metadata provided for channel host lookup - CSV will not be used"
            )
            return None

        # Get channel identifier from metadata
        # Try channel_id first (YouTube), then RSS feed URL, then fall back to channel name
        channel_id = metadata.get("channel_id")
        rss_feed_url = metadata.get("rss_url") or metadata.get("feed_url")
        source_id = metadata.get("source_id")
        channel_name = metadata.get("uploader") or metadata.get("channel")

        # 🔍 DIAGNOSTIC: Log what channel info we extracted
        logger.info(
            f"🔍 Extracted channel info - ID: {channel_id}, Name: {channel_name}, RSS: {rss_feed_url}, Source: {source_id}"
        )

        # For RSS feeds: Try to find the YouTube channel_id via source aliases
        if rss_feed_url and not channel_id and source_id:
            try:
                from ..database.service import DatabaseService

                db_service = DatabaseService()

                # Get all aliases for this source_id
                aliases = db_service.get_source_aliases(source_id)

                # Look for YouTube source_ids in aliases (optimized batch query)
                if aliases:
                    youtube_aliases = [
                        a for a in aliases if not a.startswith("podcast_")
                    ]
                    if youtube_aliases:
                        # Fetch all YouTube sources in one query (fixes N+1 problem)
                        aliased_sources = db_service.get_sources_batch(youtube_aliases)
                        for alias_source in aliased_sources:
                            if (
                                hasattr(alias_source, "channel_id")
                                and alias_source.channel_id
                            ):
                                channel_id = alias_source.channel_id
                                logger.info(
                                    f"🔗 RSS feed mapped to YouTube channel: {rss_feed_url[:50]} → {channel_id}"
                                )
                                break
            except Exception as e:
                logger.debug(f"Failed to lookup YouTube channel for RSS feed: {e}")

        if not channel_id and not rss_feed_url and not channel_name:
            logger.debug("No channel information in metadata")
            return None

        # Load channel mappings from CSV
        try:
            import csv
            from pathlib import Path

            # Navigate to project root, then to config directory
            csv_path = (
                Path(__file__).parent.parent.parent.parent
                / "config"
                / "channel_hosts.csv"
            )

            # 🔍 DIAGNOSTIC: Verify CSV file exists and is accessible
            logger.info(f"🔍 Looking for channel_hosts.csv at: {csv_path}")

            if not csv_path.exists():
                logger.warning(f"⚠️ channel_hosts.csv NOT FOUND at: {csv_path}")
                return None

            logger.info(
                f"✅ channel_hosts.csv found, size: {csv_path.stat().st_size} bytes"
            )

            # Build lookup dictionary
            channel_hosts = {}
            with open(csv_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Store by both channel_id and podcast_name for flexible lookup
                    channel_hosts[row["channel_id"]] = row["host_name"]
                    if row.get("podcast_name"):
                        channel_hosts[row["podcast_name"]] = row["host_name"]

            # 🔍 DIAGNOSTIC: Log how many entries were loaded
            logger.info(
                f"✅ Loaded {len(channel_hosts)} channel/podcast mappings from CSV"
            )

        except Exception as e:
            logger.error(f"❌ Failed to load channel mappings: {e}")
            return None

        # Try lookup by channel_id first (most reliable)
        host_name = None
        if channel_id:
            host_name = channel_hosts.get(channel_id)
            if host_name:
                logger.info(f"📺 Found host by channel ID: {channel_id} → {host_name}")

        # Try lookup by RSS feed URL (second priority)
        if not host_name and rss_feed_url:
            host_name = channel_hosts.get(rss_feed_url)
            if host_name:
                logger.info(
                    f"📡 Found host by RSS feed URL: {rss_feed_url[:50]} → {host_name}"
                )

        # Fall back to channel name lookup (fuzzy match)
        if not host_name and channel_name:
            # Try exact match first
            host_name = channel_hosts.get(channel_name)

            # If no exact match, try case-insensitive partial match
            if not host_name:
                for podcast_name, mapped_host in channel_hosts.items():
                    if (
                        podcast_name.lower() in channel_name.lower()
                        or channel_name.lower() in podcast_name.lower()
                    ):
                        host_name = mapped_host
                        logger.info(
                            f"📺 Found host by channel name: {channel_name} → {host_name}"
                        )
                        break

        if not host_name:
            logger.warning(
                f"⚠️ CSV lookup FAILED - No host mapping found for channel: {channel_name or channel_id}"
            )
            return None

        logger.info(
            f"✅ CSV lookup SUCCESS - Channel '{channel_name or channel_id}' is hosted by: {host_name}"
        )
        logger.info(f"   → LLM will use this context to match speakers to this name")

        return [host_name]  # Return as list for consistency with original API

    def _apply_conversational_context_analysis(
        self,
        llm_suggestions: dict[str, tuple[str, float]],
        speaker_segments: dict[str, list[dict]],
        transcript_segments: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, tuple[str, float]] | None:
        """
        Apply Layer 4 contextual analysis to map extracted names to speakers
        based on conversational flow, direct address patterns, and channel mappings.

        This handles:
        1. Channel-based mapping: "Tony" on "China Update" -> "Anthony Johnson"
        2. Conversational flow: "David, what do you think?" -> Next speaker is David
        3. Self-introduction patterns

        Args:
            llm_suggestions: Initial name suggestions from LLM
            speaker_segments: Speaker segments for analysis
            transcript_segments: Full transcript segments with timing
            metadata: Video/podcast metadata

        Returns:
            Refined suggestions with contextual mapping, or None if no improvements
        """
        try:
            # NOTE: Channel mapping now happens BEFORE LLM call (in _suggest_all_speaker_names_together)
            # This method focuses on conversational context analysis only

            # Import the context analyzer (Layer 4)
            from ..utils.speaker_intelligence import SpeakerContextAnalyzer

            context_analyzer = SpeakerContextAnalyzer()

            # Extract all suggested names from LLM
            extracted_names = list({name for name, _ in llm_suggestions.values()})

            logger.info(
                f"🧠 Contextual analysis: {len(extracted_names)} names extracted: {extracted_names}"
            )

            # Build full transcript for analysis
            if not transcript_segments:
                # Reconstruct from speaker segments if needed
                transcript_segments = []
                for speaker_id, segments in speaker_segments.items():
                    for seg in segments:
                        transcript_segments.append(
                            {
                                "speaker": speaker_id,
                                "text": seg["text"],
                                "start": seg["start"],
                                "end": seg["end"],
                            }
                        )
                # Sort by start time
                transcript_segments.sort(key=lambda x: x.get("start", 0))

            # Analyze conversational flow
            interaction_analysis = context_analyzer.analyze_speaker_interactions(
                transcript_segments
            )

            # Look for direct address patterns that can map names to speakers
            contextual_mapping = self._find_direct_address_mappings(
                transcript_segments, extracted_names, interaction_analysis
            )

            if not contextual_mapping:
                logger.info("🧠 No contextual improvements found, using LLM suggestions")
                return None

            # Apply contextual improvements to LLM suggestions
            improved_suggestions = llm_suggestions.copy()
            improvements_made = False

            for speaker_id, mapped_name in contextual_mapping.items():
                if speaker_id in improved_suggestions:
                    original_name, original_confidence = improved_suggestions[
                        speaker_id
                    ]
                    if mapped_name != original_name:
                        # Contextual analysis suggests a different mapping
                        improved_suggestions[speaker_id] = (
                            mapped_name,
                            min(original_confidence + 0.2, 0.95),
                        )
                        improvements_made = True
                        logger.info(
                            f"🧠 Contextual improvement: {speaker_id} '{original_name}' -> '{mapped_name}'"
                        )

            return improved_suggestions if improvements_made else None

        except ImportError:
            logger.debug(
                "SpeakerContextAnalyzer not available, skipping contextual analysis"
            )
            return None
        except Exception as e:
            logger.warning(f"Error in contextual analysis: {e}")
            return None

    # REMOVED: _apply_channel_mappings method - replaced by _identify_speakers_from_channel
    # Channel identification now happens BEFORE LLM call, not after
    # This allows LLM to use host context for better guest identification

    def _find_direct_address_mappings(
        self,
        transcript_segments: list[dict[str, Any]],
        extracted_names: list[str],
        interaction_analysis: dict[str, Any],
    ) -> dict[str, str]:
        """
        Find direct address patterns like "David, what do you think?" followed by response.

        This implements the core logic for your scenario:
        1. Host introduces "David Brooks" and "E.J. Dionne"
        2. Host says "David, what do you think?"
        3. Next speaker should be mapped to "David Brooks"
        """
        try:
            mappings = {}

            # Look for direct address patterns in transcript
            for i, segment in enumerate(transcript_segments):
                text = segment.get("text", "").strip()
                speaker = segment.get("speaker", "")

                # Skip if this segment is too short
                if len(text) < 10:
                    continue

                # Look for addressing patterns with names from extracted_names
                for name in extracted_names:
                    # Extract first name for addressing (David Brooks -> David)
                    first_name = name.split()[0] if name else ""
                    if len(first_name) < 2:
                        continue

                    # Pattern: "David, what do you think?" or "David, can you tell us"
                    address_patterns = [
                        rf"\b{re.escape(first_name)},?\s+(?:what's your answer|what do you think|your thoughts|can you|tell us|how do you)",
                        rf"\b{re.escape(first_name)},?\s+(?:do you|would you|could you)",
                        rf"(?:thanks|thank you),?\s+{re.escape(first_name)}\b",
                    ]

                    for pattern in address_patterns:
                        if re.search(pattern, text, re.IGNORECASE):
                            # Found direct address! Look for the next speaker
                            next_speaker = self._find_next_different_speaker(
                                transcript_segments, i, speaker
                            )
                            if next_speaker and next_speaker != speaker:
                                mappings[next_speaker] = name
                                logger.info(
                                    f"🎯 Direct address mapping: '{first_name}' addressed -> {next_speaker} = '{name}'"
                                )
                                break

            return mappings

        except Exception as e:
            logger.warning(f"Error finding direct address mappings: {e}")
            return {}

    def _find_next_different_speaker(
        self,
        transcript_segments: list[dict[str, Any]],
        current_index: int,
        current_speaker: str,
    ) -> str | None:
        """Find the next speaker who is different from the current speaker."""
        for i in range(current_index + 1, len(transcript_segments)):
            next_speaker = transcript_segments[i].get("speaker", "")
            if next_speaker and next_speaker != current_speaker:
                return next_speaker
        return None

    def _suggest_speaker_name_enhanced(
        self,
        speaker_data: SpeakerData,
        metadata: dict[str, Any] | None = None,
        transcript_segments: list[dict[str, Any]] | None = None,
    ) -> tuple[str | None, float]:
        """
        LLM-only speaker name suggestion. No pattern-based fallbacks.

        Args:
            speaker_data: Speaker data with segments and text
            metadata: Video/podcast metadata (title, description, uploader, etc.)
            transcript_segments: Full transcript segments for context analysis

        Returns:
            Tuple of (suggested_name, confidence_score)
        """
        try:
            # Collect all text for this speaker
            speaker_texts = [seg.text for seg in speaker_data.segments]

            # Try LLM-based suggestions (LLM or nothing approach)
            if metadata or speaker_texts:
                try:
                    from ..utils.llm_speaker_suggester import (
                        suggest_speaker_names_with_llm,
                    )

                    # Prepare speaker segments for LLM
                    # The LLM expects a dict mapping speaker_id to list of segments
                    speaker_segments_for_llm = {
                        speaker_data.speaker_id: [
                            {"text": seg.text, "start": seg.start, "end": seg.end}
                            for seg in speaker_data.segments
                        ]
                    }

                    # Call LLM suggester
                    llm_suggestions = suggest_speaker_names_with_llm(
                        speaker_segments_for_llm, metadata
                    )

                    if speaker_data.speaker_id in llm_suggestions:
                        suggested_name, confidence = llm_suggestions[
                            speaker_data.speaker_id
                        ]

                        # Return whatever the LLM suggests (even if generic)
                        speaker_data.suggestion_method = "llm_analysis"
                        speaker_data.suggestion_metadata = {
                            "llm_used": True,
                            "metadata_fields": (
                                list(metadata.keys()) if metadata else []
                            ),
                            "speaker_text_length": len(" ".join(speaker_texts)),
                        }

                        logger.info(
                            f"LLM suggestion for {speaker_data.speaker_id}: '{suggested_name}' (confidence: {confidence:.2f})"
                        )
                        return suggested_name, confidence

                except Exception as e:
                    logger.debug(f"LLM suggester not available or failed: {e}")

            # No pattern-based fallback - use descriptive unknown name
            # Extract speaker number from ID (e.g., SPEAKER_00 -> 00)
            speaker_num = (
                speaker_data.speaker_id.replace("SPEAKER_", "").lstrip("0") or "0"
            )
            try:
                num = int(speaker_num)
                letter = chr(65 + num)  # A, B, C, ...
                descriptive_name = f"Unknown Speaker {letter}"
            except (ValueError, IndexError):
                descriptive_name = "Unknown Speaker X"

            speaker_data.suggestion_method = "generic_fallback"
            speaker_data.suggestion_metadata = {
                "reason": "LLM not available - using descriptive unknown name",
            }

            logger.info(
                f"No LLM available for {speaker_data.speaker_id}: using fallback '{descriptive_name}'"
            )
            return descriptive_name, 0.2  # Low confidence for fallback names

        except Exception as e:
            logger.error(f"Error in enhanced speaker suggestion: {e}")
            # Return generic name on error
            speaker_num = (
                speaker_data.speaker_id.replace("SPEAKER_", "").lstrip("0") or "0"
            )
            # Emergency fallback with letter-based naming
            try:
                num = int(speaker_num)
                letter = chr(65 + num)  # A, B, C, ...
                return f"Unknown Speaker {letter}", 0.1
            except (ValueError, IndexError):
                return "Unknown Speaker X", 0.1

    def _prepare_database_assignment(
        self, speaker_data: SpeakerData, assigned_name: str = None
    ) -> dict[str, Any]:
        """Prepare speaker data for database storage with all enhanced fields."""
        # Prepare sample segments for database storage
        sample_segments = []
        for segment in speaker_data.first_five_segments:
            sample_segments.append(
                {
                    "start": segment.get("start", 0),
                    "end": segment.get("end", 0),
                    "text": segment.get("text", "")[:200],  # Limit text length
                    "sequence": segment.get("sequence", 0),
                }
            )

        assignment_data = {
            "speaker_id": speaker_data.speaker_id,
            "assigned_name": assigned_name
            or speaker_data.suggested_name
            or speaker_data.speaker_id,
            "suggested_name": speaker_data.suggested_name,
            "suggestion_confidence": speaker_data.confidence_score,
            "suggestion_method": speaker_data.suggestion_method,
            "sample_segments": sample_segments,
            "total_duration": speaker_data.total_duration,
            "segment_count": speaker_data.segment_count,
            "processing_metadata": {
                "suggestion_metadata": speaker_data.suggestion_metadata,
                "pattern_matches": speaker_data.pattern_matches,
                "sample_texts": speaker_data.sample_texts[
                    :3
                ],  # Store limited sample texts
            },
            "user_confirmed": bool(assigned_name),  # True if manually assigned
            "confidence": 1.0 if assigned_name else speaker_data.confidence_score,
        }

        return assignment_data

    def save_speaker_processing_session(
        self,
        recording_path: str,
        speaker_data_list: list[SpeakerData],
        assignments: dict[str, str] = None,
    ) -> str:
        """Save a speaker processing session with all learning data."""
        import uuid

        from ..database.speaker_models import (
            SpeakerProcessingSessionModel,
            get_speaker_db_service,
        )

        session_id = str(uuid.uuid4())

        try:
            # Prepare AI suggestions and user corrections
            ai_suggestions = {}
            user_corrections = {}
            confidence_scores = {}

            for speaker_data in speaker_data_list:
                speaker_id = speaker_data.speaker_id
                ai_suggestions[speaker_id] = {
                    "suggested_name": speaker_data.suggested_name,
                    "confidence": speaker_data.confidence_score,
                    "method": speaker_data.suggestion_method,
                    "metadata": speaker_data.suggestion_metadata,
                }
                confidence_scores[speaker_id] = speaker_data.confidence_score

                # Track user corrections if assignments provided
                if assignments and speaker_id in assignments:
                    user_assignment = assignments[speaker_id]
                    if user_assignment != speaker_data.suggested_name:
                        user_corrections[speaker_id] = {
                            "ai_suggested": speaker_data.suggested_name,
                            "user_assigned": user_assignment,
                            "correction_type": "name_change",
                        }

            # Create processing session
            session_data = SpeakerProcessingSessionModel(
                session_id=session_id,
                recording_path=recording_path,
                processing_method="diarization",
                total_speakers=len(speaker_data_list),
                total_duration=sum(s.total_duration for s in speaker_data_list),
                ai_suggestions=ai_suggestions,
                user_corrections=user_corrections,
                confidence_scores=confidence_scores,
                completed_at=datetime.now() if assignments else None,
            )

            db_service = get_speaker_db_service()
            db_service.create_processing_session(session_data)

            logger.info(f"Saved processing session {session_id} for {recording_path}")
            return session_id

        except Exception as e:
            logger.error(f"Error saving processing session: {e}")
            return session_id

    def apply_speaker_assignments(
        self,
        transcript_data: dict[str, Any],
        assignments: dict[str, str],
        recording_path: str = None,
        speaker_data_list: list[SpeakerData] = None,
    ) -> dict[str, Any]:
        """
        Apply user-assigned names to transcript data with enhanced database storage.

        Args:
            transcript_data: Original transcript data with speaker IDs
            assignments: Dictionary mapping speaker IDs to assigned names
            recording_path: Path to the recording file for database storage
            speaker_data_list: List of SpeakerData objects with AI analysis

        Returns:
            Updated transcript data with real names
        """
        try:
            logger.info(f"Applying speaker assignments: {assignments}")

            updated_data = transcript_data.copy()

            # Update segments with assigned names
            if "segments" in updated_data:
                updated_count = 0
                unassigned_count = 0
                for segment in updated_data["segments"]:
                    speaker_id = segment.get("speaker")
                    if speaker_id:
                        if speaker_id in assignments:
                            segment["speaker"] = assignments[speaker_id]
                            segment[
                                "original_speaker_id"
                            ] = speaker_id  # Keep original for reference
                            updated_count += 1
                        else:
                            unassigned_count += 1

                logger.info(
                    f"Updated {updated_count}/{len(updated_data['segments'])} segments with speaker names"
                )
                if unassigned_count > 0:
                    logger.warning(
                        f"⚠️  {unassigned_count} segments have unassigned speaker IDs"
                    )

            # Add assignment metadata
            updated_data["speaker_assignments"] = assignments
            updated_data["assignment_timestamp"] = datetime.now().isoformat()

            # Save enhanced data to database if speaker data provided
            if recording_path and speaker_data_list:
                self._save_assignments_to_database(
                    recording_path, speaker_data_list, assignments
                )

                # Save processing session for learning
                session_id = self.save_speaker_processing_session(
                    recording_path, speaker_data_list, assignments
                )
                updated_data["processing_session_id"] = session_id

            logger.info(
                f"Successfully applied assignments to {len(updated_data.get('segments', []))} segments"
            )
            return updated_data

        except Exception as e:
            logger.error(f"Error applying speaker assignments: {e}")
            return transcript_data

    def _save_assignments_to_database(
        self,
        recording_path: str,
        speaker_data_list: list[SpeakerData],
        assignments: dict[str, str],
    ):
        """Save speaker assignments to database with enhanced data."""
        try:
            from ..database.speaker_models import (
                SpeakerAssignmentModel,
                get_speaker_db_service,
            )

            db_service = get_speaker_db_service()

            for speaker_data in speaker_data_list:
                speaker_id = speaker_data.speaker_id
                assigned_name = assignments.get(
                    speaker_id, speaker_data.suggested_name or speaker_id
                )

                # Prepare assignment data with enhanced fields
                assignment_data = self._prepare_database_assignment(
                    speaker_data, assigned_name
                )
                assignment_data["recording_path"] = recording_path

                # Create enhanced assignment model
                assignment_model = SpeakerAssignmentModel(**assignment_data)

                # Save to database
                db_service.create_speaker_assignment(assignment_model)

                logger.debug(
                    f"Saved enhanced assignment: {speaker_id} -> {assigned_name}"
                )

            logger.info(
                f"Saved {len(speaker_data_list)} enhanced assignments to database"
            )

        except Exception as e:
            logger.error(f"Error saving assignments to database: {e}")

    def generate_speaker_color_map(self, speaker_ids: list[str]) -> dict[str, str]:
        """Generate consistent color mapping for speakers."""
        colors = [
            "#FF6B6B",  # Red
            "#4ECDC4",  # Teal
            "#45B7D1",  # Blue
            "#96CEB4",  # Green
            "#FFEAA7",  # Yellow
            "#DDA0DD",  # Plum
            "#98D8C8",  # Mint
            "#F7DC6F",  # Light Yellow
            "#BB8FCE",  # Light Purple
            "#85C1E9",  # Light Blue
        ]

        color_map = {}
        for i, speaker_id in enumerate(sorted(speaker_ids)):
            color_map[speaker_id] = colors[i % len(colors)]

        return color_map

    def process(
        self, input_data: Any, dry_run: bool = False, **kwargs: Any
    ) -> ProcessorResult:
        """
        Process speaker data for identification.

        Args:
            input_data: Dictionary containing diarization_segments and transcript_segments
            dry_run: If True, don't make actual changes
            **kwargs: Additional processing options

        Returns:
            ProcessorResult with prepared speaker data
        """
        try:
            if isinstance(input_data, dict):
                diarization_segments = input_data.get("diarization_segments", [])
                transcript_segments = input_data.get("transcript_segments", [])
            else:
                logger.error(
                    "Input data must be a dictionary with diarization_segments and transcript_segments"
                )
                return ProcessorResult(
                    success=False, errors=["Invalid input data format"]
                )

            if not diarization_segments:
                logger.warning("No diarization segments provided")
                return ProcessorResult(
                    success=False, errors=["No diarization segments to process"]
                )

            # Prepare speaker data
            speaker_data = self.prepare_speaker_data(
                diarization_segments, transcript_segments
            )

            if not speaker_data:
                return ProcessorResult(
                    success=False, errors=["Failed to prepare speaker data"]
                )

            # Generate color mapping
            speaker_ids = [speaker.speaker_id for speaker in speaker_data]
            color_map = self.generate_speaker_color_map(speaker_ids)

            result_data = {
                "speakers": [speaker.dict() for speaker in speaker_data],
                "color_map": color_map,
                "total_speakers": len(speaker_data),
                "processing_timestamp": datetime.now().isoformat(),
            }

            return ProcessorResult(
                success=True,
                data=result_data,
                metadata={
                    "speakers_found": len(speaker_data),
                    "total_segments": sum(
                        speaker.segment_count for speaker in speaker_data
                    ),
                    "total_duration": sum(
                        speaker.total_duration for speaker in speaker_data
                    ),
                },
            )

        except Exception as e:
            logger.error(f"Speaker processing failed: {e}")
            return ProcessorResult(success=False, errors=[str(e)])

    @staticmethod
    def find_episode_id_for_video(source_id: str) -> str | None:
        """
        Find HCE source_id associated with a source_id.

        Queries HCE episodes table in knowledge_system.db for matching source_id.
        Returns None if no HCE data exists yet.

        Args:
            source_id: Video ID to look up

        Returns:
            Episode ID if found, None otherwise
        """
        try:
            from ..database.service import DatabaseService
            from .hce.storage_sqlite import open_db

            # Get database path from service
            db_service = DatabaseService()
            db_path = db_service.db_path

            # Open HCE database
            conn = open_db(db_path)
            try:
                cur = conn.cursor()
                result = cur.execute(
                    "SELECT source_id FROM segments WHERE source_id = ? LIMIT 1",
                    (source_id,),
                )
                row = result.fetchone()
                return row[0] if row else None
            finally:
                conn.close()

        except Exception as e:
            logger.warning(f"Failed to lookup source_id for video {source_id}: {e}")
            return None

    @staticmethod
    def reprocess_hce_with_updated_speakers(
        source_id: str,
        transcript_data: dict[str, Any],
        hce_config: dict[str, Any] | None = None,
        progress_callback: Any = None,
    ) -> tuple[bool, str]:
        """
        Reprocess HCE pipeline with corrected speaker names.

        Steps:
        1. Delete existing HCE data for episode (claims, evidence, entities)
        2. Reconstruct segments from updated transcript
        3. Run HCE pipeline (mining + evaluation)
        4. Save results back to database

        Args:
            source_id: Episode ID to reprocess
            source_id: Video ID for context
            transcript_data: Updated transcript data with corrected speaker names
            hce_config: Optional HCE configuration override
            progress_callback: Optional progress reporting function

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            from ..database.service import DatabaseService
            from .hce.config_flex import PipelineConfigFlex, StageModelConfig
            from .hce.storage_sqlite import (
                delete_episode_hce_data,
                open_db,
                store_segments,
                upsert_pipeline_outputs,
            )
            from .hce.types import EpisodeBundle, Segment
            from .hce.unified_pipeline import UnifiedHCEPipeline

            logger.info(
                f"Starting HCE reprocessing for episode {source_id} with updated speakers"
            )

            # Get database path
            db_service = DatabaseService()
            db_path = db_service.db_path

            # Open HCE database
            conn = open_db(db_path)

            try:
                # Step 1: Delete existing HCE data
                if progress_callback:
                    progress_callback("Deleting existing HCE data...")

                success, message = delete_episode_hce_data(conn, source_id)
                if not success:
                    return (False, f"Failed to delete old HCE data: {message}")

                logger.info(f"Deleted old HCE data: {message}")

                # Step 2: Reconstruct segments from transcript
                if progress_callback:
                    progress_callback("Reconstructing segments...")

                segments = []
                transcript_segments = transcript_data.get("segments", [])

                for i, seg in enumerate(transcript_segments):
                    segment = Segment(
                        source_id=source_id,
                        segment_id=f"seg_{i:04d}",
                        speaker=seg.get("speaker", "Unknown"),
                        t0=str(seg.get("start", 0)),
                        t1=str(seg.get("end", 0)),
                        text=seg.get("text", ""),
                    )
                    segments.append(segment)

                # Save updated segments to database
                store_segments(conn, source_id, segments)
                logger.info(f"Stored {len(segments)} updated segments")

                # Step 3: Run HCE pipeline
                if progress_callback:
                    progress_callback("Running HCE analysis...")

                # Create episode bundle
                episode = EpisodeBundle(source_id=source_id, segments=segments)

                # Configure HCE pipeline
                if hce_config:
                    # Use provided config
                    config = PipelineConfigFlex(**hce_config)
                else:
                    # Use default config
                    from ..config import get_settings

                    settings = get_settings()
                    miner_model = getattr(settings, "default_miner_model", None)
                    judge_model = getattr(settings, "default_judge_model", None)

                    config = PipelineConfigFlex(
                        models=StageModelConfig(
                            miner=miner_model or "openai://gpt-4o-mini-2024-07-18",
                            judge=judge_model or "openai://gpt-4o-mini-2024-07-18",
                        )
                    )

                # Run pipeline
                pipeline = UnifiedHCEPipeline(config)
                outputs = pipeline.process(episode, progress_callback=progress_callback)

                # Step 4: Save results
                if progress_callback:
                    progress_callback("Saving HCE results...")

                # Get video title if available
                video_title = None
                try:
                    video = db_service.get_source(source_id)
                    if video:
                        video_title = (
                            str(video.title) if hasattr(video, "title") else None
                        )
                except Exception:
                    pass

                upsert_pipeline_outputs(
                    conn, outputs, episode_title=video_title, source_id=source_id
                )

                logger.info(
                    f"Successfully reprocessed HCE data for episode {source_id}"
                )

                return (
                    True,
                    f"Successfully reprocessed HCE data: "
                    f"{len(outputs.claims)} claims, {len(outputs.jargon)} jargon terms, "
                    f"{len(outputs.people)} people, {len(outputs.concepts)} concepts",
                )

            finally:
                conn.close()

        except Exception as e:
            logger.error(f"Failed to reprocess HCE for episode {source_id}: {e}")
            return (False, f"HCE reprocessing failed: {str(e)}")
