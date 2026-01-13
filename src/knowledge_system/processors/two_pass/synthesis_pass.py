"""
Synthesis Pass - Two-Pass System

Pass 2 of the two-pass architecture: Generate world-class long summary from extracted entities.
Synthesizes high-importance claims, jargon, people, and mental models into sophisticated narrative.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class SynthesisResult:
    """Result from synthesis pass."""
    long_summary: str
    key_themes: list[str]
    synthesis_quality: dict[str, Any]
    raw_response: str = ""


class SynthesisPass:
    """
    Synthesis Pass implementation for two-pass system.
    
    Generates world-class long summary by integrating:
    - High-importance claims (importance >= 7.0)
    - All jargon terms with definitions
    - All people mentioned with context
    - All mental models with implications
    - YouTube AI summary (if available)
    """
    
    def __init__(self, llm_adapter):
        """
        Initialize synthesis pass.
        
        Args:
            llm_adapter: LLM adapter instance (supports complete() method)
        """
        self.llm = llm_adapter
        self.prompt_template = self._load_prompt_template()
    
    def _load_prompt_template(self) -> str:
        """Load synthesis pass prompt template with cache awareness."""
        prompt_path = Path(__file__).parent / "prompts" / "synthesis_pass.txt"
        
        # Check if prompt cache is stale
        try:
            from knowledge_system.services.prompt_sync import get_prompt_sync_service
            
            sync_service = get_prompt_sync_service()
            cache_info = sync_service.get_prompt_cache_info('synthesis_pass')
            
            if cache_info and cache_info.get('is_stale'):
                logger.warning(
                    f"⚠️ Using cached synthesis prompt version '{cache_info['version_name']}' "
                    f"(synced {cache_info['age_days']} days ago). "
                    f"Sync may have failed - you may be offline or server unreachable."
                )
                # Note: Caller should check this and show GUI warning if needed
            elif cache_info:
                logger.info(
                    f"✅ Using synthesis prompt version '{cache_info['version_name']}' "
                    f"(synced {cache_info['age_days']} days ago)"
                )
        except ImportError:
            logger.debug("Prompt sync service not available - using local prompt file")
        except Exception as e:
            logger.warning(f"Could not check prompt cache: {e} - continuing with local file")
        
        try:
            return prompt_path.read_text()
        except FileNotFoundError:
            logger.error(f"Synthesis prompt not found at {prompt_path}")
            raise
    
    def synthesize(
        self,
        extraction_result,  # ExtractionResult from extraction pass
        metadata: dict[str, Any],
        youtube_ai_summary: Optional[str] = None,
        importance_threshold: float = 7.0,
    ) -> SynthesisResult:
        """
        Run synthesis pass to generate long summary.
        
        Args:
            extraction_result: Result from extraction pass
            metadata: Video metadata
            youtube_ai_summary: YouTube AI-generated summary (optional)
            importance_threshold: Minimum importance for claims to include
        
        Returns:
            SynthesisResult with long summary and metadata
        """
        # Filter high-importance claims
        top_claims = [
            c for c in extraction_result.claims
            if c.get('importance', 0) >= importance_threshold
        ]
        
        if not top_claims:
            logger.warning(
                f"No claims above importance threshold {importance_threshold}. "
                f"Using all claims."
            )
            top_claims = extraction_result.claims
        
        logger.info(
            f"Synthesizing summary from {len(top_claims)} high-importance claims "
            f"(threshold: {importance_threshold})"
        )
        
        # Build prompt
        prompt = self._build_prompt(
            top_claims=top_claims,
            jargon=extraction_result.jargon,
            people=extraction_result.people,
            mental_models=extraction_result.mental_models,
            extraction_metadata=extraction_result.metadata,
            video_metadata=metadata,
            youtube_ai_summary=youtube_ai_summary,
        )
        
        # Call LLM
        logger.info("Starting synthesis pass...")
        try:
            response = self.llm.complete(prompt)
            logger.info("Synthesis pass complete")
        except Exception as e:
            logger.error(f"Synthesis pass failed: {e}")
            raise
        
        # Parse response
        result = self._parse_response(response)
        result.raw_response = response
        
        logger.info(
            f"Generated summary with {len(result.key_themes)} key themes"
        )
        
        return result
    
    def _calculate_synthesis_length(
        self,
        top_claims: list[dict],
        video_metadata: dict,
    ) -> str:
        """
        Calculate recommended synthesis length based on content density.
        
        Args:
            top_claims: List of high-importance claims
            video_metadata: Video metadata including duration
        
        Returns:
            Length guidance string (e.g., "5-7 paragraphs" or "1-2 pages")
        """
        # Get duration in seconds
        duration = video_metadata.get('duration', 0)
        if isinstance(duration, str):
            # Parse duration string if needed (e.g., "1:23:45" -> seconds)
            try:
                parts = duration.split(':')
                if len(parts) == 3:  # HH:MM:SS
                    duration = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                elif len(parts) == 2:  # MM:SS
                    duration = int(parts[0]) * 60 + int(parts[1])
                else:
                    duration = int(duration)
            except (ValueError, AttributeError):
                duration = 0
        
        # Count claims
        claim_count = len(top_claims)
        
        # Calculate claim density (claims per minute)
        duration_minutes = duration / 60 if duration > 0 else 1
        claim_density = claim_count / duration_minutes if duration_minutes > 0 else claim_count
        
        # Determine synthesis length based on content complexity
        # Short content (< 15 min) or low density (< 1 claim/min) -> 3-5 paragraphs
        if duration_minutes < 15 or claim_count < 10:
            return "3-5 paragraphs"
        
        # Medium content (15-45 min) or medium density -> 5-8 paragraphs
        elif duration_minutes < 45 or claim_count < 30:
            return "5-8 paragraphs"
        
        # Long content (45-90 min) or high density -> 8-12 paragraphs (1-1.5 pages)
        elif duration_minutes < 90 or claim_count < 50:
            return "8-12 paragraphs (approximately 1-1.5 pages)"
        
        # Very long content (90+ min) or very high density -> 12-20 paragraphs (1.5-2 pages)
        else:
            return "12-20 paragraphs (approximately 1.5-2 pages)"
    
    def _build_prompt(
        self,
        top_claims: list[dict],
        jargon: list[dict],
        people: list[dict],
        mental_models: list[dict],
        extraction_metadata: dict,
        video_metadata: dict,
        youtube_ai_summary: Optional[str],
    ) -> str:
        """Build synthesis prompt from template."""
        # Calculate recommended synthesis length
        synthesis_length = self._calculate_synthesis_length(top_claims, video_metadata)
        
        # Format top claims
        claims_text = self._format_claims(top_claims)
        
        # Format jargon
        jargon_text = self._format_jargon(jargon)
        
        # Format people
        people_text = self._format_people(people)
        
        # Format mental models
        models_text = self._format_mental_models(mental_models)
        
        # Format extraction stats
        stats_text = self._format_extraction_stats(extraction_metadata, top_claims)
        
        # Format YouTube AI summary
        yt_summary = youtube_ai_summary or "Not available"
        
        # Build prompt
        prompt = self.prompt_template.format(
            title=video_metadata.get('title', 'Unknown Title'),
            channel=video_metadata.get('channel', video_metadata.get('uploader', 'Unknown Channel')),
            duration=video_metadata.get('duration', 'Unknown'),
            description=video_metadata.get('description', 'No description')[:500],
            synthesis_length=synthesis_length,
            top_claims=claims_text,
            jargon=jargon_text,
            people=people_text,
            mental_models=models_text,
            extraction_stats=stats_text,
            youtube_ai_summary=yt_summary,
        )
        
        return prompt
    
    def _format_claims(self, claims: list[dict]) -> str:
        """Format claims for prompt."""
        if not claims:
            return "No high-importance claims extracted."
        
        lines = []
        for i, claim in enumerate(claims, 1):
            importance = claim.get('importance', 0)
            text = claim.get('claim_text', claim.get('canonical', 'Unknown claim'))
            evidence = claim.get('evidence_quote', '')[:200]
            speaker = claim.get('speaker', 'Unknown')
            timestamp = claim.get('timestamp', '00:00')
            
            lines.append(
                f"{i}. [Importance: {importance:.1f}] {text}\n"
                f"   Speaker: {speaker} [{timestamp}]\n"
                f"   Evidence: {evidence}"
            )
        
        return "\n\n".join(lines)
    
    def _format_jargon(self, jargon: list[dict]) -> str:
        """Format jargon terms for prompt."""
        if not jargon:
            return "No jargon terms identified."
        
        lines = []
        for term in jargon[:20]:  # Limit to 20 terms
            name = term.get('term', 'Unknown term')
            definition = term.get('definition', 'No definition')
            domain = term.get('domain', 'Unknown')
            
            lines.append(f"- **{name}** ({domain}): {definition}")
        
        return "\n".join(lines)
    
    def _format_people(self, people: list[dict]) -> str:
        """Format people for prompt."""
        if not people:
            return "No people mentioned."
        
        lines = []
        for person in people[:20]:  # Limit to 20 people
            name = person.get('name', 'Unknown person')
            role = person.get('role', 'Unknown role')
            context = person.get('context', 'No context')
            
            lines.append(f"- **{name}** ({role}): {context}")
        
        return "\n".join(lines)
    
    def _format_mental_models(self, models: list[dict]) -> str:
        """Format mental models for prompt."""
        if not models:
            return "No mental models identified."
        
        lines = []
        for model in models[:15]:  # Limit to 15 models
            name = model.get('name', 'Unknown model')
            description = model.get('description', 'No description')
            implications = model.get('implications', 'No implications')
            
            lines.append(
                f"- **{name}**: {description}\n"
                f"  Implications: {implications}"
            )
        
        return "\n\n".join(lines)
    
    def _format_extraction_stats(
        self,
        extraction_metadata: dict,
        top_claims: list[dict],
    ) -> str:
        """Format extraction statistics for prompt."""
        total_claims = extraction_metadata.get('total_claims_extracted', 0)
        avg_importance = extraction_metadata.get('avg_importance', 0.0)
        high_count = len(top_claims)
        
        # Calculate score distribution
        if top_claims:
            scores = [c.get('importance', 0) for c in top_claims]
            score_9_10 = sum(1 for s in scores if s >= 9)
            score_8_9 = sum(1 for s in scores if 8 <= s < 9)
            score_7_8 = sum(1 for s in scores if 7 <= s < 8)
        else:
            score_9_10 = score_8_9 = score_7_8 = 0
        
        return f"""
