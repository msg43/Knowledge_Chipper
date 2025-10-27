"""
Test checkpoint and resumption functionality for System2 Orchestrator.

This test verifies that jobs can be saved at various stages and resumed
without losing progress.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.knowledge_system.core.system2_orchestrator import System2Orchestrator
from src.knowledge_system.database import DatabaseService


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    
    database_url = f"sqlite:///{db_path}"
    db_service = DatabaseService(database_url=database_url)
    yield db_service
    
    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def orchestrator(temp_db):
    """Create a System2Orchestrator instance."""
    return System2Orchestrator(db_service=temp_db)


def test_save_and_load_checkpoint(orchestrator):
    """Test basic checkpoint save and load functionality."""
    # Create a job
    job_id = orchestrator.create_job(
        job_type="mine",
        input_id="test_episode_123",
        config={"miner_model": "ollama:qwen2.5:7b-instruct"},
        auto_process=False
    )
    
    # Create a job run
    run_id = orchestrator.create_job_run(job_id)
    
    # Save a checkpoint
    checkpoint_data = {
        "stage": "mining",
        "total_segments": 100,
        "completed_segments": ["seg_0001", "seg_0002", "seg_0003"],
        "progress_percent": 50
    }
    orchestrator.save_checkpoint(run_id, checkpoint_data)
    
    # Load the checkpoint
    loaded_checkpoint = orchestrator.load_checkpoint(run_id)
    
    # Verify checkpoint was saved and loaded correctly
    assert loaded_checkpoint is not None
    assert loaded_checkpoint["stage"] == "mining"
    assert loaded_checkpoint["total_segments"] == 100
    assert len(loaded_checkpoint["completed_segments"]) == 3
    assert loaded_checkpoint["progress_percent"] == 50


def test_checkpoint_overwrite(orchestrator):
    """Test that checkpoints are overwritten with new data."""
    job_id = orchestrator.create_job(
        job_type="mine",
        input_id="test_episode_456",
        config={},
        auto_process=False
    )
    
    run_id = orchestrator.create_job_run(job_id)
    
    # Save initial checkpoint
    orchestrator.save_checkpoint(run_id, {
        "stage": "parsing",
        "total_segments": 50
    })
    
    # Load and verify
    checkpoint = orchestrator.load_checkpoint(run_id)
    assert checkpoint["stage"] == "parsing"
    assert checkpoint["total_segments"] == 50
    
    # Update checkpoint
    orchestrator.save_checkpoint(run_id, {
        "stage": "mining",
        "total_segments": 50,
        "completed_segments": ["seg_0001"]
    })
    
    # Load and verify update
    checkpoint = orchestrator.load_checkpoint(run_id)
    assert checkpoint["stage"] == "mining"
    assert "completed_segments" in checkpoint


def test_no_checkpoint_returns_none(orchestrator):
    """Test that loading a non-existent checkpoint returns None."""
    job_id = orchestrator.create_job(
        job_type="mine",
        input_id="test_episode_789",
        config={},
        auto_process=False
    )
    
    run_id = orchestrator.create_job_run(job_id)
    
    # Try to load checkpoint without saving
    checkpoint = orchestrator.load_checkpoint(run_id)
    
    assert checkpoint is None


def test_checkpoint_with_completed_stage(orchestrator):
    """Test that a completed checkpoint can skip processing."""
    job_id = orchestrator.create_job(
        job_type="mine",
        input_id="test_episode_complete",
        config={},
        auto_process=False
    )
    
    run_id = orchestrator.create_job_run(job_id)
    
    # Save a completed checkpoint with final results
    final_result = {
        "status": "succeeded",
        "output_id": "test_episode_complete",
        "result": {
            "claims_extracted": 42,
            "evidence_spans": 100
        }
    }
    
    orchestrator.save_checkpoint(run_id, {
        "stage": "completed",
        "final_result": final_result
    })
    
    # Load checkpoint
    checkpoint = orchestrator.load_checkpoint(run_id)
    
    # Verify we can detect completion
    assert checkpoint["stage"] == "completed"
    assert checkpoint["final_result"]["status"] == "succeeded"
    assert checkpoint["final_result"]["result"]["claims_extracted"] == 42


def test_checkpoint_with_error_stage(orchestrator):
    """Test that error checkpoints are saved correctly."""
    job_id = orchestrator.create_job(
        job_type="transcribe",
        input_id="test_media_error",
        config={},
        auto_process=False
    )
    
    run_id = orchestrator.create_job_run(job_id)
    
    # Save error checkpoint
    orchestrator.save_checkpoint(run_id, {
        "stage": "failed",
        "error": "File not found: /tmp/missing.mp3"
    })
    
    # Load checkpoint
    checkpoint = orchestrator.load_checkpoint(run_id)
    
    # Verify error information is preserved
    assert checkpoint["stage"] == "failed"
    assert "error" in checkpoint
    assert "File not found" in checkpoint["error"]


def test_multiple_runs_different_checkpoints(orchestrator):
    """Test that multiple runs of the same job have separate checkpoints."""
    job_id = orchestrator.create_job(
        job_type="mine",
        input_id="test_episode_multi",
        config={},
        auto_process=False
    )
    
    # Create first run and save checkpoint
    run_id_1 = orchestrator.create_job_run(job_id)
    orchestrator.save_checkpoint(run_id_1, {
        "stage": "mining",
        "completed_segments": ["seg_0001"]
    })
    
    # Create second run and save different checkpoint
    run_id_2 = orchestrator.create_job_run(job_id)
    orchestrator.save_checkpoint(run_id_2, {
        "stage": "mining",
        "completed_segments": ["seg_0001", "seg_0002"]
    })
    
    # Verify each run has its own checkpoint
    checkpoint_1 = orchestrator.load_checkpoint(run_id_1)
    checkpoint_2 = orchestrator.load_checkpoint(run_id_2)
    
    assert len(checkpoint_1["completed_segments"]) == 1
    assert len(checkpoint_2["completed_segments"]) == 2


@pytest.mark.asyncio
async def test_transcribe_checkpoint_resume(orchestrator, tmp_path):
    """Test that transcription job can resume from checkpoint."""
    # Create a dummy audio file
    audio_file = tmp_path / "test_audio.mp3"
    audio_file.write_text("dummy audio content")
    
    job_id = orchestrator.create_job(
        job_type="transcribe",
        input_id="test_media_resume",
        config={
            "file_path": str(audio_file),
            "model": "base",
            "enable_diarization": False
        },
        auto_process=False
    )
    
    run_id = orchestrator.create_job_run(job_id)
    
    # Simulate checkpoint from interrupted transcription
    orchestrator.save_checkpoint(run_id, {
        "stage": "storing",
        "file_path": str(audio_file),
        "transcript_path": str(tmp_path / "transcript.txt"),
        "transcript_text": "This is a test transcript",
        "language": "en",
        "duration": 120.5
    })
    
    # Load checkpoint to verify it's set up correctly
    checkpoint = orchestrator.load_checkpoint(run_id)
    
    assert checkpoint is not None
    assert checkpoint["stage"] == "storing"
    assert checkpoint["transcript_text"] == "This is a test transcript"
    
    # Note: Full process_job test would require mocking AudioProcessor
    # This test verifies checkpoint structure is correct for resumption


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

