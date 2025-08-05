"""
Transcribe command for the Knowledge System CLI.

Handles transcription of audio/video files and YouTube URLs using OpenAI Whisper.
"""

import csv
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import click
from rich.table import Table

from ..logger import log_system_event
from ..utils.text_utils import strip_bracketed_content
from ..utils.youtube_utils import extract_video_id
from .common import CLIContext, console, logger, pass_context


def format_timestamp(seconds: float) -> str:
    """Format seconds to MM:SS format."""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"


def format_timestamp_srt(seconds: float) -> str:
    """Format seconds to SRT timestamp format (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millisecs = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"


def format_timestamp_vtt(seconds: float) -> str:
    """Format seconds to VTT timestamp format (HH:MM:SS.mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millisecs = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millisecs:03d}"


def extract_audio_video_metadata(file_path: Path) -> dict[str, Any]:
    """Extract metadata from audio/video files using FFmpeg."""
    try:
        from knowledge_system.utils.audio_utils import get_audio_metadata

        metadata = get_audio_metadata(file_path)

        # Add additional file info
        metadata.update(
            {
                "extracted_at": datetime.now().isoformat(),
            }
        )

        return metadata

    except Exception as e:
        logger.warning(f"Error extracting metadata from {file_path}: {e}")
        return {
            "filename": file_path.name,
            "file_path": str(file_path),
            "file_size": file_path.stat().st_size if file_path.exists() else 0,
            "file_extension": file_path.suffix.lower(),
            "extracted_at": datetime.now().isoformat(),
        }


