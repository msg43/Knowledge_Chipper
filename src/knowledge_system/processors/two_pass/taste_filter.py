"""
Taste Filter - Vector-based style validation (Pass 1.5a)

Fast vector similarity check against user feedback to:
- Auto-discard entities highly similar to past rejections (>95%)
- Flag suspicious entities for review (80-95% similar to rejections)
- Boost entities highly similar to past acceptances (>95% - Positive Echo)
- Keep everything else

This is the "Taste" layer - catches style errors, duplicates, and patterns.
The Truth Critic (Pass 1.5b) handles logic errors.
"""

from dataclasses import dataclass
from typing import Literal, Optional

from ...logger import get_logger
from ...services.taste_engine import get_taste_engine, SimilarExample

logger = get_logger(__name__)


@dataclass
class FilterVerdict:
    """Result of filtering a single entity."""
    action: Literal["discard", "flag", "keep", "boost"]
    similarity_to_reject: float
    similarity_to_accept: float
    matched_example: str
    reason_category: str
    warning_message: str
    score_adjustment: float  # 0 for most, positive for boost


@dataclass
class FilterResult:
    """Result of filtering all entities in an extraction."""
    claims: list[dict]
    people: list[dict]
    jargon: list[dict]
    concepts: list[dict]
    stats: dict


