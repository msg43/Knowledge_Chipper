"""Entity caching system for reusing people and concept extractions across documents."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class CachedEntity:
    """Cached entity with metadata."""

    name: str
    description: str
    entity_type: str  # 'person' or 'concept'
    confidence: float
    first_seen: datetime
    last_seen: datetime
    document_count: int
    aliases: set[str]  # Alternative names/spellings


class EntityCache:
    """Cache for storing and reusing entity extractions across documents.

    This cache helps improve performance by:
    1. Avoiding re-extraction of known entities
    2. Providing consistent entity resolution across documents
    3. Building a knowledge base of recognized entities
    """

    def __init__(
        self,
        cache_file: Path | None = None,
        similarity_threshold: float = 0.85,
        ttl_days: int = 30,
    ):
        """Initialize entity cache.

        Args:
            cache_file: Path to cache file (defaults to ~/.cache/knowledge_chipper/entities.json)
            similarity_threshold: Threshold for entity matching
            ttl_days: Time-to-live for cached entities in days
        """
        if cache_file is None:
            cache_dir = Path.home() / ".cache" / "knowledge_chipper"
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file = cache_dir / "entities.json"

        self.cache_file = Path(cache_file)
        self.similarity_threshold = similarity_threshold
        self.ttl_days = ttl_days

        # In-memory cache
        self._entities: dict[str, CachedEntity] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        """Load entities from cache file."""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, encoding="utf-8") as f:
                    data = json.load(f)

                for entity_data in data.get("entities", []):
                    entity = CachedEntity(
                        name=entity_data["name"],
                        description=entity_data["description"],
                        entity_type=entity_data["entity_type"],
                        confidence=entity_data["confidence"],
                        first_seen=datetime.fromisoformat(entity_data["first_seen"]),
                        last_seen=datetime.fromisoformat(entity_data["last_seen"]),
                        document_count=entity_data["document_count"],
                        aliases=set(entity_data.get("aliases", [])),
                    )
                    self._entities[entity.name.lower()] = entity

                logger.info(f"Loaded {len(self._entities)} cached entities")

        except Exception as e:
            logger.warning(f"Failed to load entity cache: {e}")
            self._entities = {}

    def _save_cache(self) -> None:
        """Save entities to cache file."""
        try:
            # Clean up expired entities first
            self._cleanup_expired()

            data = {
                "last_updated": datetime.now().isoformat(),
                "entities": [
                    {
                        "name": entity.name,
                        "description": entity.description,
                        "entity_type": entity.entity_type,
                        "confidence": entity.confidence,
                        "first_seen": entity.first_seen.isoformat(),
                        "last_seen": entity.last_seen.isoformat(),
                        "document_count": entity.document_count,
                        "aliases": list(entity.aliases),
                    }
                    for entity in self._entities.values()
                ],
            }

            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.debug(f"Saved {len(self._entities)} entities to cache")

        except Exception as e:
            logger.error(f"Failed to save entity cache: {e}")

    def _cleanup_expired(self) -> None:
        """Remove expired entities from cache."""
        cutoff_date = datetime.now() - timedelta(days=self.ttl_days)
        expired_keys = [
            key
            for key, entity in self._entities.items()
            if entity.last_seen < cutoff_date
        ]

        for key in expired_keys:
            del self._entities[key]

        if expired_keys:
            logger.info(f"Removed {len(expired_keys)} expired entities from cache")

    def find_matching_entity(self, name: str, entity_type: str) -> CachedEntity | None:
        """Find a matching cached entity by name and type.

        Args:
            name: Entity name to search for
            entity_type: Type of entity ('person' or 'concept')

        Returns:
            Matching cached entity or None
        """
        name_lower = name.lower().strip()

        # Direct match
        if name_lower in self._entities:
            entity = self._entities[name_lower]
            if entity.entity_type == entity_type:
                return entity

        # Check aliases
        for entity in self._entities.values():
            if entity.entity_type == entity_type and name_lower in entity.aliases:
                return entity

        # Fuzzy matching for common variations
        for entity in self._entities.values():
            if entity.entity_type == entity_type:
                if self._is_similar_name(name_lower, entity.name.lower()):
                    return entity

        return None

    def _is_similar_name(self, name1: str, name2: str) -> bool:
        """Check if two names are similar enough to be considered the same entity."""
        # Simple similarity checks
        if name1 == name2:
            return True

        # Check if one is contained in the other (for "Dr. John Smith" vs "John Smith")
        if name1 in name2 or name2 in name1:
            return True

        # Check for common title variations
        titles = ["dr.", "prof.", "mr.", "ms.", "mrs."]
        name1_clean = name1
        name2_clean = name2

        for title in titles:
            name1_clean = name1_clean.replace(title, "").strip()
            name2_clean = name2_clean.replace(title, "").strip()

        return name1_clean == name2_clean

    def add_or_update_entity(
        self, name: str, description: str, entity_type: str, confidence: float = 1.0
    ) -> CachedEntity:
        """Add a new entity or update an existing one.

        Args:
            name: Entity name
            description: Entity description
            entity_type: Type ('person' or 'concept')
            confidence: Confidence score (0.0-1.0)

        Returns:
            The cached entity (new or updated)
        """
        name_clean = name.strip()
        name_lower = name_clean.lower()

        # Check if entity already exists
        existing = self.find_matching_entity(name_clean, entity_type)

        if existing:
            # Update existing entity
            existing.last_seen = datetime.now()
            existing.document_count += 1
            existing.aliases.add(name_lower)

            # Update description if new one is more detailed
            if len(description) > len(existing.description):
                existing.description = description

            # Update confidence (take higher value)
            existing.confidence = max(existing.confidence, confidence)

            return existing
        else:
            # Create new entity
            entity = CachedEntity(
                name=name_clean,
                description=description,
                entity_type=entity_type,
                confidence=confidence,
                first_seen=datetime.now(),
                last_seen=datetime.now(),
                document_count=1,
                aliases={name_lower},
            )

            self._entities[name_lower] = entity
            return entity

    def get_suggested_entities(self, text: str, entity_type: str) -> list[CachedEntity]:
        """Get entities that might be relevant for the given text.

        Args:
            text: Text to analyze
            entity_type: Type of entities to suggest

        Returns:
            List of potentially relevant cached entities
        """
        text_lower = text.lower()
        suggestions = []

        for entity in self._entities.values():
            if entity.entity_type == entity_type:
                # Check if entity name appears in text
                if entity.name.lower() in text_lower:
                    suggestions.append(entity)
                    continue

                # Check aliases
                for alias in entity.aliases:
                    if alias in text_lower:
                        suggestions.append(entity)
                        break

        # Sort by document count (more frequently seen entities first)
        suggestions.sort(key=lambda e: e.document_count, reverse=True)
        return suggestions[:10]  # Return top 10 suggestions

    def get_entity_stats(self) -> dict[str, int]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        people_count = sum(
            1 for e in self._entities.values() if e.entity_type == "person"
        )
        concepts_count = sum(
            1 for e in self._entities.values() if e.entity_type == "concept"
        )

        return {
            "total_entities": len(self._entities),
            "people": people_count,
            "concepts": concepts_count,
            "cache_size_mb": self.cache_file.stat().st_size / 1024 / 1024
            if self.cache_file.exists()
            else 0,
        }

    def save(self) -> None:
        """Save cache to disk."""
        self._save_cache()

    def clear(self) -> None:
        """Clear all cached entities."""
        self._entities.clear()
        if self.cache_file.exists():
            self.cache_file.unlink()
        logger.info("Entity cache cleared")


# Global cache instance
_entity_cache: EntityCache | None = None


def get_entity_cache() -> EntityCache:
    """Get the global entity cache instance."""
    global _entity_cache
    if _entity_cache is None:
        _entity_cache = EntityCache()
    return _entity_cache


def clear_entity_cache() -> None:
    """Clear the global entity cache."""
    global _entity_cache
    if _entity_cache:
        _entity_cache.clear()
    _entity_cache = None
