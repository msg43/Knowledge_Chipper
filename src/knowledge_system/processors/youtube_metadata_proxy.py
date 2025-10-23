"""
Enhanced YouTube Metadata Processor with PacketStream Proxy Support

Uses yt-dlp with PacketStream residential proxies for reliable metadata extraction
while avoiding bot detection and rate limiting.
"""

import os
import time
from datetime import datetime
from typing import Any

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

from ..utils.packetstream_proxy import PacketStreamProxyManager
from ..utils.youtube_utils import extract_urls
from .base import BaseProcessor, ProcessorResult
from .youtube_metadata import YouTubeMetadata


class YouTubeMetadataProxyProcessor(BaseProcessor):
    """Enhanced YouTube metadata processor using PacketStream proxies."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.proxy_manager = None
        self._initialize_proxy_manager()

    def _initialize_proxy_manager(self):
        """Initialize PacketStream proxy manager if credentials are available."""
        try:
            username = None
            auth_key = None

            # Try multiple methods to get PacketStream credentials

            # Method 1: From settings.api_keys (if available)
            try:
                if hasattr(self, "settings") and hasattr(self.settings, "api_keys"):
                    username = getattr(
                        self.settings.api_keys, "packetstream_username", None
                    )
                    auth_key = getattr(
                        self.settings.api_keys, "packetstream_auth_key", None
                    )
                    if username and auth_key:
                        self.logger.debug("Found PacketStream credentials in settings")
            except Exception as e:
                self.logger.debug(f"Could not load from settings: {e}")

            # Method 2: From environment variables
            if not username or not auth_key:
                env_username = os.getenv("PACKETSTREAM_USERNAME")
                env_auth_key = os.getenv("PACKETSTREAM_AUTH_KEY")
                if env_username and env_auth_key:
                    username = env_username
                    auth_key = env_auth_key
                    self.logger.debug(
                        "Found PacketStream credentials in environment variables"
                    )

            # Method 3: Try to load from config directly
            if not username or not auth_key:
                try:
                    from ..config import KnowledgeSystemConfig

                    config = KnowledgeSystemConfig()
                    if hasattr(config.api_keys, "packetstream_username") and hasattr(
                        config.api_keys, "packetstream_auth_key"
                    ):
                        config_username = config.api_keys.packetstream_username
                        config_auth_key = config.api_keys.packetstream_auth_key
                        if config_username and config_auth_key:
                            username = config_username
                            auth_key = config_auth_key
                            self.logger.debug(
                                "Found PacketStream credentials in direct config"
                            )
                except Exception as e:
                    self.logger.debug(f"Could not load from direct config: {e}")

            if username and auth_key:
                self.proxy_manager = PacketStreamProxyManager(username, auth_key)
                self.logger.info("✅ PacketStream proxy manager initialized")
            else:
                self.proxy_manager = None
                self.logger.info(
                    "PacketStream credentials not configured. Using direct connection (may be rate-limited for bulk operations)."
                )
                self.logger.info(
                    "💡 To improve reliability for bulk operations, configure PacketStream credentials in Settings > API Keys"
                )

        except Exception as e:
            self.logger.error(f"Failed to initialize PacketStream proxy manager: {e}")
            self.proxy_manager = None

    def _extract_video_id(self, url: str) -> str | None:
        """Extract YouTube video ID from URL using unified extractor."""
        from ..utils.video_id_extractor import VideoIDExtractor

        return VideoIDExtractor.extract_video_id(url)

    def _extract_metadata_with_proxy(self, url: str) -> YouTubeMetadata | None:
        """Extract YouTube metadata using yt-dlp with PacketStream proxy."""
        if not yt_dlp:
            self.logger.error("yt-dlp not installed. Install with: pip install yt-dlp")
            return None

        # Ensure URL is a plain string, not a list or other format
        if isinstance(url, list):
            self.logger.error(f"URL is a list: {url}, taking first element")
            url = url[0] if url else ""
        elif not isinstance(url, str):
            self.logger.error(f"URL is not a string: {type(url)}, converting to string")
            url = str(url)

        video_id = self._extract_video_id(url)
        if not video_id:
            self.logger.error(f"Could not extract video ID from URL: {url}")
            return None

        try:
            # Configure yt-dlp options
            from ..utils.browser_fingerprint import (
                get_standard_user_agent,
                get_standard_yt_dlp_headers,
            )

            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": False,
                "writesubtitles": False,
                "writeautomaticsub": False,
                "ignoreerrors": False,
                # No format specified - just extract metadata without downloading
                # Extract all available metadata
                "writeinfojson": False,
                "writethumbnail": False,
                # Add timeout and retry settings
                "socket_timeout": 30,
                "retries": 3,
                # Add standardized browser fingerprinting
                "user_agent": get_standard_user_agent(),
                "http_headers": get_standard_yt_dlp_headers(),
            }

            # Extract metadata with proxy session management
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    # Configure proxy for this attempt
                    current_ydl_opts = ydl_opts.copy()
                    if self.proxy_manager:
                        # Use sticky session for first attempt, rotate IP for retries
                        if attempt == 0:
                            # First attempt: use sticky session based on URL
                            session_id = PacketStreamProxyManager.generate_session_id(
                                url, video_id
                            )
                            proxy_url = self.proxy_manager.get_proxy_url(
                                session_id=session_id
                            )
                            self.logger.info(
                                f"🌐 Using PacketStream proxy session '{session_id}' for {video_id}"
                            )
                        else:
                            # Retry: use different session to rotate IP
                            retry_session_id = f"{video_id}_retry{attempt}"
                            proxy_url = self.proxy_manager.get_proxy_url(
                                session_id=retry_session_id
                            )
                            self.logger.info(
                                f"🔄 Using PacketStream retry session '{retry_session_id}' for {video_id} (attempt {attempt + 1})"
                            )

                        current_ydl_opts["proxy"] = proxy_url
                    else:
                        # No proxy available - check if strict mode prevents direct connection
                        from ..config import get_settings
                        settings = get_settings()
                        strict_mode = getattr(settings.youtube_processing, "proxy_strict_mode", True)
                        
                        if strict_mode:
                            self.logger.error(
                                f"🚫 PROXY STRICT MODE: No proxy available for {video_id}, blocking direct connection"
                            )
                            return None
                        
                        self.logger.warning(
                            f"🔗 Using direct connection for {video_id} (attempt {attempt + 1}) - strict mode disabled"
                        )

                    with yt_dlp.YoutubeDL(current_ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=False)

                    if info:
                        # Convert to our YouTubeMetadata model
                        metadata = self._convert_to_metadata_model(info, url)
                        self.logger.info(
                            f"✅ Successfully extracted metadata for {video_id}"
                        )
                        return metadata

                except yt_dlp.utils.DownloadError as e:
                    self.logger.error(f"YouTube extraction failed for {video_id}: {e}")
                    if attempt == max_retries - 1:
                        return None
                    time.sleep(2)  # Brief wait before retry

                except Exception as e:
                    self.logger.error(f"Unexpected error extracting {video_id}: {e}")
                    if attempt == max_retries - 1:
                        return None
                    time.sleep(1)

            return None

        except Exception as e:
            self.logger.error(f"Failed to extract metadata for {video_id}: {e}")
            return None

    def _convert_to_metadata_model(self, yt_info: dict, url: str) -> YouTubeMetadata:
        """Convert yt-dlp info dict to our YouTubeMetadata model."""

        # Extract duration (convert to seconds if needed)
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
            except Exception:
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
            video_id=yt_info.get("id", self._extract_video_id(url)),
            title=yt_info.get("title", ""),
            url=url,
            description=yt_info.get("description", ""),
            duration=duration,
            view_count=yt_info.get("view_count"),
            like_count=yt_info.get("like_count"),
            comment_count=yt_info.get("comment_count"),
            uploader=yt_info.get("uploader") or yt_info.get("channel"),
            uploader_id=yt_info.get("uploader_id") or yt_info.get("channel_id"),
            upload_date=upload_date,
            tags=tags,
            categories=categories,
            thumbnail_url=thumbnail_url,
            caption_availability=bool(
                yt_info.get("subtitles") or yt_info.get("automatic_captions")
            ),
            privacy_status=yt_info.get("availability", "public"),
            related_videos=related_videos,
            channel_stats=channel_stats,
            video_chapters=video_chapters,
        )

    def _parse_duration_string(self, duration_str: str) -> int | None:
        """Parse duration string to seconds."""
        if not duration_str:
            return None

        # Handle different duration formats
        if isinstance(duration_str, (int, float)):
            return int(duration_str)

        # Parse HH:MM:SS or MM:SS format
        parts = str(duration_str).split(":")
        try:
            if len(parts) == 3:  # HH:MM:SS
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            elif len(parts) == 2:  # MM:SS
                return int(parts[0]) * 60 + int(parts[1])
            else:
                return int(float(duration_str))
        except Exception:
            return None

    def process(
        self, input_data: Any, dry_run: bool = False, **kwargs: Any
    ) -> ProcessorResult:
        """Process YouTube URLs and extract metadata using PacketStream proxies."""
        start_time = time.time()

        try:
            # Extract URLs from input
            urls = extract_urls(input_data)
            if not urls:
                return ProcessorResult(
                    success=False, errors=["No valid YouTube URLs found in input"]
                )

            youtube_urls = [
                url for url in urls if "youtube.com" in url or "youtu.be" in url
            ]

            if not youtube_urls:
                return ProcessorResult(
                    success=False, errors=["No YouTube URLs found in input"]
                )

            if dry_run:
                return ProcessorResult(
                    success=True,
                    data={"message": f"Would process {len(youtube_urls)} YouTube URLs"},
                    metadata={"url_count": len(youtube_urls)},
                )

            results = []
            errors = []

            for url in youtube_urls:
                try:
                    metadata = self._extract_metadata_with_proxy(url)
                    if metadata:
                        results.append(metadata.dict())
                    else:
                        errors.append(f"Failed to extract metadata for {url}")

                except Exception as e:
                    error_msg = f"Error processing {url}: {str(e)}"
                    self.logger.error(error_msg)
                    errors.append(error_msg)

            processing_time = time.time() - start_time

            if results:
                return ProcessorResult(
                    success=True,
                    data={"metadata": results},
                    metadata={
                        "processing_time": processing_time,
                        "url_count": len(youtube_urls),
                        "success_count": len(results),
                        "error_count": len(errors),
                        "proxy_used": self.proxy_manager is not None,
                    },
                    errors=errors if errors else None,
                )
            else:
                return ProcessorResult(
                    success=False,
                    errors=errors or ["No metadata extracted from any URLs"],
                    metadata={
                        "processing_time": processing_time,
                        "url_count": len(youtube_urls),
                    },
                )

        except Exception as e:
            error_msg = f"YouTube metadata processing failed: {str(e)}"
            self.logger.error(error_msg)
            return ProcessorResult(
                success=False,
                errors=[error_msg],
                metadata={"processing_time": time.time() - start_time},
            )

        finally:
            # Cleanup proxy manager if needed
            if self.proxy_manager:
                try:
                    self.proxy_manager.cleanup()
                except Exception:
                    pass

    def validate_input(self, input_data: Any) -> bool:
        """Validate input data contains YouTube URLs."""
        if not input_data:
            return False

        # Check if input contains at least one YouTube URL
        youtube_urls = extract_urls(input_data)
        return len(youtube_urls) > 0

    @property
    def supported_formats(self) -> list[str]:
        """Return list of supported input formats."""
        return ["youtube_url", "youtube_urls", "text_with_urls"]


def test_youtube_metadata_proxy():
    """Test function for the YouTube metadata processor with PacketStream proxy."""
    processor = YouTubeMetadataProxyProcessor()

    test_urls = [
        "https://www.youtube.com/watch?v=ksHkSuNTIKo",  # Test video
        "https://youtu.be/dQw4w9WgXcQ",  # Rick Roll
    ]

    print("🎬 Testing YouTube Metadata Extraction with PacketStream Proxy")
    print("=" * 65)

    for url in test_urls:
        print(f"\n📹 Processing: {url}")
        result = processor.process(url)

        if result.success:
            metadata = result.data.get("metadata", [])
            if metadata:
                video = metadata[0]
                print("✅ Success!")
                print(f"   Title: {video.get('title', 'N/A')}")
                print(f"   Duration: {video.get('duration', 'N/A')} seconds")
                print(f"   Views: {video.get('view_count', 'N/A'):,}")
                print(f"   Uploader: {video.get('uploader', 'N/A')}")
                print(f"   Proxy used: {result.metadata.get('proxy_used', False)}")
        else:
            print(f"❌ Failed: {result.errors}")


if __name__ == "__main__":
    test_youtube_metadata_proxy()