class TasteFilter:
    """
    Vector-based filter for style/pattern validation.
    
    Uses the TasteEngine to compare new entities against past feedback.
    Fast (~50ms per entity) compared to LLM-based validation.
    """
    
    # Similarity thresholds (using normalized similarity 0-1)
    # Higher = more similar
    DISCARD_THRESHOLD = 0.95  # >95% similar to rejection = auto-discard
    FLAG_THRESHOLD = 0.80     # 80-95% similar to rejection = flag for review
    BOOST_THRESHOLD = 0.95    # >95% similar to acceptance = quality boost
    
    # Score adjustments
    POSITIVE_ECHO_BOOST = 2.0  # Add to importance score for boosted entities
    
    def __init__(
        self,
        discard_threshold: float = 0.95,
        flag_threshold: float = 0.80,
        boost_threshold: float = 0.95,
        positive_echo_boost: float = 2.0
    ):
        """
        Initialize the TasteFilter.
        
        Args:
            discard_threshold: Similarity to rejection above which to auto-discard.
            flag_threshold: Similarity to rejection above which to flag.
            boost_threshold: Similarity to acceptance above which to boost.
            positive_echo_boost: Score adjustment for boosted entities.
        """
        self.discard_threshold = discard_threshold
        self.flag_threshold = flag_threshold
        self.boost_threshold = boost_threshold
        self.positive_echo_boost = positive_echo_boost
        
        self._taste_engine = None
    
    @property
    def taste_engine(self):
        """Lazy-load the taste engine."""
        if self._taste_engine is None:
            self._taste_engine = get_taste_engine()
        return self._taste_engine
    
    def filter(self, extraction_result: dict) -> FilterResult:
        """
        Filter all entities in an extraction result.
        
        Args:
            extraction_result: Dict with claims, people, jargon, concepts lists.
            
        Returns:
            FilterResult with filtered entities and statistics.
        """
        stats = {
            "total_processed": 0,
            "discarded": 0,
            "flagged": 0,
            "boosted": 0,
            "kept": 0,
            "by_type": {}
        }
        
        filtered_claims = self._filter_entity_list(
            extraction_result.get("claims", []),
            "claim",
            stats
        )
        
        filtered_people = self._filter_entity_list(
            extraction_result.get("people", []),
            "person",
            stats
        )
        
        filtered_jargon = self._filter_entity_list(
            extraction_result.get("jargon", []),
            "jargon",
            stats
        )
        
        filtered_concepts = self._filter_entity_list(
            extraction_result.get("concepts", []),
            "concept",
            stats
        )
        
        logger.info(
            f"TasteFilter: {stats['discarded']} discarded, "
            f"{stats['flagged']} flagged, {stats['boosted']} boosted, "
            f"{stats['kept']} kept"
        )
        
        return FilterResult(
            claims=filtered_claims,
            people=filtered_people,
            jargon=filtered_jargon,
            concepts=filtered_concepts,
            stats=stats
        )
    
    def _filter_entity_list(
        self,
        entities: list[dict],
        entity_type: str,
        stats: dict
    ) -> list[dict]:
        """Filter a list of entities of the same type."""
        filtered = []
        type_stats = {"discarded": 0, "flagged": 0, "boosted": 0, "kept": 0}
        
        for entity in entities:
            stats["total_processed"] += 1
            
            # Get the text to compare
            entity_text = self._get_entity_text(entity, entity_type)
            if not entity_text:
                filtered.append(entity)
                type_stats["kept"] += 1
                continue
            
            verdict = self._check_entity(entity_text, entity_type)
            
            if verdict.action == "discard":
                # Skip this entity entirely
                type_stats["discarded"] += 1
                stats["discarded"] += 1
                logger.debug(
                    f"Discarded {entity_type}: '{entity_text[:50]}...' "
                    f"(similar to: '{verdict.matched_example[:50]}...')"
                )
                continue
            
            elif verdict.action == "flag":
                # Keep but mark as flagged
                entity["_flagged"] = True
                entity["_flag_reason"] = verdict.warning_message
                entity["_similar_rejection"] = verdict.matched_example
                type_stats["flagged"] += 1
                stats["flagged"] += 1
                filtered.append(entity)
            
            elif verdict.action == "boost":
                # Keep and boost importance score
                entity["_boosted"] = True
                entity["_boost_reason"] = "Positive Echo: similar to accepted example"
                entity["_similar_acceptance"] = verdict.matched_example
                
                # Apply score boost if entity has importance_score
                if "importance_score" in entity:
                    original = entity["importance_score"]
                    entity["importance_score"] = min(10.0, original + verdict.score_adjustment)
                    entity["_original_importance"] = original
                
                type_stats["boosted"] += 1
                stats["boosted"] += 1
                filtered.append(entity)
            
            else:  # keep
                type_stats["kept"] += 1
                stats["kept"] += 1
                filtered.append(entity)
        
        stats["by_type"][entity_type] = type_stats
        return filtered
    
    def _get_entity_text(self, entity: dict, entity_type: str) -> Optional[str]:
        """Extract the text content from an entity for comparison."""
        if entity_type == "claim":
            return entity.get("canonical") or entity.get("text")
        elif entity_type == "person":
            return entity.get("name")
        elif entity_type == "jargon":
            return entity.get("term")
        elif entity_type == "concept":
            return entity.get("name")
        return None
    
    def _check_entity(self, text: str, entity_type: str) -> FilterVerdict:
        """
        Check a single entity against the taste engine.
        
        Returns a verdict with action and metadata.
        """
        # Query for similar rejections
        reject_results = self.taste_engine.query_similar(
            text=text,
            entity_type=entity_type,
            verdict="reject",
            n_results=1
        )
        
        # Query for similar acceptances
        accept_results = self.taste_engine.query_similar(
            text=text,
            entity_type=entity_type,
            verdict="accept",
            n_results=1
        )
        
        # Get similarity scores
        reject_similarity = reject_results[0].similarity if reject_results else 0.0
        accept_similarity = accept_results[0].similarity if accept_results else 0.0
        
        reject_example = reject_results[0] if reject_results else None
        accept_example = accept_results[0] if accept_results else None
        
        # Decision logic: Check rejections first (safety-first)
        if reject_similarity >= self.discard_threshold:
            return FilterVerdict(
                action="discard",
                similarity_to_reject=reject_similarity,
                similarity_to_accept=accept_similarity,
                matched_example=reject_example.text if reject_example else "",
                reason_category=reject_example.metadata.get("reason_category", "") if reject_example else "",
                warning_message=f"Auto-discarded: {reject_similarity:.0%} similar to past rejection",
                score_adjustment=0.0
            )
        
        elif reject_similarity >= self.flag_threshold:
            return FilterVerdict(
                action="flag",
                similarity_to_reject=reject_similarity,
                similarity_to_accept=accept_similarity,
                matched_example=reject_example.text if reject_example else "",
                reason_category=reject_example.metadata.get("reason_category", "") if reject_example else "",
                warning_message=f"Flagged: {reject_similarity:.0%} similar to past rejection",
                score_adjustment=0.0
            )
        
        # Check for positive echo (boost)
        elif accept_similarity >= self.boost_threshold:
            return FilterVerdict(
                action="boost",
                similarity_to_reject=reject_similarity,
                similarity_to_accept=accept_similarity,
                matched_example=accept_example.text if accept_example else "",
                reason_category=accept_example.metadata.get("reason_category", "") if accept_example else "",
                warning_message="",
                score_adjustment=self.positive_echo_boost
            )
        
        # Default: keep as-is
        return FilterVerdict(
            action="keep",
            similarity_to_reject=reject_similarity,
            similarity_to_accept=accept_similarity,
            matched_example="",
            reason_category="",
            warning_message="",
            score_adjustment=0.0
        )
