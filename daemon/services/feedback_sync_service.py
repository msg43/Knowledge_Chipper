"""
Feedback Sync Service - Download shared feedback from GetReceipts.org

Syncs Matt's curated feedback (is_shared=TRUE) from the web API
into the local TasteEngine for all users.
"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx

from ..config.settings import Settings
from ...src.knowledge_system.services.taste_engine import get_taste_engine, FeedbackExample
from ...src.knowledge_system.logger import get_logger

logger = get_logger(__name__)

# Sync interval (24 hours)
SYNC_INTERVAL_HOURS = 24


class FeedbackSyncService:
    """Syncs shared feedback from GetReceipts.org to local TasteEngine."""
    
    LAST_SYNC_FILE = Path.home() / "Library" / "Application Support" / "KnowledgeChipper" / ".last_feedback_sync"
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = "https://getreceipts.org"  # Or from settings
        self.taste_engine = get_taste_engine()
    
    async def sync_feedback(self) -> dict:
        """
        Sync shared feedback from web API.
        
        Returns stats about the sync operation.
        """
        try:
            # Get last sync timestamp
            last_sync = self._get_last_sync_timestamp()
            
            # Build API URL
            url = f"{self.base_url}/api/feedback/sync"
            params = {}
            if last_sync:
                params['since'] = last_sync.isoformat()
            
            # Fetch feedback
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
            
            feedback_list = data.get('feedback', [])
            
            # Ingest into TasteEngine
            added_count = 0
            skipped_count = 0
            
            for item in feedback_list:
                # Check if already exists
                if self.taste_engine.has_example(
                    item['entity_text'],
                    item['entity_type'],
                    item['verdict']
                ):
                    skipped_count += 1
                    continue
                
                # Add to TasteEngine
                feedback = FeedbackExample(
                    entity_type=item['entity_type'],
                    entity_text=item['entity_text'],
                    verdict=item['verdict'],
                    reason_category=item['reason_category'],
                    user_notes=item.get('user_notes', ''),
                    source_id=item.get('source_id', ''),
                    created_at=item['created_at'],
                    is_shared=True  # Mark as shared feedback
                )
                
                self.taste_engine.add_feedback(feedback, skip_validation=True)
                added_count += 1
            
            # Update last sync timestamp
            self._save_last_sync_timestamp()
            
            stats = {
                'success': True,
                'added': added_count,
                'skipped': skipped_count,
                'total_available': data.get('total_count', 0),
                'sync_timestamp': data.get('sync_timestamp')
            }
            
            logger.info(f"Feedback sync complete: {added_count} added, {skipped_count} skipped")
            return stats
            
        except Exception as e:
            logger.error(f"Feedback sync failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def should_sync(self) -> bool:
        """Check if it's time to sync."""
        last_sync = self._get_last_sync_timestamp()
        if not last_sync:
            return True
        
        time_since_sync = datetime.utcnow() - last_sync
        return time_since_sync > timedelta(hours=SYNC_INTERVAL_HOURS)
    
    def _get_last_sync_timestamp(self) -> Optional[datetime]:
        """Get the last sync timestamp from file."""
        if not self.LAST_SYNC_FILE.exists():
            return None
        
        try:
            timestamp_str = self.LAST_SYNC_FILE.read_text().strip()
            return datetime.fromisoformat(timestamp_str)
        except Exception:
            return None
    
    def _save_last_sync_timestamp(self):
        """Save the current timestamp as last sync."""
        try:
            self.LAST_SYNC_FILE.parent.mkdir(parents=True, exist_ok=True)
            self.LAST_SYNC_FILE.write_text(datetime.utcnow().isoformat())
        except Exception as e:
            logger.warning(f"Failed to save last sync timestamp: {e}")


class FeedbackSyncScheduler:
    """Schedules periodic feedback syncs."""
    
    def __init__(self, sync_service: FeedbackSyncService):
        """
        Initialize feedback sync scheduler.
        
        Args:
            sync_service: FeedbackSyncService instance
        """
        self.sync_service = sync_service
        self.task: Optional[asyncio.Task] = None
        self.running = False
    
    async def start(self):
        """Start the feedback sync scheduler."""
        if self.running:
            logger.warning("Feedback sync scheduler already running")
            return
            
        self.running = True
        self.task = asyncio.create_task(self._sync_loop())
        logger.info(f"Feedback sync scheduler started (syncs every {SYNC_INTERVAL_HOURS} hours)")
    
    async def stop(self):
        """Stop the feedback sync scheduler."""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None
        logger.info("Feedback sync scheduler stopped")
    
    async def _sync_loop(self):
        """Periodic feedback sync loop."""
        # Initial sync on startup (after 5 minute delay to avoid startup issues)
        logger.info("Scheduling initial feedback sync in 5 minutes...")
        await asyncio.sleep(300)  # 5 minutes
        
        while self.running:
            try:
                if self.sync_service.should_sync():
                    logger.info("Running scheduled feedback sync...")
                    result = await self.sync_service.sync_feedback()
                    
                    if result.get('success'):
                        logger.info(f"Scheduled sync complete: {result.get('added', 0)} added, {result.get('skipped', 0)} skipped")
                    else:
                        logger.error(f"Scheduled sync failed: {result.get('error', 'Unknown error')}")
                else:
                    logger.debug("Skipping sync (synced recently)")
                    
            except Exception as e:
                logger.error(f"Feedback sync failed: {e}", exc_info=True)
            
            # Wait for next sync interval
            logger.debug(f"Next feedback sync in {SYNC_INTERVAL_HOURS} hours")
            await asyncio.sleep(SYNC_INTERVAL_HOURS * 3600)


# Global instances
_feedback_sync_service: Optional[FeedbackSyncService] = None
_feedback_sync_scheduler: Optional[FeedbackSyncScheduler] = None


def get_feedback_sync_service(settings: Settings) -> FeedbackSyncService:
    """Get or create global feedback sync service instance."""
    global _feedback_sync_service
    if _feedback_sync_service is None:
        _feedback_sync_service = FeedbackSyncService(settings)
    return _feedback_sync_service


def get_feedback_sync_scheduler(settings: Settings) -> FeedbackSyncScheduler:
    """Get or create global feedback sync scheduler instance."""
    global _feedback_sync_scheduler
    if _feedback_sync_scheduler is None:
        sync_service = get_feedback_sync_service(settings)
        _feedback_sync_scheduler = FeedbackSyncScheduler(sync_service)
    return _feedback_sync_scheduler
