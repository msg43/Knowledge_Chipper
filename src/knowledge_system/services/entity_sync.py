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

from datetime import datetime
from typing import Any
from uuid import uuid4

from ..database.connection import DatabaseConnection
from ..database.models import HealthIntervention, HealthMetric, HealthIssue
from ..logger import get_logger
from .device_auth import get_device_auth

logger = get_logger(__name__)


class EntitySyncService:
    """
    Unified sync service for ALL entity types.
    
    Handles:
    - Extraction entities (claims, jargon, people, concepts) - batch
    - Predictions - individual
    - Health tracking (interventions, metrics, issues) - individual
    - Any future entity types
    """

    def __init__(self, use_production: bool = True):
        """
        Initialize the entity sync service.
        
        Args:
            use_production: Whether to use production API (default: True)
        """
        self.use_production = use_production
        self.device_auth = get_device_auth()
        self.db = DatabaseConnection()

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


# Singleton instance
_entity_sync_service = None


def get_entity_sync_service(use_production: bool = True) -> EntitySyncService:
    """Get the global entity sync service instance."""
    global _entity_sync_service
    if _entity_sync_service is None:
        _entity_sync_service = EntitySyncService(use_production=use_production)
    return _entity_sync_service

