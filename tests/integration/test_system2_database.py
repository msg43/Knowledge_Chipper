"""
Integration tests for System 2 database operations.

Tests:
- Job table CRUD operations
- JobRun table with status transitions
- LLMRequest and LLMResponse tracking
- Optimistic locking with updated_at
- WAL mode configuration
- Foreign key constraints
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from knowledge_system.database import DatabaseService
from knowledge_system.database.system2_models import (
    Job,
    JobRun,
    LLMRequest,
    LLMResponse,
)
from tests.fixtures.system2_fixtures import (
    cleanup_test_jobs,
    create_test_job,
    create_test_job_run,
    create_test_llm_request,
    create_test_llm_response,
    validate_job_state_transition,
)


class TestJobTable:
    """Test Job table operations."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment."""
        self.db_service = DatabaseService()
        # Cleanup before to ensure clean state
        cleanup_test_jobs(self.db_service, job_id_prefix="test_job")
        yield
        # Cleanup after each test
        cleanup_test_jobs(self.db_service, job_id_prefix="test_job")

    def test_create_job(self):
        """Test creating a job."""
        job = create_test_job(
            self.db_service,
            job_id="test_job_1",
            job_type="transcribe",
            input_id="test_video_1",
        )

        assert job.job_id == "test_job_1"
        assert job.job_type == "transcribe"
        assert job.input_id == "test_video_1"
        assert job.auto_process == "false"

    def test_job_updated_at_tracking(self):
        """Test that updated_at is tracked for optimistic locking."""
        job = create_test_job(
            self.db_service,
            job_id="test_job_2",
            job_type="mine",
            input_id="test_transcript_1",
        )

        original_updated_at = job.updated_at
        assert original_updated_at is not None

        # Update job
        with self.db_service.get_session() as session:
            job_to_update = session.query(Job).filter_by(job_id="test_job_2").first()
            job_to_update.auto_process = True
            session.commit()
            session.refresh(job_to_update)

            # updated_at should change
            assert job_to_update.updated_at > original_updated_at

    def test_job_auto_process_flag(self):
        """Test auto_process flag for job chaining."""
        job = create_test_job(
            self.db_service,
            job_id="test_job_3",
            job_type="transcribe",
            input_id="test_video_2",
            auto_process=True,
        )

        assert job.auto_process == "true"

    def test_job_unique_constraint(self):
        """Test that job_id must be unique."""
        # Create first job
        job1 = create_test_job(
            self.db_service,
            job_id="test_duplicate_job",
            job_type="transcribe",
            input_id="test_video_3",
        )
        assert job1.job_id == "test_duplicate_job"

        # Attempting to create another job with same job_id should fail
        with pytest.raises(IntegrityError):
            create_test_job(
                self.db_service,
                job_id="test_duplicate_job",
                job_type="mine",
                input_id="test_transcript_2",
            )


class TestJobRunTable:
    """Test JobRun table operations."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment."""
        self.db_service = DatabaseService()
        cleanup_test_jobs(self.db_service, job_id_prefix="test_job")

        # Create a job for testing
        self.test_job = create_test_job(
            self.db_service,
            job_id="test_job_for_runs",
            job_type="transcribe",
            input_id="test_video_4",
        )

        yield
        cleanup_test_jobs(self.db_service, job_id_prefix="test_job")

    def test_create_job_run(self):
        """Test creating a job run."""
        job_run = create_test_job_run(
            self.db_service,
            job_id="test_job_for_runs",
            status="queued",
        )

        assert job_run.job_id == "test_job_for_runs"
        assert job_run.status == "queued"
        assert job_run.attempt_number == 1

    def test_job_run_status_transitions(self):
        """Test valid status transitions."""
        job_run = create_test_job_run(
            self.db_service,
            job_id="test_job_for_runs",
            status="queued",
        )

        # Transition to running (valid transition)
        with self.db_service.get_session() as session:
            run_to_update = (
                session.query(JobRun).filter_by(run_id=job_run.run_id).first()
            )
            run_to_update.status = "running"
            run_to_update.started_at = datetime.now()
            session.commit()
            session.refresh(run_to_update)

            assert run_to_update.status == "running"
            assert run_to_update.started_at is not None

        # Transition to succeeded (valid transition)
        with self.db_service.get_session() as session:
            run_to_update = (
                session.query(JobRun).filter_by(run_id=job_run.run_id).first()
            )
            run_to_update.status = "succeeded"
            run_to_update.completed_at = datetime.now()
            session.commit()
            session.refresh(run_to_update)

            assert run_to_update.status == "succeeded"
            assert run_to_update.completed_at is not None

    def test_job_run_attempt_numbers(self):
        """Test that attempt numbers increment correctly."""
        # Create first run
        run1 = create_test_job_run(
            self.db_service,
            job_id="test_job_for_runs",
            status="failed",
        )
        assert run1.attempt_number == 1

        # Create second run (retry)
        run2 = create_test_job_run(
            self.db_service,
            job_id="test_job_for_runs",
            status="queued",
        )
        assert run2.attempt_number == 2

    def test_job_run_metrics_tracking(self):
        """Test metrics_json storage."""
        job_run = create_test_job_run(
            self.db_service,
            job_id="test_job_for_runs",
            status="succeeded",
            metrics={"duration": 120.5, "tokens_used": 1500},
        )

        assert job_run.metrics_json is not None
        assert "duration" in job_run.metrics_json
        assert job_run.metrics_json["duration"] == 120.5

    def test_job_run_foreign_key(self):
        """Test foreign key constraint to Job table."""
        # Attempting to create run for non-existent job should fail
        with pytest.raises(IntegrityError):
            create_test_job_run(
                self.db_service,
                job_id="nonexistent_job",
                status="queued",
            )


