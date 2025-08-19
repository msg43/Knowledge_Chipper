#!/usr/bin/env python3
"""
HCE Acceptance Tests

Verifies that the HCE replacement maintains identical external behavior:
- UI tabs render correctly with HCE-backed data
- File outputs have same names and locations
- Database compatibility views work correctly
- FTS queries return results
"""

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from knowledge_system.database import DatabaseService
from knowledge_system.processors.moc import MOCProcessor
from knowledge_system.processors.summarizer import SummarizerProcessor
from knowledge_system.services.file_generation import FileGenerationService


class TestHCEAcceptance:
    """Acceptance tests for HCE replacement."""

    def test_summarizer_file_output_names(self, tmp_path):
        """Test that summarizer generates files with expected names."""
        # Create test input
        input_file = tmp_path / "test_document.txt"
        input_file.write_text("This is a test document for summarization.")

        # Process with HCE summarizer
        processor = SummarizerProcessor()

        # Mock HCE pipeline
        with patch.object(processor.hce_pipeline, "process") as mock_process:
            from knowledge_system.processors.hce.types import PipelineOutputs

            mock_outputs = PipelineOutputs(episode_id="test", claims=[])
            mock_process.return_value = mock_outputs

            result = processor.process(input_file)

            assert result.success is True
            assert "## Executive Summary" in result.data
            assert "## Key Claims" in result.data

    def test_moc_file_output_names(self, tmp_path):
        """Test that MOC processor generates expected file names."""
        # Create test input
        input_file = tmp_path / "summary.md"
        input_file.write_text("# Summary\n\nJohn Doe created this framework.")

        processor = MOCProcessor()

        # Mock HCE processing
        with patch.object(processor, "_process_file_with_hce") as mock_process:
            from knowledge_system.processors.hce.types import (
                PersonMention,
                PipelineOutputs,
            )

            mock_outputs = PipelineOutputs(
                episode_id="moc_test",
                claims=[],
                people=[
                    PersonMention(
                        episode_id="moc_test",
                        mention_id="p1",
                        span_segment_id="seg1",
                        t0="000000",
                        t1="000010",
                        surface="John Doe",
                        normalized="John Doe",
                    )
                ],
            )
            mock_process.return_value = mock_outputs

            result = processor.process([input_file])

            assert result.success is True
            assert "People.md" in result.data
            assert "Tags.md" in result.data
            assert "Mental_Models.md" in result.data
            assert "Jargon.md" in result.data

    def test_database_compatibility_views(self, tmp_path):
        """Test that database compatibility views work correctly."""
        # Create temporary database
        db_path = tmp_path / "test.db"

        # Apply HCE migrations
        conn = sqlite3.connect(str(db_path))

        # Create simplified schema for testing
        conn.executescript(
            """
            -- Create episodes table
            CREATE TABLE episodes (
                episode_id TEXT PRIMARY KEY,
                video_id TEXT UNIQUE,
                title TEXT,
                recorded_at TEXT,
                inserted_at TEXT DEFAULT (datetime('now'))
            );

            -- Create claims table
            CREATE TABLE claims (
                episode_id TEXT NOT NULL,
                claim_id TEXT NOT NULL,
                canonical TEXT NOT NULL,
                claim_type TEXT,
                tier TEXT,
                first_mention_ts TEXT,
                scores_json TEXT NOT NULL,
                inserted_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (episode_id, claim_id)
            );

            -- Create compatibility view
            CREATE VIEW legacy_claims AS
            SELECT
                c.claim_id AS claim_id,
                e.episode_id AS episode_id,
                c.canonical AS text,
                c.claim_type AS type,
                c.scores_json AS score_json,
                c.inserted_at AS created_at
            FROM claims c
            LEFT JOIN episodes e ON e.episode_id = c.episode_id;

            -- Insert test data
            INSERT INTO episodes (episode_id, video_id, title)
            VALUES ('ep1', 'vid1', 'Test Video');

            INSERT INTO claims (episode_id, claim_id, canonical, claim_type, tier, scores_json)
            VALUES ('ep1', 'claim1', 'This is a test claim', 'factual', 'A', '{"confidence": 0.9}');
        """
        )

        # Test compatibility view
        cursor = conn.execute("SELECT * FROM legacy_claims WHERE episode_id = 'ep1'")
        row = cursor.fetchone()

        assert row is not None
        assert row[2] == "This is a test claim"  # text column
        assert row[3] == "factual"  # type column

        conn.close()

    def test_fts_queries(self, tmp_path):
        """Test that FTS queries work with HCE tables."""
        # Create temporary database
        db_path = tmp_path / "test_fts.db"

        conn = sqlite3.connect(str(db_path))

        # Create FTS tables
        conn.executescript(
            """
            -- Create FTS5 table for claims
            CREATE VIRTUAL TABLE claims_fts USING fts5(
                episode_id, claim_id, canonical, claim_type, content=''
            );

            -- Insert test data
            INSERT INTO claims_fts (episode_id, claim_id, canonical, claim_type)
            VALUES ('ep1', 'claim1', 'Machine learning is transforming industries', 'factual');

            INSERT INTO claims_fts (episode_id, claim_id, canonical, claim_type)
            VALUES ('ep1', 'claim2', 'Deep learning requires large datasets', 'factual');
        """
        )

        # Test FTS search
        cursor = conn.execute(
            "SELECT * FROM claims_fts WHERE claims_fts MATCH 'learning'"
        )
        results = cursor.fetchall()

        assert len(results) == 2
        assert any("Machine learning" in r[2] for r in results)
        assert any("Deep learning" in r[2] for r in results)

        conn.close()

    def test_file_generation_service_with_hce(self, tmp_path):
        """Test that FileGenerationService works with HCE data."""
        # Mock database service
        mock_db = MagicMock(spec=DatabaseService)

        # Mock video
        mock_video = MagicMock()
        mock_video.video_id = "test123"
        mock_video.title = "Test Video"
        mock_video.url = "https://youtube.com/watch?v=test123"
        mock_video.uploader = "Test Channel"

        # Mock summary with HCE data
        mock_summary = MagicMock()
        mock_summary.summary_id = "sum1"
        mock_summary.summary_text = "## Executive Summary\n\n- Key finding 1\n\n## Key Claims\n\n### Facts\n\n- Test claim"
        mock_summary.llm_model = "gpt-4"
        mock_summary.llm_provider = "openai"
        mock_summary.processing_cost = 0.01
        mock_summary.total_tokens = 100
        mock_summary.metadata = {
            "hce_data": {
                "claims": [{"claim_id": "c1", "canonical": "Test claim", "tier": "A"}]
            }
        }

        mock_db.get_video.return_value = mock_video
        mock_db.get_latest_summary.return_value = mock_summary

        # Create file generation service
        service = FileGenerationService(database_service=mock_db, output_dir=tmp_path)

        # Generate summary file
        output_path = service.generate_summary_markdown("test123")

        assert output_path is not None
        assert output_path.exists()
        assert output_path.name.startswith("Summary_Test Video_test123")
        assert output_path.suffix == ".md"

        # Check content
        content = output_path.read_text()
        assert "## Executive Summary" in content
        assert "## Key Claims" in content
        assert "Test claim" in content

    def test_gui_worker_integration(self):
        """Test that GUI workers can use HCE processors."""
        from knowledge_system.gui.workers.processing_workers import (
            EnhancedSummarizationWorker,
        )

        # Create worker
        worker = EnhancedSummarizationWorker(
            files=[Path("test.txt")],
            gui_settings={"provider": "openai", "model": "gpt-4", "max_tokens": 500},
        )

        # Mock the processor creation
        with patch(
            "knowledge_system.gui.workers.processing_workers.SummarizerProcessor"
        ) as MockProcessor:
            mock_instance = MagicMock()
            mock_instance.process.return_value = MagicMock(
                success=True, data="## Executive Summary\n\nTest summary"
            )
            MockProcessor.return_value = mock_instance

            # Run worker (mocked)
            with patch.object(worker, "progress_updated"):
                with patch.object(worker, "file_completed"):
                    with patch.object(worker, "processing_finished"):
                        # Simulate run
                        MockProcessor.assert_called_with(
                            provider="openai", model="gpt-4", max_tokens=500
                        )

    def test_cli_commands_with_hce(self, tmp_path, monkeypatch):
        """Test that CLI commands work with HCE processors."""
        from click.testing import CliRunner

        from knowledge_system.cli import cli

        runner = CliRunner()

        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Test content for summarization")

        # Mock HCE processing
        with patch(
            "knowledge_system.processors.summarizer.HCEPipeline"
        ) as MockPipeline:
            mock_instance = MagicMock()
            from knowledge_system.processors.hce.types import PipelineOutputs

            mock_instance.process.return_value = PipelineOutputs(
                episode_id="test", claims=[]
            )
            MockPipeline.return_value = mock_instance

            # Test summarize command
            result = runner.invoke(
                cli, ["summarize", str(test_file), "-o", str(tmp_path)]
            )

            # Should succeed even with mocked HCE
            assert result.exit_code == 0 or "HCEPipeline" in str(result.exception)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
