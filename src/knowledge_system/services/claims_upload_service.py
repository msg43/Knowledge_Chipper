"""
Claims Upload Service for Cloud Uploads functionality.

Reads claims from SQLite database and prepares them for upload to Supabase.
Handles tracking of upload status and associated data collection.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

from ..logger import get_logger
from ..database import DatabaseService
from ..config import get_settings

logger = get_logger(__name__)


class ClaimUploadData:
    """Data structure for a claim with its associated data."""
    
    def __init__(self, claim_data: Dict[str, Any]):
        self.episode_id = claim_data['episode_id']
        self.claim_id = claim_data['claim_id']
        self.canonical = claim_data['canonical']
        self.claim_type = claim_data['claim_type']
        self.tier = claim_data['tier']
        self.first_mention_ts = claim_data['first_mention_ts']
        self.scores_json = claim_data['scores_json']
        self.inserted_at = claim_data['inserted_at']
        self.last_uploaded_at = claim_data.get('last_uploaded_at')
        self.upload_status = claim_data.get('upload_status', 'pending')
        
        # Associated data (populated by collector)
        self.episode_data: Optional[Dict[str, Any]] = None
        self.evidence_spans: List[Dict[str, Any]] = []
        self.people: List[Dict[str, Any]] = []
        self.concepts: List[Dict[str, Any]] = []
        self.jargon: List[Dict[str, Any]] = []
        self.relations: List[Dict[str, Any]] = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for upload."""
        return {
            'claim': {
                'episode_id': self.episode_id,
                'claim_id': self.claim_id,
                'canonical': self.canonical,
                'claim_type': self.claim_type,
                'tier': self.tier,
                'first_mention_ts': self.first_mention_ts,
                'scores_json': self.scores_json,
                'inserted_at': self.inserted_at,
                'last_uploaded_at': self.last_uploaded_at,
                'upload_status': self.upload_status
            },
            'episode': self.episode_data,
            'evidence_spans': self.evidence_spans,
            'people': self.people,
            'concepts': self.concepts,
            'jargon': self.jargon,
            'relations': self.relations
        }


