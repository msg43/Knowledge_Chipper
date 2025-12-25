"""
Review Queue Service for database operations.

Provides CRUD operations for review queue items, supporting persistence
of the bulk review workflow across sessions.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from ..logger import get_logger
from .models import ReviewQueueItem
from .service import DatabaseService

logger = get_logger(__name__)


class ReviewQueueService:
    """
    Service for managing review queue items in the database.
    
    Supports:
    - Loading pending items on app startup
    - Saving new items from extraction
    - Updating item status (accept/reject)
    - Syncing accepted items to GetReceipts
    - Cleaning up synced items
    """

    def __init__(self, db_service: Optional[DatabaseService] = None):
        """Initialize the service."""
        self.db_service = db_service or DatabaseService()
    
    def _get_session(self) -> Session:
        """Get a database session."""
        return self.db_service.get_session()
    
    # ========================================================================
    # Load operations
    # ========================================================================
    
    def load_pending_items(self) -> list[dict]:
        """
        Load all pending (unreviewed) items from the database.
        
        Returns:
            List of item dictionaries suitable for ReviewQueueModel
        """
        session = self._get_session()
        try:
            items = session.query(ReviewQueueItem).filter(
                ReviewQueueItem.review_status == "pending"
            ).order_by(
                ReviewQueueItem.source_title,
                ReviewQueueItem.entity_type,
                ReviewQueueItem.importance.desc()
            ).all()
            
            return [self._item_to_dict(item) for item in items]
        except Exception as e:
            logger.error(f"Error loading pending items: {e}")
            return []
        finally:
            session.close()
    
    def load_all_unsynced_items(self) -> list[dict]:
        """
        Load all items that haven't been synced yet (pending + accepted but unsynced).
        
        Returns:
            List of item dictionaries
        """
        session = self._get_session()
        try:
            items = session.query(ReviewQueueItem).filter(
                or_(
                    ReviewQueueItem.review_status == "pending",
                    and_(
                        ReviewQueueItem.review_status == "accepted",
                        ReviewQueueItem.synced_at.is_(None)
                    )
                )
            ).order_by(
                ReviewQueueItem.source_title,
                ReviewQueueItem.entity_type,
                ReviewQueueItem.importance.desc()
            ).all()
            
            return [self._item_to_dict(item) for item in items]
        except Exception as e:
            logger.error(f"Error loading unsynced items: {e}")
            return []
        finally:
            session.close()
    
    def load_items_by_source(self, source_id: str) -> list[dict]:
        """
        Load all items for a specific source.
        
        Args:
            source_id: Source ID to filter by
            
        Returns:
            List of item dictionaries
        """
        session = self._get_session()
        try:
            items = session.query(ReviewQueueItem).filter(
                ReviewQueueItem.source_id == source_id
            ).order_by(
                ReviewQueueItem.entity_type,
                ReviewQueueItem.importance.desc()
            ).all()
            
            return [self._item_to_dict(item) for item in items]
        except Exception as e:
            logger.error(f"Error loading items for source {source_id}: {e}")
            return []
        finally:
            session.close()
    
    def get_status_counts(self) -> dict[str, int]:
        """
        Get counts of items by status.
        
        Returns:
            Dict with counts: {"pending": N, "accepted": N, "rejected": N}
        """
        session = self._get_session()
        try:
            from sqlalchemy import func
            
            counts = session.query(
                ReviewQueueItem.review_status,
                func.count(ReviewQueueItem.item_id)
            ).group_by(ReviewQueueItem.review_status).all()
            
            result = {"pending": 0, "accepted": 0, "rejected": 0}
            for status, count in counts:
                result[status] = count
            
            return result
        except Exception as e:
            logger.error(f"Error getting status counts: {e}")
            return {"pending": 0, "accepted": 0, "rejected": 0}
        finally:
            session.close()
    
    def get_type_counts(self) -> dict[str, int]:
        """
        Get counts of items by entity type.
        
        Returns:
            Dict with counts: {"claim": N, "jargon": N, "person": N, "concept": N}
        """
        session = self._get_session()
        try:
            from sqlalchemy import func
            
            counts = session.query(
                ReviewQueueItem.entity_type,
                func.count(ReviewQueueItem.item_id)
            ).group_by(ReviewQueueItem.entity_type).all()
            
            result = {"claim": 0, "jargon": 0, "person": 0, "concept": 0}
            for entity_type, count in counts:
                result[entity_type] = count
            
            return result
        except Exception as e:
            logger.error(f"Error getting type counts: {e}")
            return {"claim": 0, "jargon": 0, "person": 0, "concept": 0}
        finally:
            session.close()
    
    def get_unique_sources(self) -> list[tuple[str, str]]:
        """
        Get list of unique sources in the queue.
        
        Returns:
            List of (source_title, source_id) tuples
        """
        session = self._get_session()
        try:
            sources = session.query(
                ReviewQueueItem.source_title,
                ReviewQueueItem.source_id
            ).distinct().filter(
                ReviewQueueItem.source_id.isnot(None)
            ).all()
            
            return [(title or "Unknown", sid or "") for title, sid in sources]
        except Exception as e:
            logger.error(f"Error getting unique sources: {e}")
            return []
        finally:
            session.close()
    
    # ========================================================================
    # Save operations
    # ========================================================================
    
    def add_item(
        self,
        entity_type: str,
        content: str,
        source_id: str = "",
        source_title: str = "",
        tier: str = "C",
        importance: float = 0,
        raw_data: Optional[dict] = None,
        review_status: str = "pending",
    ) -> str:
        """
        Add a new item to the review queue.
        
        Args:
            entity_type: 'claim', 'jargon', 'person', or 'concept'
            content: Display text for the item
            source_id: Optional source ID
            source_title: Optional source title
            tier: Quality tier (A/B/C/D)
            importance: Importance score
            raw_data: Full entity data as dict
            review_status: Initial status (default: 'pending')
            
        Returns:
            Generated item_id
        """
        item_id = str(uuid.uuid4())
        
        session = self._get_session()
        try:
            item = ReviewQueueItem(
                item_id=item_id,
                entity_type=entity_type,
                review_status=review_status,
                source_id=source_id if source_id else None,
                source_title=source_title,
                content=content,
                tier=tier,
                importance=importance,
                raw_data=raw_data,
            )
            session.add(item)
            session.commit()
            logger.debug(f"Added review queue item: {item_id} ({entity_type})")
            return item_id
        except Exception as e:
            session.rollback()
            logger.error(f"Error adding review queue item: {e}")
            raise
        finally:
            session.close()
    
    def add_items_batch(self, items: list[dict]) -> list[str]:
        """
        Add multiple items to the review queue in a single transaction.
        
        Args:
            items: List of item dicts with keys matching add_item args
            
        Returns:
            List of generated item_ids
        """
        item_ids = []
        session = self._get_session()
        try:
            for item_data in items:
                item_id = str(uuid.uuid4())
                item_ids.append(item_id)
                
                item = ReviewQueueItem(
                    item_id=item_id,
                    entity_type=item_data.get("entity_type", "claim"),
                    review_status=item_data.get("review_status", "pending"),
                    source_id=item_data.get("source_id") or None,
                    source_title=item_data.get("source_title", ""),
                    content=item_data.get("content", ""),
                    tier=item_data.get("tier", "C"),
                    importance=item_data.get("importance", 0),
                    raw_data=item_data.get("raw_data"),
                )
                session.add(item)
            
            session.commit()
            logger.info(f"Added {len(item_ids)} items to review queue")
            return item_ids
        except Exception as e:
            session.rollback()
            logger.error(f"Error adding batch to review queue: {e}")
            raise
        finally:
            session.close()
    
    # ========================================================================
    # Update operations
    # ========================================================================
    
    def update_status(self, item_id: str, status: str) -> bool:
        """
        Update the review status of an item.
        
        Args:
            item_id: Item ID
            status: New status ('pending', 'accepted', 'rejected')
            
        Returns:
            True if successful
        """
        session = self._get_session()
        try:
            item = session.query(ReviewQueueItem).filter(
                ReviewQueueItem.item_id == item_id
            ).first()
            
            if item:
                item.review_status = status
                item.reviewed_at = datetime.utcnow()
                item.updated_at = datetime.utcnow()
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating item status: {e}")
            return False
        finally:
            session.close()
    
    def update_status_batch(self, item_ids: list[str], status: str) -> int:
        """
        Update the review status of multiple items.
        
        Args:
            item_ids: List of item IDs
            status: New status
            
        Returns:
            Number of items updated
        """
        session = self._get_session()
        try:
            now = datetime.utcnow()
            count = session.query(ReviewQueueItem).filter(
                ReviewQueueItem.item_id.in_(item_ids)
            ).update({
                "review_status": status,
                "reviewed_at": now,
                "updated_at": now,
            }, synchronize_session=False)
            
            session.commit()
            logger.info(f"Updated {count} items to status '{status}'")
            return count
        except Exception as e:
            session.rollback()
            logger.error(f"Error batch updating status: {e}")
            return 0
        finally:
            session.close()
    
    def update_item(
        self,
        item_id: str,
        content: Optional[str] = None,
        tier: Optional[str] = None,
        importance: Optional[float] = None,
        raw_data: Optional[dict] = None,
    ) -> bool:
        """
        Update item content/metadata.
        
        Args:
            item_id: Item ID
            content: New content text
            tier: New tier
            importance: New importance score
            raw_data: New raw data dict
            
        Returns:
            True if successful
        """
        session = self._get_session()
        try:
            item = session.query(ReviewQueueItem).filter(
                ReviewQueueItem.item_id == item_id
            ).first()
            
            if item:
                if content is not None:
                    item.content = content
                if tier is not None:
                    item.tier = tier
                if importance is not None:
                    item.importance = importance
                if raw_data is not None:
                    item.raw_data = raw_data
                item.updated_at = datetime.utcnow()
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating item: {e}")
            return False
        finally:
            session.close()
    
    def mark_synced(self, item_ids: list[str]) -> int:
        """
        Mark items as synced to GetReceipts.
        
        Args:
            item_ids: List of item IDs that were synced
            
        Returns:
            Number of items marked
        """
        session = self._get_session()
        try:
            now = datetime.utcnow()
            count = session.query(ReviewQueueItem).filter(
                ReviewQueueItem.item_id.in_(item_ids)
            ).update({
                "synced_at": now,
                "updated_at": now,
            }, synchronize_session=False)
            
            session.commit()
            logger.info(f"Marked {count} items as synced")
            return count
        except Exception as e:
            session.rollback()
            logger.error(f"Error marking items as synced: {e}")
            return 0
        finally:
            session.close()
    
    def mark_sync_error(self, item_id: str, error: str) -> bool:
        """
        Record a sync error for an item.
        
        Args:
            item_id: Item ID
            error: Error message
            
        Returns:
            True if successful
        """
        session = self._get_session()
        try:
            item = session.query(ReviewQueueItem).filter(
                ReviewQueueItem.item_id == item_id
            ).first()
            
            if item:
                item.sync_error = error
                item.updated_at = datetime.utcnow()
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"Error recording sync error: {e}")
            return False
        finally:
            session.close()
    
    def is_item_synced(self, item_id: str) -> bool:
        """
        Check if an item has been synced to GetReceipts.
        
        Args:
            item_id: Item ID to check
            
        Returns:
            True if item has been synced (synced_at is not NULL)
        """
        session = self._get_session()
        try:
            item = session.query(ReviewQueueItem).filter(
                ReviewQueueItem.item_id == item_id
            ).first()
            
            if item:
                return item.synced_at is not None
            return False
        except Exception as e:
            logger.error(f"Error checking sync status: {e}")
            return False
        finally:
            session.close()
    
    # ========================================================================
    # Delete operations
    # ========================================================================
    
    def delete_item(self, item_id: str) -> bool:
        """
        Delete an item from the queue.
        
        Args:
            item_id: Item ID
            
        Returns:
            True if successful
        """
        session = self._get_session()
        try:
            count = session.query(ReviewQueueItem).filter(
                ReviewQueueItem.item_id == item_id
            ).delete()
            session.commit()
            return count > 0
        except Exception as e:
            session.rollback()
            logger.error(f"Error deleting item: {e}")
            return False
        finally:
            session.close()
    
    def delete_synced_items(self) -> int:
        """
        Delete all items that have been synced.
        
        Returns:
            Number of items deleted
        """
        session = self._get_session()
        try:
            count = session.query(ReviewQueueItem).filter(
                ReviewQueueItem.synced_at.isnot(None)
            ).delete()
            session.commit()
            logger.info(f"Deleted {count} synced items from queue")
            return count
        except Exception as e:
            session.rollback()
            logger.error(f"Error deleting synced items: {e}")
            return 0
        finally:
            session.close()
    
    def clear_queue(self) -> int:
        """
        Clear all items from the queue.
        
        Returns:
            Number of items deleted
        """
        session = self._get_session()
        try:
            count = session.query(ReviewQueueItem).delete()
            session.commit()
            logger.info(f"Cleared {count} items from review queue")
            return count
        except Exception as e:
            session.rollback()
            logger.error(f"Error clearing queue: {e}")
            return 0
        finally:
            session.close()
    
    # ========================================================================
    # Helper methods
    # ========================================================================
    
    def _item_to_dict(self, item: ReviewQueueItem) -> dict:
        """Convert a ReviewQueueItem to a dictionary."""
        return {
            "item_id": item.item_id,
            "entity_type": item.entity_type,
            "review_status": item.review_status,
            "source_id": item.source_id,
            "source_title": item.source_title,
            "content": item.content,
            "tier": item.tier,
            "importance": item.importance,
            "raw_data": item.raw_data or {},
            "synced_at": item.synced_at.isoformat() if item.synced_at else None,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "reviewed_at": item.reviewed_at.isoformat() if item.reviewed_at else None,
        }
    
    def ensure_table_exists(self):
        """Ensure the review_queue_items table exists."""
        try:
            from .models import Base, create_database_engine
            engine = create_database_engine()
            Base.metadata.create_all(engine, tables=[ReviewQueueItem.__table__])
            logger.info("Review queue table ensured")
        except Exception as e:
            logger.error(f"Error ensuring review queue table: {e}")

