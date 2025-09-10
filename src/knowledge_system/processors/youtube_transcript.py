"""
Advanced YouTube Transcript Processor

Uses youtube-transcript-api with PacketStream proxies for transcript extraction.

PacketStream provides reliable residential proxies for accessing YouTube transcripts.
"""

import json
import os  # Added for os.access
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:
    requests = None

from pydantic import BaseModel, Field

from ..logger import get_logger
from ..utils.cancellation import CancellationError, CancellationToken
from ..utils.text_utils import strip_bracketed_content
from ..utils.youtube_utils import extract_urls, is_youtube_url
from .base import BaseProcessor, ProcessorResult

logger = get_logger(__name__)


def sanitize_tag(tag: str) -> str:
    """
    Sanitize YouTube tags by replacing spaces with underscores and removing/converting non-alphanumeric characters
    Sanitize YouTube tags by replacing spaces with underscores and removing/converting non-alphanumeric characters.

    Args:
        tag: Original tag string

    Returns:
        Sanitized tag string suitable for YAML and general use
    """
    if not tag or not isinstance(tag, str):
        return ""

    # Replace spaces with underscores
    sanitized = tag.replace(" ", "_")

    # Keep only alphanumeric characters and underscores
    # This removes special characters like punctuation, emojis, etc.
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "", sanitized)

    # Remove leading/trailing underscores and collapse multiple underscores
    sanitized = re.sub(r"_+", "_", sanitized).strip("_")

    # Return empty string if nothing valid remains
    return sanitized if sanitized else ""


def sanitize_tags(tags: list[str]) -> list[str]:
    """
    Sanitize a list of YouTube tags
    Sanitize a list of YouTube tags.

    Args:
        tags: List of original tag strings

    Returns:
        List of sanitized tag strings with empty strings filtered out
    """
    if not tags:
        return []

    sanitized_tags = []
    for tag in tags:
        sanitized = sanitize_tag(tag)
        if sanitized:  # Only add non-empty sanitized tags
            sanitized_tags.append(sanitized)

    return sanitized_tags


YouTubeTranscriptApi = None
WebshareProxyConfig = None


