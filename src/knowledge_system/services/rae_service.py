"""
Retrieval-Augmented Extraction (RAE) Service

Fetches channel history from GetReceipts.org to inject into extraction prompts.
Implements two strategies:
1. Jargon: STRICT REGISTRY (block inconsistent definitions)
2. Claims: EVOLUTION CONTEXT (track changes, expose contradictions)

Usage:
    from knowledge_system.services.rae_service import get_rae_service
    
    rae_service = get_rae_service()
    history = await rae_service.fetch_channel_history(channel_id)
    
    # Build prompt sections
    jargon_section = rae_service.build_jargon_registry_section(history['jargon_registry'])
    claims_section = rae_service.build_claims_context_section(history['top_claims'])
"""

import httpx
from typing import Any, Optional
from ..logger import get_logger

logger = get_logger(__name__)

GETRECEIPTS_API = "https://getreceipts.org/api"
DEVELOPMENT_API = "http://localhost:3000/api"


class RAEService:
    """Manages RAE context retrieval and formatting."""
    
    def __init__(self, use_production: bool = True):
        """
        Initialize RAE service.
        
        Args:
            use_production: Whether to use production API (default True)
        """
        self.api_url = GETRECEIPTS_API if use_production else DEVELOPMENT_API
        logger.info(f"RAEService initialized - API: {self.api_url}")
    
    async def fetch_channel_history(
        self, 
        channel_id: str,
        claim_limit: int = 50,
        jargon_limit: int = 100
    ) -> dict[str, Any]:
        """
        Fetch channel history for RAE context.
        
        Args:
            channel_id: YouTube channel ID
            claim_limit: Maximum number of claims to fetch
            jargon_limit: Maximum number of jargon terms to fetch
        
        Returns:
            {
                "jargon_registry": [...],
                "top_claims": {...},
                "metadata": {...}
            }
        """
        if not channel_id:
            logger.debug("No channel_id provided, skipping RAE context")
            return {"jargon_registry": [], "top_claims": {}, "metadata": {}}
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.api_url}/channels/{channel_id}/history",
                    params={
                        "claim_limit": claim_limit,
                        "jargon_limit": jargon_limit
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(
                        f"✅ RAE context fetched for channel {channel_id[:12]}...: "
                        f"{len(data.get('jargon_registry', []))} jargon terms, "
                        f"{sum(len(claims) for claims in data.get('top_claims', {}).values())} claims"
                    )
                    return data
                elif response.status_code == 404:
                    logger.debug(f"No history found for channel {channel_id[:12]}...")
                    return {"jargon_registry": [], "top_claims": {}, "metadata": {}}
                else:
                    logger.warning(f"RAE fetch failed: {response.status_code}")
                    return {"jargon_registry": [], "top_claims": {}, "metadata": {}}
                    
        except httpx.TimeoutException:
            logger.warning(f"RAE fetch timeout for channel {channel_id[:12]}...")
            return {"jargon_registry": [], "top_claims": {}, "metadata": {}}
        except Exception as e:
            logger.error(f"RAE fetch error: {e}")
            return {"jargon_registry": [], "top_claims": {}, "metadata": {}}
    
    def build_jargon_registry_section(self, jargon_terms: list[dict]) -> str:
        """
        Build STRICT REGISTRY section for jargon.
        
        Strategy: Block extraction of terms with different definitions.
        
        Args:
            jargon_terms: List of jargon terms from channel history
            
        Returns:
            Formatted section for prompt injection
        """
        if not jargon_terms:
            return ""
        
        section = "\n\n# 📚 JARGON REGISTRY - STRICT CONSISTENCY REQUIRED\n\n"
        section += "## CRITICAL: Use Established Definitions\n\n"
        section += "The following terms have been defined in previous episodes from this channel.\n"
        section += "**YOU MUST use these exact definitions. DO NOT extract the same term with a different definition.**\n\n"
        section += "If the speaker uses a term differently than defined below:\n"
        section += "1. Note the discrepancy in your extraction metadata\n"
        section += "2. Flag it as `definition_conflict: true`\n"
        section += "3. Include both definitions for human review\n\n"
        
        # Group by domain
        by_domain: dict[str, list[dict]] = {}
        for term in jargon_terms[:50]:  # Top 50 most-used terms
            domain = term.get('domain', 'general')
            if domain not in by_domain:
                by_domain[domain] = []
            by_domain[domain].append(term)
        
        # Format by domain
        for domain, terms in sorted(by_domain.items()):
            section += f"### {domain.title()} Terms:\n\n"
            for term in terms:
                definition = term.get('definition', 'No definition available')
                section += f"- **{term['term']}**: {definition}\n"
                episode_ref = term.get('episode_id', 'unknown')
                section += f"  (First defined: Episode {episode_ref})\n"
            section += "\n"
        
        return section
    
    def build_claims_context_section(self, claims_by_topic: dict[str, list[dict]]) -> str:
        """
        Build EVOLUTION CONTEXT section for claims.
        
        Strategy: Show what's been said before, enable duplicate detection and contradiction exposure.
        
        Args:
            claims_by_topic: Claims grouped by topic/domain
            
        Returns:
            Formatted section for prompt injection
        """
        if not claims_by_topic:
            return ""
        
        section = "\n\n# 🔄 PREVIOUS CLAIMS FROM THIS CHANNEL\n\n"
        section += "## Instructions for Claim Extraction:\n\n"
        section += "1. **If claim is ≥95% similar to one below**: SKIP IT (already extracted)\n"
        section += "2. **If claim is 85-94% similar but different**: EXTRACT IT and note:\n"
        section += "   - `evolves_from`: Reference to previous claim\n"
        section += "   - `evolution_note`: What changed from previous version\n"
        section += "3. **If claim CONTRADICTS a previous claim**: DEFINITELY EXTRACT IT and flag:\n"
        section += "   - `is_contradiction: true`\n"
        section += "   - `contradicts_claim_id`: ID of contradicted claim\n"
        section += "   - `contradiction_explanation`: How they contradict\n\n"
        section += "**IMPORTANT**: We WANT to expose contradictions, not hide them!\n\n"
        
        # Format claims by topic
        for topic, claims in sorted(claims_by_topic.items()):
            section += f"## {topic.title()} Claims:\n\n"
            for claim in claims[:10]:  # Top 10 per topic
                episode_ref = claim.get('episode_id', 'unknown')
                date = claim.get('created_at', '')[:10] if claim.get('created_at') else 'unknown date'
                canonical = claim.get('canonical', 'No text')
                section += f"- \"{canonical}\" (Episode {episode_ref}, {date})\n"
            section += "\n"
        
        return section


# ============================================================================
# Singleton instance
# ============================================================================

_rae_service: Optional[RAEService] = None


def get_rae_service(use_production: bool = True) -> RAEService:
    """
    Get or create singleton RAEService instance.
    
    Args:
        use_production: Whether to use production API (default True)
        
    Returns:
        RAEService singleton instance
    """
    global _rae_service
    if _rae_service is None:
        _rae_service = RAEService(use_production=use_production)
    return _rae_service
