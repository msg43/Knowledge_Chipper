"""
Entity Converters for HCE Pipeline

Breaks down the massive _convert_to_pipeline_outputs() method (217 lines)
into focused converter classes for each entity type.

Extracted from unified_pipeline.py lines 560-777.
"""

from typing import Any

from .types import (
    ConceptEntity,
    EpisodeBundle,
    EvidenceSpan,
    JargonEntity,
    PersonEntity,
    ScoredClaim,
    UnifiedMinerOutput,
)


class ClaimConverter:
    """Converts evaluated claims to ScoredClaim format."""

    @staticmethod
    def convert(
        episode: EpisodeBundle,
        miner_outputs: list[UnifiedMinerOutput],
        claims_evaluation,  # FlagshipEvaluationOutput
    ) -> list[ScoredClaim]:
        """
        Convert evaluated claims to ScoredClaim format.

        Args:
            episode: Episode bundle with metadata
            miner_outputs: Raw miner outputs with evidence
            claims_evaluation: Flagship evaluation results

        Returns:
            List of scored claims with evidence
        """
        scored_claims = []
        accepted_claims = claims_evaluation.get_claims_by_rank()

        for eval_claim in accepted_claims:
            # Find original claim data to get evidence
            original_claim = ClaimConverter._find_original_claim(
                miner_outputs, eval_claim.original_claim_text
            )

            if not original_claim:
                continue

            # Convert evidence spans
            evidence_spans = ClaimConverter._convert_evidence_spans(original_claim)

            # Create scored claim
            scored_claim = ScoredClaim(
                source_id=episode.source_id,
                claim_id=original_claim.get("claim_id", ""),
                canonical=eval_claim.original_claim_text,
                claim_type=original_claim.get("type", "factual"),
                evidence=evidence_spans,
                tier=eval_claim.tier,
                scores={
                    "importance": eval_claim.importance,
                    "novelty": eval_claim.novelty,
                    "confidence": eval_claim.confidence,
                },
                domain=original_claim.get("domain", "general"),
                temporality_score=None,
                temporality_confidence=None,
                temporality_rationale=None,
                structured_categories=[],
                category_relevance_scores={},
            )

            scored_claims.append(scored_claim)

        return scored_claims

    @staticmethod
    def _find_original_claim(
        miner_outputs: list[UnifiedMinerOutput],
        claim_text: str,
    ) -> dict[str, Any] | None:
        """Find original claim data from miner outputs."""
        for output in miner_outputs:
            for claim in output.claims:
                if claim.get("claim_text", "") == claim_text:
                    return claim
        return None

    @staticmethod
    def _convert_evidence_spans(claim: dict[str, Any]) -> list[EvidenceSpan]:
        """Convert evidence spans to v2 schema format."""
        evidence_spans = []
        for evidence in claim.get("evidence_spans", []):
            evidence_spans.append(
                EvidenceSpan(
                    t0=evidence.get("t0", ""),
                    t1=evidence.get("t1", ""),
                    quote=evidence.get("quote", ""),
                    segment_id=evidence.get("segment_id"),
                    context_t0=evidence.get("context_t0"),
                    context_t1=evidence.get("context_t1"),
                    context_text=evidence.get("context_text"),
                    context_type=evidence.get("context_type", "exact"),
                )
            )
        return evidence_spans


class JargonConverter:
    """Converts evaluated jargon terms to JargonEntity format."""

    @staticmethod
    def convert(
        episode: EpisodeBundle,
        miner_outputs: list[UnifiedMinerOutput],
        jargon_evaluation,  # JargonEvaluationOutput | None
    ) -> list[JargonEntity]:
        """Convert evaluated jargon to JargonEntity format."""
        if not jargon_evaluation:
            return []

        jargon_entities = []
        accepted_jargon = jargon_evaluation.accepted_terms

        for eval_term in accepted_jargon:
            # Find original jargon data
            original_jargon = JargonConverter._find_original_jargon(
                miner_outputs, eval_term.term
            )

            if not original_jargon:
                continue

            jargon_entity = JargonEntity(
                term=eval_term.term,
                definition=original_jargon.get("definition", ""),
                category=original_jargon.get("category", "general"),
                importance_score=eval_term.importance,
                context=original_jargon.get("context", ""),
            )

            jargon_entities.append(jargon_entity)

        return jargon_entities

    @staticmethod
    def _find_original_jargon(
        miner_outputs: list[UnifiedMinerOutput],
        term: str,
    ) -> dict[str, Any] | None:
        """Find original jargon data from miner outputs."""
        for output in miner_outputs:
            for jargon in output.jargon:
                if jargon.get("term", "") == term:
                    return jargon
        return None


class PersonConverter:
    """Converts evaluated people to PersonEntity format."""

    @staticmethod
    def convert(
        episode: EpisodeBundle,
        miner_outputs: list[UnifiedMinerOutput],
        people_evaluation,  # PeopleEvaluationOutput | None
    ) -> list[PersonEntity]:
        """Convert evaluated people to PersonEntity format."""
        if not people_evaluation:
            return []

        person_entities = []
        accepted_people = people_evaluation.accepted_people

        for eval_person in accepted_people:
            # Find original person data
            original_person = PersonConverter._find_original_person(
                miner_outputs, eval_person.name
            )

            if not original_person:
                continue

            person_entity = PersonEntity(
                name=eval_person.name,
                description=original_person.get("description", ""),
                role=original_person.get("role", ""),
                relevance_score=eval_person.relevance,
                mentions=original_person.get("mentions", []),
            )

            person_entities.append(person_entity)

        return person_entities

    @staticmethod
    def _find_original_person(
        miner_outputs: list[UnifiedMinerOutput],
        name: str,
    ) -> dict[str, Any] | None:
        """Find original person data from miner outputs."""
        for output in miner_outputs:
            for person in output.people:
                if person.get("name", "") == name:
                    return person
        return None


class ConceptConverter:
    """Converts evaluated concepts to ConceptEntity format."""

    @staticmethod
    def convert(
        episode: EpisodeBundle,
        miner_outputs: list[UnifiedMinerOutput],
        concepts_evaluation,  # ConceptsEvaluationOutput | None
    ) -> list[ConceptEntity]:
        """Convert evaluated concepts to ConceptEntity format."""
        if not concepts_evaluation:
            return []

        concept_entities = []
        accepted_concepts = concepts_evaluation.accepted_concepts

        for eval_concept in accepted_concepts:
            # Find original concept data
            original_concept = ConceptConverter._find_original_concept(
                miner_outputs, eval_concept.concept
            )

            if not original_concept:
                continue

            concept_entity = ConceptEntity(
                concept=eval_concept.concept,
                description=original_concept.get("description", ""),
                importance_score=eval_concept.importance,
                related_terms=original_concept.get("related_terms", []),
            )

            concept_entities.append(concept_entity)

        return concept_entities

    @staticmethod
    def _find_original_concept(
        miner_outputs: list[UnifiedMinerOutput],
        concept: str,
    ) -> dict[str, Any] | None:
        """Find original concept data from miner outputs."""
        for output in miner_outputs:
            for con in output.concepts:
                if con.get("concept", "") == concept:
                    return con
        return None
