"""
Prediction service layer for personal forecasting system.

Provides business logic for creating, managing, and resolving predictions with
confidence tracking, evidence linking, and export capabilities.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ..database.models import Claim, Concept, JargonTerm, Person
from ..database.service import DatabaseService
from ..logger import get_logger

logger = get_logger(__name__)


class PredictionService:
    """High-level service for prediction management."""

    def __init__(self, db_service: DatabaseService = None):
        """Initialize prediction service."""
        self.db = db_service or DatabaseService()

    def create_prediction(
        self,
        title: str,
        description: str = None,
        confidence: float = 0.5,
        deadline: str = None,
        privacy_status: str = "private",
        user_notes: str = None,
    ) -> str:
        """
        Create a new prediction.
        
        Args:
            title: Short prediction title
            description: Detailed prediction statement
            confidence: Initial confidence (0.0-1.0)
            deadline: Deadline date (YYYY-MM-DD)
            privacy_status: 'public' or 'private'
            user_notes: User's reasoning
        
        Returns:
            prediction_id
        """
        # Validate inputs
        if not title or not title.strip():
            raise ValueError("Title is required")
        
        if confidence < 0.0 or confidence > 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        
        if privacy_status not in ["public", "private"]:
            raise ValueError("Privacy status must be 'public' or 'private'")
        
        # Create prediction
        prediction_id = self.db.create_prediction(
            title=title.strip(),
            description=description,
            confidence=confidence,
            deadline=deadline,
            privacy_status=privacy_status,
            user_notes=user_notes,
        )
        
        logger.info(f"Created prediction '{title}' with ID {prediction_id}")
        return prediction_id

    def update_prediction_confidence(
        self,
        prediction_id: str,
        new_confidence: float,
        reason: str = None,
    ) -> bool:
        """
        Update prediction confidence and create history entry.
        
        Args:
            prediction_id: Prediction ID
            new_confidence: New confidence value (0.0-1.0)
            reason: Reason for change
        
        Returns:
            True if successful
        """
        if new_confidence < 0.0 or new_confidence > 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        
        return self.db.update_prediction(
            prediction_id=prediction_id,
            confidence=new_confidence,
            change_reason=reason or "Confidence updated",
        )

    def update_prediction_deadline(
        self,
        prediction_id: str,
        new_deadline: str,
        reason: str = None,
    ) -> bool:
        """
        Update prediction deadline and create history entry.
        
        Args:
            prediction_id: Prediction ID
            new_deadline: New deadline (YYYY-MM-DD)
            reason: Reason for change
        
        Returns:
            True if successful
        """
        return self.db.update_prediction(
            prediction_id=prediction_id,
            deadline=new_deadline,
            change_reason=reason or "Deadline updated",
        )

    def add_evidence(
        self,
        prediction_id: str,
        evidence_type: str,
        entity_id: str,
        stance: str = "neutral",
        notes: str = None,
    ) -> int | None:
        """
        Add evidence to prediction with stance classification.
        
        Args:
            prediction_id: Prediction ID
            evidence_type: 'claim', 'jargon', 'concept', or 'person'
            entity_id: ID of the entity
            stance: 'pro', 'con', or 'neutral'
            notes: User's notes about why this evidence matters
        
        Returns:
            evidence_id if successful
        """
        # Validate evidence_type
        if evidence_type not in ["claim", "jargon", "concept", "person"]:
            raise ValueError(f"Invalid evidence type: {evidence_type}")
        
        # Validate stance
        if stance not in ["pro", "con", "neutral"]:
            raise ValueError(f"Invalid stance: {stance}")
        
        # Verify entity exists
        if not self._verify_entity_exists(evidence_type, entity_id):
            raise ValueError(f"Entity {entity_id} of type {evidence_type} does not exist")
        
        return self.db.add_prediction_evidence(
            prediction_id=prediction_id,
            evidence_type=evidence_type,
            entity_id=entity_id,
            stance=stance,
            user_notes=notes,
        )

    def remove_evidence(self, evidence_id: int) -> bool:
        """Remove evidence from prediction."""
        return self.db.remove_prediction_evidence(evidence_id)

    def update_evidence_stance(self, evidence_id: int, new_stance: str) -> bool:
        """
        Update stance classification for evidence.
        
        Args:
            evidence_id: Evidence ID
            new_stance: 'pro', 'con', or 'neutral'
        
        Returns:
            True if successful
        """
        if new_stance not in ["pro", "con", "neutral"]:
            raise ValueError(f"Invalid stance: {new_stance}")
        
        return self.db.update_evidence_stance(evidence_id, new_stance)

    def resolve_prediction(
        self,
        prediction_id: str,
        resolution_status: str,
        notes: str = None,
    ) -> bool:
        """
        Mark prediction as resolved.
        
        Args:
            prediction_id: Prediction ID
            resolution_status: 'correct', 'incorrect', 'ambiguous', or 'cancelled'
            notes: Explanation of resolution
        
        Returns:
            True if successful
        """
        if resolution_status not in ["correct", "incorrect", "ambiguous", "cancelled"]:
            raise ValueError(f"Invalid resolution status: {resolution_status}")
        
        return self.db.resolve_prediction(
            prediction_id=prediction_id,
            resolution_status=resolution_status,
            resolution_notes=notes,
        )

    def get_prediction_with_evidence(self, prediction_id: str) -> dict | None:
        """
        Get prediction with all related data and full entity details.
        
        Returns:
            Dictionary with prediction, evidence (with entity details), and history
        """
        details = self.db.get_prediction_with_details(prediction_id)
        if not details:
            return None
        
        # Enrich evidence with actual entity data
        enriched_evidence = []
        for evidence in details["evidence"]:
            entity_data = self._get_entity_data(evidence.evidence_type, evidence.entity_id)
            enriched_evidence.append({
                "evidence_id": evidence.evidence_id,
                "evidence_type": evidence.evidence_type,
                "entity_id": evidence.entity_id,
                "stance": evidence.stance,
                "user_notes": evidence.user_notes,
                "added_at": evidence.added_at,
                "entity_data": entity_data,
            })
        
        return {
            "prediction": details["prediction"],
            "evidence": enriched_evidence,
            "history": details["history"],
        }

    def get_confidence_history(self, prediction_id: str) -> list[dict]:
        """
        Get confidence and deadline history for graphing.
        
        Returns:
            List of {timestamp, confidence, deadline, reason} dicts
        """
        history = self.db.get_prediction_history(prediction_id)
        return [
            {
                "timestamp": h.timestamp,
                "confidence": h.confidence,
                "deadline": h.deadline,
                "reason": h.change_reason,
            }
            for h in history
        ]

    def export_prediction(self, prediction_id: str, format: str = "json") -> str:
        """
        Export prediction to JSON for sharing.
        
        Args:
            prediction_id: Prediction ID
            format: Export format ('json' only for now)
        
        Returns:
            JSON string
        """
        if format != "json":
            raise ValueError("Only JSON export is currently supported")
        
        details = self.get_prediction_with_evidence(prediction_id)
        if not details:
            raise ValueError(f"Prediction {prediction_id} not found")
        
        # Build export structure
        pred = details["prediction"]
        export_data = {
            "prediction_id": pred.prediction_id,
            "title": pred.title,
            "description": pred.description,
            "confidence": pred.confidence,
            "deadline": pred.deadline,
            "resolution_status": pred.resolution_status,
            "resolution_notes": pred.resolution_notes,
            "user_notes": pred.user_notes,
            "created_at": pred.created_at.isoformat() if pred.created_at else None,
            "resolved_at": pred.resolved_at.isoformat() if pred.resolved_at else None,
            "evidence": details["evidence"],
            "history": [
                {
                    "timestamp": h["timestamp"].isoformat() if h["timestamp"] else None,
                    "confidence": h["confidence"],
                    "deadline": h["deadline"],
                    "reason": h["reason"],
                }
                for h in details["history"]
            ],
        }
        
        return json.dumps(export_data, indent=2)

    def search_predictions(
        self,
        query: str = None,
        privacy_status: str = None,
        resolution_status: str = None,
    ) -> list:
        """
        Search predictions by title/description.
        
        Args:
            query: Search query (searches title and description)
            privacy_status: Filter by 'public' or 'private'
            resolution_status: Filter by resolution status
        
        Returns:
            List of matching predictions
        """
        predictions = self.db.get_all_predictions(
            privacy_status=privacy_status,
            resolution_status=resolution_status,
        )
        
        # Filter by search query if provided
        if query:
            query_lower = query.lower()
            predictions = [
                p for p in predictions
                if (query_lower in p.title.lower() or
                    (p.description and query_lower in p.description.lower()))
            ]
        
        return predictions

    def get_predictions_by_deadline(self, upcoming_days: int = 30) -> list:
        """
        Get predictions with upcoming deadlines.
        
        Args:
            upcoming_days: Number of days ahead to look
        
        Returns:
            List of predictions with deadlines in the next N days
        """
        from datetime import date, timedelta
        
        today = date.today()
        cutoff = today + timedelta(days=upcoming_days)
        
        predictions = self.db.get_all_predictions(resolution_status="pending")
        
        # Filter by deadline
        upcoming = []
        for pred in predictions:
            if pred.deadline:
                try:
                    deadline_date = datetime.strptime(pred.deadline, "%Y-%m-%d").date()
                    if today <= deadline_date <= cutoff:
                        upcoming.append(pred)
                except ValueError:
                    logger.warning(f"Invalid deadline format for {pred.prediction_id}: {pred.deadline}")
        
        # Sort by deadline
        upcoming.sort(key=lambda p: p.deadline)
        return upcoming

    def _verify_entity_exists(self, evidence_type: str, entity_id: str) -> bool:
        """Verify that an entity exists in the database."""
        try:
            with self.db.get_session() as session:
                if evidence_type == "claim":
                    return session.query(Claim).filter_by(claim_id=entity_id).first() is not None
                elif evidence_type == "jargon":
                    return session.query(JargonTerm).filter_by(term_id=entity_id).first() is not None
                elif evidence_type == "concept":
                    return session.query(Concept).filter_by(concept_id=entity_id).first() is not None
                elif evidence_type == "person":
                    return session.query(Person).filter_by(person_id=entity_id).first() is not None
                return False
        except Exception as e:
            logger.error(f"Failed to verify entity {entity_id}: {e}")
            return False

    def _get_entity_data(self, evidence_type: str, entity_id: str) -> dict | None:
        """Get full entity data for enriching evidence."""
        try:
            with self.db.get_session() as session:
                if evidence_type == "claim":
                    claim = session.query(Claim).filter_by(claim_id=entity_id).first()
                    if claim:
                        return {
                            "canonical": claim.canonical,
                            "tier": claim.tier,
                            "speaker": claim.speaker,
                        }
                elif evidence_type == "jargon":
                    term = session.query(JargonTerm).filter_by(term_id=entity_id).first()
                    if term:
                        return {
                            "term": term.term,
                            "definition": term.definition,
                            "introduced_by": term.introduced_by,
                        }
                elif evidence_type == "concept":
                    concept = session.query(Concept).filter_by(concept_id=entity_id).first()
                    if concept:
                        return {
                            "name": concept.name,
                            "description": concept.description,
                            "advocated_by": concept.advocated_by,
                        }
                elif evidence_type == "person":
                    person = session.query(Person).filter_by(person_id=entity_id).first()
                    if person:
                        return {
                            "name": person.name,
                            "description": person.description,
                        }
                return None
        except Exception as e:
            logger.error(f"Failed to get entity data for {entity_id}: {e}")
            return None

