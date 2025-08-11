"""
YouTube Metadata Processor
YouTube Metadata Processor

Fetches metadata from YouTube videos using YT-DLP with rotating proxies as primary method.
Tracks failures and performs batch backfill using YouTube Data API v3.
Provides comprehensive logging of extraction statistics and final failures.
"""

import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

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

    # Categorization
    tags: list[str] = Field(default_factory=list, description="Video tags")
    categories: list[str] = Field(default_factory=list, description="Video categories")

    # Media information
    thumbnail_url: str | None = Field(default=None, description="Thumbnail URL")
    resolution: str | None = Field(default=None, description="Video resolution")

    # Privacy and captions
    privacy_status: str | None = Field(default=None, description="Privacy status")
    caption_availability: bool | None = Field(
        default=None, description="Caption availability"
    )

    # Transcript availability
    has_transcript: bool = Field(
        default=False, description="Whether transcript is available"
    )
    transcript_languages: list[str] = Field(
        default_factory=list, description="Available transcript languages"
    )

    # Extraction metadata
    extraction_method: str = Field(
        default="yt-dlp", description="Method used for extraction"
    )
    fetched_at: datetime = Field(
        default_factory=datetime.now, description="When metadata was fetched"
    )

    def to_dict(self) -> dict[str, Any]:
        """ Convert to dictionary for JSON serialization."""
        data = self.model_dump()
        # Convert datetime to ISO string for JSON serialization
        if "fetched_at" in data and isinstance(data["fetched_at"], datetime):
            data["fetched_at"] = data["fetched_at"].isoformat()
        return data

    def to_markdown_metadata(self) -> str:
        """ Convert to markdown metadata section."""
        lines = ["# Metadata"]
        lines.append("")

        # Basic info
        lines.append(f"- **Title**: {self.title}")
        lines.append(f"- **URL**: {self.url}")
        lines.append(f"- **Video ID**: {self.video_id}")
        lines.append(f"- **Uploader**: {self.uploader}")

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

        if self.privacy_status:
            lines.append(f"- **Privacy**: {self.privacy_status}")

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

        # Extraction info
        lines.append(f"- **Extracted via**: {self.extraction_method}")
        lines.append(
            f"- **Fetched at**: {self.fetched_at.strftime('%Y-%m-%d %H:%M:%S')}"
        )

        return "\n".join(lines)


class FailedVideo(BaseModel):
    """ Information about a failed video extraction."""

    video_id: str = Field(..., description="YouTube video ID")
    url: str = Field(..., description="Full YouTube URL")
    title: str | None = Field(default=None, description="Video title if available")
    uploader: str | None = Field(default=None, description="Channel name if available")
    failure_reason: str = Field(default="Unknown", description="Reason for failure")
    ytdlp_failed: bool = Field(
        default=True, description="Whether YT-DLP extraction failed"
    )
    api_failed: bool = Field(default=True, description="Whether API extraction failed")

    def to_dict(self) -> dict[str, Any]:
        """ Convert to dictionary."""
        return self.model_dump()


class MetadataExtractionStats(BaseModel):
    """ Statistics for metadata extraction session."""

    total_videos: int = 0
    primary_success: int = 0
    primary_failures: int = 0
    backfill_success: int = 0
    backfill_failures: int = 0
    final_failures: int = 0
    extraction_time: float = 0.0

    def success_rate(self) -> float:
        """ Calculate overall success rate."""
        if self.total_videos == 0:
            return 0.0
        return (self.primary_success + self.backfill_success) / self.total_videos

    def to_dict(self) -> dict[str, Any]:
        """ Convert to dictionary."""
        return {
            "total_videos": self.total_videos,
            "primary_success": self.primary_success,
            "primary_failures": self.primary_failures,
            "backfill_success": self.backfill_success,
            "backfill_failures": self.backfill_failures,
            "final_failures": self.final_failures,
            "extraction_time": self.extraction_time,
            "success_rate": self.success_rate(),
        }


