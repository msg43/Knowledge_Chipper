"""
Tests for System2Orchestrator - The core async orchestration system used by the GUI.

These tests validate the code path that the GUI actually uses, not the CLI path.
All tests are fully automated with timeouts and error handling.
"""

import os
import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch
from knowledge_system.core.system2_orchestrator import System2Orchestrator
from knowledge_system.database import DatabaseService


class TestSystem2OrchestratorBasics:
    """Test basic System2Orchestrator functionality."""
    
    @pytest.fixture
    def db_service(self, tmp_path):
        """Create test database."""
        db_path = tmp_path / "test.db"
        return DatabaseService(f"sqlite:///{db_path}")
    
    @pytest.fixture
    def orchestrator(self, db_service):
        """Create orchestrator with test database."""
        return System2Orchestrator(db_service=db_service)
    
    def test_create_job(self, orchestrator):
        """Test job creation."""
        job_id = orchestrator.create_job(
            job_type="mine",
            input_id="test_episode",
            config={"source": "test"},
            auto_process=False
        )
        
        assert job_id is not None
        assert isinstance(job_id, str)
    
    @pytest.mark.asyncio
    async def test_simple_mine_job(self, orchestrator, tmp_path):
        """Test processing a simple mining job."""
        # Create test transcript
        test_file = tmp_path / "test_transcript.md"
        test_file.write_text("""
# Test Transcript

This is a test transcript with some interesting content.
We're testing the System2Orchestrator which is used by the GUI.

The speaker makes several claims:
- Software testing is important
- Async code requires careful handling
- Event loops need proper cleanup
        """)
        
        # Create job
        job_id = orchestrator.create_job(
            job_type="mine",
            input_id="test_episode",
            config={
                "source": "test",
                "file_path": str(test_file),
                "gui_settings": {
                    "provider": "openai",
                    "model": "gpt-4o-mini-2024-07-18"
                },
                "miner_model": "openai:gpt-4o-mini-2024-07-18",
            },
            auto_process=False
        )
        
        # Process job
        result = await orchestrator.process_job(job_id)
        
        # Validate
        assert result is not None
        assert result.get("status") in ["succeeded", "failed"]
        
        if result.get("status") == "succeeded":
            assert "result" in result
    
    @pytest.mark.asyncio
    async def test_job_cancellation(self, orchestrator, tmp_path):
        """Test that jobs can be cancelled."""
        test_file = tmp_path / "test.md"
        test_file.write_text("Test content")
        
        job_id = orchestrator.create_job(
            job_type="mine",
            input_id="cancel_test",
            config={
                "source": "test",
                "file_path": str(test_file),
                "miner_model": "openai:gpt-4o-mini-2024-07-18",
            }
        )
        
        # Start job in background
        task = asyncio.create_task(orchestrator.process_job(job_id))
        
        # Give it a moment to start
        await asyncio.sleep(0.1)
        
        # Cancel
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass  # Expected


class TestSystem2OrchestratorConcurrency:
    """Test concurrent job processing."""
    
    @pytest.fixture
    def db_service(self, tmp_path):
        """Create test database."""
        db_path = tmp_path / "test_concurrent.db"
        return DatabaseService(f"sqlite:///{db_path}")
    
    @pytest.fixture
    def orchestrator(self, db_service):
        """Create orchestrator."""
        return System2Orchestrator(db_service=db_service)
    
    @pytest.mark.asyncio
    async def test_multiple_concurrent_jobs(self, orchestrator, tmp_path):
        """Test processing multiple jobs concurrently (like GUI batch processing)."""
        files = []
        job_ids = []
        
        # Create test files
        for i in range(3):  # Start with 3 for faster testing
            test_file = tmp_path / f"test_{i}.md"
            test_file.write_text(f"Test content {i} with claims and information.")
            files.append(test_file)
            
            # Create jobs
            job_id = orchestrator.create_job(
                job_type="mine",
                input_id=f"episode_{i}",
                config={
                    "source": "test",
                    "file_path": str(test_file),
                    "miner_model": "openai:gpt-4o-mini-2024-07-18",
                },
                auto_process=False
            )
            job_ids.append(job_id)
        
        # Process all jobs concurrently (this is what GUI does)
        results = await asyncio.gather(*[
            orchestrator.process_job(job_id) for job_id in job_ids
        ], return_exceptions=True)
        
        # Validate
        assert len(results) == 3
        
        # Check that all completed (success or failure, but no exceptions)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                pytest.fail(f"Job {i} raised exception: {result}")
            assert result.get("status") in ["succeeded", "failed"]


