"""
Standardized JSON Output Schema for Transcription + Diarization Pipeline

This module defines the Pydantic models for the output of the transcription
and speaker diarization pipeline. These schemas ensure consistent data
structures across the entire system.

The output schema captures:
- Word-level timestamps from pywhispercpp DTW
- Speaker assignments from pyannote-whisper word-driven alignment
- Merged segments by speaker
- Stable regions used for voice fingerprinting
"""

from typing import Optional

from pydantic import BaseModel, Field


class Word(BaseModel):
    """A single transcribed word with DTW timestamp and speaker assignment.
    
    The timestamps come from whisper.cpp's DTW (Dynamic Time Warping) algorithm,
    providing accurate word-level timing. Speaker assignment comes from the
    pyannote-whisper word-driven alignment with median filter smoothing.
    """
    word: str = Field(..., description="The transcribed word text")
    start: float = Field(..., description="Start time in seconds (DTW timestamp)")
    end: float = Field(..., description="End time in seconds (DTW timestamp)")
    speaker: Optional[str] = Field(None, description="Assigned speaker ID (e.g., SPEAKER_00)")
    confidence: Optional[float] = Field(None, description="Word-level confidence score (0-1)")


class Segment(BaseModel):
    """A contiguous segment of speech from a single speaker.
    
    Segments are created by merging consecutive words that have the same
    speaker assignment after median filter smoothing.
    """
    text: str = Field(..., description="Full text of the segment")
    start: float = Field(..., description="Segment start time in seconds")
    end: float = Field(..., description="Segment end time in seconds")
    speaker: str = Field(..., description="Speaker ID for this segment")
    words: list[Word] = Field(default_factory=list, description="Words in this segment")


class StableRegion(BaseModel):
    """A region where speaker assignment is stable for reliable fingerprinting.
    
    Stable regions are periods where a single speaker talks continuously
    for at least `min_duration` seconds (typically 2.0s). These regions
    are used for building and updating persistent speaker profiles,
    ensuring fingerprints are extracted from clean, single-speaker audio.
    """
    speaker: str = Field(..., description="Speaker ID")
    start: float = Field(..., description="Region start time in seconds")
    end: float = Field(..., description="Region end time in seconds")
    duration: float = Field(..., description="Region duration in seconds")
    word_count: int = Field(..., description="Number of words in this region")


class TranscriptionOutput(BaseModel):
    """Standardized output schema from transcription + diarization pipeline.
    
    This schema captures the complete output of the transcription and speaker
    diarization pipeline, including:
    - Full transcript text
    - Speaker-labeled segments (merged from words)
    - Word-level data with DTW timestamps and speaker assignments
    - Stable regions for voice fingerprinting
    - Processing metadata
    
    Example usage:
        ```python
        from knowledge_system.schemas import TranscriptionOutput
        
        # After transcription + diarization
        output = TranscriptionOutput(
            source_id="abc123",
            duration_seconds=3600.0,
            language="en",
            text="Full transcript...",
            segments=[...],
            words=[...],
            stable_regions=[...],
            model="medium.en",
            diarization_model="pyannote/speaker-diarization-3.1",
            num_speakers=2,
            processing_time_seconds=180.5,
        )
        
        # Validate and serialize
        json_str = output.model_dump_json(indent=2)
        ```
    """
    # Source identification
    source_id: str = Field(..., description="Unique identifier for the source (video/audio)")
    
    # Audio metadata
    duration_seconds: float = Field(..., description="Total audio duration in seconds")
    language: str = Field(..., description="Detected or specified language code (e.g., 'en')")
    
    # Full text without speaker labels
    text: str = Field(..., description="Complete transcript text without speaker labels")
    
    # Speaker-labeled segments (merged from words)
    segments: list[Segment] = Field(
        default_factory=list,
        description="Speech segments grouped by speaker"
    )
    
    # Word-level data with timestamps and speakers
    words: list[Word] = Field(
        default_factory=list,
        description="Individual words with DTW timestamps and speaker assignments"
    )
    
    # Stable regions used for fingerprinting
    stable_regions: list[StableRegion] = Field(
        default_factory=list,
        description="Stable speaker regions for voice profile building"
    )
    
    # Model information
    model: str = Field(..., description="Whisper model used (e.g., 'medium.en')")
    diarization_model: str = Field(
        default="pyannote/speaker-diarization-3.1",
        description="Diarization model used"
    )
    
    # Processing metadata
    num_speakers: int = Field(..., description="Number of speakers detected/specified")
    processing_time_seconds: float = Field(
        ..., 
        description="Total processing time in seconds"
    )
    
    # Optional metadata
    channel_id: Optional[str] = Field(None, description="YouTube channel ID if applicable")
    channel_name: Optional[str] = Field(None, description="YouTube channel name if applicable")
    
    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "source_id": "dQw4w9WgXcQ",
                "duration_seconds": 212.0,
                "language": "en",
                "text": "Never gonna give you up, never gonna let you down...",
                "segments": [
                    {
                        "text": "Never gonna give you up",
                        "start": 0.0,
                        "end": 2.5,
                        "speaker": "SPEAKER_00",
                        "words": [
                            {"word": "Never", "start": 0.0, "end": 0.4, "speaker": "SPEAKER_00"},
                            {"word": "gonna", "start": 0.4, "end": 0.7, "speaker": "SPEAKER_00"},
                        ]
                    }
                ],
                "words": [
                    {"word": "Never", "start": 0.0, "end": 0.4, "speaker": "SPEAKER_00"},
                ],
                "stable_regions": [
                    {"speaker": "SPEAKER_00", "start": 0.0, "end": 30.0, "duration": 30.0, "word_count": 50}
                ],
                "model": "medium.en",
                "diarization_model": "pyannote/speaker-diarization-3.1",
                "num_speakers": 1,
                "processing_time_seconds": 15.5,
            }
        }
