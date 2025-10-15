"""
Structured Categories Analysis for Episodes

This module analyzes episodes to determine what Wikidata-style structured categories
they cover, following the methodology described at:
https://www.wikidata.org/wiki/Wikidata:Structured_Categories

The analyzer identifies topics based on claims, people, concepts, and jargon,
then maps them to structured category hierarchies similar to how Wikidata
organizes knowledge.
"""

import logging
from collections import defaultdict
from pathlib import Path

from .models.llm_system2 import System2LLM
from .types import PipelineOutputs, ScoredClaim, StructuredCategory

logger = logging.getLogger(__name__)


class StructuredCategoryAnalyzer:
    """
    Analyzes episode content to identify structured category coverage.

    This implements a simplified version of Wikidata's structured categories approach,
    identifying what topics an episode covers based on its claims, entities, and concepts.
    """

    def __init__(self, llm: System2LLM, prompt_path: Path):
        self.llm = llm
        self.template = prompt_path.read_text()

    def extract_topic_signals(self, outputs: PipelineOutputs) -> dict[str, list[str]]:
        """
        Extract topic signals from all pipeline outputs.

        Returns a mapping of signal_type -> list of signals
        """
        signals = defaultdict(list)

        # Extract from claims
        for claim in outputs.claims:
            signals["claims"].append(claim.canonical)
            signals["claim_types"].append(claim.claim_type)

        # Extract from people (organizations and persons)
        for person in outputs.people:
            signals["entities"].append(person.normalized or person.surface)
            if person.entity_type:
                signals["entity_types"].append(person.entity_type)

        # Extract from concepts/mental models
        for concept in outputs.concepts:
            signals["concepts"].append(concept.name)
            if concept.definition:
                signals["concept_definitions"].append(concept.definition)

        # Extract from jargon/technical terms
        for jargon in outputs.jargon:
            signals["jargon"].append(jargon.term)
            if jargon.category:
                signals["jargon_categories"].append(jargon.category)

        return dict(signals)

    def analyze_episode_categories(
        self, outputs: PipelineOutputs
    ) -> list[StructuredCategory]:
        """
        Analyze an episode to determine its structured category coverage.

        Args:
            outputs: Complete pipeline outputs for the episode

        Returns:
            List of structured categories with confidence scores
        """
        try:
            # Extract topic signals
            signals = self.extract_topic_signals(outputs)

            # Prepare analysis prompt
            prompt_text = self.template.format(
                episode_id=outputs.episode_id,
                num_claims=len(outputs.claims),
                claims_sample="\n".join(
                    [c.canonical for c in outputs.claims[:10]]
                ),  # First 10 claims
                entities=", ".join(
                    signals.get("entities", [])[:20]
                ),  # First 20 entities
                concepts=", ".join(
                    signals.get("concepts", [])[:15]
                ),  # First 15 concepts
                jargon=", ".join(
                    signals.get("jargon", [])[:15]
                ),  # First 15 jargon terms
                entity_types=", ".join(set(signals.get("entity_types", []))),
                claim_types=", ".join(set(signals.get("claim_types", []))),
            )

            # Get LLM analysis
            result = self.llm.generate_json(prompt_text)

            if not result or not isinstance(result, list):
                logger.warning(f"Invalid LLM response for episode {outputs.episode_id}")
                return []

            categories = []
            for i, category_data in enumerate(result):
                try:
                    # Ensure category_data is a dictionary before calling .get()
                    if not isinstance(category_data, dict):
                        logger.warning(
                            f"Skipping invalid category result type {type(category_data)} at index {i}: {category_data}"
                        )
                        continue

                    category = StructuredCategory(
                        category_id=f"cat_{outputs.episode_id}_{i}",
                        category_name=category_data.get(
                            "category_name", "Unknown Category"
                        ),
                        wikidata_qid=category_data.get("wikidata_qid"),
                        coverage_confidence=min(
                            max(category_data.get("confidence", 0.5), 0.0), 1.0
                        ),
                        supporting_evidence=category_data.get(
                            "supporting_claim_ids", []
                        ),
                        frequency_score=category_data.get("frequency_score", 0.0),
                    )
                    categories.append(category)

                except Exception as e:
                    logger.warning(
                        f"Failed to parse category {i} for episode {outputs.episode_id}: {e}"
                    )
                    continue

            # Propagate categories to individual claims
            self.propagate_categories_to_claims(outputs.claims, categories)

            return categories

        except Exception as e:
            logger.error(
                f"Failed to analyze categories for episode {outputs.episode_id}: {e}"
            )
            return []

    def propagate_categories_to_claims(
        self, claims: list[ScoredClaim], categories: list[StructuredCategory]
    ) -> None:
        """
        Propagate episode-level categories to individual claims based on relevance.

        This addresses point #2: writing category information into each claim.
        """
        try:
            # Create mapping of category names to categories for easy lookup
            category_map = {cat.category_name: cat for cat in categories}

            for claim in claims:
                claim_categories = []
                claim_relevance_scores = {}

                # For each category, determine if this claim is relevant
                for category in categories:
                    relevance_score = self.calculate_claim_category_relevance(
                        claim, category
                    )

                    # Only include categories where the claim has meaningful relevance
                    if relevance_score > 0.3:  # Threshold for inclusion
                        claim_categories.append(category.category_name)
                        claim_relevance_scores[category.category_name] = relevance_score

                # Update claim with category information
                claim.structured_categories = claim_categories
                claim.category_relevance_scores = claim_relevance_scores

                logger.debug(
                    f"Claim '{claim.canonical[:30]}...' assigned to {len(claim_categories)} categories"
                )

        except Exception as e:
            logger.error(f"Failed to propagate categories to claims: {e}")

    def calculate_claim_category_relevance(
        self, claim: ScoredClaim, category: StructuredCategory
    ) -> float:
        """
        Calculate how relevant a specific claim is to a specific category.

        Returns a score from 0.0-1.0 indicating relevance.
        """
        try:
            # Simple keyword-based relevance scoring
            category_keywords = category.category_name.lower().split()
            claim_text = claim.canonical.lower()

            # Check for direct keyword matches
            keyword_matches = sum(
                1 for keyword in category_keywords if keyword in claim_text
            )
            keyword_score = keyword_matches / max(len(category_keywords), 1)

            # Check if this claim is explicitly listed as supporting evidence
            explicit_support = (
                1.0 if claim.claim_id in category.supporting_evidence else 0.0
            )

            # Combine scores (weighted towards explicit support)
            relevance_score = (explicit_support * 0.7) + (keyword_score * 0.3)

            return min(relevance_score, 1.0)

        except Exception as e:
            logger.warning(f"Failed to calculate claim-category relevance: {e}")
            return 0.0

    def calculate_frequency_scores(
        self, categories: list[StructuredCategory], signals: dict[str, list[str]]
    ) -> list[StructuredCategory]:
        """
        Calculate frequency scores based on how often category-related terms appear.
        """
        total_signals = sum(len(signal_list) for signal_list in signals.values())

        for category in categories:
            # Simple frequency calculation based on category name appearing in signals
            category_terms = category.category_name.lower().split()
            frequency_count = 0

            for signal_list in signals.values():
                for signal in signal_list:
                    signal_lower = signal.lower()
                    if any(term in signal_lower for term in category_terms):
                        frequency_count += 1

            category.frequency_score = frequency_count / max(total_signals, 1)

        return categories


