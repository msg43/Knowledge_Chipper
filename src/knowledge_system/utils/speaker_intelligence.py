"""
Speaker Intelligence Module

Provides intelligent name suggestions and speaker analysis capabilities
for the speaker identification system.
"""

import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from ..database.speaker_models import SpeakerVoiceModel, get_speaker_db_service
from ..logger import get_logger

logger = get_logger(__name__)


class SpeakerNameSuggester:
    """Intelligent speaker name suggestions based on context analysis."""

    def __init__(self):
        """Initialize the name suggester."""
        self.db_service = get_speaker_db_service()
        self._compile_patterns()
        self._load_common_names()

    def _compile_patterns(self):
        """Compile regex patterns for name detection and analysis."""
        self.patterns = {
            # Direct name introductions
            "self_intro_formal": re.compile(
                r"\b(?:my name is|I am|I\'m)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
                re.IGNORECASE,
            ),
            "self_intro_casual": re.compile(
                r"\b(?:hi|hello|hey),?\s+(?:I\'m|this is)\s+([A-Z][a-z]+)",
                re.IGNORECASE,
            ),
            "third_person_intro": re.compile(
                r"\b(?:this is|meet|introducing)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
                re.IGNORECASE,
            ),
            # Role-based introductions
            "role_intro": re.compile(
                r"\b(?:I\'m the|as the|from)\s+(CEO|CTO|manager|director|lead|president|VP|vice president)",
                re.IGNORECASE,
            ),
            "department_intro": re.compile(
                r"\b(?:I\'m from|I work in|from the)\s+(marketing|sales|engineering|HR|finance|operations)",
                re.IGNORECASE,
            ),
            # Direct addressing patterns
            "thanks_pattern": re.compile(
                r"\b(?:thanks?|thank you),?\s+([A-Z][a-z]+)", re.IGNORECASE
            ),
            "addressing_pattern": re.compile(
                r"\b([A-Z][a-z]+),?\s+(?:what do you think|your thoughts|can you)",
                re.IGNORECASE,
            ),
            # Meeting context patterns
            "meeting_leader": re.compile(
                r"\b(?:let\'s start|welcome everyone|good morning everyone|shall we begin)",
                re.IGNORECASE,
            ),
            "presenter": re.compile(
                r"\b(?:next slide|as you can see|moving on to|in conclusion)",
                re.IGNORECASE,
            ),
            # Question/answer patterns
            "question_asker": re.compile(
                r"\b(?:I have a question|can I ask|quick question)", re.IGNORECASE
            ),
            "answer_giver": re.compile(
                r"\b(?:good question|to answer that|that\'s a great point)",
                re.IGNORECASE,
            ),
        }

    def _load_common_names(self):
        """Load common names for validation and suggestions."""
        # Common first names for validation
        self.common_first_names = {
            "male": [
                "John",
                "Michael",
                "David",
                "James",
                "Robert",
                "William",
                "Richard",
                "Thomas",
                "Christopher",
                "Daniel",
                "Matthew",
                "Anthony",
                "Mark",
                "Donald",
                "Steven",
                "Paul",
                "Andrew",
                "Joshua",
                "Kenneth",
                "Kevin",
            ],
            "female": [
                "Mary",
                "Patricia",
                "Jennifer",
                "Linda",
                "Elizabeth",
                "Barbara",
                "Susan",
                "Jessica",
                "Sarah",
                "Karen",
                "Nancy",
                "Lisa",
                "Betty",
                "Helen",
                "Sandra",
                "Donna",
                "Carol",
                "Ruth",
                "Sharon",
                "Michelle",
            ],
            "neutral": [
                "Alex",
                "Taylor",
                "Jordan",
                "Casey",
                "Riley",
                "Avery",
                "Quinn",
                "Sage",
                "River",
                "Phoenix",
                "Rowan",
                "Skyler",
                "Cameron",
                "Drew",
            ],
        }

        # Professional titles and roles
        self.professional_roles = {
            "leadership": [
                "CEO",
                "CTO",
                "CFO",
                "President",
                "VP",
                "Director",
                "Manager",
            ],
            "technical": [
                "Engineer",
                "Developer",
                "Architect",
                "Analyst",
                "Specialist",
            ],
            "business": ["Sales", "Marketing", "Operations", "Strategy", "Consultant"],
            "support": ["HR", "Admin", "Assistant", "Coordinator", "Representative"],
        }

    def suggest_names_from_context(
        self, speaker_texts: list[str], metadata: dict | None = None
    ) -> list[tuple[str, float]]:
        """
        Analyze speech patterns and content for name suggestions.

        Args:
            speaker_texts: List of text segments from the speaker
            metadata: Optional YouTube/podcast metadata (title, description, channel)

        Returns:
            List of (suggested_name, confidence_score) tuples
        """
        try:
            all_text = " ".join(speaker_texts)
            suggestions = []

            # NEW: Try metadata-based extraction first (highest priority for podcasts)
            if metadata:
                metadata_names = self._extract_names_from_metadata(metadata)
                suggestions.extend(metadata_names)

            # Try direct name extraction
            direct_names = self._extract_direct_names(all_text)
            suggestions.extend(direct_names)

            # Try role-based suggestions
            role_suggestions = self._suggest_from_roles(all_text)
            suggestions.extend(role_suggestions)

            # Try behavioral pattern suggestions
            behavior_suggestions = self._suggest_from_behavior(all_text, speaker_texts)
            suggestions.extend(behavior_suggestions)

            # Try historical matching
            historical_suggestions = self._suggest_from_history(all_text)
            suggestions.extend(historical_suggestions)

            # Deduplicate and sort by confidence
            unique_suggestions = self._deduplicate_suggestions(suggestions)

            # Limit to top 5 suggestions
            return sorted(unique_suggestions, key=lambda x: x[1], reverse=True)[:5]

        except Exception as e:
            logger.error(f"Error generating name suggestions: {e}")
            return []

    def _extract_names_from_metadata(self, metadata: dict) -> list[tuple[str, float]]:
        """
        Extract speaker names from YouTube/podcast metadata.
        Optimized for informal interviews like Joe Rogan podcasts.

        Args:
            metadata: Dictionary containing title, description, uploader, etc.

        Returns:
            List of (suggested_name, confidence_score) tuples
        """
        suggestions = []

        try:
            title = metadata.get("title", "").lower()
            description = metadata.get("description", "").lower()
            uploader = metadata.get("uploader", "").lower()

            # Common podcast patterns
            podcast_hosts = {
                "joe rogan": ["joe rogan", "jre"],
                "lex fridman": ["lex fridman", "lex"],
                "jordan peterson": ["jordan peterson", "peterson"],
                "sam harris": ["sam harris", "harris"],
                "tim ferriss": ["tim ferriss", "tim ferris"],
                "naval ravikant": ["naval", "ravikant"],
                "andrew huberman": ["huberman", "andrew huberman"],
                "dan carlin": ["dan carlin", "hardcore history"],
                "ben shapiro": ["ben shapiro", "shapiro"],
                "dave rubin": ["dave rubin", "rubin"],
                "eric weinstein": ["eric weinstein", "weinstein"],
                "bret weinstein": ["bret weinstein"],
                "jordan harbinger": ["jordan harbinger"],
                "rogan": ["joe rogan"],  # Common shorthand
            }

            # Extract channel-based host identification
            for host_name, identifiers in podcast_hosts.items():
                for identifier in identifiers:
                    if identifier in uploader:
                        suggestions.append((host_name.title(), 0.9))
                        break

            # Pattern: "Host with Guest" or "Guest on Host"
            # Examples: "Jordan Peterson with Sam Harris", "Sam Harris on Joe Rogan"
            interview_patterns = [
                r"(\w+\s+\w+)\s+with\s+(\w+\s+\w+)",  # "Peterson with Harris"
                r"(\w+\s+\w+)\s+on\s+(\w+\s+\w+)",  # "Harris on Rogan"
                r"(\w+\s+\w+)\s+interviews?\s+(\w+\s+\w+)",  # "Rogan interviews Peterson"
                r"(\w+\s+\w+)\s+talks?\s+with\s+(\w+\s+\w+)",  # "Peterson talks with Harris"
                r"(\w+\s+\w+)\s+&\s+(\w+\s+\w+)",  # "Peterson & Harris"
                r"(\w+\s+\w+)\s+and\s+(\w+\s+\w+)",  # "Peterson and Harris"
                r"(\w+\s+\w+)\s+vs\.?\s+(\w+\s+\w+)",  # "Peterson vs Harris"
            ]

            search_text = f"{title} {description}"

            for pattern in interview_patterns:
                matches = re.finditer(pattern, search_text, re.IGNORECASE)
                for match in matches:
                    name1 = self._clean_name(match.group(1))
                    name2 = self._clean_name(match.group(2))

                    if name1 and len(name1.split()) == 2:
                        suggestions.append((name1, 0.85))
                    if name2 and len(name2.split()) == 2:
                        suggestions.append((name2, 0.85))

            # Extract names from title using common name patterns
            # Look for capitalized first + last names
            name_pattern = r"\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b"
            title_names = re.findall(name_pattern, metadata.get("title", ""))

            for name in title_names:
                clean_name = self._clean_name(name)
                if clean_name and self._is_likely_person_name(clean_name):
                    suggestions.append((clean_name, 0.75))

            # Guest identification from description
            guest_patterns = [
                r"guest:\s*([A-Z][a-z]+\s+[A-Z][a-z]+)",
                r"featuring\s+([A-Z][a-z]+\s+[A-Z][a-z]+)",
                r"with\s+guest\s+([A-Z][a-z]+\s+[A-Z][a-z]+)",
            ]

            for pattern in guest_patterns:
                matches = re.findall(pattern, description, re.IGNORECASE)
                for match in matches:
                    clean_name = self._clean_name(match)
                    if clean_name:
                        suggestions.append((clean_name, 0.8))

            logger.debug(f"Metadata extraction found {len(suggestions)} suggestions")
            return suggestions

        except Exception as e:
            logger.warning(f"Error extracting names from metadata: {e}")
            return []

    def _clean_name(self, name: str) -> str:
        """Clean and normalize a name."""
        if not name:
            return ""

        # Remove common prefixes/suffixes
        name = re.sub(
            r"\b(dr\.?|mr\.?|ms\.?|mrs\.?|prof\.?)\s+", "", name, flags=re.IGNORECASE
        )
        name = re.sub(r"\s+(jr\.?|sr\.?|ii|iii)$", "", name, flags=re.IGNORECASE)

        # Title case
        return " ".join(word.capitalize() for word in name.split())

    def _is_likely_person_name(self, name: str) -> bool:
        """Check if a string is likely a person's name."""
        words = name.split()
        if len(words) != 2:
            return False

        # Exclude common non-name patterns
        excluded_words = {
            "youtube",
            "podcast",
            "show",
            "episode",
            "part",
            "season",
            "channel",
            "media",
            "news",
            "radio",
            "tv",
            "network",
            "joe rogan",
            "experience",  # Avoid duplicating known hosts
        }

        name_lower = name.lower()
        return not any(excluded in name_lower for excluded in excluded_words)

    def _extract_direct_names(self, text: str) -> list[tuple[str, float]]:
        """Extract names directly mentioned in the text."""
        suggestions = []

        # Check each pattern
        for pattern_name, pattern in self.patterns.items():
            if (
                "intro" in pattern_name
                or "thanks" in pattern_name
                or "addressing" in pattern_name
            ):
                matches = pattern.findall(text)
                for match in matches:
                    name = match.strip().title()
                    if self._is_valid_name(name):
                        confidence = 0.9 if "formal" in pattern_name else 0.8
                        suggestions.append((name, confidence))

        return suggestions

    def _suggest_from_roles(self, text: str) -> list[tuple[str, float]]:
        """Suggest generic names based on detected roles."""
        suggestions = []

        # Check for role indicators
        role_matches = self.patterns["role_intro"].findall(text)
        dept_matches = self.patterns["department_intro"].findall(text)

        for role in role_matches:
            role_title = role.title()
            suggestions.append((f"{role_title}", 0.6))

        for dept in dept_matches:
            dept_name = dept.title()
            suggestions.append((f"{dept_name} Rep", 0.5))

        return suggestions

    def _suggest_from_behavior(
        self, all_text: str, segments: list[str]
    ) -> list[tuple[str, float]]:
        """Suggest names based on speaking behavior and patterns."""
        suggestions = []

        # Analyze speaking patterns
        total_length = len(all_text)
        segment_count = len(segments)
        total_length / segment_count if segment_count > 0 else 0

        # Check for meeting leadership patterns
        if self.patterns["meeting_leader"].search(all_text):
            suggestions.append(("Meeting Leader", 0.7))

        # Check for presenter patterns
        if self.patterns["presenter"].search(all_text):
            suggestions.append(("Presenter", 0.7))

        # Check for question/answer patterns
        question_count = len(self.patterns["question_asker"].findall(all_text))
        answer_count = len(self.patterns["answer_giver"].findall(all_text))

        if question_count > answer_count and question_count > 2:
            suggestions.append(("Participant", 0.5))
        elif answer_count > question_count and answer_count > 2:
            suggestions.append(("Expert", 0.6))

        # Analyze formality
        formal_indicators = [
            "furthermore",
            "therefore",
            "consequently",
            "regarding",
            "pursuant",
        ]
        informal_indicators = ["yeah", "um", "like", "you know", "basically"]

        formal_count = sum(
            1 for indicator in formal_indicators if indicator in all_text.lower()
        )
        informal_count = sum(
            1 for indicator in informal_indicators if indicator in all_text.lower()
        )

        if formal_count > informal_count and formal_count > 2:
            suggestions.append(("Formal Speaker", 0.4))
        elif informal_count > formal_count and informal_count > 3:
            suggestions.append(("Casual Speaker", 0.4))

        # Speaking time analysis
        if total_length > 1000:  # Long speaker
            suggestions.append(("Main Speaker", 0.5))
        elif total_length < 200:  # Short speaker
            suggestions.append(("Brief Participant", 0.4))

        return suggestions

    def _suggest_from_history(self, text: str) -> list[tuple[str, float]]:
        """Suggest names based on historical speaker data."""
        suggestions = []

        try:
            # Get previously learned speakers
            voices = self.db_service.find_matching_voices({}, threshold=0.5)

            # Simple text similarity matching (can be enhanced with better algorithms)
            for voice in voices:
                # For now, suggest based on usage frequency
                if voice.usage_count > 5:  # Frequently used speaker
                    suggestions.append((voice.name, 0.3))

        except Exception as e:
            logger.warning(f"Error accessing speaker history: {e}")

        return suggestions

    def _is_valid_name(self, name: str) -> bool:
        """Validate if a string looks like a real name."""
        if not name or len(name) < 2:
            return False

        # Check if it's in common names
        name_parts = name.split()
        if len(name_parts) > 0:
            first_name = name_parts[0]
            all_names = (
                self.common_first_names["male"]
                + self.common_first_names["female"]
                + self.common_first_names["neutral"]
            )
            if first_name in all_names:
                return True

        # Check basic name patterns
        if re.match(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*$", name):
            # Avoid common false positives
            false_positives = [
                "Thank You",
                "Good Morning",
                "Next Steps",
                "Moving Forward",
                "Let Me",
                "Right Now",
                "Last Week",
                "Next Time",
            ]
            if name not in false_positives:
                return True

        return False

    def _deduplicate_suggestions(
        self, suggestions: list[tuple[str, float]]
    ) -> list[tuple[str, float]]:
        """Remove duplicate suggestions and combine confidence scores."""
        name_scores = {}

        for name, confidence in suggestions:
            if name in name_scores:
                # Take the higher confidence score
                name_scores[name] = max(name_scores[name], confidence)
            else:
                name_scores[name] = confidence

        return list(name_scores.items())

    def suggest_names_from_calendar(self, meeting_time: datetime) -> list[str]:
        """
        Suggest names from calendar integration (future enhancement).

        Args:
            meeting_time: Time of the meeting/recording

        Returns:
            List of suggested names from calendar
        """
        # Placeholder for future calendar integration
        logger.info("Calendar integration not yet implemented")
        return []

    def suggest_names_from_contacts(self, email_context: str) -> list[str]:
        """
        Suggest names from email/contact integration (future enhancement).

        Args:
            email_context: Email context or meeting invitation

        Returns:
            List of suggested names from contacts
        """
        # Placeholder for future contact integration
        logger.info("Contact integration not yet implemented")
        return []

    def learn_speaker_voice_patterns(
        self, speaker_id: str, audio_features: dict[str, Any], assigned_name: str
    ):
        """
        Learn voice characteristics for future recognition.

        Args:
            speaker_id: Original speaker ID
            audio_features: Audio characteristics (future enhancement)
            assigned_name: User-assigned name
        """
        try:
            # Create or update voice profile
            voice_data = SpeakerVoiceModel(
                name=assigned_name,
                voice_fingerprint=audio_features,
                confidence_threshold=0.7,
            )

            existing_voice = self.db_service.get_speaker_voice_by_name(assigned_name)
            if existing_voice:
                # Update existing voice profile
                self.db_service.update_voice_usage(existing_voice.id)
                logger.info(f"Updated voice profile for '{assigned_name}'")
            else:
                # Create new voice profile
                new_voice = self.db_service.create_speaker_voice(voice_data)
                if new_voice:
                    logger.info(f"Created new voice profile for '{assigned_name}'")

        except Exception as e:
            logger.error(f"Error learning speaker voice patterns: {e}")

    def analyze_speaker_consistency(self, folder_path: Path) -> dict[str, Any]:
        """
        Analyze speaker consistency across multiple recordings in a folder.

        Args:
            folder_path: Path to folder containing recordings

        Returns:
            Analysis results with suggested consistent speakers
        """
        try:
            # Get all assignments in the folder
            assignments = []
            for audio_file in folder_path.glob(
                "*.mp3"
            ):  # Add more extensions as needed
                file_assignments = self.db_service.get_assignments_for_recording(
                    str(audio_file)
                )
                assignments.extend(file_assignments)

            if not assignments:
                return {"consistent_speakers": [], "suggestions": []}

            # Analyze name frequency
            name_counts = Counter(
                [assignment.assigned_name for assignment in assignments]
            )

            # Find consistent speakers (appear in multiple recordings)
            consistent_speakers = [
                name for name, count in name_counts.items() if count > 1
            ]

            # Generate suggestions for new recordings
            suggestions = [
                {"name": name, "frequency": count, "confidence": min(0.8, count * 0.2)}
                for name, count in name_counts.most_common(5)
            ]

            return {
                "consistent_speakers": consistent_speakers,
                "suggestions": suggestions,
                "total_recordings": len(
                    {assignment.recording_path for assignment in assignments}
                ),
                "unique_speakers": len(name_counts),
            }

        except Exception as e:
            logger.error(f"Error analyzing speaker consistency: {e}")
            return {"consistent_speakers": [], "suggestions": []}

    def get_speaker_suggestions_for_new_recording(
        self, folder_path: Path, speaker_count: int
    ) -> list[dict[str, Any]]:
        """
        Get speaker suggestions for a new recording based on folder history.

        Args:
            folder_path: Path to folder containing recordings
            speaker_count: Number of speakers detected in new recording

        Returns:
            List of speaker suggestions with confidence scores
        """
        try:
            consistency_analysis = self.analyze_speaker_consistency(folder_path)
            suggestions = consistency_analysis.get("suggestions", [])

            # Limit suggestions to the number of detected speakers
            return suggestions[:speaker_count]

        except Exception as e:
            logger.error(f"Error getting speaker suggestions for new recording: {e}")
            return []

    def validate_speaker_assignment(
        self, speaker_name: str, context_text: str
    ) -> tuple[bool, float]:
        """
        Validate if a speaker assignment makes sense given the context.

        Args:
            speaker_name: Proposed speaker name
            context_text: Text context for validation

        Returns:
            Tuple of (is_valid, confidence_score)
        """
        try:
            # Check if name appears in the text
            if speaker_name.lower() in context_text.lower():
                return True, 0.9

            # Check if it's a reasonable name
            if self._is_valid_name(speaker_name):
                return True, 0.7

            # Check if it's a role-based assignment
            all_roles = []
            for role_list in self.professional_roles.values():
                all_roles.extend(role_list)

            if any(role.lower() in speaker_name.lower() for role in all_roles):
                return True, 0.6

            # Default validation
            return True, 0.5

        except Exception as e:
            logger.error(f"Error validating speaker assignment: {e}")
            return True, 0.5  # Default to valid with low confidence


class SpeakerContextAnalyzer:
    """Analyze speaker context and relationships."""

    def __init__(self):
        """Initialize the context analyzer."""
        self.suggester = SpeakerNameSuggester()

    def analyze_speaker_interactions(
        self, segments: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Analyze interactions between speakers.

        Args:
            segments: List of speaker segments with timing and text

        Returns:
            Analysis of speaker interactions and relationships
        """
        try:
            interactions = {}
            speaker_stats = {}

            # Analyze each segment
            for i, segment in enumerate(segments):
                speaker_id = segment.get("speaker_id", "UNKNOWN")
                text = segment.get("text", "")

                # Update speaker statistics
                if speaker_id not in speaker_stats:
                    speaker_stats[speaker_id] = {
                        "total_time": 0,
                        "segment_count": 0,
                        "word_count": 0,
                        "questions_asked": 0,
                        "responses_given": 0,
                    }

                stats = speaker_stats[speaker_id]
                stats["segment_count"] += 1
                stats["total_time"] += segment.get("end", 0) - segment.get("start", 0)
                stats["word_count"] += len(text.split())

                # Count questions and responses
                if "?" in text:
                    stats["questions_asked"] += text.count("?")

                # Look for response patterns
                response_patterns = ["yes", "no", "exactly", "that's right", "I agree"]
                if any(pattern in text.lower() for pattern in response_patterns):
                    stats["responses_given"] += 1

                # Analyze speaker transitions
                if i > 0:
                    prev_speaker = segments[i - 1].get("speaker_id")
                    if prev_speaker != speaker_id:
                        interaction_key = f"{prev_speaker}->{speaker_id}"
                        interactions[interaction_key] = (
                            interactions.get(interaction_key, 0) + 1
                        )

            return {
                "speaker_stats": speaker_stats,
                "interactions": interactions,
                "dominant_speaker": max(
                    speaker_stats.keys(), key=lambda x: speaker_stats[x]["total_time"]
                ),
                "most_interactive": self._find_most_interactive_speakers(interactions),
            }

        except Exception as e:
            logger.error(f"Error analyzing speaker interactions: {e}")
            return {}

    def _find_most_interactive_speakers(
        self, interactions: dict[str, int]
    ) -> list[str]:
        """Find speakers with the most interactions."""
        speaker_interaction_counts = {}

        for interaction, count in interactions.items():
            speakers = interaction.split("->")
            for speaker in speakers:
                speaker_interaction_counts[speaker] = (
                    speaker_interaction_counts.get(speaker, 0) + count
                )

        # Return top 3 most interactive speakers
        return sorted(
            speaker_interaction_counts.keys(),
            key=lambda x: speaker_interaction_counts[x],
            reverse=True,
        )[:3]
