"""
Claims Upload Service for Cloud Uploads functionality.

Reads claims from SQLite database and prepares them for upload to Supabase.
Handles tracking of upload status and associated data collection.

Uses SQLAlchemy ORM to query the claim-centric database schema.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import or_

from ..config import get_settings
from ..database import DatabaseService, Claim, MediaSource, EvidenceSpan, ClaimPerson, ClaimConcept, ClaimJargon, ClaimRelation
from ..logger import get_logger

logger = get_logger(__name__)


class ClaimUploadData:
    """Data structure for a claim with its associated data."""

    def __init__(self, claim_data: dict[str, Any]):
        self.source_id = claim_data["source_id"]
        self.claim_id = claim_data["claim_id"]
        self.canonical = claim_data["canonical"]
        self.claim_type = claim_data["claim_type"]
        self.tier = claim_data["tier"]
        self.first_mention_ts = claim_data["first_mention_ts"]
        self.scores_json = claim_data["scores_json"]
        self.inserted_at = claim_data["inserted_at"]
        self.last_uploaded_at = claim_data.get("last_uploaded_at")
        self.upload_status = claim_data.get("upload_status", "pending")

        # Associated data (populated by collector)
        self.episode_data: dict[str, Any] | None = None
        self.evidence_spans: list[dict[str, Any]] = []
        self.people: list[dict[str, Any]] = []
        self.concepts: list[dict[str, Any]] = []
        self.jargon: list[dict[str, Any]] = []
        self.relations: list[dict[str, Any]] = []

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for upload."""
        return {
            "claim": {
                "source_id": self.source_id,
                "claim_id": self.claim_id,
                "canonical": self.canonical,
                "claim_type": self.claim_type,
                "tier": self.tier,
                "first_mention_ts": self.first_mention_ts,
                "scores_json": self.scores_json,
                "inserted_at": self.inserted_at,
                "last_uploaded_at": self.last_uploaded_at,
                "upload_status": self.upload_status,
            },
            "episode": self.episode_data,
            "evidence_spans": self.evidence_spans,
            "people": self.people,
            "concepts": self.concepts,
            "jargon": self.jargon,
            "relations": self.relations,
        }


