"""
Transcript Fetcher Module

Provides unified interface for fetching transcripts from YouTube or Whisper.
Implements quality assessment for auto-upgrade decisions.
"""

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

from knowledge_system.logger import get_logger

logger = get_logger(__name__)


class TranscriptSourceType(str, Enum):
    """Type of transcript source."""
    YOUTUBE = "youtube"
    WHISPER = "whisper"
    MANUAL = "manual"


@dataclass
class TranscriptSegment:
    """A segment of transcript with timing information."""
    text: str
    start: float  # Start time in seconds
    duration: float  # Duration in seconds
    
    @property
    def end(self) -> float:
        """End time in seconds."""
        return self.start + self.duration


@dataclass
class TranscriptWord:
    """A single word with timing information (for Whisper word-level timestamps)."""
    word: str
    start: float  # Start time in seconds
    end: float  # End time in seconds


@dataclass
class TranscriptResult:
    """
    Result from transcript fetching.
    
    Contains the transcript text, segments/words with timestamps,
    metadata about the source, and quality metrics.
    """
    text: str  # Full transcript text
    segments: list[TranscriptSegment]  # Segment-level timing (always available)
    words: Optional[list[TranscriptWord]]  # Word-level timing (Whisper only)
    source_type: TranscriptSourceType
    video_id: Optional[str] = None
    language: str = "en"
    quality_score: float = 1.0  # 0.0-1.0, estimated quality
    processing_time_seconds: float = 0.0
    timestamp_precision: str = "segment"  # "word" or "segment"
    
    @property
    def has_word_timestamps(self) -> bool:
        """Whether word-level timestamps are available."""
        return self.words is not None and len(self.words) > 0


