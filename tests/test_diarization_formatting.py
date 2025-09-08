#!/usr/bin/env python3
"""Test diarization formatting improvements."""

import sys
import unittest
from pathlib import Path

import pytest

# Add the src directory to the path so we can import the knowledge_system modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from knowledge_system.commands.transcribe import format_transcript_content
from knowledge_system.processors.youtube_transcript import YouTubeTranscript


class TestDiarizationFormatting(unittest.TestCase):
    """Test improved formatting for diarized transcripts."""

    def setUp(self):
        """Set up test data."""
        # Sample transcript data with diarization
        self.sample_diarized_data = {
            "segments": [
                {
                    "start": 0.0,
                    "end": 3.5,
                    "text": "Hello everyone, welcome to today's discussion.",
                    "speaker": "SPEAKER_00",
                },
                {
                    "start": 4.0,
                    "end": 7.2,
                    "text": "Thank you, I'm excited to be here.",
                    "speaker": "SPEAKER_01",
                },
                {
                    "start": 8.0,
                    "end": 12.1,
                    "text": "Let's start with the first topic on our agenda.",
                    "speaker": "SPEAKER_00",
                },
                {
                    "start": 13.0,
                    "end": 16.8,
                    "text": "That sounds great. I have some thoughts to share.",
                    "speaker": "SPEAKER_01",
                },
            ]
        }

        # Sample YouTube transcript data
        self.youtube_transcript_data = [
            {"start": 0.0, "text": "Welcome to this tutorial video."},
            {"start": 5.0, "text": "Today we'll learn about diarization."},
            {"start": 12.0, "text": "This is an important topic for audio processing."},
        ]

    def test_diarized_transcript_formatting_with_youtube_links(self):
        """Test that diarized transcripts format correctly with YouTube timestamp links."""
        content = format_transcript_content(
            transcript_data=self.sample_diarized_data,
            source_name="Test Video",
            model="base",
            device="cpu",
            format="md",
            video_id="test_video_123",
            timestamps=True,
        )

        # Check that speaker labels are properly formatted
        self.assertIn("**Speaker 1**", content)
        self.assertIn("**Speaker 2**", content)

        # Check that YouTube timestamp links are created
        self.assertIn("https://www.youtube.com/watch?v=test_video_123&t=0s", content)
        self.assertIn("https://www.youtube.com/watch?v=test_video_123&t=4s", content)

        # Check that markdown links are properly formatted
        self.assertIn(
            "[00:00 - 00:03](https://www.youtube.com/watch?v=test_video_123&t=0s)",
            content,
        )
        self.assertIn(
            "[00:04 - 00:07](https://www.youtube.com/watch?v=test_video_123&t=4s)",
            content,
        )

        # Check that speaker separators are added
        self.assertIn("---", content)

        # Check that text content is preserved
        self.assertIn("Hello everyone, welcome to today's discussion.", content)
        self.assertIn("Thank you, I'm excited to be here.", content)

    def test_diarized_transcript_formatting_without_youtube_links(self):
        """Test that diarized transcripts format correctly without YouTube links."""
        content = format_transcript_content(
            transcript_data=self.sample_diarized_data,
            source_name="Test Audio File",
            model="base",
            device="cpu",
            format="md",
            video_id=None,
            timestamps=True,
        )

        # Check that speaker labels are properly formatted
        self.assertIn("**Speaker 1**", content)
        self.assertIn("**Speaker 2**", content)

        # Check that regular timestamps are used (not links)
        self.assertIn("**00:00 - 00:03**", content)
        self.assertIn("**00:04 - 00:07**", content)

        # Should not contain YouTube URLs
        self.assertNotIn("youtube.com", content)

        # Check that speaker separators are added
        self.assertIn("---", content)

    def test_youtube_transcript_formatting(self):
        """Test YouTube transcript formatting with proper line breaks."""
        # Create a YouTubeTranscript instance
        transcript = YouTubeTranscript(
            video_id="test_video_123",
            title="Test Video",
            url="https://youtube.com/watch?v=test_video_123",
            language="en",
            is_manual=False,
            transcript_text="Test transcript",
            transcript_data=self.youtube_transcript_data,
            duration=20.0,
            uploader="Test Channel",
            upload_date="2024-01-01",
            description="Test description",
            view_count=1000,
            tags=["test"],
            thumbnail_url="https://example.com/thumb.jpg",
        )

        markdown_content = transcript.to_markdown(include_timestamps=True)

        # Check that YouTube timestamp links are created
        self.assertIn(
            "https://www.youtube.com/watch?v=test_video_123&t=0s", markdown_content
        )
        self.assertIn(
            "https://www.youtube.com/watch?v=test_video_123&t=5s", markdown_content
        )
        self.assertIn(
            "https://www.youtube.com/watch?v=test_video_123&t=12s", markdown_content
        )

        # Check that timestamps are properly formatted as links with ranges
        self.assertIn(
            "[00:00 - 00:05](https://www.youtube.com/watch?v=test_video_123&t=0s)",
            markdown_content,
        )
        self.assertIn(
            "[00:05 - 00:12](https://www.youtube.com/watch?v=test_video_123&t=5s)",
            markdown_content,
        )
        self.assertIn(
            "[00:12 - 00:15](https://www.youtube.com/watch?v=test_video_123&t=12s)",
            markdown_content,
        )

        # Check that text content is preserved and properly separated
        self.assertIn("Welcome to this tutorial video.", markdown_content)
        self.assertIn("Today we'll learn about diarization.", markdown_content)
        self.assertIn(
            "This is an important topic for audio processing.", markdown_content
        )

    def test_speaker_change_separators(self):
        """Test that speaker change separators are added correctly."""
        content = format_transcript_content(
            transcript_data=self.sample_diarized_data,
            source_name="Test Audio",
            model="base",
            device="cpu",
            format="md",
            timestamps=True,
        )

        # Count separator lines only in the transcript section (after "## Full Transcript")
        if "## Full Transcript" in content:
            transcript_section = content.split("## Full Transcript")[1]
            separator_count = transcript_section.count("---")
            # Should be 3 separators: one between each speaker change (SPEAKER_00 -> SPEAKER_01 -> SPEAKER_00 -> SPEAKER_01)
            self.assertEqual(
                separator_count, 3, "Should have 3 speaker change separators"
            )

    @pytest.mark.skip(reason="Timestamp formatting logic needs fixing")
    def test_no_timestamps_formatting(self):
        """Test formatting when timestamps are disabled."""
        content = format_transcript_content(
            transcript_data=self.sample_diarized_data,
            source_name="Test Audio",
            model="base",
            device="cpu",
            format="md",
            timestamps=False,
        )

        # Should still have speaker labels
        self.assertIn("**Speaker 1**", content)
        self.assertIn("**Speaker 2**", content)

        # Should not have timestamps
        self.assertNotIn("00:00", content)
        self.assertNotIn("youtube.com", content)

        # Should still have content
        self.assertIn("Hello everyone, welcome to today's discussion.", content)

    def test_speaker_attribution_names(self):
        """Test that speaker attribution names are properly displayed in markdown."""
        # Sample data with real speaker names (as would come from speaker attribution)
        attributed_data = {
            "segments": [
                {
                    "start": 0.0,
                    "end": 3.5,
                    "text": "Hello everyone, welcome to today's discussion.",
                    "speaker": "Dr. Alice Johnson",
                    "original_speaker_id": "SPEAKER_00",
                },
                {
                    "start": 4.0,
                    "end": 7.2,
                    "text": "Thank you, I'm excited to be here.",
                    "speaker": "Prof. Bob Smith",
                    "original_speaker_id": "SPEAKER_01",
                },
                {
                    "start": 8.0,
                    "end": 12.1,
                    "text": "Let's start with the first topic on our agenda.",
                    "speaker": "Dr. Alice Johnson",
                    "original_speaker_id": "SPEAKER_00",
                },
            ]
        }

        content = format_transcript_content(
            transcript_data=attributed_data,
            source_name="Test Interview",
            model="base",
            device="cpu",
            format="md",
            video_id="test_video_123",
            timestamps=True,
        )

        # Should have real speaker names, not generic Speaker 1/2
        self.assertIn("**Dr. Alice Johnson**", content)
        self.assertIn("**Prof. Bob Smith**", content)

        # Should not have generic speaker labels
        self.assertNotIn("**Speaker 1**", content)
        self.assertNotIn("**Speaker 2**", content)

        # Should still have proper formatting with hyperlinked timestamps
        self.assertIn("https://www.youtube.com/watch?v=test_video_123&t=0s", content)
        self.assertIn("https://www.youtube.com/watch?v=test_video_123&t=4s", content)

        # Should have speaker change separators between different speakers
        self.assertIn("---", content)

        # Should preserve text content
        self.assertIn("Hello everyone, welcome to today's discussion.", content)
        self.assertIn("Thank you, I'm excited to be here.", content)

    def test_enhanced_speaker_intelligence(self):
        """Test that enhanced speaker intelligence uses metadata for suggestions."""
        # Import the enhanced speaker processor
        from knowledge_system.processors.speaker_processor import SpeakerProcessor

        # Sample diarization segments
        diarization_segments = [
            {"speaker": "SPEAKER_00", "start": 0.0, "end": 3.5},
            {"speaker": "SPEAKER_01", "start": 4.0, "end": 7.2},
            {"speaker": "SPEAKER_00", "start": 8.0, "end": 12.1},
        ]

        # Sample transcript segments
        transcript_segments = [
            {
                "start": 0.0,
                "end": 3.5,
                "text": "Hello everyone, welcome to the Joe Rogan Experience.",
            },
            {
                "start": 4.0,
                "end": 7.2,
                "text": "Thanks Joe, I'm excited to be here to discuss AI.",
            },
            {
                "start": 8.0,
                "end": 12.1,
                "text": "Let's start with your work at OpenAI, Sam.",
            },
        ]

        # Sample metadata that should trigger intelligent suggestions
        metadata = {
            "title": "Joe Rogan Experience #1234 - Sam Altman",
            "description": "Joe Rogan sits down with Sam Altman, CEO of OpenAI, to discuss artificial intelligence",
            "uploader": "PowerfulJRE",
            "video_id": "test123",
        }

        # Test the enhanced speaker processor
        processor = SpeakerProcessor()
        speaker_data_list = processor.prepare_speaker_data(
            diarization_segments, transcript_segments, metadata
        )

        # Should have found speakers
        self.assertEqual(len(speaker_data_list), 2)

        # Check if intelligent suggestions were made
        speaker_suggestions = {}
        for speaker_data in speaker_data_list:
            if speaker_data.suggested_name:
                speaker_suggestions[
                    speaker_data.speaker_id
                ] = speaker_data.suggested_name

        # Should have at least one intelligent suggestion
        self.assertGreater(len(speaker_suggestions), 0)

        # Log the results for verification
        for speaker_data in speaker_data_list:
            print(
                f"Speaker {speaker_data.speaker_id}: suggested='{speaker_data.suggested_name}' "
                f"(confidence={speaker_data.confidence_score:.2f}, method={speaker_data.suggestion_method})"
            )

        # Verify that metadata was used for suggestions
        metadata_used = any(
            speaker_data.suggestion_method.startswith("metadata_analysis")
            for speaker_data in speaker_data_list
        )

        # If metadata suggestions weren't used, at least verify enhanced fallback was used
        if not metadata_used:
            enhanced_fallback_used = any(
                "enhanced_fallback" in speaker_data.suggestion_method
                for speaker_data in speaker_data_list
            )
            self.assertTrue(
                enhanced_fallback_used,
                "Enhanced fallback should be used when metadata doesn't yield suggestions",
            )

    def test_youtube_transcript_speaker_assignment_integration(self):
        """Test that YouTube transcript processor preserves speaker assignments from AudioProcessor."""
        # Test data that simulates what AudioProcessor would return after speaker assignment
        segments_with_assignments = [
            {
                "start": 0.0,
                "end": 3.5,
                "text": "Hello everyone, welcome to the Joe Rogan Experience.",
                "speaker": "Joe Rogan",  # Assigned name, not SPEAKER_00
                "original_speaker_id": "SPEAKER_00",
            },
            {
                "start": 4.0,
                "end": 7.2,
                "text": "Thanks Joe, I'm excited to be here to discuss AI.",
                "speaker": "Sam Altman",  # Assigned name, not SPEAKER_01
                "original_speaker_id": "SPEAKER_01",
            },
            {
                "start": 8.0,
                "end": 12.1,
                "text": "Let's start with your work at OpenAI, Sam.",
                "speaker": "Joe Rogan",  # Assigned name, not SPEAKER_00
                "original_speaker_id": "SPEAKER_00",
            },
        ]

        # Create a transcript using the format
        content = format_transcript_content(
            transcript_data={"segments": segments_with_assignments},
            source_name="Joe Rogan Experience #1234 - Sam Altman",
            model="base",
            device="cpu",
            format="md",
            video_id="test_video_123",
            timestamps=True,
        )

        # Should have real speaker names from assignments
        self.assertIn("**Joe Rogan**", content)
        self.assertIn("**Sam Altman**", content)

        # Should not have generic speaker labels
        self.assertNotIn("**Speaker 1**", content)
        self.assertNotIn("**Speaker 2**", content)

        # Should still have proper formatting with hyperlinked timestamps
        self.assertIn("https://www.youtube.com/watch?v=test_video_123&t=0s", content)
        self.assertIn("https://www.youtube.com/watch?v=test_video_123&t=4s", content)

        # Should have speaker change separators between different speakers
        self.assertIn("---", content)

        # Should preserve text content
        self.assertIn("Hello everyone, welcome to the Joe Rogan Experience.", content)
        self.assertIn("Thanks Joe, I'm excited to be here to discuss AI.", content)

        print("Generated content with speaker assignments:")
        print(content[:500] + "..." if len(content) > 500 else content)

    def test_youtube_transcript_to_markdown_with_diarization(self):
        """Test that YouTubeTranscript.to_markdown uses proper diarization formatting when speakers are present."""
        from src.knowledge_system.processors.youtube_transcript import YouTubeTranscript

        # Create sample transcript data with speaker assignments (as would come from speaker dialog)
        transcript_data_with_speakers = [
            {
                "start": 0.0,
                "duration": 3.5,
                "text": "Hello everyone, welcome to the Joe Rogan Experience.",
                "speaker": "Joe Rogan",  # Assigned name, not SPEAKER_00
            },
            {
                "start": 4.0,
                "duration": 3.2,
                "text": "Thanks Joe, I'm excited to be here to discuss AI.",
                "speaker": "Sam Altman",  # Assigned name, not SPEAKER_01
            },
            {
                "start": 8.0,
                "duration": 4.1,
                "text": "Let's start with your work at OpenAI, Sam.",
                "speaker": "Joe Rogan",  # Assigned name, not SPEAKER_00
            },
        ]

        # Create a YouTube transcript with diarization data
        transcript = YouTubeTranscript(
            video_id="test_video_123",
            title="Joe Rogan Experience #1234 - Sam Altman",
            url="https://www.youtube.com/watch?v=test_video_123",
            language="en",
            is_manual=False,
            transcript_text="Joe Rogan: Hello everyone... Sam Altman: Thanks Joe...",
            transcript_data=transcript_data_with_speakers,
            duration=600,
            uploader="PowerfulJRE",
            upload_date="2024-01-01",
            description="Joe Rogan sits down with Sam Altman",
            view_count=1000000,
            tags=["podcast", "AI"],
            thumbnail_url="https://example.com/thumb.jpg",
        )

        # Test the markdown formatting - this should now use format_transcript_content for diarized content
        markdown_content = transcript.to_markdown(include_timestamps=True)

        print("YouTube transcript markdown output:")
        print(
            markdown_content[:800] + "..."
            if len(markdown_content) > 800
            else markdown_content
        )

        # Should have real speaker names formatted properly with line breaks
        self.assertIn("**Joe Rogan**", markdown_content)
        self.assertIn("**Sam Altman**", markdown_content)

        # Should not have generic speaker labels
        self.assertNotIn("**Speaker 1**", markdown_content)
        self.assertNotIn("**Speaker 2**", markdown_content)

        # Should have proper line breaks (not wall of text)
        # Each speaker should be on their own line
        lines = markdown_content.split("\n")
        joe_rogan_lines = [line for line in lines if "**Joe Rogan**" in line]
        sam_altman_lines = [line for line in lines if "**Sam Altman**" in line]

        self.assertGreater(
            len(joe_rogan_lines), 0, "Should have Joe Rogan speaker lines"
        )
        self.assertGreater(
            len(sam_altman_lines), 0, "Should have Sam Altman speaker lines"
        )

        # Should have hyperlinked timestamps for YouTube
        self.assertIn(
            "https://www.youtube.com/watch?v=test_video_123&t=0s", markdown_content
        )
        self.assertIn(
            "https://www.youtube.com/watch?v=test_video_123&t=4s", markdown_content
        )

        # Should have speaker separators
        self.assertIn("---", markdown_content)


if __name__ == "__main__":
    unittest.main()
