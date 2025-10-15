"""
Speaker Learning Service

Enhances speaker attribution using historical data and user corrections.
Provides auto-assignment suggestions based on accumulated learning.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ..database.speaker_models import get_speaker_db_service
from ..logger import get_logger

logger = get_logger(__name__)


class SpeakerLearningService:
    """Service for learning from user corrections and improving speaker suggestions."""

    def __init__(self):
        """Initialize the learning service."""
        self.db_service = get_speaker_db_service()

    def suggest_assignments_from_learning(
        self, recording_path: str, diarization_data: list[dict]
    ) -> dict[str, tuple[str, float]]:
        """Use learning data to suggest speaker assignments with confidence scores."""
        suggestions = {}

        try:
            # Extract metadata from recording path for pattern matching
            file_name = Path(recording_path).stem.lower()

            # Get channel-specific patterns if this is a YouTube recording
            channel_patterns = self._extract_channel_patterns(recording_path)

            # Get historical patterns for similar content
            content_patterns = self._get_content_patterns(file_name, diarization_data)

            # Generate suggestions for each speaker
            for speaker_data in diarization_data:
                speaker_id = speaker_data.get("speaker_id", "UNKNOWN")

                # Try channel-specific patterns first
                suggestion = self._suggest_from_channel_patterns(
                    speaker_data, channel_patterns
                )

                # Fall back to content analysis patterns
                if not suggestion or suggestion[1] < 0.6:
                    content_suggestion = self._suggest_from_content_patterns(
                        speaker_data, content_patterns
                    )
                    if content_suggestion and (
                        not suggestion or content_suggestion[1] > suggestion[1]
                    ):
                        suggestion = content_suggestion

                # Fall back to voice similarity patterns
                if not suggestion or suggestion[1] < 0.5:
                    voice_suggestion = self._suggest_from_voice_patterns(speaker_data)
                    if voice_suggestion and (
                        not suggestion or voice_suggestion[1] > suggestion[1]
                    ):
                        suggestion = voice_suggestion

                if suggestion:
                    suggestions[speaker_id] = suggestion

            logger.info(
                f"Generated {len(suggestions)} learned suggestions for {recording_path}"
            )
            return suggestions

        except Exception as e:
            logger.error(f"Error generating learned suggestions: {e}")
            return {}

    def _extract_channel_patterns(self, recording_path: str) -> dict[str, Any]:
        """Extract patterns specific to YouTube channels or content creators."""
        try:
            # Try to extract channel info from file path or metadata
            path_parts = Path(recording_path).parts
            channel_indicators = []

            # Look for common channel patterns in path
            for part in path_parts:
                if any(
                    keyword in part.lower()
                    for keyword in ["channel", "podcast", "show"]
                ):
                    channel_indicators.append(part)

            # Get historical assignments for similar paths
            similar_assignments = self._get_similar_path_assignments(recording_path)

            return {
                "channel_indicators": channel_indicators,
                "historical_assignments": similar_assignments,
                "pattern_strength": len(similar_assignments),
            }

        except Exception as e:
            logger.debug(f"Error extracting channel patterns: {e}")
            return {}

    def _get_similar_path_assignments(self, recording_path: str) -> list[dict]:
        """Get assignments from recordings with similar paths."""
        try:
            path_obj = Path(recording_path)
            parent_dir = str(path_obj.parent)
            file_prefix = path_obj.stem.split("_")[0]  # First part before underscore

            # Query for recordings in same directory or with similar names
            from ..database.speaker_models import SpeakerAssignment

            with self.db_service.get_session() as session:
                # Get assignments from same directory
                similar_by_dir = (
                    session.query(SpeakerAssignment)
                    .filter(
                        SpeakerAssignment.recording_path.like(f"{parent_dir}%"),
                        SpeakerAssignment.user_confirmed.is_(True),
                    )
                    .all()
                )

                # Get assignments with similar file names
                similar_by_name = (
                    session.query(SpeakerAssignment)
                    .filter(
                        SpeakerAssignment.recording_path.like(f"%{file_prefix}%"),
                        SpeakerAssignment.user_confirmed.is_(True),
                    )
                    .all()
                )

            # Combine and deduplicate
            all_similar = list(set(similar_by_dir + similar_by_name))

            return [
                {
                    "speaker_id": a.speaker_id,
                    "assigned_name": a.assigned_name,
                    "confidence": a.confidence,
                    "recording_path": a.recording_path,
                }
                for a in all_similar
            ]

        except Exception as e:
            logger.debug(f"Error getting similar path assignments: {e}")
            return []

    def _suggest_from_channel_patterns(
        self, speaker_data: dict, channel_patterns: dict
    ) -> tuple[str, float] | None:
        """Suggest speaker name based on channel-specific patterns."""
        try:
            historical = channel_patterns.get("historical_assignments", [])

            if not historical:
                return None

            # Count frequency of names for similar speaker positions
            _speaker_position = speaker_data.get(
                "position", 0
            )  # 0=main, 1=first guest, etc.
            name_counts = {}

            for assignment in historical:
                # Simple heuristic: assume first speaker (SPEAKER_00) is often the host
                if speaker_data.get("speaker_id", "").endswith("00") and assignment[
                    "speaker_id"
                ].endswith("00"):
                    name = assignment["assigned_name"]
                    name_counts[name] = name_counts.get(name, 0) + 1
                elif assignment["speaker_id"] == speaker_data.get("speaker_id"):
                    name = assignment["assigned_name"]
                    name_counts[name] = name_counts.get(name, 0) + 1

            if name_counts:
                # Return most frequent name with confidence based on frequency
                best_name = max(name_counts, key=name_counts.get)
                frequency = name_counts[best_name]
                total_samples = len(historical)
                confidence = min(
                    0.9, frequency / max(1, total_samples) * 2
                )  # Scale confidence

                return best_name, confidence

            return None

        except Exception as e:
            logger.debug(f"Error suggesting from channel patterns: {e}")
            return None

    def _get_content_patterns(
        self, file_name: str, diarization_data: list[dict]
    ) -> dict[str, Any]:
        """Get patterns based on content analysis of similar recordings."""
        try:
            # Look for content keywords in filename
            content_keywords = []

            # Common content type indicators
            content_types = {
                "interview": ["interview", "conversation", "chat", "talk"],
                "podcast": ["podcast", "episode", "show"],
                "meeting": ["meeting", "call", "conference"],
                "presentation": ["presentation", "speech", "lecture"],
            }

            detected_type = None
            for content_type, keywords in content_types.items():
                if any(keyword in file_name for keyword in keywords):
                    detected_type = content_type
                    content_keywords.extend(keywords)
                    break

            # Get assignments from recordings of similar content type
            similar_content_assignments = self._get_content_type_assignments(
                detected_type
            )

            return {
                "content_type": detected_type,
                "keywords": content_keywords,
                "similar_assignments": similar_content_assignments,
            }

        except Exception as e:
            logger.debug(f"Error getting content patterns: {e}")
            return {}

    def _get_content_type_assignments(self, content_type: str) -> list[dict]:
        """Get assignments from recordings of similar content type."""
        if not content_type:
            return []

        try:
            from ..database.speaker_models import SpeakerAssignment

            with self.db_service.get_session() as session:
                # Get assignments where processing metadata indicates similar content
                assignments = (
                    session.query(SpeakerAssignment)
                    .filter(
                        SpeakerAssignment.processing_metadata_json.like(
                            f"%{content_type}%"
                        ),
                        SpeakerAssignment.user_confirmed.is_(True),
                    )
                    .all()
                )

            return [
                {
                    "speaker_id": a.speaker_id,
                    "assigned_name": a.assigned_name,
                    "confidence": a.confidence,
                    "content_type": content_type,
                }
                for a in assignments
            ]

        except Exception as e:
            logger.debug(f"Error getting content type assignments: {e}")
            return []

    def _suggest_from_content_patterns(
        self, speaker_data: dict, content_patterns: dict
    ) -> tuple[str, float] | None:
        """Suggest speaker name based on content type patterns."""
        try:
            content_type = content_patterns.get("content_type")
            similar_assignments = content_patterns.get("similar_assignments", [])

            if not content_type or not similar_assignments:
                return None

            # Content-specific role mapping
            role_mappings = {
                "interview": {
                    "SPEAKER_00": ["Interviewer", "Host", "Journalist"],
                    "SPEAKER_01": ["Interviewee", "Guest", "Subject"],
                },
                "podcast": {
                    "SPEAKER_00": ["Host", "Podcaster", "Main Host"],
                    "SPEAKER_01": ["Co-host", "Guest", "Co-podcaster"],
                },
                "meeting": {
                    "SPEAKER_00": ["Meeting Leader", "Chair", "Facilitator"],
                    "SPEAKER_01": ["Participant", "Team Member", "Attendee"],
                },
            }

            speaker_id = speaker_data.get("speaker_id", "")
            suggested_roles = role_mappings.get(content_type, {}).get(speaker_id, [])

            # Check if any historical assignments match suggested roles
            for assignment in similar_assignments:
                if assignment["assigned_name"] in suggested_roles:
                    return assignment["assigned_name"], 0.7

            # Fallback: return most common role for this content type
            if suggested_roles:
                return suggested_roles[0], 0.5

            return None

        except Exception as e:
            logger.debug(f"Error suggesting from content patterns: {e}")
            return None

    def _suggest_from_voice_patterns(
        self, speaker_data: dict
    ) -> tuple[str, float] | None:
        """Suggest speaker name based on voice pattern similarity."""
        try:
            # This would integrate with voice recognition/similarity
            # For now, return generic suggestions based on speaking patterns

            duration = speaker_data.get("total_duration", 0)
            speaker_data.get("segment_count", 0)

            # Simple heuristic based on speaking time
            if duration > 300:  # More than 5 minutes
                return "Main Speaker", 0.4
            elif duration > 60:  # More than 1 minute
                return "Participant", 0.3
            else:
                return "Brief Speaker", 0.2

        except Exception as e:
            logger.debug(f"Error suggesting from voice patterns: {e}")
            return None

    def get_channel_speaker_patterns(self, channel_id: str) -> dict[str, float]:
        """Get common speakers for a specific channel with frequency scores."""
        try:
            from ..database.speaker_models import SpeakerAssignment

            with self.db_service.get_session() as session:
                # Get all assignments for this channel (approximate by path matching)
                assignments = (
                    session.query(SpeakerAssignment)
                    .filter(
                        SpeakerAssignment.recording_path.like(f"%{channel_id}%"),
                        SpeakerAssignment.user_confirmed.is_(True),
                    )
                    .all()
                )

            # Count frequency of each speaker name
            name_counts = {}
            total_assignments = len(assignments)

            for assignment in assignments:
                name = assignment.assigned_name
                name_counts[name] = name_counts.get(name, 0) + 1

            # Convert to frequency scores
            frequency_scores = {}
            for name, count in name_counts.items():
                frequency_scores[name] = count / max(1, total_assignments)

            return frequency_scores

        except Exception as e:
            logger.error(f"Error getting channel speaker patterns: {e}")
            return {}

    def update_pattern_confidence(self, pattern_type: str, success: bool):
        """Update confidence in specific patterns based on user validation."""
        try:
            # This would update pattern confidence scores in a separate table
            # For now, log the feedback for future implementation
            logger.info(
                f"Pattern feedback: {pattern_type} {'succeeded' if success else 'failed'}"
            )

            # Future: Store pattern confidence metrics
            # - Track success/failure rates for different pattern types
            # - Adjust confidence scores based on historical accuracy
            # - Learn which patterns work best for different content types

        except Exception as e:
            logger.error(f"Error updating pattern confidence: {e}")

    def analyze_learning_effectiveness(self) -> dict[str, Any]:
        """Analyze how well the learning system is performing."""
        try:
            from ..database.speaker_models import SpeakerProcessingSession

            with self.db_service.get_session() as session:
                # Get recent processing sessions
                recent_sessions = (
                    session.query(SpeakerProcessingSession)
                    .filter(
                        SpeakerProcessingSession.created_at
                        > datetime.now() - timedelta(days=30)
                    )
                    .all()
                )

            total_sessions = len(recent_sessions)
            sessions_with_corrections = 0
            avg_confidence = 0.0

            for session in recent_sessions:
                if session.user_corrections:
                    corrections = (
                        json.loads(session.user_corrections_json)
                        if session.user_corrections_json
                        else {}
                    )
                    if corrections:
                        sessions_with_corrections += 1

                if session.confidence_scores:
                    scores = (
                        json.loads(session.confidence_scores_json)
                        if session.confidence_scores_json
                        else {}
                    )
                    if scores:
                        avg_confidence += sum(scores.values()) / len(scores)

            if total_sessions > 0:
                avg_confidence /= total_sessions
                correction_rate = sessions_with_corrections / total_sessions
            else:
                correction_rate = 0

            return {
                "total_sessions": total_sessions,
                "correction_rate": correction_rate,
                "average_confidence": avg_confidence,
                "learning_effectiveness": 1.0 - correction_rate,  # Higher is better
            }

        except Exception as e:
            logger.error(f"Error analyzing learning effectiveness: {e}")
            return {}


# Global learning service instance
_learning_service: SpeakerLearningService | None = None


def get_speaker_learning_service() -> SpeakerLearningService:
    """Get the global speaker learning service instance."""
    global _learning_service
    if _learning_service is None:
        _learning_service = SpeakerLearningService()
    return _learning_service
