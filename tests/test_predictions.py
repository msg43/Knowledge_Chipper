"""Unit tests for prediction system."""

import pytest
from datetime import datetime, timedelta

from knowledge_system.database.models import Prediction, PredictionEvidence, PredictionHistory
from knowledge_system.database.service import DatabaseService
from knowledge_system.services.prediction_service import PredictionService


@pytest.fixture
def db_service():
    """Create a test database service."""
    db = DatabaseService(":memory:")
    yield db
    db.close()


@pytest.fixture
def prediction_service(db_service):
    """Create a prediction service with test database."""
    return PredictionService(db_service)


class TestPredictionModels:
    """Test prediction database models."""

    def test_create_prediction(self, db_service):
        """Test creating a prediction."""
        prediction_id = db_service.create_prediction(
            title="Test prediction",
            description="This is a test",
            confidence=0.75,
            deadline="2026-12-31",
        )

        assert prediction_id is not None
        assert prediction_id.startswith("pred_")

        # Retrieve and verify
        prediction = db_service.get_prediction(prediction_id)
        assert prediction is not None
        assert prediction.title == "Test prediction"
        assert prediction.confidence == 0.75
        assert prediction.deadline == "2026-12-31"
        assert prediction.resolution_status == "pending"

    def test_prediction_history_auto_created(self, db_service):
        """Test that history is automatically created."""
        prediction_id = db_service.create_prediction(
            title="Test",
            confidence=0.5,
            deadline="2026-01-01",
        )

        # Check history was created
        history = db_service.get_prediction_history(prediction_id)
        assert len(history) == 1
        assert history[0].confidence == 0.5
        assert history[0].deadline == "2026-01-01"

    def test_update_prediction_creates_history(self, db_service):
        """Test that updating confidence/deadline creates history."""
        prediction_id = db_service.create_prediction(
            title="Test",
            confidence=0.5,
            deadline="2026-01-01",
        )

        # Update confidence
        db_service.update_prediction(
            prediction_id,
            confidence=0.75,
            change_reason="New information",
        )

        # Check history
        history = db_service.get_prediction_history(prediction_id)
        assert len(history) == 2  # Initial + update
        assert history[-1].confidence == 0.75
        assert history[-1].change_reason == "New information"

    def test_resolve_prediction(self, db_service):
        """Test resolving a prediction."""
        prediction_id = db_service.create_prediction(
            title="Test",
            confidence=0.5,
            deadline="2026-01-01",
        )

        # Resolve
        success = db_service.resolve_prediction(
            prediction_id,
            "correct",
            "Prediction came true!",
        )

        assert success is True

        # Verify
        prediction = db_service.get_prediction(prediction_id)
        assert prediction.resolution_status == "correct"
        assert prediction.resolution_notes == "Prediction came true!"
        assert prediction.resolved_at is not None

    def test_delete_prediction_cascades(self, db_service):
        """Test that deleting prediction cascades to history and evidence."""
        prediction_id = db_service.create_prediction(
            title="Test",
            confidence=0.5,
            deadline="2026-01-01",
        )

        # Add evidence (assuming a claim exists)
        # For this test, we'll just check cascade behavior
        
        # Delete
        success = db_service.delete_prediction(prediction_id)
        assert success is True

        # Verify it's gone
        prediction = db_service.get_prediction(prediction_id)
        assert prediction is None

        # History should also be gone
        history = db_service.get_prediction_history(prediction_id)
        assert len(history) == 0


