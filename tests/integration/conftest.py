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
        "claims_to_evaluate": [
            {
                "claim_text": "The Earth orbits around the Sun in an elliptical path",
                "claim_type": "factual",
                "stance": "asserts",
                "evidence_spans": [
                    {
                        "quote": "The Earth orbits around the Sun in an elliptical path",
                        "t0": "00:01:00",
                        "t1": "00:01:05",
                    }
                ],
                "speaker": "Dr. Jane Smith",
                "segment_id": "seg_001",
            },
            {
                "claim_text": "Johannes Kepler established the laws of planetary motion in the 17th century",
                "claim_type": "factual",
                "stance": "asserts",
                "evidence_spans": [
                    {
                        "quote": "established by Johannes Kepler in the 17th century",
                        "t0": "00:01:30",
                        "t1": "00:01:35",
                    }
                ],
                "speaker": "Dr. Jane Smith",
                "segment_id": "seg_001",
            },
        ],
        "episode_metadata": {
            "episode_id": "video_123",
            "title": "Introduction to Astronomy",
            "duration": "00:10:00",
            "speakers": ["Dr. Jane Smith"],
            "key_topics": ["astronomy", "planetary motion"],
        },
    }


@pytest.fixture
def sample_flagship_output_v2():
    """
    Provide sample flagship evaluator output in v2 schema format.
    """
    return {
        "evaluated_claims": [
            {
                "original_claim_text": "The Earth orbits around the Sun in an elliptical path",
                "decision": "accept",
                "reasoning": "Well-established scientific fact with strong evidence",
                "importance": 8.5,
                "novelty": 2.0,
                "confidence_final": 9.5,
                "rank": 1,
                "tier": "A",
            },
            {
                "original_claim_text": "Johannes Kepler established the laws of planetary motion in the 17th century",
                "decision": "accept",
                "reasoning": "Historical fact with solid evidence",
                "importance": 7.0,
                "novelty": 3.0,
                "confidence_final": 8.0,
                "rank": 2,
                "tier": "B",
            },
        ],
        "summary_assessment": {
            "total_claims_processed": 2,
            "claims_accepted": 2,
            "claims_rejected": 0,
            "claims_merged": 0,
            "claims_split": 0,
            "overall_quality": "high",
            "key_themes": ["astronomy", "planetary motion", "historical science"],
            "recommendations": "Strong educational content with well-established facts",
            "average_scores": {
                "importance": 7.75,
                "novelty": 2.5,
                "confidence": 8.75,
            },
        },
        "tier_distribution": {
            "A": 1,
            "B": 1,
            "C": 0,
        },
    }
