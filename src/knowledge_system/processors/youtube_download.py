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
        output_format: str = "mp3",
        download_thumbnails: bool = True,
    ) -> None:
        super().__init__(name or "youtube_download")
        self.output_format = output_format
        self.download_thumbnails = download_thumbnails

        # Base options without cookies (cookies will be added dynamically)
        self.ydl_opts_base = {
            "quiet": True,
            "no_warnings": True,
            "format": "bestaudio/best",
            "outtmpl": "%(title)s.%(ext)s",
            "ignoreerrors": True,
            "noplaylist": False,
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
            "retries": 10,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": self.output_format,
                    "preferredquality": "192",
                }
            ],
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

        # Configure WebShare proxy only
        proxy_url = f"http://{webshare_username}:{webshare_password}@p.webshare.io:80/"
        ydl_opts = {**self.ydl_opts_base, "proxy": proxy_url}
        logger.info(
            "Using WebShare rotating residential proxy for YouTube download (no fallback methods)"
        )
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

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    logger.info(f"Downloading audio for: {url}{playlist_context}")
                    info = ydl.extract_info(url, download=True)

                    if info is None:
                        logger.warning(f"No info extracted for {url}")
                        continue

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
) -> str:
    """Convenience function to download audio for a single video. Returns output file path."""
    processor = YouTubeDownloadProcessor(
        output_format=output_format, download_thumbnails=download_thumbnails
    )
    result = processor.process(url, output_dir=output_dir, output_format=output_format)
    if not result.success:
        raise YouTubeAPIError(f"Failed to download audio: {result.errors}")
    files = result.data.get("downloaded_files", [])
    if not files:
        raise YouTubeAPIError("No audio file downloaded")
    return files[0]
