"""
Speaker Attribution System

Maps generic speaker labels (Speaker_1, Speaker_2) to actual speaker names.
Provides multiple detection methods with a clear priority hierarchy.
"""

import re
from pathlib import Path

import yaml

try:
    from ..logger import get_logger
except ImportError:
    import logging

    def get_logger(name):
        return logging.getLogger(name)


logger = get_logger(__name__)


class SpeakerAttributor:
    """
    Speaker attribution with multiple detection methods and clear priority hierarchy.

    PRIORITY ORDER (highest to lowest):
    1. Manual Override - User explicitly sets speaker mapping
    2. Video-Specific Mapping - Pre-configured mappings for specific videos
    3. Content-Based Detection - Keyword analysis
    4. Default Fallback - Keep original Speaker_N labels
    """

    def __init__(self, config_path: Path | None = None):
        self.config_path = (
            config_path
            or Path(__file__).parent.parent.parent.parent
            / "config"
            / "speaker_attribution.yaml"
        )
        self.load_config()

    def load_config(self):
        """Load speaker attribution configuration."""
        try:
            if self.config_path.exists():
                with open(self.config_path) as f:
                    config = yaml.safe_load(f)
                self._load_from_config(config)
                logger.info(f"Loaded speaker config from {self.config_path}")
            else:
                self._create_default_config()
        except Exception as e:
            logger.warning(f"Failed to load speaker config: {e}")
            self._create_default_config()

    def _load_from_config(self, config):
        """Load configuration from YAML."""
        self.content_patterns = config.get("content_detection", {}).get("keywords", {})
        self.video_mappings = config.get("video_mappings", {})
        self.speaker_profiles = config.get("speaker_profiles", {})

    def _create_default_config(self):
        """Create default configuration for Peterson/Harris debates."""
        default_config = {
            "content_detection": {
                "keywords": {
                    "peterson_indicators": [
                        "roughly speaking",
                        "clean up your room",
                        "archetypal",
                        "hierarchies",
                        "dominance hierarchy",
                        "responsibility",
                        "meaning",
                        "chaos",
                        "order",
                        "lobster",
                        "bucko",
                    ],
                    "harris_indicators": [
                        "moral landscape",
                        "consciousness",
                        "meditation",
                        "free will",
                        "neuroscience",
                        "rationality",
                        "illusion",
                        "mindfulness",
                        "secular",
                        "dharma",
                    ],
                }
            },
            # video_mappings removed - now handled by database learning system
            "speaker_profiles": {
                "Jordan Peterson": {
                    "aliases": ["Peterson", "JP", "Jordan B Peterson"],
                    "characteristics": [
                        "canadian accent",
                        "deeper voice",
                        "measured speech",
                    ],
                },
                "Sam Harris": {
                    "aliases": ["Harris", "SH", "Sam"],
                    "characteristics": [
                        "american accent",
                        "precise diction",
                        "analytical tone",
                    ],
                },
            },
        }

        # Create config directory and file
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w") as f:
            yaml.dump(default_config, f, default_flow_style=False)

        self._load_from_config(default_config)
        logger.info(f"Created default speaker config at {self.config_path}")

    def attribute_speakers(
        self,
        speaker_segments: list[dict],
        video_id: str | None = None,
        transcript_text: str | None = None,
        manual_mapping: dict[str, str] | None = None,
    ) -> list[dict]:
        """
        Apply speaker attribution using priority hierarchy.

        Args:
            speaker_segments: List of segments with 'speaker' field
            video_id: YouTube video ID for video-specific mapping
            transcript_text: Full transcript for content analysis
            manual_mapping: Manual override mapping (highest priority)

        Returns:
            List of segments with attributed speaker names

        Priority Order:
        1. Manual Override (manual_mapping parameter)
        2. Video-Specific Mapping (based on video_id)
        3. Content-Based Detection (based on transcript_text)
        4. Default Fallback (keep original labels)
        """

        # Start with original segments
        result_segments = [seg.copy() for seg in speaker_segments]
        attribution_method = "none"
        applied_mapping = {}

        # PRIORITY 1: Manual Override (highest priority)
        if manual_mapping:
            result_segments = self._apply_mapping(result_segments, manual_mapping)
            attribution_method = "manual_override"
            applied_mapping = manual_mapping
            logger.info(f"Applied MANUAL OVERRIDE speaker mapping: {manual_mapping}")

        # PRIORITY 2: Content-Based Detection (video-specific mapping removed)
        elif transcript_text:
            mapping = self._detect_speakers_by_content(transcript_text)
            if mapping:
                result_segments = self._apply_mapping(result_segments, mapping)
                attribution_method = "content_based"
                applied_mapping = mapping
                logger.info(f"Applied CONTENT-BASED speaker mapping: {mapping}")

        # PRIORITY 3: Default Fallback (no changes)
        if not applied_mapping:
            attribution_method = "fallback"
            logger.info("No speaker attribution applied - using original labels")

        # Add metadata to segments
        for segment in result_segments:
            segment["attribution_method"] = attribution_method
            segment["applied_mapping"] = applied_mapping

        return result_segments

    def _apply_mapping(
        self, segments: list[dict], mapping: dict[str, str]
    ) -> list[dict]:
        """Apply speaker mapping to segments."""
        for segment in segments:
            original_speaker = segment.get("speaker", "")
            if original_speaker in mapping:
                segment["speaker"] = mapping[original_speaker]
                segment["original_speaker"] = original_speaker
        return segments

    def _detect_speakers_by_content(self, transcript_text: str) -> dict[str, str]:
        """Detect speakers based on content keywords."""
        speaker_scores = {}

        # Score each speaker based on keyword matches
        for speaker_type, keywords in self.content_patterns.items():
            score = 0
            for keyword in keywords:
                matches = len(
                    re.findall(re.escape(keyword), transcript_text, re.IGNORECASE)
                )
                score += matches
            speaker_scores[speaker_type] = score

        # Map highest scoring indicators to speaker labels
        mapping = {}

        # Peterson indicators
        if speaker_scores.get("peterson_indicators", 0) > 0:
            mapping["Speaker_1"] = "Jordan Peterson"

        # Harris indicators
        if speaker_scores.get("harris_indicators", 0) > 0:
            # If Peterson already assigned to Speaker_1, assign Harris to Speaker_2
            if "Speaker_1" in mapping:
                mapping["Speaker_2"] = "Sam Harris"
            else:
                mapping["Speaker_1"] = "Sam Harris"

        return mapping

    def format_transcript_with_speakers(
        self, segments: list[dict], format_type: str = "vtt"
    ) -> str:
        """Format transcript with speaker names."""
        if format_type == "vtt":
            return self._format_vtt(segments)
        elif format_type == "md":
            return self._format_markdown(segments)
        elif format_type == "txt":
            return self._format_text(segments)
        else:
            raise ValueError(f"Unsupported format: {format_type}")

    def _format_vtt(self, segments: list[dict]) -> str:
        """Format as VTT with speaker labels."""
        lines = ["WEBVTT", ""]

        for segment in segments:
            start = self._format_vtt_time(segment.get("start", 0))
            end = self._format_vtt_time(segment.get("end", 0))
            speaker = segment.get("speaker", "Unknown")
            text = segment.get("text", "")

            lines.append(f"{start} --> {end}")
            lines.append(f"<v {speaker}>{text}</v>")
            lines.append("")

        return "\n".join(lines)

    def _format_markdown(self, segments: list[dict]) -> str:
        """Format as Markdown with speaker labels."""
        lines = []
        for segment in segments:
            time = self._format_readable_time(segment.get("start", 0))
            speaker = segment.get("speaker", "Unknown")
            text = segment.get("text", "")
            lines.append(f"**{time}** **{speaker}**: {text}")
            lines.append("")
        return "\n".join(lines)

    def _format_text(self, segments: list[dict]) -> str:
        """Format as plain text with speaker labels."""
        lines = []
        for segment in segments:
            time = self._format_readable_time(segment.get("start", 0))
            speaker = segment.get("speaker", "Unknown")
            text = segment.get("text", "")
            lines.append(f"[{time}] {speaker}: {text}")
        return "\n".join(lines)

    def _format_vtt_time(self, seconds: float) -> str:
        """Format seconds to VTT timestamp."""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

    def _format_readable_time(self, seconds: float) -> str:
        """Format seconds to readable timestamp."""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)

        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        else:
            return f"{m:02d}:{s:02d}"

    def get_attribution_summary(self, segments: list[dict]) -> dict:
        """Get summary of applied speaker attribution."""
        if not segments:
            return {"method": "none", "mapping": {}, "speakers_found": []}

        sample_segment = segments[0]
        method = sample_segment.get("attribution_method", "unknown")
        mapping = sample_segment.get("applied_mapping", {})

        # Count unique speakers
        speakers = {seg.get("speaker", "Unknown") for seg in segments}

        return {
            "method": method,
            "mapping": mapping,
            "speakers_found": sorted(list(speakers)),
            "total_segments": len(segments),
        }


