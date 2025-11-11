#!/usr/bin/env python3
"""
Podcast Ad Detector

Detects and filters advertisement segments from podcast transcriptions
to prevent ad content from polluting claim extraction.
"""

import re
from typing import Any

from ..logger import get_logger

logger = get_logger(__name__)


class PodcastAdDetector:
    """
    Detects advertisement segments in podcast transcriptions.

    Uses multiple detection methods:
    1. Keyword matching (promo codes, sponsor phrases)
    2. Pattern recognition (URLs, discount codes)
    3. Segment duration analysis (ads are typically 30-90 seconds)
    4. LLM-based classification (optional, for high accuracy)
    """

    # Common ad indicator phrases
    AD_KEYWORDS = [
        # Sponsor intros
        "this episode is sponsored by",
        "this podcast is brought to you by",
        "today's sponsor is",
        "our sponsor for today",
        "brought to you by",
        "sponsored by",
        # Promo codes
        "promo code",
        "discount code",
        "coupon code",
        "use code",
        "enter code",
        "code:",
        # Call to action
        "visit",
        "go to",
        "head over to",
        "check out",
        "sign up at",
        "get % off",
        "% discount",
        "free trial",
        "first month free",
        # Patreon/Support
        "support the show",
        "join the patreon",
        "become a patron",
        "patreon.com",
        # Common sponsor categories
        "mattress",
        "vpn",
        "meal kit",
        "audiobook",
        "podcast app",
        "hosting service",
        "insurance",
        "investing app",
    ]

    # URL patterns (strong ad indicator)
    URL_PATTERN = re.compile(
        r"(?:https?://)?(?:www\.)?[a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?",
        re.IGNORECASE,
    )

    # Promo code patterns
    PROMO_CODE_PATTERN = re.compile(
        r"\b(?:code|promo|coupon)\s+[A-Z0-9]{3,15}\b", re.IGNORECASE
    )

    # Discount patterns
    DISCOUNT_PATTERN = re.compile(r"\b\d{1,3}\s*%\s*(?:off|discount)\b", re.IGNORECASE)

    def __init__(self, sensitivity: str = "medium"):
        """
        Initialize ad detector.

        Args:
            sensitivity: Detection sensitivity
                - "low": Only flag obvious ads (high precision, low recall)
                - "medium": Balanced detection (default)
                - "high": Flag anything suspicious (high recall, lower precision)
        """
        self.sensitivity = sensitivity
        logger.info(f"PodcastAdDetector initialized with sensitivity={sensitivity}")

    def detect_ads_in_segments(
        self, segments: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Detect advertisement segments in transcription.

        Args:
            segments: List of transcription segments with 'text', 'start_time', 'end_time'

        Returns:
            List of segments with added 'is_ad' and 'ad_confidence' fields

        Example:
            >>> segments = [
            ...     {"text": "This episode is sponsored by...", "start_time": 10.0, "end_time": 40.0},
            ...     {"text": "Now let's talk about...", "start_time": 40.0, "end_time": 50.0}
            ... ]
            >>> detector = PodcastAdDetector()
            >>> result = detector.detect_ads_in_segments(segments)
            >>> result[0]['is_ad']  # True
            >>> result[1]['is_ad']  # False
        """
        annotated_segments = []

        for segment in segments:
            text = segment.get("text", "")
            is_ad, confidence, reasons = self._classify_segment(text, segment)

            annotated_segment = segment.copy()
            annotated_segment["is_ad"] = is_ad
            annotated_segment["ad_confidence"] = confidence
            annotated_segment["ad_detection_reasons"] = reasons

            if is_ad:
                logger.debug(
                    f"Ad detected (confidence={confidence:.2f}): {text[:50]}... "
                    f"Reasons: {', '.join(reasons)}"
                )

            annotated_segments.append(annotated_segment)

        ad_count = sum(1 for s in annotated_segments if s["is_ad"])
        logger.info(f"Detected {ad_count}/{len(segments)} ad segments")

        return annotated_segments

    def _classify_segment(
        self, text: str, segment: dict[str, Any]
    ) -> tuple[bool, float, list[str]]:
        """
        Classify a segment as ad or content.

        Returns:
            (is_ad, confidence, reasons)
        """
        reasons = []
        score = 0.0

        text_lower = text.lower()

        # Check for ad keywords
        keyword_matches = sum(
            1 for keyword in self.AD_KEYWORDS if keyword in text_lower
        )
        if keyword_matches > 0:
            score += keyword_matches * 0.3
            reasons.append(f"{keyword_matches} ad keywords")

        # Check for URLs
        if self.URL_PATTERN.search(text):
            score += 0.4
            reasons.append("contains URL")

        # Check for promo codes
        if self.PROMO_CODE_PATTERN.search(text):
            score += 0.5
            reasons.append("contains promo code")

        # Check for discount offers
        if self.DISCOUNT_PATTERN.search(text):
            score += 0.4
            reasons.append("contains discount offer")

        # Check segment duration (ads are typically 30-90 seconds)
        start_time = segment.get("start_time", 0)
        end_time = segment.get("end_time", 0)
        duration = end_time - start_time

        if 20 < duration < 120 and score > 0:
            # Segment is ad-length and has ad indicators
            score += 0.2
            reasons.append(f"ad-length duration ({duration:.1f}s)")

        # Apply sensitivity threshold
        thresholds = {
            "low": 0.8,  # Only flag very obvious ads
            "medium": 0.5,  # Balanced
            "high": 0.3,  # Flag anything suspicious
        }
        threshold = thresholds.get(self.sensitivity, 0.5)

        is_ad = score >= threshold
        confidence = min(score, 1.0)

        return is_ad, confidence, reasons

    def filter_ads_from_segments(
        self, segments: list[dict[str, Any]], remove_ads: bool = True
    ) -> list[dict[str, Any]]:
        """
        Filter advertisement segments from transcription.

        Args:
            segments: List of transcription segments
            remove_ads: If True, remove ad segments. If False, just mark them.

        Returns:
            Filtered list of segments (with ads removed or marked)
        """
        # Detect ads
        annotated_segments = self.detect_ads_in_segments(segments)

        if remove_ads:
            # Remove ad segments entirely
            filtered_segments = [s for s in annotated_segments if not s["is_ad"]]
            removed_count = len(annotated_segments) - len(filtered_segments)
            logger.info(f"Removed {removed_count} ad segments")
            return filtered_segments
        else:
            # Keep ads but mark them
            logger.info("Ads marked but not removed")
            return annotated_segments

    def get_ad_free_text(self, segments: list[dict[str, Any]]) -> str:
        """
        Get concatenated text with ads removed.

        Args:
            segments: List of transcription segments

        Returns:
            Ad-free text
        """
        filtered_segments = self.filter_ads_from_segments(segments, remove_ads=True)
        return " ".join(s.get("text", "") for s in filtered_segments)


def detect_ads_in_transcription(
    segments: list[dict[str, Any]], sensitivity: str = "medium"
) -> list[dict[str, Any]]:
    """
    Convenience function to detect ads in transcription segments.

    Args:
        segments: List of transcription segments
        sensitivity: Detection sensitivity ("low", "medium", "high")

    Returns:
        Segments with ad detection annotations
    """
    detector = PodcastAdDetector(sensitivity=sensitivity)
    return detector.detect_ads_in_segments(segments)


def filter_ads_from_transcription(
    segments: list[dict[str, Any]], sensitivity: str = "medium", remove_ads: bool = True
) -> list[dict[str, Any]]:
    """
    Convenience function to filter ads from transcription segments.

    Args:
        segments: List of transcription segments
        sensitivity: Detection sensitivity ("low", "medium", "high")
        remove_ads: If True, remove ad segments. If False, just mark them.

    Returns:
        Filtered segments
    """
    detector = PodcastAdDetector(sensitivity=sensitivity)
    return detector.filter_ads_from_segments(segments, remove_ads=remove_ads)
