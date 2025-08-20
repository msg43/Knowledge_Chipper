"""
Comprehensive tests for HCE-based MOC (Maps of Content) processor.

This replaces the legacy test_moc.py with HCE-specific MOC generation tests.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from knowledge_system.processors.moc import (
    Belief,
    JargonEntry,
    MentalModel,
    MOCData,
    MOCProcessor,
    Person,
    Tag,
)


class TestHCEMOCProcessor:
    """Test HCE-based MOC processor functionality."""

    def test_processor_initialization(self):
        """Test processor initialization."""
        processor = MOCProcessor()
        assert processor.name == "moc"
        assert ".md" in processor.supported_formats
        assert ".txt" in processor.supported_formats
        # Check HCE config is initialized
        assert hasattr(processor, "hce_config")

    def test_process_with_hce(self, tmp_path):
        """Test processing with HCE pipeline."""
        processor = MOCProcessor()

        # Create test file
        md_file = tmp_path / "test.md"
        md_file.write_text(
            "# Test Document\n\nJohn Doe discussed the framework.\n\nThis is important."
        )

        # Mock HCE pipeline
        with patch.object(processor, "_process_file_with_hce") as mock_process:
            from knowledge_system.processors.hce.types import (
                JargonTerm,
                MentalModel,
                PersonMention,
                PipelineOutputs,
            )

            # Create mock HCE output
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
                concepts=[
                    MentalModel(
                        episode_id="moc_test",
                        model_id="m1",
                        name="Framework",
                        definition="A conceptual framework",
                    )
                ],
                jargon=[
                    JargonTerm(
                        episode_id="moc_test",
                        term_id="j1",
                        term="important",
                        definition="Of great significance",
                    )
                ],
            )
            mock_process.return_value = mock_outputs

            result = processor.process([md_file])

            assert result.success is True
            assert isinstance(result.data, dict)

            # Check generated files
            assert "People.md" in result.data
            assert "Tags.md" in result.data
            assert "Mental_Models.md" in result.data
            assert "Jargon.md" in result.data

            # Check content
            assert "John Doe" in result.data["People.md"]
            assert "Framework" in result.data["Mental_Models.md"]
            assert "important" in result.data["Jargon.md"]

            # Check metadata
            assert result.metadata["people_found"] == 1
            assert result.metadata["mental_models_found"] == 1
            assert result.metadata["jargon_found"] == 1

    def test_process_with_database_hce_data(self, tmp_path):
        """Test processing when HCE data exists in database."""
        processor = MOCProcessor()

        # Create test file
        md_file = tmp_path / "test.md"
        md_file.write_text("# Test")

        # Mock database service
        with patch.object(processor, "db_service") as mock_db:
            mock_summary = MagicMock()
            mock_summary.metadata = {
                "hce_data": {
                    "people": [{"surface": "Alice", "normalized": "Alice"}],
                    "concepts": [
                        {"name": "Testing", "definition": "Quality assurance"}
                    ],
                    "jargon": [{"term": "QA", "definition": "Quality Assurance"}],
                    "claims": [
                        {
                            "canonical": "Testing is important",
                            "tier": "A",
                            "scores": {"confidence": 0.9},
                        }
                    ],
                }
            }
            mock_db.get_latest_summary.return_value = mock_summary

            result = processor.process([md_file], include_beliefs=True)

            assert result.success is True
            assert "People.md" in result.data
            assert "Alice" in result.data["People.md"]
            assert "Testing" in result.data["Tags.md"]
            assert "QA" in result.data["Jargon.md"]
            assert "beliefs.yaml" in result.data

    def test_legacy_pattern_fallback(self, tmp_path):
        """Test fallback to legacy patterns when HCE fails."""
        processor = MOCProcessor()

        # Create test file with patterns
        md_file = tmp_path / "test.md"
        content = """
        # Test Document

        Bob Smith is working on this.
        Alice Johnson reviewed it.

        #important #review

        The agile framework is used here.
        """
        md_file.write_text(content)

        # Make HCE fail
        with patch.object(
            processor, "_process_file_with_hce", side_effect=Exception("HCE failed")
        ):
            result = processor.process([md_file])

            assert result.success is True

            # Check that legacy patterns were extracted
            assert "Bob Smith" in result.data["People.md"]
            assert "Alice Johnson" in result.data["People.md"]
            assert "#important" in result.data["Tags.md"]
            assert "#review" in result.data["Tags.md"]
            assert "agile framework" in result.data["Mental_Models.md"]

    def test_dry_run(self, tmp_path):
        """Test dry run mode."""
        processor = MOCProcessor()

        md_file = tmp_path / "test.md"
        md_file.write_text("# Test")

        result = processor.process([md_file], dry_run=True)

        assert result.success is True
        assert result.dry_run is True
        assert "[DRY RUN]" in result.data
        assert result.metadata["files_count"] == 1

    def test_moc_file_generation(self):
        """Test MOC file generation format."""
        processor = MOCProcessor()

        moc_data = MOCData()
        moc_data.people["John Doe"] = Person(
            name="John Doe",
            mentions=["file1.md", "file2.md"],
            first_mention="file1.md",
            mention_count=2,
        )
        moc_data.tags["concept"] = Tag(
            name="concept", category="concept", files=["file1.md"], count=1
        )
        moc_data.mental_models["Framework"] = MentalModel(
            name="Framework", description="A test framework", source_files=["file1.md"]
        )
        moc_data.jargon["API"] = JargonEntry(
            term="API",
            definition="Application Programming Interface",
            files=["file1.md"],
        )
        moc_data.beliefs.append(
            Belief(
                statement="This is important",
                sources=["file1.md"],
                epistemic_weight=0.8,
            )
        )

        files = processor._generate_moc_files(moc_data)

        # Check all expected files are generated
        assert "People.md" in files
        assert "Tags.md" in files
        assert "Mental_Models.md" in files
        assert "Jargon.md" in files
        assert "beliefs.yaml" in files

        # Check file content structure
        assert "## John Doe" in files["People.md"]
        assert "Total mentions: 2" in files["People.md"]
        assert "### #concept" in files["Tags.md"]
        assert "## Framework" in files["Mental_Models.md"]
        assert "## API" in files["Jargon.md"]
        assert "epistemic_weight: 0.8" in files["beliefs.yaml"]

    def test_multiple_file_processing(self, tmp_path):
        """Test processing multiple files."""
        processor = MOCProcessor()

        # Create multiple test files
        file1 = tmp_path / "doc1.md"
        file1.write_text("# Doc 1\n\nAlice works here.")

        file2 = tmp_path / "doc2.md"
        file2.write_text("# Doc 2\n\nBob works here.")

        # Mock HCE processing
        def mock_hce_process(file_path):
            from knowledge_system.processors.hce.types import (
                PersonMention,
                PipelineOutputs,
            )

            if "doc1" in str(file_path):
                person = PersonMention(
                    episode_id="moc_doc1",
                    mention_id="p1",
                    span_segment_id="seg1",
                    t0="000000",
                    t1="000010",
                    surface="Alice",
                    normalized="Alice",
                )
            else:
                person = PersonMention(
                    episode_id="moc_doc2",
                    mention_id="p2",
                    span_segment_id="seg1",
                    t0="000000",
                    t1="000010",
                    surface="Bob",
                    normalized="Bob",
                )

            return PipelineOutputs(
                episode_id=f"moc_{file_path.stem}",
                claims=[],
                people=[person],
                concepts=[],
                jargon=[],
            )

        with patch.object(
            processor, "_process_file_with_hce", side_effect=mock_hce_process
        ):
            result = processor.process([file1, file2])

            assert result.success is True
            assert result.metadata["files_processed"] == 2
            assert result.metadata["people_found"] == 2
            assert "Alice" in result.data["People.md"]
            assert "Bob" in result.data["People.md"]
