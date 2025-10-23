"""
Output validation tests.

Validates that processing results are correctly written to:
1. SQLite database (jobs, transcripts, summaries, llm_requests, llm_responses)
2. Markdown files (.md) with proper YAML frontmatter and content
"""

import os
import pytest
from pathlib import Path

# Set testing mode before any imports
os.environ["KNOWLEDGE_CHIPPER_TESTING_MODE"] = "1"
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from .utils import DBValidator, read_markdown_with_frontmatter, assert_markdown_has_sections


@pytest.fixture
def test_sandbox(tmp_path):
    """Create test sandbox."""
    from .utils import create_sandbox
    return create_sandbox(tmp_path / "sandbox")


class TestDatabaseOutput:
    """Test database output validation."""
    
    def test_transcript_in_database(self, test_sandbox):
        """Test that transcription results are saved to database."""
        db = DBValidator(test_sandbox.db_path)
        
        # TODO: Run a transcription (fake mode)
        # TODO: Verify video record exists
        # TODO: Verify transcript record exists with correct fields:
        #   - transcript_id
        #   - video_id
        #   - language
        #   - transcript_text
        #   - transcript_segments_json
        #   - created_at
        #   - diarization_enabled
        #   - whisper_model
        
        pytest.skip("Implementation pending - need fake transcription run")
    
    def test_summary_in_database(self, test_sandbox):
        """Test that summarization results are saved to database."""
        db = DBValidator(test_sandbox.db_path)
        
        # TODO: Run a summarization (fake mode)
        # TODO: Verify summary record exists with correct fields:
        #   - summary_id
        #   - video_id
        #   - summary_text
        #   - llm_provider ('ollama')
        #   - llm_model ('qwen2.5:7b-instruct')
        #   - total_tokens
        #   - processing_cost
        #   - created_at
        
        pytest.skip("Implementation pending - need fake summarization run")
    
    def test_job_tracking(self, test_sandbox):
        """Test that processing jobs are tracked."""
        db = DBValidator(test_sandbox.db_path)
        
        # TODO: Run a job
        # TODO: Verify job record with:
        #   - job_type
        #   - status='completed'
        #   - input_file/output_file
        #   - created_at, completed_at
        
        pytest.skip("Implementation pending")


class TestMarkdownOutput:
    """Test markdown file output validation."""
    
    def test_transcript_markdown_created(self, test_sandbox):
        """Test that transcript .md file is created."""
        # TODO: Run transcription
        # TODO: Find generated .md in output/transcripts/
        # TODO: Verify file exists and size > 0
        
        pytest.skip("Implementation pending")
    
    def test_transcript_yaml_frontmatter(self, test_sandbox):
        """Test transcript markdown has valid YAML frontmatter."""
        # TODO: Read transcript .md
        # frontmatter, body = read_markdown_with_frontmatter(md_path)
        # TODO: Assert required fields present:
        #   - title
        #   - video_id
        #   - language
        #   - duration
        #   - processed_at
        
        pytest.skip("Implementation pending")
    
    def test_summary_markdown_created(self, test_sandbox):
        """Test that summary .md file is created."""
        # TODO: Run summarization
        # TODO: Find generated .md in output/summaries/
        # TODO: Verify file exists
        
        pytest.skip("Implementation pending")
    
    def test_summary_yaml_frontmatter(self, test_sandbox):
        """Test summary markdown has valid YAML frontmatter."""
        # TODO: Read summary .md
        # frontmatter, body = read_markdown_with_frontmatter(md_path)
        # TODO: Assert required fields:
        #   - title
        #   - video_id
        #   - model_name ('qwen2.5:7b-instruct')
        #   - provider ('ollama')
        #   - timestamp
        
        pytest.skip("Implementation pending")
    
    def test_summary_required_sections(self, test_sandbox):
        """Test summary markdown contains required sections."""
        # TODO: Read summary .md
        # TODO: For flagship: assert has "Summary" section
        # TODO: For mining: assert has "Jargon", "People", "Mental Models"
        # success = assert_markdown_has_sections(md_path, ["Summary", "Jargon"])
        
        pytest.skip("Implementation pending")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

