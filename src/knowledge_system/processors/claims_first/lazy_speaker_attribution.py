"""
Lazy Speaker Attribution Module

Provides targeted speaker attribution for high-value claims only.
Uses LLM with claim content and local context as attribution signals.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from knowledge_system.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SpeakerAttribution:
    """
    Result from speaker attribution.
    
    Contains the identified speaker and confidence score.
    """
    speaker_name: str
    confidence: float  # 0.0-1.0
    reasoning: list[str] = field(default_factory=list)
    is_host: bool = False
    claim_id: Optional[str] = None
    
    @property
    def is_confident(self) -> bool:
        """Whether attribution is confident enough to display."""
        return self.confidence >= 0.7
    
    @property
    def is_unknown(self) -> bool:
        """Whether speaker is unknown."""
        return self.speaker_name.lower() in ["unknown", "unidentified", "speaker"]


class LazySpeakerAttributor:
    """
    Targeted speaker attribution for high-value claims.
    
    Only attributes speakers to claims with importance >= threshold.
    Uses claim content + local context + metadata as attribution signals.
    
    Attribution Signals:
    1. First-person language ("my research", "I think")
    2. Expertise matching (topic vs. guest credentials)
    3. Turn-taking patterns (question → claim → response)
    4. Metadata (guest names from description)
    5. Self-introductions nearby in transcript
    
    Usage:
        attributor = LazySpeakerAttributor(llm_client)
        result = attributor.attribute_speaker(
            claim={"canonical": "...", "timestamp_start": 125.5},
            transcript="...",
            metadata={"title": "...", "participants": [...]}
        )
    """
    
    def __init__(
        self,
        llm_provider: str = "gemini",
        model: str = "gemini-2.0-flash",
        context_window_seconds: int = 60,
        confidence_threshold: float = 0.7,
    ):
        """
        Initialize speaker attributor.
        
        Args:
            llm_provider: LLM provider (gemini, anthropic, openai, ollama)
            model: Model name
            context_window_seconds: Context window around claim for attribution
            confidence_threshold: Minimum confidence to accept attribution
        """
        self.llm_provider = llm_provider
        self.model = model
        self.context_window_seconds = context_window_seconds
        self.confidence_threshold = confidence_threshold
        
        # Lazy load LLM adapter
        self._llm_adapter = None
    
    def _get_llm_adapter(self):
        """Lazy-load LLM adapter."""
        if self._llm_adapter is None:
            from knowledge_system.core.llm_adapter import LLMAdapter
            self._llm_adapter = LLMAdapter(
                provider=self.llm_provider,
                model=self.model,
            )
        return self._llm_adapter
    
    def attribute_speaker(
        self,
        claim: dict,
        transcript: str,
        metadata: dict,
        context_window_seconds: Optional[int] = None,
    ) -> SpeakerAttribution:
        """
        Attribute speaker to a single claim.
        
        Args:
            claim: Claim dict with canonical text, timestamp, evidence
            transcript: Full transcript text
            metadata: Episode metadata (title, description, participants)
            context_window_seconds: Override default context window
        
        Returns:
            SpeakerAttribution with speaker name and confidence
        """
        context_window = context_window_seconds or self.context_window_seconds
        
        # Extract context window around claim
        timestamp = claim.get('timestamp_start') or claim.get('timestamp', 0)
        context = self._extract_context_window(
            transcript, 
            timestamp, 
            window_seconds=context_window
        )
        
        # Build prompt
        prompt = self._build_attribution_prompt(claim, context, metadata)
        
        # Call LLM
        try:
            llm = self._get_llm_adapter()
            response = llm.complete(prompt, temperature=0.1)
            
            # Parse response
            return self._parse_attribution_response(response, claim)
            
        except Exception as e:
            logger.error(f"Speaker attribution failed: {e}")
            return SpeakerAttribution(
                speaker_name="Unknown",
                confidence=0.0,
                reasoning=[f"Attribution failed: {str(e)}"],
                claim_id=claim.get('id'),
            )
    
    def _extract_context_window(
        self,
        transcript: str,
        timestamp: float,
        window_seconds: int = 60,
    ) -> str:
        """
        Extract context window around a timestamp.
        
        Since we have text but not word-level timing, we estimate position
        based on transcript length and timestamp.
        """
        if not transcript:
            return ""
        
        # Estimate characters per second (typical speech: 2-3 words/sec, ~15 chars/word)
        chars_per_second = 25  # Conservative estimate
        
        # Calculate approximate character positions
        center_char = int(timestamp * chars_per_second)
        window_chars = int(window_seconds * chars_per_second)
        
        start_char = max(0, center_char - window_chars // 2)
        end_char = min(len(transcript), center_char + window_chars // 2)
        
        # Expand to word boundaries
        while start_char > 0 and transcript[start_char] != ' ':
            start_char -= 1
        while end_char < len(transcript) and transcript[end_char] != ' ':
            end_char += 1
        
        context = transcript[start_char:end_char].strip()
        
        # If context is too short, return more
        if len(context) < 200 and len(transcript) > 200:
            # Just return a reasonable chunk from the transcript
            return transcript[:min(2000, len(transcript))]
        
        return context
    
    def _build_attribution_prompt(
        self,
        claim: dict,
        context: str,
        metadata: dict,
    ) -> str:
        """Build prompt for speaker attribution."""
        
        canonical = claim.get('canonical') or claim.get('claim_text', '')
        evidence = claim.get('evidence') or claim.get('evidence_quote', '')
        timestamp = claim.get('timestamp_start') or claim.get('timestamp', 0)
        
        # Extract participants from metadata
        participants = metadata.get('participants', [])
        if not participants:
            # Try to extract from description
            description = metadata.get('description', '')
            participants = self._extract_participants_from_description(description)
        
        participants_str = ', '.join(participants) if participants else 'Unknown'
        
        prompt = f"""Identify who made this claim based on the context and metadata.