class YouTubeMetadataProcessor(BaseProcessor):
    """ Processor for extracting YouTube video metadata using YT-DLP with rotating proxies."""

    def __init__(self, name: str | None = None) -> None:
        """ Initialize the YouTube metadata processor."""
        super().__init__(name or "youtube_metadata")

        if yt_dlp is None:
            raise YouTubeAPIError(
                "yt-dlp is required for YouTube metadata extraction. "
                "Please install it with: pip install yt-dlp"
            )

        # Get settings
        self.settings = get_settings()

        # YT-DLP configuration with rotating proxies
        self.ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "ignoreerrors": True,
            "no_check_certificate": True,
            "skip_download": True,  # We only want metadata
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "headers": {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-us,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Accept-Charset": "ISO-8859-1,utf-8;q=0.7,*;q=0.7",
                "Keep-Alive": "timeout=5, max=100",
                "Connection": "keep-alive",
            },
            "extractor_retries": 3,
            "socket_timeout": 30,
            "retries": 5,
        }

        # Add proxy configuration if available
        self._configure_proxy()

    def _configure_proxy(self):
        """ Configure rotating proxy for YT-DLP if credentials are available."""
        try:
            webshare_username = self.settings.api_keys.webshare_username
            webshare_password = self.settings.api_keys.webshare_password

            if webshare_username and webshare_password:
                proxy_url = (
                    f"http://{webshare_username}:{webshare_password}@p.webshare.io:80/"
                )
                self.ydl_opts["proxy"] = proxy_url
                logger.info("Configured YT-DLP with WebShare rotating proxy")
            else:
                logger.warning(
                    "WebShare credentials not found. Using direct connections (may be rate limited)"
                )
        except Exception as e:
            logger.warning(f"Failed to configure proxy: {e}")

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

    def _extract_metadata_ytdlp(self, url: str) -> YouTubeMetadata | None:
        """ Extract metadata using YT-DLP with rotating proxies."""
        try:
            # Add configurable delay to avoid rate limiting
            delay_config = self.settings.youtube_processing

            # Check if we should skip delays when using proxies
            has_proxy = (
                self.settings.api_keys.webshare_username
                and self.settings.api_keys.webshare_password
            )

            if delay_config.disable_delays_with_proxy and has_proxy:
                logger.debug("Skipping delay - using rotating proxies")
            elif delay_config.use_proxy_delays or not has_proxy:
                delay_time = random.uniform(
                    delay_config.metadata_delay_min, delay_config.metadata_delay_max
                )
                if delay_time > 0:
                    logger.debug(
                        f"Adding {delay_time:.2f}s delay to avoid rate limiting"
                    )
                    time.sleep(delay_time)

            if yt_dlp is None:
                logger.error("yt-dlp is not available")
                return None

            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                if not info:
                    logger.warning(f"No info extracted from {url}")
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
                        # Try to parse other formats
                        from datetime import datetime

                        dt = datetime.strptime(upload_date, "%Y%m%d")
                        upload_date = dt.strftime("%Y%m%d")
                    except ValueError:
                        upload_date = None

                # Get thumbnail URL (prefer highest quality)
                thumbnail_url = info.get("thumbnail")
                if not thumbnail_url and info.get("thumbnails"):
                    thumbnails = info.get("thumbnails", [])
                    if thumbnails:
                        thumbnail_url = thumbnails[-1].get(
                            "url"
                        )  # Last is usually highest quality

                # Parse view count
                view_count = info.get("view_count")
                if view_count and isinstance(view_count, str):
                    try:
                        view_count = int(view_count)
                    except ValueError:
                        view_count = None

                # Parse like count
                like_count = info.get("like_count")
                if like_count and isinstance(like_count, str):
                    try:
                        like_count = int(like_count)
                    except ValueError:
                        like_count = None

                # Parse comment count
                comment_count = info.get("comment_count")
                if comment_count and isinstance(comment_count, str):
                    try:
                        comment_count = int(comment_count)
                    except ValueError:
                        comment_count = None

                # Check for captions
                has_captions = False
                if info.get("subtitles") or info.get("automatic_captions"):
                    has_captions = True

                # Create metadata object
                metadata = YouTubeMetadata(
                    video_id=video_id,
                    title=info.get("title", ""),
                    url=url,
                    description=info.get("description", ""),
                    duration=duration,
                    view_count=view_count,
                    like_count=like_count,
                    comment_count=comment_count,
                    uploader=info.get("uploader", ""),
                    uploader_id=info.get("uploader_id", ""),
                    upload_date=upload_date,
                    tags=info.get("tags", []) or [],
                    categories=info.get("categories", []) or [],
                    thumbnail_url=thumbnail_url,
                    resolution=info.get("resolution"),
                    privacy_status=None,  # Not available in YT-DLP
                    caption_availability=has_captions,
                    extraction_method="yt-dlp",
                )

                logger.info(
                    f"Successfully extracted metadata via YT-DLP: {metadata.title}"
                )
                return metadata

        except Exception as e:
            logger.warning(f"YT-DLP extraction failed for {url}: {e}")
            return None

    def _batch_backfill_api(
        self, failed_video_ids: list[str]
    ) -> tuple[list[YouTubeMetadata], list[str]]:
        """ Batch backfill failed metadata using YouTube Data API v3."""
        if not failed_video_ids:
            return [], []

        # Check if API key is available
        api_key = self.settings.api_keys.youtube_api_key
        if not api_key:
            logger.warning(
                "YouTube API key not configured. Cannot backfill failed metadata."
            )
            return [], failed_video_ids

        successful_metadata = []
        still_failed = []

        # Process in batches of 50 (API limit)
        batch_size = 50
        for i in range(0, len(failed_video_ids), batch_size):
            batch = failed_video_ids[i : i + batch_size]

            try:
                # Add configurable delay between batches to avoid rate limiting
                if i > 0:
                    delay_config = self.settings.youtube_processing

                    # Check if we should skip delays when using proxies
                    has_proxy = (
                        self.settings.api_keys.webshare_username
                        and self.settings.api_keys.webshare_password
                    )

                    if delay_config.disable_delays_with_proxy and has_proxy:
                        logger.debug(
                            "Skipping API batch delay - using rotating proxies"
                        )
                    elif delay_config.use_proxy_delays or not has_proxy:
                        delay_time = random.uniform(
                            delay_config.api_batch_delay_min,
                            delay_config.api_batch_delay_max,
                        )
                        if delay_time > 0:
                            logger.debug(
                                f"Adding {delay_time:.2f}s delay between API batches"
                            )
                            time.sleep(delay_time)

                # Create session without proxy (direct API call)
                session = requests.Session()
                session.headers.update(
                    {
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                    }
                )

                # YouTube Data API v3 endpoint
                api_url = "https://www.googleapis.com/youtube/v3/videos"
                params = {
                    "part": "snippet,statistics,contentDetails,status",
                    "id": ",".join(batch),
                    "key": api_key,
                }

                response = session.get(api_url, params=params, timeout=30)
                response.raise_for_status()

                data = response.json()
                items = data.get("items", [])

                # Process each item
                for item in items:
                    try:
                        video_id = item["id"]
                        snippet = item.get("snippet", {})
                        statistics = item.get("statistics", {})
                        content_details = item.get("contentDetails", {})
                        status = item.get("status", {})

                        # Parse duration from ISO 8601 format
                        duration_str = content_details.get("duration", "")
                        duration_seconds = None
                        if duration_str:
                            try:
                                duration_match = re.match(
                                    r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration_str
                                )
                                if duration_match:
                                    hours = int(duration_match.group(1) or 0)
                                    minutes = int(duration_match.group(2) or 0)
                                    seconds = int(duration_match.group(3) or 0)
                                    duration_seconds = (
                                        hours * 3600 + minutes * 60 + seconds
                                    )
                            except Exception as e:
                                logger.warning(
                                    f"Failed to parse duration '{duration_str}': {e}"
                                )

                        # Parse upload date
                        upload_date = None
                        published_at = snippet.get("publishedAt", "")
                        if published_at:
                            try:
                                dt = datetime.fromisoformat(
                                    published_at.replace("Z", "+00:00")
                                )
                                upload_date = dt.strftime("%Y%m%d")
                            except Exception as e:
                                logger.warning(
                                    f"Failed to parse upload date '{published_at}': {e}"
                                )

                        # Get thumbnail URL
                        thumbnails = snippet.get("thumbnails", {})
                        thumbnail_url = None
                        for quality in ["maxresdefault", "high", "medium", "default"]:
                            if quality in thumbnails:
                                thumbnail_url = thumbnails[quality]["url"]
                                break

                        # Check for captions
                        has_captions = content_details.get("caption", "false") == "true"

                        # Create metadata object
                        metadata = YouTubeMetadata(
                            video_id=video_id,
                            title=snippet.get("title", ""),
                            url=f"https://www.youtube.com/watch?v={video_id}",
                            description=snippet.get("description", ""),
                            duration=duration_seconds,
                            view_count=(
                                int(statistics.get("viewCount", 0))
                                if statistics.get("viewCount")
                                else None
                            ),
                            like_count=(
                                int(statistics.get("likeCount", 0))
                                if statistics.get("likeCount")
                                else None
                            ),
                            comment_count=(
                                int(statistics.get("commentCount", 0))
                                if statistics.get("commentCount")
                                else None
                            ),
                            uploader=snippet.get("channelTitle", ""),
                            uploader_id=snippet.get("channelId", ""),
                            upload_date=upload_date,
                            tags=snippet.get("tags", []),
                            categories=snippet.get("categories", []),
                            thumbnail_url=thumbnail_url,
                            resolution=None,  # Not available in basic API response
                            privacy_status=status.get("privacyStatus"),
                            caption_availability=has_captions,
                            extraction_method="youtube-api-v3",
                        )

                        successful_metadata.append(metadata)
                        logger.info(
                            f"Successfully backfilled metadata via API: {metadata.title}"
                        )

                    except Exception as e:
                        logger.warning(
                            f"Failed to process API item for video {item.get('id', 'unknown')}: {e}"
                        )
                        if item.get("id"):
                            still_failed.append(item["id"])

                # Check for videos that weren't returned by API
                returned_ids = {item["id"] for item in items}
                for video_id in batch:
                    if video_id not in returned_ids:
                        still_failed.append(video_id)
                        logger.warning(f"Video {video_id} not found in API response")

            except Exception as e:
                logger.error(f"API batch request failed: {e}")
                still_failed.extend(batch)

        return successful_metadata, still_failed

    def _get_basic_video_info(self, video_id: str) -> dict[str, str | None]:
        """ Try to get basic video info (title, uploader) using a lightweight method."""
        try:
            # Use a simple regex approach to extract title from YouTube page
            import requests

            url = f"https://www.youtube.com/watch?v={video_id}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }

            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                content = response.text

                # Extract title using regex
                title_match = re.search(
                    r'<meta property="og:title" content="([^"]*)"', content
                )
                title = title_match.group(1) if title_match else None

                # Extract uploader using regex
                uploader_match = re.search(
                    r'<meta property="og:video:channel" content="([^"]*)"', content
                )
                uploader = uploader_match.group(1) if uploader_match else None

                # Alternative title extraction from page title
                if not title:
                    title_match = re.search(r"<title>([^<]*)</title>", content)
                    if title_match:
                        title = title_match.group(1).replace(" - YouTube", "").strip()

                return {"title": title, "uploader": uploader}

        except Exception as e:
            logger.debug(f"Could not get basic info for {video_id}: {e}")

        return {"title": None, "uploader": None}

    def _write_failure_log(
        self, failed_videos: list[FailedVideo], output_dir: Path | None = None
    ):
        """ Write final failure log file with human-readable titles."""
        if not failed_videos:
            return

        try:
            # Get the logs directory from settings instead of using output_dir or cwd
            from ..config import get_settings

            settings = get_settings()
            logs_dir = Path(settings.paths.logs).expanduser()
            logs_dir.mkdir(parents=True, exist_ok=True)

            # Use a single consolidated log file that appends entries
            log_file = logs_dir / "youtube_metadata_failures_complex.log"

            logger.info(
                f"Attempting to retrieve titles for {len(failed_videos)} failed videos..."
            )

            # Try to get basic info for videos that don't have titles
            for failed_video in failed_videos:
                if not failed_video.title:
                    basic_info = self._get_basic_video_info(failed_video.video_id)
                    failed_video.title = basic_info.get("title")
                    if not failed_video.uploader:
                        failed_video.uploader = basic_info.get("uploader")
                    time.sleep(0.5)  # Rate limiting

            with open(
                log_file, "a", encoding="utf-8"
            ) as f:  # Changed 'w' to 'a' for append
                f.write("\n\nYouTube Metadata Extraction Failures\n")
                f.write(f"Generated: {datetime.now().isoformat()}\n")
                f.write(f"Total failures: {len(failed_videos)}\n")
                f.write(f"{'='*70}\n\n")
                f.write(
                    "These videos failed both YT-DLP and YouTube Data API v3 extraction.\n"
                )
                f.write(
                    "You may need to check them manually or try alternative methods.\n\n"
                )

                for i, failed_video in enumerate(failed_videos, 1):
                    f.write(f"{i}. ")

                    # Write title (human-readable)
                    if failed_video.title:
                        f.write(f'"{failed_video.title}"\n')
                    else:
                        f.write(
                            f"[Title Unknown] (Video ID: {failed_video.video_id})\n"
                        )

                    # Write channel if available
                    if failed_video.uploader:
                        f.write(f"   Channel: {failed_video.uploader}\n")

                    # Write URL for easy access
                    f.write(f"   URL: {failed_video.url}\n")

                    # Write failure details
                    f.write(f"   Failure Reason: {failed_video.failure_reason}\n")

                    # Write what was attempted
                    attempts = []
                    if failed_video.ytdlp_failed:
                        attempts.append("YT-DLP")
                    if failed_video.api_failed:
                        attempts.append("YouTube Data API v3")
                    f.write(f"   Failed Methods: {', '.join(attempts)}\n")

                    f.write("\n")

                f.write(f"\n{'='*70}\n")
                f.write("Manual Investigation Tips:\n")
                f.write(
                    "• Check if videos are private, deleted, or region-restricted\n"
                )
                f.write("• Verify your YouTube Data API key has sufficient quota\n")
                f.write("• Try accessing videos directly in a browser\n")
                f.write("• Consider using alternative extraction methods\n")

            logger.info(f"Human-readable failure log written to: {log_file}")

        except Exception as e:
            logger.error(f"Failed to write failure log: {e}")

    def process(
        self,
        input_data: Any,
        dry_run: bool = False,
        output_dir: Path | None = None,
        **kwargs: Any,
    ) -> ProcessorResult:
        """ Process YouTube URLs and extract metadata using YT-DLP + API backfill."""
        start_time = time.time()

        try:
            # Extract URLs from input
            urls = extract_urls(input_data)
            if not urls:
                return ProcessorResult(
                    success=False, errors=["No valid YouTube URLs found in input"]
                )

            logger.info(f"Processing {len(urls)} YouTube URLs for metadata extraction")

            # Initialize tracking
            stats = MetadataExtractionStats(total_videos=len(urls))
            all_metadata = []
            failed_videos = []
            errors = []

            # Phase 1: Primary extraction using YT-DLP with rotating proxies
            logger.info(
                "Phase 1: Primary metadata extraction using YT-DLP with rotating proxies"
            )

            for i, url in enumerate(urls, 1):
                try:
                    video_id = self._extract_video_id(url)
                    if not video_id:
                        logger.warning(f"Could not extract video ID from {url}")
                        errors.append(f"Invalid URL format: {url}")
                        continue

                    logger.info(f"Processing {i}/{len(urls)}: {video_id}")

                    if dry_run:
                        logger.info(f"DRY RUN: Would extract metadata for {url}")
                        continue

                    metadata = self._extract_metadata_ytdlp(url)
                    if metadata:
                        all_metadata.append(metadata)
                        stats.primary_success += 1
                    else:
                        failed_video = FailedVideo(
                            video_id=video_id,
                            url=url,
                            failure_reason="YT-DLP extraction failed",
                            ytdlp_failed=True,
                            api_failed=False,  # Will be updated in Phase 2
                        )
                        failed_videos.append(failed_video)
                        stats.primary_failures += 1
                        logger.warning(f"Primary extraction failed for {video_id}")

                except Exception as e:
                    error_msg = f"Error processing {url}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                    # Try to extract video ID for potential backfill
                    video_id = self._extract_video_id(url)
                    if video_id:
                        failed_video = FailedVideo(
                            video_id=video_id,
                            url=url,
                            failure_reason=f"YT-DLP exception: {str(e)}",
                            ytdlp_failed=True,
                            api_failed=False,  # Will be updated in Phase 2
                        )
                        failed_videos.append(failed_video)
                        stats.primary_failures += 1

            # Phase 2: Batch backfill using YouTube Data API v3
            if failed_videos and not dry_run:
                failed_video_ids = [fv.video_id for fv in failed_videos]
                logger.info(
                    f"Phase 2: Batch backfill using YouTube Data API v3 for {len(failed_video_ids)} failed videos"
                )

                backfill_metadata, still_failed_ids = self._batch_backfill_api(
                    failed_video_ids
                )

                all_metadata.extend(backfill_metadata)
                stats.backfill_success = len(backfill_metadata)
                stats.backfill_failures = len(still_failed_ids)

                # Update failed_videos list to only include final failures
                final_failed_videos = []
                for failed_video in failed_videos:
                    if failed_video.video_id in still_failed_ids:
                        failed_video.api_failed = True
                        failed_video.failure_reason += " + API extraction also failed"
                        final_failed_videos.append(failed_video)

                stats.final_failures = len(final_failed_videos)

                # Write failure log if there are still failures
                if final_failed_videos:
                    self._write_failure_log(final_failed_videos, output_dir)

                    # Add to errors list
                    for failed_video in final_failed_videos:
                        errors.append(
                            f"Final failure: {failed_video.video_id} - failed both YT-DLP and API extraction"
                        )

            # Calculate final stats
            stats.extraction_time = time.time() - start_time

            # Log comprehensive statistics
            logger.info("=" * 60)
            logger.info("METADATA EXTRACTION STATISTICS")
            logger.info("=" * 60)
            logger.info(f"Total videos processed: {stats.total_videos}")
            logger.info(f"Primary successes (YT-DLP): {stats.primary_success}")
            logger.info(f"Primary failures: {stats.primary_failures}")
            logger.info(f"Backfill successes (API): {stats.backfill_success}")
            logger.info(f"Backfill failures: {stats.backfill_failures}")
            logger.info(f"Final failures: {stats.final_failures}")
            logger.info(f"Overall success rate: {stats.success_rate():.1%}")
            logger.info(f"Extraction time: {stats.extraction_time:.2f}s")
            logger.info("=" * 60)

            # Create output data
            output_data = {
                "metadata": [meta.to_dict() for meta in all_metadata],
                "count": len(all_metadata),
                "errors": errors,
                "processed_urls": len(urls),
                "statistics": stats.to_dict(),
            }

            # Create markdown outputs for each video
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

            output_data["markdown_files"] = markdown_outputs

            success = len(all_metadata) > 0
            return ProcessorResult(
                success=success,
                data=output_data,
                errors=errors,
                metadata={
                    "processed_count": len(all_metadata),
                    "statistics": stats.to_dict(),
                },
            )

        except Exception as e:
            logger.error(f"Error processing YouTube URLs: {e}")
            return ProcessorResult(
                success=False,
                errors=[f"Processing failed: {e}"],
                metadata={"processed_count": 0},
            )


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
