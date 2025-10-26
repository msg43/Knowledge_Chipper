"""
Integration tests for System 2 Orchestrator.

Tests the complete flow of job creation, execution, and tracking.
"""

import asyncio
from datetime import datetime

import pytest

from knowledge_system.core.system2_orchestrator import (
    System2Orchestrator,
    get_orchestrator,
)
from knowledge_system.database import DatabaseService
from knowledge_system.database.system2_models import Job, JobRun
from knowledge_system.errors import ErrorCode, KnowledgeSystemError


@pytest.fixture
def orchestrator(test_database: DatabaseService) -> System2Orchestrator:
    """Create orchestrator with test database."""
    return System2Orchestrator(test_database)


class TestJobCreation:
    """Test job creation and management."""

    def test_create_job(self, orchestrator: System2Orchestrator):
        """Test creating a new job."""
        job_id = orchestrator.create_job(
            job_type="mine",
            input_id="test_episode_001",
            config={"model": "gpt-3.5-turbo"},
            auto_process=True,
        )

        assert job_id.startswith("mine_test_episode_001")

        # Verify job in database
        with orchestrator.db_service.get_session() as session:
            job = session.query(Job).filter_by(job_id=job_id).first()
            assert job is not None
            assert job.job_type == "mine"
            assert job.input_id == "test_episode_001"
            assert job.auto_process == "true"

    def test_create_duplicate_job(self, orchestrator: System2Orchestrator):
        """Test creating duplicate job returns same ID."""
        config = {"model": "gpt-3.5-turbo"}

        job_id1 = orchestrator.create_job("mine", "episode_001", config)
        job_id2 = orchestrator.create_job("mine", "episode_001", config)

        assert job_id1 == job_id2

    def test_create_job_run(self, orchestrator: System2Orchestrator):
        """Test creating a job run."""
        job_id = orchestrator.create_job("mine", "episode_001", {})
        run_id = orchestrator.create_job_run(job_id)

        assert run_id.startswith(f"{job_id}_run_")

        # Verify in database
        with orchestrator.db_service.get_session() as session:
            job_run = session.query(JobRun).filter_by(run_id=run_id).first()
            assert job_run is not None
            assert job_run.job_id == job_id
            assert job_run.attempt_number == 1
            assert job_run.status == "queued"


class TestJobExecution:
    """Test job execution flow."""

    @pytest.mark.asyncio
    async def test_process_job_success(self, orchestrator: System2Orchestrator):
        """Test successful job processing."""
        job_id = orchestrator.create_job("transcribe", "video_001", {})

        result = await orchestrator.process_job(job_id)

        assert result["status"] == "completed"
        assert "output_id" in result

        # Verify job run status
        with orchestrator.db_service.get_session() as session:
            job_run = (
                session.query(JobRun)
                .filter_by(job_id=job_id)
                .order_by(JobRun.created_at.desc())
                .first()
            )
            assert job_run.status == "succeeded"
            assert job_run.started_at is not None
            assert job_run.completed_at is not None

    @pytest.mark.asyncio
    async def test_process_job_with_auto_chain(self, orchestrator: System2Orchestrator):
        """Test job auto-chaining."""
        job_id = orchestrator.create_job(
            "transcribe", "video_001", {}, auto_process=True
        )

        result = await orchestrator.process_job(job_id)

        # Give async task time to create next job
        await asyncio.sleep(0.1)

        # Check if mine job was created
        with orchestrator.db_service.get_session() as session:
            mine_job = (
                session.query(Job)
                .filter_by(job_type="mine", input_id="episode_video_001")
                .first()
            )
            assert mine_job is not None
            assert mine_job.auto_process == "true"

    @pytest.mark.asyncio
    async def test_process_job_with_checkpoint(self, orchestrator: System2Orchestrator):
        """Test checkpoint save and resume."""
        job_id = orchestrator.create_job("mine", "episode_001", {})
        run_id = orchestrator.create_job_run(job_id)

        # Save checkpoint
        checkpoint = {"segments_processed": 10, "total_segments": 20}
        orchestrator.save_checkpoint(run_id, checkpoint)

        # Load checkpoint
        loaded = orchestrator.load_checkpoint(run_id)
        assert loaded == checkpoint

    @pytest.mark.asyncio
    async def test_resume_failed_jobs(self, orchestrator: System2Orchestrator):
        """Test resuming failed jobs."""
        # Create failed job
        job_id = orchestrator.create_job("mine", "episode_001", {})
        run_id = orchestrator.create_job_run(job_id)
        orchestrator.update_job_run_status(
            run_id, "failed", error_code=ErrorCode.PROCESSING_FAILED
        )

        # Resume failed jobs
        resumed_count = await orchestrator.resume_failed_jobs()
        assert resumed_count == 1


