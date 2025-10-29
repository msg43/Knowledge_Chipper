"""
Test fixtures for System 2 components.

Provides reusable test data for:
- Miner input/output
- Flagship input/output
- Job and JobRun records
- LLM request/response tracking
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import pytest

from knowledge_system.database import DatabaseService
from knowledge_system.database.system2_models import (
    Job,
    JobRun,
    LLMRequest,
    LLMResponse,
)
from knowledge_system.processors.hce.types import Segment


@pytest.fixture
def sample_segment() -> Segment:
    """Sample segment for miner input."""
    return Segment(
        episode_id="test_episode_001",
        segment_id="seg_001",
        speaker="Speaker A",
        t0="00:00:00",
        t1="00:00:30",
        text="The Federal Reserve's quantitative easing program has fundamentally altered the relationship between monetary policy and asset prices. This creates what economists call a 'wealth effect'.",
        topic_guess="Monetary Policy",
    )


@pytest.fixture
def sample_miner_input() -> dict[str, Any]:
    """Sample miner input matching schema."""
    return {
        "segment": {
            "segment_id": "seg_001",
            "speaker": "Speaker A",
            "timestamp_start": "00:00:00",
            "timestamp_end": "00:00:30",
            "text": "The Federal Reserve's quantitative easing program has fundamentally altered the relationship between monetary policy and asset prices. This creates what economists call a 'wealth effect'.",
        },
        "context": {
            "episode_id": "test_episode_001",
            "episode_title": "Understanding Monetary Policy",
        },
    }


@pytest.fixture
def sample_miner_output() -> dict[str, Any]:
    """Sample miner output matching schema."""
    return {
        "claims": [
            {
                "claim_text": "The Federal Reserve's quantitative easing program has fundamentally altered the relationship between monetary policy and asset prices",
                "claim_type": "causal",
                "stance": "asserts",
                "context_quote": "quantitative easing program has fundamentally altered the relationship",
                "timestamp": "00:10",
                "evidence_spans": [
                    {
                        "quote": "QE has fundamentally altered the relationship",
                        "timestamp": "00:10",
                    }
                ],
            }
        ],
        "jargon": [
            {
                "term": "quantitative easing",
                "usage_context": "The Federal Reserve's quantitative easing program",
                "implied_meaning": "Central bank policy of creating money to buy assets",
                "timestamp": "00:05",
            },
            {
                "term": "wealth effect",
                "usage_context": "creates what economists call a 'wealth effect'",
                "implied_meaning": "Economic theory that rising asset values increase consumer spending",
                "timestamp": "00:25",
            },
        ],
        "people": [
            {
                "name": "Federal Reserve",
                "role_or_description": "US Central Bank",
                "context_quote": "The Federal Reserve's quantitative easing program",
                "timestamp": "00:05",
            }
        ],
        "mental_models": [
            {
                "name": "wealth effect mechanism",
                "description": "Framework explaining how monetary policy affects consumer behavior through asset price changes",
                "context_quote": "creates what economists call a 'wealth effect'",
                "timestamp": "00:25",
            }
        ],
    }


@pytest.fixture
def sample_flagship_input() -> dict[str, Any]:
    """Sample flagship input matching schema."""
    return {
        "content_summary": "Discussion of Federal Reserve monetary policy and its effects on asset markets, featuring analysis of quantitative easing programs and their distributional impacts.",
        "episode_metadata": {
            "episode_id": "test_episode_001",
            "title": "Understanding Monetary Policy",
            "duration": "00:45:00",
            "speakers": ["Speaker A", "Speaker B"],
            "key_topics": ["monetary policy", "quantitative easing", "asset prices"],
        },
        "claims_to_evaluate": [
            {
                "claim_id": "claim_001",
                "claim_text": "The Federal Reserve's quantitative easing program has fundamentally altered the relationship between monetary policy and asset prices",
                "claim_type": "causal",
                "stance": "asserts",
                "evidence_spans": [
                    {
                        "quote": "QE has completely changed how monetary policy transmits through asset markets",
                        "t0": "05:23",
                        "t1": "05:31",
                    }
                ],
                "speaker": "Speaker A",
                "segment_id": "seg_001",
            },
            {
                "claim_id": "claim_002",
                "claim_text": "QE benefits primarily wealthy asset holders",
                "claim_type": "normative",
                "stance": "asserts",
                "evidence_spans": [
                    {
                        "quote": "The distributional effects favor those who already own stocks and real estate",
                        "t0": "07:45",
                        "t1": "07:52",
                    }
                ],
                "speaker": "Speaker A",
                "segment_id": "seg_002",
            },
        ],
    }


@pytest.fixture
def sample_flagship_output() -> dict[str, Any]:
    """Sample flagship output matching schema."""
    return {
        "evaluated_claims": [
            {
                "claim_id": "claim_001",
                "original_claim_text": "The Federal Reserve's quantitative easing program has fundamentally altered the relationship between monetary policy and asset prices",
                "decision": "accept",
                "importance": 8,
                "novelty": 6,
                "confidence_final": 7,
                "reasoning": "This claim identifies a significant structural change in monetary policy transmission with substantial evidence. While not entirely novel to economists, it's an important insight for understanding modern markets.",
                "rank": 1,
                "tier": "A",
            },
            {
                "claim_id": "claim_002",
                "original_claim_text": "QE benefits primarily wealthy asset holders",
                "decision": "accept",
                "importance": 7,
                "novelty": 4,
                "confidence_final": 8,
                "reasoning": "Well-documented distributional effect of QE policy. Important for policy discussions but widely recognized.",
                "rank": 2,
                "tier": "B",
            },
        ],
        "summary_assessment": {
            "total_claims_processed": 2,
            "claims_accepted": 2,
            "claims_rejected": 0,
            "key_themes": [
                "monetary policy transmission",
                "quantitative easing effects",
                "wealth inequality",
            ],
            "overall_quality": "good",
            "recommendations": "Consider exploring more specific mechanisms and empirical evidence.",
            "average_scores": {"importance": 7.5, "novelty": 5.0, "confidence": 7.5},
        },
        "tier_distribution": {"A": 1, "B": 1, "C": 0},
    }


@pytest.fixture
def sample_job(db_service: DatabaseService) -> Job:
    """Create a sample job record."""
    with db_service.get_session() as session:
        job = Job(
            job_id="job_test_001",
            job_type="mine",
            input_id="episode_001",
            config_json={"model": "gpt-3.5-turbo", "temperature": 0.7},
            auto_process="true",
        )
        session.add(job)
        session.commit()
        return job


@pytest.fixture
def sample_job_run(sample_job: Job, db_service: DatabaseService) -> JobRun:
    """Create a sample job run record."""
    with db_service.get_session() as session:
        job_run = JobRun(
            run_id="run_test_001",
            job_id=sample_job.job_id,
            attempt_number=1,
            status="running",
            started_at=datetime.utcnow(),
            checkpoint_json={"segments_processed": 5, "total_segments": 20},
        )
        session.add(job_run)
        session.commit()
        return job_run


@pytest.fixture
def sample_llm_request(
    sample_job_run: JobRun, db_service: DatabaseService
) -> LLMRequest:
    """Create a sample LLM request record."""
    with db_service.get_session() as session:
        request = LLMRequest(
            request_id="req_test_001",
            job_run_id=sample_job_run.run_id,
            provider="openai",
            model="gpt-3.5-turbo",
            endpoint="/v1/chat/completions",
            prompt_tokens=150,
            max_tokens=500,
            temperature=0.7,
            request_json={
                "messages": [
                    {"role": "user", "content": "Extract claims from this text..."}
                ],
                "temperature": 0.7,
            },
        )
        session.add(request)
        session.commit()
        return request


@pytest.fixture
def sample_llm_response(
    sample_llm_request: LLMRequest, db_service: DatabaseService
) -> LLMResponse:
    """Create a sample LLM response record."""
    with db_service.get_session() as session:
        response = LLMResponse(
            response_id="resp_test_001",
            request_id=sample_llm_request.request_id,
            response_json={
                "content": "Here are the extracted claims...",
                "usage": {
                    "prompt_tokens": 150,
                    "completion_tokens": 200,
                    "total_tokens": 350,
                },
            },
            response_time_ms=1250,
            completion_tokens=200,
            total_tokens=350,
        )
        session.add(response)
        session.commit()
        return response


@pytest.fixture
def mock_schema_files(tmp_path: Path) -> Path:
    """Create mock schema files for testing."""
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir()

    # Write test schemas
    schemas = {
        "miner_input.v1.json": {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "required": ["segment"],
            "properties": {"segment": {"type": "object"}},
        },
        "miner_output.v1.json": {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "required": ["claims", "jargon", "people", "mental_models"],
            "properties": {
                "claims": {"type": "array"},
                "jargon": {"type": "array"},
                "people": {"type": "array"},
                "mental_models": {"type": "array"},
            },
        },
    }

    for filename, schema in schemas.items():
        with open(schema_dir / filename, "w") as f:
            json.dump(schema, f)

    return schema_dir


@pytest.fixture
def test_database(tmp_path: Path) -> DatabaseService:
    """Create a test database."""
    db_path = tmp_path / "test.db"
    db_service = DatabaseService(f"sqlite:///{db_path}")

    # Create all tables
    from knowledge_system.database.models import Base, Claim, Episode
    from knowledge_system.database.system2_models import Job, JobRun

    with db_service.engine.begin() as conn:
        Base.metadata.create_all(conn)

    return db_service


# Helper functions for test data generation


def create_test_job(
    db_service: DatabaseService,
    job_id: str | None = None,
    job_type: str = "mine",
    input_id: str = "test_input",
    config: dict[str, Any] | None = None,
    auto_process: bool = False,
) -> Job:
    """Create a test job record."""
    if config is None:
        config = {"model": "gpt-3.5-turbo"}

    # Generate job_id if not provided
    if job_id is None:
        job_id = f"job_{job_type}_{input_id}"

    with db_service.get_session() as session:
        job = Job(
            job_id=job_id,
            job_type=job_type,
            input_id=input_id,
            config_json=config,
            auto_process="true" if auto_process else "false",
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        # Detach from session so it can be used outside context
        session.expunge(job)
        return job


def create_test_job_run(
    db_service: DatabaseService,
    job_id: str,
    status: str = "queued",
    checkpoint: dict[str, Any] | None = None,
    metrics: dict[str, Any] | None = None,
) -> JobRun:
    """Create a test job run record."""
    with db_service.get_session() as session:
        # Get next attempt number
        existing_runs = session.query(JobRun).filter_by(job_id=job_id).all()
        attempt_number = len(existing_runs) + 1

        job_run = JobRun(
            run_id=f"{job_id}_run_{attempt_number}",
            job_id=job_id,
            attempt_number=attempt_number,
            status=status,
            checkpoint_json=checkpoint,
            metrics_json=metrics,
        )

        if status == "running":
            job_run.started_at = datetime.utcnow()
        elif status in ["succeeded", "failed", "cancelled"]:
            job_run.started_at = datetime.utcnow()
            job_run.completed_at = datetime.utcnow()

        session.add(job_run)
        session.commit()
        session.refresh(job_run)
        # Detach from session so it can be used outside context
        session.expunge(job_run)
        return job_run


def create_test_llm_request(
    db_service: DatabaseService,
    job_run_id: str,
    provider: str = "openai",
    model: str = "gpt-3.5-turbo",
    request_payload: dict[str, Any] | None = None,
    prompt_text: str | None = None,
) -> LLMRequest:
    """Create a test LLM request record."""
    if request_payload is None:
        request_payload = {
            "messages": [{"role": "user", "content": prompt_text or "Test prompt"}]
        }

    with db_service.get_session() as session:
        request = LLMRequest(
            request_id=f"req_{job_run_id}_{len(session.query(LLMRequest).filter_by(job_run_id=job_run_id).all()) + 1}",
            job_run_id=job_run_id,
            provider=provider,
            model=model,
            endpoint="/v1/chat/completions",
            prompt_tokens=100,
            max_tokens=500,
            temperature=0.7,
            request_json=request_payload,
        )
        session.add(request)
        session.commit()
        session.refresh(request)
        session.expunge(request)
        return request


def create_test_llm_response(
    db_service: DatabaseService,
    request_id: str,
    response_payload: dict[str, Any] | None = None,
    response_text: str | None = None,
    status: str = "success",
    tokens_used: int | None = None,
    duration_ms: int | None = None,
) -> LLMResponse:
    """Create a test LLM response record."""
    if response_payload is None:
        response_payload = {
            "content": response_text or "Test response",
            "usage": {"total_tokens": tokens_used or 200},
        }

    with db_service.get_session() as session:
        response = LLMResponse(
            response_id=f"resp_{request_id}",
            request_id=request_id,
            response_json=response_payload,
            status_code=200 if status == "success" else 500,
            latency_ms=float(duration_ms) if duration_ms else 1000.0,
            completion_tokens=(tokens_used or 200) // 2,
            total_tokens=tokens_used or 200,
        )
        session.add(response)
        session.commit()
        session.refresh(response)
        session.expunge(response)
        return response


def validate_job_state_transition(
    db_service: DatabaseService,
    job_id: str,
    expected_states: list[str],
) -> bool:
    """Validate that a job went through expected state transitions."""
    with db_service.get_session() as session:
        job_runs = (
            session.query(JobRun)
            .filter_by(job_id=job_id)
            .order_by(JobRun.created_at)
            .all()
        )

        actual_states = [run.status for run in job_runs]
        return actual_states == expected_states


def get_llm_metrics_for_job(
    db_service: DatabaseService,
    job_id: str,
) -> dict[str, Any]:
    """Get aggregated LLM metrics for a job."""
    with db_service.get_session() as session:
        job_runs = session.query(JobRun).filter_by(job_id=job_id).all()

        total_requests = 0
        total_tokens = 0
        total_time_ms = 0

        for run in job_runs:
            requests = session.query(LLMRequest).filter_by(job_run_id=run.run_id).all()
            total_requests += len(requests)

            for req in requests:
                response = (
                    session.query(LLMResponse)
                    .filter_by(request_id=req.request_id)
                    .first()
                )
                if response:
                    total_tokens += response.total_tokens or 0
                    total_time_ms += response.latency_ms or 0

        return {
            "total_requests": total_requests,
            "total_tokens": total_tokens,
            "total_time_ms": total_time_ms,
            "avg_time_per_request": total_time_ms / total_requests
            if total_requests > 0
            else 0,
        }


def cleanup_test_jobs(db_service: DatabaseService, job_id_prefix: str = "job_test"):
    """Clean up test jobs and related records."""
    with db_service.get_session() as session:
        # Delete in order to respect foreign key constraints
        jobs = session.query(Job).filter(Job.job_id.like(f"{job_id_prefix}%")).all()

        for job in jobs:
            # Delete LLM responses
            job_runs = session.query(JobRun).filter_by(job_id=job.job_id).all()
            for run in job_runs:
                requests = (
                    session.query(LLMRequest).filter_by(job_run_id=run.run_id).all()
                )
                for req in requests:
                    session.query(LLMResponse).filter_by(
                        request_id=req.request_id
                    ).delete()
                session.query(LLMRequest).filter_by(job_run_id=run.run_id).delete()

            # Delete job runs
            session.query(JobRun).filter_by(job_id=job.job_id).delete()

            # Delete job
            session.delete(job)

        session.commit()
