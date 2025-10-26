"""
Comprehensive Real System2 Testing Suite

Tests the complete System2 orchestration functionality with real LLM integration,
job tracking, and database operations.

This replaces:
- tests/system2/test_orchestrator.py
- tests/system2/test_orchestrator_integration.py
- tests/system2/test_llm_adapter_real.py
- tests/integration/test_system2_orchestrator.py
- tests/integration/test_system2_database.py
"""

import asyncio
import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from knowledge_system.core.system2_orchestrator import (
    System2Orchestrator,
    get_orchestrator,
)
from knowledge_system.database import DatabaseService
from knowledge_system.database.system2_models import (
    Job,
    JobRun,
    LLMRequest,
    LLMResponse,
)
from knowledge_system.errors import ErrorCode, KnowledgeSystemError


@pytest.fixture
def orchestrator(test_database: DatabaseService) -> System2Orchestrator:
    """Create orchestrator with test database."""
    return System2Orchestrator(test_database)


@pytest.fixture
def sample_transcript_file():
    """Create a sample transcript file for testing."""
    content = """
# Test Transcript

This is a test transcript about artificial intelligence and machine learning.

AI has transformed many industries including healthcare and finance.

Machine learning models require large datasets to train effectively.

Geoffrey Hinton is a pioneer in deep learning research.

Neural networks are inspired by biological neural networks in the human brain.

Deep learning uses multiple layers of neural networks to learn hierarchical representations.
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        file_path = f.name

    yield file_path

    # Cleanup
    Path(file_path).unlink(missing_ok=True)


class TestRealJobCreation:
    """Test job creation and management with real database operations."""

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


class TestRealJobExecution:
    """Test job execution flow with real processing."""

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


class TestRealStatusTracking:
    """Test job status tracking with real database operations."""

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


class TestRealLLMTracking:
    """Test LLM request/response tracking with real database operations."""

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
        with orchestrator.db_service.get_session() as session:
            response = (
                session.query(LLMResponse).filter_by(request_id=request_id).first()
            )
            assert response is not None
            assert response.latency_ms == 500
            assert response.total_tokens == 100


class TestRealErrorHandling:
    """Test error handling in orchestrator with real scenarios."""

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


class TestRealSingletonBehavior:
    """Test singleton pattern with real database operations."""

    def test_get_orchestrator_singleton(self, test_database: DatabaseService):
        """Test orchestrator singleton behavior."""
        orch1 = get_orchestrator(test_database)
        orch2 = get_orchestrator(test_database)

        assert orch1 is orch2


class TestRealMiningIntegration:
    """Test real mining integration with System2 orchestration."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_mining_pipeline(
        self, test_database: DatabaseService, sample_transcript_file
    ):
        """Test complete mining from transcript to database."""
        orchestrator = System2Orchestrator(test_database)

        episode_id = "episode_integration_test"

        # Create job
        job_id = orchestrator.create_job(
            job_type="mine",
            input_id=episode_id,
            config={
                "file_path": sample_transcript_file,
                "miner_model": "ollama:qwen2.5:7b-instruct",
            },
        )

        # Verify job was created
        with test_database.get_session() as session:
            job = session.query(Job).filter_by(job_id=job_id).first()
            assert job is not None
            assert job.job_type == "mine"

        # Process job
        result = await orchestrator.process_job(job_id)

        # Verify result
        assert result.get("status") == "succeeded"
        assert "result" in result

        # Verify database has data
        with test_database.get_session() as session:
            from src.knowledge_system.database.hce_models import Episode

            episode = session.query(Episode).filter_by(episode_id=episode_id).first()
            assert episode is not None

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_pipeline_with_all_stages(
        self, test_database: DatabaseService, sample_transcript_file
    ):
        """Test pipeline with all stages (transcribe, mine, flagship)."""
        orchestrator = System2Orchestrator(test_database)

        # Create transcribe job
        transcribe_job_id = orchestrator.create_job(
            job_type="transcribe",
            input_id="test_video",
            config={"file_path": sample_transcript_file},
            auto_process=True,
        )

        # Process transcribe job
        result = await orchestrator.process_job(transcribe_job_id)
        assert result.get("status") == "succeeded"

        # Give time for auto-chain to create mine job
        await asyncio.sleep(0.1)

        # Check if mine job was created
        with test_database.get_session() as session:
            mine_job = (
                session.query(Job)
                .filter_by(job_type="mine", input_id="episode_test_video")
                .first()
            )
            assert mine_job is not None
            assert mine_job.auto_process == "true"


