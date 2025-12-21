"""
Enhanced YouTube Download Processor with AI Summary Scraping
Wraps the existing YouTubeDownloadProcessor and adds YouTube AI summary extraction.
"""
import asyncio
import logging
from pathlib import Path
from typing import Any
from datetime import datetime

from .base import BaseProcessor, ProcessorResult
from .youtube_download import YouTubeDownloadProcessor
from ..services.playwright_youtube_scraper import PlaywrightYouTubeScraper
from ..database.service import DatabaseService

logger = logging.getLogger(__name__)


class YouTubeDownloadWithAISummary(BaseProcessor):
    """
    Enhanced YouTube downloader that also scrapes YouTube's AI-generated summary.
    
    Workflow:
    1. Download video audio + metadata (existing pipeline)
    2. Scrape YouTube AI summary (new feature)
    3. Save AI summary to database
    4. Return combined result
    """
    
    @property
    def supported_formats(self):
        """Return supported input formats."""
        return ["url"]
    
    def validate_input(self, input_data: Any) -> bool:
        """Validate that input is a YouTube URL."""
        url = str(input_data)
        return "youtube.com" in url or "youtu.be" in url
    
    def __init__(
        self,
        enable_ai_summary: bool = True,
        **youtube_processor_kwargs
    ):
        """
        Initialize enhanced processor.
        
        Args:
            enable_ai_summary: Whether to scrape YouTube AI summary
            **youtube_processor_kwargs: Arguments passed to YouTubeDownloadProcessor
        """
        super().__init__()
        self.enable_ai_summary = enable_ai_summary
        self.youtube_processor = YouTubeDownloadProcessor(**youtube_processor_kwargs)
        
        if enable_ai_summary:
            self.ai_scraper = PlaywrightYouTubeScraper(headless=True)
    
    def process(
        self,
        input_data: Any,
        progress_callback=None,
        **kwargs
    ) -> ProcessorResult:
        """
        Process YouTube URL: download + scrape AI summary.
        
        Args:
            input_data: YouTube URL
            progress_callback: Optional progress callback
            **kwargs: Additional arguments (db_service, etc.)
            
        Returns:
            ProcessorResult with download data + AI summary
        """
        url = str(input_data)
        db_service = kwargs.get('db_service')
        
        # Step 1: Download using existing pipeline
        if progress_callback:
            progress_callback("📥 Downloading video...")
        
        download_result = self.youtube_processor.process(
            input_data=input_data,
            progress_callback=progress_callback,
            **kwargs
        )
        
        if not download_result.success:
            return download_result
        
        # Extract source_id from download result
        source_id = download_result.data.get('source_id')
        if not source_id:
            logger.warning("No source_id in download result, cannot save AI summary")
            return download_result
        
        # Step 2: Scrape YouTube AI summary (if enabled)
        ai_summary = None
        if self.enable_ai_summary and db_service:
            if progress_callback:
                progress_callback("🤖 Scraping YouTube AI summary...")
            
            try:
                ai_summary_result = asyncio.run(
                    self.ai_scraper.scrape_summary(url, progress_callback)
                )
                
                if ai_summary_result['success']:
                    ai_summary = ai_summary_result['summary']
                    
                    # Save to database
                    self._save_ai_summary_to_db(
                        db_service,
                        source_id,
                        ai_summary,
                        ai_summary_result.get('duration', 0)
                    )
                    
                    if progress_callback:
                        progress_callback(f"✅ YouTube AI summary saved ({len(ai_summary)} chars)")
                    
                    logger.info(f"✅ Scraped YouTube AI summary for {source_id}: {len(ai_summary)} chars")
                else:
                    logger.warning(f"⚠️  YouTube AI summary scraping failed: {ai_summary_result.get('error')}")
                    if progress_callback:
                        progress_callback(f"⚠️  YouTube AI summary not available")
                        
            except Exception as e:
                logger.error(f"Failed to scrape AI summary: {e}", exc_info=True)
                if progress_callback:
                    progress_callback(f"⚠️  YouTube AI summary failed: {str(e)[:50]}")
        
        # Add AI summary to result data
        if ai_summary:
            download_result.data['youtube_ai_summary'] = ai_summary
            download_result.metadata['youtube_ai_summary_length'] = len(ai_summary)
        
        return download_result
    
    def _save_ai_summary_to_db(
        self,
        db_service: DatabaseService,
        source_id: str,
        ai_summary: str,
        duration: float
    ):
        """Save YouTube AI summary to database."""
        try:
            # Update the media source record with AI summary
            with db_service.get_session() as session:
                from ..database.models import MediaSource
                
                video = session.query(MediaSource).filter_by(source_id=source_id).first()
                if video:
                    video.youtube_ai_summary = ai_summary
                    video.youtube_ai_summary_fetched_at = datetime.utcnow()
                    video.youtube_ai_summary_method = 'playwright_scraper'
                    session.commit()
                    logger.info(f"✅ Saved YouTube AI summary to database for {source_id}")
                else:
                    logger.warning(f"⚠️  Video record not found for {source_id}, cannot save AI summary")
                    
        except Exception as e:
            logger.error(f"Failed to save AI summary to database: {e}", exc_info=True)

