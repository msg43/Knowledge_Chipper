"""
Feedback Processor - Background worker for async feedback processing

Processes the pending_feedback queue and updates ChromaDB asynchronously.
This ensures the /feedback/sync endpoint remains low-latency.

Key features:
- Reads from pending_feedback SQLite queue
- Calculates embeddings and adds to TasteEngine
- Handles retries with exponential backoff
- Runs as a background thread
"""

import json
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..logger import get_logger
from ..services.taste_engine import get_taste_engine, FeedbackExample

logger = get_logger(__name__)


class FeedbackProcessor:
    """
    Background worker that processes the pending_feedback queue.
    
    Reads raw JSON from the queue, validates it, calculates embeddings,
    and adds to the TasteEngine (ChromaDB).
    """
    
    def __init__(
        self,
        db_path: Optional[Path] = None,
        poll_interval: float = 5.0,
        max_retries: int = 3
    ):
        """
        Initialize the feedback processor.
        
        Args:
            db_path: Path to the SQLite database. Defaults to Application Support.
            poll_interval: Seconds between queue checks.
            max_retries: Maximum retry attempts for failed items.
        """
        if db_path is None:
            db_path = Path.home() / "Library" / "Application Support" / "SkipThePodcast" / "knowledge_system.db"
        
        self.db_path = Path(db_path)
        self.poll_interval = poll_interval
        self.max_retries = max_retries
        
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._taste_engine = None
    
    @property
    def taste_engine(self):
        """Lazy-load the taste engine."""
        if self._taste_engine is None:
            self._taste_engine = get_taste_engine()
        return self._taste_engine
    
    def start(self):
        """Start the background processor thread."""
        if self._running:
            logger.warning("Feedback processor already running")
            return
        
        self._running = True
        self._thread = threading.Thread(
            target=self._process_loop,
            name="FeedbackProcessor",
            daemon=True
        )
        self._thread.start()
        logger.info("Feedback processor started")
    
    def stop(self):
        """Stop the background processor thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
        logger.info("Feedback processor stopped")
    
    def _process_loop(self):
        """Main processing loop."""
        while self._running:
            try:
                processed = self._process_pending_items()
                if processed > 0:
                    logger.info(f"Processed {processed} feedback items")
            except Exception as e:
                logger.error(f"Error in feedback processor loop: {e}")
            
            # Wait before next poll
            time.sleep(self.poll_interval)
    
    def _process_pending_items(self) -> int:
        """Process all pending items in the queue."""
        if not self.db_path.exists():
            return 0
        
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get unprocessed items
        cursor.execute("""
            SELECT id, raw_json, retry_count
            FROM pending_feedback
            WHERE processed_at IS NULL
            AND retry_count < ?
            ORDER BY received_at ASC
            LIMIT 50
        """, (self.max_retries,))
        
        items = cursor.fetchall()
        processed_count = 0
        
        for item in items:
            try:
                self._process_item(item, cursor)
                processed_count += 1
            except Exception as e:
                logger.error(f"Failed to process feedback item {item['id']}: {e}")
                self._mark_failed(item['id'], str(e), cursor)
        
        conn.commit()
        conn.close()
        
        return processed_count
    
    def _process_item(self, item: sqlite3.Row, cursor: sqlite3.Cursor):
        """Process a single feedback item."""
        raw_json = item['raw_json']
        
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")
        
        entity_text = data.get('entity_text', '')
        entity_type = data.get('entity_type', 'claim')
        verdict = data.get('verdict', 'reject')
        
        # Check for duplicates before adding
        if self.taste_engine.has_example(entity_text, entity_type, verdict):
            logger.debug(f"Skipping duplicate feedback: {entity_text[:50]}...")
            # Mark as processed even though we skipped it (to avoid reprocessing)
            cursor.execute("""
                UPDATE pending_feedback
                SET processed_at = ?
                WHERE id = ?
            """, (datetime.utcnow().isoformat(), item['id']))
            return
        
        # Create FeedbackExample from data
        feedback = FeedbackExample(
            entity_type=entity_type,
            entity_text=entity_text,
            verdict=verdict,
            reason_category=data.get('reason_category', 'other'),
            user_notes=data.get('user_notes', ''),
            source_id=data.get('source_id', ''),
            created_at=data.get('created_at', datetime.utcnow().isoformat()),
            is_golden=False,
            is_shared=data.get('is_shared', False)  # From GetReceipts sync
        )
        
        # Add to TasteEngine (this calculates embedding)
        doc_id = self.taste_engine.add_feedback(feedback)
        
        # Mark as processed
        cursor.execute("""
            UPDATE pending_feedback
            SET processed_at = ?
            WHERE id = ?
        """, (datetime.utcnow().isoformat(), item['id']))
        
        # Also insert into feedback_examples for audit trail
        cursor.execute("""
            INSERT INTO feedback_examples 
            (entity_type, entity_text, verdict, reason_category, user_notes, source_id, is_processed, processed_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
        """, (
            feedback.entity_type,
            feedback.entity_text,
            feedback.verdict,
            feedback.reason_category,
            feedback.user_notes,
            feedback.source_id,
            datetime.utcnow().isoformat()
        ))
        
        logger.debug(f"Processed feedback: {doc_id}")
    
    def _mark_failed(self, item_id: int, error: str, cursor: sqlite3.Cursor):
        """Mark an item as failed and increment retry count."""
        cursor.execute("""
            UPDATE pending_feedback
            SET retry_count = retry_count + 1,
                error_message = ?
            WHERE id = ?
        """, (error, item_id))
    
    def get_queue_status(self) -> dict:
        """Get the current status of the pending queue."""
        if not self.db_path.exists():
            return {
                "pending": 0,
                "failed": 0,
                "processed_today": 0
            }
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Count pending
        cursor.execute("""
            SELECT COUNT(*) FROM pending_feedback
            WHERE processed_at IS NULL AND retry_count < ?
        """, (self.max_retries,))
        pending = cursor.fetchone()[0]
        
        # Count failed (exceeded retries)
        cursor.execute("""
            SELECT COUNT(*) FROM pending_feedback
            WHERE processed_at IS NULL AND retry_count >= ?
        """, (self.max_retries,))
        failed = cursor.fetchone()[0]
        
        # Count processed today
        today = datetime.utcnow().strftime("%Y-%m-%d")
        cursor.execute("""
            SELECT COUNT(*) FROM pending_feedback
            WHERE processed_at LIKE ?
        """, (f"{today}%",))
        processed_today = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "pending": pending,
            "failed": failed,
            "processed_today": processed_today,
            "is_running": self._running
        }


# Module-level singleton
_feedback_processor: Optional[FeedbackProcessor] = None


def start_feedback_processor(
    db_path: Optional[Path] = None,
    poll_interval: float = 5.0
) -> FeedbackProcessor:
    """Start the global feedback processor."""
    global _feedback_processor
    
    if _feedback_processor is None:
        _feedback_processor = FeedbackProcessor(
            db_path=db_path,
            poll_interval=poll_interval
        )
    
    _feedback_processor.start()
    return _feedback_processor


def stop_feedback_processor():
    """Stop the global feedback processor."""
    global _feedback_processor
    
    if _feedback_processor is not None:
        _feedback_processor.stop()


def get_feedback_processor() -> Optional[FeedbackProcessor]:
    """Get the global feedback processor instance."""
    return _feedback_processor
