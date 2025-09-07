"""
LLM Speaker Suggestion Module

Simple approach: LLM reads metadata + first 5 statements per speaker and makes best guess.
User can override anything in the popup dialog.
"""

import json
from typing import Any, Dict, List, Optional, Tuple

from ..config import get_settings
from ..logger import get_logger
from ..utils.llm_providers import UnifiedLLMClient

logger = get_logger(__name__)


class LLMSpeakerSuggester:
    """Simple LLM-based speaker name suggestions."""

    def __init__(self):
        """Initialize the LLM speaker suggester."""
        self.settings = get_settings()
        self.llm_client = None
        self._initialize_llm()

    def _initialize_llm(self):
        """Initialize LLM client for suggestions."""
        try:
            self.llm_client = UnifiedLLMClient(
                provider=self.settings.llm.provider,
                model=self.settings.llm.model,
                temperature=0.3,  # Slightly higher for more creative name suggestions
            )
            logger.info(f"LLM Speaker Suggester ready")
        except Exception as e:
            logger.warning(f"LLM not available for speaker suggestions: {e}")
            self.llm_client = None

    def suggest_speaker_names(
        self,
        speaker_segments: dict[str, list[dict]],
        metadata: dict | None = None,
    ) -> dict[str, tuple[str, float]]:
        """
        Simple LLM suggestion: read metadata + first 5 statements and guess.

        Args:
            speaker_segments: Dict mapping speaker_id to list of speech segments
            metadata: Video/podcast metadata (title, description, uploader, etc.)

        Returns:
            Dict mapping speaker_id to (suggested_name, confidence_score)
        """
        if not self.llm_client:
            logger.info("LLM not available - using simple fallback names")
            return self._simple_fallback(speaker_segments)

        try:
            # Create simple prompt with metadata + first 5 statements per speaker
            prompt = self._create_simple_prompt(speaker_segments, metadata)

            # Get LLM suggestions
            response = self.llm_client.generate(prompt=prompt)

            # Parse response
            suggestions = self._parse_suggestions(response.content, speaker_segments)

            logger.info(f"LLM suggested names for {len(suggestions)} speakers")
            return suggestions

        except Exception as e:
            logger.error(f"LLM suggestion failed: {e}")
            return self._simple_fallback(speaker_segments)

    def _create_simple_prompt(
        self, speaker_segments: dict[str, list[dict]], metadata: dict | None
    ) -> str:
        """Create simple LLM prompt with metadata + first 5 statements."""

        # Build metadata section
        metadata_text = "No metadata available"
        if metadata:
            parts = []
            if metadata.get("title"):
                parts.append(f"Title: {metadata['title']}")
            if metadata.get("uploader"):
                parts.append(f"Channel: {metadata['uploader']}")
            if metadata.get("description"):
                desc = (
                    metadata["description"][:300] + "..."
                    if len(metadata["description"]) > 300
                    else metadata["description"]
                )
                parts.append(f"Description: {desc}")
            if parts:
                metadata_text = "\n".join(parts)

        # Build speaker sections with first 5 statements
        speaker_sections = []
        for speaker_id, segments in speaker_segments.items():
            # Get first 5 non-empty statements
            statements = []
            for seg in segments[:10]:  # Look at first 10 segments to find 5 good ones
                text = seg.get("text", "").strip()
                if text and len(text) > 10:  # Only substantial statements
                    statements.append(text)
                if len(statements) >= 5:
                    break

            speaker_section = f"\n{speaker_id}:"
            for i, statement in enumerate(statements, 1):
                # Limit statement length for prompt efficiency
                clean_statement = (
                    statement[:150] + "..." if len(statement) > 150 else statement
                )
                speaker_section += f'\n  {i}. "{clean_statement}"'

            if not statements:
                speaker_section += "\n  (No clear statements found)"

            speaker_sections.append(speaker_section)

        speakers_text = "".join(speaker_sections)

        prompt = f"""Based on the metadata and speech samples, guess who each speaker is.

METADATA:
{metadata_text}

SPEAKERS AND THEIR FIRST STATEMENTS:
{speakers_text}

Look for:
- Names mentioned in title/description
- Speaking patterns (who asks questions vs answers)
- Context clues about roles (host, guest, expert, etc.)

If you can identify actual names, use them. Otherwise, use descriptive roles like "Host", "Guest", "Interviewer".

Respond in JSON format:
{{
    "SPEAKER_00": {{"name": "Best guess name", "confidence": 0.8}},
    "SPEAKER_01": {{"name": "Best guess name", "confidence": 0.7}}
}}

Confidence scale: 0.9+ = very sure, 0.7-0.8 = confident, 0.5-0.6 = decent guess, 0.3-0.4 = uncertain"""

        return prompt

    def _parse_suggestions(
        self, response: str, speaker_segments: dict[str, list[dict]]
    ) -> dict[str, tuple[str, float]]:
        """Parse LLM response into suggestions."""
        try:
            # Extract JSON from response
            response_text = response.strip()
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}") + 1

            if start_idx >= 0 and end_idx > start_idx:
                json_text = response_text[start_idx:end_idx]
                llm_result = json.loads(json_text)
            else:
                logger.warning("No JSON found in LLM response")
                return self._simple_fallback(speaker_segments)

            suggestions = {}

            for speaker_id in speaker_segments.keys():
                if speaker_id in llm_result:
                    suggestion_data = llm_result[speaker_id]
                    suggested_name = suggestion_data.get(
                        "name", f"Speaker {speaker_id[-2:]}"
                    )
                    confidence = float(suggestion_data.get("confidence", 0.5))

                    # Validate confidence range
                    confidence = max(0.1, min(1.0, confidence))

                    suggestions[speaker_id] = (suggested_name, confidence)
                    logger.debug(
                        f"LLM: {speaker_id} -> '{suggested_name}' ({confidence:.1f})"
                    )
                else:
                    # Fallback for missing speakers
                    suggestions[speaker_id] = (f"Speaker {speaker_id[-2:]}", 0.3)

            return suggestions

        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            return self._simple_fallback(speaker_segments)

    def _simple_fallback(
        self, speaker_segments: dict[str, list[dict]]
    ) -> dict[str, tuple[str, float]]:
        """Simple fallback when LLM is not available."""
        suggestions = {}

        # Just use Speaker 1, Speaker 2, etc.
        for i, speaker_id in enumerate(sorted(speaker_segments.keys()), 1):
            suggestions[speaker_id] = (f"Speaker {i}", 0.3)

        return suggestions


def suggest_speaker_names_with_llm(
    speaker_segments: dict[str, list[dict]],
    metadata: dict | None = None,
) -> dict[str, tuple[str, float]]:
    """
    Convenience function for LLM speaker suggestions.

    Args:
        speaker_segments: Dict mapping speaker_id to list of speech segments
        metadata: Optional metadata (title, description, etc.)

    Returns:
        Dict mapping speaker_id to (suggested_name, confidence_score)
    """
    suggester = LLMSpeakerSuggester()
    return suggester.suggest_speaker_names(speaker_segments, metadata)
