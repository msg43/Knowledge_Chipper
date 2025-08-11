"""
Simplified YouTube Metadata Processor
Simplified YouTube Metadata Processor

Uses only WebShare rotating proxies with YT-DLP. Eliminates complex fallback strategies,
manual proxy rotation, and elaborate retry logic since WebShare handles rotation automatically.
"""

import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import yt_dlp  # type: ignore[import-untyped]
except ImportError:
    yt_dlp = None

from pydantic import BaseModel, Field

from ..config import get_settings
from ..errors import YouTubeAPIError
from ..logger import get_logger
from ..utils.youtube_utils import extract_urls, is_youtube_url
from .base import BaseProcessor, ProcessorResult

logger = get_logger(__name__)


class YouTubeMetadata(BaseModel):
    """ YouTube video metadata model."""

    # Core identifiers
    video_id: str = Field(..., description="YouTube video ID")
    title: str = Field(..., description="Video title")
    url: str = Field(..., description="Full YouTube URL")

    # Content details
    description: str = Field(default="", description="Video description")
    duration: int | None = Field(default=None, description="Duration in seconds")
    view_count: int | None = Field(default=None, description="View count")
    like_count: int | None = Field(default=None, description="Like count")
    comment_count: int | None = Field(default=None, description="Comment count")

    # Creator information
    uploader: str = Field(default="", description="Channel name")
    uploader_id: str = Field(default="", description="Channel ID")
    upload_date: str | None = Field(default=None, description="Upload date (YYYYMMDD)")

    # Additional metadata
    tags: list[str] = Field(default_factory=list, description="Video tags")
    categories: list[str] = Field(default_factory=list, description="Video categories")
    thumbnail_url: str | None = Field(default=None, description="Thumbnail URL")
    caption_availability: bool | None = Field(
        default=None, description="Whether captions are available"
    )
    privacy_status: str | None = Field(default=None, description="Privacy status")

    # Extraction metadata
    extraction_method: str = Field(
        default="yt-dlp", description="Method used to extract metadata"
    )
    fetched_at: datetime = Field(
        default_factory=datetime.now, description="When metadata was fetched"
    )

    def to_dict(self) -> dict[str, Any]:
        """ Convert to dictionary."""
        return self.model_dump()

    def to_markdown_metadata(self) -> str:
        """ Generate markdown metadata section."""
        lines = ["## Video Metadata", ""]

        lines.append(f"- **Title**: {self.title}")
        lines.append(f"- **Channel**: {self.uploader}")
        lines.append(f"- **Video ID**: {self.video_id}")
        lines.append(f"- **URL**: {self.url}")

        if self.upload_date:
            # Convert YYYYMMDD to readable format
            try:
                date_obj = datetime.strptime(self.upload_date, "%Y%m%d")
                lines.append(f"- **Upload Date**: {date_obj.strftime('%B %d, %Y')}")
            except ValueError:
                lines.append(f"- **Upload Date**: {self.upload_date}")

        if self.duration:
            minutes = self.duration // 60
            seconds = self.duration % 60
            lines.append(f"- **Duration**: {minutes}:{seconds:02d}")

        if self.view_count:
            lines.append(f"- **Views**: {self.view_count:,}")

        if self.like_count:
            lines.append(f"- **Likes**: {self.like_count:,}")

        if self.comment_count:
            lines.append(f"- **Comments**: {self.comment_count:,}")

        if self.caption_availability is not None:
            lines.append(
                f"- **Captions**: {'Available' if self.caption_availability else 'Not Available'}"
            )

        # Description (truncated if too long)
        if self.description:
            desc = self.description.strip()
            if len(desc) > 500:
                desc = desc[:500] + "..."
            lines.append(f"- **Description**: {desc}")

        # Tags
        if self.tags:
            lines.append(f"- **Tags**: {', '.join(self.tags[:10])}")
            if len(self.tags) > 10:
                lines.append(f"  _(and {len(self.tags) - 10} more)_")

        lines.append(
            f"- **Extracted**: {self.fetched_at.strftime('%Y-%m-%d %H:%M:%S')}"
        )

        return "\n".join(lines)


