#!/usr/bin/env python3
"""
Unified Download Orchestrator

Coordinates RSS and YouTube downloads in parallel while maintaining source_id mappings.
"""

import asyncio
import logging
from pathlib import Path

from ..database.service import DatabaseService
from ..logger import get_logger
from .podcast_rss_downloader import PodcastRSSDownloader
from .session_based_scheduler import SessionBasedScheduler
from .youtube_to_podcast_mapper import YouTubeToPodcastMapper

logger = get_logger(__name__)


class UnifiedDownloadOrchestrator:
    """
    Coordinates RSS and YouTube downloads in parallel.

    Features:
    - Splits URLs into RSS-available and YouTube-only
    - Maintains source_id mappings throughout
    - Launches RSS downloader (parallel, no rate limiting)
    - Launches SessionBasedScheduler for YouTube (staggered, rate-limited)
    - Merges downloaded files into single queue for transcription
    - Passes source_id with each file to transcription pipeline
    """

    def __init__(
        self,
        youtube_urls: list[str],
        cookie_files: list[str],
        output_dir: Path,
        db_service: DatabaseService | None = None,
        progress_callback=None,
    ):
        """
        Initialize orchestrator.

        Args:
            youtube_urls: List of YouTube video URLs
            cookie_files: List of cookie file paths for YouTube downloads
            output_dir: Directory to save downloaded audio files
            db_service: Database service
            progress_callback: Callback for progress updates
        """
        self.youtube_urls = youtube_urls
        self.cookie_files = cookie_files
        self.output_dir = Path(output_dir)
        self.db_service = db_service or DatabaseService()
        self.progress_callback = progress_callback

        # Initialize components
        self.mapper = YouTubeToPodcastMapper()
        self.podcast_downloader = PodcastRSSDownloader(db_service=self.db_service)

        logger.info(
            f"UnifiedDownloadOrchestrator initialized: "
            f"{len(youtube_urls)} URLs, {len(cookie_files)} accounts"
        )

    async def process_all(self) -> list[tuple[Path, str]]:
        """
        Process all URLs (RSS + YouTube in parallel).

        Returns:
            [(audio_file_path, source_id), ...]
        """
        logger.info(
            f"🚀 Starting unified download orchestration for {len(self.youtube_urls)} URLs"
        )

        if self.progress_callback:
            self.progress_callback(
                f"🔍 Mapping {len(self.youtube_urls)} YouTube URLs to podcast RSS feeds..."
            )

        # Step 1: Map YouTube URLs to podcast RSS feeds
        rss_mappings = self.mapper.map_urls_batch(self.youtube_urls)

        # Step 2: Split URLs into RSS-available and YouTube-only
        rss_urls = {url: mapping for url, mapping in rss_mappings.items()}

        # Extract YouTube source_ids for all URLs
        youtube_source_ids = {}
        for url in self.youtube_urls:
            source_id = self.mapper._extract_youtube_source_id(url)
            if source_id:
                youtube_source_ids[url] = source_id

        # YouTube-only URLs (not in RSS mappings)
        youtube_only_urls = {
            url: source_id
            for url, source_id in youtube_source_ids.items()
            if url not in rss_mappings
        }

        logger.info(
            f"📊 Mapping results:\n"
            f"   ✅ {len(rss_urls)} URLs mapped to podcast RSS feeds ({len(rss_urls)/len(self.youtube_urls)*100:.1f}%)\n"
            f"   📺 {len(youtube_only_urls)} URLs require YouTube download ({len(youtube_only_urls)/len(self.youtube_urls)*100:.1f}%)"
        )

        if self.progress_callback:
            self.progress_callback(
                f"📊 Mapping complete:\n"
                f"   ✅ {len(rss_urls)} podcast RSS feeds\n"
                f"   📺 {len(youtube_only_urls)} YouTube downloads\n"
                f"   🚀 Processing both streams in parallel..."
            )

        # Step 3: Process RSS and YouTube downloads in parallel
        rss_task = self._process_rss_downloads(rss_mappings)
        youtube_task = self._process_youtube_downloads(youtube_only_urls)

        # Run both in parallel
        rss_files, youtube_files = await asyncio.gather(rss_task, youtube_task)

        # Step 4: Merge results
        all_files = self._merge_download_queues(rss_files, youtube_files)

        logger.info(
            f"✅ Download orchestration complete:\n"
            f"   📥 RSS downloads: {len(rss_files)}\n"
            f"   📺 YouTube downloads: {len(youtube_files)}\n"
            f"   📁 Total files: {len(all_files)}"
        )

        if self.progress_callback:
            self.progress_callback(
                f"✅ All downloads complete: {len(all_files)} files ready for transcription"
            )

        return all_files

    async def _process_rss_downloads(
        self,
        rss_mappings: dict[str, tuple[str, str]],  # {youtube_url: (rss_url, source_id)}
    ) -> list[tuple[Path, str]]:
        """
        Download from RSS feeds (parallel).

        Args:
            rss_mappings: YouTube URL to (RSS URL, podcast source_id) mappings

        Returns:
            [(audio_file_path, source_id), ...]
        """
        if not rss_mappings:
            logger.info("No RSS feeds to download")
            return []

        logger.info(f"📥 Starting RSS downloads for {len(rss_mappings)} URLs")

        if self.progress_callback:
            self.progress_callback(
                f"📥 Downloading from {len(rss_mappings)} podcast RSS feeds..."
            )

        # Group URLs by RSS feed
        feed_to_urls = {}
        for youtube_url, (rss_url, podcast_source_id) in rss_mappings.items():
            if rss_url not in feed_to_urls:
                feed_to_urls[rss_url] = {}
            # Map YouTube source_id to YouTube URL for matching
            youtube_source_id = self.mapper._extract_youtube_source_id(youtube_url)
            feed_to_urls[rss_url][youtube_source_id] = youtube_url

        # Download from each feed
        all_downloaded = []
        for rss_url, target_source_ids in feed_to_urls.items():
            try:
                downloaded = self.podcast_downloader.download_from_rss(
                    rss_url=rss_url,
                    target_source_ids=target_source_ids,
                    output_dir=self.output_dir / "podcast_rss",
                )
                all_downloaded.extend(downloaded)

                if self.progress_callback:
                    self.progress_callback(
                        f"📥 RSS: {len(all_downloaded)}/{len(rss_mappings)} episodes downloaded"
                    )
            except Exception as e:
                logger.error(f"Failed to download from RSS feed {rss_url[:60]}: {e}")

        logger.info(f"✅ RSS downloads complete: {len(all_downloaded)} files")
        return all_downloaded

    async def _process_youtube_downloads(
        self, urls_with_source_ids: dict[str, str]  # {youtube_url: source_id}
    ) -> list[tuple[Path, str]]:
        """
        Download from YouTube (session-based).

        Args:
            urls_with_source_ids: YouTube URLs with their source_ids

        Returns:
            [(audio_file_path, source_id), ...]
        """
        if not urls_with_source_ids:
            logger.info("No YouTube downloads needed")
            return []

        logger.info(
            f"📺 Starting YouTube downloads for {len(urls_with_source_ids)} URLs"
        )

        if self.progress_callback:
            self.progress_callback(
                f"📺 Starting session-based YouTube downloads for {len(urls_with_source_ids)} videos..."
            )

        # Create session-based scheduler
        scheduler = SessionBasedScheduler(
            cookie_files=self.cookie_files,
            urls_with_source_ids=urls_with_source_ids,
            output_dir=self.output_dir / "youtube",
            db_service=self.db_service,
            progress_callback=self.progress_callback,
        )

        # Run scheduler (blocking)
        # Note: This runs in executor to not block the event loop
        loop = asyncio.get_event_loop()
        downloaded_files = await loop.run_in_executor(None, scheduler.start)

        logger.info(f"✅ YouTube downloads complete: {len(downloaded_files)} files")
        return downloaded_files

    def _merge_download_queues(
        self, rss_files: list[tuple[Path, str]], youtube_files: list[tuple[Path, str]]
    ) -> list[tuple[Path, str]]:
        """
        Merge RSS and YouTube download queues.

        Args:
            rss_files: Downloaded files from RSS feeds
            youtube_files: Downloaded files from YouTube

        Returns:
            [(audio_file_path, source_id), ...]
        """
        all_files = rss_files + youtube_files

        logger.info(
            f"📁 Merged download queues: "
            f"{len(rss_files)} RSS + {len(youtube_files)} YouTube = {len(all_files)} total"
        )

        return all_files