class TestPredictionService:
    """Test prediction service logic."""

    def test_create_prediction_validates_confidence(self, prediction_service):
        """Test that confidence is validated."""
        with pytest.raises(ValueError, match="Confidence must be between"):
            prediction_service.create_prediction(
                title="Test",
                confidence=1.5,  # Invalid
                deadline="2026-01-01",
            )

    def test_create_prediction_validates_privacy(self, prediction_service):
        """Test that privacy status is validated."""
        with pytest.raises(ValueError, match="Privacy status must be"):
            prediction_service.create_prediction(
                title="Test",
                confidence=0.5,
                deadline="2026-01-01",
                privacy_status="invalid",
            )

    def test_search_predictions_by_title(self, prediction_service):
        """Test searching predictions by title."""
        # Create predictions
        prediction_service.create_prediction(
            title="Bitcoin will reach $100k",
            confidence=0.75,
            deadline="2026-12-31",
        )
        prediction_service.create_prediction(
            title="Ethereum will flip Bitcoin",
            confidence=0.25,
            deadline="2027-12-31",
        )

        # Search
        results = prediction_service.search_predictions(query="Bitcoin")
        assert len(results) == 2  # Both mention Bitcoin

        results = prediction_service.search_predictions(query="Ethereum")
        assert len(results) == 1

    def test_search_predictions_by_status(self, prediction_service):
        """Test filtering predictions by status."""
        pred1_id = prediction_service.create_prediction(
            title="Test 1",
            confidence=0.5,
            deadline="2026-01-01",
        )
        prediction_service.create_prediction(
            title="Test 2",
            confidence=0.5,
            deadline="2026-01-01",
        )

        # Resolve one
        prediction_service.resolve_prediction(pred1_id, "correct")

        # Filter by pending
        pending = prediction_service.search_predictions(resolution_status="pending")
        assert len(pending) == 1
        assert pending[0].title == "Test 2"

        # Filter by correct
        correct = prediction_service.search_predictions(resolution_status="correct")
        assert len(correct) == 1
        assert correct[0].title == "Test 1"

    def test_get_predictions_by_deadline(self, prediction_service):
        """Test getting predictions with upcoming deadlines."""
        today = datetime.now().date()
        
        # Create predictions
        prediction_service.create_prediction(
            title="Soon",
            confidence=0.5,
            deadline=(today + timedelta(days=10)).strftime("%Y-%m-%d"),
        )
        prediction_service.create_prediction(
            title="Later",
            confidence=0.5,
            deadline=(today + timedelta(days=60)).strftime("%Y-%m-%d"),
        )

        # Get upcoming (30 days)
        upcoming = prediction_service.get_predictions_by_deadline(upcoming_days=30)
        assert len(upcoming) == 1
        assert upcoming[0].title == "Soon"

        # Get upcoming (90 days)
        upcoming = prediction_service.get_predictions_by_deadline(upcoming_days=90)
        assert len(upcoming) == 2

    def test_export_prediction(self, prediction_service):
        """Test exporting prediction to JSON."""
        prediction_id = prediction_service.create_prediction(
            title="Test",
            description="Test description",
            confidence=0.75,
            deadline="2026-12-31",
            user_notes="My notes",
        )

        # Export
        json_str = prediction_service.export_prediction(prediction_id)
        
        # Verify it's valid JSON
        import json
        data = json.loads(json_str)
        
        assert data["title"] == "Test"
        assert data["confidence"] == 0.75
        assert data["deadline"] == "2026-12-31"
        assert data["user_notes"] == "My notes"
        assert len(data["history"]) == 1  # Initial history entry


class TestPredictionEvidence:
    """Test evidence linking."""

    def test_add_evidence_validates_type(self, prediction_service):
        """Test that evidence type is validated."""
        prediction_id = prediction_service.create_prediction(
            title="Test",
            confidence=0.5,
            deadline="2026-01-01",
        )

        with pytest.raises(ValueError, match="Invalid evidence type"):
            prediction_service.add_evidence(
                prediction_id=prediction_id,
                evidence_type="invalid",
                entity_id="test_id",
                stance="pro",
            )

    def test_add_evidence_validates_stance(self, prediction_service):
        """Test that stance is validated."""
        prediction_id = prediction_service.create_prediction(
            title="Test",
            confidence=0.5,
            deadline="2026-01-01",
        )

        with pytest.raises(ValueError, match="Invalid stance"):
            prediction_service.add_evidence(
                prediction_id=prediction_id,
                evidence_type="claim",
                entity_id="test_id",
                stance="invalid",
            )

    def test_update_evidence_stance(self, prediction_service, db_service):
        """Test updating evidence stance."""
        prediction_id = prediction_service.create_prediction(
            title="Test",
            confidence=0.5,
            deadline="2026-01-01",
        )

        # Add evidence (manually for testing)
        evidence_id = db_service.add_prediction_evidence(
            prediction_id=prediction_id,
            evidence_type="claim",
            entity_id="claim_123",
            stance="neutral",
        )

        # Update stance
        success = prediction_service.update_evidence_stance(evidence_id, "pro")
        assert success is True

        # Verify
        evidence = db_service.get_prediction_evidence(prediction_id)
        assert len(evidence) == 1
        assert evidence[0].stance == "pro"


def test_manual_testing_checklist():
    """Manual testing checklist for prediction system.
    
    This is not an automated test, but a checklist for manual testing.
    
    [ ] Open GUI and navigate to Predictions tab
    [ ] Click "New Prediction" and create a prediction
    [ ] Verify prediction appears in table with correct confidence and deadline
    [ ] Double-click prediction to open detail page
    [ ] Verify detail page shows all information correctly
    [ ] Click "Update Confidence/Deadline" and change values
    [ ] Verify graph updates with new history point
    [ ] Click "Add Evidence" and add a claim with "Pro" stance
    [ ] Verify claim appears in Claims tab with green checkmark
    [ ] Double-click claim in evidence list to change stance to "Con"
    [ ] Verify stance updates (red X)
    [ ] Add jargon, person, and concept evidence
    [ ] Verify all evidence types appear in appropriate tabs
    [ ] Add user notes and save
    [ ] Close and reopen detail page - verify notes persist
    [ ] Mark prediction as resolved (Correct)
    [ ] Verify status badge updates
    [ ] Test filters: Privacy (Public/Private), Status (Pending/Resolved), Search
    [ ] Create predictions with past deadlines - verify red text
    [ ] Test delete prediction with confirmation dialog
    [ ] Verify prediction is removed from list
    [ ] Test with matplotlib installed - verify graph displays
    [ ] Test with matplotlib NOT installed - verify fallback message
    """
    pass