- Total claims extracted: {total_claims}
- High-importance claims (≥7.0): {high_count}
- Average importance score: {avg_importance:.2f}
- Score distribution:
  * 9.0-10.0: {score_9_10} claims
  * 8.0-8.9: {score_8_9} claims
  * 7.0-7.9: {score_7_8} claims
"""
    
    def _parse_response(self, response: str) -> SynthesisResult:
        """Parse LLM response into SynthesisResult."""
        # Try to extract JSON from response
        try:
            json_str = response.strip()
            
            # Look for JSON block - handle missing closing fence gracefully
            if "```json" in response:
                json_start = response.index("```json") + 7
                try:
                    json_end = response.index("```", json_start)
                    json_str = response[json_start:json_end].strip()
                except ValueError:
                    # No closing fence - likely truncated, use rest of response
                    logger.warning("No closing ``` found in synthesis - using rest of response")
                    json_str = response[json_start:].strip()
            elif "```" in response:
                json_start = response.index("```") + 3
                try:
                    json_end = response.index("```", json_start)
                    json_str = response[json_start:json_end].strip()
                except ValueError:
                    logger.warning("No closing ``` found - using rest of response")
                    json_str = response[json_start:].strip()
            
            # Handle trailing text after JSON by finding matching closing brace
            if json_str.startswith('{'):
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
            
            return SynthesisResult(
                long_summary=data.get('long_summary', ''),
                key_themes=data.get('key_themes', []),
                synthesis_quality=data.get('synthesis_quality', {}),
            )
        
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse synthesis response: {e}")
            logger.debug(f"Response: {response[:500]}...")
            
            # If JSON parsing fails, try to extract summary as plain text
            # Look for paragraph breaks
            if '\n\n' in response:
                # Assume response is the summary itself
                return SynthesisResult(
                    long_summary=response.strip(),
                    key_themes=[],
                    synthesis_quality={"error": f"Parse error: {str(e)}"},
                )
            else:
                return SynthesisResult(
                    long_summary=f"Synthesis failed: {str(e)}",
                    key_themes=[],
                    synthesis_quality={"error": f"Parse error: {str(e)}"},
                )

