"""Comprehensive tests for HCE-based SummarizerProcessor.

This replaces the legacy test_summarizer.py with HCE-specific functionality tests.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from knowledge_system.processors.summarizer import SummarizerProcessor


class TestHCESummarizerProcessor:
    """Comprehensive test suite for HCE-based summarizer processor.

    This test suite validates the complete HCE summarization pipeline,
    replacing the legacy summarizer tests with HCE-specific functionality.
    """

    def test_init_with_defaults(self):
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.llm.model = "gpt-4"
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor()
            assert processor.provider == "openai"
            assert processor.max_tokens == 500
            # Check HCE config is initialized
            assert hasattr(processor, "hce_config")
            assert hasattr(processor, "hce_pipeline")

    def test_hce_output_format(self):
        """Test that HCE processor generates expected output format."""
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.llm.model = "gpt-4"
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor()

            # Mock HCE pipeline
            with patch.object(processor.hce_pipeline, "process") as mock_process:
                from knowledge_system.processors.hce.types import (
                    MentalModel,
                    PersonMention,
                    PipelineOutputs,
                    ScoredClaim,
                )

                # Create mock HCE output
                mock_outputs = PipelineOutputs(
                    episode_id="test_episode",
                    claims=[
                        ScoredClaim(
                            episode_id="test_episode",
                            claim_id="claim1",
                            canonical="This is a key finding",
                            claim_type="factual",
                            evidence=[],
                            tier="A",
                            scores={"confidence": 0.9},
                        ),
                        ScoredClaim(
                            episode_id="test_episode",
                            claim_id="claim2",
                            canonical="This causes that",
                            claim_type="causal",
                            evidence=[],
                            tier="B",
                            scores={"confidence": 0.7},
                        ),
                    ],
                    people=[
                        PersonMention(
                            episode_id="test_episode",
                            mention_id="p1",
                            span_segment_id="seg1",
                            t0="000000",
                            t1="000010",
                            surface="John Smith",
                            normalized="John Smith",
                        )
                    ],
                    concepts=[
                        MentalModel(
                            episode_id="test_episode",
                            model_id="m1",
                            name="Test Framework",
                            definition="A framework for testing",
                        )
                    ],
                )
                mock_process.return_value = mock_outputs

                # Process text
                result = processor.process("Test text for summarization")

                # Check result structure
                assert result.success is True
                assert "## Executive Summary" in result.data
                assert "## Key Claims" in result.data
                assert "### Facts" in result.data
                assert "This is a key finding" in result.data
                assert "### Causal Relationships" in result.data
                assert "This causes that" in result.data
                assert "## Key People Mentioned" in result.data
                assert "John Smith" in result.data
                assert "## Key Concepts" in result.data
                assert "Test Framework" in result.data
                assert "Extracted 2 claims using HCE analysis" in result.data

                # Check metadata
                assert result.metadata["claims_extracted"] == 2
                assert result.metadata["people_found"] == 1
                assert result.metadata["concepts_found"] == 1
                assert "hce_data" in result.metadata

    def test_process_file_input(self):
        """Test processing file input."""
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.llm.model = "gpt-4"
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor()

            # Mock file reading
            test_content = "This is test content from a file."
            with (
                patch.object(Path, "exists", return_value=True),
                patch.object(Path, "is_file", return_value=True),
                patch.object(Path, "read_text", return_value=test_content),
                patch.object(Path, "suffix", ".txt"),
                patch.object(processor.hce_pipeline, "process") as mock_process,
            ):
                from knowledge_system.processors.hce.types import PipelineOutputs

                mock_outputs = PipelineOutputs(
                    episode_id="file_test",
                    claims=[],
                    relations=[],
                    milestones=[],
                    people=[],
                    concepts=[],
                    jargon=[],
                )
                mock_process.return_value = mock_outputs

                result = processor.process(Path("test.txt"))

                assert result.success is True
                mock_process.assert_called_once()

    def test_dry_run_mode(self):
        """Test dry run mode."""
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.llm.model = "gpt-4"
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor()

            result = processor.process("Test text", dry_run=True)

            assert result.success is True
            assert result.dry_run is True
            assert "[DRY RUN]" in result.data
            assert "HCE" in result.data

    def test_progress_callback(self):
        """Test progress callback functionality."""
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.llm.model = "gpt-4"
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor()

            progress_called = False

            def progress_callback(progress):
                nonlocal progress_called
                progress_called = True
                assert progress.status == "Extracting claims..."
                assert progress.current_operation == "HCE Pipeline"

            with patch.object(processor.hce_pipeline, "process") as mock_process:
                from knowledge_system.processors.hce.types import PipelineOutputs

                mock_outputs = PipelineOutputs(episode_id="test", claims=[])
                mock_process.return_value = mock_outputs

                result = processor.process(
                    "Test text", progress_callback=progress_callback
                )

                assert result.success is True
                assert progress_called

    def test_hce_pipeline_fallback(self):
        """Test fallback when HCE pipeline fails."""
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.llm.model = "gpt-4"
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor()

            # Make HCE pipeline fail
            with patch.object(
                processor.hce_pipeline, "process", side_effect=Exception("HCE failed")
            ):
                result = processor.process("Test text")

                # Should still succeed with empty results
                assert result.success is True
                assert "Extracted 0 claims" in result.data

    def test_supported_formats(self):
        """Test supported file formats."""
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor()
            assert ".txt" in processor.supported_formats
            assert ".md" in processor.supported_formats
            assert ".json" in processor.supported_formats
            assert ".html" in processor.supported_formats
            assert ".htm" in processor.supported_formats
