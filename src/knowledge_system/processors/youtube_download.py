"""
YouTube Download Processor
YouTube Download Processor

Downloads audio and thumbnails from YouTube videos or playlists using yt-dlp.
Supports configurable output format (mp3/wav), error handling, and returns output file paths and metadata.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

import yt_dlp

from ..errors import YouTubeAPIError
from ..logger import get_logger
from ..utils.youtube_utils import extract_urls, is_youtube_url
from .base import BaseProcessor, ProcessorResult

logger = get_logger(__name__)


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
        output_format: str = "webm",  # Default to WebM for best source quality (temp file only)
        download_thumbnails: bool = True,
    ) -> None:
        super().__init__(name or "youtube_download")
        self.output_format = output_format
        self.download_thumbnails = download_thumbnails

        # Base options without cookies (cookies will be added dynamically)
        self.ydl_opts_base = {
            "quiet": True,
            "no_warnings": True,
            "format": "250",  # Optimal Opus WebM (70kbps) - excellent quality with smallest size
            "outtmpl": "%(title)s.%(ext)s",
            "ignoreerrors": True,
            "noplaylist": False,
            # Performance optimizations - optimized for stable proxy connections
            "http_chunk_size": 524288,  # 512KB chunks - balance between efficiency and stability
            "no_check_formats": True,  # Skip format validation for faster processing
            "prefer_free_formats": True,  # Prefer formats that don't require fragmentation
            "youtube_include_dash_manifest": False,  # Disable DASH (fragmented) formats
            "no_part": False,  # Enable partial downloading/resuming for connection interruptions
            "retries": 3,  # Standard retries for connection issues
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "headers": {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-us,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Accept-Charset": "ISO-8859-1,utf-8;q=0.7,*;q=0.7",
                "Keep-Alive": "timeout=5, max=100",
                "Connection": "keep-alive",
                # Additional headers to appear more like a regular browser
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
            },
            "extractor_retries": 3,  # Standard retries for connection issues
            "socket_timeout": 45,  # Longer timeout for large file downloads through proxy
            "fragment_retries": 5,  # Moderate fragment retries for stability
            # SSL/TLS troubleshooting for WebShare proxy
            "nocheckcertificate": True,  # Skip SSL certificate verification for proxy
            "prefer_insecure": True,  # Prefer HTTP over HTTPS when possible
            # WebShare proxy optimizations for parallel downloads
            "http_chunk_retry": True,  # Retry failed chunks
            "keep_fragments": False,  # Don't keep fragments to save space
            "concurrent_fragment_downloads": 8,  # Use multiple connections for parallel chunks
            "postprocessors": [
                {"key": "FFmpegAudioConvertor", "preferredcodec": "mp3"}
            ],  # Default post-processor for audio conversion
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
                    pass
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
        """Extract video ID from YouTube URL."""
        import re

        patterns = [
            r"(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]+)",
            r"youtube\.com/playlist\?list=([a-zA-Z0-9_-]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        # Fallback: use a hash of the URL
        import hashlib

        return hashlib.md5(url.encode()).hexdigest()[:8]

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
        output_format = output_format or self.output_format
        download_thumbnails = (
            download_thumbnails
            if download_thumbnails is not None
            else self.download_thumbnails
        )

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

        output_dir = Path(output_dir) if output_dir else Path.cwd()
        output_dir.mkdir(parents=True, exist_ok=True)

        # Create Thumbnails subdirectory for consistent organization
        thumbnails_dir = output_dir / "Thumbnails"
        thumbnails_dir.mkdir(exist_ok=True)

        # ENFORCE WebShare proxy ONLY - no fallback authentication strategies
        from ..config import get_settings

        settings = get_settings()
        webshare_username = settings.api_keys.webshare_username
        webshare_password = settings.api_keys.webshare_password

        if not webshare_username or not webshare_password:
            return ProcessorResult(
                success=False,
                errors=[
                    "WebShare proxy credentials are required for YouTube processing. Please configure WebShare Username and Password in Settings. This system only uses WebShare rotating residential proxies for YouTube access."
                ],
            )

        # Test WebShare credentials before proceeding
        logger.info("Testing WebShare proxy credentials...")
        if progress_callback:
            progress_callback("🔐 Testing WebShare proxy credentials...")

        try:
            import requests

            proxy_url_for_test = (
                f"http://{webshare_username}:{webshare_password}@p.webshare.io:80/"
            )
            test_response = requests.get(
                "https://httpbin.org/ip",
                proxies={"http": proxy_url_for_test, "https": proxy_url_for_test},
                timeout=15,
            )
            if test_response.status_code == 200:
                proxy_ip = test_response.json().get("origin", "unknown")
                logger.info(f"✅ WebShare proxy working - connected via IP: {proxy_ip}")
                if progress_callback:
                    progress_callback(f"✅ WebShare proxy working - IP: {proxy_ip}")
            else:
                logger.warning(
                    f"WebShare proxy test returned status {test_response.status_code}"
                )
                if progress_callback:
                    progress_callback(
                        f"⚠️ WebShare proxy test: unexpected status {test_response.status_code}"
                    )
        except Exception as proxy_test_error:
            error_msg = str(proxy_test_error)
            logger.error(f"❌ WebShare proxy test failed: {error_msg}")
            if progress_callback:
                if "407" in error_msg or "authentication" in error_msg.lower():
                    progress_callback(
                        "❌ WebShare authentication failed - check username/password"
                    )
                elif "timeout" in error_msg.lower():
                    progress_callback("❌ WebShare proxy timeout - check account status")
                else:
                    progress_callback(f"❌ WebShare proxy test failed: {error_msg}")
                progress_callback(
                    "   Continuing anyway - may work for YouTube specifically..."
                )
            # Continue anyway as proxy might work for YouTube even if test fails

        # Configure WebShare proxy with dynamic concurrency
        proxy_url = f"http://{webshare_username}:{webshare_password}@p.webshare.io:80/"
        ydl_opts = {**self.ydl_opts_base, "proxy": proxy_url}

        # Dynamic concurrency based on expected file size and connection count
        def calculate_optimal_concurrency(estimated_size_mb: float) -> int:
            """Calculate optimal concurrent connections based on file size."""
            if estimated_size_mb < 10:  # Small files: 2-4 connections
                return min(4, max(2, int(estimated_size_mb / 3)))
            elif estimated_size_mb < 50:  # Medium files: 4-8 connections
                return min(8, max(4, int(estimated_size_mb / 8)))
            elif estimated_size_mb < 200:  # Large files: 8-16 connections
                return min(16, max(8, int(estimated_size_mb / 15)))
            else:  # Very large files: 16-32 connections
                return min(32, max(16, int(estimated_size_mb / 25)))

        # Estimate file size for format 250 (70kbps Opus)
        # Rough estimate: 70kbps ≈ 0.5MB per minute
        estimated_duration_minutes = 60  # Default assumption for unknown duration
        estimated_size_mb = estimated_duration_minutes * 0.5
        optimal_concurrency = calculate_optimal_concurrency(estimated_size_mb)

        # Override concurrent downloads with calculated value
        ydl_opts["concurrent_fragment_downloads"] = optimal_concurrency

        logger.info(
            f"Using WebShare proxy with {optimal_concurrency} concurrent connections "
            f"(estimated {estimated_size_mb:.1f}MB file)"
        )

        # Add progress hook for real-time download progress in GUI with diagnostic info
        if progress_callback:
            import time

            last_progress_time = [time.time()]  # Use list for mutable reference

            def download_progress_hook(d):
                """Hook to capture yt-dlp download progress and forward to GUI with diagnostic info."""
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

                        progress_msg = f"📥 Downloading: {clean_filename[:50]}{'...' if len(clean_filename) > 50 else ''}"
                        progress_detail = (
                            f"   {downloaded_mb:.1f}/{total_mb:.1f} MB ({percent:.1f}%)"
                        )

                        # Enhanced diagnostics for parallel download performance
                        time_since_last = current_time - last_progress_time[0]
                        if speed_mbps > 0:
                            progress_detail += f" @ {speed_mbps:.1f} MB/s"
                            # Show parallel connection info for higher speeds
                            if speed_mbps > 2.0:  # Good parallel performance
                                progress_detail += (
                                    f" [{optimal_concurrency} connections]"
                                )
                        elif time_since_last > 10:  # No progress for 10+ seconds
                            progress_detail += f" (stalled - retrying with {optimal_concurrency} connections)"
                        else:
                            progress_detail += (
                                f" (buffering {optimal_concurrency} streams...)"
                            )

                        progress_callback(progress_msg)
                        progress_callback(progress_detail)
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
                            f"⏱️ Download timeout - retrying (YouTube may be throttling)..."
                        )
                    elif "connection" in error_msg.lower():
                        progress_callback(f"🔗 Connection issue - retrying...")
                    else:
                        progress_callback(f"❌ Download error: {error_msg}")

            ydl_opts["progress_hooks"] = [download_progress_hook]

        ydl_opts["postprocessors"][0]["preferredcodec"] = output_format
        ydl_opts["outtmpl"] = str(output_dir / "%(title)s.%(ext)s")

        all_files = []
        all_thumbnails = []
        errors = []

        for i, url in enumerate(urls, 1):
            try:
                # Determine playlist context for progress display
                playlist_context = ""
                for playlist in playlist_info:
                    if playlist["start_index"] <= (i - 1) <= playlist["end_index"]:
                        playlist_position = (i - 1) - playlist["start_index"] + 1
                        playlist_context = f" [Playlist: {playlist['title'][:40]}{'...' if len(playlist['title']) > 40 else ''} - Video {playlist_position}/{playlist['total_videos']}]"
                        break

                # First, extract metadata to get actual duration for better concurrency calculation
                if progress_callback:
                    progress_callback(f"🔍 Extracting video metadata for: {url}")

                try:
                    # Test WebShare proxy connectivity first
                    test_opts = {
                        "proxy": proxy_url,
                        "quiet": True,
                        "no_warnings": True,
                        "extract_flat": True,
                        "socket_timeout": 30,
                    }

                    with yt_dlp.YoutubeDL(test_opts) as ydl_test:
                        logger.info(f"Testing WebShare proxy connectivity for: {url}")
                        if progress_callback:
                            progress_callback(
                                f"🔗 Testing WebShare proxy connectivity..."
                            )

                        # Quick connectivity test
                        test_info = ydl_test.extract_info(url, download=False)
                        if not test_info:
                            raise Exception(
                                "Proxy connectivity test failed - no video info returned"
                            )

                        logger.info("✅ WebShare proxy connectivity test passed")
                        if progress_callback:
                            progress_callback(
                                f"✅ WebShare proxy working - extracting full metadata..."
                            )

                    # Now extract full metadata
                    with yt_dlp.YoutubeDL(
                        {**ydl_opts, "extract_flat": False}
                    ) as ydl_info:
                        info_only = ydl_info.extract_info(url, download=False)
                        duration_seconds = info_only.get(
                            "duration", 3600
                        )  # Default to 1 hour if unknown
                        duration_minutes = duration_seconds / 60
                        video_title = info_only.get("title", "Unknown Title")

                        # Recalculate optimal concurrency with actual duration
                        estimated_size_mb = (
                            duration_minutes * 0.5
                        )  # 70kbps ≈ 0.5MB per minute
                        optimal_concurrency = calculate_optimal_concurrency(
                            estimated_size_mb
                        )
                        ydl_opts["concurrent_fragment_downloads"] = optimal_concurrency

                        logger.info(
                            f"✅ Video '{video_title}' - Duration: {duration_minutes:.1f}min, "
                            f"estimated size: {estimated_size_mb:.1f}MB, "
                            f"using {optimal_concurrency} concurrent connections"
                        )

                        if progress_callback:
                            progress_callback(
                                f"📊 '{video_title[:40]}...' - {duration_minutes:.1f}min → {optimal_concurrency} connections"
                            )

                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"❌ Metadata extraction failed for {url}: {error_msg}")

                    if progress_callback:
                        if "403" in error_msg or "forbidden" in error_msg.lower():
                            progress_callback(
                                f"❌ Access denied - YouTube may be blocking this proxy IP"
                            )
                        elif "404" in error_msg or "not found" in error_msg.lower():
                            progress_callback(f"❌ Video not found or private: {url}")
                        elif "timeout" in error_msg.lower():
                            progress_callback(
                                f"❌ Proxy connection timeout - WebShare may have connectivity issues"
                            )
                        elif "proxy" in error_msg.lower():
                            progress_callback(
                                f"❌ Proxy error: Check WebShare credentials and account status"
                            )
                        else:
                            progress_callback(
                                f"❌ Metadata extraction failed: {error_msg}"
                            )

                    # Continue with default settings if metadata extraction fails
                    logger.warning(
                        f"Continuing with default concurrency settings due to metadata failure"
                    )
                    if progress_callback:
                        progress_callback(
                            f"⚠️ Using default settings - attempting download anyway..."
                        )

                # Attempt the actual download with enhanced error handling
                if progress_callback:
                    progress_callback(
                        f"🚀 Starting download with {optimal_concurrency} parallel connections..."
                    )

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    logger.info(f"Downloading audio for: {url}{playlist_context}")
                    try:
                        info = ydl.extract_info(url, download=True)

                        if info is None:
                            logger.warning(f"No info extracted for {url}")
                            if progress_callback:
                                progress_callback(
                                    f"⚠️ No video information returned - video may be unavailable"
                                )
                            continue

                        logger.info(f"✅ Successfully downloaded audio for: {url}")
                        if progress_callback:
                            progress_callback(
                                f"✅ Audio download completed successfully"
                            )

                    except Exception as download_error:
                        download_error_msg = str(download_error)
                        logger.error(
                            f"❌ Download failed for {url}: {download_error_msg}"
                        )

                        if progress_callback:
                            if "HTTP Error 403" in download_error_msg:
                                progress_callback(
                                    f"❌ Download blocked (403) - YouTube detected proxy"
                                )
                                progress_callback(
                                    f"   Try again later or check WebShare IP rotation"
                                )
                            elif "HTTP Error 429" in download_error_msg:
                                progress_callback(
                                    f"❌ Rate limited (429) - too many requests"
                                )
                                progress_callback(
                                    f"   YouTube is throttling this proxy IP"
                                )
                            elif "HTTP Error 404" in download_error_msg:
                                progress_callback(
                                    f"❌ Video not found (404) - may be private or deleted"
                                )
                            elif "timeout" in download_error_msg.lower():
                                progress_callback(
                                    f"❌ Download timeout - connection too slow"
                                )
                                progress_callback(
                                    f"   Try reducing concurrent connections or check WebShare speed"
                                )
                            elif "proxy" in download_error_msg.lower():
                                progress_callback(f"❌ Proxy connection failed")
                                progress_callback(
                                    f"   Check WebShare account status and credentials"
                                )
                            elif "certificate" in download_error_msg.lower():
                                progress_callback(f"❌ SSL certificate issue with proxy")
                            else:
                                progress_callback(
                                    f"❌ Download error: {download_error_msg}"
                                )

                        # Re-raise the exception to be caught by outer try-catch
                        raise download_error

                    if "entries" in info and info["entries"]:
                        entries = info["entries"]
                    else:
                        entries = [info]

                    for entry in entries:
                        if entry and "title" in entry:
                            # Audio file
                            filename = output_dir / f"{entry['title']}.{output_format}"
                            all_files.append(str(filename))

                            # Thumbnail - save to Thumbnails subdirectory
                            if download_thumbnails:
                                thumbnail_path = self._download_thumbnail_from_url(
                                    url, thumbnails_dir
                                )
                                if thumbnail_path:
                                    all_thumbnails.append(thumbnail_path)

            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error downloading audio for {url}: {error_msg}")

                # Check for specific payment required error
                if "402 Payment Required" in error_msg:
                    errors.append(
                        f"💰 WebShare payment required for {url}: Your WebShare account is out of funds. Please add payment at https://panel.webshare.io/"
                    )
                else:
                    errors.append(f"Failed to download {url}: {error_msg}")

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
            },
            errors=errors if errors else None,
            metadata={
                "files_downloaded": len(all_files),
                "thumbnails_downloaded": len(all_thumbnails),
                "errors_count": len(errors),
                "urls_processed": len(urls),
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
