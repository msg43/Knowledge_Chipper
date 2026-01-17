"""
Truth Critic - LLM-based logic validation (Pass 1.5b)

Selective LLM validation for high-importance entities to catch:
- Misclassifications (e.g., "Washington University" as Person)
- Logic errors that vector similarity cannot detect
- Novel hallucinations not in the feedback history

This is the "Truth" layer - catches logic errors and factual mistakes.
The Taste Filter (Pass 1.5a) handles style errors and patterns.

Key features:
- Only reviews high-importance entities (≥7.0) for efficiency
- Uses entity-local context (not transcript beginning)
- "Reasoning First" prompt strategy
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

from ...logger import get_logger
from ...core.llm_adapter import LLMAdapter

logger = get_logger(__name__)


@dataclass
class CriticVerdict:
    """Result of validating a single entity."""
    entity_id: str
    action: Literal["approve", "override", "flag"]
    reasoning: str
    original_type: str
    corrected_type: Optional[str]
    confidence: float
    warning_message: str


@dataclass
class CriticResult:
    """Result of validating all entities in an extraction."""
    verdicts: list[CriticVerdict]
    stats: dict


class TruthCritic:
    """
    LLM-based critic for logic/fact validation.
    
    Selectively reviews high-importance entities to catch errors
    that vector similarity cannot detect.
    """
    
    # Review thresholds
    REVIEW_THRESHOLD = 7.0  # Only review entities with importance >= this
    MAX_ENTITIES_PER_RUN = 10  # Limit LLM calls per processing run
    
    # Prompt template path
    PROMPT_PATH = Path(__file__).parent / "prompts" / "truth_critic.txt"
    
    def __init__(
        self,
        llm_adapter: Optional[LLMAdapter] = None,
        review_threshold: float = 7.0,
        max_entities_per_run: int = 10,
        provider: str = "ollama",
        model: str = "qwen2.5:7b-instruct"
    ):
        """
        Initialize the TruthCritic.
        
        Args:
            llm_adapter: LLM adapter for API calls. Created if not provided.
            review_threshold: Minimum importance score to trigger review.
            max_entities_per_run: Maximum entities to review per run.
            provider: LLM provider (ollama, openai, anthropic).
            model: Model name for the provider.
        """
        self.review_threshold = review_threshold
        self.max_entities_per_run = max_entities_per_run
        self.provider = provider
        self.model = model
        
        self._llm_adapter = llm_adapter
        self._prompt_template = self._load_prompt_template()
    
    @property
    def llm_adapter(self) -> LLMAdapter:
        """Lazy-load the LLM adapter."""
        if self._llm_adapter is None:
            self._llm_adapter = LLMAdapter()
        return self._llm_adapter
    
    def _load_prompt_template(self) -> str:
        """Load the prompt template from file."""
        if not self.PROMPT_PATH.exists():
            logger.warning(f"Prompt template not found at {self.PROMPT_PATH}")
            return self._get_fallback_prompt()
        
        return self.PROMPT_PATH.read_text()
    
    def _get_fallback_prompt(self) -> str:
        """Fallback prompt if template file is missing."""
        return """Validate this entity:
Type: {{entity_type}}
Text: "{{entity_text}}"
Context: {{context_snippet}}