def format_audio_video_metadata_markdown(metadata: dict[str, Any]) -> str:
    """Format audio/video metadata as markdown section."""
    lines = ["## Metadata"]
    lines.append("")

    # Basic file info
    lines.append(f"- **Filename**: {metadata.get('filename', 'Unknown')}")
    lines.append(f"- **File Path**: {metadata.get('file_path', 'Unknown')}")

    file_size = metadata.get("file_size", 0)
    if file_size > 0:
        if file_size > 1024 * 1024 * 1024:  # GB
            size_str = f"{file_size / (1024**3):.2f} GB"
        elif file_size > 1024 * 1024:  # MB
            size_str = f"{file_size / (1024**2):.2f} MB"
        elif file_size > 1024:  # KB
            size_str = f"{file_size / 1024:.2f} KB"
        else:
            size_str = f"{file_size} bytes"
        lines.append(f"- **File Size**: {size_str}")

    lines.append(
        f"- **File Type**: {metadata.get('file_extension', 'Unknown').upper()}"
    )

    # Duration
    duration = metadata.get("duration")
    if duration:
        try:
            duration_sec = float(duration)
            minutes = int(duration_sec // 60)
            seconds = int(duration_sec % 60)
            lines.append(f"- **Duration**: {minutes}:{seconds:02d}")
        except (ValueError, TypeError):
            lines.append(f"- **Duration**: {duration}")

    # Audio information
    audio_codec = metadata.get("audio_codec")
    if audio_codec:
        lines.append(f"- **Audio Codec**: {audio_codec}")

    sample_rate = metadata.get("sample_rate")
    if sample_rate:
        lines.append(f"- **Sample Rate**: {sample_rate} Hz")

    channels = metadata.get("channels")
    if channels:
        lines.append(f"- **Channels**: {channels}")

    return "\n".join(lines)


def _add_analysis_sections(text: str, vault_path: Path | None = None) -> str:
    """Add analysis sections to transcript (currently disabled)."""
    # Analysis sections disabled per user request
    return ""


def _generate_obsidian_link(
    source_file_stem: str, link_type: str, output_dir: Path | None = None
) -> str:
    """
    Generate Obsidian link to the corresponding file.

    Args:
        source_file_stem: The base filename without extension (e.g., 'video_123')
        link_type: Either 'summary' or 'transcript' to determine target file
        output_dir: Directory where files are stored (for validation)

    Returns:
        Formatted Obsidian link or empty string if target doesn't exist
    """
    if link_type == "summary":
        target_filename = f"{source_file_stem}_summary"
        link_text = "View Summary"
    elif link_type == "transcript":
        target_filename = f"{source_file_stem}_transcript"
        link_text = "View Transcript"
    else:
        return ""

    # Check if target file exists (optional validation)
    if output_dir:
        # Check for common extensions
        target_exists = False
        for ext in [".md", ".txt"]:
            target_path = output_dir / f"{target_filename}{ext}"
            if target_path.exists():
                target_exists = True
                break

        # If we're creating the transcript, the summary might not exist yet
        # If we're creating the summary, the transcript should exist
        # For now, we'll create the link regardless to support both scenarios

    return f"[[{target_filename}|{link_text}]]"


def format_transcript_content(
    transcript_data,
    source_name: str,
    model: str,
    device: str,
    format: str,
    file_path: Path | None = None,
    video_id: str | None = None,
    vault_path: Path | None = None,
    timestamps: bool = True,
    output_dir: Path | None = None,
) -> str:
    """Format transcript content based on output format."""
    if format == "md":
        # Add YAML frontmatter with title instead of level 1 header
        # Escape quotes in source name for YAML safety
        safe_source_name = source_name.replace('"', '\\"')
        content = f'---\ntitle: "Transcript of {safe_source_name}"\n---\n\n'

        # Add thumbnail reference for YouTube videos
        if video_id:
            content += f"![Video Thumbnail](Thumbnails/{video_id}_thumbnail.jpg)\n\n"

        # Add metadata section for file inputs
        if file_path and file_path.exists():
            metadata = extract_audio_video_metadata(file_path)
            content += format_audio_video_metadata_markdown(metadata)
            # Add transcription metadata to existing metadata section
            content += f"\n- **Model:** {model}\n"
            content += f"- **Device:** {device}\n"
            content += f"- **Generated:** {datetime.now().isoformat()}\n"
            content += "\n---\n\n"
        else:
            # Create basic metadata section for non-file inputs (e.g., YouTube)
            content += "## Metadata\n\n"
            content += f"- **Model:** {model}\n"
            content += f"- **Device:** {device}\n"
            content += f"- **Generated:** {datetime.now().isoformat()}\n\n"
            content += "---\n\n"

        # Extract text for analysis
        if isinstance(transcript_data, dict) and "segments" in transcript_data:
            full_text = " ".join(
                segment.get("text", "") for segment in transcript_data["segments"]
            )
        elif isinstance(transcript_data, str):
            full_text = transcript_data
        else:
            full_text = str(transcript_data)

        # Add analysis sections for audio transcripts
        if full_text.strip():
            content += _add_analysis_sections(full_text, vault_path)

        # Add link to corresponding summary if we can determine the base filename
        base_filename = None
        if video_id:
            base_filename = video_id
        elif file_path:
            base_filename = file_path.stem
            # If filename ends with _transcript, remove it to get base name
            if base_filename.endswith("_transcript"):
                base_filename = base_filename[:-11]  # Remove "_transcript"

        if base_filename:
            summary_link = _generate_obsidian_link(base_filename, "summary", output_dir)
            if summary_link:
                content += f"## Related Documents\n\n{summary_link}\n\n"

        # Add Full Transcript section
        content += "## Full Transcript\n\n"

        # Format Whisper output with proper timestamps
        if isinstance(transcript_data, dict) and "segments" in transcript_data:
            # Whisper format with segments
            for segment in transcript_data["segments"]:
                text = segment.get("text", "").strip()
                speaker = segment.get("speaker")
                if text:
                    # Remove bracketed content like [music], [applause], etc.
                    text = strip_bracketed_content(text)
                    # Only add the segment if there's still text after bracket removal
                    if text.strip():
                        if speaker:
                            content += f"**Speaker {speaker}** "
                        if timestamps:
                            start_time = format_timestamp(segment.get("start", 0))
                            end_time = format_timestamp(segment.get("end", 0))
                            content += f"**{start_time} - {end_time}** {text}\n\n"
                        else:
                            content += f"{text}\n\n"
        elif isinstance(transcript_data, str):
            # Plain text format - also remove bracketed content
            cleaned_text = strip_bracketed_content(transcript_data)
            content += cleaned_text
        else:
            # Fallback - also remove bracketed content
            cleaned_text = strip_bracketed_content(str(transcript_data))
            content += cleaned_text
    elif format == "txt":
        content = f"Transcript of {source_name}\n"
        content += f"Model: {model}\n"
        content += f"Device: {device}\n"
        content += f"Generated: {datetime.now().isoformat()}\n\n"
        # Format content similar to md format but without markdown
        if isinstance(transcript_data, dict) and "segments" in transcript_data:
            for segment in transcript_data["segments"]:
                text = segment.get("text", "").strip()
                if text:
                    # Remove bracketed content like [music], [applause], etc.
                    text = strip_bracketed_content(text)
                    # Only add the segment if there's still text after bracket removal
                    if text.strip():
                        if timestamps:
                            start_time = format_timestamp(segment.get("start", 0))
                            end_time = format_timestamp(segment.get("end", 0))
                            content += f"{start_time} - {end_time} {text}\n\n"
                        else:
                            content += f"{text}\n\n"
        elif isinstance(transcript_data, str):
            cleaned_text = strip_bracketed_content(transcript_data)
            content += cleaned_text
        else:
            cleaned_text = strip_bracketed_content(str(transcript_data))
            content += cleaned_text
    elif format == "srt":
        # SRT format with proper timestamps
        if isinstance(transcript_data, dict) and "segments" in transcript_data:
            content = ""
            for i, segment in enumerate(transcript_data["segments"], 1):
                start_time = format_timestamp_srt(segment.get("start", 0))
                end_time = format_timestamp_srt(segment.get("end", 0))
                text = segment.get("text", "").strip()
                if text:
                    # Remove bracketed content like [music], [applause], etc.
                    text = strip_bracketed_content(text)
                    # Only add the segment if there's still text after bracket removal
                    if text.strip():
                        content += f"{i}\n{start_time} --> {end_time}\n{text}\n\n"
        else:
            cleaned_text = strip_bracketed_content(str(transcript_data))
            content = f"1\n00:00:00,000 --> 00:00:00,000\n{cleaned_text}\n"
    elif format == "vtt":
        # VTT format with proper timestamps
        if isinstance(transcript_data, dict) and "segments" in transcript_data:
            content = "WEBVTT\n\n"
            for segment in transcript_data["segments"]:
                start_time = format_timestamp_vtt(segment.get("start", 0))
                end_time = format_timestamp_vtt(segment.get("end", 0))
                text = segment.get("text", "").strip()
                content += f"{start_time} --> {end_time}\n{text}\n\n"
        else:
            content = f"WEBVTT\n\n00:00:00.000 --> 00:00:00.000\n{transcript_data}\n"
    else:
        content = transcript_data

    return content


def track_failed_transcript(url: str, reason: str, output_dir: Path) -> None:
    """Track URLs that failed to transcribe or had very short transcripts."""
    failed_file = output_dir / "failed_transcripts.csv"
    file_exists = failed_file.exists()

    with open(failed_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "url", "reason"])
        writer.writerow([datetime.now().isoformat(), url, reason])