class TestStatusTracking:
    """Test job status tracking."""

    def test_update_job_run_status(self, orchestrator: System2Orchestrator):
        """Test updating job run status."""
        job_id = orchestrator.create_job("mine", "episode_001", {})
        run_id = orchestrator.create_job_run(job_id)

        # Update to running
        orchestrator.update_job_run_status(run_id, "running")

        with orchestrator.db_service.get_session() as session:
            job_run = session.query(JobRun).filter_by(run_id=run_id).first()
            assert job_run.status == "running"
            assert job_run.started_at is not None

        # Update to failed
        orchestrator.update_job_run_status(
            run_id,
            "failed",
            error_code=ErrorCode.LLM_API_ERROR,
            error_message="API rate limit",
        )

        with orchestrator.db_service.get_session() as session:
            job_run = session.query(JobRun).filter_by(run_id=run_id).first()
            assert job_run.status == "failed"
            assert job_run.error_code == ErrorCode.LLM_API_ERROR
            assert job_run.error_message == "API rate limit"
            assert job_run.completed_at is not None

    @pytest.mark.asyncio
    async def test_list_jobs(self, orchestrator: System2Orchestrator):
        """Test listing jobs with filters."""
        # Create test jobs
        orchestrator.create_job("transcribe", "video_001", {})
        orchestrator.create_job("mine", "episode_001", {})
        orchestrator.create_job("mine", "episode_002", {})

        # List all jobs
        all_jobs = await orchestrator.list_jobs()
        assert len(all_jobs) == 3

        # List by type
        mine_jobs = await orchestrator.list_jobs(job_type="mine")
        assert len(mine_jobs) == 2
        assert all(j["job_type"] == "mine" for j in mine_jobs)


class TestLLMTracking:
    """Test LLM request/response tracking."""

    def test_track_llm_request(self, orchestrator: System2Orchestrator):
        """Test tracking LLM requests."""
        job_id = orchestrator.create_job("mine", "episode_001", {})
        run_id = orchestrator.create_job_run(job_id)
        orchestrator._current_job_run_id = run_id

        request_id = orchestrator.track_llm_request(
            provider="openai",
            model="gpt-3.5-turbo",
            request_payload={"messages": [{"role": "user", "content": "Test"}]},
        )

        assert request_id.startswith("llm_req_")

        # Verify in database
        from knowledge_system.database.system2_models import LLMRequest

        with orchestrator.db_service.get_session() as session:
            request = session.query(LLMRequest).filter_by(request_id=request_id).first()
            assert request is not None
            assert request.job_run_id == run_id
            assert request.provider == "openai"
            assert request.model == "gpt-3.5-turbo"

    def test_track_llm_response(self, orchestrator: System2Orchestrator):
        """Test tracking LLM responses."""
        # Create request first
        job_id = orchestrator.create_job("mine", "episode_001", {})
        run_id = orchestrator.create_job_run(job_id)
        orchestrator._current_job_run_id = run_id

        request_id = orchestrator.track_llm_request(
            "openai", "gpt-3.5-turbo", {"test": "payload"}
        )

        # Track response
        orchestrator.track_llm_response(
            request_id,
            response_payload={
                "content": "Test response",
                "usage": {"total_tokens": 100},
            },
            response_time_ms=500,
        )

        # Verify in database
        from knowledge_system.database.system2_models import LLMResponse

        with orchestrator.db_service.get_session() as session:
            response = (
                session.query(LLMResponse).filter_by(request_id=request_id).first()
            )
            assert response is not None
            assert response.latency_ms == 500
            assert response.total_tokens == 100


class TestErrorHandling:
    """Test error handling in orchestrator."""

    @pytest.mark.asyncio
    async def test_process_unknown_job_type(self, orchestrator: System2Orchestrator):
        """Test processing unknown job type."""
        job_id = orchestrator.create_job("unknown_type", "test_001", {})

        with pytest.raises(KnowledgeSystemError) as exc_info:
            await orchestrator.process_job(job_id)

        assert exc_info.value.error_code == ErrorCode.INVALID_INPUT

    @pytest.mark.asyncio
    async def test_process_nonexistent_job(self, orchestrator: System2Orchestrator):
        """Test processing non-existent job."""
        with pytest.raises(KnowledgeSystemError) as exc_info:
            await orchestrator.process_job("nonexistent_job_id")

        assert exc_info.value.error_code == ErrorCode.PROCESSING_FAILED


class TestSingletonBehavior:
    """Test singleton pattern."""

    def test_get_orchestrator_singleton(self, test_database: DatabaseService):
        """Test orchestrator singleton behavior."""
        orch1 = get_orchestrator(test_database)
        orch2 = get_orchestrator(test_database)

        assert orch1 is orch2
