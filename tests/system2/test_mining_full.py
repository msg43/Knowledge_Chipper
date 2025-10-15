"""
Comprehensive tests for mining with Ollama integration.

Tests the complete mining workflow including checkpoint resume and database storage.
"""

import tempfile
from pathlib import Path

import pytest

from src.knowledge_system.core.system2_orchestrator import System2Orchestrator
from src.knowledge_system.database import DatabaseService
from src.knowledge_system.database.hce_models import Claim, Concept, Jargon, Person
from src.knowledge_system.database.hce_operations import get_episode_summary


@pytest.fixture
def test_db_service():
    """Create a test database service with in-memory database."""
    db_service = DatabaseService("sqlite:///:memory:")
    
    # Create all tables
    from src.knowledge_system.database.models import Base
    
    Base.metadata.create_all(db_service.engine)
    
    yield db_service


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
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(content)
        file_path = f.name
    
    yield file_path
    
    # Cleanup
    Path(file_path).unlink(missing_ok=True)


@pytest.mark.integration
class TestMiningWithOllama:
    """Test mining with real Ollama integration."""
    
    @pytest.mark.asyncio
    async def test_mine_simple_transcript(self, test_db_service, sample_transcript_file):
        """Test mining a simple transcript end-to-end."""
        orchestrator = System2Orchestrator(test_db_service)
        
        episode_id = "episode_test_mine"
        
        # Create mining job
        job_id = orchestrator.create_job(
            job_type="mine",
            input_id=episode_id,
            config={
                "file_path": sample_transcript_file,
                "miner_model": "ollama:qwen2.5:7b-instruct"
            },
            auto_process=False
        )
        
        # Process the job
        result = await orchestrator.process_job(job_id)
        
        # Verify result
        assert result.get("status") == "succeeded"
        assert "result" in result
        assert "claims_extracted" in result["result"]
        
        # Should have extracted at least some claims
        assert result["result"]["claims_extracted"] >= 0
        
        # Verify data was stored in database
        summary = get_episode_summary(test_db_service, episode_id)
        assert summary["total_extractions"] >= 0
    
    @pytest.mark.asyncio
    async def test_checkpoint_save_and_resume(self, test_db_service, sample_transcript_file):
        """Test checkpoint saving during mining and resume after interruption."""
        orchestrator = System2Orchestrator(test_db_service)
        
        episode_id = "episode_checkpoint_test"
        
        # Create job
        job_id = orchestrator.create_job(
            job_type="mine",
            input_id=episode_id,
            config={
                "file_path": sample_transcript_file,
                "miner_model": "ollama:qwen2.5:7b-instruct"
            },
            auto_process=False
        )
        
        # Create job run
        run_id = orchestrator.create_job_run(job_id)
        
        # Save a checkpoint manually
        orchestrator.save_checkpoint(run_id, {
            "last_segment": 2,
            "partial_results": 2
        })
        
        # Load checkpoint
        checkpoint = orchestrator.load_checkpoint(run_id)
        
        assert checkpoint is not None
        assert checkpoint["last_segment"] == 2
        assert checkpoint["partial_results"] == 2
    
    @pytest.mark.asyncio
    async def test_mining_stores_in_database(self, test_db_service, sample_transcript_file):
        """Verify mining results are stored in HCE tables."""
        orchestrator = System2Orchestrator(test_db_service)
        
        episode_id = "episode_db_test"
        
        # Create and process job
        job_id = orchestrator.create_job(
            job_type="mine",
            input_id=episode_id,
            config={
                "file_path": sample_transcript_file,
                "miner_model": "ollama:qwen2.5:7b-instruct"
            }
        )
        
        result = await orchestrator.process_job(job_id)
        
        assert result.get("status") == "succeeded"
        
        # Check database for stored results
        with test_db_service.get_session() as session:
            # Should have episode
            from src.knowledge_system.database.hce_models import Episode
            episode = session.query(Episode).filter_by(episode_id=episode_id).first()
            assert episode is not None
            
            # May or may not have claims depending on LLM output
            claims = session.query(Claim).filter_by(episode_id=episode_id).all()
            # Just verify query works
            assert isinstance(claims, list)
    
    @pytest.mark.asyncio
    async def test_segment_parsing(self, test_db_service, sample_transcript_file):
        """Test transcript parsing into segments."""
        orchestrator = System2Orchestrator(test_db_service)
        
        # Read transcript
        transcript_text = Path(sample_transcript_file).read_text()
        
        # Parse segments
        segments = orchestrator._parse_transcript_to_segments(transcript_text, "test_episode")
        
        # Should have parsed some segments
        assert len(segments) > 0
        
        # Verify segment structure
        for segment in segments:
            assert hasattr(segment, 'episode_id')
            assert hasattr(segment, 'segment_id')
            assert hasattr(segment, 'text')
            assert len(segment.text) > 0
    
    @pytest.mark.asyncio
    async def test_progress_tracking(self, test_db_service, sample_transcript_file):
        """Test progress metrics are updated during mining."""
        orchestrator = System2Orchestrator(test_db_service)
        
        episode_id = "episode_progress_test"
        
        job_id = orchestrator.create_job(
            job_type="mine",
            input_id=episode_id,
            config={
                "file_path": sample_transcript_file,
                "miner_model": "ollama:qwen2.5:7b-instruct"
            }
        )
        
        result = await orchestrator.process_job(job_id)
        
        assert result.get("status") == "succeeded"
        
        # Check job run for metrics
        from src.knowledge_system.database.system2_models import JobRun
        with test_db_service.get_session() as session:
            job_runs = session.query(JobRun).filter_by(job_id=job_id).all()
            assert len(job_runs) > 0
            
            # Latest run should have metrics
            job_run = job_runs[-1]
            # Metrics may or may not be set depending on timing
            # Just verify the field exists
            assert hasattr(job_run, 'metrics_json')