class TranscriptFetcher:
    """
    Unified interface for fetching transcripts from YouTube or Whisper.
    
    Supports:
    - YouTube Transcript API (fast path: ~5 seconds)
    - Whisper transcription (accurate path: 10-15 minutes)
    - Automatic quality assessment and upgrade decisions
    
    Usage:
        fetcher = TranscriptFetcher()
        result = fetcher.get_transcript(
            "https://youtube.com/watch?v=abc123",
            prefer_youtube=True,
            quality_threshold=0.7
        )
    """
    
    def __init__(
        self,
        whisper_model: str = "medium",
        enable_word_timestamps: bool = True,
    ):
        """
        Initialize transcript fetcher.
        
        Args:
            whisper_model: Whisper model size for transcription
            enable_word_timestamps: Whether to extract word-level timestamps
        """
        self.whisper_model = whisper_model
        self.enable_word_timestamps = enable_word_timestamps
        
        # Lazy imports to avoid loading heavy dependencies
        self._youtube_api = None
        self._whisper_processor = None
    
    def get_transcript(
        self,
        source_url: str,
        audio_path: Optional[Path] = None,
        prefer_youtube: bool = True,
        quality_threshold: float = 0.7,
        force_whisper: bool = False,
    ) -> TranscriptResult:
        """
        Get transcript from the best available source.
        
        Args:
            source_url: URL of the source (YouTube URL or other)
            audio_path: Path to audio file (required for Whisper)
            prefer_youtube: Try YouTube first if available
            quality_threshold: Minimum quality to accept YouTube transcript
            force_whisper: Always use Whisper regardless of YouTube availability
        
        Returns:
            TranscriptResult with transcript text and timing information
        """
        start_time = time.time()
        
        # Check if this is a YouTube URL
        video_id = self._extract_youtube_video_id(source_url)
        is_youtube = video_id is not None
        
        # Determine which path to take
        if force_whisper:
            logger.info("Forcing Whisper transcription (force_whisper=True)")
            return self._get_whisper_transcript(audio_path, start_time)
        
        if is_youtube and prefer_youtube:
            try:
                youtube_result = self._get_youtube_transcript(video_id, start_time)
                
                # Check quality
                if youtube_result.quality_score >= quality_threshold:
                    logger.info(
                        f"YouTube transcript accepted (quality={youtube_result.quality_score:.2f} >= {quality_threshold})"
                    )
                    return youtube_result
                else:
                    logger.info(
                        f"YouTube transcript quality too low ({youtube_result.quality_score:.2f} < {quality_threshold}), "
                        f"upgrading to Whisper"
                    )
                    # Fall through to Whisper
            except Exception as e:
                logger.warning(f"YouTube transcript unavailable: {e}, falling back to Whisper")
        
        # Use Whisper
        if audio_path is None:
            raise ValueError("audio_path required for Whisper transcription")
        
        return self._get_whisper_transcript(audio_path, start_time, video_id=video_id)
    
    def _extract_youtube_video_id(self, url: str) -> Optional[str]:
        """Extract YouTube video ID from URL."""
        if not url:
            return None
        
        # Handle various YouTube URL formats
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com/shorts/([a-zA-Z0-9_-]{11})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        # Try query string parsing
        try:
            parsed = urlparse(url)
            if 'youtube.com' in parsed.netloc:
                qs = parse_qs(parsed.query)
                if 'v' in qs:
                    return qs['v'][0]
        except Exception:
            pass
        
        return None
    
    def _get_youtube_transcript(
        self,
        video_id: str,
        start_time: float,
    ) -> TranscriptResult:
        """
        Fetch transcript from YouTube's auto-generated captions.
        
        Args:
            video_id: YouTube video ID
            start_time: Time when request started (for timing)
        
        Returns:
            TranscriptResult with YouTube transcript
        """
        # Lazy import
        if self._youtube_api is None:
            try:
                from youtube_transcript_api import YouTubeTranscriptApi
                self._youtube_api = YouTubeTranscriptApi()
            except ImportError:
                raise ImportError(
                    "youtube-transcript-api not installed. "
                    "Install with: pip install youtube-transcript-api"
                )
        
        logger.info(f"Fetching YouTube transcript for video {video_id}")
        
        # Get transcript (API v1.0+ uses .fetch() and returns objects)
        transcript_data = self._youtube_api.fetch(video_id)
        
        # Convert to our format (new API returns objects with .text, .start, .duration attrs)
        segments = [
            TranscriptSegment(
                text=item.text,
                start=item.start,
                duration=item.duration,
            )
            for item in transcript_data
        ]
        
        # Build full text
        full_text = ' '.join(segment.text for segment in segments)
        
        # Estimate quality based on heuristics
        quality_score = self._estimate_youtube_quality(segments, full_text)
        
        processing_time = time.time() - start_time
        
        return TranscriptResult(
            text=full_text,
            segments=segments,
            words=None,  # YouTube doesn't provide word-level
            source_type=TranscriptSourceType.YOUTUBE,
            video_id=video_id,
            quality_score=quality_score,
            processing_time_seconds=processing_time,
            timestamp_precision="segment",
        )
    
    def _estimate_youtube_quality(
        self,
        segments: list[TranscriptSegment],
        full_text: str,
    ) -> float:
        """
        Estimate quality of YouTube transcript using heuristics.
        
        Quality indicators:
        - Ratio of recognized words vs [Music], [Applause], etc.
        - Average segment length (very short = garbled)
        - Presence of obvious errors (repeated words, gibberish)
        
        Returns:
            Quality score from 0.0 to 1.0
        """
        if not segments or not full_text:
            return 0.0
        
        score = 1.0
        
        # Check for music/sound markers
        markers = ['[Music]', '[Applause]', '[Laughter]', '[Inaudible]', '[MUSIC]']
        marker_count = sum(full_text.count(marker) for marker in markers)
        if marker_count > 10:
            score -= 0.2
        elif marker_count > 5:
            score -= 0.1
        
        # Check average segment length
        avg_segment_length = len(full_text) / len(segments) if segments else 0
        if avg_segment_length < 10:  # Very short segments = poor quality
            score -= 0.2
        elif avg_segment_length < 20:
            score -= 0.1
        
        # Check for repeated words (common auto-caption error)
        words = full_text.lower().split()
        if words:
            repeated = sum(1 for i in range(len(words) - 1) if words[i] == words[i + 1])
            repeat_ratio = repeated / len(words)
            if repeat_ratio > 0.1:  # More than 10% repeated
                score -= 0.2
            elif repeat_ratio > 0.05:
                score -= 0.1
        
        # Check for very long words (gibberish)
        long_words = sum(1 for word in words if len(word) > 25)
        if long_words > 5:
            score -= 0.15
        
        return max(0.0, min(1.0, score))
    
    def _get_whisper_transcript(
        self,
        audio_path: Path,
        start_time: float,
        video_id: Optional[str] = None,
    ) -> TranscriptResult:
        """
        Transcribe audio using Whisper.
        
        Args:
            audio_path: Path to audio file
            start_time: Time when request started (for timing)
            video_id: Optional YouTube video ID for metadata
        
        Returns:
            TranscriptResult with Whisper transcript
        """
        # Lazy import
        if self._whisper_processor is None:
            from knowledge_system.processors.whisper_cpp_transcribe import (
                WhisperCppTranscribeProcessor,
            )
            self._whisper_processor = WhisperCppTranscribeProcessor(
                model=self.whisper_model,
                enable_word_timestamps=self.enable_word_timestamps,
            )
        
        logger.info(f"Transcribing with Whisper (model={self.whisper_model}): {audio_path}")
        
        # Run transcription
        result = self._whisper_processor.process(str(audio_path))
        
        # Extract segments
        segments = []
        if hasattr(result, 'segments') and result.segments:
            for seg in result.segments:
                segments.append(TranscriptSegment(
                    text=seg.get('text', ''),
                    start=seg.get('start', 0.0),
                    duration=seg.get('end', 0.0) - seg.get('start', 0.0),
                ))
        
        # Extract words if available
        words = None
        if self.enable_word_timestamps and hasattr(result, 'words') and result.words:
            words = [
                TranscriptWord(
                    word=w.get('word', ''),
                    start=w.get('start', 0.0),
                    end=w.get('end', 0.0),
                )
                for w in result.words
            ]
        
        # Get full text
        full_text = result.text if hasattr(result, 'text') else ''
        if not full_text and segments:
            full_text = ' '.join(seg.text for seg in segments)
        
        processing_time = time.time() - start_time
        
        return TranscriptResult(
            text=full_text,
            segments=segments,
            words=words,
            source_type=TranscriptSourceType.WHISPER,
            video_id=video_id,
            quality_score=0.95,  # Whisper is high quality
            processing_time_seconds=processing_time,
            timestamp_precision="word" if words else "segment",
        )
    
    def assess_quality(self, transcript_result: TranscriptResult) -> dict[str, Any]:
        """
        Perform detailed quality assessment of a transcript.
        
        Returns dict with quality metrics for logging/debugging.
        """
        text = transcript_result.text
        segments = transcript_result.segments
        
        # Calculate metrics
        word_count = len(text.split())
        segment_count = len(segments)
        avg_segment_words = word_count / segment_count if segment_count else 0
        
        # Check for markers
        markers = ['[Music]', '[Applause]', '[Laughter]', '[Inaudible]']
        marker_count = sum(text.count(m) for m in markers)
        
        return {
            "source_type": transcript_result.source_type.value,
            "quality_score": transcript_result.quality_score,
            "word_count": word_count,
            "segment_count": segment_count,
            "avg_segment_words": avg_segment_words,
            "marker_count": marker_count,
            "has_word_timestamps": transcript_result.has_word_timestamps,
            "processing_time_seconds": transcript_result.processing_time_seconds,
        }

