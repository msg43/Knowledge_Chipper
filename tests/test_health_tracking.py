"""Tests for health tracking system."""

import uuid

import pytest

from knowledge_system.database import (
    DatabaseService,
    HealthIntervention,
    HealthIssue,
    HealthMetric,
)


@pytest.fixture
def db():
    """Create database service."""
    return DatabaseService()


def test_create_health_intervention(db):
    """Test creating a health intervention."""
    with db.get_session() as session:
        intervention = HealthIntervention()
        intervention.intervention_id = str(uuid.uuid4())
        intervention.active = True
        intervention.name = "Red Light Therapy Cap"
        intervention.body_system = "Nervous System"
        intervention.organs = "Brain"
        intervention.author = "Andrew Huberman"
        intervention.frequency = "1 x Day"
        intervention.pete_attia_category = "Neurodegenerative disease"
        intervention.source_1 = "Huberman Lab Podcast"
        intervention.matt_notes = "Added 4/15/24"
        
        session.add(intervention)
        session.commit()
        
        # Verify it was saved
        loaded = session.query(HealthIntervention).filter_by(
            intervention_id=intervention.intervention_id
        ).first()
        
        assert loaded is not None
        assert loaded.name == "Red Light Therapy Cap"
        assert loaded.active is True
        assert loaded.body_system == "Nervous System"
        assert loaded.organs == "Brain"


def test_create_health_metric(db):
    """Test creating a health metric."""
    with db.get_session() as session:
        metric = HealthMetric()
        metric.metric_id = str(uuid.uuid4())
        metric.active = True
        metric.name = "VO2 Max"
        metric.body_system = "Respiratory System"
        metric.organs = "Lungs"
        metric.author = "Peter Attia"
        metric.frequency = "1 x Day"
        metric.pete_attia_category = "Cardiovascular disease"
        
        session.add(metric)
        session.commit()
        
        # Verify it was saved
        loaded = session.query(HealthMetric).filter_by(
            metric_id=metric.metric_id
        ).first()
        
        assert loaded is not None
        assert loaded.name == "VO2 Max"
        assert loaded.active is True
        assert loaded.body_system == "Respiratory System"


def test_create_health_issue(db):
    """Test creating a health issue."""
    with db.get_session() as session:
        issue = HealthIssue()
        issue.issue_id = str(uuid.uuid4())
        issue.active = True
        issue.name = "Bilateral hemiplegia"
        issue.body_system = "Nervous System"
        issue.organs = "Brain"
        issue.pete_attia_category = "Neurodegenerative disease"
        issue.matt_notes = "Monitoring closely"
        
        session.add(issue)
        session.commit()
        
        # Verify it was saved
        loaded = session.query(HealthIssue).filter_by(
            issue_id=issue.issue_id
        ).first()
        
        assert loaded is not None
        assert loaded.name == "Bilateral hemiplegia"
        assert loaded.active is True
        assert loaded.body_system == "Nervous System"


def test_intervention_active_toggle(db):
    """Test toggling intervention active status."""
    with db.get_session() as session:
        intervention = HealthIntervention()
        intervention.intervention_id = str(uuid.uuid4())
        intervention.active = True
        intervention.name = "Test Intervention"
        
        session.add(intervention)
        session.commit()
        
        # Toggle active status
        intervention.active = False
        session.commit()
        
        # Verify change persisted
        loaded = session.query(HealthIntervention).filter_by(
            intervention_id=intervention.intervention_id
        ).first()
        
        assert loaded.active is False


def test_query_interventions_by_category(db):
    """Test querying interventions by Pete Attia category."""
    with db.get_session() as session:
        # Create multiple interventions
        for i, category in enumerate([
            "Metabolic dysfunction",
            "Cancer",
            "Metabolic dysfunction"
        ]):
            intervention = HealthIntervention()
            intervention.intervention_id = str(uuid.uuid4())
            intervention.active = True
            intervention.name = f"Intervention {i+1}"
            intervention.pete_attia_category = category
            session.add(intervention)
        
        session.commit()
        
        # Query by category
        metabolic_interventions = session.query(HealthIntervention).filter_by(
            pete_attia_category="Metabolic dysfunction"
        ).all()
        
        assert len(metabolic_interventions) == 2
        assert all(i.pete_attia_category == "Metabolic dysfunction" for i in metabolic_interventions)


def test_query_active_only(db):
    """Test querying only active health tracking items."""
    with db.get_session() as session:
        # Create mix of active and inactive
        for i in range(5):
            intervention = HealthIntervention()
            intervention.intervention_id = str(uuid.uuid4())
            intervention.active = (i % 2 == 0)  # Even indices are active
            intervention.name = f"Intervention {i+1}"
            session.add(intervention)
        
        session.commit()
        
        # Query active only
        active_interventions = session.query(HealthIntervention).filter_by(
            active=True
        ).all()
        
        assert len(active_interventions) == 3  # Indices 0, 2, 4

