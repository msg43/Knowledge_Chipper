"""
Auto-Sync Worker for Extract Tab.

Handles background syncing of accepted items to GetReceipts immediately
after user accepts them, following standard best practices (Gmail, Slack, etc.).
"""

import sys
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal

# Add project root to path for OAuth imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from ...logger import get_logger

logger = get_logger(__name__)


class AutoSyncWorker(QThread):
    """
    Background worker for auto-syncing accepted items to GetReceipts.
    
    Syncs items immediately after acceptance without blocking the UI.
    Handles failures gracefully by queuing items for retry.
    """
    
    sync_complete = pyqtSignal(int, list)  # (count, item_ids)
    sync_failed = pyqtSignal(str, list)     # (error_message, item_ids)
    
    def __init__(self, items: list[Any], parent=None):
        """
        Initialize auto-sync worker.
        
        Args:
            items: List of ReviewItem objects to sync
            parent: Parent QObject
        """
        super().__init__(parent)
        self.items = items
        self.should_stop = False
    
    def run(self):
        """Run the auto-sync operation."""
        if not self.items:
            logger.warning("AutoSyncWorker: No items to sync")
            self.sync_complete.emit(0, [])
            return
        
        try:
            # Import GetReceipts dependencies
            from knowledge_chipper_oauth.getreceipts_config import (
                get_config,
                set_production,
                validate_config,
            )
            from knowledge_chipper_oauth.getreceipts_uploader import GetReceiptsUploader
            
            # Check if device is linked
            from ...services.device_auth import get_device_auth
            device_auth = get_device_auth()
            
            if not device_auth.is_enabled():
                error_msg = "Device not linked - items queued for sync"
                logger.info(f"AutoSyncWorker: {error_msg}")
                item_ids = [item.item_id for item in self.items if item.item_id]
                self.sync_failed.emit(error_msg, item_ids)
                return
            
            # Configure for production
            set_production()
            config = get_config()
            
            if not validate_config(config):
                error_msg = "GetReceipts configuration incomplete"
                logger.warning(f"AutoSyncWorker: {error_msg}")
                item_ids = [item.item_id for item in self.items if item.item_id]
                self.sync_failed.emit(error_msg, item_ids)
                return
            
            # Initialize uploader
            api_base_url = f"{config['base_url']}/api/knowledge-chipper"
            uploader = GetReceiptsUploader(api_base_url=api_base_url)
            
            # Convert items to GetReceipts format
            session_data = self._convert_items_to_session_data()
            
            if not session_data or not any(session_data.values()):
                logger.warning("AutoSyncWorker: No data to upload")
                self.sync_complete.emit(0, [])
                return
            
            # Upload data
            logger.info(f"AutoSyncWorker: Uploading {len(self.items)} items...")
            upload_results = uploader.upload_session_data(session_data)
            
            # Count successes
            success_count = sum(
                len(data) if data else 0 for data in upload_results.values()
            )
            
            item_ids = [item.item_id for item in self.items if item.item_id]
            
            logger.info(f"AutoSyncWorker: Successfully synced {success_count} items")
            self.sync_complete.emit(success_count, item_ids)
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"AutoSyncWorker: Sync failed - {error_msg}")
            item_ids = [item.item_id for item in self.items if item.item_id]
            self.sync_failed.emit(error_msg, item_ids)
    
    def _convert_items_to_session_data(self) -> dict[str, Any]:
        """
        Convert ReviewItem objects to GetReceipts session data format.
        
        Returns:
            Dictionary with episodes, claims, jargon, people, concepts, etc.
        """
        session_data = {
            "episodes": [],
            "claims": [],
            "evidence_spans": [],
            "people": [],
            "jargon": [],
            "concepts": [],
            "relations": [],
        }
        
        seen_episodes = set()
        
        for item in self.items:
            raw_data = item.raw_data
            source_id = item.source_id
            
            # Add episode data if not already added
            if source_id and source_id not in seen_episodes:
                # TODO: Fetch episode data from database if needed
                # For now, create minimal episode entry
                episode_data = {
                    "source_id": source_id,
                    "title": item.source_title,
                }
                session_data["episodes"].append(episode_data)
                seen_episodes.add(source_id)
            
            # Add entity data based on type
            from ..components.review_queue import EntityType
            
            if item.entity_type == EntityType.CLAIM:
                claim_data = {
                    "claim_id": raw_data.get("claim_id", f"{source_id}_claim_{item.item_id}"),
                    "canonical": item.content,
                    "source_id": source_id,
                    "claim_type": raw_data.get("claim_type", "factual"),
                    "tier": item.tier,
                    "scores_json": raw_data.get("scores", {}),
                    "domain": raw_data.get("domain", "general"),
                    "speaker": raw_data.get("speaker", "Unknown"),  # NEW: Speaker field
                }
                session_data["claims"].append(claim_data)
                
                # Add evidence spans if present
                evidence = raw_data.get("evidence_spans", [])
                if evidence:
                    session_data["evidence_spans"].extend(evidence)
            
            elif item.entity_type == EntityType.JARGON:
                jargon_data = {
                    "term": item.content,
                    "definition": raw_data.get("definition", ""),
                    "domain": raw_data.get("domain", "general"),
                    "introduced_by": raw_data.get("introduced_by", "Unknown"),  # NEW: Speaker field
                }
                session_data["jargon"].append(jargon_data)
            
            elif item.entity_type == EntityType.PERSON:
                person_data = {
                    "name": item.content,
                    "description": raw_data.get("description", ""),
                    "entity_type": raw_data.get("entity_type", "person"),
                }
                session_data["people"].append(person_data)
            
            elif item.entity_type == EntityType.CONCEPT:
                concept_data = {
                    "name": item.content,
                    "definition": raw_data.get("definition", ""),
                    "description": raw_data.get("description", ""),
                    "advocated_by": raw_data.get("advocated_by", "Unknown"),  # NEW: Speaker field
                }
                session_data["concepts"].append(concept_data)
        
        return session_data
    
    def stop(self):
        """Request worker to stop."""
        self.should_stop = True