class TestRealDatabaseOperations:
    """Test real database operations with System2 models."""

    def test_job_table_operations(self, test_database: DatabaseService):
        """Test Job table CRUD operations."""
        with test_database.get_session() as session:
            # Create job
            job = Job(
                job_id="test_job_1",
                job_type="transcribe",
                input_id="test_video_1",
                config_json='{"model": "gpt-3.5-turbo"}',
                auto_process="false",
            )
            session.add(job)
            session.commit()

            # Read job
            retrieved_job = session.query(Job).filter_by(job_id="test_job_1").first()
            assert retrieved_job is not None
            assert retrieved_job.job_type == "transcribe"
            assert retrieved_job.input_id == "test_video_1"

            # Update job
            retrieved_job.auto_process = "true"
            session.commit()

            # Verify update
            updated_job = session.query(Job).filter_by(job_id="test_job_1").first()
            assert updated_job.auto_process == "true"

            # Delete job
            session.delete(updated_job)
            session.commit()

            # Verify deletion
            deleted_job = session.query(Job).filter_by(job_id="test_job_1").first()
            assert deleted_job is None

    def test_job_run_status_transitions(self, test_database: DatabaseService):
        """Test JobRun table with status transitions."""
        with test_database.get_session() as session:
            # Create job and run
            job = Job(
                job_id="test_job_2",
                job_type="mine",
                input_id="test_episode_2",
                config_json="{}",
                auto_process="false",
            )
            session.add(job)
            session.commit()

            job_run = JobRun(
                run_id="test_job_2_run_1",
                job_id="test_job_2",
                attempt_number=1,
                status="queued",
            )
            session.add(job_run)
            session.commit()

            # Test status transitions
            job_run.status = "running"
            job_run.started_at = datetime.utcnow()
            session.commit()

            job_run.status = "succeeded"
            job_run.completed_at = datetime.utcnow()
            session.commit()

            # Verify final state
            final_run = (
                session.query(JobRun).filter_by(run_id="test_job_2_run_1").first()
            )
            assert final_run.status == "succeeded"
            assert final_run.started_at is not None
            assert final_run.completed_at is not None

    def test_llm_request_response_tracking(self, test_database: DatabaseService):
        """Test LLMRequest and LLMResponse tracking."""
        with test_database.get_session() as session:
            # Create job and run
            job = Job(
                job_id="test_job_3",
                job_type="mine",
                input_id="test_episode_3",
                config_json="{}",
                auto_process="false",
            )
            session.add(job)
            session.commit()

            job_run = JobRun(
                run_id="test_job_3_run_1",
                job_id="test_job_3",
                attempt_number=1,
                status="running",
            )
            session.add(job_run)
            session.commit()

            # Create LLM request
            llm_request = LLMRequest(
                request_id="llm_req_test_1",
                job_run_id="test_job_3_run_1",
                provider="openai",
                model="gpt-3.5-turbo",
                temperature=0.7,
                request_json='{"messages": [{"role": "user", "content": "Test"}]}',
            )
            session.add(llm_request)
            session.commit()

            # Create LLM response
            llm_response = LLMResponse(
                request_id="llm_req_test_1",
                completion_tokens=50,
                prompt_tokens=100,
                total_tokens=150,
                latency_ms=2500,
                response_json='{"content": "Test response"}',
            )
            session.add(llm_response)
            session.commit()

            # Verify tracking
            request = (
                session.query(LLMRequest).filter_by(request_id="llm_req_test_1").first()
            )
            response = (
                session.query(LLMResponse)
                .filter_by(request_id="llm_req_test_1")
                .first()
            )

            assert request is not None
            assert response is not None
            assert request.provider == "openai"
            assert response.total_tokens == 150
            assert response.latency_ms == 2500

    def test_optimistic_locking(self, test_database: DatabaseService):
        """Test optimistic locking with updated_at."""
        with test_database.get_session() as session:
            # Create job
            job = Job(
                job_id="test_job_4",
                job_type="mine",
                input_id="test_episode_4",
                config_json="{}",
                auto_process="false",
            )
            session.add(job)
            session.commit()

            # Get initial updated_at
            initial_updated_at = job.updated_at

            # Update job
            job.auto_process = "true"
            session.commit()

            # Verify updated_at changed
            assert job.updated_at > initial_updated_at

    def test_foreign_key_constraints(self, test_database: DatabaseService):
        """Test foreign key constraints."""
        with test_database.get_session() as session:
            # Try to create JobRun without Job (should fail)
            job_run = JobRun(
                run_id="test_job_5_run_1",
                job_id="nonexistent_job",
                attempt_number=1,
                status="queued",
            )
            session.add(job_run)

            with pytest.raises(IntegrityError):
                session.commit()

    def test_wal_mode_configuration(self, test_database: DatabaseService):
        """Test WAL mode configuration."""
        with test_database.get_session() as session:
            # Check WAL mode is enabled
            result = session.execute(text("PRAGMA journal_mode"))
            journal_mode = result.fetchone()[0]
            assert journal_mode.upper() == "WAL"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
