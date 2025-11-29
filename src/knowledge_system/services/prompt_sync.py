"""
Prompt Refinements Sync Service

Syncs approved prompt refinements from GetReceipts.org to local files.
These refinements are bad_example entries that get injected into extraction
prompts to prevent previously-identified classes of mistakes.

Architecture:
- Refinements are stored on GetReceipts.org (web is canonical)
- Desktop apps fetch and cache them locally in refinements/*.txt files
- At extraction time, these files are read and injected into prompts
- Files are overwritten on each sync (clean sync, no merge)

Usage:
    from knowledge_system.services.prompt_sync import PromptSyncService
    
    sync_service = PromptSyncService()
    sync_service.sync_refinements()  # Fetches from web and updates local files
    
    # Later, when building prompts:
    refinements = sync_service.get_refinements_for_entity_type('person')
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from ..logger import get_logger
from ..utils.macos_paths import get_application_support_dir
from .device_auth import get_device_auth

logger = get_logger(__name__)

# API endpoints
PRODUCTION_API = "https://getreceipts.org/api/prompt-refinements"
DEVELOPMENT_API = "http://localhost:3000/api/prompt-refinements"


class PromptSyncService:
    """
    Syncs and manages prompt refinements from GetReceipts.org.
    
    Refinements are stored locally in:
        ~/Library/Application Support/Knowledge Chipper/refinements/
            person_refinements.txt
            jargon_refinements.txt
            concept_refinements.txt
            sync_metadata.json
    """

    def __init__(self, use_production: bool = True) -> None:
        """
        Initialize the sync service.
        
        Args:
            use_production: Whether to sync from production API (default True)
        """
        self.api_url = PRODUCTION_API if use_production else DEVELOPMENT_API
        self.device_auth = get_device_auth()
        self.refinements_dir = get_application_support_dir() / "refinements"
        self.refinements_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"PromptSyncService initialized - refinements dir: {self.refinements_dir}")

    def get_refinements_file(self, entity_type: str) -> Path:
        """Get the path to the refinements file for an entity type."""
        return self.refinements_dir / f"{entity_type}_refinements.txt"

    def get_metadata_file(self) -> Path:
        """Get the path to the sync metadata file."""
        return self.refinements_dir / "sync_metadata.json"

    def sync_refinements(self, force: bool = False) -> dict[str, Any]:
        """
        Sync refinements from GetReceipts.org.
        
        This fetches all active refinements and overwrites local files.
        Call this on app startup or when user requests a sync.
        
        Args:
            force: Force sync even if device is not enabled for uploads
            
        Returns:
            Dict with sync results (counts, timestamp, errors)
        """
        try:
            # Check if device is enabled (unless forced)
            if not force and not self.device_auth.is_enabled():
                logger.info("Device sync disabled - skipping refinement sync")
                return {"success": False, "reason": "sync_disabled"}

            # Get device credentials for auth
            credentials = self.device_auth.get_credentials()
            
            logger.info(f"🔄 Syncing refinements from {self.api_url}...")

            # Fetch refinements from API
            response = requests.get(
                self.api_url,
                headers={
                    "X-Device-ID": credentials["device_id"],
                    "X-Device-Key": credentials["device_key"],
                },
                timeout=30
            )

            if response.status_code == 401:
                logger.warning("Device authentication failed - refinements not synced")
                return {"success": False, "reason": "auth_failed"}

            if not response.ok:
                logger.error(f"Failed to fetch refinements: {response.status_code}")
                return {"success": False, "reason": f"http_{response.status_code}"}

            data = response.json()
            
            if not data.get("success"):
                logger.error(f"API error: {data.get('error')}")
                return {"success": False, "reason": "api_error", "error": data.get("error")}

            # Process refinements by entity type
            grouped = data.get("grouped", {})
            counts = {}
            
            for entity_type in ["person", "jargon", "concept"]:
                refinements = grouped.get(entity_type, [])
                count = self._write_refinements_file(entity_type, refinements)
                counts[entity_type] = count
                logger.info(f"  {entity_type}: {count} refinements")

            # Update sync metadata
            metadata = {
                "last_sync": datetime.utcnow().isoformat(),
                "api_version": data.get("version", 0),
                "counts": counts,
                "total": sum(counts.values()),
                "api_last_updated": data.get("last_updated")
            }
            self._write_metadata(metadata)

            logger.info(f"✅ Refinements synced: {sum(counts.values())} total")
            return {
                "success": True,
                "counts": counts,
                "total": sum(counts.values()),
                "last_sync": metadata["last_sync"]
            }

        except requests.RequestException as e:
            logger.error(f"Network error syncing refinements: {e}")
            return {"success": False, "reason": "network_error", "error": str(e)}
        except Exception as e:
            logger.error(f"Error syncing refinements: {e}")
            return {"success": False, "reason": "unknown", "error": str(e)}

    def _write_refinements_file(self, entity_type: str, refinements: list[dict]) -> int:
        """
        Write refinements to a file for an entity type.
        
        The file format is designed to be easily appended to prompts:
        - XML bad_example entries, one per refinement
        - Comments indicating the source pattern
        
        Args:
            entity_type: The entity type (person, jargon, concept)
            refinements: List of refinement objects from API
            
        Returns:
            Number of refinements written
        """
        file_path = self.get_refinements_file(entity_type)
        
        lines = [
            f"<!-- Synced refinements for {entity_type} extraction -->",
            f"<!-- Last sync: {datetime.utcnow().isoformat()} -->",
            f"<!-- Source: GetReceipts.org prompt refinements -->",
            "",
        ]
        
        for refinement in refinements:
            if not refinement.get("active", True):
                continue
                
            pattern_name = refinement.get("pattern_name", "Unnamed pattern")
            example_xml = refinement.get("example_xml", "")
            
            if example_xml:
                lines.append(f"  <!-- Pattern: {pattern_name} -->")
                lines.append(f"  {example_xml}")
                lines.append("")

        content = "\n".join(lines)
        
        # Write file (overwrite completely - clean sync)
        file_path.write_text(content, encoding="utf-8")
        
        return len([r for r in refinements if r.get("active", True)])

    def _write_metadata(self, metadata: dict) -> None:
        """Write sync metadata to JSON file."""
        metadata_path = self.get_metadata_file()
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    def get_sync_metadata(self) -> dict | None:
        """
        Get the last sync metadata.
        
        Returns:
            Metadata dict or None if never synced
        """
        metadata_path = self.get_metadata_file()
        if not metadata_path.exists():
            return None
        
        try:
            return json.loads(metadata_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def get_refinements_for_entity_type(self, entity_type: str) -> str:
        """
        Get the refinements content for a specific entity type.
        
        This is the content that should be injected into prompts.
        
        Args:
            entity_type: The entity type (person, jargon, concept)
            
        Returns:
            String containing the refinements XML, or empty string if none
        """
        file_path = self.get_refinements_file(entity_type)
        
        if not file_path.exists():
            return ""
        
        try:
            content = file_path.read_text(encoding="utf-8")
            # Strip the header comments but keep the examples
            lines = content.split("\n")
            # Skip comment lines at the start
            example_lines = []
            in_examples = False
            for line in lines:
                if line.strip().startswith("<!-- Pattern:"):
                    in_examples = True
                if in_examples:
                    example_lines.append(line)
            return "\n".join(example_lines)
        except Exception as e:
            logger.error(f"Error reading refinements for {entity_type}: {e}")
            return ""

    def get_all_refinements(self) -> dict[str, str]:
        """
        Get refinements for all entity types.
        
        Returns:
            Dict mapping entity_type to refinements content
        """
        return {
            "person": self.get_refinements_for_entity_type("person"),
            "jargon": self.get_refinements_for_entity_type("jargon"),
            "concept": self.get_refinements_for_entity_type("concept"),
        }

    def has_refinements(self) -> bool:
        """Check if any refinements are available locally."""
        metadata = self.get_sync_metadata()
        return metadata is not None and metadata.get("total", 0) > 0


# Module-level instance for convenience
_prompt_sync_service: PromptSyncService | None = None


def get_prompt_sync_service(use_production: bool = True) -> PromptSyncService:
    """
    Get the shared PromptSyncService instance.
    
    Args:
        use_production: Whether to use production API
        
    Returns:
        PromptSyncService instance
    """
    global _prompt_sync_service
    if _prompt_sync_service is None:
        _prompt_sync_service = PromptSyncService(use_production=use_production)
    return _prompt_sync_service


def sync_refinements_on_startup() -> None:
    """
    Convenience function to sync refinements on app startup.
    
    Call this from the main application initialization.
    """
    try:
        service = get_prompt_sync_service()
        result = service.sync_refinements()
        if result.get("success"):
            logger.info(f"Startup refinement sync: {result.get('total', 0)} refinements")
        else:
            logger.debug(f"Startup refinement sync skipped: {result.get('reason')}")
    except Exception as e:
        logger.debug(f"Startup refinement sync error (non-fatal): {e}")
