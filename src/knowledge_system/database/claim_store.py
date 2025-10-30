"""
Claim-Centric HCE storage for the main application database.

Stores HCE pipeline outputs using a claim-first architecture where claims are
the fundamental unit and sources provide attribution metadata.
"""

from __future__ import annotations

import logging
from typing import Any

from ..processors.hce.types import Milestone, PipelineOutputs
from .models import (
    Claim,
    ClaimCategory,
    ClaimConcept,
    ClaimExport,
    ClaimJargon,
    ClaimPerson,
    ClaimRelation,
    ClaimTag,
    Concept,
    ConceptAlias,
    ConceptEvidence,
    Episode,
    EvidenceSpan,
    JargonEvidence,
    JargonTerm,
    MediaSource,
    Person,
    PersonEvidence,
    PersonExternalId,
    Segment,
    WikiDataCategory,
)
from .service import DatabaseService

logger = logging.getLogger(__name__)


class ClaimStore:
    """
    Facade for persisting HCE PipelineOutputs into the claim-centric database.

    This replaces the old HCEStore with a claim-first approach:
    - Claims have global unique IDs
    - Claims reference sources (not vice versa)
    - Sources provide attribution metadata
    - Episodes are optional (only for segmented content)
    """

    def __init__(self, db_service: DatabaseService):
        self.db_service = db_service

    def store_segments(
        self,
        episode_id: str,
        segments: list,
    ) -> None:
        """
        Store segments for an episode before storing claims.
        
        This must be called before upsert_pipeline_outputs to ensure
        foreign key constraints are satisfied when storing evidence spans.
        
        Args:
            episode_id: The episode ID
            segments: List of Segment objects with segment_id, text, speaker, t0, t1
        """
        with self.db_service.get_session() as session:
            # Delete existing segments for this episode
            session.query(Segment).filter_by(episode_id=episode_id).delete()
            
            # Store new segments
            for i, segment in enumerate(segments):
                # Generate fully qualified segment_id (episode_id + segment_id)
                # The segment.segment_id is just "seg_0001", we need to make it globally unique
                segment_id = f"{episode_id}_{segment.segment_id}"
                
                db_segment = Segment(
                    segment_id=segment_id,
                    episode_id=episode_id,
                    speaker=segment.speaker,
                    start_time=segment.t0,
                    end_time=segment.t1,
                    text=segment.text,
                    topic_guess=getattr(segment, "topic_guess", None),
                    sequence=i,
                )
                session.add(db_segment)
            
            session.commit()
            logger.info(f"Stored {len(segments)} segments for episode {episode_id}")

    def upsert_pipeline_outputs(
        self,
        outputs: PipelineOutputs,
        source_id: str,
        source_type: str = "episode",
        episode_title: str | None = None,
        recorded_at: str | None = None,
    ) -> None:
        """
        Persist pipeline outputs into the claim-centric schema.

        Args:
            outputs: PipelineOutputs from UnifiedHCEPipeline
            source_id: The media source ID
            source_type: 'episode' or 'document'
            episode_title: Title for episode (optional)
            recorded_at: Recording timestamp (optional)
        """
        with self.db_service.get_session() as session:
            # 1. Ensure source exists
            # MediaSource might not exist if using old schema - handle gracefully
            try:
                source = (
                    session.query(MediaSource).filter_by(source_id=source_id).first()
                )
            except Exception as e:
                # If MediaSource table doesn't have source_id column, handle gracefully
                logger.warning(f"MediaSource query failed (might be old schema): {e}")
                session.rollback()  # Rollback before trying again
                source = None

            if not source:
                logger.info(f"Creating new source: {source_id}")
                try:
                    source = MediaSource(
                        source_id=source_id,
                        source_type=source_type,
                        title=episode_title or source_id,
                        url=f"local://{source_id}",
                    )
                    session.add(source)
                    session.flush()
                except Exception as e:
                    # If MediaSource model doesn't work, rollback and use raw SQL
                    logger.warning(
                        f"MediaSource model creation failed: {e}, using raw SQL"
                    )
                    session.rollback()  # Rollback before raw SQL
                    from sqlalchemy import text

                    try:
                        session.execute(
                            text(
                                """
                            INSERT OR IGNORE INTO media_sources (source_id, source_type, title, url)
                            VALUES (:source_id, :source_type, :title, :url)
                        """
                            ),
                            {
                                "source_id": source_id,
                                "source_type": source_type,
                                "title": episode_title or source_id,
                                "url": f"local://{source_id}",
                            },
                        )
                        session.commit()
                        # Reload source in new transaction
                        source = (
                            session.query(MediaSource)
                            .filter_by(source_id=source_id)
                            .first()
                        )
                    except Exception as e2:
                        logger.error(
                            f"Failed to create MediaSource even with raw SQL: {e2}"
                        )
                        session.rollback()
                        raise  # Re-raise - cannot proceed without source

            # 2. If episode type, create/update episode
            episode_id = None
            if source_type == "episode":
                episode_id = outputs.episode_id
                episode = (
                    session.query(Episode).filter_by(episode_id=episode_id).first()
                )

                if not episode:
                    logger.info(
                        f"Creating new episode: {episode_id} (source_id={source_id})"
                    )
                    episode = Episode(
                        episode_id=episode_id,
                        source_id=source_id,
                        title=episode_title,
                        recorded_at=recorded_at,
                    )
                    session.add(episode)
                    session.flush()  # Flush to get episode in DB before updating
                else:
                    logger.info(f"Updating existing episode: {episode_id}")

                # Update summaries
                episode.short_summary = outputs.short_summary
                episode.long_summary = outputs.long_summary

                # Calculate input_length from segments stored in database
                # PipelineOutputs doesn't include segments, so we get them from the database
                segments = session.query(Segment).filter_by(episode_id=episode_id).all()
                input_text_length = sum(len(s.text or "") for s in segments)
                episode.input_length = (
                    len(outputs.short_summary or "") + input_text_length
                )
                episode.output_length = len(outputs.long_summary or "")

                if episode.input_length > 0:
                    episode.compression_ratio = (
                        episode.output_length / episode.input_length
                    )

                session.flush()  # Ensure episode updates are flushed
                logger.info(f"Episode {episode_id} updated/created successfully")

            # 3. Store milestones (chapter/section markers with timestamps)
            if hasattr(outputs, "milestones") and outputs.milestones:
                for milestone_data in outputs.milestones:
                    # Check if milestone exists
                    milestone = (
                        session.query(Milestone)
                        .filter_by(
                            episode_id=episode_id,
                            milestone_id=milestone_data.milestone_id,
                        )
                        .first()
                    )

                    if not milestone:
                        milestone = Milestone(
                            episode_id=episode_id,
                            milestone_id=milestone_data.milestone_id,
                            start_time=milestone_data.t0,
                            end_time=milestone_data.t1,
                            summary=milestone_data.summary,
                        )
                        session.add(milestone)
                    else:
                        # Update existing
                        milestone.start_time = milestone_data.t0
                        milestone.end_time = milestone_data.t1
                        milestone.summary = milestone_data.summary

                session.flush()
                logger.info(f"Stored {len(outputs.milestones)} milestones")

            # 4. Store claims (claims are the fundamental unit)
            # Note: FTS indexing moved to after session.commit() to avoid database locks
            for claim_data in outputs.claims:
                # Generate global claim ID
                global_claim_id = f"{source_id}_{claim_data.claim_id}"

                # Check if claim exists
                claim = session.query(Claim).filter_by(claim_id=global_claim_id).first()

                if not claim:
                    claim = Claim(
                        claim_id=global_claim_id,
                        source_id=source_id,
                        episode_id=episode_id,
                    )
                    session.add(claim)

                # Update claim data
                claim.canonical = claim_data.canonical
                claim.original_text = getattr(claim_data, "original_text", None)
                claim.claim_type = claim_data.claim_type
                claim.tier = claim_data.tier

                # Scores (normalized - no JSON)
                if hasattr(claim_data, "scores") and claim_data.scores:
                    claim.importance_score = claim_data.scores.get("importance")
                    claim.specificity_score = claim_data.scores.get("specificity")
                    claim.verifiability_score = claim_data.scores.get("verifiability")

                # Temporality
                claim.temporality_score = getattr(claim_data, "temporality_score", 3)
                claim.temporality_confidence = getattr(
                    claim_data, "temporality_confidence", 0.5
                )
                claim.temporality_rationale = getattr(
                    claim_data, "temporality_rationale", None
                )

                if claim_data.evidence:
                    claim.first_mention_ts = claim_data.evidence[0].t0

                session.flush()

                # 3a. Store evidence spans
                # Delete old evidence for this claim
                session.query(EvidenceSpan).filter_by(claim_id=global_claim_id).delete()

                for seq, evidence in enumerate(claim_data.evidence):
                    # Generate fully qualified segment_id (episode_id + segment_id)
                    # The evidence.segment_id is just "seg_0001", we need to make it match the stored segment
                    fully_qualified_segment_id = None
                    if evidence.segment_id and episode_id:
                        fully_qualified_segment_id = f"{episode_id}_{evidence.segment_id}"
                    
                    evidence_span = EvidenceSpan(
                        claim_id=global_claim_id,
                        segment_id=fully_qualified_segment_id,
                        sequence=seq,
                        start_time=evidence.t0,
                        end_time=evidence.t1,
                        quote=evidence.quote,
                        context_start_time=evidence.context_t0,
                        context_end_time=evidence.context_t1,
                        context_text=evidence.context_text,
                        context_type=evidence.context_type,
                    )
                    session.add(evidence_span)

                session.flush()

                # Store claim categories (normalized - no JSON)
                if (
                    hasattr(claim_data, "structured_categories")
                    and claim_data.structured_categories
                ):
                    # Delete old categories
                    session.query(ClaimCategory).filter_by(
                        claim_id=global_claim_id
                    ).delete()

                    # Store new categories
                    for i, cat in enumerate(claim_data.structured_categories):
                        # Extract WikiData ID
                        wikidata_id = cat.get("wikidata_qid") or cat.get("wikidata_id")
                        relevance = cat.get("relevance_score") or cat.get(
                            "coverage_confidence", 0.5
                        )

                        if wikidata_id:
                            # Verify WikiData category exists
                            wikidata_cat = (
                                session.query(WikiDataCategory)
                                .filter_by(wikidata_id=wikidata_id)
                                .first()
                            )

                            if wikidata_cat:
                                claim_category = ClaimCategory(
                                    claim_id=global_claim_id,
                                    wikidata_id=wikidata_id,
                                    relevance_score=relevance,
                                    confidence=0.8,  # Default confidence
                                    is_primary=(i == 0),  # First one is primary
                                    source="system",
                                )
                                session.add(claim_category)
                            else:
                                logger.warning(
                                    f"WikiData category not found: {wikidata_id}"
                                )

            # 6. Store claim relations
            for relation in outputs.relations:
                # Generate global claim IDs
                source_global_id = f"{source_id}_{relation.source_claim_id}"
                target_global_id = f"{source_id}_{relation.target_claim_id}"

                # Check if relation already exists
                existing = (
                    session.query(ClaimRelation)
                    .filter_by(
                        source_claim_id=source_global_id,
                        target_claim_id=target_global_id,
                        relation_type=relation.type,
                    )
                    .first()
                )

                if not existing:
                    claim_relation = ClaimRelation(
                        source_claim_id=source_global_id,
                        target_claim_id=target_global_id,
                        relation_type=relation.type,
                        strength=relation.strength,
                        rationale=relation.rationale,
                    )
                    session.add(claim_relation)
                else:
                    # Update existing
                    existing.strength = relation.strength
                    existing.rationale = relation.rationale

            # 7. Store people (normalized - no JSON for external_ids)
            # Group person mentions by normalized name to track all mentions
            person_mentions_by_name = {}
            for person_data in outputs.people:
                person_name = person_data.normalized or person_data.surface
                if person_name not in person_mentions_by_name:
                    person_mentions_by_name[person_name] = []
                person_mentions_by_name[person_name].append(person_data)

            for person_name, mentions in person_mentions_by_name.items():
                # Create/get person (using first mention for metadata)
                first_mention = mentions[0]
                person = session.query(Person).filter_by(name=person_name).first()

                if not person:
                    person_id = f"person_{person_name.replace(' ', '_').lower()}"
                    person = Person(
                        person_id=person_id,
                        name=person_name,
                        normalized_name=first_mention.normalized,
                        entity_type=first_mention.entity_type or "person",
                        confidence=first_mention.confidence,
                    )
                    session.add(person)
                    session.flush()

                # Link person to claims (many-to-many)
                for claim_data in outputs.claims:
                    global_claim_id = f"{source_id}_{claim_data.claim_id}"

                    # Check if person is mentioned in this claim's canonical text
                    if person_name.lower() in claim_data.canonical.lower():
                        claim_person = (
                            session.query(ClaimPerson)
                            .filter_by(
                                claim_id=global_claim_id,
                                person_id=person.person_id,
                            )
                            .first()
                        )

                        if not claim_person:
                            claim_person = ClaimPerson(
                                claim_id=global_claim_id,
                                person_id=person.person_id,
                                first_mention_ts=first_mention.t0,
                                mention_context=first_mention.surface,
                            )
                            session.add(claim_person)

                # Store ALL mentions with timestamps (not just first)
                # Delete old evidence for this person
                session.query(PersonEvidence).filter_by(
                    person_id=person.person_id
                ).delete()

                for seq, mention in enumerate(mentions):
                    # Link to the claim that contains this mention
                    for claim_data in outputs.claims:
                        global_claim_id = f"{source_id}_{claim_data.claim_id}"
                        # Check if this mention's segment matches any claim evidence
                        if mention.span_segment_id and any(
                            e.segment_id == mention.span_segment_id
                            for e in claim_data.evidence
                        ):
                            person_evidence = PersonEvidence(
                                person_id=person.person_id,
                                claim_id=global_claim_id,
                                sequence=seq,
                                start_time=mention.t0,
                                end_time=mention.t1,
                                quote=mention.surface,  # How they were mentioned
                                surface_form=mention.surface,
                                segment_id=mention.span_segment_id,
                                # No extended context for person mentions in current schema
                                context_type="exact",
                            )
                            session.add(person_evidence)
                            break  # Found the claim, move to next mention

                # Store external IDs (normalized)
                if (
                    hasattr(first_mention, "external_ids")
                    and first_mention.external_ids
                ):
                    for system, ext_id in first_mention.external_ids.items():
                        existing_ext = (
                            session.query(PersonExternalId)
                            .filter_by(
                                person_id=person.person_id,
                                external_system=system,
                            )
                            .first()
                        )

                        if not existing_ext:
                            external_id = PersonExternalId(
                                person_id=person.person_id,
                                external_system=system,
                                external_id=ext_id,
                            )
                            session.add(external_id)

            # 8. Store concepts (normalized - no JSON for aliases)
            for concept_data in outputs.concepts:
                # Create/get concept
                concept = (
                    session.query(Concept).filter_by(name=concept_data.name).first()
                )

                if not concept:
                    concept_id = (
                        f"concept_{concept_data.name.replace(' ', '_').lower()}"
                    )
                    concept = Concept(
                        concept_id=concept_id,
                        name=concept_data.name,
                        description=getattr(concept_data, "description", None),
                        definition=concept_data.definition,
                    )
                    session.add(concept)
                    session.flush()

                # Link concept to claims
                for claim_data in outputs.claims:
                    global_claim_id = f"{source_id}_{claim_data.claim_id}"

                    # Check if concept is mentioned in this claim
                    if concept_data.name.lower() in claim_data.canonical.lower():
                        claim_concept = (
                            session.query(ClaimConcept)
                            .filter_by(
                                claim_id=global_claim_id,
                                concept_id=concept.concept_id,
                            )
                            .first()
                        )

                        if not claim_concept:
                            claim_concept = ClaimConcept(
                                claim_id=global_claim_id,
                                concept_id=concept.concept_id,
                                first_mention_ts=concept_data.first_mention_ts,
                            )
                            session.add(claim_concept)

                # Store ALL evidence spans (not just first mention)
                if (
                    hasattr(concept_data, "evidence_spans")
                    and concept_data.evidence_spans
                ):
                    # Delete old evidence for this concept
                    session.query(ConceptEvidence).filter_by(
                        concept_id=concept.concept_id
                    ).delete()

                    for seq, evidence in enumerate(concept_data.evidence_spans):
                        # Link to the claim that contains this evidence
                        for claim_data in outputs.claims:
                            global_claim_id = f"{source_id}_{claim_data.claim_id}"
                            # Check if this evidence belongs to this claim (by segment or text match)
                            if evidence.segment_id and any(
                                e.segment_id == evidence.segment_id
                                for e in claim_data.evidence
                            ):
                                concept_evidence = ConceptEvidence(
                                    concept_id=concept.concept_id,
                                    claim_id=global_claim_id,
                                    sequence=seq,
                                    start_time=evidence.t0,
                                    end_time=evidence.t1,
                                    quote=evidence.quote,
                                    segment_id=evidence.segment_id,
                                    context_start_time=evidence.context_t0,
                                    context_end_time=evidence.context_t1,
                                    context_text=evidence.context_text,
                                    context_type=evidence.context_type,
                                )
                                session.add(concept_evidence)
                                break  # Found the claim, move to next evidence

                # Store aliases (normalized)
                if hasattr(concept_data, "aliases") and concept_data.aliases:
                    for alias in concept_data.aliases:
                        existing_alias = (
                            session.query(ConceptAlias)
                            .filter_by(
                                concept_id=concept.concept_id,
                                alias=alias,
                            )
                            .first()
                        )

                        if not existing_alias:
                            concept_alias = ConceptAlias(
                                concept_id=concept.concept_id,
                                alias=alias,
                            )
                            session.add(concept_alias)

            # 9. Store jargon (normalized)
            for jargon_data in outputs.jargon:
                # Create/get jargon term
                jargon = (
                    session.query(JargonTerm).filter_by(term=jargon_data.term).first()
                )

                if not jargon:
                    jargon_id = f"jargon_{jargon_data.term.replace(' ', '_').lower()}"
                    jargon = JargonTerm(
                        jargon_id=jargon_id,
                        term=jargon_data.term,
                        definition=jargon_data.definition,
                        domain=jargon_data.category,
                    )
                    session.add(jargon)
                    session.flush()

                # Link jargon to claims
                for claim_data in outputs.claims:
                    global_claim_id = f"{source_id}_{claim_data.claim_id}"

                    # Check if jargon is used in this claim
                    if jargon_data.term.lower() in claim_data.canonical.lower():
                        claim_jargon = (
                            session.query(ClaimJargon)
                            .filter_by(
                                claim_id=global_claim_id,
                                jargon_id=jargon.jargon_id,
                            )
                            .first()
                        )

                        if not claim_jargon:
                            claim_jargon = ClaimJargon(
                                claim_id=global_claim_id,
                                jargon_id=jargon.jargon_id,
                                first_mention_ts=jargon_data.evidence_spans[0].t0
                                if jargon_data.evidence_spans
                                else None,
                            )
                            session.add(claim_jargon)

                # Store ALL evidence spans (not just first mention)
                if (
                    hasattr(jargon_data, "evidence_spans")
                    and jargon_data.evidence_spans
                ):
                    # Delete old evidence for this jargon
                    session.query(JargonEvidence).filter_by(
                        jargon_id=jargon.jargon_id
                    ).delete()

                    for seq, evidence in enumerate(jargon_data.evidence_spans):
                        # Link to the claim that contains this evidence
                        for claim_data in outputs.claims:
                            global_claim_id = f"{source_id}_{claim_data.claim_id}"
                            # Check if this evidence belongs to this claim (by segment or text match)
                            if evidence.segment_id and any(
                                e.segment_id == evidence.segment_id
                                for e in claim_data.evidence
                            ):
                                jargon_evidence = JargonEvidence(
                                    jargon_id=jargon.jargon_id,
                                    claim_id=global_claim_id,
                                    sequence=seq,
                                    start_time=evidence.t0,
                                    end_time=evidence.t1,
                                    quote=evidence.quote,
                                    segment_id=evidence.segment_id,
                                    context_start_time=evidence.context_t0,
                                    context_end_time=evidence.context_t1,
                                    context_text=evidence.context_text,
                                    context_type=evidence.context_type,
                                )
                                session.add(jargon_evidence)
                                break  # Found the claim, move to next evidence

            # 10. NOTE: We do NOT store source-level WikiData categories
            # Sources are categorized by:
            # - Platform categories (from YouTube/RSS) - handled separately
            # - Aggregated claim categories (computed via JOIN)

            # Platform categories would be stored elsewhere when processing YouTube/RSS metadata
            # For now, structured_categories from the pipeline are used for claim categorization only

            session.commit()

            # Calculate total evidence spans stored
            total_claim_evidence = sum(len(c.evidence) for c in outputs.claims)
            total_concept_evidence = sum(
                len(c.evidence_spans)
                for c in outputs.concepts
                if hasattr(c, "evidence_spans")
            )
            total_jargon_evidence = sum(
                len(j.evidence_spans)
                for j in outputs.jargon
                if hasattr(j, "evidence_spans")
            )
            total_people_mentions = len(outputs.people)

            logger.info(
                f"✅ Stored {len(outputs.claims)} claims ({total_claim_evidence} evidence spans), "
                f"{len(outputs.relations)} relations, "
                f"{len(person_mentions_by_name)} people ({total_people_mentions} mentions), "
                f"{len(outputs.concepts)} concepts ({total_concept_evidence} evidence spans), "
                f"{len(outputs.jargon)} jargon terms ({total_jargon_evidence} evidence spans)"
            )

        # FTS indexing AFTER session commit to avoid database locks
        # This runs outside the SQLAlchemy session context
        self._update_fts_indexes(source_id, episode_id, outputs)

    def get_claim(self, claim_id: str, with_context: bool = True) -> dict | None:
        """
        Get a claim with optional source context.

        Args:
            claim_id: Global claim ID
            with_context: Include source metadata

        Returns:
            Claim data with context
        """
        with self.db_service.get_session() as session:
            claim = session.query(Claim).filter_by(claim_id=claim_id).first()

            if not claim:
                return None

            result = {
                "claim_id": claim.claim_id,
                "canonical": claim.canonical,
                "claim_type": claim.claim_type,
                "tier": claim.tier,
                "importance_score": claim.importance_score,
                "verification_status": claim.verification_status,
            }

            if with_context and claim.source:
                result["source"] = {
                    "source_id": claim.source.source_id,
                    "title": claim.source.title,
                    "uploader": claim.source.uploader,
                    "upload_date": claim.source.upload_date,
                    "source_type": claim.source.source_type,
                }

            return result

    def get_claims_by_category(
        self,
        wikidata_id: str,
        tier_filter: list[str] | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """
        Get claims by WikiData category.

        Args:
            wikidata_id: WikiData category ID
            tier_filter: Filter by tiers (e.g., ['A', 'B'])
            limit: Maximum number of claims

        Returns:
            List of claims with source context
        """
        with self.db_service.get_session() as session:
            query = (
                session.query(Claim)
                .join(ClaimCategory, Claim.claim_id == ClaimCategory.claim_id)
                .filter(ClaimCategory.wikidata_id == wikidata_id)
                .filter(ClaimCategory.is_primary == True)
            )

            if tier_filter:
                query = query.filter(Claim.tier.in_(tier_filter))

            query = query.limit(limit)

            results = []
            for claim in query.all():
                results.append(
                    {
                        "claim_id": claim.claim_id,
                        "canonical": claim.canonical,
                        "tier": claim.tier,
                        "source_title": claim.source.title if claim.source else None,
                        "source_author": claim.source.uploader
                        if claim.source
                        else None,
                    }
                )

            return results

    def get_claims_by_source(
        self,
        source_id: str,
        include_evidence: bool = False,
    ) -> list[dict]:
        """
        Get all claims attributed to a source.

        Args:
            source_id: Source ID
            include_evidence: Include evidence spans

        Returns:
            List of claims
        """
        with self.db_service.get_session() as session:
            claims = session.query(Claim).filter_by(source_id=source_id).all()

            results = []
            for claim in claims:
                claim_dict = {
                    "claim_id": claim.claim_id,
                    "canonical": claim.canonical,
                    "tier": claim.tier,
                    "claim_type": claim.claim_type,
                }

                if include_evidence:
                    claim_dict["evidence"] = [
                        {
                            "quote": ev.quote,
                            "start_time": ev.start_time,
                            "end_time": ev.end_time,
                        }
                        for ev in claim.evidence_spans
                    ]

                results.append(claim_dict)

            return results

    def _update_fts_indexes(
        self, source_id: str, episode_id: str | None, outputs: PipelineOutputs
    ) -> None:
        """
        Update FTS indexes after main data is committed.

        This runs in a separate connection AFTER session.commit() to avoid database locks.

        Args:
            source_id: The media source ID
            episode_id: The episode ID (if applicable)
            outputs: Pipeline outputs with claims and evidence
        """
        import time

        max_retries = 3
        retry_delay = 0.1  # Start with 100ms

        # Step 1: Clear old FTS entries
        for attempt in range(max_retries):
            conn = self.db_service.engine.raw_connection()
            try:
                cur = conn.cursor()
                # Wait up to 5s if the database is busy
                cur.execute("PRAGMA busy_timeout=5000")

                # Check if FTS tables exist
                cur.execute(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name IN ('claims_fts','evidence_fts')
                    """
                )
                existing_tables = {row[0] for row in cur.fetchall()}

                # Clear old FTS entries for this episode
                # Note: FTS tables only have episode_id, not source_id
                if episode_id and existing_tables:
                    if "claims_fts" in existing_tables:
                        cur.execute(
                            "DELETE FROM claims_fts WHERE episode_id = ?",
                            (episode_id,),
                        )
                    if "evidence_fts" in existing_tables:
                        cur.execute(
                            "DELETE FROM evidence_fts WHERE episode_id = ?",
                            (episode_id,),
                        )

                conn.commit()
                logger.debug(f"FTS cleanup completed for episode {episode_id}")
                break  # Success, exit retry loop

            except Exception as e:
                conn.rollback()
                if attempt < max_retries - 1:
                    logger.debug(
                        f"FTS cleanup attempt {attempt + 1} failed, retrying in {retry_delay}s: {e}"
                    )
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.warning(
                        f"FTS cleanup failed after {max_retries} attempts: {e}"
                    )
                    return  # Skip indexing if cleanup failed
            finally:
                conn.close()

        # Step 2: Index all claims and evidence
        for attempt in range(max_retries):
            conn = self.db_service.engine.raw_connection()
            try:
                cur = conn.cursor()
                cur.execute("PRAGMA busy_timeout=5000")

                # Check if FTS tables exist
                cur.execute(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name IN ('claims_fts','evidence_fts')
                    """
                )
                existing_tables = {row[0] for row in cur.fetchall()}

                if not existing_tables:
                    logger.debug("No FTS tables found, skipping indexing")
                    return

                # Index all claims
                claims_indexed = 0
                evidence_indexed = 0

                for claim_data in outputs.claims:
                    global_claim_id = f"{source_id}_{claim_data.claim_id}"

                    # Index claim text
                    if "claims_fts" in existing_tables:
                        cur.execute(
                            """
                            INSERT INTO claims_fts(
                                claim_id, episode_id, canonical, claim_type
                            ) VALUES(?, ?, ?, ?)
                            """,
                            (
                                global_claim_id,
                                episode_id,
                                claim_data.canonical,
                                claim_data.claim_type,
                            ),
                        )
                        claims_indexed += 1

                    # Index evidence quotes
                    if "evidence_fts" in existing_tables:
                        for evidence in claim_data.evidence:
                            if evidence.quote:
                                cur.execute(
                                    """
                                    INSERT INTO evidence_fts(
                                        claim_id, episode_id, quote
                                    ) VALUES(?, ?, ?)
                                    """,
                                    (
                                        global_claim_id,
                                        episode_id,
                                        evidence.quote,
                                    ),
                                )
                                evidence_indexed += 1

                conn.commit()
                logger.debug(
                    f"FTS indexing completed: {claims_indexed} claims, {evidence_indexed} evidence spans"
                )
                break  # Success, exit retry loop

            except Exception as e:
                conn.rollback()
                if attempt < max_retries - 1:
                    logger.debug(
                        f"FTS indexing attempt {attempt + 1} failed, retrying in {retry_delay}s: {e}"
                    )
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.warning(
                        f"FTS indexing failed after {max_retries} attempts: {e}"
                    )
            finally:
                conn.close()
