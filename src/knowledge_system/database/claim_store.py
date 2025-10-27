"""
Claim-Centric HCE storage for the main application database.

Stores HCE pipeline outputs using a claim-first architecture where claims are
the fundamental unit and sources provide attribution metadata.
"""

from __future__ import annotations

import logging
from typing import Any

from ..processors.hce.types import PipelineOutputs
from .service import DatabaseService
from .claim_models import (
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
    Episode,
    EvidenceSpan,
    JargonTerm,
    MediaSource,
    Person,
    PersonExternalId,
    Segment,
    WikiDataCategory,
)

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
    
    def upsert_pipeline_outputs(
        self,
        outputs: PipelineOutputs,
        source_id: str,
        source_type: str = 'episode',
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
            source = session.query(MediaSource).filter_by(source_id=source_id).first()
            if not source:
                logger.info(f"Creating new source: {source_id}")
                source = MediaSource(
                    source_id=source_id,
                    source_type=source_type,
                    title=episode_title or source_id,
                    url=f"local://{source_id}",
                )
                session.add(source)
                session.flush()
            
            # 2. If episode type, create/update episode
            episode_id = None
            if source_type == 'episode':
                episode_id = outputs.episode_id
                episode = session.query(Episode).filter_by(episode_id=episode_id).first()
                
                if not episode:
                    episode = Episode(
                        episode_id=episode_id,
                        source_id=source_id,
                        title=episode_title,
                        recorded_at=recorded_at,
                    )
                    session.add(episode)
                
                # Update summaries
                episode.short_summary = outputs.short_summary
                episode.long_summary = outputs.long_summary
                episode.input_length = len(outputs.short_summary or "") + sum(len(s.text) for s in outputs.episode.segments if hasattr(outputs, 'episode'))
                episode.output_length = len(outputs.long_summary or "")
                
                if episode.input_length > 0:
                    episode.compression_ratio = episode.output_length / episode.input_length
                
                session.flush()
            
            # 3. Store claims (claims are the fundamental unit)
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
                claim.original_text = getattr(claim_data, 'original_text', None)
                claim.claim_type = claim_data.claim_type
                claim.tier = claim_data.tier
                
                # Scores (normalized - no JSON)
                if hasattr(claim_data, 'scores') and claim_data.scores:
                    claim.importance_score = claim_data.scores.get('importance')
                    claim.specificity_score = claim_data.scores.get('specificity')
                    claim.verifiability_score = claim_data.scores.get('verifiability')
                
                # Temporality
                claim.temporality_score = getattr(claim_data, 'temporality_score', 3)
                claim.temporality_confidence = getattr(claim_data, 'temporality_confidence', 0.5)
                claim.temporality_rationale = getattr(claim_data, 'temporality_rationale', None)
                
                if claim_data.evidence:
                    claim.first_mention_ts = claim_data.evidence[0].t0
                
                session.flush()
                
                # 3a. Store evidence spans
                # Delete old evidence for this claim
                session.query(EvidenceSpan).filter_by(claim_id=global_claim_id).delete()
                
                for seq, evidence in enumerate(claim_data.evidence):
                    evidence_span = EvidenceSpan(
                        claim_id=global_claim_id,
                        segment_id=evidence.segment_id,
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
                
                # 3b. Store claim categories (normalized - no JSON)
                if hasattr(claim_data, 'structured_categories') and claim_data.structured_categories:
                    # Delete old categories
                    session.query(ClaimCategory).filter_by(claim_id=global_claim_id).delete()
                    
                    # Store new categories
                    for i, cat in enumerate(claim_data.structured_categories):
                        # Extract WikiData ID
                        wikidata_id = cat.get('wikidata_qid') or cat.get('wikidata_id')
                        relevance = cat.get('relevance_score') or cat.get('coverage_confidence', 0.5)
                        
                        if wikidata_id:
                            # Verify WikiData category exists
                            wikidata_cat = session.query(WikiDataCategory).filter_by(
                                wikidata_id=wikidata_id
                            ).first()
                            
                            if wikidata_cat:
                                claim_category = ClaimCategory(
                                    claim_id=global_claim_id,
                                    wikidata_id=wikidata_id,
                                    relevance_score=relevance,
                                    confidence=0.8,  # Default confidence
                                    is_primary=(i == 0),  # First one is primary
                                    source='system',
                                )
                                session.add(claim_category)
                            else:
                                logger.warning(f"WikiData category not found: {wikidata_id}")
            
            # 4. Store claim relations
            for relation in outputs.relations:
                # Generate global claim IDs
                source_global_id = f"{source_id}_{relation.source_claim_id}"
                target_global_id = f"{source_id}_{relation.target_claim_id}"
                
                # Check if relation already exists
                existing = session.query(ClaimRelation).filter_by(
                    source_claim_id=source_global_id,
                    target_claim_id=target_global_id,
                    relation_type=relation.type,
                ).first()
                
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
            
            # 5. Store people (normalized - no JSON for external_ids)
            for person_data in outputs.people:
                # Create/get person
                person_name = person_data.normalized or person_data.surface
                person = session.query(Person).filter_by(name=person_name).first()
                
                if not person:
                    person_id = f"person_{person_name.replace(' ', '_').lower()}"
                    person = Person(
                        person_id=person_id,
                        name=person_name,
                        normalized_name=person_data.normalized,
                        entity_type=person_data.entity_type or 'person',
                        confidence=person_data.confidence,
                    )
                    session.add(person)
                    session.flush()
                
                # Link person to claims (many-to-many)
                # We need to determine which claims mention this person
                # For now, link to all claims in this source (can be refined later)
                for claim_data in outputs.claims:
                    global_claim_id = f"{source_id}_{claim_data.claim_id}"
                    
                    # Check if person is mentioned in this claim's canonical text
                    if person_name.lower() in claim_data.canonical.lower():
                        claim_person = session.query(ClaimPerson).filter_by(
                            claim_id=global_claim_id,
                            person_id=person.person_id,
                        ).first()
                        
                        if not claim_person:
                            claim_person = ClaimPerson(
                                claim_id=global_claim_id,
                                person_id=person.person_id,
                                first_mention_ts=person_data.t0,
                                mention_context=person_data.surface,
                            )
                            session.add(claim_person)
                
                # Store external IDs (normalized)
                if hasattr(person_data, 'external_ids') and person_data.external_ids:
                    for system, ext_id in person_data.external_ids.items():
                        existing_ext = session.query(PersonExternalId).filter_by(
                            person_id=person.person_id,
                            external_system=system,
                        ).first()
                        
                        if not existing_ext:
                            external_id = PersonExternalId(
                                person_id=person.person_id,
                                external_system=system,
                                external_id=ext_id,
                            )
                            session.add(external_id)
            
            # 6. Store concepts (normalized - no JSON for aliases)
            for concept_data in outputs.concepts:
                # Create/get concept
                concept = session.query(Concept).filter_by(name=concept_data.name).first()
                
                if not concept:
                    concept_id = f"concept_{concept_data.name.replace(' ', '_').lower()}"
                    concept = Concept(
                        concept_id=concept_id,
                        name=concept_data.name,
                        description=getattr(concept_data, 'description', None),
                        definition=concept_data.definition,
                    )
                    session.add(concept)
                    session.flush()
                
                # Link concept to claims
                for claim_data in outputs.claims:
                    global_claim_id = f"{source_id}_{claim_data.claim_id}"
                    
                    # Check if concept is mentioned in this claim
                    if concept_data.name.lower() in claim_data.canonical.lower():
                        claim_concept = session.query(ClaimConcept).filter_by(
                            claim_id=global_claim_id,
                            concept_id=concept.concept_id,
                        ).first()
                        
                        if not claim_concept:
                            claim_concept = ClaimConcept(
                                claim_id=global_claim_id,
                                concept_id=concept.concept_id,
                                first_mention_ts=concept_data.first_mention_ts,
                            )
                            session.add(claim_concept)
                
                # Store aliases (normalized)
                if hasattr(concept_data, 'aliases') and concept_data.aliases:
                    for alias in concept_data.aliases:
                        existing_alias = session.query(ConceptAlias).filter_by(
                            concept_id=concept.concept_id,
                            alias=alias,
                        ).first()
                        
                        if not existing_alias:
                            concept_alias = ConceptAlias(
                                concept_id=concept.concept_id,
                                alias=alias,
                            )
                            session.add(concept_alias)
            
            # 7. Store jargon (normalized)
            for jargon_data in outputs.jargon:
                # Create/get jargon term
                jargon = session.query(JargonTerm).filter_by(term=jargon_data.term).first()
                
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
                        claim_jargon = session.query(ClaimJargon).filter_by(
                            claim_id=global_claim_id,
                            jargon_id=jargon.jargon_id,
                        ).first()
                        
                        if not claim_jargon:
                            claim_jargon = ClaimJargon(
                                claim_id=global_claim_id,
                                jargon_id=jargon.jargon_id,
                                first_mention_ts=jargon_data.evidence_spans[0].t0 if jargon_data.evidence_spans else None,
                            )
                            session.add(claim_jargon)
            
            # 8. NOTE: We do NOT store source-level WikiData categories
            # Sources are categorized by:
            # - Platform categories (from YouTube/RSS) - handled separately
            # - Aggregated claim categories (computed via JOIN)
            
            # Platform categories would be stored elsewhere when processing YouTube/RSS metadata
            # For now, structured_categories from the pipeline are used for claim categorization only
            
            session.commit()
            
            logger.info(
                f"✅ Stored {len(outputs.claims)} claims with evidence, "
                f"{len(outputs.relations)} relations, "
                f"{len(outputs.people)} people, "
                f"{len(outputs.concepts)} concepts, "
                f"{len(outputs.jargon)} jargon terms"
            )
    
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
                'claim_id': claim.claim_id,
                'canonical': claim.canonical,
                'claim_type': claim.claim_type,
                'tier': claim.tier,
                'importance_score': claim.importance_score,
                'verification_status': claim.verification_status,
            }
            
            if with_context and claim.source:
                result['source'] = {
                    'source_id': claim.source.source_id,
                    'title': claim.source.title,
                    'uploader': claim.source.uploader,
                    'upload_date': claim.source.upload_date,
                    'source_type': claim.source.source_type,
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
                results.append({
                    'claim_id': claim.claim_id,
                    'canonical': claim.canonical,
                    'tier': claim.tier,
                    'source_title': claim.source.title if claim.source else None,
                    'source_author': claim.source.uploader if claim.source else None,
                })
            
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
                    'claim_id': claim.claim_id,
                    'canonical': claim.canonical,
                    'tier': claim.tier,
                    'claim_type': claim.claim_type,
                }
                
                if include_evidence:
                    claim_dict['evidence'] = [
                        {
                            'quote': ev.quote,
                            'start_time': ev.start_time,
                            'end_time': ev.end_time,
                        }
                        for ev in claim.evidence_spans
                    ]
                
                results.append(claim_dict)
            
            return results