class ClaimsUploadService:
    """Service for reading claims from SQLite and preparing them for upload."""
    
    def __init__(self, db_path: str | Path | None = None):
        """Initialize the service with optional database path."""
        self.db_path = Path(db_path) if db_path else self._get_default_db_path()
        self.db_service = DatabaseService(f"sqlite:///{self.db_path}")
        
    def _get_default_db_path(self) -> Path:
        """Get the default knowledge_system.db path."""
        # Try to get from settings first
        try:
            settings = get_settings()
            if hasattr(settings, 'database') and hasattr(settings.database, 'url'):
                db_url = settings.database.url
                if db_url.startswith('sqlite:///'):
                    return Path(db_url[10:])
        except Exception:
            pass
        
        # Default fallback
        return Path.cwd() / "knowledge_system.db"
    
    def is_database_valid(self) -> Tuple[bool, str]:
        """Check if the database file is valid and has required tables."""
        if not self.db_path.exists():
            return False, f"Database file not found: {self.db_path}"
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check for required tables
                required_tables = ['claims', 'episodes', 'evidence_spans', 'people', 'concepts', 'jargon', 'relations']
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                existing_tables = {row[0] for row in cursor.fetchall()}
                
                missing_tables = set(required_tables) - existing_tables
                if missing_tables:
                    return False, f"Missing required tables: {', '.join(missing_tables)}"
                
                # Check if upload tracking columns exist, add them if not
                cursor.execute("PRAGMA table_info(claims)")
                columns = {row[1] for row in cursor.fetchall()}
                
                if 'last_uploaded_at' not in columns or 'upload_status' not in columns:
                    logger.info("Adding upload tracking columns to claims table")
                    self._add_upload_tracking_columns(conn)
                
                return True, "Database is valid"
                
        except Exception as e:
            return False, f"Database error: {str(e)}"
    
    def _add_upload_tracking_columns(self, conn: sqlite3.Connection) -> None:
        """Add upload tracking columns if they don't exist."""
        try:
            cursor = conn.cursor()
            cursor.execute("ALTER TABLE claims ADD COLUMN last_uploaded_at TEXT DEFAULT NULL")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            cursor.execute("ALTER TABLE claims ADD COLUMN upload_status TEXT DEFAULT 'pending'")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        conn.commit()
    
    def get_unuploaded_claims(self) -> List[ClaimUploadData]:
        """Get all claims that haven't been uploaded or have been modified since last upload."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Get claims that are pending upload or have never been uploaded
                query = """
                SELECT c.*, e.title as episode_title, e.video_id
                FROM claims c
                LEFT JOIN episodes e ON c.episode_id = e.episode_id
                WHERE (c.upload_status IS NULL OR c.upload_status = 'pending' OR c.upload_status = 'failed')
                   OR c.last_uploaded_at IS NULL
                ORDER BY c.inserted_at DESC
                """
                
                cursor.execute(query)
                rows = cursor.fetchall()
                
                claims = []
                for row in rows:
                    claim_data = dict(row)
                    claim = ClaimUploadData(claim_data)
                    
                    # Collect associated data
                    self._collect_associated_data(conn, claim)
                    claims.append(claim)
                
                logger.info(f"Found {len(claims)} unuploaded claims")
                return claims
                
        except Exception as e:
            logger.error(f"Error reading unuploaded claims: {e}")
            return []
    
    def _collect_associated_data(self, conn: sqlite3.Connection, claim: ClaimUploadData) -> None:
        """Collect all data associated with a claim."""
        cursor = conn.cursor()
        conn.row_factory = sqlite3.Row
        
        try:
            # Get episode data
            cursor.execute(
                "SELECT * FROM episodes WHERE episode_id = ?",
                (claim.episode_id,)
            )
            episode_row = cursor.fetchone()
            if episode_row:
                claim.episode_data = dict(episode_row)
            
            # Get evidence spans
            cursor.execute(
                "SELECT * FROM evidence_spans WHERE episode_id = ? AND claim_id = ? ORDER BY seq",
                (claim.episode_id, claim.claim_id)
            )
            claim.evidence_spans = [dict(row) for row in cursor.fetchall()]
            
            # Get people mentioned in this episode
            cursor.execute(
                "SELECT * FROM people WHERE episode_id = ?",
                (claim.episode_id,)
            )
            claim.people = [dict(row) for row in cursor.fetchall()]
            
            # Get concepts from this episode
            cursor.execute(
                "SELECT * FROM concepts WHERE episode_id = ?",
                (claim.episode_id,)
            )
            claim.concepts = [dict(row) for row in cursor.fetchall()]
            
            # Get jargon from this episode
            cursor.execute(
                "SELECT * FROM jargon WHERE episode_id = ?",
                (claim.episode_id,)
            )
            claim.jargon = [dict(row) for row in cursor.fetchall()]
            
            # Get relations involving this claim
            cursor.execute(
                """SELECT * FROM relations 
                   WHERE episode_id = ? AND (source_claim_id = ? OR target_claim_id = ?)""",
                (claim.episode_id, claim.claim_id, claim.claim_id)
            )
            claim.relations = [dict(row) for row in cursor.fetchall()]
            
        except Exception as e:
            logger.error(f"Error collecting associated data for claim {claim.claim_id}: {e}")
    
    def mark_claims_uploaded(self, claim_ids: List[Tuple[str, str]]) -> None:
        """Mark claims as uploaded with current timestamp."""
        if not claim_ids:
            return
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                timestamp = datetime.now().isoformat()
                
                for episode_id, claim_id in claim_ids:
                    cursor.execute(
                        """UPDATE claims 
                           SET upload_status = 'uploaded', last_uploaded_at = ? 
                           WHERE episode_id = ? AND claim_id = ?""",
                        (timestamp, episode_id, claim_id)
                    )
                
                conn.commit()
                logger.info(f"Marked {len(claim_ids)} claims as uploaded")
                
        except Exception as e:
            logger.error(f"Error marking claims as uploaded: {e}")
    
    def mark_claims_failed(self, claim_ids: List[Tuple[str, str]]) -> None:
        """Mark claims as failed upload."""
        if not claim_ids:
            return
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                for episode_id, claim_id in claim_ids:
                    cursor.execute(
                        """UPDATE claims 
                           SET upload_status = 'failed' 
                           WHERE episode_id = ? AND claim_id = ?""",
                        (episode_id, claim_id)
                    )
                
                conn.commit()
                logger.info(f"Marked {len(claim_ids)} claims as failed")
                
        except Exception as e:
            logger.error(f"Error marking claims as failed: {e}")
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get statistics about the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                stats = {}
                
                # Count total claims
                cursor.execute("SELECT COUNT(*) FROM claims")
                stats['total_claims'] = cursor.fetchone()[0]
                
                # Count unuploaded claims
                cursor.execute(
                    """SELECT COUNT(*) FROM claims 
                       WHERE upload_status IS NULL OR upload_status = 'pending' OR upload_status = 'failed'"""
                )
                stats['unuploaded_claims'] = cursor.fetchone()[0]
                
                # Count uploaded claims
                cursor.execute("SELECT COUNT(*) FROM claims WHERE upload_status = 'uploaded'")
                stats['uploaded_claims'] = cursor.fetchone()[0]
                
                # Count episodes
                cursor.execute("SELECT COUNT(*) FROM episodes")
                stats['total_episodes'] = cursor.fetchone()[0]
                
                return stats
                
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {}
