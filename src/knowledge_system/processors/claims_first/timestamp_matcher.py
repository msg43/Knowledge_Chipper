"""
Timestamp Matcher Module

Provides fuzzy matching of claim evidence quotes to transcript timestamps.
Handles both word-level (Whisper) and segment-level (YouTube) timestamps.
"""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Optional

from knowledge_system.logger import get_logger

from .transcript_fetcher import TranscriptResult, TranscriptSegment, TranscriptWord

logger = get_logger(__name__)


@dataclass
class TimestampResult:
    """
    Result from timestamp matching.
    
    Contains the matched timestamp range and confidence score.
    """
    timestamp_start: float  # Start time in seconds
    timestamp_end: float  # End time in seconds
    confidence: float  # 0.0-1.0, how confident we are in the match
    precision: str  # "word" or "segment"
    matched_text: str  # The text that was matched
    match_method: str  # "exact", "fuzzy", "semantic", "fallback"
    
    @property
    def duration(self) -> float:
        """Duration of the matched segment in seconds."""
        return self.timestamp_end - self.timestamp_start
    
    @property
    def midpoint(self) -> float:
        """Midpoint timestamp for jumping to approximate location."""
        return (self.timestamp_start + self.timestamp_end) / 2


class TimestampMatcher:
    """
    Matches claim evidence quotes to transcript timestamps.
    
    Supports:
    - Exact matching (verbatim quote found)
    - Fuzzy matching (handle LLM paraphrasing)
    - Semantic fallback (find most similar region)
    - Both word-level and segment-level timestamps
    
    Usage:
        matcher = TimestampMatcher()
        result = matcher.match_claim_to_timestamps(
            claim={"canonical": "...", "evidence": "The Fed creates..."},
            transcript=transcript_result,
            threshold=0.7
        )
    """
    
    def __init__(
        self,
        default_threshold: float = 0.7,
        min_words_to_match: int = 3,
    ):
        """
        Initialize timestamp matcher.
        
        Args:
            default_threshold: Default similarity threshold for fuzzy matching
            min_words_to_match: Minimum number of words required for matching
        """
        self.default_threshold = default_threshold
        self.min_words_to_match = min_words_to_match
    
    def match_claim_to_timestamps(
        self,
        claim: dict,
        transcript: TranscriptResult,
        threshold: Optional[float] = None,
    ) -> Optional[TimestampResult]:
        """
        Match a claim's evidence quote to transcript timestamps.
        
        Args:
            claim: Claim dict with 'evidence' or 'evidence_quote' field
            transcript: TranscriptResult with segments and optionally words
            threshold: Similarity threshold (0.0-1.0)
        
        Returns:
            TimestampResult if match found, None otherwise
        """
        threshold = threshold or self.default_threshold
        
        # Extract evidence quote from claim
        evidence = claim.get('evidence') or claim.get('evidence_quote') or ''
        if not evidence:
            logger.warning("Claim has no evidence quote for timestamp matching")
            return None
        
        evidence_clean = self._normalize_text(evidence)
        evidence_words = evidence_clean.split()
        
        if len(evidence_words) < self.min_words_to_match:
            logger.warning(f"Evidence too short for matching: {len(evidence_words)} words")
            return None
        
        # Try word-level matching first if available
        if transcript.has_word_timestamps:
            result = self._match_with_words(evidence_clean, transcript.words, threshold)
            if result:
                return result
        
        # Fall back to segment-level matching
        result = self._match_with_segments(evidence_clean, transcript.segments, threshold)
        if result:
            return result
        
        # Final fallback: find most similar segment
        return self._semantic_fallback(evidence_clean, transcript.segments)
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for matching (lowercase, strip punctuation)."""
        # Convert to lowercase
        text = text.lower()
        # Remove punctuation except apostrophes
        text = re.sub(r"[^\w\s']", " ", text)
        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _match_with_words(
        self,
        evidence: str,
        words: list[TranscriptWord],
        threshold: float,
    ) -> Optional[TimestampResult]:
        """
        Match evidence quote using word-level timestamps.
        
        Uses sliding window to find best matching sequence.
        """
        if not words:
            return None
        
        evidence_words = evidence.split()
        n_evidence = len(evidence_words)
        
        # Create searchable text from words
        transcript_words = [self._normalize_text(w.word) for w in words]
        n_transcript = len(transcript_words)
        
        if n_transcript < n_evidence:
            return None
        
        best_match = None
        best_score = 0.0
        best_indices = (0, 0)
        
        # Sliding window search
        window_size = n_evidence
        for window_mult in [1.0, 1.2, 1.5, 2.0]:  # Try different window sizes
            adjusted_window = int(window_size * window_mult)
            
            for i in range(n_transcript - adjusted_window + 1):
                window_words = transcript_words[i:i + adjusted_window]
                window_text = ' '.join(window_words)
                
                # Calculate similarity
                score = self._calculate_similarity(evidence, window_text)
                
                if score > best_score:
                    best_score = score
                    best_indices = (i, i + adjusted_window)
                    best_match = window_text
        
        if best_score >= threshold:
            start_idx, end_idx = best_indices
            return TimestampResult(
                timestamp_start=words[start_idx].start,
                timestamp_end=words[min(end_idx - 1, len(words) - 1)].end,
                confidence=best_score,
                precision="word",
                matched_text=best_match,
                match_method="fuzzy" if best_score < 0.95 else "exact",
            )
        
        return None
    
    def _match_with_segments(
        self,
        evidence: str,
        segments: list[TranscriptSegment],
        threshold: float,
    ) -> Optional[TimestampResult]:
        """
        Match evidence quote using segment-level timestamps.
        
        Searches individual segments and consecutive segment pairs.
        """
        if not segments:
            return None
        
        best_match = None
        best_score = 0.0
        best_segment_range = (0, 0)
        
        # Search individual segments
        for i, segment in enumerate(segments):
            segment_text = self._normalize_text(segment.text)
            score = self._calculate_similarity(evidence, segment_text)
            
            if score > best_score:
                best_score = score
                best_segment_range = (i, i + 1)
                best_match = segment_text
        
        # Search consecutive segment pairs/triples
        for window_size in [2, 3, 4]:
            for i in range(len(segments) - window_size + 1):
                combined_text = ' '.join(
                    self._normalize_text(segments[j].text)
                    for j in range(i, i + window_size)
                )
                score = self._calculate_similarity(evidence, combined_text)
                
                if score > best_score:
                    best_score = score
                    best_segment_range = (i, i + window_size)
                    best_match = combined_text
        
        if best_score >= threshold:
            start_idx, end_idx = best_segment_range
            return TimestampResult(
                timestamp_start=segments[start_idx].start,
                timestamp_end=segments[end_idx - 1].end,
                confidence=best_score,
                precision="segment",
                matched_text=best_match,
                match_method="fuzzy" if best_score < 0.95 else "exact",
            )
        
        return None
    
    def _semantic_fallback(
        self,
        evidence: str,
        segments: list[TranscriptSegment],
    ) -> Optional[TimestampResult]:
        """
        Find most similar segment when exact/fuzzy matching fails.
        
        Always returns a result (unless no segments), but with low confidence.
        """
        if not segments:
            return None
        
        best_segment_idx = 0
        best_score = 0.0
        
        for i, segment in enumerate(segments):
            segment_text = self._normalize_text(segment.text)
            score = self._calculate_similarity(evidence, segment_text)
            
            if score > best_score:
                best_score = score
                best_segment_idx = i
        
        segment = segments[best_segment_idx]
        
        return TimestampResult(
            timestamp_start=segment.start,
            timestamp_end=segment.end,
            confidence=best_score * 0.5,  # Reduce confidence for fallback
            precision="segment",
            matched_text=segment.text,
            match_method="fallback",
        )
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity between two text strings.
        
        Uses SequenceMatcher for fuzzy string matching.
        Returns value from 0.0 (no match) to 1.0 (exact match).
        """
        if not text1 or not text2:
            return 0.0
        
        # Use SequenceMatcher for basic similarity
        matcher = SequenceMatcher(None, text1, text2)
        base_score = matcher.ratio()
        
        # Boost score if key words overlap
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if words1 and words2:
            overlap = len(words1 & words2)
            total = len(words1 | words2)
            word_overlap = overlap / total if total else 0
            
            # Weight: 70% sequence match, 30% word overlap
            return 0.7 * base_score + 0.3 * word_overlap
        
        return base_score
    
    def match_multiple_claims(
        self,
        claims: list[dict],
        transcript: TranscriptResult,
        threshold: Optional[float] = None,
    ) -> list[tuple[dict, Optional[TimestampResult]]]:
        """
        Match multiple claims to timestamps.
        
        Args:
            claims: List of claim dicts
            transcript: TranscriptResult
            threshold: Similarity threshold
        
        Returns:
            List of (claim, TimestampResult or None) tuples
        """
        results = []
        for claim in claims:
            result = self.match_claim_to_timestamps(claim, transcript, threshold)
            results.append((claim, result))
        
        return results

