"""
Context Expansion for Evidence Spans

This module provides functionality to expand precise evidence quotes into
extended conversational context using smart boundary detection.
"""

import logging

from .types import EvidenceSpan, Segment

logger = logging.getLogger(__name__)


def parse_timestamp_to_seconds(timestamp: str) -> float | None:
    """Parse timestamp string (HH:MM:SS or MM:SS) to seconds."""
    try:
        parts = timestamp.split(":")
        if len(parts) == 3:  # HH:MM:SS
            hours, minutes, seconds = map(float, parts)
            return hours * 3600 + minutes * 60 + seconds
        elif len(parts) == 2:  # MM:SS
            minutes, seconds = map(float, parts)
            return minutes * 60 + seconds
        else:
            return float(timestamp)  # Assume it's already in seconds
    except (ValueError, AttributeError):
        return None


def seconds_to_timestamp(seconds: float) -> str:
    """Convert seconds to timestamp string (HH:MM:SS)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"


def find_conversational_boundaries(
    quote_start: float,
    quote_end: float,
    segments: list[Segment],
    target_context_seconds: int = 45,
) -> tuple[float, float, str]:
    """
    Find smart conversational boundaries around a quote.

    This implements "Option 2: Smart Conversational Boundaries" by finding
    natural topic/speaker changes around the quote rather than using fixed windows.

    Args:
        quote_start: Quote start time in seconds
        quote_end: Quote end time in seconds
        segments: List of all segments in the episode
        target_context_seconds: Target context duration (default 45 seconds)

    Returns:
        tuple of (context_start_seconds, context_end_seconds, context_text)
    """

    # Convert segments to (start_time, end_time, segment) tuples for easier processing
    segment_times = []
    for seg in segments:
        start_sec = parse_timestamp_to_seconds(seg.t0)
        end_sec = parse_timestamp_to_seconds(seg.t1)
        if start_sec is not None and end_sec is not None:
            segment_times.append((start_sec, end_sec, seg))

    # Sort by start time
    segment_times.sort(key=lambda x: x[0])

    # Find the segment containing the quote
    quote_segment_idx = None
    for i, (start, end, seg) in enumerate(segment_times):
        if start <= quote_start <= end:
            quote_segment_idx = i
            break

    if quote_segment_idx is None:
        # Fallback: return the quote itself
        logger.warning(f"Could not find segment for quote at {quote_start}")
        return quote_start, quote_end, ""

    # Start with the quote segment
    context_start = quote_start
    context_end = quote_end
    context_segments = [segment_times[quote_segment_idx][2]]

    # Expand backwards to find natural boundary
    current_speaker = segment_times[quote_segment_idx][2].speaker
    segment_times[quote_segment_idx][2].topic_guess

    # Look backwards for speaker/topic changes or time limit
    for i in range(quote_segment_idx - 1, -1, -1):
        seg_start, seg_end, seg = segment_times[i]

        # Check if we've reached our time target
        potential_duration = context_end - seg_start
        if potential_duration > target_context_seconds:
            break

        # Check for natural boundaries (speaker or topic change)
        if seg.speaker != current_speaker and current_speaker.lower() not in [
            "narrator",
            "host",
            "unknown",
        ]:
            # Found speaker change - this might be a good boundary
            # But include one more segment for context unless it would exceed time limit
            if (
                potential_duration + (seg_end - seg_start)
                <= target_context_seconds * 1.2
            ):
                context_start = seg_start
                context_segments.insert(0, seg)
            break

        # Include this segment
        context_start = seg_start
        context_segments.insert(0, seg)

    # Look forwards for speaker/topic changes or time limit
    for i in range(quote_segment_idx + 1, len(segment_times)):
        seg_start, seg_end, seg = segment_times[i]

        # Check if we've reached our time target
        potential_duration = seg_end - context_start
        if potential_duration > target_context_seconds:
            break

        # Check for natural boundaries
        if seg.speaker != current_speaker and current_speaker.lower() not in [
            "narrator",
            "host",
            "unknown",
        ]:
            # Found speaker change
            if (
                potential_duration + (seg_end - seg_start)
                <= target_context_seconds * 1.2
            ):
                context_end = seg_end
                context_segments.append(seg)
            break

        # Include this segment
        context_end = seg_end
        context_segments.append(seg)

    # Build context text
    context_text = "\n".join(
        [f"[{seg.t0}-{seg.t1}] {seg.speaker}: {seg.text}" for seg in context_segments]
    )

    return context_start, context_end, context_text


def expand_evidence_context(
    evidence: EvidenceSpan,
    segments: list[Segment],
    method: str = "conversational_boundary",
) -> EvidenceSpan:
    """
    Expand an evidence span with extended conversational context.

    Args:
        evidence: Original evidence span with precise quote
        segments: All segments from the episode
        method: Context expansion method ("conversational_boundary", "fixed_window", "segment")

    Returns:
        Updated evidence span with context fields populated
    """

    # Parse original timestamps
    quote_start = parse_timestamp_to_seconds(evidence.t0)
    quote_end = parse_timestamp_to_seconds(evidence.t1)

    if quote_start is None or quote_end is None:
        logger.warning(f"Could not parse timestamps: {evidence.t0}, {evidence.t1}")
        return evidence

    if method == "conversational_boundary":
        context_start, context_end, context_text = find_conversational_boundaries(
            quote_start, quote_end, segments
        )
    elif method == "fixed_window":
        # Simple 30-second window around quote
        window_seconds = 30
        context_start = max(0, quote_start - window_seconds // 2)
        context_end = quote_end + window_seconds // 2

        # Find segments within this window
        context_segments = []
        for seg in segments:
            seg_start = parse_timestamp_to_seconds(seg.t0)
            seg_end = parse_timestamp_to_seconds(seg.t1)
            if (
                seg_start is not None
                and seg_end is not None
                and seg_start < context_end
                and seg_end > context_start
            ):
                context_segments.append(seg)

        context_text = "\n".join(
            [
                f"[{seg.t0}-{seg.t1}] {seg.speaker}: {seg.text}"
                for seg in context_segments
            ]
        )
    elif method == "segment":
        # Use the entire segment containing the quote
        quote_segment = None
        for seg in segments:
            if seg.segment_id == evidence.segment_id:
                quote_segment = seg
                break

        if quote_segment:
            context_start = parse_timestamp_to_seconds(quote_segment.t0) or quote_start
            context_end = parse_timestamp_to_seconds(quote_segment.t1) or quote_end
            context_text = f"[{quote_segment.t0}-{quote_segment.t1}] {quote_segment.speaker}: {quote_segment.text}"
        else:
            context_start, context_end, context_text = (
                quote_start,
                quote_end,
                evidence.quote,
            )
    else:
        # Default to exact quote
        context_start, context_end, context_text = (
            quote_start,
            quote_end,
            evidence.quote,
        )

    # Update the evidence span
    evidence.context_t0 = seconds_to_timestamp(context_start)
    evidence.context_t1 = seconds_to_timestamp(context_end)
    evidence.context_text = context_text

    # Map method to valid context_type
    if method == "conversational_boundary":
        evidence.context_type = "extended"
    elif method == "fixed_window":
        evidence.context_type = "extended"
    elif method == "segment":
        evidence.context_type = "segment"
    else:
        evidence.context_type = "exact"

    return evidence


def expand_all_evidence_context(
    evidence_spans: list[EvidenceSpan],
    segments: list[Segment],
    method: str = "conversational_boundary",
) -> list[EvidenceSpan]:
    """
    Expand context for all evidence spans in a list.

    Args:
        evidence_spans: List of evidence spans to expand
        segments: All segments from the episode
        method: Context expansion method

    Returns:
        List of evidence spans with context populated
    """
    return [
        expand_evidence_context(evidence, segments, method)
        for evidence in evidence_spans
    ]
