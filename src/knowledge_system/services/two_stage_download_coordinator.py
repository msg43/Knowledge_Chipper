"""
Two-Stage Download Coordinator

Orchestrates metadata-first, then audio download workflow.
Separates concerns for reliability and efficiency.
"""

import asyncio
from pathlib import Path
from typing import Any, Callable, Optional

from ..config import get_settings
from ..database import DatabaseService
from ..logger import get_logger
from ..utils.video_id_extractor import VideoIDExtractor
from ..utils.youtube_metadata_validator import validate_and_clean_metadata
from .youtube_data_api import YouTubeDataAPI, QuotaExceededError

logger = get_logger(__name__)


class TwoStageDownloadCoordinator:
    """
    Coordinates two-stage download workflow:
    1. Fetch metadata via YouTube Data API (fast, reliable)
    2. Download audio via yt-dlp (only for new videos)
    
    Benefits:
    - Metadata fetch is fast and happens first
    - Can deduplicate before downloading
    - Audio download failures don't lose metadata
    - Clear separation of concerns
    """
    
    def __init__(
        self,
        db_service: DatabaseService = None,
        youtube_api: YouTubeDataAPI = None,
        output_dir: Path = None
    ):
        """
        Initialize coordinator.
        
        Args:
            db_service: Database service instance
            youtube_api: YouTube Data API instance
            output_dir: Output directory for downloads
        """
        self.db_service = db_service or DatabaseService()
        self.config = get_settings()
        
        # Initialize YouTube Data API
        self.youtube_api = youtube_api
        if not self.youtube_api and self.config.youtube_api.enabled:
            if self.config.youtube_api.api_key:
                self.youtube_api = YouTubeDataAPI(
                    api_key=self.config.youtube_api.api_key,
                    quota_limit=self.config.youtube_api.quota_limit,
                    batch_size=self.config.youtube_api.batch_size
                )
                logger.info("✅ YouTube Data API initialized")
            else:
                logger.warning("YouTube Data API enabled but no API key configured")
        
        self.output_dir = output_dir or Path.cwd() / "downloads"
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    async def process_urls(
        self,
        urls: list[str],
        progress_callback: Callable[[str], None] = None
    ) -> dict[str, Any]:
        """
        Process URLs through two-stage workflow.
        
        Args:
            urls: List of YouTube URLs
            progress_callback: Optional progress callback
        
        Returns:
            Statistics dict
        """
        stats = {
            "total_urls": len(urls),
            "metadata_fetched": 0,
            "metadata_failed": 0,
            "audio_downloaded": 0,
            "audio_failed": 0,
            "skipped_duplicates": 0,
            "skipped_existing_audio": 0,
        }
        
        logger.info(f"Starting two-stage download for {len(urls)} URLs")
        
        # Stage 1: Fetch all metadata
        if progress_callback:
            progress_callback("Stage 1: Fetching metadata...")
        
        video_ids = self._extract_video_ids(urls)
        logger.info(f"Extracted {len(video_ids)} video IDs")
        
        metadata_results = await self._fetch_metadata_stage(
            video_ids,
            progress_callback
        )
        
        stats["metadata_fetched"] = len(metadata_results)
        stats["metadata_failed"] = len(video_ids) - len(metadata_results)
        
        # Stage 2: Download audio for videos without audio
        if progress_callback:
            progress_callback("Stage 2: Downloading audio...")
        
        audio_results = await self._download_audio_stage(
            metadata_results,
            progress_callback
        )
        
        stats["audio_downloaded"] = audio_results["downloaded"]
        stats["audio_failed"] = audio_results["failed"]
        stats["skipped_existing_audio"] = audio_results["skipped"]
        
        logger.info(
            f"✅ Two-stage download complete: "
            f"{stats['metadata_fetched']} metadata, "
            f"{stats['audio_downloaded']} audio"
        )
        
        return stats
    
    def _extract_video_ids(self, urls: list[str]) -> list[str]:
        """Extract video IDs from URLs."""
        video_ids = []
        
        for url in urls:
            video_id = VideoIDExtractor.extract_video_id(url)
            if video_id:
                video_ids.append(video_id)
            else:
                logger.warning(f"Could not extract video ID from: {url}")
        
        return video_ids
    
    async def _fetch_metadata_stage(
        self,
        video_ids: list[str],
        progress_callback: Callable[[str], None] = None
    ) -> dict[str, dict[str, Any]]:
        """
        Stage 1: Fetch metadata for all videos.
        
        Returns:
            Dict mapping video_id → metadata
        """
        results = {}
        
        # Check for existing metadata
        new_video_ids = []
        for video_id in video_ids:
            source = self.db_service.get_source(video_id)
            if source and source.metadata_complete:
                logger.info(f"Metadata already exists for {video_id}, skipping")
                results[video_id] = self._source_to_metadata_dict(source)
            else:
                new_video_ids.append(video_id)
        
        if not new_video_ids:
            logger.info("All videos already have metadata")
            return results
        
        logger.info(f"Fetching metadata for {len(new_video_ids)} new videos")
        
        # Use YouTube Data API if available
        if self.youtube_api:
            try:
                if progress_callback:
                    progress_callback(f"Fetching metadata via API for {len(new_video_ids)} videos...")
                
                api_results = self.youtube_api.fetch_videos_batch(new_video_ids)
                
                # Store metadata in database
                for video_id, metadata in api_results.items():
                    # Validate and clean
                    clean_metadata = validate_and_clean_metadata(metadata, source="youtube_api")
                    
                    # Store in database
                    self.db_service.create_source(
                        source_id=video_id,
                        title=clean_metadata["title"],
                        url=f"https://www.youtube.com/watch?v={video_id}",
                        **clean_metadata
                    )
                    
                    # Mark metadata as complete
                    self.db_service.update_metadata_status(video_id, metadata_complete=True)
                    
                    results[video_id] = metadata
                
                logger.info(f"✅ Fetched metadata for {len(api_results)} videos via API")
                
                return results
            
            except QuotaExceededError:
                logger.warning("⚠️ API quota exceeded, falling back to yt-dlp")
            except Exception as e:
                logger.error(f"API metadata fetch failed: {e}")
        
        # Fallback to yt-dlp
        if progress_callback:
            progress_callback(f"Fetching metadata via yt-dlp for {len(new_video_ids)} videos...")
        
        for video_id in new_video_ids:
            try:
                metadata = await self._fetch_metadata_ytdlp(video_id)
                if metadata:
                    results[video_id] = metadata
            except Exception as e:
                logger.error(f"Failed to fetch metadata for {video_id}: {e}")
        
        return results
    
    async def _fetch_metadata_ytdlp(self, video_id: str) -> dict[str, Any] | None:
        """Fetch metadata using yt-dlp (fallback)."""
        try:
            import yt_dlp
            
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
            }
            
            url = f"https://www.youtube.com/watch?v={video_id}"
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    return None
                
                # Validate and clean
                clean_metadata = validate_and_clean_metadata(info, source="ytdlp")
                
                # Store in database
                self.db_service.create_source(
                    source_id=video_id,
                    title=clean_metadata["title"],
                    url=url,
                    **clean_metadata
                )
                
                # Mark metadata as complete
                self.db_service.update_metadata_status(video_id, metadata_complete=True)
                
                return clean_metadata
        
        except Exception as e:
            logger.error(f"yt-dlp metadata fetch failed for {video_id}: {e}")
            return None
    
    async def _download_audio_stage(
        self,
        metadata_results: dict[str, dict[str, Any]],
        progress_callback: Callable[[str], None] = None
    ) -> dict[str, int]:
        """
        Stage 2: Download audio for videos without audio.
        
        Args:
            metadata_results: Dict of video_id → metadata
            progress_callback: Optional progress callback
        
        Returns:
            Dict with downloaded, failed, skipped counts
        """
        results = {
            "downloaded": 0,
            "failed": 0,
            "skipped": 0,
        }
        
        # Check which videos need audio
        videos_needing_audio = []
        for video_id in metadata_results.keys():
            source = self.db_service.get_source(video_id)
            if source and source.audio_downloaded and source.audio_file_path:
                # Verify audio file exists
                if Path(source.audio_file_path).exists():
                    logger.info(f"Audio already exists for {video_id}, skipping")
                    results["skipped"] += 1
                    continue
            
            videos_needing_audio.append(video_id)
        
        if not videos_needing_audio:
            logger.info("All videos already have audio")
            return results
        
        logger.info(f"Downloading audio for {len(videos_needing_audio)} videos")
        
        # Download audio using yt-dlp
        from ..processors.youtube_download import YouTubeDownloadProcessor
        
        downloader = YouTubeDownloadProcessor(
            download_thumbnails=False,
            output_format="best"
        )
        
        for i, video_id in enumerate(videos_needing_audio):
            if progress_callback:
                progress_callback(
                    f"Downloading audio {i+1}/{len(videos_needing_audio)}: {video_id}"
                )
            
            try:
                url = f"https://www.youtube.com/watch?v={video_id}"
                
                result = downloader.process(
                    input_data=url,
                    output_dir=str(self.output_dir),
                    db_service=self.db_service
                )
                
                if result.success:
                    # Verify audio was linked
                    verification = self.db_service.verify_audio_metadata_link(video_id)
                    if verification["valid"]:
                        results["downloaded"] += 1
                        logger.info(f"✅ Downloaded and linked audio for {video_id}")
                    else:
                        results["failed"] += 1
                        logger.error(
                            f"❌ Audio download succeeded but linking failed: "
                            f"{verification['issues']}"
                        )
                else:
                    results["failed"] += 1
                    logger.error(f"❌ Audio download failed for {video_id}: {result.errors}")
            
            except Exception as e:
                results["failed"] += 1
                logger.error(f"❌ Error downloading audio for {video_id}: {e}")
        
        return results
    
    def _source_to_metadata_dict(self, source) -> dict[str, Any]:
        """Convert MediaSource to metadata dict."""
        return {
            "source_id": source.source_id,
            "title": source.title,
            "description": source.description,
            "uploader": source.uploader,
            "uploader_id": source.uploader_id,
            "upload_date": source.upload_date,
            "duration_seconds": source.duration_seconds,
            "view_count": source.view_count,
            "like_count": source.like_count,
            "comment_count": source.comment_count,
        }

