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

    def process(self, input_data: Any, **kwargs) -> ProcessorResult:
        """
        Process speaker diarization data.

        Args:
            input_data: Dictionary containing diarization_segments and transcript_segments
            **kwargs: Additional processing options

        Returns:
            ProcessorResult: Processing result with speaker data
        """
        try:
            if not self.validate_input(input_data):
                return ProcessorResult(
                    success=False, error="Invalid input data for speaker processing"
                )

            diarization_segments = input_data["diarization_segments"]
            transcript_segments = input_data["transcript_segments"]

            # Prepare speaker data
            speaker_data_list = self.prepare_speaker_data(
                diarization_segments, transcript_segments
            )

            return ProcessorResult(
                success=True, data={"speaker_data_list": speaker_data_list}
            )

        except Exception as e:
            logger.error(f"Error processing speaker data: {e}")
            return ProcessorResult(success=False, error=str(e))

    def prepare_speaker_data(
        self,
        diarization_segments: list[dict[str, Any]],
        transcript_segments: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
    ) -> list[SpeakerData]:
        """
        Merge diarization and transcript data for speaker assignment.

        Args:
            diarization_segments: List of diarization segments with speaker IDs and timing
            transcript_segments: List of transcript segments with text and timing

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

            # Generate sample texts and suggestions for each speaker
            for speaker_data in speaker_map.values():
                speaker_data.sample_texts = self._extract_sample_texts(
                    speaker_data.segments
                )
                speaker_data.first_five_segments = self._extract_first_five_segments(
                    speaker_data.segments
                )

                # Enhanced intelligent suggestion using metadata and full transcript
                (
                    speaker_data.suggested_name,
                    speaker_data.confidence_score,
                ) = self._suggest_speaker_name_enhanced(
                    speaker_data, metadata, transcript_segments
                )

            # Sort speakers by total speaking time (most active first)
            sorted_speakers = sorted(
                speaker_map.values(), key=lambda x: x.total_duration, reverse=True
            )

            logger.info(f"Prepared data for {len(sorted_speakers)} speakers")
            return sorted_speakers

        except Exception as e:
            logger.error(f"Error preparing speaker data: {e}")
            return []

    def _find_overlapping_text(
        self,
        start_time: float,
        end_time: float,
        transcript_segments: list[dict[str, Any]],
    ) -> str:
        """Find transcript text that overlaps with the given time range."""
        overlapping_texts = []

        for trans_seg in transcript_segments:
            trans_start = float(trans_seg.get("start", 0))
            trans_end = float(trans_seg.get("end", trans_start + 1))

            # Check for overlap
            if not (end_time <= trans_start or start_time >= trans_end):
                text = trans_seg.get("text", "").strip()
                if text:
                    overlapping_texts.append(text)

        return " ".join(overlapping_texts)

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

            # No pattern-based fallback - just return generic name
            # Extract speaker number from ID (e.g., SPEAKER_00 -> 00)
            speaker_num = (
                speaker_data.speaker_id.replace("SPEAKER_", "").lstrip("0") or "0"
            )
            generic_name = f"Speaker {int(speaker_num) + 1}"

            speaker_data.suggestion_method = "generic_fallback"
            speaker_data.suggestion_metadata = {
                "reason": "LLM not available - using generic name",
            }

            logger.info(
                f"No LLM available for {speaker_data.speaker_id}: using generic '{generic_name}'"
            )
            return generic_name, 0.2  # Low confidence for generic names

        except Exception as e:
            logger.error(f"Error in enhanced speaker suggestion: {e}")
            # Return generic name on error
            speaker_num = (
                speaker_data.speaker_id.replace("SPEAKER_", "").lstrip("0") or "0"
            )
            return f"Speaker {int(speaker_num) + 1}", 0.1

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
                for segment in updated_data["segments"]:
                    speaker_id = segment.get("speaker")
                    if speaker_id and speaker_id in assignments:
                        segment["speaker"] = assignments[speaker_id]
                        segment[
                            "original_speaker_id"
                        ] = speaker_id  # Keep original for reference

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
