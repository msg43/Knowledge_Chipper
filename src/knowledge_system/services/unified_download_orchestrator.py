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
        enable_rss_mapping: bool = False,
    ):
        """
        Initialize orchestrator.

        Args:
            youtube_urls: List of YouTube video URLs
            cookie_files: List of cookie file paths for YouTube downloads
            output_dir: Directory to save downloaded audio files
            db_service: Database service
            progress_callback: Callback for progress updates
            enable_rss_mapping: Enable YouTube to RSS mapping (default: False)
        """
        self.youtube_urls = youtube_urls
        self.cookie_files = cookie_files
        self.output_dir = Path(output_dir)
        self.db_service = db_service or DatabaseService()
        self.progress_callback = progress_callback
        self.enable_rss_mapping = enable_rss_mapping

        # Initialize components
        self.mapper = YouTubeToPodcastMapper()
        self.podcast_downloader = PodcastRSSDownloader(db_service=self.db_service)

        logger.info(
            f"UnifiedDownloadOrchestrator initialized: "
            f"{len(youtube_urls)} URLs, {len(cookie_files)} accounts, "
            f"RSS mapping: {'enabled' if enable_rss_mapping else 'disabled'}"
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

        # Step 1: Filter out already-downloaded URLs (deduplication)
        # Only skip if source is FULLY processed (downloaded + transcribed)
        urls_to_process = []
        skipped_count = 0

        # OPTIMIZATION: Batch extraction of source_ids and batch database lookup
        url_to_source_id = {}
        for url in self.youtube_urls:
            source_id = self.mapper._extract_youtube_source_id(url)
            if source_id:
                url_to_source_id[url] = source_id

        # Batch check: Get all sources in single query (10-50x faster)
        source_ids = list(url_to_source_id.values())
        existing_sources_map = {s.source_id: s for s in self.db_service.get_sources_batch(source_ids)}

        for url, source_id in url_to_source_id.items():
            # Initialize download stage status as queued
            self.db_service.upsert_stage_status(
                source_id=source_id,
                stage="download",
                status="queued",
                metadata={
                    "url": url,
                    "orchestrator": "unified",
                    "rss_mapping_enabled": self.enable_rss_mapping,
                },
            )

            # Check if source is fully processed (downloaded + transcribed) using batched data
            is_complete, existing_source_id = self.db_service.source_is_fully_processed(source_id)

            if is_complete:
                logger.info(
                    f"⏭️  Skipping {url[:60]}... (already fully processed as {existing_source_id})"
                )
                skipped_count += 1

                # Update status to completed
                self.db_service.upsert_stage_status(
                    source_id=source_id,
                    stage="download",
                    status="completed",
                    progress_percent=100.0,
                    metadata={
                        "url": url,
                        "skipped_reason": "already_processed",
                        "existing_source_id": existing_source_id,
                    },
                )
            else:
                urls_to_process.append(url)

        if skipped_count > 0:
            logger.info(
                f"📊 Deduplication: {skipped_count}/{len(self.youtube_urls)} URLs already downloaded"
            )
            if self.progress_callback:
                self.progress_callback(
                    f"⏭️  Skipped {skipped_count} already-downloaded URLs"
                )

        if not urls_to_process:
            logger.info("✅ All URLs already downloaded, nothing to do")
            return []

        # Step 2: Map YouTube URLs to podcast RSS feeds (if enabled)
        rss_mappings = {}
        if self.enable_rss_mapping:
            if self.progress_callback:
                self.progress_callback(
                    f"🔍 Mapping {len(urls_to_process)} YouTube URLs to podcast RSS feeds..."
                )
            rss_mappings = self.mapper.map_urls_batch(urls_to_process)
        else:
            logger.info(
                "📺 RSS mapping disabled - all URLs will be downloaded from YouTube"
            )
            if self.progress_callback:
                self.progress_callback(
                    f"📺 RSS mapping disabled - downloading {len(urls_to_process)} URLs from YouTube"
                )

        # Step 3: Split URLs into RSS-available and YouTube-only
        rss_urls = {url: mapping for url, mapping in rss_mappings.items()}

        # Extract YouTube source_ids for all URLs
        youtube_source_ids = {}
        for url in urls_to_process:
            source_id = self.mapper._extract_youtube_source_id(url)
            if source_id:
                youtube_source_ids[url] = source_id

        # YouTube-only URLs (not in RSS mappings)
        youtube_only_urls = {
            url: source_id
            for url, source_id in youtube_source_ids.items()
            if url not in rss_mappings
        }

        if self.enable_rss_mapping:
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
        else:
            logger.info(
                f"📺 All {len(youtube_only_urls)} URLs will be downloaded from YouTube"
            )
            if self.progress_callback:
                self.progress_callback(
                    f"📺 Downloading {len(youtube_only_urls)} videos from YouTube..."
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

        # Choose download strategy based on batch size
        # SessionBasedScheduler: For large batches (100+) with duty-cycle scheduling
        # MultiAccountDownloadScheduler: For small batches (<100) - immediate download
        BATCH_SIZE_THRESHOLD = 100

        if len(urls_with_source_ids) >= BATCH_SIZE_THRESHOLD:
            # Large batch: Use session-based scheduler with duty cycles
            logger.info(
                f"📊 Large batch detected ({len(urls_with_source_ids)} URLs) - using session-based scheduler"
            )

            if self.progress_callback:
                self.progress_callback(
                    f"📺 Starting session-based YouTube downloads for {len(urls_with_source_ids)} videos..."
                )

            scheduler = SessionBasedScheduler(
                cookie_files=self.cookie_files,
                urls_with_source_ids=urls_with_source_ids,
                output_dir=self.output_dir / "youtube",
                db_service=self.db_service,
                progress_callback=self.progress_callback,
            )

            # Run scheduler (blocking)
            loop = asyncio.get_event_loop()
            downloaded_files = await loop.run_in_executor(None, scheduler.start)
        else:
            # Small batch: Use direct download with rotation (immediate start)
            logger.info(
                f"📊 Small batch detected ({len(urls_with_source_ids)} URLs) - using immediate download"
            )

            if self.progress_callback:
                self.progress_callback(
                    f"📺 Downloading {len(urls_with_source_ids)} videos with rate limiting..."
                )

            # Check if we have cookies
            if self.cookie_files:
                # Use multi-account downloader with cookies
                from ..config import get_settings
                from .multi_account_downloader import MultiAccountDownloadScheduler

                settings = get_settings()
                yt_config = settings.youtube_processing

                scheduler = MultiAccountDownloadScheduler(
                    cookie_files=self.cookie_files,
                    parallel_workers=yt_config.concurrent_downloads_max,
                    enable_sleep_period=False,  # No sleep period for small batches
                    min_delay=180.0,  # 3 min
                    max_delay=300.0,  # 5 min
                    db_service=self.db_service,
                    disable_proxies_with_cookies=yt_config.disable_proxies_with_cookies,
                )

                if self.progress_callback:
                    scheduler.progress_callback = self.progress_callback

                # Download with rotation
                results = await scheduler.download_batch_with_rotation(
                    urls=list(urls_with_source_ids.keys()),
                    output_dir=self.output_dir / "youtube",
                )

                # Convert results to expected format
                downloaded_files = []
                for result in results:
                    if result.get("success") and result.get("audio_file"):
                        audio_file_data = result["audio_file"]
                        # Handle both dict (from scheduler) and string/Path formats
                        if isinstance(audio_file_data, dict):
                            # Scheduler returns dict with 'downloaded_files' list
                            files = audio_file_data.get("downloaded_files", [])
                            if files:
                                audio_file = Path(files[0])
                            else:
                                continue
                        else:
                            # Direct string/Path
                            audio_file = Path(audio_file_data)

                        url = result["url"]
                        source_id = urls_with_source_ids[url]
                        downloaded_files.append((audio_file, source_id))
            else:
                # No cookies: Use simple sequential download
                logger.info(
                    "📥 No cookies provided - using sequential download without authentication"
                )
                from .youtube_download_service import YouTubeDownloadService

                service = YouTubeDownloadService(
                    enable_cookies=False,
                    cookie_file_path=None,
                    youtube_delay=5,
                    db_service=self.db_service,
                )

                # Download sequentially
                results = service.download_sequential(
                    urls=list(urls_with_source_ids.keys()),
                    downloads_dir=self.output_dir / "youtube",
                )

                # Convert results to expected format
                downloaded_files = []
                for result in results:
                    if result.success and result.audio_file:
                        source_id = urls_with_source_ids[result.url]
                        downloaded_files.append((result.audio_file, source_id))

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