def analyze_structured_categories(
    outputs: PipelineOutputs, model_uri: str
) -> list[StructuredCategory]:
    """
    Analyze structured categories for an episode.

    Args:
        outputs: Complete pipeline outputs
        model_uri: URI for the LLM model to use

    Returns:
        List of structured categories
    """
    try:
        # Use the prompt from config/prompts directory
        prompt_path = (
            Path(__file__).parent.parent.parent.parent
            / "config"
            / "prompts"
            / "structured_categories.txt"
        )

        if not prompt_path.exists():
            logger.warning(
                f"Structured categories prompt not found at {prompt_path}, skipping analysis"
            )
            return []

        logger.info(f"Analyzing structured categories for episode {outputs.episode_id}")

        # Create LLM instance and analyzer
        from .model_uri_parser import parse_model_uri
        from .models.llm_system2 import create_system2_llm

        # Parse model URI with proper handling of local:// and other formats
        provider, model = parse_model_uri(model_uri)

        llm = create_system2_llm(provider=provider, model=model)
        analyzer = StructuredCategoryAnalyzer(llm, prompt_path)
        categories = analyzer.analyze_episode_categories(outputs)

        logger.info(
            f"Identified {len(categories)} structured categories for episode {outputs.episode_id}"
        )
        return categories

    except Exception as e:
        logger.error(f"Failed to analyze structured categories: {e}")
        return []


