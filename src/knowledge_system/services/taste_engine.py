"""
Taste Engine - Vector-based feedback storage and retrieval

Stores user Accept/Reject feedback as vector embeddings in ChromaDB.
Provides semantic similarity search for:
- Dynamic prompt injection (few-shot examples)
- Taste Filter (style validation)
- Positive Echo (quality boost)

Key features:
- Automatic backup on startup (keeps 5 rotating copies)
- Golden set loading for cold start
- Reason validation against feedback_config.yaml
"""

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Literal

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

from ..logger import get_logger

logger = get_logger(__name__)


@dataclass
class FeedbackExample:
    """A single feedback example from user review."""
    entity_type: str  # claim, person, jargon, concept
    entity_text: str
    verdict: Literal["accept", "reject"]
    reason_category: str  # Key from feedback_reasons.yaml
    user_notes: str = ""
    source_id: str = ""  # Episode/source reference
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    is_golden: bool = False  # True if from golden_feedback.json


@dataclass
class SimilarExample:
    """A similar example found via vector search."""
    text: str
    similarity: float
    metadata: dict


class TasteEngine:
    """
    Vector database for storing and querying user feedback.
    
    Uses ChromaDB for persistence and sentence-transformers for embeddings.
    """
    
    COLLECTION_NAME = "taste_feedback"
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # Fast, good quality, runs locally
    
    # Paths
    GOLDEN_SET_PATH = Path(__file__).parent.parent / "data" / "golden_feedback.json"
    VERSION_FILE_PATH = Path(__file__).parent.parent / "data" / ".golden_version"
    
    # Backup settings
    BACKUP_DIR_NAME = "taste_engine_backups"
    MAX_BACKUPS = 5
    
    def __init__(
        self, 
        persist_dir: Optional[Path] = None,
        auto_load_golden: bool = True,
        backup_count: int = 5
    ):
        """
        Initialize the TasteEngine.
        
        Args:
            persist_dir: Directory for ChromaDB storage. Defaults to Application Support.
            auto_load_golden: Whether to load golden set on cold start.
            backup_count: Number of backups to keep (default 5).
        """
        self.backup_count = backup_count
        
        # Default to Application Support for persistence across reinstalls
        if persist_dir is None:
            persist_dir = Path.home() / "Library" / "Application Support" / "KnowledgeChipper" / "taste_engine"
        
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        
        # Backup existing data before any modifications
        self._backup_on_startup()
        
        # Initialize ChromaDB with persistence
        self._client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"description": "User feedback for dynamic learning"}
        )
        
        # Initialize embedding model (lazy load)
        self._embedder: Optional[SentenceTransformer] = None
        
        # Load golden set if needed
        if auto_load_golden:
            self._check_and_load_golden_set()
        
        logger.info(f"TasteEngine initialized with {self._collection.count()} examples")
    
    @property
    def embedder(self) -> SentenceTransformer:
        """Lazy-load the embedding model."""
        if self._embedder is None:
            logger.info(f"Loading embedding model: {self.EMBEDDING_MODEL}")
            self._embedder = SentenceTransformer(self.EMBEDDING_MODEL)
        return self._embedder
    
    def _backup_on_startup(self):
        """
        Create timestamped backup of ChromaDB on every startup.
        Keeps last N backups (default 5), deletes older ones.
        """
        backup_dir = self.persist_dir.parent / self.BACKUP_DIR_NAME
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Only backup if there's data to backup
        if not self.persist_dir.exists() or not any(self.persist_dir.iterdir()):
            logger.debug("No existing ChromaDB to backup")
            return
        
        # Create timestamped backup
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_path = backup_dir / f"backup_{timestamp}"
        
        try:
            shutil.copytree(self.persist_dir, backup_path)
            logger.info(f"Created ChromaDB backup: {backup_path}")
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return
        
        # Rotate: keep only last N backups
        self._rotate_backups(backup_dir)
    
    def _rotate_backups(self, backup_dir: Path):
        """Delete old backups, keeping only the most recent N."""
        backups = sorted(
            backup_dir.glob("backup_*"), 
            key=lambda p: p.stat().st_mtime
        )
        
        if len(backups) > self.backup_count:
            for old_backup in backups[:-self.backup_count]:
                try:
                    shutil.rmtree(old_backup)
                    logger.info(f"Deleted old backup: {old_backup.name}")
                except Exception as e:
                    logger.warning(f"Failed to delete old backup {old_backup}: {e}")
    
    def _check_and_load_golden_set(self) -> int:
        """
        Check if golden set needs to be loaded/reloaded.
        
        Returns number of examples loaded (0 if skipped).
        """
        if not self.GOLDEN_SET_PATH.exists():
            logger.warning(f"Golden set not found at {self.GOLDEN_SET_PATH}")
            return 0
        
        try:
            with open(self.GOLDEN_SET_PATH, 'r') as f:
                golden_data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load golden set: {e}")
            return 0
        
        file_version = golden_data.get("schema_version", "0.0.0")
        loaded_version = self._get_loaded_golden_version()
        
        # Check if we need to load/reload
        if loaded_version == file_version and self._collection.count() > 0:
            logger.debug(f"Golden set v{file_version} already loaded")
            return 0
        
        # Delete old golden examples if version changed
        if loaded_version and loaded_version != file_version:
            logger.info(f"Golden set version changed: {loaded_version} -> {file_version}")
            self._delete_golden_examples()
        
        # Load new golden examples
        count = self._ingest_golden_set(golden_data)
        self._save_golden_version(file_version)
        
        return count
    
    def _get_loaded_golden_version(self) -> Optional[str]:
        """Get the version of the currently loaded golden set."""
        if not self.VERSION_FILE_PATH.exists():
            return None
        try:
            return self.VERSION_FILE_PATH.read_text().strip()
        except Exception:
            return None
    
    def _save_golden_version(self, version: str):
        """Save the version of the loaded golden set."""
        try:
            self.VERSION_FILE_PATH.write_text(version)
        except Exception as e:
            logger.warning(f"Failed to save golden version: {e}")
    
    def _delete_golden_examples(self):
        """Delete all golden examples from the collection."""
        try:
            # Query for golden examples
            results = self._collection.get(
                where={"is_golden": True}
            )
            if results["ids"]:
                self._collection.delete(ids=results["ids"])
                logger.info(f"Deleted {len(results['ids'])} old golden examples")
        except Exception as e:
            logger.warning(f"Failed to delete golden examples: {e}")
    
    def _ingest_golden_set(self, golden_data: dict) -> int:
        """Ingest golden examples into the collection."""
        examples = golden_data.get("examples", [])
        if not examples:
            return 0
        
        count = 0
        for ex in examples:
            try:
                feedback = FeedbackExample(
                    entity_type=ex["entity_type"],
                    entity_text=ex["entity_text"],
                    verdict=ex["verdict"],
                    reason_category=ex["reason_category"],
                    user_notes=ex.get("user_notes", ""),
                    source_id="golden_set",
                    is_golden=True
                )
                self.add_feedback(feedback, skip_validation=True)
                count += 1
            except Exception as e:
                logger.warning(f"Failed to ingest golden example: {e}")
        
        logger.info(f"Loaded {count} golden examples")
        return count
    
    def add_feedback(
        self, 
        feedback: FeedbackExample,
        skip_validation: bool = False
    ) -> str:
        """
        Add a feedback example to the vector store.
        
        Args:
            feedback: The feedback example to add.
            skip_validation: Skip reason validation (for golden set).
            
        Returns:
            The ID of the added example.
        """
        # Validate reason_category against config
        if not skip_validation:
            from .feedback_config import get_feedback_config
            
            config = get_feedback_config()
            
            if not config.validate_reason(
                feedback.entity_type, 
                feedback.verdict, 
                feedback.reason_category
            ):
                logger.warning(
                    f"Unknown reason_category '{feedback.reason_category}' "
                    f"for {feedback.entity_type}/{feedback.verdict}, storing as 'other'"
                )
                feedback.reason_category = "other"
        
        # Generate embedding
        embedding = self.embedder.encode(feedback.entity_text).tolist()
        
        # Generate unique ID
        doc_id = f"{feedback.entity_type}_{feedback.verdict}_{datetime.utcnow().timestamp()}"
        
        # Prepare metadata
        metadata = {
            "entity_type": feedback.entity_type,
            "verdict": feedback.verdict,
            "reason_category": feedback.reason_category,
            "user_notes": feedback.user_notes,
            "source_id": feedback.source_id,
            "created_at": feedback.created_at,
            "is_golden": feedback.is_golden
        }
        
        # Add to collection
        self._collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[feedback.entity_text],
            metadatas=[metadata]
        )
        
        logger.debug(f"Added feedback: {doc_id}")
        return doc_id
    
    def query_similar(
        self,
        text: str,
        entity_type: Optional[str] = None,
        verdict: Optional[Literal["accept", "reject"]] = None,
        n_results: int = 5
    ) -> list[SimilarExample]:
        """
        Query for similar examples.
        
        Args:
            text: The text to find similar examples for.
            entity_type: Filter by entity type (claim, person, etc.).
            verdict: Filter by verdict (accept/reject).
            n_results: Maximum number of results.
            
        Returns:
            List of similar examples with similarity scores.
        """
        # Build where clause using ChromaDB's $and syntax for multiple conditions
        where = None
        conditions = []
        if entity_type:
            conditions.append({"entity_type": entity_type})
        if verdict:
            conditions.append({"verdict": verdict})
        
        if len(conditions) == 1:
            where = conditions[0]
        elif len(conditions) > 1:
            where = {"$and": conditions}
        
        # Generate query embedding
        query_embedding = self.embedder.encode(text).tolist()
        
        # Query collection
        try:
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where if where else None,
                include=["documents", "metadatas", "distances"]
            )
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return []
        
        # Convert to SimilarExample objects
        examples = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                # ChromaDB returns L2 distance, convert to similarity
                # Similarity = 1 / (1 + distance) for normalized comparison
                distance = results["distances"][0][i] if results["distances"] else 0
                similarity = 1 / (1 + distance)
                
                examples.append(SimilarExample(
                    text=doc,
                    similarity=similarity,
                    metadata=results["metadatas"][0][i] if results["metadatas"] else {}
                ))
        
        return examples
    
    def get_stats(self) -> dict:
        """Get statistics about the feedback store."""
        total = self._collection.count()
        
        # Count by verdict
        try:
            accepts = len(self._collection.get(where={"verdict": "accept"})["ids"])
            rejects = len(self._collection.get(where={"verdict": "reject"})["ids"])
            golden = len(self._collection.get(where={"is_golden": True})["ids"])
        except Exception:
            accepts = rejects = golden = 0
        
        return {
            "total_examples": total,
            "accepts": accepts,
            "rejects": rejects,
            "golden_examples": golden,
            "user_examples": total - golden,
            "persist_dir": str(self.persist_dir),
            "embedding_model": self.EMBEDDING_MODEL
        }
    
    def clear(self):
        """Clear all examples (for testing)."""
        self._client.delete_collection(self.COLLECTION_NAME)
        self._collection = self._client.create_collection(
            name=self.COLLECTION_NAME,
            metadata={"description": "User feedback for dynamic learning"}
        )
        logger.info("Cleared all feedback examples")


# Module-level singleton
_taste_engine: Optional[TasteEngine] = None


def get_taste_engine() -> TasteEngine:
    """Get the global TasteEngine instance."""
    global _taste_engine
    if _taste_engine is None:
        _taste_engine = TasteEngine()
    return _taste_engine


def reset_taste_engine():
    """Reset the global TasteEngine instance (for testing)."""
    global _taste_engine
    _taste_engine = None
