"""
YouTube Download Processor
YouTube Download Processor

Downloads audio and thumbnails from YouTube videos or playlists using yt-dlp.
Supports configurable output format (mp3/wav), error handling, and returns output file paths and metadata.
"""

import sys
from contextlib import contextmanager
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any

import yt_dlp

from ..config import get_settings
from ..errors import YouTubeAPIError
from ..logger import get_logger
from ..utils.deduplication import DuplicationPolicy, VideoDeduplicationService
from ..utils.youtube_utils import extract_urls, is_youtube_url
from .base import BaseProcessor, ProcessorResult

logger = get_logger(__name__)


@contextmanager
def suppress_stderr():
    """
    Capture stderr output to prevent yt-dlp from printing internal errors,
    but return the captured content for error analysis.
    """
    old_stderr = sys.stderr
    captured = StringIO()
    sys.stderr = captured
    try:
        yield captured
    finally:
        sys.stderr = old_stderr


class YouTubeDownloadProcessor(BaseProcessor):
    """Processor for downloading audio and thumbnails from YouTube videos/playlists."""

    # Class-level cookie cache to avoid reloading cookies for each instance
    _cookie_cache = None
    _cookie_cache_timestamp = 0
    _cookie_cache_ttl = 3600  # Cache cookies for 1 hour
    _cookiejar_cache = None  # Cache the actual cookiejar object

    def __init__(
        self,
        name: str | None = None,
        output_format: str = "best",  # Keep original format - will be converted to WAV for transcription
        download_thumbnails: bool = True,
        enable_cookies: bool = False,
        cookie_file_path: str | None = None,
        disable_proxies_with_cookies: bool | None = None,
    ) -> None:
        super().__init__(name or "youtube_download")
        self.output_format = output_format
        self.download_thumbnails = download_thumbnails
        self.enable_cookies = enable_cookies
        self.cookie_file_path = cookie_file_path
        self.disable_proxies_with_cookies = disable_proxies_with_cookies

        # Base options without cookies (cookies will be added dynamically if needed)
        # Session-based anti-bot settings will be applied from config
        self.ydl_opts_base = {
            "quiet": False,  # Changed to False to capture stderr messages
            "no_warnings": False,  # Changed to False to see warnings
            "noprogress": True,  # Disable yt-dlp's built-in progress to avoid parsing errors with "stalled" messages
            # OPTIMAL: Audio-only with worst quality to minimize traffic
            # Use worstaudio to get smallest available format (often m4a format 139 @ 48-50kbps)
            # Sort by ascending bitrate and sample rate to ensure we get the absolute smallest
            "format": "worstaudio[vcodec=none]/worstaudio",
            # Sort by ascending audio bitrate (+abr) and sample rate (+asr) = smallest file first
            "format_sort": ["+abr", "+asr"],
            "outtmpl": "%(title)s [%(id)s].%(ext)s",
            "ignoreerrors": True,
            "noplaylist": False,
            # Performance optimizations - optimized for stable connections
            "http_chunk_size": 524288,  # 512KB chunks - balance between efficiency and stability
            "no_check_formats": True,  # Skip format validation for faster processing
            "prefer_free_formats": True,  # Prefer formats that don't require fragmentation
            "no_part": False,  # Enable partial downloading/resuming for connection interruptions
            # Exponential backoff retry strategy (limited retries to avoid looking suspicious)
            "retries": 4,  # Retry up to 4 times (avoids infinite hammering on persistent failures)
            "retry_sleep": "3,8,15,34",  # Custom backoff sequence: 3s, 8s, 15s, 34s (total ~60s)
            "extractor_retries": 5,
            "socket_timeout": 60,  # Longer timeout to handle stalls
            "fragment_retries": 10,  # Increased fragment retries for stability
            "file_access_retries": 5,  # Retry file access operations
            # Network tuning
            "nocheckcertificate": True,
            "http_chunk_retry": True,
            "keep_fragments": False,  # Don't keep fragments to save space
            "continue": True,  # Resume partial downloads
            "no_mtime": True,  # Don't set file modification time
            # Anti-bot jitter (will be overridden by session-based settings from config)
            "sleep_interval": 8,  # Base sleep between files
            "max_sleep_interval": 25,  # Max sleep between files
            "sleep_interval_requests": 0.8,  # Sleep between HTTP requests
            # NO postprocessors - keep original format to avoid double conversion
            # Audio will be converted directly to 16kHz mono WAV by AudioProcessor
        }

    @property
    def supported_formats(self) -> list[str]:
        return [".url", ".txt"]

    def validate_input(self, input_data: Any) -> bool:
        if isinstance(input_data, (str, Path)):
            input_str = str(input_data)
            if is_youtube_url(input_str):
                return True
            if Path(input_str).exists():
                try:
                    with open(input_str, encoding="utf-8") as f:
                        return any(is_youtube_url(line.strip()) for line in f)
                except Exception:
                    pass  # nosec B110 - Legitimate file read error handling
        return False

    def _download_thumbnail_from_url(self, url: str, output_dir: Path) -> str | None:
        """Download thumbnail using centralized utility function."""
        try:
            from ..utils.youtube_utils import download_thumbnail

            return download_thumbnail(url, output_dir, use_cookies=False)
        except Exception as e:
            logger.warning(f"Failed to download thumbnail: {e}")
            return None

    def _extract_video_id(self, url: str) -> str:
        """Extract video ID from YouTube URL using unified extractor with fallback."""
        from ..utils.video_id_extractor import VideoIDExtractor

        source_id = VideoIDExtractor.extract_video_id(url)
        if source_id:
            return source_id

        # Fallback for non-standard URLs: use a hash of the URL
        import hashlib

        return hashlib.md5(url.encode(), usedforsecurity=False).hexdigest()[:8]

    def _is_rate_limited(self, error_msg: str) -> bool:
        """
        Detect if error indicates rate limiting (429/403).

        Args:
            error_msg: Error message from yt-dlp or exception

        Returns:
            True if rate limiting detected
        """
        error_lower = error_msg.lower()
        return any(
            [
                "429" in error_msg,
                "403" in error_msg,
                "too many requests" in error_lower,
                "rate limit" in error_lower,
                "throttl" in error_lower,
            ]
        )

    def _trigger_cooldown(self, progress_callback=None):
        """
        Trigger automatic cooldown when rate limiting is detected.

        Args:
            progress_callback: Optional callback for progress updates
        """
        config = get_settings()
        yt_config = config.youtube_processing

        if not yt_config.enable_auto_cooldown:
            logger.warning("⚠️ Rate limiting detected but auto-cooldown is disabled")
            return

        import random
        import time

        cooldown_minutes = random.randint(
            yt_config.cooldown_min_minutes, yt_config.cooldown_max_minutes
        )
        cooldown_seconds = cooldown_minutes * 60

        logger.warning(
            f"🛑 RATE LIMITING DETECTED - Triggering cooldown for {cooldown_minutes} minutes"
        )
        if progress_callback:
            progress_callback(
                f"🛑 Rate limited - cooling down for {cooldown_minutes} minutes..."
            )

        # Log cooldown event for tracking
        from datetime import datetime

        cooldown_end = datetime.now().timestamp() + cooldown_seconds
        logger.info(
            f"📊 Cooldown session: start={datetime.now().isoformat()}, "
            f"end={datetime.fromtimestamp(cooldown_end).isoformat()}, "
            f"duration={cooldown_minutes}min"
        )

        # Sleep with periodic progress updates
        update_interval = 60  # Update every minute
        elapsed = 0
        while elapsed < cooldown_seconds:
            time.sleep(min(update_interval, cooldown_seconds - elapsed))
            elapsed += update_interval
            remaining_minutes = (cooldown_seconds - elapsed) / 60
            if remaining_minutes > 0 and progress_callback:
                progress_callback(
                    f"⏳ Cooldown: {remaining_minutes:.0f} minutes remaining..."
                )

        logger.info("✅ Cooldown complete - resuming downloads")
        if progress_callback:
            progress_callback("✅ Cooldown complete - resuming downloads")

    def process(
        self,
        input_data: Any,
        dry_run: bool = False,
        output_dir: str | Path | None = None,
        output_format: str | None = None,
        download_thumbnails: bool | None = None,
        progress_callback=None,
        **kwargs,
    ) -> ProcessorResult:
        """
        Process YouTube URLs for audio download with smart proxy fallback.

        SECURITY FEATURE: When Bright Data proxy fails:
        - Single video downloads: Allowed with direct connection (low risk)
        - Bulk downloads (2+ URLs): Blocked to prevent YouTube IP bans

        This protects users from triggering YouTube's anti-bot detection while
        still allowing legitimate single-video use cases.
        """
        output_format = output_format or self.output_format
        download_thumbnails = (
            download_thumbnails
            if download_thumbnails is not None
            else self.download_thumbnails
        )

        # Extract optional services from kwargs
        session_manager = kwargs.get("session_manager")
        db_service = kwargs.get("db_service")
        cancellation_token = kwargs.get("cancellation_token")

        urls = extract_urls(input_data)
        if not urls:
            return ProcessorResult(
                success=False, errors=["No valid YouTube URLs found in input"]
            )

        # Apply deduplication to save costs and prevent reprocessing
        if progress_callback:
            progress_callback("🔍 Checking for duplicate videos...")

        # Initialize deduplication service
        dedup_service = VideoDeduplicationService()

        original_count = len(urls)
        unique_urls, duplicate_results = dedup_service.check_batch_duplicates(
            urls,
            DuplicationPolicy.SKIP_ALL,  # Default policy - can be made configurable
        )

        if duplicate_results:
            logger.info(
                f"🔍 Deduplication: {len(duplicate_results)} duplicates found, {len(unique_urls)} unique videos to process"
            )
            if progress_callback:
                progress_callback(
                    f"💾 Skipped {len(duplicate_results)} duplicate videos (already processed)"
                )
                for dup in duplicate_results[:3]:  # Show first 3 duplicates
                    progress_callback(f"   • {dup.source_id}: {dup.skip_reason}")
                if len(duplicate_results) > 3:
                    progress_callback(f"   • ... and {len(duplicate_results) - 3} more")

        # Update URLs to only process unique ones
        urls = unique_urls
        if not urls:
            return ProcessorResult(
                success=True,
                data={
                    "downloaded_files": [],
                    "downloaded_thumbnails": [],
                    "errors": [],
                    "duplicates_skipped": len(duplicate_results),
                    "message": "All videos were duplicates - no new downloads needed",
                },
                metadata={"duplicates_skipped": len(duplicate_results)},
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
                f"📋 Found {len(playlist_info)} playlist(s) with {total_playlist_videos} total videos:"
            )
            for i, playlist in enumerate(playlist_info, 1):
                title = playlist.get("title", "Unknown Playlist")
                video_count = playlist.get("total_videos", 0)
                logger.info(f"   {i}. {title} ({video_count} videos)")

        output_dir = Path(output_dir) if output_dir else Path.cwd()
        output_dir.mkdir(parents=True, exist_ok=True)

        # Create Thumbnails subdirectory for consistent organization
        thumbnails_dir = output_dir / "Thumbnails"
        thumbnails_dir.mkdir(exist_ok=True)

        # PROXY CONFIGURATION - PacketStream (optional)
        from ..config import get_settings
        from ..utils.packetstream_proxy import PacketStreamProxyManager

        settings = get_settings()
        yt_config = settings.youtube_processing

        # Note: VideoDeduplicationService already initialized at line 170
        # No need to reinitialize here

        # Check if we should disable proxies due to cookie usage
        # Use instance variables if available, otherwise fall back to config
        enable_cookies_check = (
            self.enable_cookies
            if hasattr(self, "enable_cookies")
            else yt_config.enable_cookies
        )
        # CRITICAL: Check instance variable first (from GUI), then fall back to config
        disable_proxies_check = (
            self.disable_proxies_with_cookies
            if self.disable_proxies_with_cookies is not None
            else yt_config.disable_proxies_with_cookies
        )

        # DIAGNOSTIC LOGGING
        logger.info(f"🔍 Proxy/Cookie Decision Point:")
        logger.info(f"   self.enable_cookies = {self.enable_cookies}")
        logger.info(f"   self.cookie_file_path = {self.cookie_file_path}")
        logger.info(
            f"   self.disable_proxies_with_cookies = {self.disable_proxies_with_cookies}"
        )
        logger.info(f"   enable_cookies_check = {enable_cookies_check}")
        logger.info(f"   disable_proxies_check = {disable_proxies_check}")
        logger.info(
            f"   Decision: {'DISABLE PROXIES' if (enable_cookies_check and disable_proxies_check) else 'USE PROXIES'}"
        )

        if enable_cookies_check and disable_proxies_check:
            use_proxy = False
            proxy_manager = None
            proxy_url = None
            logger.info(
                "🏠 Cookies enabled - using direct connection (home IP) as configured"
            )
            if progress_callback:
                progress_callback("🏠 Using cookies with home IP (proxies disabled)")
        else:
            # PacketStream proxy (optional)
            use_proxy = False
            proxy_manager = None
            proxy_url = None

            try:
                proxy_manager = PacketStreamProxyManager()
                if proxy_manager.username and proxy_manager.auth_key:
                    use_proxy = True
                    logger.info(
                        "🌐 Using PacketStream residential proxies for YouTube processing"
                    )
                    if progress_callback:
                        progress_callback("🌐 Using PacketStream residential proxies...")
                else:
                    logger.warning("⚠️ PACKETSTREAM CREDENTIALS NOT CONFIGURED")
                    logger.warning(
                        "⚠️ Using direct access - YouTube may block bulk downloads!"
                    )
                    if progress_callback:
                        progress_callback(
                            "⚠️ PacketStream not configured - risk of YouTube blocking..."
                        )
            except Exception as e:
                logger.warning(f"⚠️ PACKETSTREAM PROXY NOT AVAILABLE: {e}")
                logger.warning(
                    "⚠️ Using direct access - YouTube may trigger anti-bot detection for downloads!"
                )
                logger.warning(
                    "⚠️ For reliable bulk downloads, configure PacketStream in Settings > API Keys"
                )
                if progress_callback:
                    progress_callback(
                        "⚠️ PacketStream proxy not configured - using direct access (may be blocked)..."
                    )

        # Note: PacketStream is optional - we can proceed without it (but may get rate limited)

        # PROXY CONFIGURATION
        # Note: Proxy is configured and will be tested per-URL
        # Each URL gets unique session ID for IP rotation

        if use_proxy and proxy_manager:
            logger.info("✅ Using PacketStream proxy for downloads")
            if progress_callback:
                progress_callback("✅ PacketStream proxy configured")

        # Proxy usage with PacketStream (optional); no legacy WebShare fallback

        # Configure base yt-dlp options
        import copy
        import random

        ydl_opts = copy.deepcopy(
            self.ydl_opts_base
        )  # Deep copy to avoid modifying base config

        # Apply session-based anti-bot configuration from settings
        config = get_settings()
        yt_config = config.youtube_processing

        if yt_config.enable_session_based_downloads:
            # Apply randomized rate limiting
            rate_limit = random.uniform(
                yt_config.rate_limit_min_mbps, yt_config.rate_limit_max_mbps
            )
            ydl_opts["ratelimit"] = int(
                rate_limit * 1024 * 1024
            )  # Convert MB/s to bytes/s

            # Apply randomized jitter between files and requests
            sleep_interval = random.randint(
                yt_config.sleep_interval_min, yt_config.sleep_interval_max
            )
            ydl_opts["sleep_interval"] = sleep_interval
            ydl_opts["max_sleep_interval"] = sleep_interval + random.randint(3, 12)
            ydl_opts["sleep_interval_requests"] = yt_config.sleep_requests

            # Apply download archive if enabled
            if yt_config.use_download_archive:
                archive_path = Path(yt_config.download_archive_path).expanduser()
                archive_path.parent.mkdir(parents=True, exist_ok=True)
                ydl_opts["download_archive"] = str(archive_path)

            logger.info(
                f"🛡️ Session-based anti-bot: rate={rate_limit:.2f}MB/s, "
                f"sleep={sleep_interval}-{ydl_opts['max_sleep_interval']}s, "
                f"sleep_requests={yt_config.sleep_requests}s"
            )

        # Add cookies if enabled (file upload only - browser extraction disabled for security)
        # Use instance variables passed during initialization, not config file
        logger.info(f"🔍 Cookie File Check:")
        logger.info(f"   self.enable_cookies = {self.enable_cookies}")
        logger.info(f"   self.cookie_file_path = {self.cookie_file_path}")

        if self.enable_cookies and self.cookie_file_path:
            cookie_path = Path(self.cookie_file_path)
            logger.info(f"   Cookie file exists: {cookie_path.exists()}")
            if cookie_path.exists():
                logger.info(f"   Cookie file size: {cookie_path.stat().st_size} bytes")
                ydl_opts["cookiefile"] = self.cookie_file_path
                logger.info(f"✅ Using cookies from file: {self.cookie_file_path}")
                logger.info(
                    f"✅ yt-dlp cookiefile option set to: {ydl_opts.get('cookiefile')}"
                )

                # NOTE: Keep session-based jitter even with cookies for better anti-bot protection
                # Old behavior was to disable ALL sleep intervals with cookies, but research shows
                # that jitter is MORE effective than rigid delays, even with authenticated requests
                logger.info(
                    f"✅ Using session-based jitter with authenticated cookies (better anti-bot)"
                )

                # Use tv_embedded client for most reliable format listings
                # tv_embedded exposes classic DASH entries and is less impacted by SABR-only manifests
                # Standard web client increasingly returns SABR-only which can hide formats
                # tv_embedded provides more complete format availability for audio-only extraction
                ydl_opts["extractor_args"] = {
                    "youtube": {
                        "player_client": [
                            "tv_embedded",  # Most reliable for DASH format listings
                            "android",  # Fallback if tv_embedded fails
                            "web",  # Last resort fallback
                        ],
                        "player_skip": ["configs"],  # Skip unnecessary config downloads
                    }
                }
                logger.info(
                    f"✅ Configured yt-dlp to use tv_embedded client (most reliable for audio-only DASH formats)"
                )

                if progress_callback:
                    progress_callback(f"🍪 Using cookies from throwaway account")
            else:
                logger.warning(f"⚠️ Cookie file not found: {self.cookie_file_path}")
                if progress_callback:
                    progress_callback(
                        f"⚠️ Cookie file not found - proceeding without cookies"
                    )
        else:
            logger.info(f"   Cookies NOT enabled or no cookie file path provided")

        # NOTE: Do NOT add custom user-agent or http_headers when using PacketStream
        # PacketStream residential proxies work best with yt-dlp's default headers
        # Custom headers can cause "Failed to parse JSON" errors through the proxy

        # Add progress hook for real-time download progress in GUI
        if progress_callback:
            import time

            last_progress_time = [time.time()]  # Use list for mutable reference
            last_status_message_time = [0.0]  # Track when we last showed status message

            # Track last progress for updating single line
            last_progress_message = ""

            def download_progress_hook(d):
                """Hook to capture yt-dlp download progress and forward to GUI with diagnostic info."""
                nonlocal last_progress_message
                current_time = time.time()

                if d["status"] == "downloading":
                    try:
                        # Extract progress information with error handling for string values
                        downloaded_bytes = d.get("downloaded_bytes", 0)
                        total_bytes = d.get("total_bytes") or d.get(
                            "total_bytes_estimate", 0
                        )
                        speed = d.get("speed", 0)
                        filename = d.get("filename", "Unknown file")

                        # Ensure values are numeric (yt-dlp sometimes returns strings like "stalled - retrying...")
                        if not isinstance(downloaded_bytes, (int, float)):
                            downloaded_bytes = 0
                        if not isinstance(total_bytes, (int, float)):
                            total_bytes = 0
                        if not isinstance(speed, (int, float)):
                            speed = 0

                        # Initialize variables for progress display
                        percent = 0
                        downloaded_mb = 0
                        total_mb = 0
                        speed_mbps = 0

                        if total_bytes > 0:
                            percent = (downloaded_bytes / total_bytes) * 100
                            downloaded_mb = downloaded_bytes / (1024 * 1024)
                            total_mb = total_bytes / (1024 * 1024)
                            speed_mbps = (speed / (1024 * 1024)) if speed else 0

                        # Extract just the filename for cleaner display
                        import os

                        clean_filename = os.path.basename(filename)

                        # Create single line progress message with all info
                        progress_msg = f"📥 Downloading: {clean_filename[:30]}{'...' if len(clean_filename) > 30 else ''} | {downloaded_mb:.1f}/{total_mb:.1f} MB ({percent:.1f}%)"

                        # Add speed information if available
                        time_since_last = current_time - last_progress_time[0]
                        if speed_mbps > 0:
                            progress_msg += f" @ {speed_mbps:.1f} MB/s"
                        elif time_since_last > 10:  # No progress for 10+ seconds
                            progress_msg += " (stalled - retrying...)"
                        else:
                            progress_msg += " (buffering...)"

                        # Use single line update if message changed significantly
                        if (
                            not last_progress_message
                            or abs(
                                percent
                                - float(
                                    last_progress_message.split("(")[-1].split("%")[0]
                                    if "(" in last_progress_message
                                    else 0
                                )
                            )
                            > 1
                        ):
                            # Pass both message and percentage for progress bar updates
                            progress_callback(progress_msg, int(percent))
                            last_progress_message = progress_msg
                        last_progress_time[0] = current_time

                    except (TypeError, ValueError, ZeroDivisionError) as e:
                        # Handle any parsing errors gracefully (e.g. when yt-dlp returns string values)
                        # Only show status message once every 5 seconds to avoid spam
                        logger.debug(f"Progress hook parsing error (non-critical): {e}")
                        if current_time - last_status_message_time[0] > 5.0:
                            progress_callback("⏳ Downloading... (checking status)")
                            last_status_message_time[0] = current_time

                elif d["status"] == "finished":
                    filename = d.get("filename", "Unknown file")
                    import os

                    clean_filename = os.path.basename(filename)

                    # Verify the file actually exists
                    if filename and Path(filename).exists():
                        # Pass 100% to indicate download complete
                        progress_callback(
                            f"✅ Download complete: {clean_filename[:50]}{'...' if len(clean_filename) > 50 else ''}",
                            100,
                        )
                    else:
                        logger.error(
                            f"Progress hook reported 'finished' but file does not exist: {filename}"
                        )
                        # Don't show success message if file doesn't exist
                elif d["status"] == "error":
                    error_msg = d.get("error", "Unknown error")
                    if "timeout" in error_msg.lower():
                        progress_callback(
                            "⏱️ Download timeout - retrying (YouTube may be throttling)..."
                        )
                    elif "connection" in error_msg.lower():
                        progress_callback("🔗 Connection issue - retrying...")
                    else:
                        progress_callback(f"❌ Download error: {error_msg}")

            ydl_opts["progress_hooks"] = [download_progress_hook]

        # No postprocessor override needed - keeping original format
        ydl_opts["outtmpl"] = str(output_dir / "%(title)s [%(id)s].%(ext)s")

        # DIAGNOSTIC: Log the actual format string being used
        logger.info(f"🔍 yt-dlp format string: {ydl_opts.get('format', 'NOT SET')}")
        if "extractor_args" in ydl_opts:
            logger.info(f"🔍 yt-dlp extractor_args: {ydl_opts['extractor_args']}")

        all_files = []
        all_thumbnails = []
        errors = []

        import random
        import time

        # Single-use IP strategy: Each video gets a unique IP with staggered delays
        # No retries - fail fast and move to next video
        urls_to_process = list(urls)
        url_index = 0

        while url_index < len(urls_to_process):
            # Check for cancellation at the start of each iteration
            if cancellation_token and cancellation_token.is_cancelled():
                logger.info("Download cancelled by user - stopping gracefully")
                if progress_callback:
                    progress_callback("⏹ Download cancelled by user")
                break

            url = urls_to_process[url_index]
            i = url_index + 1
            source_id = None  # Initialize early for error handling

            try:
                # Determine playlist context for progress display
                playlist_context = ""
                for playlist in playlist_info:
                    if playlist["start_index"] <= (i - 1) <= playlist["end_index"]:
                        playlist_position = (i - 1) - playlist["start_index"] + 1
                        playlist_context = f" [Playlist: {playlist['title'][:40]}{'...' if len(playlist['title']) > 40 else ''} - Video {playlist_position}/{playlist['total_videos']}]"
                        break

                # Extract video ID for logging
                import re

                youtube_id_match = re.search(
                    r"(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})", url
                )
                if youtube_id_match:
                    source_id = youtube_id_match.group(1)

                # Single-use IP strategy: Generate unique session ID for each video
                current_proxy_url = None
                session_id = None  # Initialize session_id
                if use_proxy and proxy_manager:
                    from ..utils.packetstream_proxy import PacketStreamProxyManager

                    # Generate unique session ID for this video (single-use IP)
                    # Add timestamp and random component to ensure uniqueness
                    session_id = PacketStreamProxyManager.generate_session_id(
                        url, source_id
                    )
                    # Make it truly unique by adding timestamp
                    session_id = (
                        f"{session_id}_{int(time.time())}_{random.randint(1000, 9999)}"
                    )

                    current_proxy_url = proxy_manager.get_proxy_url(
                        session_id=session_id
                    )

                if current_proxy_url and source_id and session_id:
                    logger.info(
                        f"Using PacketStream proxy session '{session_id}' for video {source_id} ({i}/{len(urls)})"
                    )
                    logger.info(
                        f"Proxy URL format: {current_proxy_url.split('@')[0]}@***"
                    )
                elif current_proxy_url:
                    logger.info(f"Using PacketStream proxy for URL ({i}/{len(urls)})")
                    logger.info(
                        f"Proxy URL format: {current_proxy_url.split('@')[0]}@***"
                    )
                elif source_id:
                    logger.info(
                        f"Using direct connection for video {source_id} (no proxy configured)"
                    )

                # Extract metadata to verify video availability
                if progress_callback:
                    progress_callback(f"🔍 Extracting video metadata for: {url}")

                # Track metadata and audio download success separately
                metadata_extracted = False
                metadata_error = None
                audio_downloaded_successfully = False
                audio_file_path_for_db = None
                audio_file_size = None
                audio_file_format = None

                try:
                    # Test proxy connectivity and extract metadata
                    # IMPORTANT: Include full ydl_opts (cookies, Android client, etc)
                    test_opts = {**ydl_opts, "proxy": current_proxy_url}
                    test_opts.update(
                        {
                            "quiet": True,
                            "no_warnings": True,
                            "extract_flat": True,
                            "socket_timeout": 30,
                        }
                    )

                    proxy_type = "PacketStream" if use_proxy else "Direct (NO PROXY)"
                    with yt_dlp.YoutubeDL(test_opts) as ydl_test:
                        logger.info(f"Testing {proxy_type} connectivity for: {url}")
                        if progress_callback and not use_proxy:
                            progress_callback(
                                "⚠️ WARNING: Using direct connection (no proxy protection)"
                            )
                        if progress_callback:
                            progress_callback(f"🔗 Testing {proxy_type} connectivity...")

                        # Quick connectivity test
                        test_info = ydl_test.extract_info(url, download=False)
                        if not test_info:
                            raise Exception(
                                "Connectivity test failed - no video info returned"
                            )

                        logger.info(f"✅ {proxy_type} connectivity test passed")
                        if progress_callback:
                            progress_callback(
                                f"✅ {proxy_type} working - extracting metadata..."
                            )

                    # Extract full metadata (without format validation to avoid proxy issues)
                    # IMPORTANT: Merge full ydl_opts (with cookies, Android client, etc)
                    metadata_opts = {**ydl_opts, "proxy": current_proxy_url}
                    metadata_opts.update(
                        {
                            "quiet": True,
                            "no_warnings": True,
                            "socket_timeout": 30,
                        }
                    )
                    with yt_dlp.YoutubeDL(metadata_opts) as ydl_info:
                        info_only = ydl_info.extract_info(url, download=False)
                        if info_only:
                            duration_seconds = info_only.get("duration", 0)
                            duration_minutes = (
                                duration_seconds / 60 if duration_seconds else 0
                            )
                            video_title = info_only.get("title", "Unknown Title")

                            logger.info(
                                f"✅ Video '{video_title}' - Duration: {duration_minutes:.1f}min"
                            )

                            if progress_callback:
                                progress_callback(
                                    f"📊 '{video_title[:40]}...' - {duration_minutes:.1f} min"
                                )

                            # Mark metadata as successfully extracted
                            metadata_extracted = True

                except Exception as e:
                    error_msg = str(e)
                    metadata_error = error_msg
                    logger.error(f"❌ Metadata extraction failed for {url}: {error_msg}")

                    # Check for bot detection, blocking, or proxy errors - don't continue if detected
                    is_bot_detection = any(
                        keyword in error_msg.lower()
                        for keyword in [
                            "sign in to confirm you're not a bot",
                            "bot",
                            "captcha",
                            "verify you're human",
                        ]
                    )
                    is_blocked = "403" in error_msg or "forbidden" in error_msg.lower()
                    is_not_found = (
                        "404" in error_msg or "not found" in error_msg.lower()
                    )
                    is_proxy_error = any(
                        keyword in error_msg.lower()
                        for keyword in [
                            "502",
                            "proxy error",
                            "unable to connect to proxy",
                            "tunnel connection failed",
                            "relay is offline",
                        ]
                    )

                    if progress_callback:
                        if is_bot_detection:
                            progress_callback(
                                "❌ Bot detection triggered - YouTube is blocking access"
                            )
                        elif is_blocked:
                            progress_callback(
                                "❌ Access denied (403) - YouTube may be blocking this IP"
                            )
                        elif is_not_found:
                            progress_callback(f"❌ Video not found or private: {url}")
                        elif is_proxy_error:
                            progress_callback(
                                "❌ Proxy relay offline/failed - will retry with different relay"
                            )
                        elif "timeout" in error_msg.lower():
                            progress_callback(
                                "❌ Connection timeout - Proxy service may have connectivity issues"
                            )
                        elif "proxy" in error_msg.lower():
                            progress_callback(
                                "❌ Proxy error: Check proxy credentials and account status"
                            )
                        else:
                            progress_callback(
                                f"❌ Metadata extraction failed: {error_msg}"
                            )

                    # Don't continue if bot detection, blocking, or proxy error occurred
                    # These are retryable errors - let the GUI's retry logic handle them
                    if is_bot_detection or is_blocked or is_proxy_error:
                        logger.error(
                            f"❌ Stopping download attempt - retryable error detected for {url}"
                        )
                        if progress_callback:
                            progress_callback(
                                "🚫 Skipping download - will retry with new session/IP"
                            )

                        # Mark as failed and skip to next URL
                        errors.append(f"Retryable error for {url}: {error_msg}")
                        url_index += 1
                        continue  # Skip to next URL

                # Attempt the actual download
                if progress_callback:
                    progress_callback("🚀 Starting download...")

                # Configure yt-dlp options with the specific proxy for this video
                final_ydl_opts = {**ydl_opts, "proxy": current_proxy_url}

                # Suppress yt-dlp's stderr output to prevent spurious error messages like "ERROR: 'webm'"
                # But capture it for error analysis
                with suppress_stderr() as captured_stderr:
                    with yt_dlp.YoutubeDL(final_ydl_opts) as ydl:
                        logger.info(f"Downloading audio for: {url}{playlist_context}")
                        if use_proxy and source_id:
                            logger.info(
                                f"Using PacketStream proxy for video {source_id}"
                            )

                        try:
                            # Track download start time for cost calculation
                            download_start_time = datetime.now()

                            info = ydl.extract_info(url, download=True)

                            # Log selected format to help debug unexpected video downloads
                            if info:
                                format_id = info.get("format_id", "unknown")
                                format_note = info.get("format_note", "")
                                ext = info.get("ext", "unknown")
                                vcodec = info.get("vcodec", "none")
                                acodec = info.get("acodec", "none")
                                filesize = info.get("filesize") or info.get(
                                    "filesize_approx", 0
                                )

                                # Determine if this is audio-only or includes video
                                is_audio_only = vcodec == "none" or vcodec is None
                                format_type = (
                                    "audio-only" if is_audio_only else "VIDEO+AUDIO"
                                )

                                if is_audio_only:
                                    logger.info(
                                        f"✅ Downloaded {format_type}: format={format_id} ({format_note}), "
                                        f"ext={ext}, codec={acodec}, size={filesize/1024/1024:.1f}MB"
                                    )
                                else:
                                    logger.warning(
                                        f"⚠️  Downloaded {format_type} (fallback): format={format_id} ({format_note}), "
                                        f"ext={ext}, vcodec={vcodec}, acodec={acodec}, size={filesize/1024/1024:.1f}MB"
                                    )
                                    logger.warning(
                                        f"⚠️  No audio-only format available - fell back to video. "
                                        f"Audio will be extracted during transcription."
                                    )

                            # Track whether files were already added (for info is None case)
                            files_already_tracked = False

                            # Check for stderr errors even when yt-dlp returns info
                            stderr_output = (
                                captured_stderr.getvalue() if captured_stderr else ""
                            )
                            download_failed = False
                            if stderr_output:
                                # Log all stderr output for debugging
                                logger.info(f"yt-dlp stderr output: {stderr_output}")

                                # Only treat as error if it's an actual ERROR line, not just warnings
                                # Check for lines starting with "ERROR:" (actual errors)
                                stderr_lines = stderr_output.strip().split("\n")
                                has_actual_error = any(
                                    line.strip().startswith("ERROR:")
                                    for line in stderr_lines
                                )

                                if has_actual_error:
                                    logger.error(
                                        f"yt-dlp error detected: {stderr_output}"
                                    )
                                    download_failed = True
                                else:
                                    logger.debug(
                                        f"yt-dlp warnings (non-fatal): {stderr_output}"
                                    )

                            # If download failed, treat as if info is None
                            if download_failed:
                                logger.error(
                                    f"Download failed with error in stderr, treating as failed download for {url}"
                                )
                                info = None

                            # Log the info dict structure for debugging
                            if info:
                                logger.debug(f"yt-dlp info keys: {list(info.keys())}")
                                if "entries" in info and info["entries"]:
                                    logger.debug(
                                        f"Found {len(info['entries'])} entries"
                                    )
                                    for entry in info["entries"][
                                        :1
                                    ]:  # Log first entry only
                                        logger.debug(
                                            f"First entry keys: {list(entry.keys())}"
                                        )
                                        logger.debug(
                                            f"First entry title: {entry.get('title', 'N/A')}"
                                        )

                            if info is None:
                                # yt-dlp returned None - check if files were actually downloaded
                                # Sometimes yt-dlp returns None after successful post-processing
                                # Look for any common audio formats since the actual format depends on YouTube's availability
                                logger.warning(
                                    f"yt-dlp returned None for {url}, searching for downloaded files in {output_dir}"
                                )
                                downloaded_files = []
                                for ext in ["m4a", "opus", "webm", "ogg", "mp3", "aac"]:
                                    found = list(output_dir.glob(f"*.{ext}"))
                                    logger.debug(
                                        f"   Searching *.{ext}: found {len(found)} files"
                                    )
                                    # Only include files modified AFTER download started
                                    for file_path in found:
                                        file_mtime = datetime.fromtimestamp(
                                            file_path.stat().st_mtime
                                        )
                                        if file_mtime >= download_start_time:
                                            downloaded_files.append(file_path)
                                            logger.debug(
                                                f"   Found newly downloaded file: {file_path.name} (modified {file_mtime})"
                                            )
                                        else:
                                            logger.debug(
                                                f"   Skipping old file: {file_path.name} (modified {file_mtime}, before download start {download_start_time})"
                                            )

                                # Also check all files in directory for debugging
                                all_dir_files = list(output_dir.glob("*"))
                                logger.debug(
                                    f"   Total files in {output_dir}: {[f.name for f in all_dir_files if f.is_file()]}"
                                )

                                if downloaded_files:
                                    # Files exist! This is a false negative - download succeeded
                                    logger.warning(
                                        f"yt-dlp returned None but files were downloaded for {url}"
                                    )
                                    if progress_callback:
                                        progress_callback(
                                            "✅ Audio download completed successfully"
                                        )
                                    # Add files directly to results since we have them
                                    for file_path in downloaded_files:
                                        all_files.append(str(file_path))
                                        logger.info(
                                            f"   Found downloaded file: {file_path.name}"
                                        )
                                        # Track audio file info for database
                                        audio_downloaded_successfully = True
                                        audio_file_path_for_db = str(file_path)
                                        if file_path.exists():
                                            audio_file_size = file_path.stat().st_size
                                            audio_file_format = file_path.suffix[
                                                1:
                                            ]  # Remove the dot

                                    # Mark files as already tracked to skip duplicate processing
                                    files_already_tracked = True

                                    # Create minimal info dict for database/thumbnail processing only
                                    info = {
                                        "title": downloaded_files[
                                            0
                                        ].stem,  # Use filename as title
                                        "id": source_id or "unknown",
                                        "ext": downloaded_files[0].suffix[
                                            1:
                                        ],  # Extension without dot
                                    }
                                else:
                                    # No files found - this is a real error
                                    # Check if we captured any stderr output from yt-dlp
                                    stderr_output = (
                                        captured_stderr.getvalue()
                                        if captured_stderr
                                        else ""
                                    )

                                    # Log captured stderr for debugging
                                    if stderr_output:
                                        logger.error(
                                            f"Captured stderr from yt-dlp for {url}:\n{stderr_output}"
                                        )
                                        # Extract the actual error message from stderr
                                        error_lines = [
                                            line
                                            for line in stderr_output.split("\n")
                                            if line.strip()
                                        ]
                                        if error_lines:
                                            error_msg = error_lines[
                                                0
                                            ]  # First non-empty line usually has the main error
                                        else:
                                            error_msg = "yt-dlp failed to download video (no error message captured)"
                                    else:
                                        error_msg = "Failed to extract any player response; please report this issue on  https://github.com/yt-dlp/yt-dlp/issues?q= , filling out the appropriate issue template. Confirm you are on the latest version using  yt-dlp -U"

                                    logger.error(
                                        f"No info extracted for {url}: {error_msg}"
                                    )

                                    # Provide user-friendly error message
                                    if progress_callback:
                                        if (
                                            "bot" in error_msg.lower()
                                            or "sign in" in error_msg.lower()
                                        ):
                                            progress_callback(
                                                "❌ YouTube bot detection - video blocked. Try again later or use different proxy."
                                            )
                                        elif (
                                            "403" in error_msg
                                            or "forbidden" in error_msg.lower()
                                        ):
                                            progress_callback(
                                                "❌ Access denied - YouTube may be blocking this proxy IP"
                                            )
                                        else:
                                            progress_callback(
                                                f"❌ Failed to download: {error_msg[:100]}"
                                            )
                                    # Raise exception to be caught by outer handler which adds to errors list
                                    raise Exception(error_msg)

                            # Calculate download metrics for cost tracking
                            download_end_time = datetime.now()
                            download_duration = (
                                download_end_time - download_start_time
                            ).total_seconds()

                            # PacketStream proxies do not require usage tracking (flat rate)

                            # Register video in database - MANDATORY for tracking
                            # Without database entry, downloaded files are orphaned and unusable
                            if source_id and db_service:
                                try:
                                    video_title = (
                                        info.get("title", "Unknown Title")
                                        if info
                                        else "Unknown Title"
                                    )

                                    # Extract all available metadata from info dict
                                    tags = info.get("tags", []) or []
                                    logger.debug(
                                        f"📝 Extracted {len(tags)} tags from YouTube for {source_id}"
                                    )
                                    if tags:
                                        logger.debug(f"First 5 tags: {tags[:5]}")

                                    video_metadata = {
                                        "uploader": info.get("uploader", ""),
                                        "uploader_id": info.get("uploader_id", ""),
                                        "upload_date": info.get("upload_date", ""),
                                        "description": info.get("description", ""),
                                        "duration_seconds": info.get("duration"),
                                        "view_count": info.get("view_count"),
                                        "like_count": info.get("like_count"),
                                        "comment_count": info.get("comment_count"),
                                        "tags_json": tags,
                                        "categories_json": info.get("categories", []),
                                        "thumbnail_url": info.get("thumbnail", ""),
                                        "source_type": "youtube",
                                        "status": (
                                            "completed"
                                            if (
                                                audio_downloaded_successfully
                                                and metadata_extracted
                                            )
                                            else "partial"
                                        ),
                                        # Note: extraction_method removed - not a MediaSource field
                                        # It belongs to MOCExtraction model
                                    }

                                    # Create or update video record with full metadata
                                    video = db_service.create_source(
                                        video_id=source_id,
                                        title=video_title,
                                        url=url,
                                        **video_metadata,
                                    )

                                    if not video:
                                        raise Exception(
                                            "Database create_video returned None"
                                        )

                                    # Update audio download status
                                    if audio_downloaded_successfully:
                                        db_service.update_audio_status(
                                            video_id=source_id,
                                            audio_file_path=audio_file_path_for_db,
                                            audio_downloaded=True,
                                            audio_file_size_bytes=audio_file_size,
                                            audio_format=audio_file_format,
                                        )

                                    # Update metadata status
                                    db_service.update_metadata_status(
                                        video_id=source_id,
                                        metadata_complete=metadata_extracted,
                                    )

                                    # Mark for retry if either component failed
                                    if (
                                        not audio_downloaded_successfully
                                        or not metadata_extracted
                                    ):
                                        db_service.mark_for_retry(
                                            video_id=source_id,
                                            needs_metadata_retry=not metadata_extracted,
                                            needs_audio_retry=not audio_downloaded_successfully,
                                            failure_reason=(
                                                f"Metadata: {'OK' if metadata_extracted else metadata_error or 'Failed'}; "
                                                f"Audio: {'OK' if audio_downloaded_successfully else 'Failed'}"
                                            ),
                                        )

                                    logger.info(
                                        f"Registered video {source_id} in database: "
                                        f"audio={audio_downloaded_successfully}, metadata={metadata_extracted}"
                                    )

                                except Exception as db_error:
                                    # CRITICAL: Database write failure means we can't track this download
                                    # Clean up the audio file and fail the download
                                    logger.error(
                                        f"CRITICAL: Failed to register video {source_id} in database: {db_error}"
                                    )

                                    # Clean up downloaded audio file (orphaned without database entry)
                                    if (
                                        audio_file_path_for_db
                                        and Path(audio_file_path_for_db).exists()
                                    ):
                                        try:
                                            Path(audio_file_path_for_db).unlink()
                                            logger.info(
                                                f"Cleaned up orphaned audio file: {audio_file_path_for_db}"
                                            )
                                        except Exception as cleanup_error:
                                            logger.error(
                                                f"Failed to clean up orphaned file: {cleanup_error}"
                                            )

                                    # Raise exception to mark this download as failed
                                    raise Exception(
                                        f"Database write failed - cannot track download: {db_error}"
                                    )
                            elif source_id and not db_service:
                                # No database service available - this is a critical error
                                logger.error(
                                    "CRITICAL: No database service available - cannot track downloads"
                                )
                                # Clean up audio file
                                if (
                                    audio_file_path_for_db
                                    and Path(audio_file_path_for_db).exists()
                                ):
                                    try:
                                        Path(audio_file_path_for_db).unlink()
                                        logger.info(
                                            f"Cleaned up orphaned audio file: {audio_file_path_for_db}"
                                        )
                                    except Exception as cleanup_error:
                                        logger.error(
                                            f"Failed to clean up orphaned file: {cleanup_error}"
                                        )
                                raise Exception(
                                    "No database service available - cannot track downloads"
                                )

                            logger.info(f"✅ Successfully downloaded audio for: {url}")
                            if progress_callback:
                                progress_callback(
                                    "✅ Audio download completed successfully"
                                )

                            # Process entries (handle both playlists and single videos)
                            # Skip file tracking if already done in the info is None case
                            if not files_already_tracked:
                                if "entries" in info and info["entries"]:
                                    entries = info["entries"]
                                else:
                                    entries = [info]

                                for entry in entries:
                                    if entry and "title" in entry:
                                        # Log selected format for this entry
                                        entry_format_id = entry.get(
                                            "format_id", "unknown"
                                        )
                                        entry_format_note = entry.get("format_note", "")
                                        entry_ext = entry.get("ext", "unknown")
                                        entry_vcodec = entry.get("vcodec", "none")
                                        entry_acodec = entry.get("acodec", "none")
                                        entry_filesize = entry.get(
                                            "filesize"
                                        ) or entry.get("filesize_approx", 0)

                                        entry_is_audio_only = (
                                            entry_vcodec == "none"
                                            or entry_vcodec is None
                                        )
                                        entry_format_type = (
                                            "audio-only"
                                            if entry_is_audio_only
                                            else "VIDEO+AUDIO"
                                        )

                                        if entry_is_audio_only:
                                            logger.info(
                                                f"✅ Downloaded {entry_format_type}: {entry.get('title', 'N/A')[:50]} | "
                                                f"format={entry_format_id} ({entry_format_note}), ext={entry_ext}, codec={entry_acodec}, "
                                                f"size={entry_filesize/1024/1024:.1f}MB"
                                            )
                                        else:
                                            logger.warning(
                                                f"⚠️  Downloaded {entry_format_type} (fallback): {entry.get('title', 'N/A')[:50]} | "
                                                f"format={entry_format_id} ({entry_format_note}), ext={entry_ext}, "
                                                f"vcodec={entry_vcodec}, acodec={entry_acodec}, size={entry_filesize/1024/1024:.1f}MB"
                                            )
                                            logger.warning(
                                                f"⚠️  No audio-only format available - fell back to video. "
                                                f"Audio will be extracted during transcription."
                                            )

                                        # Get actual filename from yt-dlp
                                        filename = None

                                        logger.debug(
                                            f"Processing entry: {entry.get('title', 'N/A')}"
                                        )
                                        logger.debug(
                                            f"Entry keys: {list(entry.keys())}"
                                        )

                                        # Try to get filename from requested_downloads
                                        if (
                                            "requested_downloads" in entry
                                            and entry["requested_downloads"]
                                        ):
                                            logger.debug(
                                                f"Found requested_downloads with {len(entry['requested_downloads'])} items"
                                            )
                                            filename = entry["requested_downloads"][
                                                0
                                            ].get("filepath") or entry[
                                                "requested_downloads"
                                            ][
                                                0
                                            ].get(
                                                "filename"
                                            )
                                            logger.debug(
                                                f"Filename from requested_downloads: {filename}"
                                            )

                                        # Try to get extension from entry
                                        if not filename and "ext" in entry:
                                            potential_filename = (
                                                output_dir
                                                / f"{entry['title']}.{entry['ext']}"
                                            )
                                            # Only use this filename if it actually exists
                                            if potential_filename.exists():
                                                filename = potential_filename
                                            else:
                                                logger.warning(
                                                    f"Expected file not found: {potential_filename.name}"
                                                )

                                        # Last resort: search for any file with this title
                                        if not filename:
                                            title = entry["title"]
                                            for ext in [
                                                "m4a",
                                                "opus",
                                                "webm",
                                                "ogg",
                                                "mp3",
                                                "aac",
                                            ]:
                                                potential_file = (
                                                    output_dir / f"{title}.{ext}"
                                                )
                                                if potential_file.exists():
                                                    filename = potential_file
                                                    break

                                            # If still not found, search for any audio file in output_dir
                                            if not filename:
                                                logger.warning(
                                                    f"Could not find file for title '{title}', searching all audio files in {output_dir}"
                                                )
                                                for ext in [
                                                    "m4a",
                                                    "opus",
                                                    "webm",
                                                    "ogg",
                                                    "mp3",
                                                    "aac",
                                                ]:
                                                    found_files = list(
                                                        output_dir.glob(f"*.{ext}")
                                                    )
                                                    if found_files:
                                                        filename = found_files[
                                                            0
                                                        ]  # Take first match
                                                        logger.info(
                                                            f"Found alternate file: {filename.name}"
                                                        )
                                                        break

                                        # Check for .part files (incomplete downloads) but don't clean up yet
                                        # We need to check if the file was actually downloaded first
                                        part_files = list(output_dir.glob("*.part"))

                                        if filename:
                                            # Only count as successful if the file actually exists
                                            if Path(filename).exists():
                                                all_files.append(str(filename))
                                                # Track audio file info for database
                                                audio_downloaded_successfully = True
                                                audio_file_path_for_db = str(filename)
                                                audio_file_size = (
                                                    Path(filename).stat().st_size
                                                )
                                                audio_file_format = Path(
                                                    filename
                                                ).suffix[
                                                    1:
                                                ]  # Remove the dot
                                            else:
                                                # Filename was constructed from yt-dlp metadata but file doesn't exist
                                                logger.error(
                                                    f"yt-dlp reported filename '{filename}' but file does not exist on disk"
                                                )
                                                # Continue to error handling below
                                                filename = None

                                        # Handle case where no filename was found or file doesn't exist
                                        if not filename:
                                            # Clean up any .part files if download failed
                                            if part_files:
                                                logger.warning(
                                                    f"Found {len(part_files)} incomplete download(s), cleaning up..."
                                                )
                                                for part_file in part_files:
                                                    try:
                                                        part_file.unlink()
                                                        logger.debug(
                                                            f"Removed incomplete download: {part_file.name}"
                                                        )
                                                    except Exception as e:
                                                        logger.warning(
                                                            f"Failed to remove {part_file.name}: {e}"
                                                        )

                                            # Check if we have .part files - indicates incomplete download
                                            if part_files:
                                                error_msg = f"Download incomplete for: {entry.get('title', 'Unknown')} - connection may have been interrupted or rate-limited"
                                                logger.error(error_msg)
                                                raise Exception(error_msg)
                                            else:
                                                logger.error(
                                                    f"Failed to locate downloaded file for: {entry.get('title', 'Unknown')}"
                                                )
                                                # Log entry details for debugging
                                                logger.error(
                                                    f"Entry keys: {list(entry.keys())}"
                                                )
                                                if "requested_downloads" in entry:
                                                    logger.error(
                                                        f"requested_downloads: {entry['requested_downloads']}"
                                                    )
                                                if "url" in entry:
                                                    logger.error(
                                                        f"Entry URL: {entry['url']}"
                                                    )
                                                if "ext" in entry:
                                                    logger.error(
                                                        f"Entry ext: {entry['ext']}"
                                                    )
                                                logger.error(
                                                    f"Output directory: {output_dir}"
                                                )
                                                logger.error(
                                                    f"Listing files in output_dir: {list(output_dir.glob('*'))}"
                                                )
                                                raise Exception(
                                                    f"Failed to locate downloaded file for: {entry.get('title', 'Unknown')}"
                                                )

                                        # Thumbnail - save to Thumbnails subdirectory
                                        if download_thumbnails:
                                            thumbnail_path = (
                                                self._download_thumbnail_from_url(
                                                    url, thumbnails_dir
                                                )
                                            )
                                            if thumbnail_path:
                                                all_thumbnails.append(thumbnail_path)

                            # Handle thumbnail download even if files were already tracked
                            if files_already_tracked and download_thumbnails:
                                thumbnail_path = self._download_thumbnail_from_url(
                                    url, thumbnails_dir
                                )
                                if thumbnail_path:
                                    all_thumbnails.append(thumbnail_path)

                        except Exception as download_error:
                            download_error_msg = str(download_error)
                            logger.error(
                                f"❌ Download failed for {url}: {download_error_msg}"
                            )

                            # Check for rate limiting and trigger cooldown if enabled
                            if self._is_rate_limited(download_error_msg):
                                if progress_callback:
                                    if "HTTP Error 403" in download_error_msg:
                                        progress_callback(
                                            "❌ Download blocked (403) - YouTube detected proxy"
                                        )
                                    elif "HTTP Error 429" in download_error_msg:
                                        progress_callback(
                                            "❌ Rate limited (429) - too many requests"
                                        )

                                # Trigger automatic cooldown
                                self._trigger_cooldown(progress_callback)

                            elif progress_callback:
                                if "HTTP Error 404" in download_error_msg:
                                    progress_callback(
                                        "❌ Video not found (404) - may be private or deleted"
                                    )
                                elif "timeout" in download_error_msg.lower():
                                    progress_callback(
                                        "❌ Download timeout - connection too slow"
                                    )
                                    progress_callback(
                                        "   Try reducing concurrent connections or check proxy service status"
                                    )
                                elif "proxy" in download_error_msg.lower():
                                    progress_callback("❌ Proxy connection failed")
                                    progress_callback(
                                        "   Check proxy account status and credentials"
                                    )
                                elif "certificate" in download_error_msg.lower():
                                    progress_callback(
                                        "❌ SSL certificate issue with proxy"
                                    )
                                else:
                                    progress_callback(
                                        f"❌ Download error: {download_error_msg}"
                                    )

                            # Re-raise the exception to be caught by outer try-catch
                            raise download_error

            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error downloading audio for {url}: {error_msg}")

                # Fail-fast approach: Log error and move to next video
                # Check for specific error types for better user feedback
                if (
                    "bot" in error_msg.lower()
                    or "sign in to confirm" in error_msg.lower()
                ):
                    logger.error(
                        f"🤖 Bot detection for {source_id or url[:50]} - skipping (each video uses unique IP)"
                    )
                    errors.append(f"Bot detection for {url}: {error_msg}")
                    if progress_callback:
                        progress_callback(
                            f"❌ Bot detection - skipping video (fresh IP will be used for next video)"
                        )
                elif "402 Payment Required" in error_msg:
                    logger.error(f"💰 Payment required - proxy account out of funds")
                    errors.append(
                        f"💰 Payment required for {url}: Your proxy account is out of funds. Please add payment to your proxy service account."
                    )
                    if progress_callback:
                        progress_callback(
                            f"❌ Proxy payment required - check account balance"
                        )
                else:
                    errors.append(f"Failed to download {url}: {error_msg}")
                    if progress_callback:
                        progress_callback(f"❌ Download failed: {error_msg[:100]}")

            finally:
                # PacketStream proxies do not require session cleanup (stateless)
                pass

            # Move to next URL
            url_index += 1

            # Add staggered delay between downloads (3-8 seconds) to appear more human-like
            # Skip delay for last URL or if cancelled
            if url_index < len(urls_to_process):
                if cancellation_token and cancellation_token.is_cancelled():
                    logger.info("Download cancelled - skipping delay")
                else:
                    delay = random.uniform(3, 8)
                    logger.info(
                        f"⏱️ Pausing {delay:.1f}s before next download (organic pacing)"
                    )
                    if progress_callback:
                        progress_callback(
                            f"⏱️ Pausing {delay:.1f}s before next video..."
                        )
                    time.sleep(delay)

        return ProcessorResult(
            success=len(errors) == 0,
            data={
                "downloaded_files": all_files,
                "downloaded_thumbnails": all_thumbnails,
                "errors": errors,
                "output_format": output_format,
                "output_dir": str(output_dir),
                "count": len(all_files),
                "thumbnail_count": len(all_thumbnails),
                "urls_processed": len(urls),
                "duplicates_skipped": (
                    len(duplicate_results) if "duplicate_results" in locals() else 0
                ),
                "total_urls_input": (
                    original_count if "original_count" in locals() else len(urls)
                ),
            },
            errors=errors if errors else None,
            metadata={
                "files_downloaded": len(all_files),
                "thumbnails_downloaded": len(all_thumbnails),
                "errors_count": len(errors),
                "urls_processed": len(urls),
                "duplicates_skipped": (
                    len(duplicate_results) if "duplicate_results" in locals() else 0
                ),
                "deduplication_enabled": True,
                "timestamp": datetime.now().isoformat(),
            },
        )


def fetch_audio(
    url: str,
    output_dir: str | Path | None = None,
    output_format: str = "mp3",
    download_thumbnails: bool = True,
    progress_callback=None,
) -> str:
    """Convenience function to download audio for a single video. Returns output file path."""
    processor = YouTubeDownloadProcessor(
        output_format=output_format, download_thumbnails=download_thumbnails
    )
    result = processor.process(
        url,
        output_dir=output_dir,
        output_format=output_format,
        progress_callback=progress_callback,
    )
    if not result.success:
        raise YouTubeAPIError(f"Failed to download audio: {result.errors}")
    files = result.data.get("downloaded_files", [])
    if not files:
        raise YouTubeAPIError("No audio file downloaded")
    return files[0]