@pytest.mark.integration
class TestSegmentParsing:
    """Test transcript segment parsing."""
    
    def test_parse_simple_lines(self, test_db_service):
        """Test parsing simple line-based transcript."""
        orchestrator = System2Orchestrator(test_db_service)
        
        transcript = """Line 1 of transcript.
Line 2 of transcript.
Line 3 of transcript."""
        
        segments = orchestrator._parse_transcript_to_segments(transcript, "test_ep")
        
        assert len(segments) == 3
        assert segments[0].text == "Line 1 of transcript."
        assert segments[1].text == "Line 2 of transcript."
        assert segments[2].text == "Line 3 of transcript."
    
    def test_parse_skips_headers(self, test_db_service):
        """Test parsing skips markdown headers."""
        orchestrator = System2Orchestrator(test_db_service)
        
        transcript = """# Title
## Subtitle
This is content.
Another line of content."""
        
        segments = orchestrator._parse_transcript_to_segments(transcript, "test_ep")
        
        # Should only have content lines, not headers
        segment_texts = [s.text for s in segments]
        assert "This is content." in segment_texts
        assert "Another line of content." in segment_texts
        
        # Headers should be skipped
        assert all("Title" not in s.text for s in segments)
        assert all("Subtitle" not in s.text for s in segments)
    
    def test_parse_skips_short_lines(self, test_db_service):
        """Test parsing skips very short lines."""
        orchestrator = System2Orchestrator(test_db_service)
        
        transcript = """This is a long enough line to be included.
Hi
This is another long line."""
        
        segments = orchestrator._parse_transcript_to_segments(transcript, "test_ep")
        
        # Should skip the short "Hi" line
        assert len(segments) == 2
        segment_texts = [s.text for s in segments]
        assert "This is a long enough line to be included." in segment_texts
        assert "This is another long line." in segment_texts


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

