"""
Integration tests for System 2 Orchestrator.

Tests job creation, execution, state transitions, and error handling.
"""

from unittest.mock import Mock, patch

import pytest

from src.knowledge_system.core.system2_orchestrator import System2Orchestrator
from src.knowledge_system.database.system2_models import Job, JobRun
from src.knowledge_system.errors import ErrorCode, KnowledgeSystemError

from .fixtures import (
    SAMPLE_TRANSCRIPT_DATA,
    create_job_states,
    mock_llm_adapter,
    sample_job,
    sample_job_run,
    test_db_service,
)


class TestSystem2Orchestrator:
    """Test cases for System2Orchestrator."""

    def test_orchestrator_initialization(self, test_db_service):
        """Test orchestrator initializes correctly."""
        orchestrator = System2Orchestrator(test_db_service)

        assert orchestrator.db_service is not None
        assert orchestrator.coordinator is not None

    def test_create_job(self, test_db_service):
        """Test job creation."""
        orchestrator = System2Orchestrator(test_db_service)

        job_id = orchestrator.create_job(
            "transcribe",
            "test_video_123",
            config={"source": "test"},
            auto_process=True,
        )

        assert job_id.startswith("transcribe-")

        # Verify job was created in database
        with test_db_service.get_session() as session:
            job = session.query(Job).filter_by(job_id=job_id).first()
            assert job is not None
            assert job.job_type == "transcribe"
            assert job.input_id == "test_video_123"
            assert job.auto_process == "true"
            assert job.status == "queued"

    def test_execute_transcribe_job(self, test_db_service, mock_llm_adapter):
        """Test execution of transcribe job."""
        orchestrator = System2Orchestrator(test_db_service)
        orchestrator.llm_adapter = mock_llm_adapter

        # Mock the YouTube transcript processor
        with patch.object(
            orchestrator.youtube_transcript_processor, "process"
        ) as mock_process:
            mock_result = Mock()
            mock_result.success = True
            mock_result.data = SAMPLE_TRANSCRIPT_DATA
            mock_process.return_value = mock_result

            job_id = orchestrator.create_job(
                "transcribe", "test_video_123", config={"source": "youtube"}
            )

            result = orchestrator.execute_job(job_id)

            assert result["status"] == "succeeded"
            assert "transcript_id" in result
            assert result["source"] == "youtube"

    def test_execute_mine_job(self, test_db_service, sample_episode, mock_llm_adapter):
        """Test execution of mine job."""
        orchestrator = System2Orchestrator(test_db_service)

        # Create transcript for the episode
        from src.knowledge_system.database.models import Transcript

        with test_db_service.get_session() as session:
            transcript = Transcript(
                video_id=sample_episode.video_id,
                transcript_text=SAMPLE_TRANSCRIPT_DATA["text"],
                transcript_segments_json=SAMPLE_TRANSCRIPT_DATA["segments"],
            )
            session.add(transcript)
            session.commit()

        # Mock the unified miner
        with patch(
            "src.knowledge_system.core.system2_orchestrator.UnifiedMinerSystem2"
        ) as MockMiner:
            mock_miner = Mock()
            mock_miner.mine_segment.return_value = Mock(
                claims=[
                    {
                        "claim_text": "Test claim",
                        "claim_type": "factual",
                        "stance": "asserts",
                        "evidence_spans": [],
                    }
                ],
                people=[],
                mental_models=[],
                jargon=[],
            )
            MockMiner.return_value = mock_miner
            orchestrator._unified_miner = mock_miner

            job_id = orchestrator.create_job(
                "mine",
                sample_episode.episode_id,
                config={"miner_model": "openai:gpt-4"},
            )

            result = orchestrator.execute_job(job_id)

            assert result["status"] == "succeeded"
            assert result["mined_claims_count"] > 0

    def test_job_state_transitions(self, test_db_service):
        """Test job state transitions through lifecycle."""
        orchestrator = System2Orchestrator(test_db_service)

        # Create job
        job_id = orchestrator.create_job("transcribe", "test_video")

        with test_db_service.get_session() as session:
            # Initial state
            job = session.query(Job).filter_by(job_id=job_id).first()
            assert job.status == "queued"

            # Create job run
            job_run = orchestrator._create_job_run(job_id)
            assert job_run.status == "running"

            # Update to failed
            orchestrator._update_job_run_status(
                job_run.run_id,
                "failed",
                session,
                error_code=ErrorCode.NETWORK_TIMEOUT_ERROR_MEDIUM,
                error_message="Test failure",
            )

            # Verify update
            job_run = session.query(JobRun).filter_by(run_id=job_run.run_id).first()
            assert job_run.status == "failed"
            assert job_run.error_code == ErrorCode.NETWORK_TIMEOUT_ERROR_MEDIUM.value
            assert job_run.error_message == "Test failure"

    def test_checkpoint_and_resume(self, test_db_service, sample_episode):
        """Test checkpoint saving and job resumption."""
        orchestrator = System2Orchestrator(test_db_service)

        # Create a job with checkpoint
        job_id = orchestrator.create_job(
            "mine", sample_episode.episode_id, config={"test_checkpoint": True}
        )

        # Simulate partial execution with checkpoint
        with test_db_service.get_session() as session:
            job_run = orchestrator._create_job_run(job_id)

            # Save checkpoint
            checkpoint = {
                "last_segment_id": "seg10",
                "processed_segments": 10,
                "total_segments": 20,
            }
            orchestrator._update_job_run_status(
                job_run.run_id,
                "failed",
                session,
                checkpoint=checkpoint,
                error_code="INTERRUPTED",
            )

        # Resume job
        resume_result = orchestrator.resume_job(job_id)

        assert resume_result["status"] != "no_resume_needed"

        # Verify checkpoint was used
        with test_db_service.get_session() as session:
            resumed_run = (
                session.query(JobRun)
                .filter_by(job_id=job_id)
                .order_by(JobRun.started_at.desc())
                .first()
            )

            assert resumed_run.checkpoint_json == checkpoint

    def test_auto_process_chaining(self, test_db_service):
        """Test auto_process chains to next job."""
        orchestrator = System2Orchestrator(test_db_service)

        # Create download job with auto_process
        job_id = orchestrator.create_job(
            "download", "https://youtube.com/watch?v=test123", auto_process=True
        )

        # Mock download success
        with patch.object(
            orchestrator.youtube_download_processor, "process"
        ) as mock_download:
            mock_result = Mock()
            mock_result.success = True
            mock_result.data = {"file_path": "/tmp/test.mp4"}
            mock_download.return_value = mock_result

            # Mock the chaining method
            with patch.object(orchestrator, "_chain_next_job") as mock_chain:
                result = orchestrator.execute_job(job_id)

                # Verify chaining was called
                mock_chain.assert_called_once()

                # Check the call arguments
                call_args = mock_chain.call_args[0]
                assert call_args[0].job_id == job_id  # Current job
                assert call_args[1] == result  # Result data

    def test_error_handling(self, test_db_service):
        """Test error handling and recovery."""
        orchestrator = System2Orchestrator(test_db_service)

        # Test job not found error
        with pytest.raises(KnowledgeSystemError) as exc_info:
            orchestrator.execute_job("non-existent-job")

        assert (
            exc_info.value.error_code == ErrorCode.DATABASE_CONNECTION_ERROR_HIGH.value
        )

        # Test network error during download
        job_id = orchestrator.create_job("download", "test_url")

        with patch.object(
            orchestrator.youtube_download_processor, "process"
        ) as mock_download:
            mock_result = Mock()
            mock_result.success = False
            mock_result.errors = ["Network timeout"]
            mock_download.return_value = mock_result

            result = orchestrator.execute_job(job_id)

            assert result["status"] == "failed"
            assert "error" in result
            assert result["error_code"] == ErrorCode.NETWORK_TIMEOUT_ERROR_MEDIUM.value

    def test_memory_protection(self, test_db_service):
        """Test memory protection during batch processing."""
        orchestrator = System2Orchestrator(test_db_service)

        # This would test memory monitoring, but requires mocking psutil
        # For now, just verify the memory monitor exists in LLM adapter
        assert hasattr(orchestrator.llm_adapter, "memory_monitor")

    def test_metrics_tracking(self, test_db_service):
        """Test metrics are properly tracked in job runs."""
        orchestrator = System2Orchestrator(test_db_service)

        job_id = orchestrator.create_job("transcribe", "test_video")

        # Create job run with metrics
        with test_db_service.get_session() as session:
            job_run = orchestrator._create_job_run(job_id)

            metrics = {
                "processing_time_seconds": 5.2,
                "tokens_used": 1500,
                "cost_usd": 0.03,
                "segments_processed": 25,
            }

            orchestrator._update_job_run_status(
                job_run.run_id, "succeeded", session, metrics=metrics
            )

            # Verify metrics were saved
            updated_run = session.query(JobRun).filter_by(run_id=job_run.run_id).first()
            assert updated_run.metrics_json == metrics