class TestLLMRequestResponseTable:
    """Test LLMRequest and LLMResponse table operations."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment."""
        self.db_service = DatabaseService()
        cleanup_test_jobs(self.db_service, job_id_prefix="test_job")

        # Create job and run for testing
        self.test_job = create_test_job(
            self.db_service,
            job_id="test_job_for_llm",
            job_type="mine",
            input_id="test_transcript_3",
        )

        self.test_run = create_test_job_run(
            self.db_service,
            job_id="test_job_for_llm",
            status="running",
        )

        yield
        cleanup_test_jobs(self.db_service, job_id_prefix="test_job")

    def test_create_llm_request(self):
        """Test creating an LLM request."""
        llm_request = create_test_llm_request(
            self.db_service,
            job_run_id=self.test_run.run_id,
            provider="openai",
            model="gpt-4",
        )

        assert llm_request.job_run_id == self.test_run.run_id
        assert llm_request.provider == "openai"
        assert llm_request.model == "gpt-4"

    def test_create_llm_response(self):
        """Test creating an LLM response."""
        llm_request = create_test_llm_request(
            self.db_service,
            job_run_id=self.test_run.run_id,
            provider="openai",
            model="gpt-4",
        )

        llm_response = create_test_llm_response(
            self.db_service,
            request_id=llm_request.request_id,
            status="success",
        )

        assert llm_response.request_id == llm_request.request_id
        assert llm_response.status_code == 200

    def test_llm_request_prompt_tracking(self):
        """Test that prompts are stored correctly."""
        llm_request = create_test_llm_request(
            self.db_service,
            job_run_id=self.test_run.run_id,
            provider="openai",
            model="gpt-4",
            prompt_text="Extract key claims from this transcript",
        )

        # Prompt text is stored in request_json
        assert "Extract key claims from this transcript" in str(
            llm_request.request_json
        )

    def test_llm_response_content_tracking(self):
        """Test that response content is stored."""
        llm_request = create_test_llm_request(
            self.db_service,
            job_run_id=self.test_run.run_id,
            provider="openai",
            model="gpt-4",
        )

        response_content = '{"claims": ["claim1", "claim2"]}'
        llm_response = create_test_llm_response(
            self.db_service,
            request_id=llm_request.request_id,
            status="success",
            response_text=response_content,
        )

        # Response text is stored in response_json
        assert response_content in str(llm_response.response_json)

    def test_llm_metrics_tracking(self):
        """Test metrics tracking for LLM calls."""
        llm_request = create_test_llm_request(
            self.db_service,
            job_run_id=self.test_run.run_id,
            provider="openai",
            model="gpt-4",
        )

        llm_response = create_test_llm_response(
            self.db_service,
            request_id=llm_request.request_id,
            status="success",
            tokens_used=1500,
            duration_ms=2500,
        )

        assert llm_response.total_tokens == 1500
        assert llm_response.latency_ms == 2500.0

    def test_llm_foreign_keys(self):
        """Test foreign key constraints."""
        # Request must reference valid run
        with pytest.raises(IntegrityError):
            create_test_llm_request(
                self.db_service,
                job_run_id="nonexistent_run",
                provider="openai",
                model="gpt-4",
            )

        # Response must reference valid request
        with pytest.raises(IntegrityError):
            create_test_llm_response(
                self.db_service,
                request_id="nonexistent_request",
                status="success",
            )


class TestDatabaseConfiguration:
    """Test database configuration for System 2."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment."""
        self.db_service = DatabaseService()

    def test_wal_mode_enabled(self):
        """Test that WAL mode is enabled for better concurrency."""
        with self.db_service.get_session() as session:
            result = session.execute(text("PRAGMA journal_mode")).fetchone()

            # WAL mode should be enabled (case-insensitive)
            assert result[0].lower() == "wal"

    def test_foreign_keys_enabled(self):
        """Test that foreign key constraints are enforced."""
        with self.db_service.get_session() as session:
            result = session.execute(text("PRAGMA foreign_keys")).fetchone()

            # Foreign keys should be enabled (1 = on)
            assert result[0] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