class YouTubeTranscript(BaseModel):
    """YouTube transcript model."""

    video_id: str = Field(..., description="YouTube video ID")
    title: str = Field(..., description="Video title")
    url: str = Field(..., description="Full YouTube URL")
    language: str = Field(..., description="Transcript language code")
    is_manual: bool = Field(
        ..., description="Whether this is a manual transcript (not auto-generated)"
    )
    transcript_text: str = Field(..., description="Full transcript text")
    transcript_data: list[dict[str, Any]] = Field(
        default_factory=list, description="Raw transcript data with timestamps"
    )
    duration: int | None = Field(default=None, description="Video duration in seconds")
    uploader: str = Field(default="", description="Channel name")
    upload_date: str | None = Field(default=None, description="Upload date (YYYYMMDD)")
    description: str = Field(default="", description="Video description")
    view_count: int | None = Field(default=None, description="Video view count")
    tags: list[str] = Field(default_factory=list, description="Video tags")
    thumbnail_url: str | None = Field(
        default=None, description="Thumbnail URL from YouTube API"
    )
    fetched_at: datetime = Field(
        default_factory=datetime.now, description="When transcript was fetched"
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = self.model_dump()
        # Convert datetime to ISO string for JSON serialization
        if "fetched_at" in data and isinstance(data["fetched_at"], datetime):
            data["fetched_at"] = data["fetched_at"].isoformat()
        return data

    def to_markdown(
        self,
        include_timestamps: bool = True,
        include_analysis: bool = True,
        vault_path: Path | None = None,
        output_dir: Path | None = None,
        strip_interjections: bool = False,
        interjections_file: Path | None = None,
    ) -> str:
        """Convert transcript to markdown format with enhanced Obsidian sections."""
        lines = []

        # Add YAML frontmatter with title and metadata
        # Escape quotes in title for YAML safety
        safe_title = self.title.replace('"', '\\"')
        lines.append("---")
        lines.append(f'title: "{safe_title}"')
        lines.append(f'source: "{self.url}"')
        lines.append(f'video_id: "{self.video_id}"')
        lines.append(f'language: "{self.language}"')
        lines.append(f'type: "{"Manual" if self.is_manual else "Auto-generated"}"')

        # Only include metadata if available (keeping it simple)
        if self.uploader:
            lines.append(f'uploader: "{self.uploader}"')

        if self.upload_date:
            try:
                date_obj = datetime.strptime(self.upload_date, "%Y%m%d")
                lines.append(f'upload_date: "{date_obj.strftime("%B %d, %Y")}"')
            except ValueError:
                lines.append(f'upload_date: "{self.upload_date}"')

        if self.duration:
            minutes = self.duration // 60
            seconds = self.duration % 60
            lines.append(f'duration: "{minutes}:{seconds:02d}"')

        # Add view count if available
        if self.view_count:
            lines.append(f"view_count: {self.view_count}")

        # Add tags if available (include all tags, don't truncate)
        if self.tags:
            # Use original tags with minimal sanitization (only escape quotes)
            safe_tags = [tag.replace('"', '\\"') for tag in self.tags]
            tags_yaml = "[" + ", ".join(f'"{tag}"' for tag in safe_tags) + "]"
            lines.append(f"tags: {tags_yaml}")
            lines.append(f"# Total tags: {len(self.tags)}")

        # Add transcript processing metadata
        lines.append('model: "YouTube Transcript"')
        lines.append('device: "Web API"')

        # Add extraction timestamp
        lines.append(f'fetched: "{self.fetched_at.strftime("%Y-%m-%d %H:%M:%S")}"')

        lines.append("---")
        lines.append("")

        # Create sanitized title for thumbnail reference (user-friendly naming)
        safe_title_for_filename = re.sub(r"[^\w\s-]", "", self.title).strip()
        safe_title_for_filename = re.sub(r"[-\s]+", "-", safe_title_for_filename)

        # Add thumbnail reference for YouTube videos using video ID (matches actual saved filename)
        # Thumbnails are always saved as {video_id}_thumbnail.jpg by the download function
        lines.append(f"![Video Thumbnail](Thumbnails/{self.video_id}_thumbnail.jpg)")
        lines.append("")

        # Add clickable link to the YouTube video
        lines.append(f"**🎥 [Watch on YouTube]({self.url})**")
        lines.append("")

        # Add Full Transcript section
        lines.append("## Full Transcript")
        lines.append("")

        # Format transcript with timestamps if available
        if self.transcript_data and include_timestamps:
            previous_speaker = None
            for segment in self.transcript_data:
                start_time = segment.get("start", 0)
                text = segment.get("text", "").strip()
                speaker = segment.get("speaker", "")

                if text:
                    # Remove bracketed content like [music], [applause], etc.
                    text = strip_bracketed_content(text)
                    # Only add the segment if there's still text after bracket removal
                    if text.strip():
                        # Calculate start timestamp
                        start_minutes = int(start_time // 60)
                        start_seconds = int(start_time % 60)
                        start_timestamp = f"{start_minutes:02d}:{start_seconds:02d}"

                        # Calculate end timestamp (use duration if available, otherwise estimate)
                        duration = segment.get("duration")
                        if duration is not None:
                            end_time = start_time + duration
                        else:
                            # Estimate end time as start of next segment or +3 seconds if last
                            # Find next segment with text
                            current_index = self.transcript_data.index(segment)
                            next_segment = None
                            for i in range(
                                current_index + 1, len(self.transcript_data)
                            ):
                                next_seg = self.transcript_data[i]
                                if next_seg.get("text", "").strip():
                                    next_segment = next_seg
                                    break

                            if next_segment:
                                end_time = next_segment.get("start", start_time + 3)
                            else:
                                end_time = start_time + 3  # Default 3 second segment

                        end_minutes = int(end_time // 60)
                        end_seconds = int(end_time % 60)
                        end_timestamp = f"{end_minutes:02d}:{end_seconds:02d}"

                        # Create hyperlinked timestamp for YouTube videos with start and end times
                        if self.video_id:
                            youtube_url = f"https://www.youtube.com/watch?v={self.video_id}&t={int(start_time)}s"
                            timestamp_display = (
                                f"[{start_timestamp} - {end_timestamp}]({youtube_url})"
                            )
                        else:
                            timestamp_display = (
                                f"**{start_timestamp} - {end_timestamp}**"
                            )

                        # Format with speaker information if available (for diarized transcripts)
                        if speaker:
                            # Add speaker change separator for better readability
                            if (
                                speaker != previous_speaker
                                and previous_speaker is not None
                            ):
                                lines.append("---")
                                lines.append("")

                            # Use proper diarization formatting with line breaks and proper speaker labels
                            # Convert speaker ID to human-readable format
                            speaker_display = speaker
                            if speaker.startswith("SPEAKER_"):
                                speaker_num = speaker.replace("SPEAKER_", "")
                                try:
                                    speaker_number = int(speaker_num) + 1
                                    speaker_display = f"Speaker {speaker_number}"
                                except (ValueError, TypeError):
                                    speaker_display = speaker

                            # Use the proper format with line breaks between speaker, timestamp, and text
                            lines.append(f"**{speaker_display}**")
                            lines.append(f"{timestamp_display}")
                            lines.append("")
                            lines.append(text)
                            lines.append("")

                            previous_speaker = speaker
                        else:
                            # Regular format for non-diarized transcripts
                            lines.append(f"{timestamp_display}")
                            lines.append("")
                            lines.append(text)
                            lines.append("")
        else:
            # Plain text transcript - preserve formatting if it looks like markdown
            transcript_text = self.transcript_text

            # If the text contains markdown formatting (bold speakers), preserve it
            if "**" in transcript_text and "*" in transcript_text:
                # This looks like formatted markdown, preserve line breaks
                lines.append(transcript_text)
            else:
                # Apply bracketed content removal for unformatted text
                transcript_text = strip_bracketed_content(transcript_text)
                lines.append(transcript_text)

        return "\n".join(lines)

    def to_srt(
        self,
        strip_interjections: bool = False,
        interjections_file: Path | None = None,
    ) -> str:
        """Convert transcript to SRT format."""
        if not self.transcript_data:
            return ""

        srt_lines = []
        for i, segment in enumerate(self.transcript_data, 1):
            start_time = segment.get("start", 0)
            duration = segment.get("duration", 2.0)  # Default 2 second duration
            end_time = start_time + duration
            text = segment.get("text", "").strip()

            if text:
                # Remove bracketed content like [music], [applause], etc.
                text = strip_bracketed_content(text)
                # Only add the segment if there's still text after bracket removal
                if text.strip():
                    # Format timestamps for SRT
                    start_srt = self._format_srt_timestamp(start_time)
                    end_srt = self._format_srt_timestamp(end_time)

                    srt_lines.append(str(i))
                    srt_lines.append(f"{start_srt} --> {end_srt}")
                    srt_lines.append(text)
                    srt_lines.append("")

        return "\n".join(srt_lines)

    def _format_srt_timestamp(self, seconds: float) -> str:
        """Format seconds to SRT timestamp format (HH:MM:SS,mmm)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"


class YouTubeTranscriptProcessor(BaseProcessor):
    """YouTube transcript processor using youtube-transcript-api with PacketStream proxies."""

    def __init__(
        self,
        preferred_language: str = "en",
        prefer_manual: bool = True,
        fallback_to_auto: bool = True,
        force_diarization: bool = False,
        require_diarization: bool = False,
        **kwargs,
    ) -> None:
        """Initialize the YouTube transcript processor."""
        super().__init__("youtube_transcript")
        self.preferred_language = preferred_language
        self.prefer_manual = prefer_manual
        self.fallback_to_auto = fallback_to_auto
        self.force_diarization = force_diarization
        self.require_diarization = require_diarization

        # Configure extraction method
        from ..config import get_settings

        self.settings = get_settings()
        self.use_proxy = False
        self.proxy_manager = None

        # Configure PacketStream proxy (optional)
        self._configure_packetstream_proxy()
        # Note: No requirement for API keys - youtube-transcript-api works without them

    def _configure_packetstream_proxy(self):
        """Configure PacketStream proxy for YouTube transcript access (optional)."""
        try:
            from ..utils.packetstream_proxy import PacketStreamProxyManager

            self.proxy_manager = PacketStreamProxyManager()
            if self.proxy_manager.username and self.proxy_manager.auth_key:
                self.use_proxy = True
                logger.info("✅ Configured PacketStream proxy for transcript extraction")
            else:
                logger.warning("⚠️ PACKETSTREAM PROXY NOT CONFIGURED")
                logger.warning(
                    "⚠️ Using direct access - YouTube may trigger anti-bot detection!"
                )
                logger.warning(
                    "⚠️ For reliable YouTube access, configure PacketStream in Settings > API Keys"
                )
                self.use_proxy = False

        except Exception as e:
            logger.warning(f"⚠️ PACKETSTREAM PROXY NOT AVAILABLE: {e}")
            logger.warning(
                "⚠️ Using direct access - YouTube may block requests due to anti-bot detection!"
            )
            logger.warning(
                "⚠️ For reliable access, configure PacketStream credentials in Settings > API Keys"
            )
            self.use_proxy = False

    def _configure_webshare_transcript_api(self):
        """Deprecated: WebShare support removed."""
        raise ImportError(
            "WebShare support has been removed. Use PacketStream proxy or direct access."
        )

    @property
    def supported_formats(self) -> list[str]:
        """Return list of supported input formats."""
        return ["youtube_url"]

    def validate_input(self, input_data: Any) -> bool:
        """Validate that input contains YouTube URLs."""
        if isinstance(input_data, str):
            return is_youtube_url(input_data)
        elif isinstance(input_data, list):
            return any(is_youtube_url(str(item)) for item in input_data)
        return False

    def _extract_video_id(self, url: str) -> str | None:
        """Extract video ID from YouTube URL."""
        if "youtu.be/" in url:
            return url.split("youtu.be/")[1].split("?")[0]
        elif "watch?v=" in url:
            return url.split("watch?v=")[1].split("&")[0]
        else:
            logger.error(f"Could not extract video ID from URL: {url}")
            return None

    def _validate_webshare_config(self) -> list[str]:
        """Deprecated: WebShare validation removed."""
        return []

    def _fetch_video_transcript(
        self, url: str, cancellation_token: CancellationToken | None = None
    ) -> YouTubeTranscript | None:
        """Fetch transcript for a single video using youtube-transcript-api with PacketStream proxy."""

        logger.info(f"Fetching transcript for: {url}")

        # If diarization is forced, skip transcript API but still get metadata
        if self.force_diarization:
            logger.info(
                f"Force diarization enabled - skipping transcript API for: {url}"
            )
            # Return empty transcript object with metadata - diarization will handle transcript
            from ..processors.youtube_metadata import YouTubeMetadataProcessor

            try:
                metadata_processor = YouTubeMetadataProcessor()
                metadata_result = metadata_processor.process([url])

                if (
                    metadata_result.success
                    and metadata_result.data
                    and metadata_result.data.get("metadata")
                ):
                    video_metadata = metadata_result.data["metadata"][0]
                    # Create empty transcript with metadata for diarization to fill
                    return YouTubeTranscript(
                        video_id=self._extract_video_id(url),
                        title=video_metadata.get("title", "Unknown Title"),
                        url=url,
                        language="en",  # Will be updated by diarization
                        is_manual=False,
                        transcript_text="",  # Empty - will be filled by diarization
                        transcript_data=[],  # Empty - will be filled by diarization
                        duration=video_metadata.get("duration"),
                        uploader=video_metadata.get("uploader", ""),
                        upload_date=video_metadata.get("upload_date"),
                        description=video_metadata.get("description", ""),
                        view_count=video_metadata.get("view_count"),
                        tags=video_metadata.get("tags", []),
                        thumbnail_url=video_metadata.get("thumbnail"),
                    )
                else:
                    logger.warning(
                        "Failed to get metadata for diarization - proceeding without metadata"
                    )
                    return None
            except Exception as e:
                logger.warning(
                    f"Failed to get metadata for diarization - proceeding without metadata: {e}"
                )
                # Continue without metadata rather than failing completely
                return None

        # Fetch via Bright Data API
        try:
            from ..utils.bright_data_adapters import (
                adapt_bright_data_transcript,
                validate_bright_data_response,
            )
        except Exception as e:
            logger.error(f"Bright Data adapters unavailable: {e}")
            return None

        try:
            # Check for cancellation at the start
            if cancellation_token and cancellation_token.is_cancelled():
                raise CancellationError("Transcript fetch cancelled")

            # Extract video ID from URL
            video_id = self._extract_video_id(url)
            if not video_id:
                return None

            # Bright Data YouTube Posts API - Datasets v3 (Working Implementation)
            # This uses the account-specific dataset ID for YouTube Posts "Collect by URL"
            dataset_id = "gd_lk538t2k2p1k3oos71"  # Your YouTube Posts dataset ID

            # Use the same working implementation as youtube_metadata.py
            trigger_url = f"https://api.brightdata.com/datasets/v3/trigger?dataset_id={dataset_id}&format=json"

            headers = {
                "Authorization": f"Bearer {self.bright_data_api_key}",
                "Content-Type": "application/json",
            }

            # Payload for Datasets v3 trigger
            trigger_payload = [{"url": url}]

            # Fetch real metadata using the YouTube metadata processor
            real_metadata = None
            try:
                from .youtube_metadata import YouTubeMetadataProcessor

                metadata_processor = YouTubeMetadataProcessor()
                metadata_result = metadata_processor.process(url)
                if (
                    metadata_result.success
                    and metadata_result.data
                    and metadata_result.data.get("metadata")
                ):
                    real_metadata = metadata_result.data["metadata"][0]
                    logger.info(
                        f"Successfully fetched Rich Meta data: {real_metadata.get('title', 'Unknown')}"
                    )
            except Exception as e:
                logger.warning(f"Could not fetch metadata for {video_id}: {e}")

            # Try transcript extraction once via Bright Data
            max_retries = 1
            for attempt in range(max_retries):
                try:
                    # Check for cancellation before each attempt
                    if cancellation_token and cancellation_token.is_cancelled():
                        raise CancellationError(
                            "Transcript fetch cancelled during retry"
                        )

                    # No artificial delays required with Bright Data

                    # Step 1: Trigger the collection using Datasets v3 API
                    logger.debug(
                        f"Triggering Bright Data transcript collection: {trigger_url}"
                    )
                    trigger_response = requests.post(
                        trigger_url,
                        headers=headers,
                        json=trigger_payload,
                        timeout=30,
                        verify=True,
                    )

                    logger.debug(
                        f"Trigger response status: {trigger_response.status_code}"
                    )

                    if trigger_response.status_code != 200:
                        if trigger_response.status_code == 401:
                            logger.error(
                                "Authentication failed (401) - check your Bright Data API key"
                            )
                        elif trigger_response.status_code == 403:
                            logger.error(
                                "Access forbidden (403) - check API key permissions"
                            )
                        elif trigger_response.status_code == 404:
                            logger.error("Dataset not found (404) - check dataset ID")
                        elif trigger_response.status_code == 400:
                            logger.error(
                                f"Bad request (400): {trigger_response.text[:200]}"
                            )
                        else:
                            logger.error(
                                f"Trigger failed with status {trigger_response.status_code}: {trigger_response.text[:200]}"
                            )
                        return None

                    # Get snapshot ID from trigger response
                    trigger_data = trigger_response.json()
                    snapshot_id = trigger_data.get("snapshot_id")

                    if not snapshot_id:
                        logger.error("No snapshot_id received from trigger response")
                        return None

                    logger.info(
                        f"✅ Transcript collection triggered successfully, snapshot ID: {snapshot_id}"
                    )

                    # Step 2: Poll for data with exponential backoff
                    status_url = (
                        f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}"
                    )
                    max_poll_attempts = 15  # Up to 3 minutes of polling

                    data = None
                    for poll_attempt in range(max_poll_attempts):
                        wait_time = min(
                            10, 2 ** min(poll_attempt, 4)
                        )  # Exponential backoff, max 10 seconds
                        if poll_attempt > 0:
                            logger.debug(
                                f"Waiting {wait_time} seconds before poll attempt {poll_attempt + 1}..."
                            )
                            time.sleep(wait_time)

                        logger.debug(
                            f"Polling for transcript data (attempt {poll_attempt + 1}/{max_poll_attempts}): {status_url}"
                        )

                        try:
                            poll_response = requests.get(
                                status_url, headers=headers, timeout=20, verify=True
                            )
                            logger.debug(
                                f"Poll response status: {poll_response.status_code}"
                            )

                            if poll_response.status_code == 200:
                                # Check if we have actual data (not just empty response)
                                if poll_response.text.strip():
                                    logger.info(
                                        f"✅ YouTube transcript data received after {poll_attempt + 1} attempts"
                                    )

                                    try:
                                        data = poll_response.json()
                                        if not validate_bright_data_response(data):
                                            raise RuntimeError(
                                                "Invalid Bright Data response structure"
                                            )
                                        break  # Success! Exit polling loop

                                    except json.JSONDecodeError as e:
                                        logger.error(
                                            f"Failed to parse JSON response: {e}"
                                        )
                                        logger.debug(
                                            f"Raw response: {poll_response.text[:300]}"
                                        )
                                        return None

                                else:
                                    logger.debug(
                                        "Empty response, data still processing..."
                                    )

                            elif poll_response.status_code == 202:
                                logger.debug("Status 202: Still processing...")

                            elif poll_response.status_code == 404:
                                logger.error(
                                    f"Snapshot {snapshot_id} not found or expired"
                                )
                                return None

                            else:
                                logger.warning(
                                    f"Unexpected poll status {poll_response.status_code}: {poll_response.text[:100]}"
                                )

                        except requests.exceptions.Timeout:
                            logger.warning(
                                f"Poll timeout on attempt {poll_attempt + 1}"
                            )
                            continue
                        except Exception as e:
                            logger.warning(
                                f"Poll error on attempt {poll_attempt + 1}: {str(e)[:100]}"
                            )
                            continue

                    if not data:
                        logger.error(
                            f"YouTube transcript collection timed out after {max_poll_attempts} attempts for {video_id}"
                        )
                        return None

                    # Check for cancellation after transcript list fetch
                    if cancellation_token and cancellation_token.is_cancelled():
                        raise CancellationError(
                            "Transcript fetch cancelled after getting transcript list"
                        )

                    # Adapt response to our transcript model
                    bd_transcript = adapt_bright_data_transcript(
                        data, url, self.preferred_language
                    )
                    if not bd_transcript:
                        logger.warning(f"Empty transcript data for video {video_id}")
                        return None

                    # Use real metadata if available, otherwise create fallback
                    if real_metadata:
                        title = real_metadata.get("title", f"YouTube Video {video_id}")
                        uploader = real_metadata.get("uploader", "")
                        duration = real_metadata.get("duration")
                        upload_date = real_metadata.get("upload_date")
                        description = real_metadata.get("description", "")
                        view_count = real_metadata.get("view_count")
                        tags = real_metadata.get("tags", [])
                        thumbnail_url = real_metadata.get("thumbnail_url")
                    else:
                        title = bd_transcript.title or f"YouTube Video {video_id}"
                        uploader = bd_transcript.uploader
                        duration = bd_transcript.duration
                        upload_date = bd_transcript.upload_date
                        description = bd_transcript.description
                        view_count = bd_transcript.view_count
                        tags = bd_transcript.tags
                        thumbnail_url = bd_transcript.thumbnail_url

                    # Create transcript object directly from Bright Data adapter output
                    result = YouTubeTranscript(
                        video_id=video_id,
                        title=title,
                        url=url,
                        language=bd_transcript.language,
                        is_manual=bd_transcript.is_manual,
                        transcript_text=bd_transcript.transcript_text,
                        transcript_data=bd_transcript.transcript_data,
                        duration=duration,
                        uploader=uploader,
                        upload_date=upload_date,
                        description=description,
                        view_count=view_count,
                        tags=tags,
                        thumbnail_url=thumbnail_url,
                        fetched_at=datetime.now(),
                    )

                    logger.info(f"Successfully extracted transcript for {video_id}")
                    return result

                except CancellationError:
                    # Re-raise cancellation errors
                    raise
                except Exception as e:
                    error_msg = str(e)
                    logger.info(f"Attempt {attempt + 1} failed: {error_msg}")

                    logger.error(
                        f"Transcript request failed for video {video_id}: {error_msg}"
                    )

                    if attempt < max_retries - 1:
                        wait_time = random.uniform(
                            5, 10
                        )  # Longer delay to avoid YouTube rate limiting
                        logger.info(f"Waiting {wait_time:.1f}s before retry...")

                        # Check cancellation during wait
                        if cancellation_token:
                            elapsed = 0
                            check_interval = 0.1
                            while elapsed < wait_time:
                                if cancellation_token.is_cancelled():
                                    raise CancellationError(
                                        "Transcript fetch cancelled during retry wait"
                                    )
                                time.sleep(min(check_interval, wait_time - elapsed))
                                elapsed += check_interval
                        else:
                            time.sleep(wait_time)
                    else:
                        logger.error(f"All attempts failed for video {video_id}")

        except CancellationError:
            logger.info(f"Transcript fetch cancelled for {url}")
            raise
        except Exception as proxy_error:
            logger.error(f"Webshare proxy transcript extraction failed: {proxy_error}")

        return None

    def _build_video_id_index(self, output_dir: Path) -> set:
        """Build index of existing video IDs from YAML frontmatter in output directory."""
        video_ids = set()
        files_scanned = 0
        files_failed = 0

        logger.info(f"🔍 Building video ID index from {output_dir}")

        # Get all potential transcript files
        file_patterns = ["*.md", "*.txt", "*.srt", "*.vtt"]
        all_files = []
        for pattern in file_patterns:
            all_files.extend(output_dir.glob(pattern))

        total_files = len(all_files)
        if total_files == 0:
            logger.info("No existing transcript files found in output directory")
            return video_ids

        logger.info(f"Scanning {total_files} files for video IDs...")

        for file_path in all_files:
            try:
                # For .srt and .vtt files, check filename for video ID
                if file_path.suffix in [".srt", ".vtt"]:
                    # Extract video ID from filename if present
                    filename = file_path.stem
                    # Check if filename contains a YouTube video ID pattern (11 chars)
                    import re

                    video_id_pattern = r"[a-zA-Z0-9_-]{11}"
                    matches = re.findall(video_id_pattern, filename)
                    for match in matches:
                        # Verify it looks like a video ID (has mix of letters/numbers)
                        if any(c.isalpha() for c in match) and any(
                            c.isdigit() or c in "_-" for c in match
                        ):
                            video_ids.add(match)
                            files_scanned += 1
                            break
                else:
                    # For .md and .txt files, check YAML frontmatter
                    with open(file_path, encoding="utf-8") as f:
                        # Read only the first 30 lines (frontmatter area)
                        found_frontmatter = False
                        in_frontmatter = False
                        line_count = 0

                        for line in f:
                            line_count += 1
                            if line_count > 30:  # Stop after frontmatter area
                                break

                            # Check for frontmatter delimiters
                            if line.strip() == "---":
                                if not found_frontmatter:
                                    found_frontmatter = True
                                    in_frontmatter = True
                                    continue
                                else:
                                    # End of frontmatter
                                    break

                            # Look for video_id in frontmatter
                            if in_frontmatter and line.startswith("video_id:"):
                                # Extract video ID, handling both quoted and unquoted values
                                parts = line.split(":", 1)
                                if len(parts) == 2:
                                    video_id = parts[1].strip().strip("\"'")
                                    if video_id and len(video_id) > 0:
                                        video_ids.add(video_id)
                                        files_scanned += 1
                                        break

            except UnicodeDecodeError:
                logger.debug(f"Skipping {file_path.name} - encoding error")
                files_failed += 1
            except PermissionError:
                logger.debug(f"Skipping {file_path.name} - permission denied")
                files_failed += 1
            except OSError as e:
                logger.debug(f"Skipping {file_path.name} - OS error: {e}")
                files_failed += 1
            except Exception as e:
                logger.debug(
                    f"Skipping {file_path.name} - unexpected error: {type(e).__name__}: {e}"
                )
                files_failed += 1

        # Report results
        logger.info(
            f"✅ Index built: Found {len(video_ids)} unique video IDs in {files_scanned} files"
        )
        if files_failed > 0:
            logger.warning(f"⚠️  Skipped {files_failed} files due to errors")

        return video_ids

    def _save_index_to_file(self, index_file: Path, video_ids: set) -> None:
        """Save video ID index to JSON file."""
        try:
            with open(index_file, "w", encoding="utf-8") as f:
                json.dump(sorted(list(video_ids)), f, indent=2)
            logger.debug(f"Saved index with {len(video_ids)} video IDs to {index_file}")
        except Exception as e:
            logger.error(f"Failed to save index file: {e}")

    def _process_with_diarization(
        self,
        url: str,
        original_transcript: "YouTubeTranscript",
        output_dir: Path,
        cancellation_token: CancellationToken | None = None,
        progress_callback: callable = None,
        **kwargs,
    ) -> "YouTubeTranscript | None":
        """
        Process YouTube video with diarization by downloading audio and using AudioProcessor.

        Args:
            url: YouTube video URL
            original_transcript: The original transcript from YouTube
            output_dir: Output directory for files
            cancellation_token: Cancellation token for stopping processing
            progress_callback: Function to call with progress updates
            **kwargs: Additional arguments

        Returns:
            Updated transcript with diarization data, or None if failed
        """

        def report_progress(message: str, percent: int = 0):
            """Helper to report progress if callback is available."""
            if progress_callback:
                progress_callback(message, percent)
            logger.info(message)

        try:
            import tempfile

            report_progress("🔍 Checking diarization dependencies...", 5)

            # Check if required dependencies are available
            try:
                from ..processors.audio_processor import AudioProcessor
                from ..processors.diarization import is_diarization_available
            except ImportError as e:
                logger.error(
                    f"Required dependencies not available for diarization: {e}"
                )
                report_progress("❌ Diarization dependencies not available")
                return None

            if not is_diarization_available():
                logger.error("Diarization dependencies not available")
                report_progress("❌ Diarization dependencies not installed")
                return None

            report_progress("✅ Diarization dependencies available", 10)

            # Create temporary directory for audio download
            report_progress("📁 Creating temporary workspace...", 15)
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                audio_file = temp_path / f"{original_transcript.video_id}.mp3"

                # Download audio using yt-dlp with Webshare proxy, with fallback to direct if proxy unavailable
                try:
                    report_progress(
                        "🌐 Preparing network settings for audio download...", 20
                    )

                    # No WebShare usage; proceed without proxy by default

                    # Configure yt-dlp with Webshare proxy - use HTTPS for secure connections
                    proxy_url = None

                    # Import yt-dlp
                    try:
                        import yt_dlp
                    except ImportError:
                        logger.error("yt-dlp not available for audio download")
                        report_progress("❌ yt-dlp not available for audio download")
                        return None

                    report_progress("📥 Starting audio download...", 25)

                    # Configure yt-dlp options for high-quality audio extraction
                    base_ydl_opts = {
                        "format": "bestaudio[ext=m4a]/bestaudio/best",  # High quality audio, prefer m4a
                        "extractaudio": True,
                        "audioformat": "mp3",
                        "audioquality": 0,  # Best quality for accurate transcription/diarization
                        "outtmpl": str(audio_file.with_suffix(".%(ext)s")),
                        "quiet": True,
                        "no_warnings": True,
                        "socket_timeout": 45,  # Longer timeout for parallel downloads
                        "retries": 3,  # Standard retries for connection issues
                        "fragment_retries": 5,  # Moderate fragment retries for stability
                        "http_chunk_size": 524288,  # 512KB chunks - balance between efficiency and stability
                        # Network tuning
                        "nocheckcertificate": True,
                        "prefer_insecure": True,
                        "http_chunk_retry": True,
                        "keep_fragments": False,  # Don't keep fragments to save space
                        "concurrent_fragment_downloads": 12,  # Use more connections for diarization downloads
                        "postprocessors": [
                            {
                                "key": "FFmpegExtractAudio",
                                "preferredcodec": "mp3",
                                "preferredquality": "0",  # Best quality
                            }
                        ],
                    }

                    # Add progress hook for real-time download progress in GUI
                    def download_progress_hook(d):
                        """Hook to capture yt-dlp download progress and forward to GUI."""
                        if d["status"] == "downloading":
                            # Extract progress information
                            downloaded_bytes = d.get("downloaded_bytes", 0)
                            total_bytes = d.get("total_bytes") or d.get(
                                "total_bytes_estimate", 0
                            )
                            speed = d.get("speed", 0)
                            filename = d.get("filename", "Unknown file")

                            if total_bytes > 0:
                                percent = (downloaded_bytes / total_bytes) * 100
                                downloaded_mb = downloaded_bytes / (1024 * 1024)
                                total_mb = total_bytes / (1024 * 1024)
                                speed_mbps = (speed / (1024 * 1024)) if speed else 0

                                # Extract just the filename for cleaner display
                                import os

                                clean_filename = os.path.basename(filename)

                                progress_msg = f"📥 Downloading: {clean_filename[:50]}{'...' if len(clean_filename) > 50 else ''}"
                                progress_detail = f"   {downloaded_mb:.1f}/{total_mb:.1f} MB ({percent:.1f}%)"
                                if speed_mbps > 0:
                                    progress_detail += f" @ {speed_mbps:.1f} MB/s"

                                report_progress(
                                    progress_msg, 25 + int(percent * 0.15)
                                )  # Map to 25-40% range
                                report_progress(
                                    progress_detail, 25 + int(percent * 0.15)
                                )
                        elif d["status"] == "finished":
                            filename = d.get("filename", "Unknown file")
                            import os

                            clean_filename = os.path.basename(filename)
                            report_progress(
                                f"✅ Download complete: {clean_filename[:50]}{'...' if len(clean_filename) > 50 else ''}",
                                40,
                            )
                        elif d["status"] == "error":
                            report_progress(
                                f"❌ Download error: {d.get('error', 'Unknown error')}"
                            )

                    # Attempt download directly (no proxy required)
                    def attempt_download(with_proxy: bool) -> bool:
                        opts = dict(base_ydl_opts)
                        if with_proxy and proxy_url:
                            opts["proxy"] = proxy_url
                        opts["progress_hooks"] = [download_progress_hook]
                        with yt_dlp.YoutubeDL(opts) as ydl:
                            report_progress(
                                f"📥 Starting audio download from {original_transcript.video_id}...",
                                25,
                            )
                            ydl.download([url])
                        return audio_file.exists()

                    success_download = False
                    try:
                        success_download = attempt_download(with_proxy=False)
                    except Exception as direct_exc:
                        logger.error(f"Audio download failed: {direct_exc}")
                        raise

                    if not success_download or not audio_file.exists():
                        logger.error(f"Audio file not created: {audio_file}")
                        report_progress("❌ Audio file not created after download")
                        return None

                    file_size_mb = audio_file.stat().st_size / (1024 * 1024)
                    report_progress(
                        f"✅ Audio downloaded successfully ({file_size_mb:.1f} MB)", 40
                    )

                except Exception as e:
                    logger.error(f"Failed to download audio with Webshare proxy: {e}")
                    report_progress(f"❌ Audio download failed: {e}")
                    return None

                # Check for cancellation
                if cancellation_token and cancellation_token.is_cancelled():
                    logger.info("Processing cancelled during audio download")
                    report_progress("⚠️ Processing cancelled")
                    return None

                # Process with AudioProcessor for diarization
                try:
                    report_progress("🎙️ Initializing diarization pipeline...", 45)

                    # Get settings from the main settings
                    from ..config import get_settings

                    settings = get_settings()
                    hf_token = getattr(settings.api_keys, "huggingface_token", None)

                    # Create progress callback that reports diarization progress
                    def diarization_progress_callback(message: str, percent: int = 0):
                        # Map diarization progress to overall progress (45-85%)
                        overall_percent = 45 + int((percent / 100) * 40)
                        report_progress(f"🎙️ {message}", overall_percent)

                    # Get transcription model from settings or kwargs, default to base
                    transcription_model = kwargs.get("transcription_model") or getattr(
                        settings.transcription, "whisper_model", "base"
                    )

                    processor = AudioProcessor(
                        model=transcription_model,  # Use configurable model from settings
                        enable_diarization=True,
                        require_diarization=True,  # Strict mode: require diarization success
                        hf_token=hf_token,
                        progress_callback=diarization_progress_callback,
                        speaker_assignment_callback=kwargs.get(
                            "speaker_assignment_callback"
                        ),
                    )

                    # Process the audio file
                    # Get file info for better context
                    filename = Path(audio_file).name if audio_file else "audio"
                    try:
                        file_size_mb = (
                            Path(audio_file).stat().st_size / (1024 * 1024)
                            if audio_file
                            else 0
                        )
                        file_info = f" ({file_size_mb:.1f}MB)"
                    except:
                        file_info = ""

                    report_progress(
                        f"🎯 Processing {filename}{file_info} with speaker diarization...",
                        50,
                    )

                    # Pass through kwargs to enable speaker assignment dialog if needed
                    process_kwargs = {
                        "output_dir": None,  # Don't save to file, just get data
                        "timestamps": True,
                        "gui_mode": kwargs.get("gui_mode", False),
                        "show_speaker_dialog": kwargs.get("show_speaker_dialog", True),
                        # Pass through optional speaker assignment callback if provided by GUI worker
                        "speaker_assignment_callback": kwargs.get(
                            "speaker_assignment_callback"
                        ),
                        "metadata": {
                            "video_id": original_transcript.video_id,
                            "title": original_transcript.title,
                            "url": original_transcript.url,
                            "uploader": original_transcript.uploader,
                        },
                    }

                    result = processor.process(audio_file, **process_kwargs)

                    if not result.success:
                        logger.error(f"AudioProcessor failed: {result.errors}")
                        report_progress(
                            f"❌ Diarization failed: {'; '.join(result.errors)}"
                        )
                        return None

                    if not result.data:
                        logger.error("AudioProcessor returned no data")
                        report_progress("❌ Diarization returned no data")
                        return None

                    report_progress("✅ Diarization processing completed", 85)

                    # Create new transcript with diarization data
                    report_progress("📝 Integrating diarization results...", 90)
                    segments = result.data.get("segments", [])
                    if not segments:
                        logger.warning("No segments found in diarization result")
                        report_progress(
                            "⚠️ No speaker segments found in diarization result"
                        )
                        return None

                    # Convert segments to transcript format with proper diarization structure
                    transcript_data = []
                    full_text_parts = []
                    diarized_segments = (
                        []
                    )  # Store segments with speaker info for proper formatting
                    previous_speaker = None  # Track speaker changes for formatting

                    for segment in segments:
                        start_time = segment.get("start", 0)
                        end_time = segment.get("end", start_time)
                        text = segment.get("text", "").strip()
                        speaker = segment.get("speaker", "")

                        if text:
                            # Add to transcript data with speaker information
                            segment_data = {
                                "start": start_time,
                                "duration": end_time - start_time,
                                "text": text,
                            }

                            # Add speaker info if available
                            if speaker:
                                segment_data["speaker"] = speaker

                            transcript_data.append(segment_data)
                            diarized_segments.append(segment_data)

                            # Add to full text with speaker labels formatted for markdown
                            if speaker:
                                # Add speaker change separator for better readability
                                if (
                                    full_text_parts
                                    and previous_speaker is not None
                                    and speaker != previous_speaker
                                ):
                                    full_text_parts.append("---")
                                    full_text_parts.append("")

                                # Check if this is a meaningful name (from speaker attribution) vs generic ID
                                if speaker.startswith("SPEAKER_"):
                                    # Convert generic speaker ID to human-readable format
                                    speaker_num = speaker.replace("SPEAKER_", "").zfill(
                                        2
                                    )
                                    try:
                                        speaker_number = int(speaker_num) + 1
                                        speaker_display = f"Speaker {speaker_number}"
                                    except (ValueError, AttributeError):
                                        # Fallback if speaker format is unexpected
                                        speaker_display = speaker
                                else:
                                    # This is already a meaningful name from speaker attribution
                                    speaker_display = speaker

                                # Format with proper markdown structure
                                full_text_parts.append(f"**{speaker_display}**")
                                full_text_parts.append(
                                    f"*{self._format_simple_timestamp(start_time)}*"
                                )
                                full_text_parts.append("")
                                full_text_parts.append(text)
                                full_text_parts.append("")

                                previous_speaker = speaker
                            else:
                                full_text_parts.append(text)
                                full_text_parts.append("")

                    # Create updated transcript
                    updated_transcript = YouTubeTranscript(
                        video_id=original_transcript.video_id,
                        title=original_transcript.title,
                        url=original_transcript.url,
                        language=original_transcript.language,
                        is_manual=False,  # This is AI-generated
                        transcript_text="\n".join(full_text_parts),
                        transcript_data=transcript_data,
                        duration=original_transcript.duration,
                        uploader=original_transcript.uploader,
                        upload_date=original_transcript.upload_date,
                        description=original_transcript.description,
                        view_count=original_transcript.view_count,
                        tags=original_transcript.tags,
                        thumbnail_url=original_transcript.thumbnail_url,
                        fetched_at=original_transcript.fetched_at,
                    )

                    report_progress("✅ Diarization integration completed!", 100)
                    return updated_transcript

                except Exception as e:
                    logger.error(f"Failed to process audio with diarization: {e}")
                    report_progress(f"❌ Diarization processing failed: {e}")
                    return None

        except Exception as e:
            logger.error(f"Diarization processing failed: {e}")
            report_progress(f"❌ Diarization failed: {e}")
            return None

    def _format_simple_timestamp(self, seconds: float) -> str:
        """Format seconds to MM:SS or HH:MM:SS for display."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"

    def _update_index_file(self, index_file: Path, video_id: str) -> None:
        """Append a new video ID to the index file."""
        try:
            # Read existing index
            video_ids = set()
            if index_file.exists():
                with open(index_file, encoding="utf-8") as f:
                    video_ids = set(json.load(f))

            # Add new ID and save
            video_ids.add(video_id)
            self._save_index_to_file(index_file, video_ids)

        except Exception as e:
            logger.error(f"Failed to update index file: {e}")

    def process(
        self,
        input_data: Any,
        dry_run: bool = False,
        output_dir: str | Path | None = None,
        output_format: str | None = None,
        vault_path: str | Path | None = None,
        include_timestamps: bool = True,
        include_analysis: bool = True,
        strip_interjections: bool = False,
        interjections_file: str | Path | None = None,
        enable_diarization: bool = False,
        cancellation_token: CancellationToken | None = None,
        progress_callback: callable = None,
        **kwargs,
    ) -> ProcessorResult:
        """Process YouTube URLs to extract transcripts."""
        try:
            # Check for cancellation at the start
            if cancellation_token and cancellation_token.is_cancelled():
                return ProcessorResult(
                    success=False,
                    errors=["Processing cancelled before start"],
                    metadata={"processor": self.name, "cancelled": True},
                )

            # Extract overwrite parameter from config
            overwrite_existing = kwargs.get("overwrite", False)
            logger.info(f"Overwrite existing files: {overwrite_existing}")

            output_format = output_format or "md"
            urls = extract_urls(input_data)

            if not urls:
                return ProcessorResult(
                    success=False, errors=["No valid YouTube URLs found in input"]
                )

            # Expand any playlist URLs into individual video URLs with metadata
            from ..utils.youtube_utils import expand_playlist_urls_with_metadata

            expansion_result = expand_playlist_urls_with_metadata(urls)
            urls = expansion_result["expanded_urls"]
            playlist_info = expansion_result["playlist_info"]

            if not urls:
                return ProcessorResult(
                    success=False,
                    errors=["No valid video URLs found after playlist expansion"],
                )

            # Validate WebShare configuration before processing
            config_issues = self._validate_webshare_config()
            if config_issues:
                logger.warning("WebShare configuration issues detected")
                for issue in config_issues:
                    logger.warning(issue)
                return ProcessorResult(
                    success=False,
                    errors=[
                        f"WebShare configuration issue: {'; '.join(config_issues)}"
                    ],
                )

            # CRITICAL DEBUG: Check what output_dir we received BEFORE converting to Path
            logger.info(
                f"🔍 Original output_dir parameter: {repr(output_dir)} (type: {type(output_dir)})"
            )

            output_dir = Path(output_dir).expanduser() if output_dir else Path.cwd()
            output_dir.mkdir(parents=True, exist_ok=True)

            logger.info(
                f"YouTube transcript extraction starting. Output directory: {output_dir}"
            )
            logger.info(f"Output directory exists: {output_dir.exists()}")
            logger.info(
                f"Output directory is writable: {output_dir.is_dir() and output_dir.stat().st_mode}"
            )
            logger.info(f"Absolute output path: {output_dir.absolute()}")

            # Verify if we're using the intended directory
            cwd = Path.cwd().absolute()
            if output_dir.absolute() == cwd:
                logger.warning(
                    f"⚠️ Output directory is current working directory: {cwd}"
                )
                logger.warning(
                    "⚠️ This might indicate the GUI didn't pass the intended output directory"
                )
            else:
                logger.info(
                    f"✅ Using specified output directory: {output_dir.absolute()}"
                )

            transcripts = []
            errors = []
            saved_files = []
            skipped_files = []  # Track files that were skipped due to overwrite=False
            failed_files = []  # Track files that failed processing
            database_save_failed = False  # Track database save failures

            # Build video ID index if overwrite is disabled
            existing_video_ids = set()
            index_file = None
            skipped_via_index = 0

            if not overwrite_existing:
                # Create session-specific index file
                index_filename = (
                    f".youtube_index_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                )
                index_file = output_dir / index_filename

                # Build index from existing files
                logger.info(
                    "🔎 Overwrite disabled - building index of existing videos..."
                )
                existing_video_ids = self._build_video_id_index(output_dir)

                if existing_video_ids:
                    # Save initial index
                    self._save_index_to_file(index_file, existing_video_ids)
                    logger.info(
                        f"📊 Index created with {len(existing_video_ids)} existing videos"
                    )
                    logger.info(f"💾 Session index saved to: {index_file.name}")

            # Create Thumbnails subdirectory upfront
            thumbnails_dir = output_dir / "Thumbnails"
            thumbnails_dir.mkdir(exist_ok=True)
            logger.info(f"Created thumbnails directory: {thumbnails_dir}")

            for i, url in enumerate(urls, 1):
                try:
                    # Check for cancellation before each URL
                    if cancellation_token and cancellation_token.is_cancelled():
                        logger.info("Processing cancelled by user")
                        break

                    # OPTIMIZATION: Check video ID index before fetching
                    video_id = self._extract_video_id(url)
                    if (
                        video_id
                        and not overwrite_existing
                        and video_id in existing_video_ids
                    ):
                        logger.info(
                            f"⏭️ Skipping URL {i}/{len(urls)}: Video {video_id} already in index"
                        )
                        skipped_files.append(f"{video_id} (via index)")
                        skipped_via_index += 1
                        continue

                    # Determine playlist context for progress display
                    playlist_context = ""
                    for playlist in playlist_info:
                        if playlist["start_index"] <= (i - 1) <= playlist["end_index"]:
                            playlist_position = (i - 1) - playlist["start_index"] + 1
                            playlist_context = f" [Playlist: {playlist['title'][:40]}{'...' if len(playlist['title']) > 40 else ''} - Video {playlist_position}/{playlist['total_videos']}]"
                            break

                    logger.info(
                        f"Processing URL {i}/{len(urls)}: {url}{playlist_context}"
                    )
                    transcript = self._fetch_video_transcript(url, cancellation_token)
                    if transcript:
                        # Handle diarization if enabled
                        if enable_diarization:
                            logger.info(
                                f"Diarization enabled for {transcript.video_id}, downloading audio for processing..."
                            )
                            diarized_transcript = self._process_with_diarization(
                                url,
                                transcript,
                                output_dir,
                                cancellation_token,
                                progress_callback,
                                **kwargs,
                            )
                            if diarized_transcript:
                                transcript = diarized_transcript
                                logger.info(
                                    f"Successfully processed {transcript.video_id} with diarization"
                                )
                            else:
                                # Diarization failed - write error file and record explicit failure
                                logger.error(
                                    f"Diarization failed for {transcript.video_id}, writing error file instead of transcript"
                                )

                                # Create error filename
                                safe_title = re.sub(
                                    r"[<>:\"/\\|?*]", "", transcript.title
                                ).strip()
                                safe_title = safe_title.replace("-", " ")
                                safe_title = re.sub(r"\s+", " ", safe_title)
                                if safe_title and len(safe_title) > 100:
                                    safe_title = safe_title[:100].rstrip()

                                error_filename = (
                                    f"{safe_title}_DIARIZATION_ERROR.md"
                                    if safe_title
                                    else f"{transcript.video_id}_DIARIZATION_ERROR.md"
                                )
                                error_file_path = output_dir / error_filename

                                # Write error file with details
                                error_content = """# Diarization Error Report

**Video:** {transcript.title}
**Video ID:** {transcript.video_id}
**URL:** {url}
**Error Time:** {datetime.now().isoformat()}

## Error Details
Diarization processing failed for this video. The transcript was not saved to allow re-processing with diarization once the issue is resolved.

## Troubleshooting
1. Verify yt-dlp installation and dependencies
2. Ensure sufficient disk space for audio download
4. Check diarization model dependencies (pyannote.audio, etc.)

## Next Steps
- Fix the underlying issue
- Re-run the transcript extraction with diarization enabled
- This error file will be overwritten when processing succeeds
"""

                                try:
                                    with open(
                                        error_file_path, "w", encoding="utf-8"
                                    ) as f:
                                        f.write(error_content)
                                    logger.info(
                                        f"Error file written: {error_file_path}"
                                    )
                                    # Track as a failed file instead of skipped
                                    failed_files.append(str(error_file_path))
                                except Exception as e:
                                    logger.error(
                                        f"Failed to write error file {error_file_path}: {e}"
                                    )

                                # Record explicit diarization failure for UI/CSV reporting
                                errors.append(
                                    f"Diarization failed for {transcript.video_id} ({url})"
                                )

                                # Skip adding to transcripts - no regular transcript should be saved
                                continue

                        # IMMEDIATE FILE WRITING: Write file right after extraction instead of batching
                        # Only add transcript to list after successful file writing to avoid false success
                        if output_dir and not dry_run:
                            try:
                                logger.info(
                                    f"Immediately saving transcript for {transcript.video_id}"
                                )

                                # Create sanitized filename from title with improved error handling
                                # Preserve more characters for better filename readability (keep commas, periods, parentheses)
                                safe_title = re.sub(
                                    r"[<>:\"/\\|?*]", "", transcript.title
                                ).strip()
                                # Convert dashes to spaces for consistent naming (matching YAML title behavior)
                                safe_title = safe_title.replace("-", " ")
                                # Collapse multiple spaces into single spaces
                                safe_title = re.sub(r"\s+", " ", safe_title)

                                # Additional filename safety checks for macOS
                                if safe_title:
                                    # Remove leading/trailing spaces (previously handled hyphens)
                                    safe_title = safe_title.strip()
                                    # Limit length to avoid filesystem issues
                                    if len(safe_title) > 100:
                                        safe_title = safe_title[:100].rstrip()

                                logger.debug(
                                    f"Sanitized title: '{safe_title}' (length: {len(safe_title) if safe_title else 0})"
                                )

                                # Determine filename with robust fallback logic
                                if (
                                    safe_title
                                    and len(safe_title) > 0
                                    and not safe_title.startswith("YouTube-Video")
                                    and not transcript.title.startswith(
                                        "YouTube Video "
                                    )
                                ):
                                    filename = f"{safe_title}.{output_format}"
                                    logger.debug(
                                        f"Using title-based filename: '{filename}'"
                                    )
                                else:
                                    # Fallback to video ID - ensure it's valid
                                    video_id = transcript.video_id or "unknown_video"
                                    # Sanitize video ID as well (though it should be safe)
                                    video_id = re.sub(r"[^\w-]", "", video_id)
                                    filename = f"{video_id}_transcript.{output_format}"
                                    logger.debug(
                                        f"Using video_id-based filename: '{filename}' (video_id: '{video_id}')"
                                    )

                                # Always use video_id for thumbnail naming to match how thumbnails are actually saved
                                thumbnail_filename = (
                                    f"{transcript.video_id}_thumbnail.jpg"
                                )

                                # Validate filename isn't empty or invalid
                                if (
                                    not filename
                                    or filename.startswith(".")
                                    or len(filename.split(".")[0]) == 0
                                ):
                                    logger.error(
                                        f"Generated invalid filename '{filename}' for video {transcript.video_id}"
                                    )
                                    fallback_filename = f"youtube_video_{transcript.video_id or 'unknown'}.{output_format}"
                                    logger.info(
                                        f"Using fallback filename: '{fallback_filename}'"
                                    )
                                    filename = fallback_filename

                                filepath = output_dir / filename
                                thumbnail_path = thumbnails_dir / thumbnail_filename

                                # OVERWRITE CHECKING: Skip existing files if overwrite=False
                                if filepath.exists() and not overwrite_existing:
                                    logger.info(
                                        f"⏭️ Skipping existing transcript: {filepath} (overwrite disabled)"
                                    )
                                    skipped_files.append(str(filepath))
                                    # Add transcript to list for skipped files (still considered success)
                                    transcripts.append(transcript)
                                    continue

                                logger.info(f"Creating transcript file: {filepath}")
                                logger.debug(
                                    f"Output directory exists: {output_dir.exists()}"
                                )
                                logger.debug(
                                    f"Output directory is writable: {os.access(output_dir, os.W_OK) if output_dir.exists() else 'Unknown'}"
                                )
                                logger.debug(
                                    f"File path parent exists: {filepath.parent.exists()}"
                                )

                                # Write transcript in requested format
                                vault_path_obj = (
                                    Path(vault_path) if vault_path else None
                                )
                                interjections_file_obj = (
                                    Path(interjections_file)
                                    if interjections_file
                                    else None
                                )

                                try:
                                    if output_format == "md":
                                        content = transcript.to_markdown(
                                            include_timestamps=include_timestamps,
                                            include_analysis=include_analysis,
                                            vault_path=vault_path_obj,
                                            output_dir=output_dir,
                                            strip_interjections=strip_interjections,
                                            interjections_file=interjections_file_obj,
                                        )
                                    elif output_format == "srt":
                                        content = transcript.to_srt(
                                            strip_interjections=strip_interjections,
                                            interjections_file=interjections_file_obj,
                                        )
                                    else:
                                        content = transcript.transcript_text

                                    # Validate content isn't empty
                                    if not content or len(content.strip()) == 0:
                                        logger.error(
                                            f"Generated empty content for video {transcript.video_id} (title: '{transcript.title}')"
                                        )
                                        errors.append(
                                            f"Empty transcript content for {transcript.video_id}"
                                        )
                                        continue

                                    logger.debug(
                                        f"Generated content length: {len(content)} characters"
                                    )

                                except Exception as content_error:
                                    logger.error(
                                        f"Failed to generate content for {transcript.video_id}: {content_error}"
                                    )
                                    errors.append(
                                        f"Content generation failed for {transcript.video_id}: {content_error}"
                                    )
                                    continue

                                # Write file with detailed error handling
                                try:
                                    logger.debug(
                                        f"Attempting to write {len(content)} characters to: {filepath}"
                                    )
                                    with open(filepath, "w", encoding="utf-8") as f:
                                        f.write(content)
                                    logger.info(
                                        f"✅ Successfully wrote {len(content)} characters to {filepath}"
                                    )

                                    # Verify file was written correctly
                                    if filepath.exists():
                                        file_size = filepath.stat().st_size
                                        logger.info(
                                            f"✅ File verification successful: {filepath} ({file_size} bytes)"
                                        )
                                        saved_files.append(str(filepath))

                                        # Add transcript to list only after successful file save
                                        transcripts.append(transcript)

                                        # Save to database
                                        db_service = kwargs.get("db_service")
                                        if not db_service:
                                            try:
                                                from ..database.service import (
                                                    DatabaseService,
                                                )

                                                db_service = DatabaseService()
                                            except Exception as e:
                                                logger.debug(
                                                    f"Could not create database service: {e}"
                                                )

                                        if db_service and transcript:
                                            try:
                                                # Create/update media source record
                                                video_metadata = {
                                                    "uploader": transcript.uploader
                                                    or "",
                                                    "upload_date": transcript.upload_date,
                                                    "description": transcript.description
                                                    or "",
                                                    "duration_seconds": transcript.duration,
                                                    "view_count": transcript.view_count,
                                                    "thumbnail_url": transcript.thumbnail_url,
                                                    "tags_json": transcript.tags or [],
                                                    "source_type": "youtube",
                                                }

                                                video_record = db_service.create_video(
                                                    video_id=transcript.video_id,
                                                    title=transcript.title,
                                                    url=transcript.url,
                                                    **video_metadata,
                                                )

                                                if video_record:
                                                    logger.info(
                                                        f"Saved/updated video record: {transcript.video_id}"
                                                    )

                                                # Create/update transcript record
                                                transcript_segments = (
                                                    transcript.transcript_data or []
                                                )
                                                transcript_record = db_service.create_transcript(
                                                    video_id=transcript.video_id,
                                                    language=transcript.language,
                                                    is_manual=transcript.is_manual,
                                                    transcript_text=transcript.transcript_text,
                                                    transcript_segments=transcript_segments,
                                                    transcript_type="youtube_api",
                                                    include_timestamps=include_timestamps,
                                                )

                                                if transcript_record:
                                                    logger.info(
                                                        f"Saved/updated transcript record: {transcript_record.transcript_id}"
                                                    )

                                            except Exception as e:
                                                logger.error(
                                                    f"Error saving to database: {e}"
                                                )
                                                # Track database save failure - this should affect success reporting
                                                database_save_failed = True

                                        # Update index with successfully saved video
                                        if (
                                            not overwrite_existing
                                            and index_file
                                            and transcript.video_id
                                        ):
                                            existing_video_ids.add(transcript.video_id)
                                            self._update_index_file(
                                                index_file, transcript.video_id
                                            )
                                            logger.debug(
                                                f"📝 Added {transcript.video_id} to session index"
                                            )
                                    else:
                                        logger.error(
                                            f"❌ File was not created despite no write errors: {filepath}"
                                        )
                                        errors.append(f"File not created: {filepath}")

                                except PermissionError as e:
                                    logger.error(
                                        f"❌ Permission denied writing to {filepath}: {e}"
                                    )
                                    errors.append(
                                        f"Permission denied: {filepath} - {e}"
                                    )
                                    continue
                                except OSError as e:
                                    logger.error(
                                        f"❌ OS error writing to {filepath}: {e}"
                                    )
                                    errors.append(f"OS error writing {filepath}: {e}")
                                    continue
                                except Exception as write_error:
                                    logger.error(
                                        f"❌ Unexpected error writing {filepath}: {write_error}"
                                    )
                                    errors.append(
                                        f"Write error for {filepath}: {write_error}"
                                    )
                                    continue

                                # Download thumbnail immediately
                                try:
                                    # Check if thumbnail already exists before downloading
                                    expected_thumbnail_path = (
                                        thumbnails_dir / thumbnail_filename
                                    )
                                    if (
                                        expected_thumbnail_path.exists()
                                        and not overwrite_existing
                                    ):
                                        logger.info(
                                            f"⏭️ Skipping existing thumbnail: {expected_thumbnail_path} (overwrite disabled)"
                                        )
                                    else:
                                        logger.info(
                                            f"Downloading thumbnail for {transcript.video_id}"
                                        )
                                        from ..utils.youtube_utils import (
                                            download_thumbnail,
                                        )

                                        # Pass thumbnails_dir directly since download_thumbnail now saves to exact directory provided
                                        # Use Rich Meta thumbnail URL if available
                                        thumbnail_result = download_thumbnail(
                                            transcript.url,
                                            thumbnails_dir,
                                            use_cookies=False,
                                            thumbnail_url=transcript.thumbnail_url,
                                        )
                                        if thumbnail_result:
                                            downloaded_path = Path(thumbnail_result)

                                            # Thumbnail naming is now consistent - no renaming needed
                                            if downloaded_path.exists():
                                                logger.info(
                                                    f"Thumbnail saved as: {downloaded_path}"
                                                )
                                        else:
                                            logger.warning(
                                                f"Failed to download thumbnail for {transcript.video_id}"
                                            )
                                except Exception as e:
                                    logger.warning(
                                        f"Thumbnail download failed for {transcript.video_id}: {e}"
                                    )

                            except Exception as file_error:
                                logger.error(
                                    f"Failed to save transcript for {transcript.video_id}: {file_error}"
                                )
                                errors.append(
                                    f"File save failed for {transcript.video_id}: {file_error}"
                                )
                        else:
                            # No file saving (dry run) - add transcript to list for in-memory access
                            transcripts.append(transcript)
                    else:
                        # If diarization is enabled or forced, try diarization-only path instead of failing
                        if enable_diarization or self.force_diarization:
                            logger.info(
                                f"No transcript via API for {url}, attempting diarization-only processing"
                            )
                            # Build a minimal transcript placeholder if needed
                            video_id_fallback = (
                                self._extract_video_id(url) or "unknown_video"
                            )
                            placeholder = YouTubeTranscript(
                                video_id=video_id_fallback,
                                title=f"YouTube Video {video_id_fallback}",
                                url=url,
                                language="en",
                                is_manual=False,
                                transcript_text="",
                                transcript_data=[],
                            )
                            diarized_transcript = self._process_with_diarization(
                                url,
                                placeholder,
                                output_dir,
                                cancellation_token,
                                progress_callback,
                                **kwargs,
                            )
                            if diarized_transcript:
                                transcript = diarized_transcript
                                # Note: diarized transcripts need to go through file saving logic too
                                logger.info(
                                    f"🎙️ Diarized transcript created for {transcript.video_id}, now saving to file..."
                                )

                                # Process diarized transcript through the same file saving logic
                                if output_dir and not dry_run:
                                    # Use the same file saving logic as regular transcripts
                                    try:
                                        # Create sanitized filename
                                        safe_title = re.sub(
                                            r"[<>:\"/\\|?*]", "", transcript.title
                                        ).strip()
                                        safe_title = safe_title.replace("-", " ")
                                        safe_title = re.sub(r"\s+", " ", safe_title)

                                        if (
                                            safe_title
                                            and len(safe_title) > 0
                                            and not safe_title.startswith(
                                                "YouTube-Video"
                                            )
                                        ):
                                            filename = f"{safe_title}.{output_format}"
                                        else:
                                            video_id = (
                                                transcript.video_id or "unknown_video"
                                            )
                                            video_id = re.sub(r"[^\w-]", "", video_id)
                                            filename = (
                                                f"{video_id}_transcript.{output_format}"
                                            )

                                        filepath = output_dir / filename

                                        # Check if file already exists
                                        if filepath.exists() and not overwrite_existing:
                                            logger.info(
                                                f"⏭️ Skipping existing diarized transcript: {filepath}"
                                            )
                                            skipped_files.append(str(filepath))
                                            transcripts.append(transcript)
                                        else:
                                            # Generate content and save file
                                            vault_path_obj = (
                                                Path(vault_path) if vault_path else None
                                            )
                                            interjections_file_obj = (
                                                Path(interjections_file)
                                                if interjections_file
                                                else None
                                            )

                                            if output_format == "md":
                                                # For diarized transcripts, use the proper formatting function
                                                if (
                                                    hasattr(
                                                        transcript, "transcript_data"
                                                    )
                                                    and transcript.transcript_data
                                                ):
                                                    # Check if this is a diarized transcript by looking for speaker data
                                                    has_speakers = any(
                                                        segment.get("speaker")
                                                        for segment in transcript.transcript_data
                                                    )

                                                    if has_speakers:
                                                        # Use the proper diarization formatting
                                                        from ..commands.transcribe import (
                                                            format_transcript_content,
                                                        )

                                                        # Convert transcript data to the format expected by format_transcript_content
                                                        transcript_segments = []
                                                        for (
                                                            segment
                                                        ) in transcript.transcript_data:
                                                            segment_copy = dict(segment)
                                                            # Convert duration back to end time
                                                            if (
                                                                "duration"
                                                                in segment_copy
                                                            ):
                                                                segment_copy["end"] = (
                                                                    segment_copy[
                                                                        "start"
                                                                    ]
                                                                    + segment_copy[
                                                                        "duration"
                                                                    ]
                                                                )
                                                                del segment_copy[
                                                                    "duration"
                                                                ]
                                                            transcript_segments.append(
                                                                segment_copy
                                                            )

                                                        transcript_format_data = {
                                                            "segments": transcript_segments
                                                        }

                                                        content = format_transcript_content(
                                                            transcript_data=transcript_format_data,
                                                            source_name=transcript.title
                                                            or "YouTube Video",
                                                            model="diarized",  # Indicate this is diarized
                                                            device="gpu",  # Default for diarization
                                                            format="md",
                                                            video_id=transcript.video_id,
                                                            timestamps=include_timestamps,
                                                        )
                                                    else:
                                                        # Use regular markdown formatting for non-diarized
                                                        content = transcript.to_markdown(
                                                            include_timestamps=include_timestamps,
                                                            include_analysis=include_analysis,
                                                            vault_path=vault_path_obj,
                                                            output_dir=output_dir,
                                                            strip_interjections=strip_interjections,
                                                            interjections_file=interjections_file_obj,
                                                        )
                                                else:
                                                    # Fallback to regular markdown formatting
                                                    content = transcript.to_markdown(
                                                        include_timestamps=include_timestamps,
                                                        include_analysis=include_analysis,
                                                        vault_path=vault_path_obj,
                                                        output_dir=output_dir,
                                                        strip_interjections=strip_interjections,
                                                        interjections_file=interjections_file_obj,
                                                    )
                                            elif output_format == "srt":
                                                content = transcript.to_srt(
                                                    strip_interjections=strip_interjections,
                                                    interjections_file=interjections_file_obj,
                                                )
                                            else:
                                                content = transcript.transcript_text

                                            # Write file
                                            with open(
                                                filepath, "w", encoding="utf-8"
                                            ) as f:
                                                f.write(content)

                                            if filepath.exists():
                                                saved_files.append(str(filepath))
                                                transcripts.append(transcript)
                                                logger.info(
                                                    f"✅ Saved diarized transcript: {filepath}"
                                                )

                                                # Save diarized transcript to database
                                                db_service = kwargs.get("db_service")
                                                if not db_service:
                                                    try:
                                                        from ..database.service import (
                                                            DatabaseService,
                                                        )

                                                        db_service = DatabaseService()
                                                    except Exception as e:
                                                        logger.debug(
                                                            f"Could not create database service: {e}"
                                                        )

                                                if db_service and transcript:
                                                    try:
                                                        # Create/update media source record
                                                        video_metadata = {
                                                            "uploader": transcript.uploader
                                                            or "",
                                                            "upload_date": transcript.upload_date,
                                                            "description": transcript.description
                                                            or "",
                                                            "duration_seconds": transcript.duration,
                                                            "view_count": transcript.view_count,
                                                            "thumbnail_url": transcript.thumbnail_url,
                                                            "tags_json": transcript.tags
                                                            or [],
                                                            "source_type": "youtube",
                                                        }

                                                        video_record = db_service.create_video(
                                                            video_id=transcript.video_id,
                                                            title=transcript.title,
                                                            url=transcript.url,
                                                            **video_metadata,
                                                        )

                                                        if video_record:
                                                            logger.info(
                                                                f"Saved/updated video record: {transcript.video_id}"
                                                            )

                                                        # Create/update transcript record with diarization data
                                                        transcript_segments = (
                                                            transcript.transcript_data
                                                            or []
                                                        )
                                                        diarization_segments = (
                                                            transcript_segments
                                                            if any(
                                                                seg.get("speaker")
                                                                for seg in transcript_segments
                                                            )
                                                            else None
                                                        )

                                                        transcript_record = db_service.create_transcript(
                                                            video_id=transcript.video_id,
                                                            language=transcript.language,
                                                            is_manual=transcript.is_manual,
                                                            transcript_text=transcript.transcript_text,
                                                            transcript_segments=transcript_segments,
                                                            transcript_type="diarized",
                                                            diarization_enabled=True,
                                                            diarization_segments_json=diarization_segments,
                                                            include_timestamps=include_timestamps,
                                                        )

                                                        if transcript_record:
                                                            logger.info(
                                                                f"Saved/updated diarized transcript record: {transcript_record.transcript_id}"
                                                            )

                                                    except Exception as e:
                                                        logger.error(
                                                            f"Error saving diarized transcript to database: {e}"
                                                        )
                                                        # Don't fail the transcript extraction if database save fails
                                            else:
                                                logger.error(
                                                    f"❌ Diarized transcript file not created: {filepath}"
                                                )
                                                errors.append(
                                                    f"Failed to create diarized transcript file: {filepath}"
                                                )

                                    except Exception as diarization_save_error:
                                        logger.error(
                                            f"❌ Failed to save diarized transcript: {diarization_save_error}"
                                        )
                                        errors.append(
                                            f"Diarized transcript save failed: {diarization_save_error}"
                                        )
                                else:
                                    # No file saving (dry run or no output_dir)
                                    transcripts.append(transcript)
                            else:
                                logger.warning(
                                    f"Diarization-only processing failed for {url} after transcript miss"
                                )
                                errors.append(
                                    f"Diarization failed after transcript miss for {url}"
                                )
                        else:
                            logger.warning(f"No transcript returned for {url}")
                            errors.append(f"No transcript available for {url}")
                except CancellationError:
                    logger.info("Transcript extraction cancelled by user")
                    break
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Error processing {url}: {error_msg}")

                    # Categorize the error for better user feedback
                    if (
                        "407 Proxy Authentication Required" in error_msg
                        or "Proxy authentication failed" in error_msg
                    ):
                        errors.append(
                            f"🔐 Proxy authentication failed for {url}: Please check your WebShare Username and Password in Settings"
                        )
                    elif "402 Payment Required" in error_msg:
                        errors.append(
                            f"💰 WebShare account payment required for {url}: Your WebShare proxy account is out of funds. Please add payment at https://panel.webshare.io/ to continue using YouTube extraction"
                        )
                    elif (
                        "Proxy connection failed" in error_msg
                        or "Tunnel connection failed" in error_msg
                    ):
                        errors.append(
                            f"🌐 Proxy connection failed for {url}: WebShare proxy may be unavailable or blocked"
                        )
                    elif "Sign in to confirm you're not a bot" in error_msg:
                        errors.append(
                            f"🔐 Authentication required for {url}: YouTube is requiring sign-in verification"
                        )
                    elif "live stream recording is not available" in error_msg:
                        errors.append(
                            f"❌ Video unavailable: {url} appears to be a live stream recording that is no longer available"
                        )
                    elif (
                        "Video unavailable" in error_msg
                        or "This video is not available" in error_msg
                    ):
                        errors.append(
                            f"❌ Video unavailable: {url} - video may be private, deleted, or region-restricted"
                        )
                    else:
                        errors.append(f"❌ Error processing {url}: {error_msg}")

            # Return results - BUGFIX: Success should mean files were saved, not just transcripts extracted
            # If cancellation happens during file writing, that should be reported as partial success/failure
            transcripts_extracted = len(transcripts) > 0
            files_actually_saved = len(saved_files) > 0
            files_skipped = len(skipped_files) > 0

            # Enhanced success logic: Success requires both file AND database operations to succeed
            # Based on memory requirement: "Every cloud transcription and every local transcription
            # must always write the results to the sqlite database"
            # 1. Files were actually saved (new transcripts created) AND database saves succeeded
            # 2. Files were skipped (existing files, overwrite disabled) - database not affected
            # 3. Videos were skipped via index (optimization, already exist) - database not affected
            # 4. Transcripts extracted successfully (when no output_dir specified) AND database saves succeeded

            success = (
                (
                    files_actually_saved and not database_save_failed
                )  # New files saved AND db success
                or files_skipped  # Files skipped (already exist) - database not affected
                or (  # Skipped via index optimization - database not affected
                    skipped_via_index > 0 and not overwrite_existing
                )
                or (  # Transcripts extracted (no file output) AND db success
                    transcripts_extracted
                    and not output_dir
                    and not database_save_failed
                )
            )

            # Add error messages for specific failure cases
            if not success and output_dir and len(transcripts) > 0:
                if cancellation_token and cancellation_token.is_cancelled():
                    errors = errors or []
                    errors.append(
                        f"Processing was cancelled after extracting {len(transcripts)} transcript(s)"
                    )
                else:
                    errors = errors or []
                    if database_save_failed:
                        errors.append(
                            f"Extracted {len(transcripts)} transcript(s) and saved {len(saved_files)} files, but database save failed"
                        )
                    else:
                        errors.append(
                            f"Extracted {len(transcripts)} transcript(s) but failed to save files"
                        )

            # Enhanced logging to clarify success vs failure
            logger.info(
                f"🔧 SUCCESS LOGIC: files_saved={files_actually_saved}, files_skipped={files_skipped}, skipped_via_index={skipped_via_index}, overwrite={overwrite_existing}, database_save_failed={database_save_failed}"
            )
            if success and skipped_via_index > 0 and len(transcripts) == 0:
                logger.info(
                    f"✅ Transcript processing completed successfully. All {skipped_via_index} video(s) already existed and were skipped."
                )
            else:
                logger.info(
                    f"Transcript processing completed. Success: {success}, Transcripts extracted: {len(transcripts)}, Files saved: {len(saved_files)}, Files skipped: {len(skipped_files)}, Database save failed: {database_save_failed}"
                )

            # Report index optimization statistics if applicable
            if not overwrite_existing and skipped_via_index > 0:
                logger.info(
                    f"🚀 Performance optimization: Skipped {skipped_via_index} videos via index lookup (no API calls needed)"
                )
                time_saved = skipped_via_index * 3  # Estimate ~3 seconds per video
                logger.info(
                    f"⏱️  Estimated time saved: ~{time_saved} seconds ({time_saved/60:.1f} minutes)"
                )

            # Clean up session index file
            if index_file and index_file.exists():
                try:
                    index_file.unlink()
                    logger.debug(
                        f"🗑️  Cleaned up session index file: {index_file.name}"
                    )
                except Exception as e:
                    logger.debug(f"Could not delete index file: {e}")

            return ProcessorResult(
                success=success,
                data={
                    "transcripts": [t.to_dict() for t in transcripts],
                    "saved_files": saved_files,
                    "skipped_files": skipped_files,
                    "output_format": output_format,
                    "output_directory": str(output_dir),
                    "skipped_via_index": (
                        skipped_via_index if not overwrite_existing else 0
                    ),
                },
                errors=errors if errors else None,
                metadata={
                    "processor": self.name,
                    "urls_processed": len(urls),
                    "transcripts_extracted": len(transcripts),
                    "files_saved": len(saved_files),
                    "files_skipped": len(skipped_files),
                    "skipped_via_index": (
                        skipped_via_index if not overwrite_existing else 0
                    ),
                    "overwrite_enabled": overwrite_existing,
                    "prefer_manual": self.prefer_manual,
                    "fallback_to_auto": self.fallback_to_auto,
                    "cancelled": (
                        cancellation_token.is_cancelled if cancellation_token else False
                    ),
                },
            )

        except CancellationError:
            logger.info("YouTube transcript processing cancelled")

            # Clean up session index file
            if "index_file" in locals() and index_file and index_file.exists():
                try:
                    index_file.unlink()
                    logger.debug(
                        f"🗑️  Cleaned up session index file after cancellation: {index_file.name}"
                    )
                except Exception as e:
                    logger.debug(f"Could not delete index file: {e}")

            return ProcessorResult(
                success=False,
                errors=["Processing cancelled by user"],
                metadata={
                    "processor": self.name,
                    "cancelled": True,
                },
            )
        except Exception as e:
            logger.error(f"Unexpected error in YouTube transcript processing: {e}")

            # Clean up session index file
            if "index_file" in locals() and index_file and index_file.exists():
                try:
                    index_file.unlink()
                    logger.debug(
                        f"🗑️  Cleaned up session index file after error: {index_file.name}"
                    )
                except Exception as e_cleanup:
                    logger.debug(f"Could not delete index file: {e_cleanup}")

            return ProcessorResult(
                success=False,
                errors=[f"Unexpected error: {e}"],
                metadata={
                    "processor": self.name,
                    "error": str(e),
                },
            )


def extract_youtube_transcript(
    url: str,
    preferred_language: str = "en",
    prefer_manual: bool = True,
    fallback_to_auto: bool = True,
) -> YouTubeTranscript | None:
    """
    Standalone function to extract a single YouTube transcript
    Standalone function to extract a single YouTube transcript.

    Args:
        url: YouTube video URL
        preferred_language: Preferred transcript language
        prefer_manual: Whether to prefer manual transcripts over automatic
        fallback_to_auto: Whether to fall back to automatic captions

    Returns:
        YouTubeTranscript object or None if extraction failed
    """
    processor = YouTubeTranscriptProcessor(
        preferred_language=preferred_language,
        prefer_manual=prefer_manual,
        fallback_to_auto=fallback_to_auto,
    )

    result = processor.process(url)

    if result.success and result.data and result.data.get("transcripts"):
        # Return the first transcript
        transcript_dict = result.data["transcripts"][0]
        return YouTubeTranscript(**transcript_dict)

    return None
