"""
Database operations for HCE (Hybrid Claim Extraction) data using existing tables.

This module provides functions to store and retrieve mining results using the
existing Episode, Claim, Jargon, Person, and Concept tables.
"""

import logging
import uuid
from typing import Any

from .hce_models import Claim, Concept, Episode, Jargon, Person
from .service import DatabaseService

logger = logging.getLogger(__name__)


def store_mining_results(
    db_service: DatabaseService, episode_id: str, miner_outputs: list[Any]
) -> None:
    """
    Store mining results in existing HCE tables.

    Args:
        db_service: Database service instance
        episode_id: Episode identifier
        miner_outputs: List of UnifiedMinerOutput objects
    """
    with db_service.get_session() as session:
        # Ensure episode exists
        episode = session.query(Episode).filter_by(episode_id=episode_id).first()
        if not episode:
            # Extract video_id from episode_id
            video_id = episode_id.replace("episode_", "")

            # Ensure media source exists (required for foreign key)
            from .models import MediaSource

            media_source = (
                session.query(MediaSource).filter_by(media_id=video_id).first()
            )
            if not media_source:
                # Create a minimal media source entry
                media_source = MediaSource(
                    media_id=video_id,
                    source_type="youtube",  # Default assumption
                    title=f"Media {video_id}",
                    url=f"https://youtube.com/watch?v={video_id}",  # Required field
                )
                session.add(media_source)
                session.flush()  # Ensure it's created before episode
                logger.info(f"Created media source: {video_id}")

            episode = Episode(
                episode_id=episode_id,
                video_id=video_id,
                title=f"Episode {episode_id}",
                description=f"Auto-generated episode for {episode_id}",
            )
            session.add(episode)
            logger.info(f"Created new episode: {episode_id}")

        # Store results from each miner output
        for output in miner_outputs:
            # Store claims
            for claim_data in output.claims:
                # Generate claim_id if not present
                claim_id = (
                    claim_data.get("claim_id")
                    or claim_data.get("candidate_id")
                    or f"claim_{uuid.uuid4().hex[:8]}"
                )

                # Check if claim already exists
                existing_claim = (
                    session.query(Claim)
                    .filter_by(episode_id=episode_id, claim_id=claim_id)
                    .first()
                )

                if not existing_claim:
                    # Get timestamp directly from claim data (flat schema)
                    # Fallback: try evidence_spans[0].t0 for backward compatibility
                    first_ts = claim_data.get("timestamp")
                    if not first_ts:
                        evidence_spans = claim_data.get("evidence_spans", [])
                        first_ts = (
                            evidence_spans[0].get("t0") if evidence_spans else None
                        )

                    claim = Claim(
                        episode_id=episode_id,
                        claim_id=claim_id,
                        canonical=claim_data.get("claim_text", ""),
                        original_text=claim_data.get("claim_text", ""),
                        claim_type=claim_data.get("claim_type", "factual"),
                        tier="C",  # Default tier, will be updated by flagship
                        first_mention_ts=first_ts,
                        scores_json=claim_data.get("scores", {}),
                    )
                    session.add(claim)

            # Store jargon
            for jargon_data in output.jargon:
                term_id = jargon_data.get("term_id") or f"jargon_{uuid.uuid4().hex[:8]}"

                existing_jargon = (
                    session.query(Jargon)
                    .filter_by(episode_id=episode_id, term_id=term_id)
                    .first()
                )

                if not existing_jargon:
                    jargon = Jargon(
                        episode_id=episode_id,
                        term_id=term_id,
                        term=jargon_data.get("term", ""),
                        definition=jargon_data.get("definition", ""),
                        category=jargon_data.get("category", "general"),
                        first_mention_ts=jargon_data.get("timestamp"),
                        context_quote=jargon_data.get("context_quote"),
                    )
                    session.add(jargon)

            # Store people
            for person_data in output.people:
                person_id = (
                    person_data.get("person_id")
                    or person_data.get("mention_id")
                    or f"person_{uuid.uuid4().hex[:8]}"
                )

                existing_person = (
                    session.query(Person)
                    .filter_by(episode_id=episode_id, person_id=person_id)
                    .first()
                )

                if not existing_person:
                    person = Person(
                        episode_id=episode_id,
                        person_id=person_id,
                        name=person_data.get("name", ""),
                        description=person_data.get("role_or_description", ""),
                        first_mention_ts=person_data.get("timestamp"),
                        context_quote=person_data.get("context_quote"),
                    )
                    session.add(person)

            # Store mental models (concepts)
            for model_data in output.mental_models:
                model_id = (
                    model_data.get("model_id")
                    or model_data.get("concept_id")
                    or f"concept_{uuid.uuid4().hex[:8]}"
                )

                existing_concept = (
                    session.query(Concept)
                    .filter_by(episode_id=episode_id, concept_id=model_id)
                    .first()
                )

                if not existing_concept:
                    concept = Concept(
                        episode_id=episode_id,
                        concept_id=model_id,
                        name=model_data.get("name", ""),
                        description=model_data.get("description", ""),
                        first_mention_ts=model_data.get("timestamp"),
                        context_quote=model_data.get("context_quote"),
                    )
                    session.add(concept)

        session.commit()
        logger.info(f"Stored mining results for episode {episode_id}")


