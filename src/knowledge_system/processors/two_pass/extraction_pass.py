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
        """Load extraction pass prompt template with cache awareness."""
        prompt_path = Path(__file__).parent / "prompts" / "extraction_pass.txt"
        
        # Check if prompt cache is stale
        try:
            from knowledge_system.services.prompt_sync import get_prompt_sync_service
            
            sync_service = get_prompt_sync_service()
            cache_info = sync_service.get_prompt_cache_info('extraction_pass')
            
            if cache_info and cache_info.get('is_stale'):
                logger.warning(
                    f"⚠️ Using cached extraction prompt version '{cache_info['version_name']}' "
                    f"(synced {cache_info['age_days']} days ago). "
                    f"Sync may have failed - you may be offline or server unreachable."
                )
                # Note: Caller should check this and show GUI warning if needed
            elif cache_info:
                logger.info(
                    f"✅ Using extraction prompt version '{cache_info['version_name']}' "
                    f"(synced {cache_info['age_days']} days ago)"
                )
        except ImportError:
            logger.debug("Prompt sync service not available - using local prompt file")
        except Exception as e:
            logger.warning(f"Could not check prompt cache: {e} - continuing with local file")
        
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
        
        # Validate prompt was properly built
        logger.info(f"📝 Prompt built: {len(prompt):,} chars")
        logger.info(f"   - Contains transcript: {'{transcript}' not in prompt}")
        logger.info(f"   - Contains metadata: title={metadata.get('title', 'N/A')[:50]}")
        
        if len(prompt) < 1000:
            logger.warning(f"⚠️  Prompt suspiciously short ({len(prompt)} chars)! May be malformed.")
        
        if '{transcript}' in prompt:
            logger.error("❌ CRITICAL: Prompt contains unreplaced {transcript} placeholder!")
            logger.error(f"   Prompt preview: {prompt[:1000]}")
            raise ValueError("Prompt template variables not substituted")
        
        # Call LLM
        logger.info("Starting extraction pass...")
        try:
            response = self.llm.complete(prompt)
            logger.info(f"Extraction pass complete: received {len(response):,} char response")
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
            json_str = response.strip()
            
            # Look for JSON block - handle missing closing fence gracefully
            if "```json" in response:
                json_start = response.index("```json") + 7
                # Try to find closing fence, but if not found, use rest of response
                try:
                    json_end = response.index("```", json_start)
                    json_str = response[json_start:json_end].strip()
                except ValueError:
                    # No closing fence - likely truncated response, use everything after opening
                    logger.warning("No closing ``` found - response may be truncated, using rest of response")
                    json_str = response[json_start:].strip()
            elif "```" in response:
                json_start = response.index("```") + 3
                try:
                    json_end = response.index("```", json_start)
                    json_str = response[json_start:json_end].strip()
                except ValueError:
                    logger.warning("No closing ``` found - using rest of response")
                    json_str = response[json_start:].strip()
            
            # Handle case where response might have trailing text after JSON
            # Try to find the outermost JSON object
            if json_str.startswith('{'):
                # Find matching closing brace by counting braces
                brace_count = 0
                json_end_idx = 0
                in_string = False
                escape_next = False
                
                for i, char in enumerate(json_str):
                    if escape_next:
                        escape_next = False
                        continue
                    if char == '\\':
                        escape_next = True
                        continue
                    if char == '"' and not escape_next:
                        in_string = not in_string
                        continue
                    if not in_string:
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_end_idx = i + 1
                                break
                
                if json_end_idx > 0:
                    json_str = json_str[:json_end_idx]
            
            data = json.loads(json_str)
            
            # Log what we parsed
            logger.info(f"📊 Parsed extraction data:")
            logger.info(f"  - Claims: {len(data.get('claims', []))}")
            logger.info(f"  - Jargon: {len(data.get('jargon', []))}")
            logger.info(f"  - People: {len(data.get('people', []))}")
            logger.info(f"  - Mental Models: {len(data.get('mental_models', []))}")
            
            if not data.get('claims'):
                logger.warning("⚠️  No claims found in extraction response!")
                logger.warning(f"Response keys: {list(data.keys())}")
                logger.warning(f"Full data: {json.dumps(data, indent=2)[:1000]}")
            
            return ExtractionResult(
                claims=data.get('claims', []),
                jargon=data.get('jargon', []),
                people=data.get('people', []),
                mental_models=data.get('mental_models', []),
                metadata=data.get('metadata', {}),
            )
        
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Initial JSON parse failed: {e}")
            logger.info("Attempting to repair truncated JSON...")
            
            # Try to repair truncated JSON by finding last complete objects
            repaired_data = self._repair_truncated_json(json_str)
            
            if repaired_data and (repaired_data.get('claims') or repaired_data.get('jargon') 
                                   or repaired_data.get('people') or repaired_data.get('mental_models')):
                logger.info(f"✅ Successfully repaired truncated JSON!")
                logger.info(f"  - Claims: {len(repaired_data.get('claims', []))}")
                logger.info(f"  - Jargon: {len(repaired_data.get('jargon', []))}")
                logger.info(f"  - People: {len(repaired_data.get('people', []))}")
                logger.info(f"  - Mental Models: {len(repaired_data.get('mental_models', []))}")
                
                return ExtractionResult(
                    claims=repaired_data.get('claims', []),
                    jargon=repaired_data.get('jargon', []),
                    people=repaired_data.get('people', []),
                    mental_models=repaired_data.get('mental_models', []),
                    metadata={"repaired": True, "original_error": str(e)},
                )
            
            logger.error(f"Failed to parse extraction response: {e}")
            logger.error(f"Response preview: {response[:1000]}...")
            logger.error(f"Full response length: {len(response)} chars")
            
            # Return empty result with detailed error
            return ExtractionResult(
                metadata={
                    "error": f"Parse error: {str(e)}",
                    "response_preview": response[:500],
                    "response_length": len(response)
                }
            )
    
    def _repair_truncated_json(self, json_str: str) -> dict:
        """
        Attempt to repair truncated JSON by extracting complete objects.
        
        When LLM output is truncated mid-JSON, we try to salvage what we can
        by finding the last complete object in each array.
        """
        import re
        
        result = {
            'claims': [],
            'jargon': [],
            'people': [],
            'mental_models': [],
        }
        
        # Try to extract each array separately
        for key in result.keys():
            # Pattern to find the array: "claims": [...] or "claims":[...]
            pattern = rf'"{key}"\s*:\s*\['
            match = re.search(pattern, json_str)
            
            if match:
                array_start = match.end()
                # Find objects in this array by looking for complete {...} patterns
                # We'll parse object by object
                depth = 0
                obj_start = -1
                in_string = False
                escape_next = False
                
                for i in range(array_start, len(json_str)):
                    char = json_str[i]
                    
                    if escape_next:
                        escape_next = False
                        continue
                    if char == '\\':
                        escape_next = True
                        continue
                    if char == '"' and not escape_next:
                        in_string = not in_string
                        continue
                    
                    if not in_string:
                        if char == '{':
                            if depth == 0:
                                obj_start = i
                            depth += 1
                        elif char == '}':
                            depth -= 1
                            if depth == 0 and obj_start >= 0:
                                # Found a complete object
                                obj_str = json_str[obj_start:i+1]
                                try:
                                    obj = json.loads(obj_str)
                                    result[key].append(obj)
                                except json.JSONDecodeError:
                                    pass  # Skip malformed objects
                                obj_start = -1
                        elif char == ']':
                            break  # End of array
        
        return result
    
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