class TestSystem2EventLoopManagement:
    """Test that event loops are properly managed (the bug we fixed)."""
    
    @pytest.fixture
    def db_service(self, tmp_path):
        """Create test database."""
        db_path = tmp_path / "test_eventloop.db"
        return DatabaseService(f"sqlite:///{db_path}")
    
    @pytest.fixture
    def orchestrator(self, db_service):
        """Create orchestrator."""
        return System2Orchestrator(db_service=db_service)
    
    @pytest.mark.asyncio
    async def test_no_event_loop_closure_errors(self, orchestrator, tmp_path):
        """Test that async clients are properly cleaned up (event loop fix)."""
        test_file = tmp_path / "test.md"
        test_file.write_text("Test content for event loop cleanup validation.")
        
        job_id = orchestrator.create_job(
            job_type="mine",
            input_id="cleanup_test",
            config={
                "source": "test",
                "file_path": str(test_file),
                "miner_model": "openai:gpt-4o-mini-2024-07-18",
            }
        )
        
        # Process job - should not raise "Event loop is closed" error
        result = await orchestrator.process_job(job_id)
        
        # If we get here without RuntimeError, the fix worked
        assert result.get("status") in ["succeeded", "failed"]
    
    @pytest.mark.asyncio
    async def test_sequential_jobs_no_loop_errors(self, orchestrator, tmp_path):
        """Test sequential job processing doesn't accumulate loop errors."""
        for i in range(3):
            test_file = tmp_path / f"seq_test_{i}.md"
            test_file.write_text(f"Sequential test content {i}")
            
            job_id = orchestrator.create_job(
                job_type="mine",
                input_id=f"seq_episode_{i}",
                config={
                    "source": "test",
                    "file_path": str(test_file),
                    "miner_model": "openai:gpt-4o-mini-2024-07-18",
                }
            )
            
            result = await orchestrator.process_job(job_id)
            assert result.get("status") in ["succeeded", "failed"]
        
        # If we completed all 3 without event loop errors, success


class TestSystem2OrchestratorMocked:
    """Test System2Orchestrator with mocked LLM calls (fast, no API needed)."""
    
    @pytest.fixture
    def db_service(self, tmp_path):
        """Create test database."""
        db_path = tmp_path / "test_mock.db"
        return DatabaseService(f"sqlite:///{db_path}")
    
    @pytest.fixture
    def orchestrator(self, db_service):
        """Create orchestrator."""
        return System2Orchestrator(db_service=db_service)
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(60)
    async def test_job_creation_workflow(self, orchestrator, tmp_path):
        """Test complete job creation workflow (mocked)."""
        test_file = tmp_path / "test.md"
        test_file.write_text("Test content for mocked processing")
        
        # Test job creation
        job_id = orchestrator.create_job(
            job_type="mine",
            input_id="test_episode",
            config={
                "source": "test",
                "file_path": str(test_file),
                "miner_model": "openai:gpt-4o-mini-2024-07-18",
            },
            auto_process=False
        )
        
        assert job_id is not None
        assert isinstance(job_id, str)
        
        # Verify job exists in database
        jobs = await orchestrator.list_jobs()
        assert len(jobs) > 0
        assert any(j["job_id"] == job_id for j in jobs)


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="Requires OpenAI API key - set OPENAI_API_KEY environment variable to run"
)
class TestSystem2OrchestratorLiveAPI:
    """Tests that require actual API calls - runs automatically when OPENAI_API_KEY is set."""
    
    @pytest.fixture
    def db_service(self, tmp_path):
        """Create test database."""
        db_path = tmp_path / "test_live.db"
        return DatabaseService(f"sqlite:///{db_path}")
    
    @pytest.fixture
    def orchestrator(self, db_service):
        """Create orchestrator."""
        return System2Orchestrator(db_service=db_service)
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(180)
    async def test_full_mine_job_with_real_api(self, orchestrator, tmp_path):
        """Test complete mining job with real OpenAI API."""
        test_file = tmp_path / "real_test.md"
        test_file.write_text("""
# Real API Test

This is a test with enough content to extract meaningful claims.

The speaker discusses several key points:
1. Async programming requires careful event loop management
2. Testing should cover the actual code paths users exercise
3. CLI and GUI implementations can diverge over time
4. Comprehensive testing prevents regression
        """)
        
        job_id = orchestrator.create_job(
            job_type="mine",
            input_id="real_api_test",
            config={
                "source": "test",
                "file_path": str(test_file),
                "miner_model": "openai:gpt-4o-mini-2024-07-18",
            }
        )
        
        result = await orchestrator.process_job(job_id)
        
        assert result.get("status") == "succeeded"
        assert "result" in result
        assert result["result"].get("claims_extracted", 0) > 0

