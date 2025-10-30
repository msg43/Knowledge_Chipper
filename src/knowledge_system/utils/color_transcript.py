"""
Color-coded transcript generation utilities.

Provides functions to generate HTML and markdown transcripts with color-coded
speakers for improved readability and visual distinction.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from ..logger import get_logger

logger = get_logger(__name__)


class SpeakerColorManager:
    """Manages consistent color assignments for speakers."""

    def __init__(self):
        """Initialize with predefined color palette."""
        self.colors = [
            "#FF6B6B",  # Red
            "#4ECDC4",  # Teal
            "#45B7D1",  # Blue
            "#96CEB4",  # Green
            "#FFEAA7",  # Yellow
            "#DDA0DD",  # Plum
            "#98D8C8",  # Mint
            "#F7DC6F",  # Light Yellow
            "#BB8FCE",  # Light Purple
            "#85C1E9",  # Light Blue
            "#F8C471",  # Orange
            "#AED6F1",  # Light Blue 2
            "#A9DFBF",  # Light Green
            "#F5B7B1",  # Light Red
            "#D7BDE2",  # Light Lavender
        ]

        self.speaker_colors: dict[str, str] = {}
        self.color_index = 0

    def get_color_for_speaker(self, speaker_id: str) -> str:
        """
        Get consistent color for a speaker.

        Args:
            speaker_id: Speaker identifier

        Returns:
            Hex color code for the speaker
        """
        if speaker_id not in self.speaker_colors:
            self.speaker_colors[speaker_id] = self.colors[
                self.color_index % len(self.colors)
            ]
            self.color_index += 1

        return self.speaker_colors[speaker_id]

    def get_all_speaker_colors(self) -> dict[str, str]:
        """Get all assigned speaker colors."""
        return self.speaker_colors.copy()


def format_timestamp_html(seconds: float) -> str:
    """Format seconds to MM:SS format for HTML display."""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"


def generate_color_coded_html_transcript(
    transcript_data: dict[str, Any],
    source_name: str,
    model: str = "unknown",
    device: str = "unknown",
    include_timestamps: bool = True,
    include_css: bool = True,
) -> str:
    """
    Generate color-coded HTML transcript with speaker identification.

    Args:
        transcript_data: Transcript data with segments and speaker information
        source_name: Name of the source file/recording
        model: Model used for transcription
        device: Device used for processing
        include_timestamps: Whether to include timestamps
        include_css: Whether to include embedded CSS styles

    Returns:
        HTML content as string
    """
    try:
        color_manager = SpeakerColorManager()

        # Start HTML document
        html_lines = []

        if include_css:
            html_lines.extend(
                [
                    "<!DOCTYPE html>",
                    "<html lang='en'>",
                    "<head>",
                    "    <meta charset='UTF-8'>",
                    "    <meta name='viewport' content='width=device-width, initial-scale=1.0'>",
                    f"    <title>Transcript: {source_name}</title>",
                    "    <style>",
                    "        body {",
                    "            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;",
                    "            line-height: 1.6;",
                    "            max-width: 1200px;",
                    "            margin: 0 auto;",
                    "            padding: 20px;",
                    "            background-color: #f8f9fa;",
                    "        }",
                    "        .header {",
                    "            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);",
                    "            color: white;",
                    "            padding: 20px;",
                    "            border-radius: 10px;",
                    "            margin-bottom: 30px;",
                    "            box-shadow: 0 4px 6px rgba(0,0,0,0.1);",
                    "        }",
                    "        .header h1 {",
                    "            margin: 0 0 10px 0;",
                    "            font-size: 2em;",
                    "        }",
                    "        .metadata {",
                    "            font-size: 0.9em;",
                    "            opacity: 0.9;",
                    "        }",
                    "        .speaker-legend {",
                    "            background: white;",
                    "            padding: 15px;",
                    "            border-radius: 8px;",
                    "            margin-bottom: 20px;",
                    "            box-shadow: 0 2px 4px rgba(0,0,0,0.1);",
                    "        }",
                    "        .speaker-legend h3 {",
                    "            margin-top: 0;",
                    "            color: #333;",
                    "        }",
                    "        .speaker-chip {",
                    "            display: inline-block;",
                    "            padding: 4px 12px;",
                    "            margin: 4px;",
                    "            border-radius: 20px;",
                    "            color: white;",
                    "            font-weight: bold;",
                    "            font-size: 0.85em;",
                    "        }",
                    "        .transcript-container {",
                    "            background: white;",
                    "            padding: 20px;",
                    "            border-radius: 8px;",
                    "            box-shadow: 0 2px 4px rgba(0,0,0,0.1);",
                    "        }",
                    "        .segment {",
                    "            margin-bottom: 15px;",
                    "            padding: 12px;",
                    "            border-radius: 8px;",
                    "            border-left: 4px solid;",
                    "            background-color: rgba(255,255,255,0.8);",
                    "        }",
                    "        .speaker-name {",
                    "            font-weight: bold;",
                    "            font-size: 1.1em;",
                    "            margin-bottom: 5px;",
                    "        }",
                    "        .timestamp {",
                    "            font-size: 0.85em;",
                    "            color: #666;",
                    "            font-family: Consolas, Monaco, 'DejaVu Sans Mono', 'Liberation Mono', 'Courier New', monospace;",
                    "            margin-bottom: 5px;",
                    "        }",
                    "        .text {",
                    "            color: #333;",
                    "            line-height: 1.5;",
                    "        }",
                    "        .stats {",
                    "            background: #e9ecef;",
                    "            padding: 15px;",
                    "            border-radius: 8px;",
                    "            margin-top: 20px;",
                    "            font-size: 0.9em;",
                    "            color: #495057;",
                    "        }",
                    "        @media print {",
                    "            body { background-color: white; }",
                    "            .header { background: #333 !important; }",
                    "            .segment { break-inside: avoid; }",
                    "        }",
                    "    </style>",
                    "</head>",
                    "<body>",
                ]
            )

        # Header section
        html_lines.extend(
            [
                "    <div class='header'>",
                f"        <h1>🎙️ {source_name}</h1>",
                "        <div class='metadata'>",
                f"            <strong>Model:</strong> {model} | ",
                f"            <strong>Device:</strong> {device} | ",
                f"            <strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "        </div>",
                "    </div>",
            ]
        )

        # Process segments to identify speakers
        segments = transcript_data.get("segments", [])
        if not segments:
            html_lines.extend(
                [
                    "    <div class='transcript-container'>",
                    "        <p>No transcript segments available.</p>",
                    "    </div>",
                    "</body>",
                    "</html>",
                ]
            )
            return "\n".join(html_lines)

        # Collect unique speakers
        speakers = set()
        for segment in segments:
            speaker = segment.get("speaker")
            if speaker:
                speakers.add(speaker)

        # Generate speaker legend if there are multiple speakers
        if len(speakers) > 1:
            html_lines.extend(
                ["    <div class='speaker-legend'>", "        <h3>👥 Speakers</h3>"]
            )

            for speaker in sorted(speakers):
                color = color_manager.get_color_for_speaker(speaker)
                html_lines.append(
                    f"        <span class='speaker-chip' style='background-color: {color};'>{speaker}</span>"
                )

            html_lines.append("    </div>")

        # Transcript content
        html_lines.extend(
            [
                "    <div class='transcript-container'>",
                "        <h2>📝 Full Transcript</h2>",
            ]
        )

        # Process each segment
        for segment in segments:
            text = segment.get("text", "").strip()
            speaker = segment.get("speaker")
            start_time = segment.get("start", 0)
            end_time = segment.get("end", 0)

            if not text:
                continue

            # Get speaker color
            if speaker:
                color = color_manager.get_color_for_speaker(speaker)
                border_color = color
                bg_color = f"{color}15"  # Add transparency
            else:
                border_color = "#ddd"
                bg_color = "#f8f9fa"

            # Create segment HTML
            html_lines.append(
                f"        <div class='segment' style='border-left-color: {border_color}; background-color: {bg_color};'>"
            )

            if speaker:
                html_lines.append(
                    f"            <div class='speaker-name' style='color: {border_color};'>{speaker}</div>"
                )

            if include_timestamps:
                start_formatted = format_timestamp_html(start_time)
                end_formatted = format_timestamp_html(end_time)
                html_lines.append(
                    f"            <div class='timestamp'>{start_formatted} - {end_formatted}</div>"
                )

            html_lines.append(f"            <div class='text'>{text}</div>")
            html_lines.append("        </div>")

        # Statistics
        total_segments = len(segments)
        total_speakers = len(speakers)

        html_lines.extend(
            [
                "    </div>",
                "    <div class='stats'>",
                f"        📊 <strong>Statistics:</strong> {total_segments} segments, {total_speakers} speakers",
                "    </div>",
            ]
        )

        if include_css:
            html_lines.extend(["</body>", "</html>"])

        return "\n".join(html_lines)

    except Exception as e:
        logger.error(f"Error generating color-coded HTML transcript: {e}")
        return (
            f"<html><body><h1>Error generating transcript</h1><p>{e}</p></body></html>"
        )


def generate_color_coded_markdown_transcript(
    transcript_data: dict[str, Any],
    source_name: str,
    model: str = "unknown",
    device: str = "unknown",
    include_timestamps: bool = True,
    use_html_colors: bool = True,
) -> str:
    """
    Generate color-coded markdown transcript with speaker identification.

    Args:
        transcript_data: Transcript data with segments and speaker information
        source_name: Name of the source file/recording
        model: Model used for transcription
        device: Device used for processing
        include_timestamps: Whether to include timestamps
        use_html_colors: Whether to use HTML color tags in markdown

    Returns:
        Markdown content as string
    """
    try:
        color_manager = SpeakerColorManager()

        # Start with YAML frontmatter
        safe_source_name = source_name.replace('"', '\\"')
        lines = [
            "---",
            f'title: "Transcript: {safe_source_name}"',
            f'source: "{safe_source_name}"',
            f'model: "{model}"',
            f'device: "{device}"',
            f'generated: "{datetime.now().isoformat()}"',
            "transcript_type: color_coded",
            "---",
            "",
            f"# 🎙️ {source_name}",
            "",
            "## 📋 Metadata",
            "",
            f"- **Model:** {model}",
            f"- **Device:** {device}",
            f"- **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]

        # Process segments
        segments = transcript_data.get("segments", [])
        if not segments:
            lines.extend(["## 📝 Transcript", "", "*No transcript segments available.*"])
            return "\n".join(lines)

        # Collect speakers for legend
        speakers = set()
        for segment in segments:
            speaker = segment.get("speaker")
            if speaker:
                speakers.add(speaker)

        # Add speaker legend if multiple speakers
        if len(speakers) > 1:
            lines.extend(["## 👥 Speakers", ""])

            for speaker in sorted(speakers):
                color = color_manager.get_color_for_speaker(speaker)
                if use_html_colors:
                    lines.append(
                        f"- <span style='color: {color}; font-weight: bold;'>{speaker}</span>"
                    )
                else:
                    lines.append(f"- **{speaker}**")

            lines.append("")

        # Add transcript content
        lines.extend(["## 📝 Full Transcript", ""])

        # Process each segment
        for segment in segments:
            text = segment.get("text", "").strip()
            speaker = segment.get("speaker")
            start_time = segment.get("start", 0)
            end_time = segment.get("end", 0)

            if not text:
                continue

            # Format segment
            segment_lines = []

            if speaker:
                color = color_manager.get_color_for_speaker(speaker)
                if use_html_colors:
                    segment_lines.append(
                        f"<span style='color: {color}; font-weight: bold; font-size: 1.1em;'>{speaker}</span>"
                    )
                else:
                    segment_lines.append(f"**{speaker}**")

            if include_timestamps:
                start_formatted = format_timestamp_html(start_time)
                end_formatted = format_timestamp_html(end_time)
                timestamp_text = f"*{start_formatted} - {end_formatted}*"

                if use_html_colors and speaker:
                    color = color_manager.get_color_for_speaker(speaker)
                    segment_lines.append(
                        f"<span style='color: {color}; opacity: 0.7;'>{timestamp_text}</span>"
                    )
                else:
                    segment_lines.append(timestamp_text)

            # Add text with optional color coding
            if use_html_colors and speaker:
                color = color_manager.get_color_for_speaker(speaker)
                segment_lines.append(f"<span style='color: {color};'>{text}</span>")
            else:
                segment_lines.append(text)

            # Join segment lines and add to main content
            lines.append(" ".join(segment_lines))
            lines.append("")  # Empty line between segments

        # Add statistics
        total_segments = len(segments)
        total_speakers = len(speakers)

        lines.extend(
            [
                "---",
                "",
                "## 📊 Statistics",
                "",
                f"- **Total segments:** {total_segments}",
                f"- **Speakers identified:** {total_speakers}",
                f"- **Color coding:** {'Enabled' if use_html_colors else 'Disabled'}",
            ]
        )

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Error generating color-coded markdown transcript: {e}")
        return f"# Error\n\nFailed to generate transcript: {e}"


def update_transcript_with_speaker_colors(
    transcript_data: dict[str, Any],
    speaker_assignments: dict[str, str],
    output_format: str = "markdown",
    **kwargs,
) -> str:
    """
    Update transcript with color-coded speaker assignments.

    Args:
        transcript_data: Original transcript data
        speaker_assignments: Dictionary mapping speaker IDs to names
        output_format: Output format ("markdown", "html")
        **kwargs: Additional formatting options

    Returns:
        Color-coded transcript content
    """
    try:
        # Apply speaker assignments to transcript data
        updated_data = transcript_data.copy()

        if "segments" in updated_data:
            for segment in updated_data["segments"]:
                original_speaker = segment.get("speaker")
                if original_speaker and original_speaker in speaker_assignments:
                    segment["speaker"] = speaker_assignments[original_speaker]

        # Generate color-coded transcript
        source_name = kwargs.get("source_name", "Unknown")
        model = kwargs.get("model", "unknown")
        device = kwargs.get("device", "unknown")
        include_timestamps = kwargs.get("include_timestamps", True)

        if output_format.lower() == "html":
            return generate_color_coded_html_transcript(
                updated_data, source_name, model, device, include_timestamps
            )
        else:
            use_html_colors = kwargs.get("use_html_colors", True)
            return generate_color_coded_markdown_transcript(
                updated_data,
                source_name,
                model,
                device,
                include_timestamps,
                use_html_colors,
            )

    except Exception as e:
        logger.error(f"Error updating transcript with speaker colors: {e}")
        return f"Error generating color-coded transcript: {e}"


def save_color_coded_transcript(
    transcript_data: dict[str, Any],
    output_path: Path,
    speaker_assignments: dict[str, str] | None = None,
    **kwargs,
) -> bool:
    """
    Save color-coded transcript to file.

    Args:
        transcript_data: Transcript data with segments
        output_path: Path to save the transcript
        speaker_assignments: Optional speaker name assignments
        **kwargs: Additional formatting options

    Returns:
        True if successful, False otherwise
    """
    try:
        # Determine format from file extension
        output_format = "html" if output_path.suffix.lower() == ".html" else "markdown"

        # Apply speaker assignments if provided
        if speaker_assignments:
            content = update_transcript_with_speaker_colors(
                transcript_data, speaker_assignments, output_format, **kwargs
            )
        else:
            # Use original speaker IDs
            source_name = kwargs.get("source_name", output_path.stem)
            model = kwargs.get("model", "unknown")
            device = kwargs.get("device", "unknown")
            include_timestamps = kwargs.get("include_timestamps", True)

            if output_format == "html":
                content = generate_color_coded_html_transcript(
                    transcript_data, source_name, model, device, include_timestamps
                )
            else:
                use_html_colors = kwargs.get("use_html_colors", True)
                content = generate_color_coded_markdown_transcript(
                    transcript_data,
                    source_name,
                    model,
                    device,
                    include_timestamps,
                    use_html_colors,
                )

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write content to file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"Color-coded transcript saved to: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Error saving color-coded transcript: {e}")
        return False


def extract_speaker_statistics(
    transcript_data: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """
    Extract speaker statistics from transcript data.

    Args:
        transcript_data: Transcript data with segments

    Returns:
        Dictionary with speaker statistics
    """
    segments = transcript_data.get("segments", [])
    speaker_stats = {}
    total_duration = 0.0

    # Calculate per-speaker statistics
    for segment in segments:
        speaker = segment.get("speaker", "Unknown")
        # Ensure start and end are floats (they might be strings from JSON)
        try:
            start = float(segment.get("start", 0.0))
            end = float(segment.get("end", 0.0))
        except (ValueError, TypeError):
            start = 0.0
            end = 0.0
        duration = end - start

        if speaker not in speaker_stats:
            speaker_stats[speaker] = {
                "total_duration": 0.0,
                "segment_count": 0,
                "percentage": 0.0,
            }

        speaker_stats[speaker]["total_duration"] += duration
        speaker_stats[speaker]["segment_count"] += 1
        total_duration += duration

    # Calculate percentages
    for speaker, stats in speaker_stats.items():
        if total_duration > 0:
            stats["percentage"] = (stats["total_duration"] / total_duration) * 100.0
        else:
            stats["percentage"] = 0.0

    return speaker_stats


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string
    """
    seconds = int(round(seconds))

    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds}s"
    else:
        hours = seconds // 3600
        remaining_minutes = (seconds % 3600) // 60
        remaining_seconds = seconds % 60
        return f"{hours}h {remaining_minutes}m {remaining_seconds}s"
