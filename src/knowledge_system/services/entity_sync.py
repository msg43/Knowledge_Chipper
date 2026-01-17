"""
Unified Entity Sync Service

ONE service for syncing ALL entity types to GetReceipts.org.
Handles both batch (extraction) and individual (predictions, health) sync patterns.

Architecture:
- Uses existing GetReceiptsUploader under the hood
- Supports batch sync: upload_entities(entity_type, entities[])
- Supports individual sync: upload_single(entity_type, entity)
- Tracks sync status in local database
- Web is source of truth (web-canonical)

Usage:
    from knowledge_system.services.entity_sync import get_entity_sync_service
    
    sync = get_entity_sync_service()
    
    # Individual entity
    result = sync.upload_single('health_interventions', intervention_data)
    
    # Batch entities
    result = sync.upload_entities('claims', [claim1, claim2, claim3])
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from ..database.connection import DatabaseConnection
from ..database.models import HealthIntervention, HealthMetric, HealthIssue
from ..logger import get_logger
from .device_auth import get_device_auth

logger = get_logger(__name__)


# Default database path for feedback queue
DEFAULT_DB_PATH = Path.home() / "Library" / "Application Support" / "SkipThePodcast" / "knowledge_system.db"


class EntitySyncService:
    """
    Unified sync service for ALL entity types.
    
    Handles:
    - Extraction entities (claims, jargon, people, concepts) - batch
    - Predictions - individual
    - Health tracking (interventions, metrics, issues) - individual
    - Any future entity types
    """

    def __init__(self, use_production: bool = True, db_path: Optional[Path] = None):
        """
        Initialize the entity sync service.
        
        Args:
            use_production: Whether to use production API (default: True)
            db_path: Path to SQLite database for feedback queue
        """
        self.use_production = use_production
        self.device_auth = get_device_auth()
        self.db = DatabaseConnection()
        self.feedback_db_path = db_path or DEFAULT_DB_PATH

    def is_sync_enabled(self) -> bool:
        """Check if sync is enabled for this device."""
        return self.device_auth.is_enabled()

    def upload_single(self, entity_type: str, entity_data: dict[str, Any]) -> dict[str, Any]:
        """
        Upload a single entity to GetReceipts.org.
        
        Args:
            entity_type: Type of entity (health_interventions, health_metrics, health_issues, predictions, etc.)
            entity_data: Entity data dict
            
        Returns:
            Dict with upload result
        """
        if not self.is_sync_enabled():
            logger.info(f"Sync disabled - {entity_type} not synced")
            return {"success": False, "reason": "sync_disabled"}

        try:
            # Wrap single entity as batch of 1
            session_data = {entity_type: [entity_data]}
            
            # Use existing upload infrastructure
            from ..integrations.getreceipts_integration import upload_to_getreceipts
            
            logger.info(f"🔄 Uploading {entity_type} to GetReceipts...")
            result = upload_to_getreceipts(session_data, use_production=self.use_production)
            
            if result:
                logger.info(f"✅ {entity_type} synced successfully")
                return {"success": True, "result": result}
            else:
                logger.error(f"❌ {entity_type} sync failed")
                return {"success": False, "reason": "upload_failed"}
                
        except Exception as e:
            logger.error(f"❌ Failed to sync {entity_type}: {e}")
            return {"success": False, "reason": "error", "error": str(e)}

    def upload_entities(self, entity_type: str, entities: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Upload multiple entities to GetReceipts.org (batch).
        
        Args:
            entity_type: Type of entities (claims, jargon, people, concepts, etc.)
            entities: List of entity data dicts
            
        Returns:
            Dict with upload result
        """
        if not self.is_sync_enabled():
            logger.info(f"Sync disabled - {len(entities)} {entity_type} not synced")
            return {"success": False, "reason": "sync_disabled"}

        try:
            session_data = {entity_type: entities}
            
            # Use existing upload infrastructure
            from ..integrations.getreceipts_integration import upload_to_getreceipts
            
            logger.info(f"🔄 Uploading {len(entities)} {entity_type} to GetReceipts...")
            result = upload_to_getreceipts(session_data, use_production=self.use_production)
            
            if result:
                logger.info(f"✅ {len(entities)} {entity_type} synced successfully")
                return {"success": True, "result": result}
            else:
                logger.error(f"❌ {entity_type} batch sync failed")
                return {"success": False, "reason": "upload_failed"}
                
        except Exception as e:
            logger.error(f"❌ Failed to batch sync {entity_type}: {e}")
            return {"success": False, "reason": "error", "error": str(e)}

    # Convenience methods for specific entity types

    def sync_health_intervention(self, intervention_id: str) -> dict[str, Any]:
        """Sync a single health intervention."""
        try:
            with self.db.get_session() as session:
                intervention = session.query(HealthIntervention).filter_by(
                    intervention_id=intervention_id
                ).first()
                
                if not intervention:
                    return {"success": False, "reason": "not_found"}
                
                data = {
                    "intervention_id": intervention.intervention_id,
                    "privacy_status": intervention.privacy_status,
                    "active": intervention.active,
                    "name": intervention.name,
                    "body_system": intervention.body_system,
                    "organs": intervention.organs,
                    "author": intervention.author,
                    "frequency": intervention.frequency,
                    "metric": intervention.metric,
                    "pete_attia_category": intervention.pete_attia_category,
                    "pa_subcategory": intervention.pa_subcategory,
                    "source_1": intervention.source_1,
                    "source_2": intervention.source_2,
                    "source_3": intervention.source_3,
                    "matt_notes": intervention.matt_notes,
                }
                
                result = self.upload_single("health_interventions", data)
                
                if result.get("success"):
                    intervention.synced_to_web = True
                    intervention.web_id = str(uuid4())
                    intervention.last_synced_at = datetime.utcnow()
                    session.commit()
                
                return result
                
        except Exception as e:
            logger.error(f"❌ Failed to sync intervention: {e}")
            return {"success": False, "reason": "error", "error": str(e)}

    def sync_health_metric(self, metric_id: str) -> dict[str, Any]:
        """Sync a single health metric."""
        try:
            with self.db.get_session() as session:
                metric = session.query(HealthMetric).filter_by(
                    metric_id=metric_id
                ).first()
                
                if not metric:
                    return {"success": False, "reason": "not_found"}
                
                data = {
                    "metric_id": metric.metric_id,
                    "privacy_status": metric.privacy_status,
                    "active": metric.active,
                    "name": metric.name,
                    "body_system": metric.body_system,
                    "organs": metric.organs,
                    "author": metric.author,
                    "frequency": metric.frequency,
                    "metric": metric.metric,
                    "pete_attia_category": metric.pete_attia_category,
                    "pa_subcategory": metric.pa_subcategory,
                    "source_1": metric.source_1,
                    "source_2": metric.source_2,
                }
                
                result = self.upload_single("health_metrics", data)
                
                if result.get("success"):
                    metric.synced_to_web = True
                    metric.web_id = str(uuid4())
                    metric.last_synced_at = datetime.utcnow()
                    session.commit()
                
                return result
                
        except Exception as e:
            logger.error(f"❌ Failed to sync metric: {e}")
            return {"success": False, "reason": "error", "error": str(e)}

    def sync_health_issue(self, issue_id: str) -> dict[str, Any]:
        """Sync a single health issue."""
        try:
            with self.db.get_session() as session:
                issue = session.query(HealthIssue).filter_by(
                    issue_id=issue_id
                ).first()
                
                if not issue:
                    return {"success": False, "reason": "not_found"}
                
                data = {
                    "issue_id": issue.issue_id,
                    "privacy_status": issue.privacy_status,
                    "active": issue.active,
                    "name": issue.name,
                    "body_system": issue.body_system,
                    "organs": issue.organs,
                    "author": issue.author,
                    "frequency": issue.frequency,
                    "metric": issue.metric,
                    "pete_attia_category": issue.pete_attia_category,
                    "pa_subcategory": issue.pa_subcategory,
                    "source_1": issue.source_1,
                    "source_2": issue.source_2,
                    "matt_notes": issue.matt_notes,
                }
                
                result = self.upload_single("health_issues", data)
                
                if result.get("success"):
                    issue.synced_to_web = True
                    issue.web_id = str(uuid4())
                    issue.last_synced_at = datetime.utcnow()
                    session.commit()
                
                return result
                
        except Exception as e:
            logger.error(f"❌ Failed to sync issue: {e}")
            return {"success": False, "reason": "error", "error": str(e)}

    # ========================================
    # FEEDBACK SYNC (Dynamic Learning System)
    # ========================================

    def sync_feedback_from_web(self, api_url: str = None) -> dict[str, Any]:
        """
        Fetch feedback from GetReceipts.org and push to pending queue.
        
        This is the async-safe method that does NOT calculate embeddings.
        Raw JSON is pushed to pending_feedback queue for background processing.
        
        Args:
            api_url: Optional API URL override for testing
            
        Returns:
            Dict with sync result
        """
        if not self.is_sync_enabled():
            logger.info("Sync disabled - feedback not synced")
            return {"success": False, "reason": "sync_disabled"}
        
        try:
            # Fetch feedback from web API
            feedback_items = self._fetch_feedback_from_web(api_url)
            
            if not feedback_items:
                logger.info("No new feedback to sync")
                return {"success": True, "synced": 0}
            
            # Push to pending queue (async-safe)
            queued = self._queue_feedback_items(feedback_items)
            
            # Update sync metadata
            self._update_feedback_sync_metadata(queued)
            
            logger.info(f"✅ Queued {queued} feedback items for processing")
            return {"success": True, "synced": queued}
            
        except Exception as e:
            logger.error(f"❌ Failed to sync feedback: {e}")
            return {"success": False, "reason": "error", "error": str(e)}
    
    def _fetch_feedback_from_web(self, api_url: str = None) -> list[dict]:
        """
        Fetch feedback items from GetReceipts.org API.
        
        Returns list of feedback items (raw JSON).
        """
        import requests
        
        # Get device credentials
        device_id, device_key = self.device_auth.get_credentials()
        if not device_id or not device_key:
            raise ValueError("Device not authenticated")
        
        # Build API URL
        if api_url is None:
            base_url = "https://getreceipts.org" if self.use_production else "http://localhost:3000"
            api_url = f"{base_url}/api/feedback/sync"
        
        # Get last sync timestamp
        last_sync = self._get_last_feedback_sync()
        
        # Make request
        headers = {
            "X-Device-ID": device_id,
            "X-Device-Key": device_key,
            "Content-Type": "application/json"
        }
        
        params = {}
        if last_sync:
            params["since"] = last_sync
        
        response = requests.get(api_url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        feedback_items = data.get("feedback", [])
        
        # Mark all fetched items as shared (from admin, replicated to all users)
        for item in feedback_items:
            item["is_shared"] = True
        
        return feedback_items
    
    def _queue_feedback_items(self, items: list[dict]) -> int:
        """
        Push feedback items to the pending_feedback queue.
        
        Does NOT calculate embeddings - that's done by the background worker.
        """
        if not items:
            return 0
        
        # Ensure database exists
        self.feedback_db_path.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(str(self.feedback_db_path))
        cursor = conn.cursor()
        
        # Ensure table exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pending_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_json TEXT NOT NULL,
                source TEXT DEFAULT 'web',
                received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0
            )
        """)
        
        queued = 0
        for item in items:
            try:
                # Check if already queued (by web_feedback_id if present)
                web_id = item.get("web_feedback_id")
                if web_id:
                    cursor.execute("""
                        SELECT id FROM pending_feedback 
                        WHERE raw_json LIKE ?
                    """, (f'%"web_feedback_id": "{web_id}"%',))
                    if cursor.fetchone():
                        continue  # Already queued
                
                # Insert into queue
                cursor.execute("""
                    INSERT INTO pending_feedback (raw_json, source)
                    VALUES (?, 'web')
                """, (json.dumps(item),))
                queued += 1
                
            except Exception as e:
                logger.warning(f"Failed to queue feedback item: {e}")
        
        conn.commit()
        conn.close()
        
        return queued
    
    def _get_last_feedback_sync(self) -> Optional[str]:
        """Get the timestamp of the last feedback sync."""
        if not self.feedback_db_path.exists():
            return None
        
        try:
            conn = sqlite3.connect(str(self.feedback_db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT last_sync_at FROM feedback_sync_metadata WHERE id = 1
            """)
            row = cursor.fetchone()
            conn.close()
            
            return row[0] if row else None
            
        except Exception:
            return None
    
    def _update_feedback_sync_metadata(self, count: int):
        """Update the feedback sync metadata."""
        conn = sqlite3.connect(str(self.feedback_db_path))
        cursor = conn.cursor()
        
        # Ensure table exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feedback_sync_metadata (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                last_sync_at TIMESTAMP,
                last_sync_count INTEGER DEFAULT 0,
                total_synced INTEGER DEFAULT 0,
                last_error TEXT
            )
        """)
        
        # Upsert metadata
        cursor.execute("""
            INSERT INTO feedback_sync_metadata (id, last_sync_at, last_sync_count, total_synced)
            VALUES (1, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                last_sync_at = excluded.last_sync_at,
                last_sync_count = excluded.last_sync_count,
                total_synced = total_synced + excluded.last_sync_count
        """, (datetime.utcnow().isoformat(), count, count))
        
        conn.commit()
        conn.close()


# Singleton instance
_entity_sync_service = None


def get_entity_sync_service(use_production: bool = True) -> EntitySyncService:
    """Get the global entity sync service instance."""
    global _entity_sync_service
    if _entity_sync_service is None:
        _entity_sync_service = EntitySyncService(use_production=use_production)
    return _entity_sync_service

