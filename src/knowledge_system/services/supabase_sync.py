"""
Supabase Sync Service for Knowledge System.

Handles bidirectional synchronization between local SQLite database
and Supabase cloud storage with conflict resolution.
"""

import json
import logging
import hashlib
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum

# Lazy, optional import via runtime installer to avoid hard dependency
from ..utils.optional_deps import ensure_module, add_vendor_to_sys_path
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database import DatabaseService
from ..logger import get_logger
from ..config import get_settings

logger = get_logger(__name__)


class SyncStatus(Enum):
    """Sync status for records."""
    PENDING = "pending"
    SYNCED = "synced"
    CONFLICT = "conflict"
    ERROR = "error"
    DELETED = "deleted"


class ConflictResolution(Enum):
    """Conflict resolution strategies."""
    LOCAL_WINS = "local_wins"
    REMOTE_WINS = "remote_wins"
    MERGE = "merge"
    MANUAL = "manual"


@dataclass
class SyncConflict:
    """Represents a sync conflict."""
    table_name: str
    record_id: str
    local_data: Dict[str, Any]
    remote_data: Dict[str, Any]
    local_checksum: str
    remote_checksum: str
    local_updated: datetime
    remote_updated: datetime
    conflict_type: str  # "update-update", "delete-update", etc.


@dataclass
class SyncResult:
    """Result of a sync operation."""
    success: bool
    synced_count: int = 0
    conflict_count: int = 0
    error_count: int = 0
    conflicts: List[SyncConflict] = None
    errors: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.conflicts is None:
            self.conflicts = []
        if self.errors is None:
            self.errors = []


