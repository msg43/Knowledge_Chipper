"""
Claim Evolution Detector

Post-extraction analysis to detect:
- Duplicate claims (≥95% similar) → Don't re-extract
- Evolved claims (85-94% similar) → Link to previous
- Contradictions → Flag explicitly

Leverages TasteEngine's sentence-transformers for similarity.

Usage:
    from knowledge_system.processors.claim_evolution_detector import ClaimEvolutionDetector
    
    detector = ClaimEvolutionDetector()
    enhanced_claims = await detector.analyze_claims(
        new_claims=extraction_result.claims,
        channel_id='UC123...',
        episode_date='2024-01-15'
    )
"""

import asyncio
from typing import Any
from ..logger import get_logger
from ..services.rae_service import get_rae_service
from ..services.taste_engine import get_taste_engine

logger = get_logger(__name__)


class ClaimEvolutionDetector:
    """Detects claim evolution and contradictions post-extraction."""
    
    def __init__(self):
        """Initialize detector with RAE service and TasteEngine."""
        self.rae_service = get_rae_service()
        self.taste_engine = get_taste_engine()
        logger.info("ClaimEvolutionDetector initialized")
    
    async def analyze_claims(
        self,
        new_claims: list[dict],
        channel_id: str,
        episode_date: str
    ) -> list[dict]:
        """
        Analyze new claims against channel history.
        
        Args:
            new_claims: Claims extracted from current episode
            channel_id: YouTube channel ID
            episode_date: Date of current episode
        
        Returns:
            Claims with evolution metadata:
            - evolution_status: 'novel' | 'duplicate' | 'evolution' | 'contradiction'
            - evolves_from: claim_id of previous version
            - similarity_score: 0.0-1.0
            - is_contradiction: boolean
        """
        
        if not channel_id:
            logger.debug("No channel_id - marking all claims as novel")
            for claim in new_claims:
                claim['evolution_status'] = 'novel'
            return new_claims
        
        # Fetch channel history
        history = await self.rae_service.fetch_channel_history(channel_id)
        
        if not history.get('top_claims'):
            # No history, all claims are novel
            logger.info("No claim history for this channel - all claims are novel")
            for claim in new_claims:
                claim['evolution_status'] = 'novel'
            return new_claims
        
        # Flatten claims from history
        historical_claims = []
        for topic_claims in history.get('top_claims', {}).values():
            historical_claims.extend(topic_claims)
        
        if not historical_claims:
            logger.info("No historical claims found - all claims are novel")
            for claim in new_claims:
                claim['evolution_status'] = 'novel'
            return new_claims
        
        logger.info(f"Analyzing {len(new_claims)} new claims against {len(historical_claims)} historical claims")
        
        enhanced_claims = []
        stats = {
            'novel': 0,
            'duplicate': 0,
            'evolution': 0,
            'contradiction': 0
        }
        
        for claim in new_claims:
            # Calculate similarity to all historical claims using TasteEngine's embeddings
            similarities = []
            
            for hist_claim in historical_claims:
                similarity = self._calculate_similarity(
                    claim.get('canonical', ''),
                    hist_claim.get('canonical', '')
                )
                
                if similarity >= 0.85:
                    similarities.append({
                        'claim_id': hist_claim.get('claim_id'),
                        'canonical': hist_claim.get('canonical'),
                        'episode_id': hist_claim.get('episode_id'),
                        'similarity': similarity
                    })
            
            # Sort by similarity (highest first)
            similarities.sort(key=lambda x: x['similarity'], reverse=True)
            
            # Classify based on similarity
            if not similarities:
                # No similar claims found
                claim['evolution_status'] = 'novel'
                stats['novel'] += 1
            
            elif similarities[0]['similarity'] >= 0.95:
                # DUPLICATE - Skip extraction
                claim['evolution_status'] = 'duplicate'
                claim['duplicate_of'] = similarities[0]['claim_id']
                claim['similarity_score'] = similarities[0]['similarity']
                stats['duplicate'] += 1
                logger.debug(f"🔁 Duplicate claim detected ({similarities[0]['similarity']:.2f}): {claim.get('canonical', '')[:50]}...")
            
            elif similarities[0]['similarity'] >= 0.85:
                # EVOLUTION - Check for contradiction
                claim['evolution_status'] = 'evolution'
                claim['evolves_from'] = similarities[0]['claim_id']
                claim['similarity_score'] = similarities[0]['similarity']
                
                # Use LLM to check contradiction
                is_contradiction = await self._check_contradiction(
                    claim.get('canonical', ''),
                    similarities[0]['canonical']
                )
                
                if is_contradiction:
                    claim['evolution_status'] = 'contradiction'
                    claim['is_contradiction'] = True
                    claim['contradicts_claim_id'] = similarities[0]['claim_id']
                    stats['contradiction'] += 1
                    logger.warning(f"⚠️ Contradiction detected ({similarities[0]['similarity']:.2f}): {claim.get('canonical', '')[:50]}...")
                else:
                    stats['evolution'] += 1
                    logger.debug(f"🔄 Evolution detected ({similarities[0]['similarity']:.2f}): {claim.get('canonical', '')[:50]}...")
            
            enhanced_claims.append(claim)
        
        # Filter out duplicates (don't store them again)
        final_claims = [c for c in enhanced_claims if c.get('evolution_status') != 'duplicate']
        
        logger.info(
            f"Evolution analysis complete: "
            f"{stats['novel']} novel, "
            f"{stats['duplicate']} duplicates (skipped), "
            f"{stats['evolution']} evolutions, "
            f"{stats['contradiction']} contradictions"
        )
        
        return final_claims
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate semantic similarity between two claim texts.
        
        Leverages TasteEngine's sentence-transformers model.
        
        Args:
            text1: First claim text
            text2: Second claim text
            
        Returns:
            Similarity score (0.0-1.0)
        """
        if not text1 or not text2:
            return 0.0
        
        try:
            # Use TasteEngine's embedding model
            embeddings = self.taste_engine._model.encode([text1, text2])
            
            # Cosine similarity
            import numpy as np
            
            similarity = np.dot(embeddings[0], embeddings[1]) / (
                np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1])
            )
            return float(similarity)
            
        except Exception as e:
            logger.warning(f"Embedding similarity failed, using fallback: {e}")
            # Fallback to simple token overlap
            from difflib import SequenceMatcher
            return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    async def _check_contradiction(self, new_claim: str, old_claim: str) -> bool:
        """
        Use LLM to determine if claims contradict.
        
        Args:
            new_claim: Newly extracted claim
            old_claim: Historical claim
            
        Returns:
            True if claims contradict each other
        """
        if not new_claim or not old_claim:
            return False
        
        # Simple heuristic-based check for now
        # TODO: Integrate with existing LLM adapter for more sophisticated detection
        
        # Check for negation patterns
        negations = [
            'not', 'never', 'no longer', 'opposite', 'contrary', 
            'false', 'incorrect', 'wrong', 'actually', 'instead',
            'rather than', 'as opposed to'
        ]
        
        new_lower = new_claim.lower()
        old_lower = old_claim.lower()
        
        # If new claim contains negation and has high overlap with old claim
        has_negation = any(neg in new_lower for neg in negations)
        
        # Check for semantic overlap (are they about the same thing?)
        from difflib import SequenceMatcher
        token_overlap = SequenceMatcher(None, new_lower, old_lower).ratio()
        
        # Contradiction if:
        # 1. High semantic overlap (same topic)
        # 2. Contains negation words
        is_contradiction = has_negation and token_overlap > 0.5
        
        if is_contradiction:
            logger.debug(f"Contradiction detected: negation={has_negation}, overlap={token_overlap:.2f}")
        
        return is_contradiction


# ============================================================================
# Singleton instance
# ============================================================================

_detector: ClaimEvolutionDetector | None = None


def get_claim_evolution_detector() -> ClaimEvolutionDetector:
    """
    Get or create singleton ClaimEvolutionDetector instance.
    
    Returns:
        ClaimEvolutionDetector singleton instance
    """
    global _detector
    if _detector is None:
        _detector = ClaimEvolutionDetector()
    return _detector