# Utility functions for category analysis


def get_common_wikidata_categories() -> dict[str, str]:
    """
    Return a mapping of common category names to their Wikidata Q-identifiers.

    This provides a lookup for commonly referenced categories to enable
    linking to actual Wikidata entries.
    """
    return {
        "artificial intelligence": "Q11660",
        "machine learning": "Q2539",
        "technology": "Q11016",
        "science": "Q336",
        "philosophy": "Q5891",
        "economics": "Q8134",
        "politics": "Q7163",
        "business": "Q4830453",
        "health": "Q12136",
        "education": "Q8434",
        "history": "Q309",
        "mathematics": "Q395",
        "physics": "Q413",
        "biology": "Q420",
        "chemistry": "Q2329",
        "psychology": "Q9418",
        "sociology": "Q21201",
        "literature": "Q8242",
        "art": "Q735",
        "music": "Q638",
        "film": "Q11424",
        "sports": "Q349",
        "medicine": "Q11190",
        "law": "Q7748",
        "finance": "Q43015",
        "climate change": "Q125928",
        "environment": "Q2249676",
        "energy": "Q11379",
        "transportation": "Q7590",
        "communication": "Q11024",
    }


def categorize_by_domain(
    entities: list[str], concepts: list[str], jargon: list[str]
) -> dict[str, float]:
    """
    Simple heuristic categorization based on domain-specific terms.

    Returns a mapping of domain -> confidence score based on term frequency.
    """
    domain_keywords = {
        "technology": [
            "ai",
            "algorithm",
            "software",
            "computer",
            "digital",
            "data",
            "cloud",
            "api",
        ],
        "science": [
            "research",
            "study",
            "experiment",
            "hypothesis",
            "theory",
            "evidence",
            "peer review",
        ],
        "business": [
            "company",
            "market",
            "revenue",
            "profit",
            "strategy",
            "customer",
            "product",
        ],
        "politics": [
            "government",
            "policy",
            "election",
            "democracy",
            "vote",
            "congress",
            "president",
        ],
        "health": [
            "medical",
            "doctor",
            "patient",
            "treatment",
            "diagnosis",
            "therapy",
            "hospital",
        ],
        "economics": [
            "economy",
            "inflation",
            "gdp",
            "market",
            "trade",
            "finance",
            "investment",
        ],
        "education": [
            "school",
            "university",
            "student",
            "teacher",
            "learning",
            "curriculum",
            "degree",
        ],
    }

    all_terms = [term.lower() for term in entities + concepts + jargon]
    domain_scores = {}

    for domain, keywords in domain_keywords.items():
        score = sum(
            1 for term in all_terms if any(keyword in term for keyword in keywords)
        )
        domain_scores[domain] = score / max(len(all_terms), 1)

    return domain_scores


def suggest_wikidata_qids(category_name: str) -> list[str]:
    """
    Suggest potential Wikidata Q-identifiers for a category name.

    This is a simple lookup function that could be enhanced with
    actual Wikidata API calls in the future.
    """
    common_categories = get_common_wikidata_categories()

    category_lower = category_name.lower()
    suggestions = []

    # Exact match
    if category_lower in common_categories:
        suggestions.append(common_categories[category_lower])

    # Partial matches
    for cat_name, qid in common_categories.items():
        if category_lower in cat_name or cat_name in category_lower:
            suggestions.append(qid)

    return suggestions[:3]  # Return top 3 suggestions
