"""
LLM Speaker Suggestion Module

Simple approach: LLM reads metadata + first 5 statements per speaker and makes best guess.
User can override anything in the popup dialog.
"""

import json

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
            # Try to use configured LLM (cloud or local)
            if self._try_configured_llm():
                return

            # Try to use MVP LLM if available
            if self._try_mvp_llm():
                return

            # No LLM available
            logger.info(
                "No LLM available - speaker suggestions will use smart fallback"
            )
            self.llm_client = None

        except Exception as e:
            logger.info(f"LLM initialization failed - using smart fallback: {e}")
            self.llm_client = None

    def _try_configured_llm(self) -> bool:
        """Try to initialize with user's configured LLM."""
        try:
            # Check if cloud LLM is configured
            if (
                self.settings.llm.provider == "openai"
                and self.settings.api_keys.openai_api_key
            ):
                self.llm_client = UnifiedLLMClient(
                    provider=self.settings.llm.provider,
                    model=self.settings.llm.model,
                    temperature=0.3,
                )
                logger.info(
                    f"Using configured LLM: {self.settings.llm.provider}/{self.settings.llm.model}"
                )
                return True
            elif (
                self.settings.llm.provider == "anthropic"
                and self.settings.api_keys.anthropic_api_key
            ):
                self.llm_client = UnifiedLLMClient(
                    provider=self.settings.llm.provider,
                    model=self.settings.llm.model,
                    temperature=0.3,
                )
                logger.info(
                    f"Using configured LLM: {self.settings.llm.provider}/{self.settings.llm.model}"
                )
                return True

            # Check if local LLM is configured
            if self.settings.llm.provider == "local":
                self.llm_client = UnifiedLLMClient(
                    provider="local",
                    model=self.settings.llm.local_model,
                    temperature=0.3,
                )
                logger.info(
                    f"Using configured local LLM: {self.settings.llm.local_model}"
                )
                return True

            return False

        except Exception as e:
            logger.debug(f"Configured LLM not available: {e}")
            return False

    def _try_mvp_llm(self) -> bool:
        """Try to initialize with MVP LLM."""
        try:
            from .mvp_llm_setup import get_mvp_llm_setup

            setup = get_mvp_llm_setup()
            if setup.is_mvp_ready():
                mvp_model = setup.get_available_mvp_model()
                if mvp_model:
                    self.llm_client = UnifiedLLMClient(
                        provider="local",
                        model=mvp_model,
                        temperature=0.3,
                    )
                    logger.info(f"Using MVP LLM: {mvp_model}")
                    return True

            return False

        except Exception as e:
            logger.debug(f"MVP LLM not available: {e}")
            return False

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
            # Debug logging
            logger.debug(f"LLM suggester called with {len(speaker_segments)} speakers")
            logger.debug(
                f"Metadata keys: {list(metadata.keys()) if metadata else 'None'}"
            )
            for speaker_id, segments in speaker_segments.items():
                logger.debug(f"  {speaker_id}: {len(segments)} segments")

            # Create simple prompt with metadata + first 5 statements per speaker
            prompt = self._create_simple_prompt(speaker_segments, metadata)

            # Debug log the prompt
            logger.debug(f"Generated prompt (first 500 chars): {prompt[:500]}...")

            # Get LLM suggestions
            response = self.llm_client.generate(prompt=prompt)

            # Debug log the response
            logger.debug(f"LLM response (first 500 chars): {response.content[:500]}...")

            # Parse response
            suggestions = self._parse_suggestions(response.content, speaker_segments)

            logger.info(f"LLM suggested names for {len(suggestions)} speakers")
            for speaker_id, (name, conf) in suggestions.items():
                logger.info(f"  {speaker_id} -> '{name}' (confidence: {conf:.2f})")

            return suggestions

        except Exception as e:
            logger.error(f"LLM suggestion failed: {e}", exc_info=True)
            return self._simple_fallback(speaker_segments)

    def _create_simple_prompt(
        self, speaker_segments: dict[str, list[dict]], metadata: dict | None
    ) -> str:
        """Create strict JSON-only prompt with metadata + first 5 statements."""

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

        # Build speaker sections with first 5 statements (sorted chronologically)
        speaker_sections: list[str] = []
        # Use a stable order for keys to reduce variability between runs
        ordered_speaker_ids = sorted(speaker_segments.keys())
        for speaker_id in ordered_speaker_ids:
            segments = speaker_segments.get(speaker_id, [])
            # Sort by start time if available
            segments_sorted = sorted(
                segments,
                key=lambda s: (
                    s.get("start", float("in")),
                    s.get("end", float("in")),
                ),
            )

            # Get first 5 non-empty statements
            statements: list[str] = []
            for seg in segments_sorted[
                :10
            ]:  # Look at first 10 segments to find 5 good ones
                text = str(seg.get("text", "")).strip()
                if text and len(text) > 10:  # Only substantial statements
                    statements.append(text)
                if len(statements) >= 5:
                    break

            # Debug logging
            logger.debug(
                f"Speaker {speaker_id} has {len(statements)} statements extracted from {len(segments)} total segments"
            )

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

        # Build a strict JSON skeleton with the exact keys we expect
        skeleton_lines = [
            f'    "{sid}": {{"name": "", "confidence": 0.5}}'
            for sid in ordered_speaker_ids
        ]
        json_skeleton = "{\n" + ",\n".join(skeleton_lines) + "\n}"

        prompt = (
            "You are labeling speakers in an interview/podcast transcript.\n\n"
            "INSTRUCTIONS:\n"
            "- The ONLY purpose is to identify proper names in the metadata and transcript snippets and then map each to the correct speaker ID.  \n"
            "- Do NOT use roles or descriptions (e.g., Host, Guest, Interviewer). Use only the exact names you have found in your analysis of the metadata and transcript snippets only.\n"
            "- Output STRICTLY VALID JSON ONLY. No markdown, no prose, no comments.\n"
            "- Keys MUST EXACTLY match the speaker IDs provided. Do not add or remove keys.\n"
            "- Confidence is a number between 0.1 and 1.0.\n\n"
            f"METADATA:\n{metadata_text}\n\n"
            f"SPEAKERS AND THEIR FIRST STATEMENTS:\n{speakers_text}\n\n"
            "Return only a single JSON object matching this skeleton (fill in values):\n"
            f"{json_skeleton}\n"
        )

        return prompt

    def _parse_suggestions(
        self, response: str, speaker_segments: dict[str, list[dict]]
    ) -> dict[str, tuple[str, float]]:
        """Parse LLM response into suggestions."""
        try:
            # Extract JSON from response (strip any leading prose or markdown fences)
            response_text = (response or "").strip()
            if response_text.startswith("```"):
                # Remove markdown fence if present
                # e.g., ```json\n{...}\n```
                parts = response_text.split("```")
                # Choose the largest brace-containing part
                candidates = [p for p in parts if "{" in p and "}" in p]
                response_text = (
                    max(candidates, key=len) if candidates else response_text
                )

            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}") + 1

            if start_idx >= 0 and end_idx > start_idx:
                json_text = response_text[start_idx:end_idx]
                llm_result = json.loads(json_text)
            else:
                logger.warning("No JSON found in LLM response")
                return self._simple_fallback(speaker_segments)

            # Normalize keys from the model (e.g., SPEAKER_0 -> SPEAKER_00)
            def normalize_key(k: str) -> str:
                k = str(k).strip().upper().replace(" ", "_")
                # Extract numeric suffix if present
                import re

                m = re.search(r"SPEAKER[_\-\s]*(\d+)$", k)
                if m:
                    num = int(m.group(1))
                    return f"SPEAKER_{num:02d}"
                return k

            normalized_llm = {normalize_key(k): v for k, v in dict(llm_result).items()}

            suggestions: dict[str, tuple[str, float]] = {}
            for speaker_id in speaker_segments.keys():
                candidate = None
                if speaker_id in llm_result:
                    candidate = llm_result[speaker_id]
                else:
                    norm_id = normalize_key(speaker_id)
                    if norm_id in normalized_llm:
                        candidate = normalized_llm[norm_id]

                if isinstance(candidate, dict):
                    suggested_name = str(
                        candidate.get("name", f"Speaker {speaker_id[-2:]}")
                    ).strip()
                    # Sanitize name
                    if len(suggested_name) > 60:
                        suggested_name = suggested_name[:57] + "..."
                    if "\n" in suggested_name:
                        suggested_name = " ".join(suggested_name.split())

                    conf_raw = candidate.get("confidence", 0.5)
                    try:
                        confidence = float(conf_raw)
                    except Exception:
                        confidence = 0.5
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
        """Simple generic names when LLM is not available (LLM or nothing approach)."""
        suggestions = {}

        # Just assign generic numbered names - no pattern analysis
        for speaker_id in sorted(speaker_segments.keys()):
            # Extract speaker number from ID (e.g., SPEAKER_00 -> 00)
            speaker_num = speaker_id.replace("SPEAKER_", "").lstrip("0") or "0"
            generic_name = f"Speaker {int(speaker_num) + 1}"
            suggestions[speaker_id] = (generic_name, 0.2)  # Low confidence

        logger.info("No LLM available - using generic speaker names")
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
