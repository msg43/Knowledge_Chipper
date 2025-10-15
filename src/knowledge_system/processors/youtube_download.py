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
    ) -> None:
        super().__init__(name or "youtube_download")
        self.output_format = output_format
        self.download_thumbnails = download_thumbnails

        # Base options without cookies (cookies will be added dynamically if needed)
        self.ydl_opts_base = {
            "quiet": True,
            "no_warnings": True,
            "format": "worstaudio[ext=webm]/worstaudio[ext=opus]/worstaudio[ext=m4a]/worstaudio/bestaudio[ext=webm][abr<=96]/bestaudio[ext=m4a][abr<=128]/bestaudio[abr<=128]/bestaudio/worst",  # Optimal cascade: smallest formats first, guaranteed audio-only fallback
            "outtmpl": "%(title)s.%(ext)s",
            "ignoreerrors": True,
            "noplaylist": False,
            # Performance optimizations - optimized for stable proxy connections
            "http_chunk_size": 524288,  # 512KB chunks - balance between efficiency and stability
            "no_check_formats": True,  # Skip format validation for faster processing
            "prefer_free_formats": True,  # Prefer formats that don't require fragmentation
            # Note: youtube_include_dash_manifest option removed (deprecated in yt-dlp 2025.9+)
            "no_part": False,  # Enable partial downloading/resuming for connection interruptions
            "retries": 3,  # Standard retries for connection issues
            "extractor_retries": 3,  # Standard retries for connection issues
            "socket_timeout": 45,  # Longer timeout for large file downloads through proxy
            # NOTE: Do NOT use Android client with PacketStream - causes "Fixed to extract player response"
            "fragment_retries": 5,  # Moderate fragment retries for stability
            # Network tuning
            "nocheckcertificate": True,
            "http_chunk_retry": True,
            "keep_fragments": False,  # Don't keep fragments to save space
            # Additional options to help with YouTube anti-bot detection
            "sleep_interval": 1,  # Add small delay between requests
            "max_sleep_interval": 5,  # Maximum sleep interval
            "sleep_interval_requests": 1,  # Sleep between requests
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

        video_id = VideoIDExtractor.extract_video_id(url)
        if video_id:
            return video_id

        # Fallback for non-standard URLs: use a hash of the URL
        import hashlib

        return hashlib.md5(url.encode(), usedforsecurity=False).hexdigest()[:8]

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
                f"Deduplication: {len(duplicate_results)} duplicates found, {len(unique_urls)} unique videos to process"
            )
            if progress_callback:
                progress_callback(
                    f"💾 Skipped {len(duplicate_results)} duplicate videos (already processed)"
                )
                for dup in duplicate_results[:3]:  # Show first 3 duplicates
                    progress_callback(f"   • {dup.video_id}: {dup.skip_reason}")
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
                f"Found {len(playlist_info)} playlist(s) with {total_playlist_videos} total videos:"
            )
            for i, playlist in enumerate(playlist_info, 1):
                title = playlist.get("title", "Unknown Playlist")
                video_count = playlist.get("total_videos", 0)
                logger.info(f"  {i}. {title} ({video_count} videos)")

        output_dir = Path(output_dir) if output_dir else Path.cwd()
        output_dir.mkdir(parents=True, exist_ok=True)

        # Create Thumbnails subdirectory for consistent organization
        thumbnails_dir = output_dir / "Thumbnails"
        thumbnails_dir.mkdir(exist_ok=True)

        # PROXY CONFIGURATION - PacketStream (optional)
        from ..config import get_settings
        from ..utils.packetstream_proxy import PacketStreamProxyManager

        settings = get_settings()

        # Note: VideoDeduplicationService already initialized at line 170
        # No need to reinitialize here

        # PacketStream proxy (optional)
        use_proxy = False
        proxy_manager = None
        proxy_url = None

        try:
            proxy_manager = PacketStreamProxyManager()
            if proxy_manager.username and proxy_manager.auth_key:
                use_proxy = True
                logger.info(
                    "Using PacketStream residential proxies for YouTube processing"
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

        # PROXY TESTING AND CONFIGURATION
        if use_proxy and proxy_manager:
            # Test PacketStream proxy connectivity
            logger.info("Testing PacketStream proxy connectivity...")
            if progress_callback:
                progress_callback("🔐 Testing PacketStream proxy...")

            try:
                # Extract first video ID for session creation
                test_video_id = "test_connection"  # We'll use a generic test ID
                proxy_url = proxy_manager.get_proxy_url() if proxy_manager else None

                if proxy_url:
                    # Test proxy connectivity
                    import requests

                    # PacketStream proxies don't require SSL certificate verification
                    # Use HTTP endpoint to avoid SSL certificate issues
                    from ..utils.browser_fingerprint import (
                        get_standard_requests_headers,
                    )

                    test_response = requests.get(
                        "http://httpbin.org/ip",
                        proxies={"http": proxy_url, "https": proxy_url},
                        timeout=15,
                        headers=get_standard_requests_headers(),
                    )
                    if test_response.status_code == 200:
                        proxy_ip = test_response.json().get("origin", "unknown")
                        logger.info(
                            f"✅ PacketStream proxy working - connected via IP: {proxy_ip}"
                        )
                        if progress_callback:
                            progress_callback(
                                f"✅ PacketStream proxy working - IP: {proxy_ip}"
                            )
                    else:
                        logger.warning(
                            f"PacketStream proxy test returned status {test_response.status_code}"
                        )
                else:
                    logger.error("Failed to generate PacketStream proxy URL")

                    # Smart fallback: Allow single video downloads, block bulk downloads
                    if len(urls) == 1:
                        logger.warning(
                            "Single video download - allowing fallback despite proxy URL failure"
                        )
                        if progress_callback:
                            progress_callback(
                                "❌ Failed to generate PacketStream proxy URL"
                            )
                            progress_callback(
                                "⚠️ Single video: Proceeding with direct connection (low risk)"
                            )
                        use_proxy = False
                    else:
                        logger.error(
                            f"Bulk download detected ({len(urls)} URLs) - blocking due to proxy URL failure"
                        )
                        if progress_callback:
                            progress_callback(
                                "❌ Failed to generate PacketStream proxy URL"
                            )
                            progress_callback(
                                f"🚫 BLOCKED: Bulk download ({len(urls)} URLs) without proxy protection"
                            )
                            progress_callback(
                                "🛡️ This prevents YouTube from banning your IP address"
                            )
                            progress_callback(
                                "💡 Tip: Single video downloads are still allowed without proxy"
                            )
                            progress_callback(
                                "🔧 Please fix PacketStream configuration before bulk downloading"
                            )

                        return ProcessorResult(
                            success=False,
                            data=None,
                            errors=[
                                f"Failed to generate PacketStream proxy URL for bulk download ({len(urls)} URLs). "
                                "Bulk downloads without proxy protection are blocked to prevent IP bans. "
                                "Single video downloads are still allowed."
                            ],
                            metadata={
                                "proxy_required": True,
                                "bulk_download_blocked": True,
                                "urls_count": len(urls),
                                "single_video_allowed": True,
                            },
                        )

            except Exception as proxy_test_error:
                error_msg = str(proxy_test_error)
                logger.error(f"❌ PacketStream proxy test failed: {error_msg}")

                # Smart fallback: Allow single video downloads, block bulk downloads
                if len(urls) == 1:
                    logger.warning(
                        "Single video download - allowing fallback to direct connection"
                    )
                    if progress_callback:
                        progress_callback(
                            f"❌ PacketStream proxy test failed: {error_msg}"
                        )
                        progress_callback(
                            "⚠️ Single video: Proceeding with direct connection (low risk)"
                        )
                        progress_callback(
                            "🔄 Consider fixing PacketStream for future bulk downloads..."
                        )
                    use_proxy = False
                else:
                    logger.error(
                        f"Bulk download detected ({len(urls)} URLs) - blocking direct connection to prevent IP ban"
                    )
                    if progress_callback:
                        progress_callback(
                            f"❌ PacketStream proxy test failed: {error_msg}"
                        )
                        progress_callback(
                            f"🚫 BLOCKED: Bulk download ({len(urls)} URLs) without proxy protection"
                        )
                        progress_callback(
                            "🛡️ This prevents YouTube from banning your IP address"
                        )
                        progress_callback(
                            "💡 Tip: Single video downloads are still allowed without proxy"
                        )
                        progress_callback(
                            "🔧 Please fix PacketStream configuration before bulk downloading"
                        )

                    return ProcessorResult(
                        success=False,
                        data=None,
                        errors=[
                            f"PacketStream proxy failed for bulk download ({len(urls)} URLs): {error_msg}. "
                            "Bulk downloads without proxy protection are blocked to prevent IP bans. "
                            "Single video downloads are still allowed."
                        ],
                        metadata={
                            "proxy_required": True,
                            "bulk_download_blocked": True,
                            "urls_count": len(urls),
                            "single_video_allowed": True,
                        },
                    )

        # Proxy usage with PacketStream (optional); no legacy WebShare fallback

        # Configure base yt-dlp options
        import copy

        ydl_opts = copy.deepcopy(
            self.ydl_opts_base
        )  # Deep copy to avoid modifying base config

        # NOTE: Do NOT add custom user-agent or http_headers when using PacketStream
        # PacketStream residential proxies work best with yt-dlp's default headers
        # Custom headers can cause "Failed to parse JSON" errors through the proxy

        # Add progress hook for real-time download progress in GUI
        if progress_callback:
            import time

            last_progress_time = [time.time()]  # Use list for mutable reference

            # Track last progress for updating single line
            last_progress_message = ""

            def download_progress_hook(d):
                """Hook to capture yt-dlp download progress and forward to GUI with diagnostic info."""
                nonlocal last_progress_message
                current_time = time.time()

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
                            progress_callback(progress_msg)
                            last_progress_message = progress_msg
                        last_progress_time[0] = current_time

                elif d["status"] == "finished":
                    filename = d.get("filename", "Unknown file")
                    import os

                    clean_filename = os.path.basename(filename)
                    progress_callback(
                        f"✅ Download complete: {clean_filename[:50]}{'...' if len(clean_filename) > 50 else ''}"
                    )
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
        ydl_opts["outtmpl"] = str(output_dir / "%(title)s.%(ext)s")

        all_files = []
        all_thumbnails = []
        errors = []

        # Smart retry system for bot detection
        # Track URLs that hit bot detection and need retry with fresh IP
        retry_queue = []
        used_session_ids = {}  # Track session IDs to force new IPs on retry

        # Convert to list for modification during iteration
        urls_to_process = list(urls)
        url_index = 0

        while url_index < len(urls_to_process):
            url = urls_to_process[url_index]
            i = url_index + 1
            video_id = None  # Initialize early for error handling

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
                    video_id = youtube_id_match.group(1)

                # Generate unique session ID for this video (sticky IP per URL)
                # Each URL gets a consistent session ID, ensuring same IP for all requests
                # (metadata, download chunks, thumbnail) while different URLs get different IPs
                # SMART RETRY: If this URL previously hit bot detection, force a NEW session ID
                current_proxy_url = None
                if use_proxy and proxy_manager:
                    from ..utils.packetstream_proxy import PacketStreamProxyManager

                    # Generate base session ID from video
                    base_session_id = PacketStreamProxyManager.generate_session_id(
                        url, video_id
                    )

                    # If this URL was retried, append retry counter to force NEW IP
                    if url in used_session_ids:
                        retry_count = used_session_ids[url]
                        session_id = f"{base_session_id}_retry{retry_count}"
                        logger.info(
                            f"🔄 Retry #{retry_count} for {video_id or 'URL'} - forcing NEW IP with session '{session_id}'"
                        )
                    else:
                        session_id = base_session_id
                        used_session_ids[url] = 0  # Track first attempt

                    current_proxy_url = proxy_manager.get_proxy_url(
                        session_id=session_id
                    )

                if current_proxy_url and video_id:
                    logger.info(
                        f"Using PacketStream proxy session '{video_id}' for video {video_id} ({i}/{len(urls)})"
                    )
                elif current_proxy_url:
                    logger.info(f"Using PacketStream proxy for URL ({i}/{len(urls)})")
                elif video_id:
                    logger.info(
                        f"Using direct connection for video {video_id} (no proxy configured)"
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
                            progress_callback(
                                f"🔗 Testing {proxy_type} connectivity..."
                            )

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
                    logger.error(
                        f"❌ Metadata extraction failed for {url}: {error_msg}"
                    )

                    if progress_callback:
                        if "403" in error_msg or "forbidden" in error_msg.lower():
                            progress_callback(
                                "❌ Access denied - YouTube may be blocking this proxy IP"
                            )
                        elif "404" in error_msg or "not found" in error_msg.lower():
                            progress_callback(f"❌ Video not found or private: {url}")
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

                    # Continue with default settings if metadata extraction fails
                    logger.warning(
                        "Continuing with standard settings despite metadata failure"
                    )
                    if progress_callback:
                        progress_callback("⚠️ Attempting download anyway...")

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
                        if use_proxy and video_id:
                            logger.info(
                                f"Using PacketStream proxy for video {video_id}"
                            )

                        try:
                            # Track download start time for cost calculation
                            download_start_time = datetime.now()

                            info = ydl.extract_info(url, download=True)

                            # Track whether files were already added (for info is None case)
                            files_already_tracked = False

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
                                        "id": video_id or "unknown",
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
                                    if stderr_output:
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
                            if video_id and db_service:
                                try:
                                    video_title = (
                                        info.get("title", "Unknown Title")
                                        if info
                                        else "Unknown Title"
                                    )

                                    # Create or update video record
                                    video = db_service.create_video(
                                        video_id=video_id,
                                        title=video_title,
                                        url=url,
                                        status=(
                                            "completed"
                                            if (
                                                audio_downloaded_successfully
                                                and metadata_extracted
                                            )
                                            else "partial"
                                        ),
                                        extraction_method=(
                                            "packetstream" if use_proxy else "direct"
                                        ),
                                    )

                                    if not video:
                                        raise Exception(
                                            "Database create_video returned None"
                                        )

                                    # Update audio download status
                                    if audio_downloaded_successfully:
                                        db_service.update_audio_status(
                                            video_id=video_id,
                                            audio_file_path=audio_file_path_for_db,
                                            audio_downloaded=True,
                                            audio_file_size_bytes=audio_file_size,
                                            audio_format=audio_file_format,
                                        )

                                    # Update metadata status
                                    db_service.update_metadata_status(
                                        video_id=video_id,
                                        metadata_complete=metadata_extracted,
                                    )

                                    # Mark for retry if either component failed
                                    if (
                                        not audio_downloaded_successfully
                                        or not metadata_extracted
                                    ):
                                        db_service.mark_for_retry(
                                            video_id=video_id,
                                            needs_metadata_retry=not metadata_extracted,
                                            needs_audio_retry=not audio_downloaded_successfully,
                                            failure_reason=(
                                                f"Metadata: {'OK' if metadata_extracted else metadata_error or 'Failed'}; "
                                                f"Audio: {'OK' if audio_downloaded_successfully else 'Failed'}"
                                            ),
                                        )

                                    logger.info(
                                        f"Registered video {video_id} in database: "
                                        f"audio={audio_downloaded_successfully}, metadata={metadata_extracted}"
                                    )

                                except Exception as db_error:
                                    # CRITICAL: Database write failure means we can't track this download
                                    # Clean up the audio file and fail the download
                                    logger.error(
                                        f"CRITICAL: Failed to register video {video_id} in database: {db_error}"
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
                            elif video_id and not db_service:
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
                                        # Get actual filename from yt-dlp
                                        filename = None

                                        # Try to get filename from requested_downloads
                                        if (
                                            "requested_downloads" in entry
                                            and entry["requested_downloads"]
                                        ):
                                            filename = entry["requested_downloads"][
                                                0
                                            ].get("filepath") or entry[
                                                "requested_downloads"
                                            ][
                                                0
                                            ].get(
                                                "filename"
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

                                        # Clean up any .part files (incomplete downloads)
                                        part_files = list(output_dir.glob("*.part"))
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

                                        if filename:
                                            all_files.append(str(filename))
                                            # Track audio file info for database
                                            audio_downloaded_successfully = True
                                            audio_file_path_for_db = str(filename)
                                            if Path(filename).exists():
                                                audio_file_size = (
                                                    Path(filename).stat().st_size
                                                )
                                                audio_file_format = Path(
                                                    filename
                                                ).suffix[
                                                    1:
                                                ]  # Remove the dot
                                        else:
                                            # Check if we have .part files - indicates incomplete download
                                            if part_files:
                                                error_msg = f"Download incomplete for: {entry.get('title', 'Unknown')} - connection may have been interrupted or rate-limited"
                                                logger.error(error_msg)
                                                raise Exception(error_msg)
                                            else:
                                                logger.error(
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

                            if progress_callback:
                                if "HTTP Error 403" in download_error_msg:
                                    progress_callback(
                                        "❌ Download blocked (403) - YouTube detected proxy"
                                    )
                                    progress_callback(
                                        "   Try again later or check proxy IP rotation"
                                    )
                                elif "HTTP Error 429" in download_error_msg:
                                    progress_callback(
                                        "❌ Rate limited (429) - too many requests"
                                    )
                                    progress_callback(
                                        "   YouTube is throttling this proxy IP"
                                    )
                                elif "HTTP Error 404" in download_error_msg:
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

                # Check for bot detection - add to retry queue for second pass
                if (
                    "bot" in error_msg.lower()
                    or "sign in to confirm" in error_msg.lower()
                ):
                    # Check if this is already a retry
                    current_retry_count = used_session_ids.get(url, 0)
                    max_retries = 2  # Allow up to 2 retries (3 total attempts)

                    if current_retry_count < max_retries:
                        logger.warning(
                            f"🤖 Bot detection for {video_id or url[:50]} - queueing for retry with fresh IP (attempt {current_retry_count + 1}/{max_retries + 1})"
                        )
                        retry_queue.append(url)
                        used_session_ids[url] = current_retry_count + 1
                        if progress_callback:
                            progress_callback(
                                f"🔄 Bot detection - will retry with fresh IP after processing other URLs"
                            )
                        # Don't add to errors yet - will retry
                        url_index += 1
                        continue
                    else:
                        logger.error(
                            f"❌ Bot detection persists after {max_retries} retries for {video_id or url[:50]}"
                        )
                        errors.append(
                            f"Failed to download {url} after {max_retries + 1} attempts with different IPs: {error_msg}"
                        )
                # Check for specific payment required error
                elif "402 Payment Required" in error_msg:
                    errors.append(
                        f"💰 Payment required for {url}: Your proxy account is out of funds. Please add payment to your proxy service account."
                    )
                else:
                    errors.append(f"Failed to download {url}: {error_msg}")

            finally:
                # PacketStream proxies do not require session cleanup (stateless)
                pass

            # Move to next URL
            url_index += 1

            # SMART RETRY SYSTEM: Check if we need to add retry URLs
            # When we finish first pass, add retry queue to end
            if url_index == len(urls) and retry_queue:
                logger.info(
                    f"🔄 First pass complete. Adding {len(retry_queue)} URLs to retry queue with fresh IPs"
                )
                if progress_callback:
                    progress_callback(
                        f"🔄 Retrying {len(retry_queue)} bot-detected URLs with fresh IPs..."
                    )

                # Add retry URLs to end of processing list
                urls_to_process.extend(retry_queue)
                retry_queue.clear()  # Clear queue to prevent duplicates

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
