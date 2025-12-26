"""
Unit tests for PDF transcript import functionality.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.knowledge_system.processors.pdf_transcript_processor import (
    PDFTranscriptProcessor,
    PDFTranscriptMetadata
)
from src.knowledge_system.services.transcript_manager import TranscriptManager
from src.knowledge_system.services.youtube_video_matcher import YouTubeVideoMatcher


class TestPDFTranscriptProcessor:
    """Test PDF transcript processor."""
    
    def test_extract_speaker_labels_basic(self):
        """Test basic speaker label extraction."""
        processor = PDFTranscriptProcessor()
        
        text = """John Doe: Hello, this is a test.
Jane Smith: Yes, I agree with you.
John Doe: Great, let's continue."""
        
        result = processor._extract_speaker_labels(text)
        
        assert result["has_speakers"] is True
        assert "John Doe" in result["speakers"]
        assert "Jane Smith" in result["speakers"]
        assert len(result["speakers"]) == 2
    
    def test_extract_speaker_labels_no_speakers(self):
        """Test text without speaker labels."""
        processor = PDFTranscriptProcessor()
        
        text = "This is just plain text without any speaker labels."
        
        result = processor._extract_speaker_labels(text)
        
        assert result["has_speakers"] is False
        assert len(result["speakers"]) == 0
    
    def test_parse_timestamps_basic(self):
        """Test basic timestamp parsing."""
        processor = PDFTranscriptProcessor()
        
        text = """[00:00] Introduction
[05:30] Main topic
[15:45] Conclusion"""
        
        result = processor._parse_timestamps(text)
        
        assert result["has_timestamps"] is True
        assert len(result["segments"]) > 0
    
    def test_parse_timestamps_no_timestamps(self):
        """Test text without timestamps."""
        processor = PDFTranscriptProcessor()
        
        text = "This is text without any timestamps."
        
        result = processor._parse_timestamps(text)
        
        assert result["has_timestamps"] is False
    
    def test_calculate_quality_score_high_quality(self):
        """Test quality score calculation for high-quality transcript."""
        processor = PDFTranscriptProcessor()
        
        metadata = PDFTranscriptMetadata()
        metadata.has_speaker_labels = True
        metadata.has_timestamps = True
        metadata.page_count = 10
        
        text = " ".join(["word"] * 1500)  # 1500 words
        
        score = processor._calculate_quality_score(metadata, text)
        
        assert score > 0.7  # Should be high quality
        assert score <= 1.0
    
    def test_calculate_quality_score_low_quality(self):
        """Test quality score calculation for low-quality transcript."""
        processor = PDFTranscriptProcessor()
        
        metadata = PDFTranscriptMetadata()
        metadata.has_speaker_labels = False
        metadata.has_timestamps = False
        metadata.page_count = 1
        
        text = " ".join(["word"] * 100)  # Only 100 words
        
        score = processor._calculate_quality_score(metadata, text)
        
        assert score < 0.5  # Should be low quality
        assert score >= 0.0
    
    def test_extract_youtube_id_standard_url(self):
        """Test YouTube ID extraction from standard URL."""
        processor = PDFTranscriptProcessor()
        
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        video_id = processor._extract_youtube_id(url)
        
        assert video_id == "dQw4w9WgXcQ"
    
    def test_extract_youtube_id_short_url(self):
        """Test YouTube ID extraction from short URL."""
        processor = PDFTranscriptProcessor()
        
        url = "https://youtu.be/dQw4w9WgXcQ"
        video_id = processor._extract_youtube_id(url)
        
        assert video_id == "dQw4w9WgXcQ"


