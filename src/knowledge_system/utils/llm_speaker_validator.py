"""
LLM Speaker Validation Module

Provides intelligent speaker assignment validation using LLM analysis of speech content.
This module performs a "first skim" validation of metadata-based speaker assignments
before presenting them to the user for final confirmation.
"""

import json
from typing import Any

from ..config import get_settings
from ..logger import get_logger
from ..utils.llm_providers import UnifiedLLMClient

logger = get_logger(__name__)


class LLMSpeakerValidator:
    """Validates speaker assignments using LLM analysis of speech content."""

    def __init__(self):
        """Initialize the LLM speaker validator."""
        self.settings = get_settings()
        self.llm_client = None
        self._initialize_llm()

    def _initialize_llm(self):
        """Initialize LLM client for validation."""
        try:
            # Always use MVP LLM (local Llama3.2-3B) for speaker validation per user preference
            from .mvp_llm_setup import MVPLLMSetup

            mvp_setup = MVPLLMSetup()

            # Check if MVP LLM is available
            available_model = mvp_setup.get_available_mvp_model()
            if available_model:
                self.llm_client = UnifiedLLMClient(
                    provider="local",
                    model=available_model,
                    temperature=0.1,  # Low temperature for consistent analysis
                )
                logger.info(
                    f"LLM Speaker Validator initialized with MVP LLM: local/{available_model}"
                )
            else:
                logger.warning("MVP LLM not available for speaker validation")
                self.llm_client = None
        except Exception as e:
            logger.warning(f"Failed to initialize MVP LLM for speaker validation: {e}")
            self.llm_client = None

    def validate_speaker_assignments(
        self,
        proposed_assignments: dict[str, str],
        speaker_segments: dict[str, list[dict]],
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        """
        Validate proposed speaker assignments using LLM analysis.

        Args:
            proposed_assignments: Dict mapping speaker_id to proposed name
            speaker_segments: Dict mapping speaker_id to list of speech segments
            metadata: Optional metadata (title, description, etc.)

        Returns:
            Validation result with confidence scores and recommendations
        """
        if not self.llm_client:
            logger.warning("LLM not available for speaker validation")
            return self._fallback_validation(proposed_assignments)

        try:
            # Prepare analysis data
            analysis_data = self._prepare_analysis_data(
                proposed_assignments, speaker_segments, metadata
            )

            # Generate LLM prompt
            prompt = self._create_validation_prompt(analysis_data)

            # Get LLM analysis
            response = self.llm_client.generate(prompt=prompt)

            # Parse and validate response
            validation_result = self._parse_llm_response(
                response.content, proposed_assignments
            )

            logger.info(
                f"LLM speaker validation completed: {len(validation_result.get('validations', {}))} speakers analyzed"
            )
            return validation_result

        except Exception as e:
            logger.error(f"Error in LLM speaker validation: {e}")
            return self._fallback_validation(proposed_assignments)

    def _prepare_analysis_data(
        self,
        assignments: dict[str, str],
        segments: dict[str, list[dict]],
        metadata: dict | None,
    ) -> dict:
        """Prepare data for LLM analysis."""
        analysis_data = {"metadata": metadata or {}, "speakers": {}}

        for speaker_id, assigned_name in assignments.items():
            speaker_segments = segments.get(speaker_id, [])

            # Get first 5 segments for analysis
            first_segments = speaker_segments[:5]
            segment_texts = [
                seg.get("text", "") for seg in first_segments if seg.get("text")
            ]

            # Calculate speaking statistics
            total_duration = sum(
                seg.get("end", 0) - seg.get("start", 0)
                for seg in speaker_segments
                if seg.get("start") is not None and seg.get("end") is not None
            )

            analysis_data["speakers"][speaker_id] = {
                "assigned_name": assigned_name,
                "sample_texts": segment_texts[:5],  # Limit to 5 for analysis
                "segment_count": len(speaker_segments),
                "total_duration": total_duration,
                "first_appearance": (
                    first_segments[0].get("start", 0) if first_segments else 0
                ),
            }

        return analysis_data

    def _create_validation_prompt(self, analysis_data: dict) -> str:
        """Create LLM prompt for speaker validation."""
        metadata = analysis_data.get("metadata", {})
        speakers = analysis_data.get("speakers", {})

        # Build context
        context_lines = []
        if metadata.get("title"):
            context_lines.append(f"Video/Podcast Title: {metadata['title']}")
        if metadata.get("uploader"):
            context_lines.append(f"Channel/Host: {metadata['uploader']}")
        if metadata.get("description"):
            desc = (
                metadata["description"][:200] + "..."
                if len(metadata["description"]) > 200
                else metadata["description"]
            )
            context_lines.append(f"Description: {desc}")

        _context = (
            "\n".join(context_lines) if context_lines else "No metadata available"
        )

        # Build speaker analysis section
        speaker_sections = []
        for speaker_id, data in speakers.items():
            data["assigned_name"]
            sample_texts = data["sample_texts"]
            duration = data["total_duration"]
            data["segment_count"]

            mins, secs = divmod(int(duration), 60)
            _duration_str = f"{mins}:{secs:02d}"

            speaker_section = """
SPEAKER: {assigned_name} (ID: {speaker_id})
- Total speaking time: {duration_str} ({segment_count} segments)
- Sample speech content:
"""
            for i, text in enumerate(sample_texts[:3], 1):
                speaker_section += (
                    f"  {i}. \"{text[:150]}{'...' if len(text) > 150 else ''}\"\n"
                )

            speaker_sections.append(speaker_section)

        _speakers_text = "\n".join(speaker_sections)

        prompt = """You are an expert at analyzing podcast/interview transcripts to validate speaker identity assignments. Your task is to analyze the proposed speaker assignments and determine if they are accurate based on the speech content and context.

CONTEXT:
{context}

PROPOSED SPEAKER ASSIGNMENTS:
{speakers_text}

ANALYSIS INSTRUCTIONS:
1. Analyze each speaker's speech patterns, vocabulary, and content style
2. Consider the metadata context (title, channel, description)
3. Look for identity clues in the speech content (self-references, expertise areas, speaking style)
4. Evaluate if the proposed assignments make logical sense

For each speaker, provide:
- CONFIDENCE: Score from 0.0 to 1.0 indicating confidence in the assignment
- REASONING: Brief explanation of why the assignment seems correct or incorrect
- RECOMMENDATION: "ACCEPT", "REJECT", or "UNCERTAIN"
- ALTERNATIVE: If rejecting, suggest a better name or "Unknown Speaker"

Respond in JSON format:
{{
    "overall_confidence": 0.0-1.0,
    "validation_summary": "brief overall assessment",
    "speaker_validations": {{
        "SPEAKER_1": {{
            "assigned_name": "proposed name",
            "confidence": 0.0-1.0,
            "reasoning": "explanation",
            "recommendation": "ACCEPT/REJECT/UNCERTAIN",
            "alternative_name": "suggested name or null"
        }}
    }}
}}

Focus on accuracy and provide specific reasoning based on the speech content."""

        return prompt

    def _parse_llm_response(
        self, response: str, original_assignments: dict[str, str]
    ) -> dict[str, Any]:
        """Parse and validate LLM response."""
        try:
            # Try to extract JSON from response
            response_text = response.strip()

            # Handle case where response might have extra text around JSON
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}") + 1

            if start_idx >= 0 and end_idx > start_idx:
                json_text = response_text[start_idx:end_idx]
                llm_result = json.loads(json_text)
            else:
                raise ValueError("No valid JSON found in response")

            # Validate and structure the result
            validation_result = {
                "llm_available": True,
                "overall_confidence": llm_result.get("overall_confidence", 0.5),
                "validation_summary": llm_result.get(
                    "validation_summary", "LLM validation completed"
                ),
                "validations": {},
                "recommendations": {},
            }

            speaker_validations = llm_result.get("speaker_validations", {})

            for speaker_id, original_name in original_assignments.items():
                if speaker_id in speaker_validations:
                    validation = speaker_validations[speaker_id]

                    validation_result["validations"][speaker_id] = {
                        "original_assignment": original_name,
                        "llm_confidence": validation.get("confidence", 0.5),
                        "reasoning": validation.get(
                            "reasoning", "No reasoning provided"
                        ),
                        "recommendation": validation.get("recommendation", "UNCERTAIN"),
                        "alternative_name": validation.get("alternative_name"),
                    }

                    # Generate final recommendation
                    recommendation = validation.get("recommendation", "UNCERTAIN")
                    if recommendation == "REJECT" and validation.get(
                        "alternative_name"
                    ):
                        validation_result["recommendations"][speaker_id] = validation[
                            "alternative_name"
                        ]
                    elif recommendation == "ACCEPT":
                        validation_result["recommendations"][speaker_id] = original_name
                    else:
                        validation_result["recommendations"][
                            speaker_id
                        ] = original_name  # Keep original if uncertain
                else:
                    # Default validation for missing speakers
                    validation_result["validations"][speaker_id] = {
                        "original_assignment": original_name,
                        "llm_confidence": 0.5,
                        "reasoning": "Not analyzed by LLM",
                        "recommendation": "UNCERTAIN",
                        "alternative_name": None,
                    }
                    validation_result["recommendations"][speaker_id] = original_name

            return validation_result

        except Exception as e:
            logger.error(f"Error parsing LLM validation response: {e}")
            logger.debug(f"Raw LLM response: {response}")
            return self._fallback_validation(original_assignments)

    def _fallback_validation(self, assignments: dict[str, str]) -> dict[str, Any]:
        """Fallback validation when LLM is not available."""
        return {
            "llm_available": False,
            "overall_confidence": 0.6,  # Moderate confidence without LLM validation
            "validation_summary": "LLM validation not available, using metadata assignments",
            "validations": {
                speaker_id: {
                    "original_assignment": name,
                    "llm_confidence": 0.6,
                    "reasoning": "LLM validation not available",
                    "recommendation": "UNCERTAIN",
                    "alternative_name": None,
                }
                for speaker_id, name in assignments.items()
            },
            "recommendations": assignments.copy(),
        }

    def create_validation_summary_for_user(
        self, validation_result: dict[str, Any]
    ) -> str:
        """Create a human-readable summary of the validation for the user interface."""
        if not validation_result.get("llm_available", False):
            return "🤖 LLM validation not available. Please review assignments manually."

        overall_confidence = validation_result.get("overall_confidence", 0.5)
        summary = validation_result.get("validation_summary", "")
        validations = validation_result.get("validations", {})

        # Count recommendations
        accepts = sum(
            1 for v in validations.values() if v.get("recommendation") == "ACCEPT"
        )
        rejects = sum(
            1 for v in validations.values() if v.get("recommendation") == "REJECT"
        )
        uncertain = sum(
            1 for v in validations.values() if v.get("recommendation") == "UNCERTAIN"
        )

        confidence_emoji = (
            "🟢"
            if overall_confidence > 0.8
            else "🟡"
            if overall_confidence > 0.6
            else "🔴"
        )

        summary_text = (
            f"{confidence_emoji} LLM Analysis (confidence: {overall_confidence:.0%})\n"
        )
        summary_text += (
            f"✅ {accepts} confirmed, ❌ {rejects} rejected, ❓ {uncertain} uncertain\n"
        )

        if summary:
            summary_text += f"💭 {summary}"

        return summary_text


def validate_speaker_assignments_with_llm(
    proposed_assignments: dict[str, str],
    speaker_segments: dict[str, list[dict]],
    metadata: dict | None = None,
) -> dict[str, Any]:
    """
    Convenience function for LLM speaker validation.

    Args:
        proposed_assignments: Dict mapping speaker_id to proposed name
        speaker_segments: Dict mapping speaker_id to list of speech segments
        metadata: Optional metadata (title, description, etc.)

    Returns:
        Validation result with confidence scores and recommendations
    """
    validator = LLMSpeakerValidator()
    return validator.validate_speaker_assignments(
        proposed_assignments, speaker_segments, metadata
    )
