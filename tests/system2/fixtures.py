"""
Test fixtures for System 2 components.

Provides reusable test data for job states, LLM responses,
and other System 2 components.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.knowledge_system.database import Base, DatabaseService

# All models are now in models.py (unified Base)
from src.knowledge_system.database.models import Claim
from src.knowledge_system.database.system2_models import (
    Job,
    JobRun,
    LLMRequest,
    LLMResponse,
)

# Sample transcript data
SAMPLE_TRANSCRIPT_DATA = {
    "text": "This is a sample transcript discussing AI safety and machine learning.",
    "segments": [
        {
            "id": "seg1",
            "text": "AI safety is a critical concern for modern systems.",
            "start": 0.0,
            "end": 5.0,
            "speaker": "Speaker 1",
        },
        {
            "id": "seg2",
            "text": "Machine learning models need proper validation.",
            "start": 5.0,
            "end": 10.0,
            "speaker": "Speaker 2",
        },
    ],
}

# Sample miner output following schema
SAMPLE_MINER_OUTPUT = {
    "claims": [
        {
            "claim_text": "AI safety is a critical concern for modern systems",
            "claim_type": "normative",
            "domain": "artificial_intelligence",
            "stance": "asserts",
            "evidence_spans": [
                {
                    "segment_id": "seg1",
                    "quote": "AI safety is a critical concern for modern systems.",
                    "t0": "00:00:00",
                    "t1": "00:00:05",
                }
            ],
        }
    ],
    "jargon": [
        {
            "term": "AI safety",
            "definition": "The field of research aimed at ensuring artificial intelligence systems behave safely and beneficially",
            "domain": "artificial_intelligence",
            "evidence_spans": [
                {
                    "segment_id": "seg1",
                    "quote": "AI safety is a critical concern for modern systems.",
                    "t0": "00:00:00",
                    "t1": "00:00:05",
                }
            ],
        }
    ],
    "people": [],
    "mental_models": [
        {
            "name": "Risk-based AI development",
            "definition": "The approach of prioritizing safety considerations in AI system design",
            "evidence_spans": [
                {
                    "segment_id": "seg1",
                    "quote": "AI safety is a critical concern for modern systems.",
                    "t0": "00:00:00",
                    "t1": "00:00:05",
                }
            ],
        }
    ],
}

# Sample flagship output following schema
SAMPLE_FLAGSHIP_OUTPUT = {
    "evaluated_claims": [
        {
            "original_claim_text": "AI safety is a critical concern for modern systems",
            "decision": "accept",
            "refined_claim_text": "AI safety represents a critical concern for the development and deployment of modern AI systems",
            "importance": 8,
            "novelty": 6,
            "confidence_final": 9,
            "reasoning": "This is a well-established and important claim in the AI safety field",
            "rank": 1,
        }
    ],
    "summary_assessment": {
        "total_claims_processed": 1,
        "claims_accepted": 1,
        "claims_rejected": 0,
        "key_themes": ["AI safety", "system design"],
        "overall_quality": "high",
    },
}


@pytest.fixture
def test_db_service():
    """Create a test database service with in-memory SQLite."""
    # Use in-memory database for tests
    db_service = DatabaseService("sqlite:///:memory:")

    # Run System 2 migration
    from src.knowledge_system.database.migrations.system2_migration import (
        migrate_to_system2,
    )

    with db_service.get_session() as session:
        migrate_to_system2(session)

    return db_service


@pytest.fixture
def sample_job(test_db_service):
    """Create a sample job for testing."""
    job_id = f"test-job-{uuid.uuid4().hex[:8]}"

    with test_db_service.get_session() as session:
        job = Job(
            job_id=job_id,
            job_type="transcribe",
            input_id="test_video_123",
            config_json={"source": "test"},
            auto_process="false",
        )
        session.add(job)
        session.commit()
        session.refresh(job)

    return job


@pytest.fixture
def sample_job_run(test_db_service, sample_job):
    """Create a sample job run for testing."""
    run_id = f"test-run-{uuid.uuid4().hex[:8]}"

    with test_db_service.get_session() as session:
        job_run = JobRun(
            run_id=run_id,
            job_id=sample_job.job_id,
            status="running",
            started_at=datetime.utcnow(),
        )
        session.add(job_run)
        session.commit()
        session.refresh(job_run)

    return job_run


@pytest.fixture
def sample_llm_request(test_db_service, sample_job_run):
    """Create a sample LLM request for testing."""
    request_id = f"test-req-{uuid.uuid4().hex[:8]}"

    with test_db_service.get_session() as session:
        llm_request = LLMRequest(
            request_id=request_id,
            job_run_id=sample_job_run.run_id,
            provider="openai",
            model="gpt-4",
            prompt_tokens=100,
            completion_tokens=200,
            total_tokens=300,
            cost_usd=0.01,
            latency_seconds=2.5,
            request_json={
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Extract claims from this text."},
                ]
            },
        )
        session.add(llm_request)
        session.commit()
        session.refresh(llm_request)

    return llm_request


@pytest.fixture
def sample_llm_response(test_db_service, sample_llm_request):
    """Create a sample LLM response for testing."""
    response_id = f"test-res-{uuid.uuid4().hex[:8]}"

    with test_db_service.get_session() as session:
        llm_response = LLMResponse(
            response_id=response_id,
            request_id=sample_llm_request.request_id,
            response_json={
                "choices": [{"message": {"content": json.dumps(SAMPLE_MINER_OUTPUT)}}]
            },
            status_code=200,
        )
        session.add(llm_response)
        session.commit()
        session.refresh(llm_response)

    return llm_response


@pytest.fixture
def sample_episode(test_db_service):
    """Create a sample episode for testing."""
    episode_id = f"test-episode-{uuid.uuid4().hex[:8]}"

    with test_db_service.get_session() as session:
        # Episode from claim_models uses source_id (not video_id)
        episode = Episode(
            episode_id=episode_id,
            source_id="test_video_123",  # models.Episode uses source_id
            title="Test Episode: AI Safety Discussion",
            recorded_at=datetime.utcnow().isoformat(),
        )
        session.add(episode)
        session.commit()
        session.refresh(episode)

    return episode


@pytest.fixture
def sample_claim(test_db_service, sample_episode):
    """Create a sample claim for testing."""
    claim_id = f"test-claim-{uuid.uuid4().hex[:8]}"

    with test_db_service.get_session() as session:
        # Claim from models has single PK (claim_id), not composite PK
        claim = Claim(
            claim_id=claim_id,
            episode_id=sample_episode.episode_id,  # Still need episode_id for relationship
            canonical="AI safety is a critical concern for modern systems",
            claim_type="normative",
            tier="A",
            first_mention_ts="00:00:00",
            # models.Claim uses separate score columns, not scores_json
            importance_score=0.8,
            specificity_score=0.6,
            verifiability_score=0.9,
        )
        session.add(claim)
        session.commit()
        session.refresh(claim)

    return claim


class MockLLMAdapter:
    """Mock LLM adapter for testing."""

    def __init__(self, mock_responses: dict[str, Any] = None):
        self.mock_responses = mock_responses or {}
        self.call_history = []

    def call_llm(
        self,
        provider: str,
        model: str,
        prompt: str,
        job_run_id: str = None,
        max_tokens: int = None,
        temperature: float = 0.7,
        response_format: str = None,
        job_type: str = "mining",
    ) -> dict[str, Any]:
        """Mock LLM call that returns predefined responses."""
        call_data = {
            "provider": provider,
            "model": model,
            "prompt": prompt[:100],  # Store truncated prompt
            "job_run_id": job_run_id,
            "job_type": job_type,
        }
        self.call_history.append(call_data)

        # Return appropriate mock response based on job type
        if job_type == "mining":
            response_text = json.dumps(SAMPLE_MINER_OUTPUT)
        elif job_type == "evaluation":
            response_text = json.dumps(SAMPLE_FLAGSHIP_OUTPUT)
        else:
            response_text = '{"result": "mock response"}'

        return {
            "text": response_text,
            "completion_tokens": 200,
            "prompt_tokens": 100,
            "total_tokens": 300,
            "cost_usd": 0.01,
            "model": model,
            "provider": provider,
        }


@pytest.fixture
def mock_llm_adapter():
    """Create a mock LLM adapter for testing."""
    return MockLLMAdapter()


def create_job_states() -> list[dict[str, Any]]:
    """Create various job states for testing state transitions."""
    return [
        {
            "job_id": "job-queued",
            "job_type": "transcribe",
            "status": "queued",
            "input_id": "video_001",
            "auto_process": "true",
        },
        {
            "job_id": "job-running",
            "job_type": "mine",
            "status": "running",
            "input_id": "episode_001",
            "auto_process": "false",
            "job_run": {
                "run_id": "run-001",
                "status": "running",
                "checkpoint_json": {"last_segment_id": "seg5"},
            },
        },
        {
            "job_id": "job-completed",
            "job_type": "flagship",
            "status": "completed",
            "input_id": "episode_002",
            "auto_process": "false",
            "job_run": {
                "run_id": "run-002",
                "status": "succeeded",
                "metrics_json": {
                    "claims_evaluated": 10,
                    "claims_accepted": 8,
                    "claims_rejected": 2,
                },
            },
        },
        {
            "job_id": "job-failed",
            "job_type": "upload",
            "status": "failed",
            "input_id": "episode_003",
            "auto_process": "false",
            "job_run": {
                "run_id": "run-003",
                "status": "failed",
                "error_code": "NETWORK_TIMEOUT_ERROR_MEDIUM",
                "error_message": "Connection timeout during upload",
            },
        },
    ]


def create_checkpoint_scenarios() -> list[dict[str, Any]]:
    """Create checkpoint scenarios for testing resume functionality."""
    return [
        {
            "name": "Mining checkpoint mid-batch",
            "job_type": "mine",
            "checkpoint": {
                "last_segment_id": "seg15",
                "processed_segments": 15,
                "total_segments": 50,
            },
            "expected_resume_point": "seg16",
        },
        {
            "name": "Pipeline checkpoint after transcribe",
            "job_type": "pipeline",
            "checkpoint": {
                "last_completed_stage": "transcribe",
                "transcript_id": "transcript_001",
                "next_stage": "mine",
            },
            "expected_resume_point": "mine",
        },
    ]


# Snapshot test data for schema validation
SCHEMA_SNAPSHOT_DATA = {
    "miner_input.v1": {
        "valid": [
            {
                "segment": {
                    "segment_id": "seg1",
                    "speaker": "John Doe",
                    "timestamp_start": "00:01:23",
                    "timestamp_end": "00:01:45",
                    "text": "This is the segment text.",
                }
            }
        ],
        "invalid": [
            {
                "segment": {
                    # Missing required field: segment_id
                    "speaker": "John Doe",
                    "timestamp_start": "00:01:23",
                    "timestamp_end": "00:01:45",
                    "text": "This is the segment text.",
                }
            }
        ],
    },
    "miner_output.v1": {
        "valid": [SAMPLE_MINER_OUTPUT],
        "invalid": [
            {
                # Missing required field: claims
                "jargon": [],
                "people": [],
                "mental_models": [],
            }
        ],
    },
    "flagship_input.v1": {
        "valid": [
            {
                "content_summary": "A comprehensive discussion about AI safety and machine learning best practices",
                "claims_to_evaluate": SAMPLE_MINER_OUTPUT["claims"],
            }
        ],
        "invalid": [
            {
                # Missing required field: content_summary
                "claims_to_evaluate": []
            }
        ],
    },
    "flagship_output.v1": {
        "valid": [SAMPLE_FLAGSHIP_OUTPUT],
        "invalid": [
            {
                # Missing required field: evaluated_claims
                "summary_assessment": {
                    "total_claims_processed": 0,
                    "claims_accepted": 0,
                    "claims_rejected": 0,
                    "key_themes": [],
                    "overall_quality": "low",
                }
            }
        ],
    },
}