class SupabaseSyncService:
    """Service for syncing local database with Supabase."""
    
    # Tables to sync in order (respecting foreign key dependencies)
    SYNC_TABLES = [
        "media_sources",
        "transcripts",
        "summaries",
        "moc_extractions",
        "generated_files",
        "processing_jobs",
        "episodes",
        "claims",
        "claim_sources",
        "supporting_evidence",
        "people",
        "concepts",
        "jargon_terms",
        "relations",
        "claim_types",
        "quality_criteria",
        "claim_clusters"
    ]
    
    def __init__(self, 
                 supabase_url: Optional[str] = None,
                 supabase_key: Optional[str] = None):
        """Initialize the sync service."""
        self.db = DatabaseService()
        settings = get_settings()
        
        # Use provided credentials or get from settings
        self.supabase_url = supabase_url or settings.cloud.supabase_url
        self.supabase_key = supabase_key or settings.cloud.supabase_key
        
        if not self.supabase_url or not self.supabase_key:
            logger.info("Supabase credentials not configured; cloud sync disabled")
            self.client = None
        else:
            # Attempt to import/install supabase client on demand
            try:
                add_vendor_to_sys_path()
                supabase_mod = ensure_module("supabase", "supabase")
                create_client = getattr(supabase_mod, "create_client")
                self.client = create_client(self.supabase_url, self.supabase_key)
            except Exception as e:
                logger.warning(f"Supabase client unavailable: {e}")
                self.client = None
        
        self.sync_version = 1  # Increment when sync protocol changes
    
    def is_configured(self) -> bool:
        """Check if Supabase sync is properly configured."""
        return self.client is not None
    
    def calculate_checksum(self, data: Dict[str, Any]) -> str:
        """Calculate checksum for a record."""
        # Remove sync-related fields before calculating checksum
        clean_data = {k: v for k, v in data.items() 
                     if k not in ["sync_status", "last_synced", "sync_version", "sync_checksum"]}
        
        # Sort keys for consistent hashing
        data_str = json.dumps(clean_data, sort_keys=True, default=str)
        return hashlib.sha256(data_str.encode()).hexdigest()
    
    def sync_all(self, 
                 conflict_resolution: ConflictResolution = ConflictResolution.MANUAL) -> SyncResult:
        """Sync all tables with Supabase."""
        if not self.is_configured():
            return SyncResult(success=False, errors=[{"error": "Supabase not configured"}])
        
        total_result = SyncResult(success=True)
        
        for table in self.SYNC_TABLES:
            logger.info(f"Syncing table: {table}")
            result = self.sync_table(table, conflict_resolution)
            
            # Aggregate results
            total_result.synced_count += result.synced_count
            total_result.conflict_count += result.conflict_count
            total_result.error_count += result.error_count
            total_result.conflicts.extend(result.conflicts)
            total_result.errors.extend(result.errors)
            
            if not result.success:
                total_result.success = False
                logger.error(f"Failed to sync table {table}")
        
        return total_result
    
    def sync_table(self,
                   table_name: str,
                   conflict_resolution: ConflictResolution = ConflictResolution.MANUAL) -> SyncResult:
        """Sync a specific table with Supabase."""
        if not self.is_configured():
            return SyncResult(success=False, errors=[{"error": "Supabase not configured"}])
        
        result = SyncResult(success=True)
        
        try:
            # Pull changes from Supabase
            pull_result = self._pull_table(table_name, conflict_resolution)
            result.synced_count += pull_result.synced_count
            result.conflicts.extend(pull_result.conflicts)
            
            # Push local changes to Supabase
            push_result = self._push_table(table_name, conflict_resolution)
            result.synced_count += push_result.synced_count
            result.conflicts.extend(push_result.conflicts)
            
            # Update sync status for successful syncs
            self._update_sync_status(table_name)
            
        except Exception as e:
            logger.error(f"Error syncing table {table_name}: {e}")
            result.success = False
            result.errors.append({
                "table": table_name,
                "error": str(e)
            })
        
        return result
    
    def _pull_table(self,
                    table_name: str,
                    conflict_resolution: ConflictResolution) -> SyncResult:
        """Pull changes from Supabase to local database."""
        result = SyncResult(success=True)
        
        try:
            # Get last sync timestamp
            last_sync = self._get_last_sync_time(table_name)
            
            # Query remote changes
            query = self.client.table(table_name).select("*")
            if last_sync:
                query = query.gt("updated_at", last_sync.isoformat())
            
            remote_records = query.execute().data
            
            with self.db.get_session() as session:
                for remote_record in remote_records:
                    # Get primary key field (assumes 'id' or '{table_singular}_id')
                    pk_field = self._get_primary_key_field(table_name)
                    record_id = remote_record.get(pk_field)
                    
                    if not record_id:
                        continue
                    
                    # Check if record exists locally
                    local_record = session.execute(
                        text(f"SELECT * FROM {table_name} WHERE {pk_field} = :id"),
                        {"id": record_id}
                    ).fetchone()
                    
                    if local_record:
                        # Check for conflicts
                        local_data = dict(local_record._mapping)
                        local_checksum = local_data.get("sync_checksum") or self.calculate_checksum(local_data)
                        remote_checksum = remote_record.get("sync_checksum") or self.calculate_checksum(remote_record)
                        
                        if local_checksum != remote_checksum:
                            # Conflict detected
                            conflict = SyncConflict(
                                table_name=table_name,
                                record_id=record_id,
                                local_data=local_data,
                                remote_data=remote_record,
                                local_checksum=local_checksum,
                                remote_checksum=remote_checksum,
                                local_updated=local_data.get("updated_at", datetime.now()),
                                remote_updated=datetime.fromisoformat(remote_record.get("updated_at")),
                                conflict_type="update-update"
                            )
                            
                            # Resolve conflict
                            if conflict_resolution == ConflictResolution.REMOTE_WINS:
                                self._update_local_record(session, table_name, record_id, remote_record)
                                result.synced_count += 1
                            elif conflict_resolution == ConflictResolution.LOCAL_WINS:
                                # Local wins - will be pushed later
                                pass
                            else:
                                result.conflicts.append(conflict)
                                result.conflict_count += 1
                    else:
                        # New record from remote
                        self._insert_local_record(session, table_name, remote_record)
                        result.synced_count += 1
                
                session.commit()
                
        except Exception as e:
            logger.error(f"Error pulling table {table_name}: {e}")
            result.success = False
            result.errors.append({"operation": "pull", "table": table_name, "error": str(e)})
        
        return result
    
    def _push_table(self,
                    table_name: str,
                    conflict_resolution: ConflictResolution) -> SyncResult:
        """Push local changes to Supabase."""
        result = SyncResult(success=True)
        
        try:
            with self.db.get_session() as session:
                # Get local records pending sync
                pending_records = session.execute(
                    text(f"""
                        SELECT * FROM {table_name} 
                        WHERE sync_status IN ('pending', 'error') 
                        OR sync_checksum IS NULL
                        LIMIT 100
                    """)
                ).fetchall()
                
                for record in pending_records:
                    record_data = dict(record._mapping)
                    pk_field = self._get_primary_key_field(table_name)
                    record_id = record_data.get(pk_field)
                    
                    # Calculate checksum
                    checksum = self.calculate_checksum(record_data)
                    record_data["sync_checksum"] = checksum
                    record_data["sync_version"] = self.sync_version
                    record_data["last_synced"] = datetime.now(timezone.utc).isoformat()
                    
                    # Prepare data for Supabase (remove SQLAlchemy internal fields)
                    clean_data = {k: v for k, v in record_data.items() 
                                 if not k.startswith("_")}
                    
                    # Convert datetime objects to ISO format
                    for key, value in clean_data.items():
                        if isinstance(value, datetime):
                            clean_data[key] = value.isoformat()
                    
                    try:
                        # Try upsert to Supabase
                        response = self.client.table(table_name).upsert(
                            clean_data,
                            on_conflict=pk_field
                        ).execute()
                        
                        # Update local sync status
                        session.execute(
                            text(f"""
                                UPDATE {table_name}
                                SET sync_status = 'synced',
                                    sync_checksum = :checksum,
                                    last_synced = CURRENT_TIMESTAMP
                                WHERE {pk_field} = :id
                            """),
                            {"checksum": checksum, "id": record_id}
                        )
                        
                        result.synced_count += 1
                        
                    except Exception as e:
                        logger.error(f"Error pushing record {record_id} in {table_name}: {e}")
                        
                        # Mark as error
                        session.execute(
                            text(f"""
                                UPDATE {table_name}
                                SET sync_status = 'error'
                                WHERE {pk_field} = :id
                            """),
                            {"id": record_id}
                        )
                        
                        result.error_count += 1
                        result.errors.append({
                            "operation": "push",
                            "table": table_name,
                            "record_id": record_id,
                            "error": str(e)
                        })
                
                session.commit()
                
        except Exception as e:
            logger.error(f"Error pushing table {table_name}: {e}")
            result.success = False
            result.errors.append({"operation": "push", "table": table_name, "error": str(e)})
        
        return result
    
    def _get_primary_key_field(self, table_name: str) -> str:
        """Get the primary key field name for a table."""
        # Special cases
        if table_name == "media_sources":
            return "media_id"
        elif table_name.endswith("s"):
            # Remove 's' and add '_id'
            return f"{table_name[:-1]}_id"
        else:
            return f"{table_name}_id"
    
    def _get_last_sync_time(self, table_name: str) -> Optional[datetime]:
        """Get the last successful sync time for a table."""
        with self.db.get_session() as session:
            result = session.execute(
                text(f"""
                    SELECT MAX(last_synced) as last_sync
                    FROM {table_name}
                    WHERE sync_status = 'synced'
                """)
            ).fetchone()
            
            if result and result.last_sync:
                return result.last_sync
        
        return None
    
    def _update_local_record(self, session: Session, table_name: str, 
                           record_id: str, data: Dict[str, Any]):
        """Update a local record with remote data."""
        pk_field = self._get_primary_key_field(table_name)
        
        # Build UPDATE statement
        set_clauses = []
        params = {"id": record_id}
        
        for key, value in data.items():
            if key != pk_field and not key.startswith("_"):
                set_clauses.append(f"{key} = :{key}")
                params[key] = value
        
        if set_clauses:
            query = f"""
                UPDATE {table_name}
                SET {', '.join(set_clauses)}
                WHERE {pk_field} = :id
            """
            session.execute(text(query), params)
    
    def _insert_local_record(self, session: Session, table_name: str, data: Dict[str, Any]):
        """Insert a new record into local database."""
        # Build INSERT statement
        columns = []
        values = []
        params = {}
        
        for key, value in data.items():
            if not key.startswith("_"):
                columns.append(key)
                values.append(f":{key}")
                params[key] = value
        
        query = f"""
            INSERT INTO {table_name} ({', '.join(columns)})
            VALUES ({', '.join(values)})
        """
        session.execute(text(query), params)
    
    def _update_sync_status(self, table_name: str):
        """Update sync status for successfully synced records."""
        with self.db.get_session() as session:
            session.execute(
                text(f"""
                    UPDATE {table_name}
                    SET sync_status = 'synced'
                    WHERE sync_status = 'pending'
                    AND sync_checksum IS NOT NULL
                """)
            )
            session.commit()
    
    def resolve_conflict(self,
                        conflict: SyncConflict,
                        resolution: ConflictResolution) -> bool:
        """Resolve a specific sync conflict."""
        try:
            with self.db.get_session() as session:
                if resolution == ConflictResolution.LOCAL_WINS:
                    # Push local version to remote
                    self._push_single_record(
                        conflict.table_name,
                        conflict.record_id,
                        conflict.local_data
                    )
                elif resolution == ConflictResolution.REMOTE_WINS:
                    # Update local with remote version
                    self._update_local_record(
                        session,
                        conflict.table_name,
                        conflict.record_id,
                        conflict.remote_data
                    )
                elif resolution == ConflictResolution.MERGE:
                    # Merge logic would go here
                    # For now, just log
                    logger.info(f"Merge resolution not implemented for {conflict.table_name}:{conflict.record_id}")
                    return False
                
                session.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error resolving conflict: {e}")
            return False
    
    def _push_single_record(self, table_name: str, record_id: str, data: Dict[str, Any]):
        """Push a single record to Supabase."""
        if not self.is_configured():
            return
        
        pk_field = self._get_primary_key_field(table_name)
        
        # Prepare data
        clean_data = {k: v for k, v in data.items() if not k.startswith("_")}
        
        # Convert datetime objects
        for key, value in clean_data.items():
            if isinstance(value, datetime):
                clean_data[key] = value.isoformat()
        
        # Push to Supabase
        self.client.table(table_name).upsert(
            clean_data,
            on_conflict=pk_field
        ).execute()
    
    def get_sync_status(self) -> Dict[str, Dict[str, int]]:
        """Get sync status summary for all tables."""
        status = {}
        
        with self.db.get_session() as session:
            for table in self.SYNC_TABLES:
                # Count records by sync status
                result = session.execute(
                    text(f"""
                        SELECT 
                            sync_status,
                            COUNT(*) as count
                        FROM {table}
                        GROUP BY sync_status
                    """)
                ).fetchall()
                
                table_status = {}
                for row in result:
                    status_value = row.sync_status or "unsynced"
                    table_status[status_value] = row.count
                
                # Get total count
                total_result = session.execute(
                    text(f"SELECT COUNT(*) as total FROM {table}")
                ).fetchone()
                
                table_status["total"] = total_result.total if total_result else 0
                status[table] = table_status
        
        return status