class TestTranscriptManager:
    """Test transcript manager."""
    
    @patch('src.knowledge_system.services.transcript_manager.DatabaseService')
    def test_get_best_transcript_by_priority(self, mock_db):
        """Test transcript selection by priority."""
        # Create mock transcripts
        pdf_transcript = Mock()
        pdf_transcript.transcript_type = "pdf_provided"
        pdf_transcript.quality_score = 0.9
        pdf_transcript.transcript_text = "PDF transcript text"
        
        youtube_transcript = Mock()
        youtube_transcript.transcript_type = "youtube_api"
        youtube_transcript.quality_score = 0.7
        youtube_transcript.transcript_text = "YouTube transcript text"
        
        whisper_transcript = Mock()
        whisper_transcript.transcript_type = "whisper"
        whisper_transcript.quality_score = 0.6
        whisper_transcript.transcript_text = "Whisper transcript text"
        
        # Setup mock
        mock_db_instance = mock_db.return_value
        mock_session = MagicMock()
        mock_db_instance.Session.return_value = mock_session
        mock_session.query.return_value.filter.return_value.all.return_value = [
            pdf_transcript,
            youtube_transcript,
            whisper_transcript
        ]
        
        # Test
        manager = TranscriptManager(db_service=mock_db_instance)
        best = manager.get_best_transcript("test_source_id")
        
        # Should select PDF (highest priority)
        assert best.transcript_type == "pdf_provided"
    
    def test_calculate_transcript_quality_with_speakers(self):
        """Test quality calculation with speaker labels."""
        manager = TranscriptManager()
        
        metadata = {
            "has_speaker_labels": True,
            "has_timestamps": True,
            "word_count": 1500,
            "transcript_type": "pdf_provided"
        }
        
        score = manager.calculate_transcript_quality(metadata)
        
        assert score > 0.7
        assert score <= 1.0
    
    def test_calculate_transcript_quality_without_speakers(self):
        """Test quality calculation without speaker labels."""
        manager = TranscriptManager()
        
        metadata = {
            "has_speaker_labels": False,
            "has_timestamps": False,
            "word_count": 500,
            "transcript_type": "whisper"
        }
        
        score = manager.calculate_transcript_quality(metadata)
        
        assert score < 0.5
        assert score >= 0.0


class TestYouTubeVideoMatcher:
    """Test YouTube video matcher."""
    
    @patch('src.knowledge_system.services.youtube_video_matcher.DatabaseService')
    async def test_fuzzy_match_database_high_similarity(self, mock_db):
        """Test fuzzy matching with high similarity."""
        # Setup mock
        mock_db_instance = mock_db.return_value
        mock_session = MagicMock()
        mock_db_instance.Session.return_value = mock_session
        
        mock_source = Mock()
        mock_source.source_id = "test_video_id"
        mock_source.title = "Introduction to Machine Learning"
        mock_source.source_type = "youtube"
        mock_source.upload_date = None
        
        mock_session.query.return_value.filter.return_value.all.return_value = [
            mock_source
        ]
        
        # Test
        matcher = YouTubeVideoMatcher(db_service=mock_db_instance)
        
        pdf_metadata = {
            "title": "Introduction to Machine Learning",
            "speakers": ["John Doe"],
            "date": None
        }
        
        video_id, confidence, method = await matcher._fuzzy_match_database(pdf_metadata)
        
        assert video_id == "test_video_id"
        assert confidence > 0.9  # Very high similarity
        assert method == "database_fuzzy_match"
    
    def test_score_search_results_exact_match(self):
        """Test scoring search results with exact title match."""
        matcher = YouTubeVideoMatcher()
        
        results = [
            {
                "video_id": "match_id",
                "title": "Machine Learning Basics",
                "channel": "AI Channel"
            },
            {
                "video_id": "other_id",
                "title": "Deep Learning Advanced",
                "channel": "ML Channel"
            }
        ]
        
        pdf_metadata = {
            "title": "Machine Learning Basics",
            "speakers": ["AI Channel"]
        }
        
        best_match = matcher._score_search_results(results, pdf_metadata)
        
        assert best_match is not None
        video_id, confidence = best_match
        assert video_id == "match_id"
        assert confidence > 0.8


@pytest.mark.integration
class TestPDFImportWorkflow:
    """Integration tests for full PDF import workflow."""
    
    @pytest.mark.skip(reason="Requires test PDF file")
    def test_full_import_workflow_with_youtube_url(self):
        """Test complete workflow: PDF → YouTube match → storage."""
        # This would require a test PDF file
        pass
    
    @pytest.mark.skip(reason="Requires test PDF file and YouTube API")
    async def test_full_import_workflow_auto_match(self):
        """Test complete workflow with automatic YouTube matching."""
        # This would require:
        # 1. Test PDF file
        # 2. YouTube API access
        # 3. Database setup
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

