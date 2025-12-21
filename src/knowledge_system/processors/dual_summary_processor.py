"""
Dual Summary Processor
Generates both YouTube AI and local LLM summaries for comparison.
"""
import asyncio
import logging
from typing import Dict, Any, Optional, Callable
from pathlib import Path

from .base import BaseProcessor, ProcessorResult
from ..services.playwright_youtube_scraper import PlaywrightYouTubeScraper

logger = logging.getLogger(__name__)


class DualSummaryProcessor(BaseProcessor):
    """
    Generates both YouTube AI summary (via scraping) and local LLM summary
    (via download + transcribe + summarize) for comparison.
    """
    
    @property
    def supported_formats(self):
        """Return supported input formats."""
        return ["url"]
    
    def validate_input(self, input_data: Any) -> bool:
        """Validate that input is a YouTube URL."""
        url = str(input_data)
        return "youtube.com" in url or "youtu.be" in url
    
    def __init__(self, youtube_scraper_enabled: bool = True):
        super().__init__()
        self.youtube_scraper_enabled = youtube_scraper_enabled
        self.youtube_scraper = PlaywrightYouTubeScraper(headless=True)
    
    def process(
        self,
        input_data: Any,
        progress_callback: Optional[Callable] = None,
        **kwargs
    ) -> ProcessorResult:
        """
        Process video URL through both summary paths.
        
        Args:
            input_data: YouTube video URL
            progress_callback: Optional callback for progress updates
            
        Returns:
            ProcessorResult with both summaries and comparison
        """
        url = str(input_data)
        
        if progress_callback:
            progress_callback("🚀 Starting dual summary generation...")
        
        # Run both paths in parallel using asyncio
        youtube_result, local_result = asyncio.run(
            self._process_both_paths(url, progress_callback)
        )
        
        # Generate comparison
        comparison = self._generate_comparison(youtube_result, local_result)
        
        # Determine overall success
        success = youtube_result['success'] or local_result['success']
        
        return ProcessorResult(
            success=success,
            data={
                'youtube_summary': youtube_result,
                'local_summary': local_result,
                'comparison': comparison,
                'url': url
            },
            metadata={
                'youtube_enabled': self.youtube_scraper_enabled,
                'youtube_success': youtube_result['success'],
                'local_success': local_result['success']
            }
        )
    
    async def _process_both_paths(
        self,
        url: str,
        progress_callback: Optional[Callable]
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Run both processing paths in parallel."""
        
        # Create tasks for both paths
        tasks = []
        
        if self.youtube_scraper_enabled:
            tasks.append(self._youtube_path(url, progress_callback))
        else:
            # Create dummy result if disabled
            tasks.append(self._create_disabled_result())
        
        tasks.append(self._local_path(url, progress_callback))
        
        # Run in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        youtube_result = results[0] if not isinstance(results[0], Exception) else {
            'success': False,
            'error': str(results[0]),
            'method': 'youtube_ai'
        }
        
        local_result = results[1] if not isinstance(results[1], Exception) else {
            'success': False,
            'error': str(results[1]),
            'method': 'local_llm'
        }
        
        return youtube_result, local_result
    
    async def _youtube_path(
        self,
        url: str,
        progress_callback: Optional[Callable]
    ) -> Dict[str, Any]:
        """YouTube AI scraping path."""
        if progress_callback:
            progress_callback("🤖 Path 1: Scraping YouTube AI summary...")
        
        result = await self.youtube_scraper.scrape_summary(url, progress_callback)
        
        if result['success']:
            logger.info(f"✅ YouTube summary: {result['duration']:.1f}s, "
                       f"{len(result['summary'])} chars")
        else:
            logger.warning(f"❌ YouTube scraping failed: {result['error']}")
        
        return result
    
    async def _local_path(
        self,
        url: str,
        progress_callback: Optional[Callable]
    ) -> Dict[str, Any]:
        """Local download + transcribe + summarize path (placeholder for now)."""
        import time
        
        if progress_callback:
            progress_callback("🧠 Path 2: Local LLM summary (not yet implemented in this branch)")
        
        # TODO: Implement full local path with proper processor imports
        # For now, just return a placeholder
        return {
            'success': False,
            'summary': None,
            'duration': 0,
            'error': 'Local LLM path not yet implemented in this feature branch',
            'method': 'local_llm'
        }
    
    async def _create_disabled_result(self) -> Dict[str, Any]:
        """Create result for disabled YouTube scraping."""
        return {
            'success': False,
            'summary': None,
            'duration': 0,
            'error': 'YouTube scraping disabled',
            'method': 'youtube_ai'
        }
    
    def _generate_comparison(
        self,
        youtube_result: Dict[str, Any],
        local_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate comparison metrics between both summaries."""
        comparison = {
            'both_succeeded': youtube_result['success'] and local_result['success'],
            'youtube_only': youtube_result['success'] and not local_result['success'],
            'local_only': local_result['success'] and not youtube_result['success'],
            'both_failed': not youtube_result['success'] and not local_result['success']
        }
        
        if comparison['both_succeeded']:
            yt_summary = youtube_result['summary']
            local_summary = local_result['summary']
            
            comparison.update({
                'youtube_length': len(yt_summary),
                'local_length': len(local_summary),
                'youtube_words': len(yt_summary.split()),
                'local_words': len(local_summary.split()),
                'youtube_duration': youtube_result['duration'],
                'local_duration': local_result['duration'],
                'speed_ratio': local_result['duration'] / youtube_result['duration'] if youtube_result['duration'] > 0 else 0,
                'length_ratio': len(local_summary) / len(yt_summary) if len(yt_summary) > 0 else 0
            })
        
        return comparison