CLAIM: "{canonical}"

EVIDENCE QUOTE: "{evidence}"

TIMESTAMP: {timestamp:.1f} seconds into the episode

CONTEXT (60-second window around claim):
\"\"\"
{context}
\"\"\"

METADATA:
- Title: {metadata.get('title', 'Unknown')}
- Channel: {metadata.get('channel_name', 'Unknown')}
- Participants: {participants_str}
- Description excerpt: {metadata.get('description', '')[:500]}

ANALYSIS GUIDELINES:
1. Check for first-person language ("I think", "my research", "in my view")
2. Look for turn-taking patterns (question → claim → response indicates guest)
3. Match topic to participant expertise (technical claims from expert guest)
4. Check for self-introductions nearby ("I'm [name] and...")
5. Consider conversational flow and who typically explains vs asks questions
6. Hosts typically ask questions and guide discussion; guests provide expertise

IMPORTANT:
- If uncertain, return "Unknown" with low confidence rather than guessing
- Don't assume the host made a claim just because they're speaking more
- Technical/expert claims are usually from guests unless host is the expert

Return your response as JSON:
{{
    "speaker_name": "Name of the speaker",
    "confidence": 0.85,
    "is_host": false,
    "reasoning": [
        "Reason 1 for this attribution",
        "Reason 2 for this attribution"
    ]
}}

Respond with ONLY the JSON, no other text."""

        return prompt
    
    def _extract_participants_from_description(self, description: str) -> list[str]:
        """Extract participant names from episode description."""
        participants = []
        
        # Common patterns for guest names
        patterns = [
            r"(?:guest|featuring|with|interview(?:ing)?|host(?:ed by)?)[:\s]+([A-Z][a-z]+ [A-Z][a-z]+)",
            r"([A-Z][a-z]+ [A-Z][a-z]+)(?:\s*,\s*(?:PhD|MD|CEO|Professor|Dr\.|author))",
            r"(?:Dr\.|Professor)\s+([A-Z][a-z]+ [A-Z][a-z]+)",
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, description, re.IGNORECASE)
            participants.extend(matches)
        
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for p in participants:
            if p.lower() not in seen:
                seen.add(p.lower())
                unique.append(p)
        
        return unique[:5]  # Limit to 5 participants
    
    def _parse_attribution_response(
        self,
        response: str,
        claim: dict,
    ) -> SpeakerAttribution:
        """Parse LLM response into SpeakerAttribution."""
        
        # Try to extract JSON from response
        try:
            # Find JSON in response
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                # Try parsing entire response as JSON
                data = json.loads(response)
            
            return SpeakerAttribution(
                speaker_name=data.get('speaker_name', 'Unknown'),
                confidence=float(data.get('confidence', 0.5)),
                reasoning=data.get('reasoning', []),
                is_host=data.get('is_host', False),
                claim_id=claim.get('id'),
            )
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse attribution response: {e}")
            
            # Try to extract speaker name from text
            name_match = re.search(r'"speaker_name":\s*"([^"]+)"', response)
            if name_match:
                return SpeakerAttribution(
                    speaker_name=name_match.group(1),
                    confidence=0.5,
                    reasoning=["Extracted from malformed JSON response"],
                    claim_id=claim.get('id'),
                )
            
            return SpeakerAttribution(
                speaker_name="Unknown",
                confidence=0.0,
                reasoning=["Failed to parse LLM response"],
                claim_id=claim.get('id'),
            )
    
    def attribute_speakers_batch(
        self,
        claims: list[dict],
        transcript: str,
        metadata: dict,
        min_importance: int = 7,
    ) -> list[tuple[dict, Optional[SpeakerAttribution]]]:
        """
        Attribute speakers to multiple claims, filtering by importance.
        
        Args:
            claims: List of claim dicts
            transcript: Full transcript text
            metadata: Episode metadata
            min_importance: Minimum importance score for attribution
        
        Returns:
            List of (claim, SpeakerAttribution or None) tuples
        """
        results = []
        
        for claim in claims:
            importance = claim.get('importance', 0)
            
            if importance >= min_importance:
                attribution = self.attribute_speaker(claim, transcript, metadata)
                results.append((claim, attribution))
            else:
                # Skip low-importance claims
                results.append((claim, None))
                logger.debug(
                    f"Skipping speaker attribution for claim with importance {importance} "
                    f"(< {min_importance})"
                )
        
        return results
    
    def get_attribution_stats(
        self,
        attributions: list[tuple[dict, Optional[SpeakerAttribution]]],
    ) -> dict[str, Any]:
        """
        Calculate statistics about attributions.
        
        Returns dict with counts and averages.
        """
        total = len(attributions)
        attributed = sum(1 for _, a in attributions if a is not None)
        skipped = total - attributed
        
        confident = sum(
            1 for _, a in attributions 
            if a is not None and a.is_confident
        )
        
        unknown = sum(
            1 for _, a in attributions
            if a is not None and a.is_unknown
        )
        
        avg_confidence = 0.0
        if attributed > 0:
            confidences = [a.confidence for _, a in attributions if a is not None]
            avg_confidence = sum(confidences) / len(confidences)
        
        return {
            "total_claims": total,
            "attributed": attributed,
            "skipped": skipped,
            "confident": confident,
            "unknown": unknown,
            "average_confidence": avg_confidence,
        }

