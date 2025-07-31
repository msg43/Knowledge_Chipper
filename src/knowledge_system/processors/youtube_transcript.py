"""
YouTube Transcript Processor

Extracts transcripts from YouTube videos using Webshare rotating residential proxies.
Simplified version that only uses the proxy-based YouTube Transcript API.
"""

import json
import os  # Added for os.access
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from ..errors import YouTubeAPIError
from ..logger import get_logger
from ..utils.cancellation import CancellationError, CancellationToken
from ..utils.text_utils import strip_bracketed_content
from ..utils.youtube_utils import extract_urls, is_youtube_url
from .base import BaseProcessor, ProcessorResult

logger = get_logger(__name__)

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api.proxies import WebshareProxyConfig

    logger.debug("Successfully imported YouTubeTranscriptApi and WebshareProxyConfig")
except ImportError as e:
    logger.error(f"Failed to import youtube_transcript_api: {e}")
    YouTubeTranscriptApi = None
    WebshareProxyConfig = None
except Exception as e:
    logger.error(f"Unexpected error importing YouTubeTranscriptApi: {e}")
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
    duration: int | None = Field(
        default=None, description="Video duration in seconds"
    )
    uploader: str = Field(default="", description="Channel name")
    upload_date: str | None = Field(
        default=None, description="Upload date (YYYYMMDD)"
    )
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

        # Add tags if available (limit to first 10 to keep YAML manageable)
        if self.tags:
            tags_subset = self.tags[:10]
            # Format tags as a YAML array, escaping quotes in tag names
            safe_tags = [tag.replace('"', '\\"') for tag in tags_subset]
            tags_yaml = "[" + ", ".join(f'"{tag}"' for tag in safe_tags) + "]"
            lines.append(f"tags: {tags_yaml}")
            if len(self.tags) > 10:
                lines.append(f"# ... and {len(self.tags) - 10} more tags")

        # Add transcript processing metadata
        lines.append(f'model: "YouTube Transcript"')
        lines.append(f'device: "Web API"')

        # Add extraction timestamp
        lines.append(f'fetched: "{self.fetched_at.strftime("%Y-%m-%d %H:%M:%S")}"')

        lines.append("---")
        lines.append("")

        # Create sanitized title for thumbnail reference
        safe_title_for_filename = re.sub(r"[^\w\s-]", "", self.title).strip()
        safe_title_for_filename = re.sub(r"[-\s]+", "-", safe_title_for_filename)

        # Add thumbnail reference for YouTube videos using sanitized title
        if safe_title_for_filename:
            lines.append(
                f"![Video Thumbnail](Thumbnails/{safe_title_for_filename}-Thumbnail.jpg)"
            )
        else:
            lines.append(
                f"![Video Thumbnail](Thumbnails/{self.video_id}-Thumbnail.jpg)"
            )
        lines.append("")

        # Add Full Transcript section
        lines.append("## Full Transcript")
        lines.append("")

        # Format transcript with timestamps if available
        if self.transcript_data and include_timestamps:
            for segment in self.transcript_data:
                start_time = segment.get("start", 0)
                text = segment.get("text", "").strip()
                if text:
                    # Remove bracketed content like [music], [applause], etc.
                    text = strip_bracketed_content(text)
                    # Only add the segment if there's still text after bracket removal
                    if text.strip():
                        minutes = int(start_time // 60)
                        seconds = int(start_time % 60)
                        timestamp = f"{minutes:02d}:{seconds:02d}"
                        lines.append(f"**{timestamp}** {text}")
                        lines.append("")
        else:
            # Plain text transcript - also remove bracketed content
            transcript_text = strip_bracketed_content(self.transcript_text)
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
    """
    Processor for extracting YouTube transcripts using Webshare rotating proxies.

    Simplified processor that only uses the proxy-based YouTube Transcript API.
    No fallback methods - requires working Webshare credentials.
    """

    def __init__(
        self,
        preferred_language: str = "en",
        prefer_manual: bool = True,
        fallback_to_auto: bool = True,
        **kwargs,
    ) -> None:
        """Initialize the YouTube transcript processor."""
        super().__init__("youtube_transcript")
        self.preferred_language = preferred_language
        self.prefer_manual = prefer_manual
        self.fallback_to_auto = fallback_to_auto

        if YouTubeTranscriptApi is None or WebshareProxyConfig is None:
            raise ImportError(
                "youtube-transcript-api is required for transcript extraction. "
                "Install it with: pip install youtube-transcript-api"
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
        """Validate WebShare proxy configuration."""
        from ..config import get_settings

        settings = get_settings()
        issues = []

        if not settings.api_keys.webshare_username:
            issues.append("WebShare Username not configured")
        if not settings.api_keys.webshare_password:
            issues.append("WebShare Password not configured")

        return issues

    def _fetch_video_transcript(
        self, url: str, cancellation_token: CancellationToken | None = None
    ) -> YouTubeTranscript | None:
        """Fetch transcript for a single video using proxy-based YouTube Transcript API."""

        logger.info(f"Fetching transcript for: {url}")

        if YouTubeTranscriptApi is None:
            logger.error("youtube-transcript-api is not available")
            return None

        try:
            # Check for cancellation at the start
            if cancellation_token and cancellation_token.is_cancelled():
                raise CancellationError("Transcript fetch cancelled")

            from ..config import get_settings

            # Get Webshare credentials from settings
            settings = get_settings()
            username = settings.api_keys.webshare_username
            password = settings.api_keys.webshare_password

            if not username or not password:
                logger.error(
                    "Webshare credentials not found. Please configure WebShare Username and Password in Settings."
                )
                return None

            # Extract video ID from URL
            video_id = self._extract_video_id(url)
            if not video_id:
                return None

            # Configure YouTube Transcript API with WebShare proxy
            logger.info("Using Webshare rotating proxy for transcript extraction")

            # Set up WebShare proxy configuration
            proxy_config = WebshareProxyConfig(
                proxy_username=username, proxy_password=password, retries_when_blocked=3
            )

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
                        f"Successfully fetched metadata: {real_metadata.get('title', 'Unknown')}"
                    )
            except Exception as e:
                logger.warning(f"Could not fetch metadata for {video_id}: {e}")

            # Try transcript extraction with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Check for cancellation before each attempt
                    if cancellation_token and cancellation_token.is_cancelled():
                        raise CancellationError(
                            "Transcript fetch cancelled during retry"
                        )

                    # Add configurable delay to avoid rate limiting
                    delay_config = settings.youtube_processing

                    # Check if we should skip delays when using proxies
                    has_proxy = (
                        settings.api_keys.webshare_username
                        and settings.api_keys.webshare_password
                    )

                    if delay_config.disable_delays_with_proxy and has_proxy:
                        logger.debug(
                            "Skipping transcript delay - using rotating proxies"
                        )
                    else:
                        delay = random.uniform(
                            delay_config.transcript_delay_min,
                            delay_config.transcript_delay_max,
                        )
                        logger.info(f"Applying transcript delay: {delay:.1f}s")

                        # Check cancellation during delay
                        if cancellation_token:
                            elapsed = 0
                            check_interval = 0.1
                            while elapsed < delay:
                                if cancellation_token.is_cancelled():
                                    raise CancellationError(
                                        "Transcript fetch cancelled during delay"
                                    )
                                time.sleep(min(check_interval, delay - elapsed))
                                elapsed += check_interval
                        else:
                            time.sleep(delay)

                    # Get list of available transcripts with proxy
                    logger.debug(
                        f"Attempting to get transcripts for video_id: {video_id}"
                    )
                    logger.debug(
                        f"YouTubeTranscriptApi type: {type(YouTubeTranscriptApi)}"
                    )
                    logger.debug(
                        f"YouTubeTranscriptApi is None: {YouTubeTranscriptApi is None}"
                    )

                    # Double-check the API is available
                    if YouTubeTranscriptApi is None:
                        raise ImportError("YouTubeTranscriptApi is not available")

                    logger.debug(
                        "Creating YouTubeTranscriptApi instance with WebShare proxy..."
                    )
                    api = YouTubeTranscriptApi(proxy_config=proxy_config)
                    transcript_list = api.list(video_id)

                    # Check for cancellation after transcript list fetch
                    if cancellation_token and cancellation_token.is_cancelled():
                        raise CancellationError(
                            "Transcript fetch cancelled after getting transcript list"
                        )

                    # Try to find preferred transcript
                    transcript = None
                    is_manual = False

                    # First try manual transcripts
                    if self.prefer_manual:
                        try:
                            # Try preferred language first
                            transcript = (
                                transcript_list.find_manually_created_transcript(
                                    [self.preferred_language]
                                )
                            )
                            is_manual = True
                            logger.info(
                                f"Found manual transcript in {self.preferred_language}"
                            )
                        except:
                            try:
                                # Try English as fallback
                                transcript = (
                                    transcript_list.find_manually_created_transcript(
                                        ["en"]
                                    )
                                )
                                is_manual = True
                                logger.info("Found manual transcript in English")
                            except:
                                # Try any manual transcript
                                try:
                                    for t in transcript_list:
                                        # Use getattr to safely check for attribute
                                        if getattr(t, "is_manually_created", False):
                                            transcript = t
                                            is_manual = True
                                            logger.info(
                                                f"Found manual transcript in {getattr(t, 'language_code', 'unknown')}"
                                            )
                                            break
                                except:
                                    pass

                    # Then try automatic captions if no manual found and allowed
                    if not transcript and self.fallback_to_auto:
                        try:
                            # Try preferred language first
                            transcript = transcript_list.find_generated_transcript(
                                [self.preferred_language]
                            )
                            is_manual = False
                            logger.info(
                                f"Found automatic transcript in {self.preferred_language}"
                            )
                        except:
                            try:
                                # Try English as fallback
                                transcript = transcript_list.find_generated_transcript(
                                    ["en"]
                                )
                                is_manual = False
                                logger.info("Found automatic transcript in English")
                            except:
                                # Try any automatic transcript
                                try:
                                    for t in transcript_list:
                                        # Use getattr to safely check for attribute
                                        if not getattr(t, "is_manually_created", True):
                                            transcript = t
                                            is_manual = False
                                            logger.info(
                                                f"Found automatic transcript in {getattr(t, 'language_code', 'unknown')}"
                                            )
                                            break
                                except:
                                    pass

                    if not transcript:
                        logger.warning(
                            f"No suitable transcript found for video {video_id}"
                        )
                        return None

                    # Check for cancellation before fetching transcript content
                    if cancellation_token and cancellation_token.is_cancelled():
                        raise CancellationError(
                            "Transcript fetch cancelled before content download"
                        )

                    # Fetch the transcript content
                    transcript_data = transcript.fetch()

                    if not transcript_data:
                        logger.warning(f"Empty transcript data for video {video_id}")
                        return None

                    # Convert to our format - handle different transcript data formats safely
                    transcript_text_parts = []
                    formatted_transcript_data = []

                    for i, entry in enumerate(transcript_data):
                        # Handle both dict and object formats
                        if isinstance(entry, dict):
                            # Dict format
                            text = entry.get("text", "")
                            start = entry.get("start", 0)
                            duration = entry.get("duration", 0)
                        elif hasattr(entry, "text"):
                            # Object format
                            text = getattr(entry, "text", "")
                            start = getattr(entry, "start", 0)
                            duration = getattr(entry, "duration", 0)
                        else:
                            # String format or unknown - skip
                            continue

                        if text:
                            transcript_text_parts.append(text)
                            formatted_transcript_data.append(
                                {
                                    "start": start,
                                    "end": start + duration,
                                    "text": text,
                                    "duration": duration,
                                }
                            )

                    transcript_text = " ".join(transcript_text_parts)

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
                        title = f"YouTube Video {video_id}"
                        uploader = ""
                        duration = None
                        upload_date = None
                        description = ""
                        view_count = None
                        tags = []
                        thumbnail_url = None

                    # Create transcript object
                    result = YouTubeTranscript(
                        video_id=video_id,
                        title=title,
                        url=url,
                        language=getattr(transcript, "language_code", "unknown"),
                        is_manual=is_manual,
                        transcript_text=transcript_text,
                        transcript_data=formatted_transcript_data,
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

                    # Check for specific proxy authentication errors
                    if (
                        "407 Proxy Authentication Required" in error_msg
                        or "ProxyError" in error_msg
                    ):
                        logger.error(
                            f"Proxy authentication failed for video {video_id}. Please check your WebShare credentials."
                        )
                        break
                    elif "402 Payment Required" in error_msg:
                        logger.error(
                            f"💰 WebShare account requires payment for video {video_id}. Please add funds to your WebShare account at https://panel.webshare.io/"
                        )
                        # Return None for payment error instead of creating invalid transcript
                        return None
                    elif "Tunnel connection failed" in error_msg:
                        logger.error(
                            f"Proxy connection failed for video {video_id}. WebShare proxy may be unavailable."
                        )
                        break

                    if attempt < max_retries - 1:
                        wait_time = random.uniform(2, 5)
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
        output_dir: str | Path | None = None,
        output_format: str | None = None,
        vault_path: str | Path | None = None,
        include_timestamps: bool = True,
        include_analysis: bool = True,
        strip_interjections: bool = False,
        interjections_file: str | Path | None = None,
        cancellation_token: CancellationToken | None = None,
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

            # Build video ID index if overwrite is disabled
            existing_video_ids = set()
            index_file = None
            skipped_via_index = 0

            if not overwrite_existing:
                # Create session-specific index file
                from datetime import datetime

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
                        transcripts.append(transcript)

                        # IMMEDIATE FILE WRITING: Write file right after extraction instead of batching
                        try:
                            logger.info(
                                f"Immediately saving transcript for {transcript.video_id}"
                            )

                            # Create sanitized filename from title with improved error handling
                            safe_title = re.sub(
                                r"[^\w\s-]", "", transcript.title
                            ).strip()
                            safe_title = re.sub(r"[-\s]+", "-", safe_title)

                            # Additional filename safety checks for macOS
                            if safe_title:
                                # Remove leading/trailing hyphens
                                safe_title = safe_title.strip("-")
                                # Limit length to avoid filesystem issues
                                if len(safe_title) > 100:
                                    safe_title = safe_title[:100].rstrip("-")

                            logger.debug(
                                f"Sanitized title: '{safe_title}' (length: {len(safe_title) if safe_title else 0})"
                            )

                            # Determine filename with robust fallback logic
                            if (
                                safe_title
                                and len(safe_title) > 0
                                and not safe_title.startswith("YouTube-Video")
                                and not transcript.title.startswith("YouTube Video ")
                            ):
                                filename = f"{safe_title}.{output_format}"
                                thumbnail_filename = f"{safe_title}-Thumbnail.jpg"
                                logger.debug(
                                    f"Using title-based filename: '{filename}'"
                                )
                            else:
                                # Fallback to video ID - ensure it's valid
                                video_id = transcript.video_id or "unknown_video"
                                # Sanitize video ID as well (though it should be safe)
                                video_id = re.sub(r"[^\w-]", "", video_id)
                                filename = f"{video_id}_transcript.{output_format}"
                                thumbnail_filename = f"{video_id}-Thumbnail.jpg"
                                logger.debug(
                                    f"Using video_id-based filename: '{filename}' (video_id: '{video_id}')"
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
                            vault_path_obj = Path(vault_path) if vault_path else None
                            interjections_file_obj = (
                                Path(interjections_file) if interjections_file else None
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
                                errors.append(f"Permission denied: {filepath} - {e}")
                                continue
                            except OSError as e:
                                logger.error(f"❌ OS error writing to {filepath}: {e}")
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
                                    from ..utils.youtube_utils import download_thumbnail

                                    # Pass thumbnails_dir directly since download_thumbnail now saves to exact directory provided
                                    thumbnail_result = download_thumbnail(
                                        transcript.url,
                                        thumbnails_dir,
                                        use_cookies=False,
                                    )
                                    if thumbnail_result:
                                        downloaded_path = Path(thumbnail_result)

                                        # Check if we need to rename to match expected filename pattern
                                        if downloaded_path.exists():
                                            # The download function saves as {video_id}_thumbnail.jpg
                                            # But our markdown expects {safe_title}-Thumbnail.jpg
                                            expected_path = (
                                                thumbnails_dir / thumbnail_filename
                                            )

                                            if downloaded_path != expected_path:
                                                # Move/rename to expected location for consistent naming
                                                try:
                                                    downloaded_path.rename(
                                                        expected_path
                                                    )
                                                    logger.info(
                                                        f"Thumbnail renamed to match title: {expected_path}"
                                                    )
                                                except Exception as rename_error:
                                                    logger.warning(
                                                        f"Failed to rename thumbnail from {downloaded_path} to {expected_path}: {rename_error}"
                                                    )
                                                    # Keep the original if rename fails
                                                    logger.info(
                                                        f"Thumbnail kept at: {downloaded_path}"
                                                    )
                                            else:
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

            # Simplified success logic: ANY of these counts as success
            # 1. Files were actually saved (new transcripts created)
            # 2. Files were skipped (existing files, overwrite disabled)
            # 3. Videos were skipped via index (optimization, already exist)
            # 4. Transcripts extracted successfully (when no output_dir specified)

            success = (
                files_actually_saved
                or files_skipped  # New files saved
                or (  # Files skipped (already exist)
                    skipped_via_index > 0 and not overwrite_existing
                )
                or (  # Skipped via index optimization
                    transcripts_extracted and not output_dir
                )  # Transcripts extracted (no file output)
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
                    errors.append(
                        f"Extracted {len(transcripts)} transcript(s) but failed to save files"
                    )

            # Enhanced logging to clarify success vs failure
            logger.info(
                f"🔧 NEW CODE: Success determination: files_saved={files_actually_saved}, files_skipped={files_skipped}, skipped_via_index={skipped_via_index}, overwrite={overwrite_existing}"
            )
            if success and skipped_via_index > 0 and len(transcripts) == 0:
                logger.info(
                    f"✅ Transcript processing completed successfully. All {skipped_via_index} video(s) already existed and were skipped."
                )
            else:
                logger.info(
                    f"Transcript processing completed. Success: {success}, Transcripts extracted: {len(transcripts)}, Files saved: {len(saved_files)}, Files skipped: {len(skipped_files)}"
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
                    "skipped_via_index": skipped_via_index
                    if not overwrite_existing
                    else 0,
                },
                errors=errors if errors else None,
                metadata={
                    "processor": self.name,
                    "urls_processed": len(urls),
                    "transcripts_extracted": len(transcripts),
                    "files_saved": len(saved_files),
                    "files_skipped": len(skipped_files),
                    "skipped_via_index": skipped_via_index
                    if not overwrite_existing
                    else 0,
                    "overwrite_enabled": overwrite_existing,
                    "prefer_manual": self.prefer_manual,
                    "fallback_to_auto": self.fallback_to_auto,
                    "cancelled": cancellation_token.is_cancelled
                    if cancellation_token
                    else False,
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