def load_mining_results(db_service: DatabaseService, episode_id: str) -> list[Any]:
    """
    Load mining results from existing HCE tables.

    Args:
        db_service: Database service instance
        episode_id: Episode identifier

    Returns:
        List of miner output-like objects with claims, jargon, people, mental_models
    """
    from ..processors.hce.unified_miner import UnifiedMinerOutput

    with db_service.get_session() as session:
        # Load all data for this episode
        claims = session.query(Claim).filter_by(episode_id=episode_id).all()
        jargon = session.query(Jargon).filter_by(episode_id=episode_id).all()
        people = session.query(Person).filter_by(episode_id=episode_id).all()
        concepts = session.query(Concept).filter_by(episode_id=episode_id).all()

        # Convert to UnifiedMinerOutput format
        output = UnifiedMinerOutput(
            {
                "claims": [
                    {
                        "claim_id": c.claim_id,
                        "claim_text": c.canonical,
                        "text": c.canonical,
                        "original_text": c.original_text,
                        "claim_type": c.claim_type,
                        "tier": c.tier,
                        "timestamp": c.first_mention_ts,
                        "t0": c.first_mention_ts,
                        "scores": c.scores_json or {},
                    }
                    for c in claims
                ],
                "jargon": [
                    {
                        "term_id": j.term_id,
                        "term": j.term,
                        "definition": j.definition,
                        "category": j.category,
                        "timestamp": j.first_mention_ts,
                        "t0": j.first_mention_ts,
                    }
                    for j in jargon
                ],
                "people": [
                    {
                        "person_id": p.person_id,
                        "mention_id": p.person_id,
                        "name": p.name,
                        "surface": p.name,
                        "normalized": p.description,
                        "description": p.description,
                        "timestamp": p.first_mention_ts,
                        "t0": p.first_mention_ts,
                    }
                    for p in people
                ],
                "mental_models": [
                    {
                        "concept_id": c.concept_id,
                        "model_id": c.concept_id,
                        "name": c.name,
                        "definition": c.description,
                        "timestamp": c.first_mention_ts,
                        "t0": c.first_mention_ts,
                    }
                    for c in concepts
                ],
            }
        )

        logger.info(
            f"Loaded mining results for episode {episode_id}: "
            f"{len(claims)} claims, {len(jargon)} jargon, "
            f"{len(people)} people, {len(concepts)} concepts"
        )

        return [output]


def store_transcript(
    db_service: DatabaseService, episode_id: str, transcript_path: str
) -> None:
    """
    Store transcript reference in episode metadata.

    Args:
        db_service: Database service instance
        episode_id: Episode identifier
        transcript_path: Path to transcript file
    """
    with db_service.get_session() as session:
        episode = session.query(Episode).filter_by(episode_id=episode_id).first()

        if not episode:
            # Create episode if it doesn't exist
            video_id = episode_id.replace("episode_", "")

            # Ensure media source exists (required for foreign key)
            from .models import MediaSource

            media_source = (
                session.query(MediaSource).filter_by(media_id=video_id).first()
            )
            if not media_source:
                # Create a minimal media source entry
                media_source = MediaSource(
                    media_id=video_id,
                    source_type="youtube",  # Default assumption
                    title=f"Media {video_id}",
                    url=f"https://youtube.com/watch?v={video_id}",  # Required field
                )
                session.add(media_source)
                session.flush()  # Ensure it's created before episode
                logger.info(f"Created media source: {video_id}")

            episode = Episode(
                episode_id=episode_id,
                video_id=video_id,
                title=f"Episode {episode_id}",
                description=f"Transcript at: {transcript_path}",
            )
            session.add(episode)
        else:
            # Update description with transcript path
            if episode.description:
                episode.description += f"\nTranscript: {transcript_path}"
            else:
                episode.description = f"Transcript: {transcript_path}"

        session.commit()
        logger.info(
            f"Stored transcript reference for episode {episode_id}: {transcript_path}"
        )


def get_episode_summary(db_service: DatabaseService, episode_id: str) -> dict[str, Any]:
    """
    Get summary statistics for an episode.

    Args:
        db_service: Database service instance
        episode_id: Episode identifier

    Returns:
        Dictionary with counts of claims, jargon, people, concepts
    """
    with db_service.get_session() as session:
        claims_count = session.query(Claim).filter_by(episode_id=episode_id).count()
        jargon_count = session.query(Jargon).filter_by(episode_id=episode_id).count()
        people_count = session.query(Person).filter_by(episode_id=episode_id).count()
        concepts_count = session.query(Concept).filter_by(episode_id=episode_id).count()

        return {
            "episode_id": episode_id,
            "claims_count": claims_count,
            "jargon_count": jargon_count,
            "people_count": people_count,
            "concepts_count": concepts_count,
            "total_extractions": claims_count
            + jargon_count
            + people_count
            + concepts_count,
        }


def clear_episode_data(db_service: DatabaseService, episode_id: str) -> None:
    """
    Clear all HCE data for an episode (useful for re-processing).

    Args:
        db_service: Database service instance
        episode_id: Episode identifier
    """
    with db_service.get_session() as session:
        # Delete all related data (cascading should handle this)
        session.query(Claim).filter_by(episode_id=episode_id).delete()
        session.query(Jargon).filter_by(episode_id=episode_id).delete()
        session.query(Person).filter_by(episode_id=episode_id).delete()
        session.query(Concept).filter_by(episode_id=episode_id).delete()

        session.commit()
        logger.info(f"Cleared all HCE data for episode {episode_id}")
