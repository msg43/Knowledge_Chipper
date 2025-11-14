"""
Pytest fixtures specific to integration tests.
"""
from collections.abc import Generator
from pathlib import Path

import pytest

from knowledge_system.database import DatabaseService


@pytest.fixture
def integration_test_database() -> Generator[DatabaseService, None, None]:
    """
    Provide a test database with full schema for integration tests.

    Unlike the basic test_database fixture, this one includes all tables
    and relationships needed for integration testing.
    """
    # Use in-memory database
    db_service = DatabaseService("sqlite:///:memory:")

    # Ensure all tables are created
    with db_service.get_session() as session:
        # Tables are auto-created by DatabaseService.__init__
        session.commit()

    yield db_service

    # Cleanup
    db_service.close()


@pytest.fixture
def sample_miner_input_v2():
    """
    Provide sample miner input in v2 schema format.
    """
    return {
        "segment": {
            "segment_id": "seg_001",
            "speaker": "Dr. Jane Smith",
            "timestamp_start": "00:01:00",
            "timestamp_end": "00:02:00",
            "text": "The Earth orbits around the Sun in an elliptical path. This fundamental fact of astronomy was established by Johannes Kepler in the 17th century. The field of orbital mechanics explains how planets move around stars under gravitational forces.",
            "topic_guess": "astronomy",
        },
        "context": {
            "source_id": "video_123",
            "source_title": "Introduction to Astronomy",
            "content_type": "educational",
            "prior_segments": [],
            "subsequent_segments": [],
        },
    }


@pytest.fixture
def sample_miner_output_v2():
    """
    Provide sample miner output in v2 schema format.
    """
    return {
        "claims": [
            {
                "claim_text": "The Earth orbits around the Sun in an elliptical path",
                "claim_type": "factual",
                "domain": "astronomy",
                "stance": "asserts",
                "evidence_spans": [
                    {
                        "segment_id": "seg_001",
                        "quote": "The Earth orbits around the Sun in an elliptical path",
                        "t0": "00:01:00",
                        "t1": "00:01:05",
                        "context_text": "The Earth orbits around the Sun in an elliptical path. This fundamental fact of astronomy was established by Johannes Kepler.",
                        "context_type": "extended",
                    }
                ],
            }
        ],
        "jargon": [
            {
                "term": "elliptical path",
                "definition": "An oval-shaped orbital trajectory",
                "domain": "astronomy",
                "evidence_spans": [
                    {
                        "segment_id": "seg_001",
                        "quote": "elliptical path",
                        "t0": "00:01:03",
                        "t1": "00:01:05",
                        "context_text": "The Earth orbits around the Sun in an elliptical path.",
                    }
                ],
            },
            {
                "term": "orbital mechanics",
                "definition": "The study of how objects move in space under gravitational forces",
                "domain": "physics",
                "evidence_spans": [
                    {
                        "segment_id": "seg_001",
                        "quote": "orbital mechanics",
                        "t0": "00:01:50",
                        "t1": "00:01:52",
                        "context_text": "The field of orbital mechanics explains how planets move around stars.",
                    }
                ],
            },
        ],
        "people": [
            {
                "name": "Johannes Kepler",
                "normalized_name": "Johannes Kepler",
                "entity_type": "person",
                "role_or_description": "astronomer",
                "mentions": [
                    {
                        "segment_id": "seg_001",
                        "surface_form": "Johannes Kepler",
                        "quote": "This fundamental fact of astronomy was established by Johannes Kepler in the 17th century.",
                        "t0": "00:01:30",
                        "t1": "00:01:32",
                    }
                ],
            }
        ],
        "mental_models": [
            {
                "name": "orbital mechanics framework",
                "definition": "The study of how objects move in space under gravitational forces",
                "evidence_spans": [
                    {
                        "segment_id": "seg_001",
                        "quote": "orbital mechanics explains how planets move around stars under gravitational forces",
                        "t0": "00:01:50",
                        "t1": "00:01:57",
                        "context_text": "The field of orbital mechanics explains how planets move around stars under gravitational forces.",
                    }
                ],
            }
        ],
        "concepts": [
            {
                "concept": "gravitational forces",
                "description": "The attractive force between objects with mass",
                "domain": "physics",
                "evidence_spans": [
                    {
                        "segment_id": "seg_001",
                        "quote": "gravitational forces",
                        "t0": "00:01:55",
                        "t1": "00:01:57",
                        "context_text": "The field of orbital mechanics explains how planets move around stars under gravitational forces.",
                    }
                ],
            }
        ],
    }


@pytest.fixture
def sample_flagship_input_v2():
    """
    Provide sample flagship evaluator input in v2 schema format.
    """
    return {
        "content_summary": "An educational video about astronomy covering the basics of planetary motion and orbital mechanics. The speaker discusses how Earth orbits the Sun and introduces key historical figures in astronomy.",
        "claims": [
            {
                "claim_text": "The Earth orbits around the Sun in an elliptical path",
                "claim_type": "factual",
                "domain": "astronomy",
                "stance": "asserts",
                "evidence_spans": [
                    {
                        "segment_id": "seg_001",
                        "quote": "The Earth orbits around the Sun in an elliptical path",
                        "t0": "00:01:00",
                        "t1": "00:01:05",
                    }
                ],
            },
            {
                "claim_text": "Johannes Kepler established the laws of planetary motion in the 17th century",
                "claim_type": "factual",
                "domain": "astronomy",
                "stance": "asserts",
                "evidence_spans": [
                    {
                        "segment_id": "seg_001",
                        "quote": "established by Johannes Kepler in the 17th century",
                        "t0": "00:01:30",
                        "t1": "00:01:35",
                    }
                ],
            },
        ],
        "metadata": {
            "source_id": "video_123",
            "source_title": "Introduction to Astronomy",
            "total_segments": 10,
            "extraction_timestamp": "2025-11-10T00:00:00Z",
        },
    }


@pytest.fixture
def sample_flagship_output_v2():
    """
    Provide sample flagship evaluator output in v2 schema format.
    """
    return {
        "flagged_claims": [
            {
                "claim_text": "The Earth orbits around the Sun in an elliptical path",
                "tier": "high",
                "confidence": 0.95,
                "reasoning": "Well-established scientific fact with strong evidence",
                "domain": "astronomy",
            }
        ],
        "summary_assessment": {
            "overall_quality": "high",
            "claim_density": 0.2,
            "domain_coverage": ["astronomy", "physics"],
            "recommended_tier": "high",
        },
        "metadata": {
            "evaluator_model": "gpt-4",
            "evaluation_timestamp": "2025-11-10T00:00:00Z",
            "total_claims_evaluated": 2,
            "flagged_count": 1,
        },
    }
