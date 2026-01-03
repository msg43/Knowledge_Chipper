"""
Extraction Pass - Two-Pass System

Pass 1 of the two-pass architecture: Extract and score ALL entities from complete document.
Processes entire transcript in one LLM call, extracting claims, jargon, people, and mental models
with full scoring and speaker inference.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Result from extraction pass."""
    claims: list[dict] = field(default_factory=list)
    jargon: list[dict] = field(default_factory=list)
    people: list[dict] = field(default_factory=list)
    mental_models: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    raw_response: str = ""
    
    @property
    def total_claims(self) -> int:
        return len(self.claims)
    
    @property
    def high_importance_claims(self) -> list[dict]:
        """Claims with importance >= 7.0"""
        return [c for c in self.claims if c.get('importance', 0) >= 7.0]
    
    @property
    def flagged_claims(self) -> list[dict]:
        """Claims flagged for speaker review."""
        return [c for c in self.claims if c.get('flag_for_review', False)]
    
    @property
    def avg_importance(self) -> float:
        """Average importance score across all claims."""
        if not self.claims:
            return 0.0
        return sum(c.get('importance', 0) for c in self.claims) / len(self.claims)


class ExtractionPass:
    """
    Extraction Pass implementation for two-pass system.
    
    Processes entire transcript in one LLM call to extract:
    - Claims with 6-dimension scoring and importance
    - Jargon terms with definitions
    - People mentioned with context
    - Mental models with implications
    - Speaker inference with confidence scoring
    """
    
    def __init__(self, llm_adapter):
        """
        Initialize extraction pass.
        
        Args:
            llm_adapter: LLM adapter instance (supports complete() method)
        """
        self.llm = llm_adapter
        self.prompt_template = self._load_prompt_template()
    
    def _load_prompt_template(self) -> str:
        """Load extraction pass prompt template."""
        prompt_path = Path(__file__).parent / "prompts" / "extraction_pass.txt"
        try:
            return prompt_path.read_text()
        except FileNotFoundError:
            logger.error(f"Extraction prompt not found at {prompt_path}")
            raise
    
    def extract(
        self,
        transcript: str,
        metadata: dict[str, Any],
    ) -> ExtractionResult:
        """
        Run extraction pass on complete transcript.
        
        Args:
            transcript: Complete transcript text (with timestamps if available)
            metadata: Video metadata (title, channel, description, etc.)
        
        Returns:
            ExtractionResult with all extracted entities
        """
        # Token sanity check
        estimated_tokens = len(transcript) // 4
        if estimated_tokens > 100000:
            raise ValueError(
                f"Transcript too large: ~{estimated_tokens} tokens. "
                f"Maximum is 100,000 tokens."
            )
        elif estimated_tokens > 50000:
            logger.warning(
                f"Large transcript: ~{estimated_tokens} tokens. "
                f"Processing may be slow."
            )
        
        # Build prompt
        prompt = self._build_prompt(transcript, metadata)
        
        # Call LLM
        logger.info("Starting extraction pass...")
        try:
            response = self.llm.complete(prompt)
            logger.info("Extraction pass complete")
        except Exception as e:
            logger.error(f"Extraction pass failed: {e}")
            raise
        
        # Parse response
        result = self._parse_response(response)
        result.raw_response = response
        
        # Validate and repair
        result = self._validate_and_repair(result)
        
        # Log statistics
        logger.info(
            f"Extracted: {result.total_claims} claims "
            f"({len(result.high_importance_claims)} high-importance), "
            f"{len(result.jargon)} jargon terms, "
            f"{len(result.people)} people, "
            f"{len(result.mental_models)} mental models"
        )
        
        if result.flagged_claims:
            logger.info(
                f"{len(result.flagged_claims)} claims flagged for speaker review"
            )
        
        return result
    
    def _build_prompt(self, transcript: str, metadata: dict) -> str:
        """Build extraction prompt from template."""
        # Format chapters if available
        chapters = metadata.get('chapters', [])
        if chapters:
            chapters_text = "\n".join([
                f"[{ch.get('start_time', '00:00')}] {ch.get('title', 'Untitled')}"
                for ch in chapters
            ])
        else:
            chapters_text = "No chapters available"
        
        # Format tags
        tags = metadata.get('tags', [])
        if tags:
            tags_text = ", ".join(tags[:10])  # Limit to 10 tags
        else:
            tags_text = "No tags available"
        
        # Build base prompt
        prompt = self.prompt_template.format(
            title=metadata.get('title', 'Unknown Title'),
            channel=metadata.get('channel', metadata.get('uploader', 'Unknown Channel')),
            duration=metadata.get('duration', 'Unknown'),
            upload_date=metadata.get('upload_date', 'Unknown'),
            description=metadata.get('description', 'No description')[:500],
            tags=tags_text,
            chapters=chapters_text,
            transcript=transcript,
        )
        
        # Inject synced refinements from GetReceipts.org
        prompt = self._inject_refinements(prompt)
        
        return prompt
    
    def _inject_refinements(self, prompt: str) -> str:
        """
        Inject synced refinements from GetReceipts.org into the prompt.
        
        Refinements are bad_example XML patterns that teach the LLM to avoid
        previously-identified extraction mistakes (e.g., extracting "US President" 
        as a person instead of "Joe Biden").
        
        Args:
            prompt: The base extraction prompt
            
        Returns:
            Prompt with refinements injected (if available)
        """
        try:
            from knowledge_system.services.prompt_sync import get_prompt_sync_service
            
            sync_service = get_prompt_sync_service()
            refinements = sync_service.get_all_refinements()
            
            # Check if we have any refinements
            has_refinements = any(refinements.values())
            
            if not has_refinements:
                logger.debug("No refinements available - using base prompt")
                return prompt
            
            # Build refinements section
            refinements_section = "\n\n# 🔄 LEARNED PATTERNS - AVOID THESE MISTAKES\n\n"
            refinements_section += "## Patterns to Avoid (From Previous Web Corrections)\n\n"
            refinements_section += "The following patterns were identified as mistakes in previous extractions.\n"
            refinements_section += "Learn from these examples and avoid making similar errors.\n\n"
            
            refinement_count = 0
            
            if refinements['person']:
                refinements_section += "### ❌ People Extraction Mistakes:\n\n"
                refinements_section += refinements['person'] + "\n\n"
                refinement_count += 1
            
            if refinements['jargon']:
                refinements_section += "### ❌ Jargon Extraction Mistakes:\n\n"
                refinements_section += refinements['jargon'] + "\n\n"
                refinement_count += 1
            
            if refinements['concept']:
                refinements_section += "### ❌ Concept Extraction Mistakes:\n\n"
                refinements_section += refinements['concept'] + "\n\n"
                refinement_count += 1
            
            # Insert before EXTRACTION INSTRUCTIONS section
            if "# EXTRACTION INSTRUCTIONS" in prompt:
                prompt = prompt.replace(
                    "# EXTRACTION INSTRUCTIONS",
                    refinements_section + "# EXTRACTION INSTRUCTIONS"
                )
                logger.info(f"✅ Injected {refinement_count} refinement type(s) into extraction prompt")
            else:
                # Fallback: append before OUTPUT FORMAT
                if "# OUTPUT FORMAT" in prompt:
                    prompt = prompt.replace(
                        "# OUTPUT FORMAT",
                        refinements_section + "# OUTPUT FORMAT"
                    )
                    logger.info(f"✅ Injected {refinement_count} refinement type(s) into extraction prompt (fallback position)")
                else:
                    logger.warning("Could not find insertion point for refinements")
        
        except ImportError:
            logger.debug("Prompt sync service not available - using base prompt")
        except Exception as e:
            logger.warning(f"Could not load refinements: {e} - continuing with base prompt")
        
        return prompt
    
    def _parse_response(self, response: str) -> ExtractionResult:
        """Parse LLM response into ExtractionResult."""
        # Try to extract JSON from response
        try:
            # Look for JSON block
            if "```json" in response:
                json_start = response.index("```json") + 7
                json_end = response.index("```", json_start)
                json_str = response[json_start:json_end].strip()
            elif "```" in response:
                json_start = response.index("```") + 3
                json_end = response.index("```", json_start)
                json_str = response[json_start:json_end].strip()
            else:
                # Assume entire response is JSON
                json_str = response.strip()
            
            data = json.loads(json_str)
            
            return ExtractionResult(
                claims=data.get('claims', []),
                jargon=data.get('jargon', []),
                people=data.get('people', []),
                mental_models=data.get('mental_models', []),
                metadata=data.get('metadata', {}),
            )
        
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse extraction response: {e}")
            logger.debug(f"Response: {response[:500]}...")
            
            # Return empty result
            return ExtractionResult(
                metadata={"error": f"Parse error: {str(e)}"}
            )
    
    def _validate_and_repair(self, result: ExtractionResult) -> ExtractionResult:
        """Validate and repair extraction result."""
        # Validate claims
        for i, claim in enumerate(result.claims):
            # Ensure required fields
            if 'claim_text' not in claim:
                claim['claim_text'] = claim.get('canonical', claim.get('text', f'Claim {i+1}'))
            
            if 'speaker' not in claim:
                claim['speaker'] = 'Unknown Speaker'
                claim['speaker_confidence'] = 0
                claim['speaker_rationale'] = 'No speaker information provided'
                claim['flag_for_review'] = True
            
            if 'speaker_confidence' not in claim:
                claim['speaker_confidence'] = 5  # Default moderate confidence
            
            if 'flag_for_review' not in claim:
                claim['flag_for_review'] = claim.get('speaker_confidence', 5) < 7
            
            if 'timestamp' not in claim:
                claim['timestamp'] = '00:00'
            
            if 'evidence_quote' not in claim:
                claim['evidence_quote'] = claim.get('evidence', 'No evidence quote provided')
            
            if 'claim_type' not in claim:
                claim['claim_type'] = 'factual'
            
            if 'dimensions' not in claim:
                claim['dimensions'] = {
                    'epistemic': 5,
                    'actionability': 5,
                    'novelty': 5,
                    'verifiability': 5,
                    'understandability': 5,
                    'temporal_stability': 5,
                }
            
            if 'importance' not in claim:
                # Calculate from dimensions if not provided
                dims = claim['dimensions']
                claim['importance'] = sum(dims.values()) / len(dims)
        
        # Validate jargon
        for term in result.jargon:
            if 'term' not in term:
                term['term'] = 'Unknown term'
            if 'definition' not in term:
                term['definition'] = 'No definition provided'
            if 'domain' not in term:
                term['domain'] = 'Unknown'
            if 'first_mention_ts' not in term:
                term['first_mention_ts'] = '00:00'
        
        # Validate people
        for person in result.people:
            if 'name' not in person:
                person['name'] = 'Unknown person'
            if 'role' not in person:
                person['role'] = 'Unknown role'
            if 'context' not in person:
                person['context'] = 'No context provided'
            if 'first_mention_ts' not in person:
                person['first_mention_ts'] = '00:00'
        
        # Validate mental models
        for model in result.mental_models:
            if 'name' not in model:
                model['name'] = 'Unknown model'
            if 'description' not in model:
                model['description'] = 'No description provided'
            if 'implications' not in model:
                model['implications'] = 'No implications provided'
            if 'first_mention_ts' not in model:
                model['first_mention_ts'] = '00:00'
        
        # Update metadata
        result.metadata['total_claims_extracted'] = len(result.claims)
        result.metadata['avg_importance'] = result.avg_importance
        result.metadata['high_importance_count'] = len(result.high_importance_claims)
        result.metadata['flagged_count'] = len(result.flagged_claims)
        
        return result