class ClaimsUploadService:
    """Service for reading claims from SQLite and preparing them for upload."""

    def __init__(self, db_path: str | Path | None = None):
        """Initialize the service with optional database path.
        
        If db_path is None, uses DatabaseService to resolve the default path
        (which uses Application Support directory on macOS).
        """
        if db_path:
            self.db_path = Path(db_path)
            self.db_service = DatabaseService(f"sqlite:///{self.db_path}")
        else:
            # Use DatabaseService to resolve the default path (same as the app)
            # This ensures we use the same database the GUI uses
            self.db_service = DatabaseService()  # Uses default resolution
            self.db_path = self.db_service.db_path

    def _get_default_db_path(self) -> Path:
        """Get the default knowledge_system.db path."""
        # Create a temporary DatabaseService to get the resolved path
        temp_service = DatabaseService()
        return temp_service.db_path

    def is_database_valid(self) -> tuple[bool, str]:
        """Check if the database file is valid and has required tables."""
        if not self.db_path.exists():
            return False, f"Database file not found: {self.db_path}"

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Check for required tables (claim-centric schema)
                # Note: Schema uses claim_relations, jargon_terms, claim_jargon, etc.
                required_tables = [
                    "claims",
                    "media_sources",
                    "evidence_spans",
                ]
                # Optional tables (may not exist in all databases)
                optional_tables = [
                    "people",
                    "claim_people",
                    "concepts",
                    "claim_concepts",
                    "jargon_terms",
                    "claim_jargon",
                    "claim_relations",
                ]
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                existing_tables = {row[0] for row in cursor.fetchall()}

                missing_tables = set(required_tables) - existing_tables
                if missing_tables:
                    return (
                        False,
                        f"Missing required tables: {', '.join(missing_tables)}",
                    )
                
                # Log which optional tables exist
                existing_optional = set(optional_tables) & existing_tables
                if existing_optional:
                    logger.debug(f"Found optional tables: {', '.join(existing_optional)}")

                # Check if upload tracking columns exist, add them if not
                cursor.execute("PRAGMA table_info(claims)")
                columns = {row[1] for row in cursor.fetchall()}

                if "last_uploaded_at" not in columns or "upload_status" not in columns:
                    logger.info("Adding upload tracking columns to claims table")
                    self._add_upload_tracking_columns(conn)

                return True, "Database is valid"

        except Exception as e:
            return False, f"Database error: {str(e)}"

    def _add_upload_tracking_columns(self, conn: sqlite3.Connection) -> None:
        """Add upload tracking columns if they don't exist."""
        try:
            cursor = conn.cursor()
            cursor.execute(
                "ALTER TABLE claims ADD COLUMN last_uploaded_at TEXT DEFAULT NULL"
            )
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            cursor.execute(
                "ALTER TABLE claims ADD COLUMN upload_status TEXT DEFAULT 'pending'"
            )
        except sqlite3.OperationalError:
            pass  # Column already exists

        try:
            cursor.execute(
                "ALTER TABLE claims ADD COLUMN hidden BOOLEAN DEFAULT 0"
            )
        except sqlite3.OperationalError:
            pass  # Column already exists

        conn.commit()

    def get_unuploaded_claims(self) -> list[ClaimUploadData]:
        """Get all claims that haven't been uploaded or have been modified since last upload.

        EPHEMERAL-LOCAL ARCHITECTURE:
        Only returns claims that are:
        1. Not yet uploaded (upload_status != 'uploaded')
        2. Not hidden (hidden = 0)

        After upload, claims are hidden to maintain web as canonical source.
        
        Uses SQLAlchemy ORM to query the claim-centric database schema.
        """
        try:
            with self.db_service.get_session() as session:
                # Query claims using SQLAlchemy ORM
                # Filter for unuploaded claims (pending, failed, or null upload_status)
                # Note: The Claim model uses upload_status (default="pending") and upload_timestamp
                # Note: No 'hidden' column exists in Claim model - we filter by upload_status only
                unuploaded_claims_query = (
                    session.query(Claim)
                    .join(MediaSource, Claim.source_id == MediaSource.source_id, isouter=True)
                    .filter(
                        or_(
                            Claim.upload_status == None,
                            Claim.upload_status == 'pending',
                            Claim.upload_status == 'failed',
                            Claim.upload_timestamp == None
                        )
                    )
                    .order_by(Claim.created_at.desc())
                )
                
                db_claims = unuploaded_claims_query.all()
                
                logger.info(f"Found {len(db_claims)} unuploaded claims from database")
                
                claims = []
                for db_claim in db_claims:
                    # Use scores_json directly (canonical format) - no mapping needed
                    scores_json = db_claim.scores_json if isinstance(db_claim.scores_json, str) else json.dumps(db_claim.scores_json) if db_claim.scores_json else "{}"
                    
                    # Use created_at as inserted_at
                    inserted_at = db_claim.created_at.isoformat() if db_claim.created_at else None
                    upload_timestamp = db_claim.upload_timestamp.isoformat() if db_claim.upload_timestamp else None
                    
                    claim_data = {
                        "claim_id": db_claim.claim_id,
                        "source_id": db_claim.source_id,
                        "canonical": db_claim.canonical,
                        "claim_type": db_claim.claim_type,
                        "tier": db_claim.tier,
                        "first_mention_ts": db_claim.first_mention_ts,
                        "scores_json": scores_json,  # Canonical format - no mapping
                        "inserted_at": inserted_at,
                        "last_uploaded_at": upload_timestamp,
                        "upload_status": db_claim.upload_status or "pending",
                    }
                    
                    claim = ClaimUploadData(claim_data)
                    
                    # Collect associated data using SQLAlchemy relationships
                    self._collect_associated_data_orm(session, claim, db_claim)
                    claims.append(claim)

                logger.info(f"Found {len(claims)} unuploaded claims")
                return claims

        except Exception as e:
            logger.error(f"Error reading unuploaded claims: {e}", exc_info=True)
            return []

    def _collect_associated_data_orm(
        self, session, claim: ClaimUploadData, db_claim: Claim
    ) -> None:
        """Collect all data associated with a claim using SQLAlchemy ORM relationships."""
        try:
            # Get episode data from MediaSource relationship
            if db_claim.source:
                claim.episode_data = {
                    "source_id": db_claim.source.source_id,
                    "title": db_claim.source.title,
                    "url": db_claim.source.url,
                    "recorded_at": db_claim.source.recorded_at.isoformat() if db_claim.source.recorded_at else None,
                    "duration_seconds": db_claim.source.duration_seconds,
                }
            
            # Get evidence spans from relationship
            if db_claim.evidence_spans:
                claim.evidence_spans = []
                for evidence in db_claim.evidence_spans:
                    evidence_dict = {
                        "source_id": db_claim.source_id,
                        "claim_id": evidence.claim_id,
                        "seq": evidence.seq,
                        "t0": evidence.t0,
                        "t1": evidence.t1,
                        "quote": evidence.quote,
                        "context_t0": evidence.context_t0,
                        "context_t1": evidence.context_t1,
                        "context_text": evidence.context_text,
                        "context_type": evidence.context_type or "exact",
                    }
                    claim.evidence_spans.append(evidence_dict)
            
            # Get people from ClaimPerson relationship
            if db_claim.people:
                claim.people = []
                for claim_person in db_claim.people:
                    person = claim_person.person
                    person_dict = {
                        "source_id": db_claim.source_id,
                        "claim_id": db_claim.claim_id,
                        "mention_id": person.person_id if hasattr(person, 'person_id') else None,
                        "surface": person.surface_form if hasattr(person, 'surface_form') else None,
                        "normalized": person.normalized_name if hasattr(person, 'normalized_name') else None,
                        "entity_type": person.entity_type if hasattr(person, 'entity_type') else 'person',
                    }
                    claim.people.append(person_dict)
            
            # Get concepts from ClaimConcept relationship
            if db_claim.concepts:
                claim.concepts = []
                for claim_concept in db_claim.concepts:
                    concept = claim_concept.concept
                    concept_dict = {
                        "source_id": db_claim.source_id,
                        "claim_id": db_claim.claim_id,
                        "model_id": concept.concept_id if hasattr(concept, 'concept_id') else None,
                        "name": concept.name if hasattr(concept, 'name') else None,
                        "definition": concept.definition if hasattr(concept, 'definition') else None,
                    }
                    claim.concepts.append(concept_dict)
            
            # Get jargon from ClaimJargon relationship
            if db_claim.jargon:
                claim.jargon = []
                for claim_jargon in db_claim.jargon:
                    jargon_term = claim_jargon.jargon_term
                    jargon_dict = {
                        "source_id": db_claim.source_id,
                        "claim_id": db_claim.claim_id,
                        "term_id": jargon_term.term_id if hasattr(jargon_term, 'term_id') else None,
                        "term": jargon_term.term if hasattr(jargon_term, 'term') else None,
                        "definition": jargon_term.definition if hasattr(jargon_term, 'definition') else None,
                    }
                    claim.jargon.append(jargon_dict)
            
            # Get relations from ClaimRelation relationships
            if db_claim.relations_as_source or db_claim.relations_as_target:
                claim.relations = []
                # Relations where this claim is the source
                for relation in db_claim.relations_as_source:
                    relation_dict = {
                        "source_id": db_claim.source_id,
                        "source_claim_id": relation.source_claim_id,
                        "target_claim_id": relation.target_claim_id,
                        "type": relation.relation_type if hasattr(relation, 'relation_type') else relation.type,
                        "strength": relation.strength,
                        "rationale": relation.rationale,
                    }
                    claim.relations.append(relation_dict)
                # Relations where this claim is the target
                for relation in db_claim.relations_as_target:
                    relation_dict = {
                        "source_id": db_claim.source_id,
                        "source_claim_id": relation.source_claim_id,
                        "target_claim_id": relation.target_claim_id,
                        "type": relation.relation_type if hasattr(relation, 'relation_type') else relation.type,
                        "strength": relation.strength,
                        "rationale": relation.rationale,
                    }
                    claim.relations.append(relation_dict)
                    
        except Exception as e:
            logger.error(
                f"Error collecting associated data for claim {claim.claim_id}: {e}", exc_info=True
            )

    def _collect_associated_data(
        self, conn: sqlite3.Connection, claim: ClaimUploadData
    ) -> None:
        """Collect all data associated with a claim."""
        # Set row_factory on connection before creating cursor
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # Use source_id (claims table uses source_id, not episode_id)
            source_id = claim.source_id
            
            # Get episode data from media_sources table (claim-centric architecture)
            # Schema migrated from episodes to media_sources
            cursor.execute(
                "SELECT * FROM media_sources WHERE source_id = ?", (source_id,)
            )
            episode_row = cursor.fetchone()
            if episode_row:
                claim.episode_data = dict(episode_row)

            # Get evidence spans
            cursor.execute(
                "SELECT * FROM evidence_spans WHERE source_id = ? AND claim_id = ? ORDER BY seq",
                (source_id, claim.claim_id),
            )
            claim.evidence_spans = [dict(row) for row in cursor.fetchall()]

            # Get people mentioned in this episode
            cursor.execute(
                "SELECT * FROM people WHERE source_id = ?", (source_id,)
            )
            claim.people = [dict(row) for row in cursor.fetchall()]

            # Get concepts from this episode
            cursor.execute(
                "SELECT * FROM concepts WHERE source_id = ?", (source_id,)
            )
            claim.concepts = [dict(row) for row in cursor.fetchall()]

            # Get jargon from this episode
            cursor.execute(
                "SELECT * FROM jargon WHERE source_id = ?", (source_id,)
            )
            claim.jargon = [dict(row) for row in cursor.fetchall()]

            # Get relations involving this claim
            cursor.execute(
                """SELECT * FROM relations
                   WHERE source_id = ? AND (source_claim_id = ? OR target_claim_id = ?)""",
                (source_id, claim.claim_id, claim.claim_id),
            )
            claim.relations = [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(
                f"Error collecting associated data for claim {claim.claim_id}: {e}"
            )

    def mark_claims_uploaded(self, claim_ids: list[tuple[str, str]]) -> None:
        """Mark claims as uploaded with current timestamp using SQLAlchemy ORM."""
        if not claim_ids:
            return

        try:
            with self.db_service.get_session() as session:
                timestamp = datetime.utcnow()
                
                for source_id, claim_id in claim_ids:
                    # Find claim by claim_id (which is global unique ID)
                    claim = session.query(Claim).filter_by(claim_id=claim_id).first()
                    if claim:
                        claim.upload_status = 'uploaded'
                        claim.upload_timestamp = timestamp
                    else:
                        logger.warning(f"Claim not found: {claim_id}")

                session.commit()
                logger.info(f"Marked {len(claim_ids)} claims as uploaded")

        except Exception as e:
            logger.error(f"Error marking claims as uploaded: {e}", exc_info=True)

    def mark_claims_failed(self, claim_ids: list[tuple[str, str]]) -> None:
        """Mark claims as failed upload."""
        if not claim_ids:
            return

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Ensure upload tracking columns exist
                cursor.execute("PRAGMA table_info(claims)")
                columns = {row[1] for row in cursor.fetchall()}
                
                if "upload_status" not in columns:
                    logger.info("Adding upload tracking columns to claims table")
                    self._add_upload_tracking_columns(conn)

                for source_id, claim_id in claim_ids:
                    cursor.execute(
                        """UPDATE claims
                           SET upload_status = 'failed'
                           WHERE source_id = ? AND claim_id = ?""",
                        (source_id, claim_id),
                    )

                conn.commit()
                logger.info(f"Marked {len(claim_ids)} claims as failed")

        except Exception as e:
            logger.error(f"Error marking claims as failed: {e}")

    def hide_uploaded_claims(self, claim_ids: list[tuple[str, str]]) -> None:
        """Hide claims after successful upload (ephemeral-local architecture).

        This removes uploaded claims from the Review Tab, maintaining web as canonical source.
        Claims remain in local DB for reference but are hidden from user view.

        Args:
            claim_ids: List of (source_id, claim_id) tuples to hide
        """
        if not claim_ids:
            return

        # Claims are already marked as 'uploaded' in mark_claims_uploaded(),
        # which effectively hides them from future queries
        # This method is kept for API compatibility but doesn't need to do anything
        # Note: The Claim model doesn't have a 'hidden' column
        logger.info(f"Claims already marked as uploaded (hidden from unuploaded query): {len(claim_ids)}")

    def get_database_stats(self) -> dict[str, Any]:
        """Get statistics about the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Ensure upload tracking columns exist before querying
                cursor.execute("PRAGMA table_info(claims)")
                columns = {row[1] for row in cursor.fetchall()}
                
                if "last_uploaded_at" not in columns or "upload_status" not in columns or "hidden" not in columns:
                    logger.info("Adding upload tracking columns to claims table")
                    self._add_upload_tracking_columns(conn)

                stats = {}

                # Count total claims
                cursor.execute("SELECT COUNT(*) FROM claims")
                stats["total_claims"] = cursor.fetchone()[0]

                # Count unuploaded claims (not hidden)
                cursor.execute(
                    """SELECT COUNT(*) FROM claims
                       WHERE (upload_status IS NULL OR upload_status = 'pending' OR upload_status = 'failed')
                       AND (hidden IS NULL OR hidden = 0)"""
                )
                stats["unuploaded_claims"] = cursor.fetchone()[0]

                # Count uploaded claims
                cursor.execute(
                    "SELECT COUNT(*) FROM claims WHERE upload_status = 'uploaded'"
                )
                stats["uploaded_claims"] = cursor.fetchone()[0]

                # Count media sources (episodes migrated to media_sources in claim-centric architecture)
                cursor.execute("SELECT COUNT(*) FROM media_sources")
                stats["total_episodes"] = cursor.fetchone()[0]

                return stats

        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {}