Respond with JSON: {"reasoning": "...", "verdict": "approve|override|flag", "confidence": 0.0-1.0, "corrected_type": null, "warning_message": ""}"""
    
    async def validate(
        self,
        extraction_result: dict,
        full_transcript: str = ""
    ) -> CriticResult:
        """
        Validate entities in an extraction result.
        
        Args:
            extraction_result: Dict with claims, people, jargon, concepts lists.
            full_transcript: Full transcript text for context extraction.
            
        Returns:
            CriticResult with verdicts and statistics.
        """
        stats = {
            "total_candidates": 0,
            "reviewed": 0,
            "approved": 0,
            "overridden": 0,
            "flagged": 0,
            "skipped_low_importance": 0
        }
        
        # Select entities for review
        entities_to_review = self._select_entities_for_review(
            extraction_result,
            stats
        )
        
        verdicts = []
        
        for entity_data in entities_to_review[:self.max_entities_per_run]:
            stats["reviewed"] += 1
            
            # Extract entity-local context (CRITICAL FIX)
            entity_context = self._get_entity_context(
                entity_data,
                full_transcript
            )
            
            # Review the entity
            verdict = await self._review_entity(entity_data, entity_context)
            verdicts.append(verdict)
            
            # Update stats
            if verdict.action == "approve":
                stats["approved"] += 1
            elif verdict.action == "override":
                stats["overridden"] += 1
            elif verdict.action == "flag":
                stats["flagged"] += 1
        
        logger.info(
            f"TruthCritic: {stats['reviewed']} reviewed, "
            f"{stats['approved']} approved, {stats['overridden']} overridden, "
            f"{stats['flagged']} flagged"
        )
        
        return CriticResult(verdicts=verdicts, stats=stats)
    
    def _select_entities_for_review(
        self,
        extraction_result: dict,
        stats: dict
    ) -> list[dict]:
        """
        Select high-importance entities for review.
        
        Prioritizes:
        1. People (most common misclassification target)
        2. High-importance claims
        3. Jargon and concepts
        """
        candidates = []
        
        # Collect all entities with their type
        for entity_type, key in [
            ("person", "people"),
            ("claim", "claims"),
            ("jargon", "jargon"),
            ("concept", "concepts")
        ]:
            entities = extraction_result.get(key, [])
            for entity in entities:
                stats["total_candidates"] += 1
                
                # Get importance score
                importance = entity.get("importance_score", 0)
                
                if importance >= self.review_threshold:
                    candidates.append({
                        "entity_type": entity_type,
                        "entity": entity,
                        "importance": importance,
                        "text": self._get_entity_text(entity, entity_type)
                    })
                else:
                    stats["skipped_low_importance"] += 1
        
        # Sort by importance (highest first)
        candidates.sort(key=lambda x: x["importance"], reverse=True)
        
        return candidates
    
    def _get_entity_text(self, entity: dict, entity_type: str) -> str:
        """Extract the text content from an entity."""
        if entity_type == "claim":
            return entity.get("canonical") or entity.get("text", "")
        elif entity_type == "person":
            return entity.get("name", "")
        elif entity_type == "jargon":
            return entity.get("term", "")
        elif entity_type == "concept":
            return entity.get("name", "")
        return ""
    
    def _get_entity_context(
        self,
        entity_data: dict,
        full_transcript: str,
        context_window: int = 500
    ) -> str:
        """
        Extract ~500 characters SURROUNDING the entity, not from transcript start.
        
        CRITICAL FIX: The original plan used transcript[:500] which provides
        the first 500 characters. If an entity appears at minute 45, the intro
        text is useless. This method finds the entity in the transcript and
        extracts context around it.
        
        Strategy:
        1. Search for entity text in transcript
        2. If found, extract window around it
        3. Fallback to first 500 chars if not found
        """
        entity_text = entity_data.get("text", "")
        
        if not full_transcript or not entity_text:
            return "(no context available)"
        
        # Try to find entity in transcript (case-insensitive)
        transcript_lower = full_transcript.lower()
        entity_lower = entity_text.lower()
        
        pos = transcript_lower.find(entity_lower)
        
        if pos == -1:
            # Entity not found - try partial match (first 20 chars)
            partial = entity_lower[:20] if len(entity_lower) > 20 else entity_lower
            pos = transcript_lower.find(partial)
        
        if pos == -1:
            # Still not found - use beginning as fallback
            logger.debug(f"Entity '{entity_text[:30]}...' not found in transcript, using beginning")
            return full_transcript[:context_window] + "..."
        
        # Extract window around entity
        start = max(0, pos - context_window // 2)
        end = min(len(full_transcript), pos + len(entity_text) + context_window // 2)
        
        context = full_transcript[start:end]
        
        # Add ellipsis if truncated
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(full_transcript) else ""
        
        return f"{prefix}{context}{suffix}"
    
    async def _review_entity(
        self,
        entity_data: dict,
        context_snippet: str
    ) -> CriticVerdict:
        """
        Review a single entity using the LLM.
        
        Uses "Reasoning First" prompt strategy.
        """
        entity_type = entity_data["entity_type"]
        entity_text = entity_data["text"]
        importance = entity_data["importance"]
        
        # Build prompt from template
        prompt = self._prompt_template
        prompt = prompt.replace("{{entity_type}}", entity_type)
        prompt = prompt.replace("{{entity_text}}", entity_text)
        prompt = prompt.replace("{{importance_score}}", str(importance))
        prompt = prompt.replace("{{context_snippet}}", context_snippet)
        
        try:
            # Call LLM
            response = await self.llm_adapter.complete(
                provider=self.provider,
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a critical reviewer validating extracted entities. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Low temperature for consistent validation
                max_tokens=500
            )
            
            # Parse response
            content = response.get("content", "")
            verdict_data = self._parse_llm_response(content)
            
            return CriticVerdict(
                entity_id=f"{entity_type}_{hash(entity_text) % 10000}",
                action=verdict_data.get("verdict", "approve"),
                reasoning=verdict_data.get("reasoning", ""),
                original_type=entity_type,
                corrected_type=verdict_data.get("corrected_type"),
                confidence=verdict_data.get("confidence", 0.5),
                warning_message=verdict_data.get("warning_message", "")
            )
            
        except Exception as e:
            logger.error(f"LLM review failed for '{entity_text[:30]}...': {e}")
            # On error, approve by default (fail-safe)
            return CriticVerdict(
                entity_id=f"{entity_type}_{hash(entity_text) % 10000}",
                action="approve",
                reasoning=f"LLM review failed: {e}",
                original_type=entity_type,
                corrected_type=None,
                confidence=0.0,
                warning_message="Review failed, approved by default"
            )
    
    def _parse_llm_response(self, content: str) -> dict:
        """Parse the LLM response JSON."""
        # Try to extract JSON from response
        # Handle cases where LLM wraps in markdown code blocks
        json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', content, re.DOTALL)
        if json_match:
            content = json_match.group(1)
        
        # Also try to find raw JSON object
        json_obj_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
        if json_obj_match:
            content = json_obj_match.group(0)
        
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse LLM response as JSON: {content[:100]}...")
            return {
                "verdict": "approve",
                "reasoning": "Failed to parse response",
                "confidence": 0.0
            }
