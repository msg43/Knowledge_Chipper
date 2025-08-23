"""
Quality Evaluation Engine for LLM Outputs

Provides automated quality assessment of LLM-generated content using multi-criteria
evaluation. Supports evaluation of summaries, transcripts, and MOC extractions.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

from ..config import get_settings
from ..logger import get_logger
from ..utils.llm_providers import LLMResponse, UnifiedLLMClient
from .base import BaseProcessor, ProcessorResult

logger = get_logger(__name__)


class _LLMProviderAdapter:
    """Compatibility adapter exposing a .call() method over UnifiedLLMClient.

    Tests and legacy code expect a provider with a .call(prompt) API. This adapter
    wraps the new UnifiedLLMClient to preserve that interface.
    """

    def __init__(self, provider: str, model: str, temperature: float) -> None:
        self._client = UnifiedLLMClient(provider=provider, model=model, temperature=temperature)

    def call(self, prompt: str) -> LLMResponse:
        return self._client.generate(prompt)


def get_llm_provider(provider: str, model: str, temperature: float = 0.3) -> _LLMProviderAdapter:
    """Backward-compatible provider factory used by tests.

    Returns an object exposing a .call(prompt) method that delegates to
    UnifiedLLMClient. Tests patch this symbol directly, so keep it here.
    """

    return _LLMProviderAdapter(provider=provider, model=model, temperature=temperature)


class QualityEvaluator(BaseProcessor):
    """Evaluates the quality of LLM-generated content using automated assessment."""

    def __init__(
        self,
        evaluation_model: str = "gpt-3.5-turbo",
        evaluation_provider: str = "openai",
        temperature: float = 0.1,
        cache_evaluations: bool = True,
        **kwargs: Any,
    ) -> None:
        """Initialize the quality evaluator.

        Args:
            evaluation_model: Model to use for quality evaluation
            evaluation_provider: Provider for evaluation model
            temperature: Temperature for evaluation model (low for consistency)
            cache_evaluations: Whether to cache evaluation results
        """
        super().__init__(**kwargs)
        self.evaluation_model = evaluation_model
        self.evaluation_provider = evaluation_provider
        self.temperature = temperature
        self.cache_evaluations = cache_evaluations
        self.evaluation_cache: Dict[str, Dict[str, Any]] = {}

        # Quality criteria for different content types
        self.criteria: Dict[str, list[str]] = {
            "summary": ["accuracy", "completeness", "relevance", "clarity", "conciseness"],
            "transcript": ["accuracy", "completeness", "clarity", "coherence"],
            "moc_extraction": ["accuracy", "relevance", "completeness", "organization"],
        }

    def evaluate_summary_quality(
        self,
        summary: str,
        original_text: str,
        model_used: str,
        prompt_template: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Evaluate the quality of a summary.

        Args:
            summary: The generated summary text
            original_text: The original text that was summarized
            model_used: The model that generated the summary
            prompt_template: The prompt template used (optional)

        Returns:
            Dictionary containing quality evaluation results
        """
        cache_key = None
        if self.cache_evaluations:
            cache_key = self._create_cache_key("summary", summary, original_text)
            if cache_key in self.evaluation_cache:
                logger.debug("Using cached evaluation result")
                return self.evaluation_cache[cache_key]

        try:
            evaluation_prompt = self._get_summary_evaluation_prompt(summary, original_text)

            # Get evaluation from LLM (through compatibility function)
            provider = get_llm_provider(
                self.evaluation_provider,
                self.evaluation_model,
                temperature=self.temperature,
            )

            response = provider.call(evaluation_prompt)
            evaluation_result = self._parse_evaluation_response(response.content, "summary")

            # Add metadata
            evaluation_result.update(
                {
                    "evaluated_at": time.time(),
                    "evaluation_model": self.evaluation_model,
                    "evaluation_provider": self.evaluation_provider,
                    "content_model": model_used,
                    "prompt_template": prompt_template,
                    "input_characteristics": {
                        "original_length": len(original_text),
                        "summary_length": len(summary),
                        "compression_ratio": len(summary) / len(original_text) if original_text else 0,
                    },
                }
            )

            if self.cache_evaluations and cache_key:
                self.evaluation_cache[cache_key] = evaluation_result

            return evaluation_result

        except Exception as e:
            logger.error(f"Failed to evaluate summary quality: {e}")
            return self._get_fallback_evaluation("summary", summary, original_text)

    def evaluate_transcript_quality(
        self,
        transcript: str,
        audio_metadata: Dict[str, Any],
        model_used: str,
    ) -> Dict[str, Any]:
        """Evaluate the quality of a transcript.

        Args:
            transcript: The generated transcript text
            audio_metadata: Metadata about the audio (duration, etc.)
            model_used: The model that generated the transcript

        Returns:
            Dictionary containing quality evaluation results
        """
        cache_key = None
        if self.cache_evaluations:
            cache_key = self._create_cache_key("transcript", transcript, str(audio_metadata))
            if cache_key in self.evaluation_cache:
                logger.debug("Using cached evaluation result")
                return self.evaluation_cache[cache_key]

        try:
            evaluation_prompt = self._get_transcript_evaluation_prompt(transcript, audio_metadata)

            provider = get_llm_provider(
                self.evaluation_provider,
                self.evaluation_model,
                temperature=self.temperature,
            )

            response = provider.call(evaluation_prompt)
            evaluation_result = self._parse_evaluation_response(response.content, "transcript")

            evaluation_result.update(
                {
                    "evaluated_at": time.time(),
                    "evaluation_model": self.evaluation_model,
                    "evaluation_provider": self.evaluation_provider,
                    "content_model": model_used,
                    "input_characteristics": {
                        "transcript_length": len(transcript),
                        "audio_duration": audio_metadata.get("duration_seconds"),
                        "word_count": len(transcript.split()) if transcript else 0,
                    },
                }
            )

            if self.cache_evaluations and cache_key:
                self.evaluation_cache[cache_key] = evaluation_result

            return evaluation_result

        except Exception as e:
            logger.error(f"Failed to evaluate transcript quality: {e}")
            return self._get_fallback_evaluation("transcript", transcript, audio_metadata)

    def evaluate_moc_quality(
        self,
        moc_data: Dict[str, Any],
        source_content: str,
        model_used: str,
    ) -> Dict[str, Any]:
        """Evaluate the quality of MOC extraction.

        Args:
            moc_data: The extracted MOC data (people, tags, etc.)
            source_content: The original content that was processed
            model_used: The model that generated the MOC

        Returns:
            Dictionary containing quality evaluation results
        """
        cache_key = None
        if self.cache_evaluations:
            cache_key = self._create_cache_key("moc", str(moc_data), source_content)
            if cache_key in self.evaluation_cache:
                logger.debug("Using cached evaluation result")
                return self.evaluation_cache[cache_key]

        try:
            evaluation_prompt = self._get_moc_evaluation_prompt(moc_data, source_content)

            provider = get_llm_provider(
                self.evaluation_provider,
                self.evaluation_model,
                temperature=self.temperature,
            )

            response = provider.call(evaluation_prompt)
            evaluation_result = self._parse_evaluation_response(response.content, "moc_extraction")

            evaluation_result.update(
                {
                    "evaluated_at": time.time(),
                    "evaluation_model": self.evaluation_model,
                    "evaluation_provider": self.evaluation_provider,
                    "content_model": model_used,
                    "input_characteristics": {
                        "source_length": len(source_content),
                        "people_count": len(moc_data.get("people", [])),
                        "tags_count": len(moc_data.get("tags", [])),
                        "jargon_count": len(moc_data.get("jargon", [])),
                    },
                }
            )

            if self.cache_evaluations and cache_key:
                self.evaluation_cache[cache_key] = evaluation_result

            return evaluation_result

        except Exception as e:
            logger.error(f"Failed to evaluate MOC quality: {e}")
            return self._get_fallback_evaluation("moc_extraction", moc_data, source_content)

    def _get_summary_evaluation_prompt(self, summary: str, original_text: str) -> str:
        """Create evaluation prompt for summary quality assessment."""
        original_preview = original_text[:2000] + "..." if len(original_text) > 2000 else original_text

        return f"""Please evaluate the quality of this summary on a scale of 0.0 to 1.0 for each criterion.

ORIGINAL TEXT (first 2000 chars):
{original_preview}

GENERATED SUMMARY:
{summary}

Rate each criterion from 0.0 (poor) to 1.0 (excellent):

1. ACCURACY: How factually correct is the summary? Does it misrepresent any information?
2. COMPLETENESS: Does it capture the key points and main ideas from the original?
3. RELEVANCE: Is all content in the summary relevant to the main topic?
4. CLARITY: Is the summary well-written, clear, and easy to understand?
5. CONCISENESS: Is it appropriately concise without losing important meaning?

Respond ONLY in valid JSON format:
{{
    "overall_rating": 0.85,
    "criteria": {{
        "accuracy": 0.9,
        "completeness": 0.8,
        "relevance": 0.9,
        "clarity": 0.85,
        "conciseness": 0.8
    }},
    "reasoning": "Brief explanation of the rating (2-3 sentences max)"
}}"""

    def _get_transcript_evaluation_prompt(self, transcript: str, audio_metadata: Dict[str, Any]) -> str:
        """Create evaluation prompt for transcript quality assessment."""
        duration = audio_metadata.get("duration_seconds", 0)
        word_count = len(transcript.split()) if transcript else 0
        wpm = (word_count / (duration / 60)) if duration > 0 else 0

        transcript_preview = transcript[:2000] + "..." if len(transcript) > 2000 else transcript

        return f"""Please evaluate the quality of this transcript on a scale of 0.0 to 1.0 for each criterion.

TRANSCRIPT (first 2000 chars):
{transcript_preview}

AUDIO METADATA:
- Duration: {duration} seconds
- Word count: {word_count}
- Words per minute: {wpm:.1f}

Rate each criterion from 0.0 (poor) to 1.0 (excellent):

1. ACCURACY: Does the transcript appear to accurately represent spoken content?
2. COMPLETENESS: Does it seem complete without major gaps or missing sections?
3. CLARITY: Is the text clear and readable with proper punctuation?
4. COHERENCE: Does the transcript flow logically and make sense?

Consider the words-per-minute rate - normal speech is 120-180 WPM, very slow is 80-120 WPM.

Respond ONLY in valid JSON format:
{{
    "overall_rating": 0.85,
    "criteria": {{
        "accuracy": 0.9,
        "completeness": 0.8,
        "clarity": 0.9,
        "coherence": 0.8
    }},
    "reasoning": "Brief explanation of the rating (2-3 sentences max)"
}}"""

    def _get_moc_evaluation_prompt(self, moc_data: Dict[str, Any], source_content: str) -> str:
        """Create evaluation prompt for MOC extraction quality assessment."""
        source_preview = source_content[:1500] + "..." if len(source_content) > 1500 else source_content

        moc_summary = {
            "people": list(moc_data.get("people", {}).keys())[:10],
            "tags": list(moc_data.get("tags", {}).keys())[:15],
            "jargon": [item.get("term", "") for item in moc_data.get("jargon", [])][:10],
        }

        return f"""Please evaluate the quality of this MOC (Map of Content) extraction on a scale of 0.0 to 1.0.

SOURCE CONTENT (first 1500 chars):
{source_preview}

EXTRACTED MOC DATA:
People: {moc_summary['people']}
Tags: {moc_summary['tags']}
Jargon: {moc_summary['jargon']}

Rate each criterion from 0.0 (poor) to 1.0 (excellent):

1. ACCURACY: Are the extracted entities (people, tags, jargon) accurate and correctly identified?
2. RELEVANCE: Are all extracted items relevant to the content and properly categorized?
3. COMPLETENESS: Does the extraction capture the important entities without major omissions?
4. ORGANIZATION: Are the entities well-organized and properly structured?

Respond ONLY in valid JSON format:
{{
    "overall_rating": 0.85,
    "criteria": {{
        "accuracy": 0.9,
        "relevance": 0.8,
        "completeness": 0.9,
        "organization": 0.8
    }},
    "reasoning": "Brief explanation of the rating (2-3 sentences max)"
}}"""

    def _parse_evaluation_response(self, response: str, content_type: str) -> Dict[str, Any]:
        """Parse the LLM evaluation response into structured data."""
        try:
            response = response.strip()

            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                if end > start:
                    response = response[start:end].strip()
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                if end > start:
                    response = response[start:end].strip()

            evaluation_data = json.loads(response)

            if "overall_rating" not in evaluation_data:
                raise ValueError("Missing overall_rating in evaluation response")

            if "criteria" not in evaluation_data:
                raise ValueError("Missing criteria in evaluation response")

            overall_rating = float(evaluation_data["overall_rating"])
            if not 0.0 <= overall_rating <= 1.0:
                overall_rating = max(0.0, min(1.0, overall_rating))
                evaluation_data["overall_rating"] = overall_rating

            criteria = evaluation_data["criteria"]
            for criterion, rating in criteria.items():
                rating_float = float(rating)
                if not 0.0 <= rating_float <= 1.0:
                    rating_float = max(0.0, min(1.0, rating_float))
                    criteria[criterion] = rating_float

            return evaluation_data

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"Failed to parse evaluation response: {e}")
            logger.debug(f"Raw response: {response}")
            return self._get_fallback_evaluation(content_type, "", "")

    def _get_fallback_evaluation(self, content_type: str, content: Any, context: Any) -> Dict[str, Any]:
        """Generate a fallback evaluation when automated evaluation fails."""
        criteria_names = self.criteria.get(
            content_type, ["accuracy", "completeness", "relevance", "clarity"]
        )

        fallback_rating = 0.5

        if isinstance(content, str):
            if len(content) < 10:
                fallback_rating = 0.2
            elif len(content) > 1000:
                fallback_rating = 0.6

        criteria_scores = {criterion: fallback_rating for criterion in criteria_names}

        return {
            "overall_rating": fallback_rating,
            "criteria": criteria_scores,
            "reasoning": "Automated evaluation failed - using fallback heuristic rating",
            "is_fallback": True,
            "evaluated_at": time.time(),
            "evaluation_model": "fallback_heuristic",
            "evaluation_provider": "internal",
        }

    def _create_cache_key(self, content_type: str, content: str, context: str) -> str:
        """Create a cache key for evaluation results."""
        import hashlib

        content_hash = hashlib.md5(f"{content_type}:{content}:{context}".encode()).hexdigest()
        return f"{content_type}_{content_hash[:16]}"

    def process(self, input_data: Any, dry_run: bool = False, **kwargs: Any) -> ProcessorResult:
        """Process method for BaseProcessor compatibility."""
        return ProcessorResult(
            success=True,
            output_data={"message": "QualityEvaluator is a utility processor"},
            dry_run=dry_run,
        )

    def clear_cache(self) -> None:
        """Clear the evaluation cache."""
        self.evaluation_cache.clear()
        logger.info("Cleared quality evaluation cache")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about the evaluation cache."""
        return {"cache_size": len(self.evaluation_cache), "cache_enabled": self.cache_evaluations}


