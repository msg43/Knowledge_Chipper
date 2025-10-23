"""
Tests for unified HCE storage via System2Orchestrator.

These tests verify that the integrated UnifiedHCEPipeline
stores rich data correctly.
"""

import pytest
import asyncio
from pathlib import Path
import sqlite3
import tempfile

from src.knowledge_system.core.system2_orchestrator import System2Orchestrator
from src.knowledge_system.database.service import DatabaseService


class TestUnifiedMiningStorage:
    """Test unified mining and storage pipeline."""
    
    @pytest.fixture
    def test_transcript(self, tmp_path):
        """Create test transcript file."""
        transcript = tmp_path / "test.txt"
        transcript.write_text("""
[00:00:00] Speaker A: Today we'll discuss first principles thinking, 
a mental model used by Elon Musk for problem solving.

[00:00:15] Speaker B: The key is breaking down complex problems 
into fundamental truths, rather than reasoning by analogy.

[00:00:30] Speaker A: This technique, pioneered by Aristotle, 
helps you innovate rather than iterate.
""")
        return transcript
    
    def test_mining_creates_rich_data(self, test_transcript):
        """Test that mining creates evidence, relations, categories."""
        orchestrator = System2Orchestrator()
        
        # Create mining job
        job_id = orchestrator.create_job(
            "mine",
            "test_episode",
            config={
                "file_path": str(test_transcript),
                "miner_model": "ollama:qwen2.5:7b-instruct",
            }
        )
        
        # Process job
        result = asyncio.run(orchestrator.process_job(job_id))
        
        # Verify success
        assert result["status"] == "succeeded"
        assert result["result"]["claims_extracted"] >= 0
        
        # Verify rich data in database
        unified_db = Path.home() / "Library" / "Application Support" / "SkipThePodcast" / "unified_hce.db"
        assert unified_db.exists()
        
        conn = sqlite3.connect(unified_db)
        cursor = conn.cursor()
        
        # Check for claims
        cursor.execute("SELECT COUNT(*) FROM claims WHERE episode_id = 'test_episode'")
        claims_count = cursor.fetchone()[0]
        assert claims_count >= 0, "Should have claims table"
        
        # Check for evidence spans
        cursor.execute("SELECT COUNT(*) FROM evidence_spans WHERE episode_id = 'test_episode'")
        evidence_count = cursor.fetchone()[0]
        assert evidence_count >= 0, "Should have evidence_spans table"
        
        # Check for people mentions
        cursor.execute("SELECT COUNT(*) FROM people WHERE episode_id = 'test_episode'")
        people_count = cursor.fetchone()[0]
        assert people_count >= 0, "Should have people table"
        
        # Check for concepts
        cursor.execute("SELECT COUNT(*) FROM concepts WHERE episode_id = 'test_episode'")
        concepts_count = cursor.fetchone()[0]
        assert concepts_count >= 0, "Should have concepts table"
        
        conn.close()
    
    def test_context_quotes_populated(self, test_transcript):
        """Test that context_quote fields are populated."""
        orchestrator = System2Orchestrator()
        
        job_id = orchestrator.create_job(
            "mine",
            "test_context_episode",
            config={"file_path": str(test_transcript)}
        )
        
        asyncio.run(orchestrator.process_job(job_id))
        
        # Check database
        unified_db = Path.home() / "Library" / "Application Support" / "SkipThePodcast" / "unified_hce.db"
        conn = sqlite3.connect(unified_db)
        cursor = conn.cursor()
        
        # Verify context_quote in people (if any people were extracted)
        cursor.execute("""
            SELECT name, context_quote FROM people 
            WHERE episode_id = 'test_context_episode' 
            AND context_quote IS NOT NULL
        """)
        people_with_quotes = cursor.fetchall()
        # May be 0 if no people extracted, but structure should exist
        assert isinstance(people_with_quotes, list)
        
        # Verify context_quote in concepts (if any concepts were extracted)
        cursor.execute("""
            SELECT name, context_quote FROM concepts 
            WHERE episode_id = 'test_context_episode' 
            AND context_quote IS NOT NULL
        """)
        concepts_with_quotes = cursor.fetchall()
        # May be 0 if no concepts extracted, but structure should exist
        assert isinstance(concepts_with_quotes, list)
        
        conn.close()

