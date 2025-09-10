"""
Advanced YouTube Metadata Processor with Multi-Provider Support

Priority System:
1. PacketStream proxy with yt-dlp (PRIMARY)
2. Direct yt-dlp for small batches ≤2 videos (FALLBACK)
3. Bright Data API (CONSERVED but DISABLED)

Uses residential proxies to avoid bot detection while providing reliable metadata extraction.
"""

import json
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

from ..config import get_settings
from ..errors import YouTubeAPIError
from ..logger import get_logger
from ..utils.bright_data_adapters import (
    adapt_bright_data_metadata,
    validate_bright_data_response,
)
from ..utils.youtube_utils import extract_urls, is_youtube_url
from .base import BaseProcessor, ProcessorResult

logger = get_logger(__name__)


class YouTubeMetadata(BaseModel):
    """YouTube video metadata model."""

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

    # Enhanced metadata fields
    related_videos: list[dict[str, Any]] = Field(
        default_factory=list, description="Related videos suggestions"
    )
    channel_stats: dict[str, Any] = Field(
        default_factory=dict, description="Detailed channel statistics"
    )
    video_chapters: list[dict[str, Any]] = Field(
        default_factory=list, description="Video chapters/timestamps"
    )

    # Extraction metadata
    extraction_method: str = Field(
        default="bright_data_api_scraper", description="Method used to extract metadata"
    )
    fetched_at: datetime = Field(
        default_factory=datetime.now, description="When metadata was fetched"
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return self.model_dump()

    def to_markdown_metadata(self) -> str:
        """Generate markdown metadata section."""
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
    """YouTube metadata processor with dual extraction methods."""

    def __init__(self, name: str | None = None) -> None:
        """Initialize the YouTube metadata processor."""
        super().__init__(name or "youtube_metadata")

        self.settings = get_settings()
        self.use_proxy = False
        self.proxy_manager = None

        # Configure PacketStream proxy (optional)
        self._configure_packetstream_proxy()
        # Note: PacketStream is optional - we can use direct yt-dlp for metadata extraction

    def _configure_packetstream_proxy(self):
        """Configure PacketStream proxy for YouTube metadata access (optional)."""
        try:
            from ..utils.packetstream_proxy import PacketStreamProxyManager

            self.proxy_manager = PacketStreamProxyManager()
            if self.proxy_manager.username and self.proxy_manager.auth_key:
                self.use_proxy = True
                logger.info("✅ Configured PacketStream proxy for metadata extraction")
            else:
                logger.warning(
                    "⚠️ PACKETSTREAM PROXY NOT CONFIGURED for metadata extraction"
                )
                logger.warning("⚠️ Using direct access - may hit YouTube rate limits!")
                self.use_proxy = False

        except Exception as e:
            logger.warning(f"⚠️ PACKETSTREAM PROXY NOT AVAILABLE for metadata: {e}")
            logger.warning(
                "⚠️ Using direct access - may encounter YouTube anti-bot detection!"
            )
            self.use_proxy = False

    @property
    def supported_formats(self) -> list[str]:
        """Return list of supported input formats."""
        return [".url", ".txt"]

    def validate_input(self, input_data: Any) -> bool:
        """Validate that the input data is suitable for processing."""
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
        """Extract video ID from YouTube URL."""
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
        """Extract metadata using Bright Data (required)."""
        return self._extract_metadata_bright_data(url)

    def _extract_metadata_bright_data(self, url: str) -> YouTubeMetadata | None:
        """Extract metadata using Bright Data YouTube API Scraper."""
        try:
            video_id = self._extract_video_id(url)
            if not video_id:
                logger.error(f"Could not extract video ID from URL: {url}")
                return None

            # Bright Data YouTube Posts API - Datasets v3 (Working Implementation)
            # This uses the account-specific dataset ID for YouTube Posts "Collect by URL"
            dataset_id = "gd_lk538t2k2p1k3oos71"  # Your YouTube Posts dataset ID

            # Step 1: Trigger collection using Datasets v3 API
            trigger_url = f"https://api.brightdata.com/datasets/v3/trigger?dataset_id={dataset_id}&format=json"

            headers = {
                "Authorization": f"Bearer {self.bright_data_api_key}",
                "Content-Type": "application/json",
            }

            # Payload for Datasets v3 trigger
            trigger_payload = [{"url": url}]

            logger.debug(f"Requesting metadata from Bright Data for video {video_id}")

            # Step 1: Trigger the collection
            try:
                logger.debug(f"Triggering Bright Data collection: {trigger_url}")
                trigger_response = requests.post(
                    trigger_url,
                    headers=headers,
                    json=trigger_payload,
                    timeout=30,
                    verify=True,
                )

                logger.debug(f"Trigger response status: {trigger_response.status_code}")

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
                    f"✅ Collection triggered successfully, snapshot ID: {snapshot_id}"
                )

                # Step 2: Poll for data with exponential backoff
                status_url = (
                    f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}"
                )
                max_attempts = 15  # Up to 3 minutes of polling

                for attempt in range(max_attempts):
                    wait_time = min(
                        10, 2 ** min(attempt, 4)
                    )  # Exponential backoff, max 10 seconds
                    if attempt > 0:
                        logger.debug(
                            f"Waiting {wait_time} seconds before poll attempt {attempt + 1}..."
                        )
                        time.sleep(wait_time)

                    logger.debug(
                        f"Polling for data (attempt {attempt + 1}/{max_attempts}): {status_url}"
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
                                    f"✅ YouTube metadata received after {attempt + 1} attempts"
                                )

                                try:
                                    # Parse the response - handle both JSON formats
                                    bright_data_response = poll_response.json()

                                    # Validate response structure
                                    if not validate_bright_data_response(
                                        bright_data_response
                                    ):
                                        logger.error(
                                            f"Invalid Bright Data response structure for {video_id}"
                                        )
                                        return None

                                    # Use the adapter to convert to our YouTubeMetadata model
                                    metadata = adapt_bright_data_metadata(
                                        bright_data_response, url
                                    )

                                    logger.info(
                                        f"✅ Successfully extracted metadata via Bright Data for {video_id}"
                                    )
                                    return metadata

                                except json.JSONDecodeError as e:
                                    logger.error(f"Failed to parse JSON response: {e}")
                                    logger.debug(
                                        f"Raw response: {poll_response.text[:300]}"
                                    )
                                    return None

                            else:
                                logger.debug("Empty response, data still processing...")

                        elif poll_response.status_code == 202:
                            logger.debug("Status 202: Still processing...")

                        elif poll_response.status_code == 404:
                            logger.error(f"Snapshot {snapshot_id} not found or expired")
                            return None

                        else:
                            logger.warning(
                                f"Unexpected poll status {poll_response.status_code}: {poll_response.text[:100]}"
                            )

                    except requests.exceptions.Timeout:
                        logger.warning(f"Poll timeout on attempt {attempt + 1}")
                        continue
                    except Exception as e:
                        logger.warning(
                            f"Poll error on attempt {attempt + 1}: {str(e)[:100]}"
                        )
                        continue

                # If we get here, polling timed out
                logger.error(
                    f"YouTube metadata collection timed out after {max_attempts} attempts for {video_id}"
                )
                return None

            except requests.exceptions.Timeout:
                logger.error(f"Bright Data API trigger timeout for {url}")
                return None
            except Exception as e:
                logger.error(
                    f"Bright Data API trigger failed for {url}: {str(e)[:100]}"
                )
                return None

        except requests.exceptions.Timeout:
            logger.error(f"Bright Data API timeout for {url}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Bright Data API request failed for {url}: {e}")
            return None
        except Exception as e:
            logger.error(
                f"Unexpected error in Bright Data metadata extraction for {url}: {e}"
            )
            return None

    def _extract_metadata_unified(
        self, url: str, total_urls: int = 1
    ) -> YouTubeMetadata | None:
        """
        Extract metadata with priority system:
        1. PacketStream (primary)
        2. Direct yt-dlp (fallback for ≤2 videos)
        3. Bright Data (conserved but disabled)
        """
        # Ensure URL is a plain string, not a list or other format
        if isinstance(url, list):
            logger.debug(f"URL is a list: {url}, taking first element")
            url = url[0] if url else ""
        elif not isinstance(url, str):
            logger.debug(f"URL is not a string: {type(url)}, converting to string")
            url = str(url)

        video_id = self._extract_video_id(url)
        if not video_id:
            logger.error(f"Could not extract video ID from URL: {url}")
            return None

        # Method 1: Try PacketStream proxy with yt-dlp (PRIMARY)
        logger.info(f"🔄 Attempting PacketStream proxy extraction for {video_id}")
        try:
            metadata = self._extract_metadata_packetstream(url)
            if metadata:
                logger.info(f"✅ PacketStream extraction successful for {video_id}")
                metadata.extraction_method = "packetstream_proxy"
                return metadata
            else:
                logger.info(
                    f"⚠️ PacketStream extraction failed for {video_id} - trying fallback methods"
                )
        except Exception as e:
            logger.info(
                f"⚠️ PacketStream proxy error for {video_id}: {str(e)[:100]} - trying fallback methods"
            )

        # Method 2: Try direct yt-dlp (FALLBACK for small batches ≤2 videos)
        # NOTE: This fallback may be reducing PacketStream usage for single videos
        if total_urls <= 2:
            logger.info(
                f"🔄 Attempting direct yt-dlp extraction for {video_id} (≤2 videos) - this reduces PacketStream usage"
            )
            try:
                metadata = self._extract_metadata_direct_ytdlp(url)
                if metadata:
                    logger.info(
                        f"✅ Direct yt-dlp extraction successful for {video_id} - PacketStream not used"
                    )
                    metadata.extraction_method = "direct_ytdlp"
                    return metadata
                else:
                    logger.warning(f"⚠️ Direct yt-dlp extraction failed for {video_id}")
            except Exception as e:
                logger.warning(f"⚠️ Direct yt-dlp error for {video_id}: {str(e)[:100]}")
        else:
            logger.info(
                f"🚫 Skipping direct yt-dlp for {video_id} (>2 videos, would trigger bot detection)"
            )
            logger.info(
                "💡 For bulk operations, configure PacketStream credentials in Settings > API Keys"
            )

        # Method 3: Bright Data (CONSERVED but DISABLED)
        # Note: This code is preserved for future use but currently disabled
        # to prioritize PacketStream and avoid API costs
        logger.info(
            f"🚫 Bright Data extraction DISABLED for {video_id} (code conserved)"
        )
        # Uncomment the following lines to re-enable Bright Data as last resort:
        # try:
        #     metadata = self._extract_metadata_bright_data(url)
        #     if metadata:
        #         logger.info(f"✅ Bright Data extraction successful for {video_id}")
        #         metadata.extraction_method = "bright_data_api"
        #         return metadata
        # except Exception as e:
        #     logger.warning(f"⚠️ Bright Data error for {video_id}: {str(e)[:100]}")

        logger.error(f"❌ All extraction methods failed for {video_id}")
        return None

    def _extract_metadata_packetstream(self, url: str) -> YouTubeMetadata | None:
        """Extract metadata using PacketStream proxy with yt-dlp."""
        try:
            from .youtube_metadata_proxy import YouTubeMetadataProxyProcessor

            # Create proxy processor instance
            proxy_processor = YouTubeMetadataProxyProcessor()

            # Use the proxy processor's yt-dlp method
            metadata = proxy_processor._extract_metadata_with_proxy(url)
            return metadata

        except ImportError:
            logger.error("PacketStream proxy processor not available")
            return None
        except Exception as e:
            logger.error(f"PacketStream extraction error: {str(e)[:200]}")
            return None

    def _extract_metadata_direct_ytdlp(self, url: str) -> YouTubeMetadata | None:
        """Extract metadata using direct yt-dlp (no proxy) for small batches."""
        try:
            import yt_dlp
        except ImportError:
            logger.error("yt-dlp not available for direct extraction")
            return None

        # Ensure URL is a plain string, not a list or other format
        if isinstance(url, list):
            logger.debug(f"URL is a list: {url}, taking first element")
            url = url[0] if url else ""
        elif not isinstance(url, str):
            logger.debug(f"URL is not a string: {type(url)}, converting to string")
            url = str(url)

        video_id = self._extract_video_id(url)
        if not video_id:
            return None

        try:
            # Configure yt-dlp for metadata-only extraction
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": False,
                "skip_download": True,
                "writeinfojson": False,
                "writesubtitles": False,
                "writeautomaticsub": False,
                "ignoreerrors": True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.debug(f"Extracting metadata with direct yt-dlp for {video_id}")
                yt_info = ydl.extract_info(url, download=False)

                if not yt_info:
                    logger.error(f"No metadata returned by yt-dlp for {video_id}")
                    return None

                # Convert yt-dlp info to our YouTubeMetadata model
                metadata = self._convert_ytdlp_to_metadata(yt_info, url)
                return metadata

        except Exception as e:
            logger.error(
                f"Direct yt-dlp extraction failed for {video_id}: {str(e)[:200]}"
            )
            return None

    def _convert_ytdlp_to_metadata(self, yt_info: dict, url: str) -> YouTubeMetadata:
        """Convert yt-dlp info dict to YouTubeMetadata model."""
        video_id = yt_info.get("id", self._extract_video_id(url))

        # Parse duration
        duration = yt_info.get("duration")
        if isinstance(duration, str):
            duration = self._parse_duration_string(duration)

        # Extract upload date
        upload_date = None
        if yt_info.get("upload_date"):
            try:
                upload_date = datetime.strptime(
                    yt_info["upload_date"], "%Y%m%d"
                ).isoformat()
            except:
                upload_date = yt_info.get("upload_date")

        # Extract tags
        tags = yt_info.get("tags", []) or []
        if isinstance(tags, str):
            tags = [tag.strip() for tag in tags.split(",")]

        # Extract categories
        categories = []
        if yt_info.get("categories"):
            categories = (
                yt_info["categories"]
                if isinstance(yt_info["categories"], list)
                else [yt_info["categories"]]
            )

        # Extract thumbnail (best quality)
        thumbnail_url = None
        thumbnails = yt_info.get("thumbnails", [])
        if thumbnails:
            # Get highest resolution thumbnail
            best_thumb = max(
                thumbnails, key=lambda x: x.get("width", 0) * x.get("height", 0)
            )
            thumbnail_url = best_thumb.get("url")

        # Extract related videos (if available)
        related_videos = []
        if yt_info.get("related_videos"):
            related_videos = yt_info["related_videos"]

        # Extract channel stats
        channel_stats = {}
        if yt_info.get("channel_follower_count"):
            channel_stats["subscribers"] = yt_info["channel_follower_count"]
        if yt_info.get("channel_is_verified"):
            channel_stats["verified"] = yt_info["channel_is_verified"]
        if yt_info.get("channel_url"):
            channel_stats["channel_url"] = yt_info["channel_url"]

        # Extract video chapters
        video_chapters = []
        if yt_info.get("chapters"):
            video_chapters = yt_info["chapters"]

        return YouTubeMetadata(
            video_id=video_id,
            title=yt_info.get("title", ""),
            url=url,
            description=yt_info.get("description", ""),
            uploader=yt_info.get("uploader", "") or yt_info.get("channel", ""),
            uploader_id=yt_info.get("uploader_id", "") or yt_info.get("channel_id", ""),
            upload_date=upload_date,
            duration=duration,
            view_count=yt_info.get("view_count"),
            like_count=yt_info.get("like_count"),
            comment_count=yt_info.get("comment_count"),
            thumbnail_url=thumbnail_url,
            tags=tags,
            categories=categories,
            related_videos=related_videos,
            channel_stats=channel_stats,
            video_chapters=video_chapters,
            extraction_method="direct_ytdlp",
            fetched_at=datetime.now(),
        )

    def _parse_duration_string(self, duration_str: str) -> int | None:
        """Parse duration string to seconds."""
        if not duration_str:
            return None

        try:
            # If it's already a number, return it
            if isinstance(duration_str, (int, float)):
                return int(duration_str)

            # Parse HH:MM:SS format
            if ":" in duration_str:
                parts = duration_str.split(":")
                if len(parts) == 3:  # HH:MM:SS
                    hours, minutes, seconds = parts
                    return int(hours) * 3600 + int(minutes) * 60 + int(seconds)
                elif len(parts) == 2:  # MM:SS
                    minutes, seconds = parts
                    return int(minutes) * 60 + int(seconds)

            # Try to parse as plain number
            return int(float(duration_str))

        except (ValueError, TypeError):
            return None

    def process(
        self, input_data: Any, dry_run: bool = False, **kwargs: Any
    ) -> ProcessorResult:
        """Process YouTube URLs and extract metadata using priority system: PacketStream → Direct yt-dlp → Bright Data (disabled)."""
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

                metadata = self._extract_metadata_unified(url, total_urls=len(urls))
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
                    "extraction_method": "bright_data_api_scraper",
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
        """Write a simple failure log for debugging."""
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

                f.write("\nNote: Processing uses Bright Data API Scrapers.\n")
                f.write(
                    "If failures persist, check your Bright Data API key and quotas.\n"
                )
                f.write(f"\n{'='*70}\n")

            logger.info(f"Failure log appended to: {log_file}")

        except Exception as e:
            logger.error(f"Failed to write failure log: {e}")


# Convenience function for single video metadata extraction
def fetch_metadata(url: str) -> YouTubeMetadata:
    """Convenience function to fetch metadata for a single video."""
    processor = YouTubeMetadataProcessor()
    result = processor.process(url)

    if not result.success:
        raise YouTubeAPIError(f"Failed to fetch metadata: {result.errors}")

    if not result.data or not result.data.get("metadata"):
        raise YouTubeAPIError("No metadata returned")

    # Return the first metadata object
    metadata_dict = result.data["metadata"][0]
    return YouTubeMetadata(**metadata_dict)