class YouTubeMetadataProcessor(BaseProcessor):
    """ Simplified processor for extracting YouTube video metadata using YT-DLP with WebShare proxies."""

    def __init__(self, name: str | None = None) -> None:
        """ Initialize the YouTube metadata processor."""
        super().__init__(name or "youtube_metadata")

        if yt_dlp is None:
            raise YouTubeAPIError(
                "yt-dlp is required for YouTube metadata extraction. "
                "Please install it with: pip install yt-dlp"
            )

        self.settings = get_settings()

        # Simple YT-DLP configuration - WebShare handles rotation automatically
        self.ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "ignoreerrors": True,
            "skip_download": True,  # Metadata only
            "socket_timeout": 30,
            "retries": 3,  # Reduced since WebShare handles reliability
            "extractor_retries": 2,  # Reduced since WebShare handles reliability
        }

        # Configure WebShare proxy (required)
        self._configure_webshare_proxy()

    def _configure_webshare_proxy(self):
        """ Configure WebShare rotating proxy (required for YouTube access)."""
        webshare_username = self.settings.api_keys.webshare_username
        webshare_password = self.settings.api_keys.webshare_password

        if not webshare_username or not webshare_password:
            raise YouTubeAPIError(
                "WebShare proxy credentials are required for YouTube processing. "
                "Please configure WebShare Username and Password in Settings."
            )

        # WebShare automatically rotates proxies - no manual rotation needed
        proxy_url = f"http://{webshare_username}:{webshare_password}@p.webshare.io:80/"
        self.ydl_opts["proxy"] = proxy_url
        logger.info("Configured YT-DLP with WebShare rotating proxy")

    @property
    def supported_formats(self) -> list[str]:
        """ Return list of supported input formats."""
        return [".url", ".txt"]

    def validate_input(self, input_data: Any) -> bool:
        """ Validate that the input data is suitable for processing."""
        if isinstance(input_data, (str, Path)):
            input_str = str(input_data)

            # Check if it's a URL
            if is_youtube_url(input_str):
                return True

            # Check if it's a file containing URLs
            if Path(input_str).exists():
                try:
                    with open(input_str, encoding="utf-8") as f:
                        content = f.read()
                        return any(
                            is_youtube_url(line.strip()) for line in content.split("\n")
                        )
                except (OSError, UnicodeDecodeError):
                    pass

        return False

    def _extract_video_id(self, url: str) -> str | None:
        """ Extract video ID from YouTube URL."""
        patterns = [
            r"(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]+)",
            r"youtube\.com/embed/([a-zA-Z0-9_-]+)",
            r"youtube\.com/v/([a-zA-Z0-9_-]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return None

    def _extract_metadata(self, url: str) -> YouTubeMetadata | None:
        """ Extract metadata using YT-DLP with WebShare proxy."""
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:  # type: ignore[union-attr]
                info = ydl.extract_info(url, download=False)

                if not info:
                    return None

                # Extract video ID
                video_id = info.get("id", self._extract_video_id(url) or "unknown")

                # Parse duration
                duration = info.get("duration")
                if duration and isinstance(duration, str):
                    try:
                        duration = int(float(duration))
                    except ValueError:
                        duration = None

                # Parse upload date
                upload_date = info.get("upload_date")
                if upload_date and len(upload_date) == 8:
                    # Already in YYYYMMDD format
                    pass
                elif upload_date:
                    try:
                        dt = datetime.strptime(upload_date, "%Y%m%d")
                        upload_date = dt.strftime("%Y%m%d")
                    except ValueError:
                        upload_date = None

                # Get thumbnail URL (prefer highest quality)
                thumbnail_url = info.get("thumbnail")
                if not thumbnail_url and info.get("thumbnails"):
                    thumbnails = info.get("thumbnails", [])
                    if thumbnails:
                        thumbnail_url = thumbnails[-1].get("url")

                # Parse numeric fields safely
                def safe_int(value):
                    """ Safe int."""
                    if value is None:
                        return None
                    try:
                        return int(value)
                    except (ValueError, TypeError):
                        return None

                # Check for captions
                has_captions = bool(
                    info.get("subtitles") or info.get("automatic_captions")
                )

                return YouTubeMetadata(
                    video_id=video_id,
                    title=info.get("title", ""),
                    url=url,
                    description=info.get("description", ""),
                    duration=duration,
                    view_count=safe_int(info.get("view_count")),
                    like_count=safe_int(info.get("like_count")),
                    comment_count=safe_int(info.get("comment_count")),
                    uploader=info.get("uploader", ""),
                    uploader_id=info.get("uploader_id", ""),
                    upload_date=upload_date,
                    tags=info.get("tags", []) or [],
                    categories=info.get("categories", []) or [],
                    thumbnail_url=thumbnail_url,
                    caption_availability=has_captions,
                    privacy_status=info.get("availability"),
                    extraction_method="yt-dlp+webshare",
                    fetched_at=datetime.now(),
                )

        except Exception as e:
            logger.error(f"Failed to extract metadata for {url}: {e}")
            return None

    def process(
        self, input_data: Any, dry_run: bool = False, **kwargs: Any
    ) -> ProcessorResult:
        """ Process YouTube URLs and extract metadata using YT-DLP with WebShare proxy."""
        start_time = time.time()

        try:
            # Extract URLs from input
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

            # Log playlist information if any playlists were found
            if playlist_info:
                total_playlist_videos = sum(p["total_videos"] for p in playlist_info)
                logger.info(
                    f"Found {len(playlist_info)} playlist(s) with {total_playlist_videos} total videos:"
                )
                for i, playlist in enumerate(playlist_info, 1):
                    title = playlist.get("title", "Unknown Playlist")
                    video_count = playlist.get("total_videos", 0)
                    logger.info(f"  {i}. {title} ({video_count} videos)")

            logger.info(
                f"Processing {len(urls)} YouTube URLs for metadata extraction (after playlist expansion)"
            )

            all_metadata = []
            errors = []

            for i, url in enumerate(urls, 1):
                video_id = self._extract_video_id(url)
                if not video_id:
                    error_msg = f"Invalid URL format: {url}"
                    logger.warning(error_msg)
                    errors.append(error_msg)
                    continue

                # Determine playlist context for progress display
                playlist_context = ""
                for playlist in playlist_info:
                    if playlist["start_index"] <= (i - 1) <= playlist["end_index"]:
                        playlist_position = (i - 1) - playlist["start_index"] + 1
                        playlist_context = f" [Playlist: {playlist['title'][:40]}{'...' if len(playlist['title']) > 40 else ''} - Video {playlist_position}/{playlist['total_videos']}]"
                        break

                logger.info(f"Processing {i}/{len(urls)}: {video_id}{playlist_context}")

                if dry_run:
                    logger.info(f"DRY RUN: Would extract metadata for {url}")
                    continue

                metadata = self._extract_metadata(url)
                if metadata:
                    all_metadata.append(metadata)
                    logger.info(f"✓ Successfully extracted metadata for {video_id}")
                else:
                    error_msg = f"Failed to extract metadata for {video_id}"
                    logger.error(error_msg)
                    errors.append(error_msg)

            # Log simple statistics
            success_count = len(all_metadata)
            total_count = len(urls)
            success_rate = success_count / total_count if total_count > 0 else 0

            logger.info("=" * 50)
            logger.info("METADATA EXTRACTION SUMMARY")
            logger.info("=" * 50)
            logger.info(f"Total videos: {total_count}")
            logger.info(f"Successful: {success_count}")
            logger.info(f"Failed: {len(errors)}")
            logger.info(f"Success rate: {success_rate:.1%}")
            logger.info(f"Processing time: {time.time() - start_time:.2f}s")
            logger.info("=" * 50)

            # Write failed URLs to simple log file if any
            if errors:
                self._write_simple_failure_log(errors)

            # Create output data
            output_data = {
                "metadata": [meta.to_dict() for meta in all_metadata],
                "count": len(all_metadata),
                "errors": errors,
                "success_rate": success_rate,
                "processing_time": time.time() - start_time,
            }

            # Create markdown outputs
            markdown_outputs = []
            for metadata in all_metadata:
                markdown_content = metadata.to_markdown_metadata()
                markdown_outputs.append(
                    {
                        "filename": f"{metadata.video_id}_metadata.md",
                        "content": markdown_content,
                        "metadata": metadata.to_dict(),
                    }
                )

            output_data["markdown_outputs"] = markdown_outputs

            return ProcessorResult(
                success=len(errors) == 0,
                data=output_data,
                errors=errors if errors else None,
                metadata={
                    "processor": "youtube_metadata",
                    "extraction_method": "yt-dlp+webshare",
                    "total_urls": len(urls),
                    "successful_extractions": len(all_metadata),
                    "failed_extractions": len(errors),
                    "success_rate": success_rate,
                    "processing_time": time.time() - start_time,
                },
                dry_run=dry_run,
            )

        except Exception as e:
            error_msg = str(e)
            # Check for specific payment required error
            if "402 Payment Required" in error_msg:
                payment_error = (
                    "💰 WebShare Account Payment Required: Your WebShare proxy account has run out of funds. "
                    "Please add payment to your WebShare account at https://panel.webshare.io/ to continue using YouTube processing. "
                    "This is not a bug in our application - it's a billing issue with your proxy service."
                )
                return ProcessorResult(
                    success=False,
                    errors=[payment_error],
                    metadata={
                        "processor": "youtube_metadata",
                        "error": error_msg,
                        "error_type": "payment_required",
                        "processing_time": time.time() - start_time,
                    },
                    dry_run=dry_run,
                )
            else:
                return ProcessorResult(
                    success=False,
                    errors=[f"YouTube metadata extraction failed: {error_msg}"],
                    metadata={
                        "processor": "youtube_metadata",
                        "error": error_msg,
                        "processing_time": time.time() - start_time,
                    },
                    dry_run=dry_run,
                )

    def _write_simple_failure_log(self, errors: list[str]):
        """ Write a simple failure log for debugging."""
        try:
            # Get the logs directory from settings
            from ..config import get_settings

            settings = get_settings()
            logs_dir = Path(settings.paths.logs).expanduser()
            logs_dir.mkdir(parents=True, exist_ok=True)

            # Use a single consolidated log file that appends entries
            log_file = logs_dir / "youtube_metadata_failures.log"

            # Append to existing log file instead of creating new timestamped files
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"\n{'='*70}\n")
                f.write("YouTube Metadata Extraction Failures\n")
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                f.write(f"Total failures: {len(errors)}\n")
                f.write(f"{'='*70}\n\n")

                for i, error in enumerate(errors, 1):
                    f.write(f"{i}. {error}\n")

                f.write(
                    "\nNote: All processing uses WebShare rotating proxies only.\n"
                )
                f.write(
                    "If failures persist, check proxy credentials and YouTube accessibility.\n"
                )
                f.write(f"\n{'='*70}\n")

            logger.info(f"Failure log appended to: {log_file}")

        except Exception as e:
            logger.error(f"Failed to write failure log: {e}")


# Convenience function for single video metadata extraction
def fetch_metadata(url: str) -> YouTubeMetadata:
    """ Convenience function to fetch metadata for a single video."""
    processor = YouTubeMetadataProcessor()
    result = processor.process(url)

    if not result.success:
        raise YouTubeAPIError(f"Failed to fetch metadata: {result.errors}")

    if not result.data or not result.data.get("metadata"):
        raise YouTubeAPIError("No metadata returned")

    # Return the first metadata object
    metadata_dict = result.data["metadata"][0]
    return YouTubeMetadata(**metadata_dict)
