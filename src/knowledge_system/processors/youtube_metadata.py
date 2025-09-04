"""
Advanced YouTube Metadata Processor

Uses Bright Data YouTube API Scrapers for reliable metadata extraction.

Bright Data provides direct JSON responses, automatic IP rotation, and cost efficiency.
"""

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
        self.use_bright_data = False
        self.bright_data_api_key = None

        # Configure Bright Data (required)
        self._configure_bright_data()
        if not self.use_bright_data:
            from ..errors import YouTubeAPIError
            raise YouTubeAPIError(
                "Bright Data API key is required for YouTube metadata extraction. "
                "Please configure your Bright Data API Key in Settings."
            )

    def _configure_bright_data(self):
        """Configure Bright Data YouTube API Scraper (preferred method)."""
        try:
            if requests is None:
                raise YouTubeAPIError(
                    "requests library not available - cannot use Bright Data"
                )

            # Primary from settings
            self.bright_data_api_key = getattr(
                self.settings.api_keys, "bright_data_api_key", None
            )
            # Fallbacks from environment
            if not self.bright_data_api_key:
                import os
                self.bright_data_api_key = (
                    os.getenv("BRIGHT_DATA_API_KEY")
                    or os.getenv("BRIGHTDATA_API_KEY")
                    or os.getenv("BD_API_KEY")
                )

            # Accept UUID- or token-style keys (minimum length safety check)
            if self.bright_data_api_key and len(self.bright_data_api_key) >= 10:
                self.use_bright_data = True
                logger.info(
                    "✅ Configured Bright Data YouTube API Scraper for metadata extraction"
                )
                return
            else:
                logger.warning("Bright Data API key missing or invalid")

        except Exception as e:
            logger.warning(f"Failed to configure Bright Data: {e}")

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

            # Bright Data API endpoint - try different endpoint patterns
            # Based on current API documentation, try these endpoints in order
            endpoints_to_try = [
                "https://api.brightdata.com/dca/trigger_immediate",
                "https://api.brightdata.com/dataset/collect",
                "https://api.brightdata.com/datasets/youtube/trigger"
            ]
            
            headers = {
                "Authorization": f"Bearer {self.bright_data_api_key}",
                "Content-Type": "application/json",
            }

            # Request payload - try simplified structure first
            payload = {
                "url": url,
                "discover_by": "url"
            }

            logger.debug(f"Requesting metadata from Bright Data for video {video_id}")

            # Try each endpoint until one works
            response = None
            for api_url in endpoints_to_try:
                try:
                    logger.debug(f"Trying Bright Data endpoint: {api_url}")
                    response = requests.post(api_url, headers=headers, json=payload, timeout=30)
                    if response.status_code != 404:
                        break  # Found a working endpoint
                    else:
                        logger.debug(f"Endpoint {api_url} returned 404, trying next endpoint")
                except Exception as e:
                    logger.debug(f"Endpoint {api_url} failed with error: {e}")
                    continue
            
            if not response:
                logger.error("All Bright Data API endpoints failed")
                return None

            if response.status_code == 200:
                bright_data_response = response.json()

                # Validate response structure
                if not validate_bright_data_response(bright_data_response):
                    logger.error(
                        f"Invalid Bright Data response structure for {video_id}"
                    )
                    return None

                # Use the adapter to convert to our YouTubeMetadata model
                metadata = adapt_bright_data_metadata(bright_data_response, url)

                logger.debug(
                    f"✅ Successfully extracted metadata via Bright Data for {video_id}"
                )
                return metadata

            elif response.status_code == 402:
                logger.error("Bright Data API quota exceeded or payment required")
                return None
            elif response.status_code == 401:
                logger.error("Invalid Bright Data API key")
                return None
            elif response.status_code == 429:
                logger.warning("Bright Data API rate limit reached, retrying...")
                time.sleep(2)
                # Could implement retry logic here
                return None
            else:
                logger.error(
                    f"Bright Data API error {response.status_code}: {response.text}"
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

    def _extract_metadata_unified(self, url: str) -> YouTubeMetadata | None:
        """Extract metadata using Bright Data API."""
        return self._extract_metadata_bright_data(url)



    def process(
        self, input_data: Any, dry_run: bool = False, **kwargs: Any
    ) -> ProcessorResult:
        """Process YouTube URLs and extract metadata using Bright Data API Scraper."""
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

                metadata = self._extract_metadata_unified(url)
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
                f.write("If failures persist, check your Bright Data API key and quotas.\n")
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