def check_transcript_exists(video_id: str, output_dir: Path, format: str) -> bool:
    """Check if a transcript already exists for the given video ID."""
    output_file = output_dir / f"{video_id}_transcript.{format}"
    return output_file.exists()


def is_transcript_too_short(transcript_text: Any, min_words: int = 50) -> bool:
    """Check if transcript is too short (less than minimum words)."""
    if isinstance(transcript_text, dict):
        if "segments" in transcript_text:
            # Extract text from segments
            full_text = " ".join(
                segment.get("text", "") for segment in transcript_text["segments"]
            )
        else:
            full_text = str(transcript_text)
    else:
        full_text = str(transcript_text)

    word_count = len(full_text.split())
    return word_count < min_words


def extract_video_id_from_url(url: str) -> str | None:
    """Extract YouTube video ID from URL."""
    video_id_match = re.search(
        r"(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]+)", url
    )
    return video_id_match.group(1) if video_id_match else None


@click.command()
@click.option("--input", "-i", type=str, help="Input file path or YouTube URL")
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output directory (default: configured output path)",
)
@click.option(
    "--model", "-m", default="base", help="Whisper model to use (default: base)"
)
@click.option(
    "--language", "-l", help="Force specific language (auto-detect if not specified)"
)
@click.option(
    "--device",
    "-d",
    type=click.Choice(["auto", "cpu", "cuda", "mps"]),
    default="auto",
    help="Device to use for processing",
)
@click.option(
    "--batch-size", "-b", type=int, default=16, help="Batch size for processing"
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["txt", "md", "srt", "vtt"]),
    default="md",
    help="Output format",
)
@click.option(
    "--timestamps/--no-timestamps", default=True, help="Include timestamps in output"
)
@click.option(
    "--speaker-labels/--no-speaker-labels",
    default=False,
    help="Enable speaker diarization",
)
@click.option(
    "--dry-run", is_flag=True, help="Show what would be done without making changes"
)
@click.option(
    "--batch-urls",
    type=click.Path(exists=True, path_type=Path),
    help="CSV file containing YouTube URLs (one per line or comma-separated)",
)
@click.option(
    "--download-thumbnails/--no-download-thumbnails",
    default=True,
    help="Download video thumbnails (YouTube videos only)",
)
@click.option("--overwrite", is_flag=True, help="Overwrite existing transcripts")
@click.option(
    "--use-whisper-cpp", is_flag=True, help="Use whisper.cpp with Core ML acceleration"
)
@click.option(
    "--vault-path",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Path to Obsidian vault for intelligent linking",
)
@pass_context
def transcribe(
    ctx: CLIContext,
    input: str | None,
    output: Path | None,
    model: str,
    language: str | None,
    device: str,
    batch_size: int,
    format: str,
    timestamps: bool,
    speaker_labels: bool,
    dry_run: bool,
    batch_urls: Path | None,
    download_thumbnails: bool,
    overwrite: bool,
    use_whisper_cpp: bool,
    vault_path: Path | None,
) -> None:
    """
    Transcribe audio/video files or YouTube URLs using OpenAI Whisper.

    Supports local audio/video files and YouTube URLs. Uses OpenAI's Whisper model
    for high-quality transcription with automatic language detection.

    Examples:
        knowledge-system transcribe audio.mp3
        knowledge-system transcribe "https://youtube.com/watch?v=VIDEO_ID"
        knowledge-system transcribe video.mp4 --model large --device mps
        knowledge-system transcribe audio.wav --format srt --no-timestamps
        knowledge-system transcribe --batch-urls urls.csv --output ./transcripts/
    """
    settings = ctx.get_settings()

    # Handle batch URL processing
    if batch_urls:
        if not ctx.quiet:
            console.print(
                f"[bold blue]{'[DRY RUN] ' if dry_run else ''}Processing YouTube URLs from:[/bold blue] {batch_urls}"
            )

        try:
            # Read URLs from CSV file - handle both plain CSV and RTF files
            urls = []
            with open(batch_urls, encoding="utf-8") as f:
                content = f.read()

            if content.startswith("{\\rtf"):
                # RTF file detected - extract URLs from RTF content
                if not ctx.quiet:
                    console.print("[dim]RTF file detected, extracting URLs...[/dim]")

                # Extract URLs from RTF content using regex
                url_pattern = r"https?://[^\s\\,}]+"
                found_urls = re.findall(url_pattern, content)

                for url in found_urls:
                    # Clean up any RTF artifacts
                    url = url.rstrip("\\,}")
                    if "youtube.com" in url or "youtu.be" in url:
                        urls.append(url)

                if urls and not ctx.quiet:
                    console.print(
                        f"[dim]Extracted {len(urls)} YouTube URLs from RTF file[/dim]"
                    )
            else:
                # Plain CSV file - read line by line
                for line in content.split("\n"):
                    line = line.strip()
                    if line and not line.startswith(
                        "#"
                    ):  # Skip empty lines and comments
                        # Handle comma-separated URLs on the same line
                        for url in line.split(","):
                            url = url.strip()
                            if url and ("youtube.com" in url or "youtu.be" in url):
                                urls.append(url)

            if not urls:
                console.print(
                    "[red]✗ No valid YouTube URLs found in the CSV file[/red]"
                )
                sys.exit(1)

            if not ctx.quiet:
                console.print(f"[dim]Found {len(urls)} YouTube URLs to process[/dim]")

            if dry_run:
                console.print(
                    f"[yellow][DRY RUN] Would transcribe {len(urls)} YouTube URLs with the above settings.[/yellow]"
                )
                for url in urls:
                    console.print(f"[dim]  - {url}[/dim]")
                return

            # Process each URL
            from ..services.transcription_service import TranscriptionService

            service = TranscriptionService(
                whisper_model=model,
                download_thumbnails=download_thumbnails,
                use_whisper_cpp=use_whisper_cpp,
            )

            failed_urls = []
            skipped_urls = []

            # Ensure output directory is set
            if output is None:
                console.print(
                    "[red]✗ Error: Output directory is required. Use --output to specify where transcripts should be saved.[/red]"
                )
                sys.exit(1)

            for i, url in enumerate(urls, 1):
                if not ctx.quiet:
                    console.print(
                        f"[bold blue]Processing {i}/{len(urls)}:[/bold blue] {url}"
                    )

                # Extract video ID
                video_id = extract_video_id_from_url(url)
                if not video_id:
                    video_id = f"video_{i}"

                # Check if transcript already exists
                if not overwrite and check_transcript_exists(video_id, output, format):
                    if not ctx.quiet:
                        console.print(
                            f"[yellow]⚠ Transcript already exists for {video_id}, skipping (use --overwrite to replace)[/yellow]"
                        )
                    skipped_urls.append(url)
                    continue

                result = service.transcribe_youtube_url(
                    url,
                    download_thumbnails=download_thumbnails,
                    output_dir=output,
                    include_timestamps=timestamps,
                )

                if result["success"]:
                    # Check if transcript is too short
                    if is_transcript_too_short(result["transcript"]):
                        if not ctx.quiet:
                            console.print(
                                f"[yellow]⚠ Transcript too short (< 50 words) for {url}[/yellow]"
                            )
                        track_failed_transcript(
                            url, "Transcript too short (< 50 words)", output
                        )
                        failed_urls.append((url, "Too short"))
                        continue

                    # Save transcript
                    output_file = output / f"{video_id}_transcript.{format}"
                    output_file.parent.mkdir(parents=True, exist_ok=True)

                    # Format and save transcript
                    content = format_transcript_content(
                        result["transcript"],
                        f"YouTube Video {video_id}",
                        model,
                        device,
                        format,
                        video_id=video_id,
                        timestamps=timestamps,
                        output_dir=output,
                    )

                    with open(output_file, "w", encoding="utf-8") as f:
                        f.write(content)

                    if not ctx.quiet:
                        console.print(
                            f"[green]✓ Transcript saved to: {output_file}[/green]"
                        )
                        if result.get("thumbnails"):
                            for thumbnail in result["thumbnails"]:
                                console.print(
                                    f"[green]✓ Thumbnail saved to: {thumbnail}[/green]"
                                )
                else:
                    console.print(
                        f"[red]✗ Failed to transcribe {url}: {result['error']}[/red]"
                    )
                    track_failed_transcript(url, f"Error: {result['error']}", output)
                    failed_urls.append((url, result["error"]))

            # Summary
            if not ctx.quiet:
                console.print("\n[bold]Summary:[/bold]")
                console.print(
                    f"[green]✓ Successfully processed: {len(urls) - len(failed_urls) - len(skipped_urls)} URLs[/green]"
                )
                if skipped_urls:
                    console.print(
                        f"[yellow]⚠ Skipped (already exists): {len(skipped_urls)} URLs[/yellow]"
                    )
                if failed_urls:
                    console.print(f"[red]✗ Failed: {len(failed_urls)} URLs[/red]")
                    console.print(
                        f"[dim]Failed URLs saved to: {output / 'failed_transcripts.csv'}[/dim]"
                    )

            return

        except Exception as e:
            console.print(f"[red]✗ Error processing batch URLs:[/red] {e}")
            sys.exit(1)

    # Handle single input (file or URL)
    if not input:
        console.print("[red]✗ Error: Must provide either --input or --batch-urls[/red]")
        sys.exit(1)

    if not ctx.quiet:
        console.print(
            f"[bold blue]{'[DRY RUN] ' if dry_run else ''}Transcribing:[/bold blue] {input}"
        )
        console.print(f"[dim]Model: {model}, Device: {device}, Format: {format}[/dim]")

    if dry_run:
        console.print(
            "[yellow][DRY RUN] Would transcribe input with the above settings.[/yellow]"
        )
        return

    # Determine output path
    if output is None:
        console.print(
            "[red]✗ Error: Output directory is required. Use --output to specify where transcripts should be saved.[/red]"
        )
        sys.exit(1)

    # Log transcription start
    log_system_event(
        event="transcription_started",
        component="cli.transcribe",
        status="info",
        input_path=input,
        output_path=str(output),
        model=model,
        device=device,
    )

    try:
        # Check if input is a YouTube URL
        if "youtube.com" in input or "youtu.be" in input:
            # Extract video ID
            video_id = extract_video_id_from_url(input)
            if not video_id:
                video_id = "youtube_video"

            # Check if transcript already exists
            if not overwrite and check_transcript_exists(video_id, output, format):
                if not ctx.quiet:
                    console.print(
                        f"[yellow]⚠ Transcript already exists for {video_id}, skipping (use --overwrite to replace)[/yellow]"
                    )
                sys.exit(0)

            # Use transcription service for YouTube URLs
            from ..services.transcription_service import TranscriptionService

            service = TranscriptionService(
                whisper_model=model,
                download_thumbnails=download_thumbnails,
                use_whisper_cpp=use_whisper_cpp,
            )
            result = service.transcribe_youtube_url(
                input,
                download_thumbnails=download_thumbnails,
                output_dir=output,
                include_timestamps=timestamps,
            )

            if result["success"]:
                # Check if transcript is too short
                if is_transcript_too_short(result["transcript"]):
                    if not ctx.quiet:
                        console.print(
                            f"[yellow]⚠ Transcript too short (< 50 words) for {input}[/yellow]"
                        )
                    track_failed_transcript(
                        input, "Transcript too short (< 50 words)", output
                    )
                    sys.exit(1)

                if not ctx.quiet:
                    console.print(
                        "[green]✓ Transcription completed successfully[/green]"
                    )
                    console.print(
                        f"[dim]Transcript length: {len(result['transcript'])} characters[/dim]"
                    )
                    if result.get("thumbnails"):
                        console.print(
                            f"[dim]Thumbnails downloaded: {len(result['thumbnails'])}[/dim]"
                        )

                # Check if transcript processor already created output files
                existing_output_files = result.get("output_files", [])

                if existing_output_files:
                    # Use the files created by the transcript processor (with proper titles)
                    if not ctx.quiet:
                        for output_file in existing_output_files:
                            console.print(
                                f"[green]✓ Transcript saved to: {output_file}[/green]"
                            )
                else:
                    # Fallback: create file with video ID format (for backward compatibility)
                    output_file = output / f"{video_id}_transcript.{format}"
                    output_file.parent.mkdir(parents=True, exist_ok=True)

                    # Format and save transcript
                    content = format_transcript_content(
                        result["transcript"],
                        f"YouTube Video {video_id}",
                        model,
                        device,
                        format,
                        video_id=video_id,
                        vault_path=vault_path,
                        timestamps=timestamps,
                        output_dir=output,
                    )

                    with open(output_file, "w", encoding="utf-8") as f:
                        f.write(content)

                    if not ctx.quiet:
                        console.print(
                            f"[green]✓ Transcript saved to: {output_file}[/green]"
                        )
                    if result.get("thumbnails"):
                        for thumbnail in result["thumbnails"]:
                            console.print(
                                f"[green]✓ Thumbnail saved to: {thumbnail}[/green]"
                            )
            else:
                console.print(f"[red]✗ Transcription failed:[/red] {result['error']}")
                track_failed_transcript(input, f"Error: {result['error']}", output)
                sys.exit(1)
        else:
            # Handle file input (existing logic)
            input_path_obj = Path(input)
            if not input_path_obj.exists():
                console.print(f"[red]✗ File not found: {input}[/red]")
                sys.exit(1)

            # Check if transcript already exists
            output_file = output / f"{input_path_obj.stem}_transcript.{format}"
            if not overwrite and output_file.exists():
                if not ctx.quiet:
                    console.print(
                        f"[yellow]⚠ Transcript already exists: {output_file}, skipping (use --overwrite to replace)[/yellow]"
                    )
                sys.exit(0)

            # Import the audio processor
            from ..processors.audio_processor import AudioProcessor

            # Create audio processor
            processor = AudioProcessor(
                device=device, model=model, use_whisper_cpp=use_whisper_cpp
            )

            # Process the input
            from ..processors.base import ProcessorResult

            result: ProcessorResult = processor.process(input_path_obj, device=device)

            if result.success:
                if not ctx.quiet:
                    console.print(
                        "[green]✓ Transcription completed successfully[/green]"
                    )
                    # Extract text from the transcription result
                    transcript_text = (
                        result.data.get("text", "")
                        if isinstance(result.data, dict)
                        else str(result.data)
                    )
                    console.print(
                        f"[dim]Transcript length: {len(transcript_text)} characters[/dim]"
                    )

                # Save transcript to output file
                output_file = output / f"{input_path_obj.stem}_transcript.{format}"
                output_file.parent.mkdir(parents=True, exist_ok=True)

                # Format and save transcript
                content = format_transcript_content(
                    result.data,
                    input_path_obj.name,
                    model,
                    device,
                    format,
                    input_path_obj,
                    vault_path=vault_path,
                    timestamps=timestamps,
                    output_dir=output,
                )

                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(content)

                if not ctx.quiet:
                    console.print(
                        f"[green]✓ Transcript saved to: {output_file}[/green]"
                    )
            else:
                console.print(
                    f"[red]✗ Transcription failed:[/red] {'; '.join(result.errors)}"
                )
                sys.exit(1)

    except Exception as e:
        console.print(f"[red]✗ Unexpected error during transcription:[/red] {e}")
        if ctx.verbose:
            import traceback

            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)