# Example usage
def test_speaker_attribution():
    """Test the speaker attribution system."""
    print("🎙️ Testing Speaker Attribution System")
    print("=" * 50)

    # Test segments
    test_segments = [
        {
            "start": 0,
            "end": 5,
            "speaker": "Speaker_1",
            "text": "Roughly speaking, we need to clean up our room",
        },
        {
            "start": 6,
            "end": 10,
            "speaker": "Speaker_2",
            "text": "The moral landscape requires consciousness",
        },
        {
            "start": 11,
            "end": 15,
            "speaker": "Speaker_1",
            "text": "Hierarchies are archetypal structures",
        },
    ]

    test_transcript = " ".join(seg["text"] for seg in test_segments)

    attributor = SpeakerAttributor()

    print("1️⃣ Testing Content-Based Detection:")
    result1 = attributor.attribute_speakers(
        test_segments, transcript_text=test_transcript
    )
    summary1 = attributor.get_attribution_summary(result1)
    print(f"   Method: {summary1['method']}")
    print(f"   Mapping: {summary1['mapping']}")
    print(f"   Speakers: {summary1['speakers_found']}")

    print("\n2️⃣ Testing Manual Override (highest priority):")
    manual_map = {"Speaker_1": "Custom Person A", "Speaker_2": "Custom Person B"}
    result2 = attributor.attribute_speakers(test_segments, manual_mapping=manual_map)
    summary2 = attributor.get_attribution_summary(result2)
    print(f"   Method: {summary2['method']}")
    print(f"   Mapping: {summary2['mapping']}")
    print(f"   Speakers: {summary2['speakers_found']}")

    print("\n3️⃣ Testing Video-Specific Mapping:")
    result3 = attributor.attribute_speakers(test_segments, video_id="COtibNznlP4")
    summary3 = attributor.get_attribution_summary(result3)
    print(f"   Method: {summary3['method']}")
    print(f"   Mapping: {summary3['mapping']}")
    print(f"   Speakers: {summary3['speakers_found']}")


if __name__ == "__main__":
    test_speaker_attribution()
