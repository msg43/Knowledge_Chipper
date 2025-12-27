"""
Database service layer for Knowledge System.

Provides high-level CRUD operations, query builders, and transaction management
for the SQLite database with comprehensive video processing tracking.
"""

import os
import re
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import desc, func, or_, text
from sqlalchemy.orm import Session, sessionmaker

from ..logger import get_logger
from ..utils.file_io import overwrite_or_insert_summary_section
from .models import (
    BrightDataSession,
    Claim,
    ClaimRelation,
    ClaimTierValidation,
    Concept,
    EvidenceSpan,
    GeneratedFile,
    JargonTerm,
    MediaSource,
    MOCExtraction,
    Person,
    PlatformCategory,
    PlatformTag,
    ProcessingJob,
    QualityMetrics,
    Question,
    QuestionClaim,
    Segment,
    SourcePlatformCategory,
    SourcePlatformTag,
    Summary,
    Transcript,
    create_all_tables,
    create_database_engine,
)

logger = get_logger(__name__)


class DatabaseService:
    """High-level database service for Knowledge System operations.

    DATABASE ACCESS PATTERNS:
    ========================
    This service uses different patterns optimized for different use cases:

    1. ORM (SQLAlchemy Models):
       - Use for: Single-record CRUD, simple queries, typed operations
       - Examples: get_video_by_id(), create_video(), update_job_status()
       - Benefits: Type-safe, maintainable, automatic relationship handling
       - Overhead: ~10-20% slower than raw SQL for bulk operations

    2. Direct SQL (cursor.execute):
       - Use for: Bulk writes, complex joins, performance-critical paths
       - Examples: HCEStore operations (100s-1000s of records per job)
       - Benefits: Maximum performance, full control over SQL
       - Trade-off: Manual type handling, more verbose

    3. bulk_insert_json() (text() with parameter binding):
       - Use for: High-volume inserts (100+ records at once)
       - Examples: Batch data imports, bulk entity storage
       - Benefits: Fast, safe (parameterized), bypasses ORM overhead
       - When: Need speed but want parameter safety

    RULE OF THUMB:
    - Single record? Use ORM
    - 10-100 records? Use ORM with session.flush() batching
    - 100+ records? Use bulk_insert_json() or direct SQL
    - Complex analytics query? Use direct SQL

    See HCEStore for example of optimized bulk write pattern.
    """

    def __init__(self, database_url: str = "sqlite:///knowledge_system.db"):
        """Initialize database service with connection.

        Defaults to a per-user writable SQLite database location to avoid
        permission issues when launching from /Applications.
        """
        # Resolve default/writable database path for SQLite
        # Allow tests to override DB via environment variable without impacting prod
        try:
            import os

            test_db_url = os.environ.get("KNOWLEDGE_CHIPPER_TEST_DB_URL")
            test_db_path = os.environ.get("KNOWLEDGE_CHIPPER_TEST_DB")
            if test_db_url:
                database_url = test_db_url
            elif test_db_path:
                # Accept absolute or relative path; treat as sqlite file path
                database_url = f"sqlite:///{test_db_path}"
        except Exception:
            # Do not let env parsing affect normal startup
            pass

        resolved_url = database_url
        db_path: Path | None = None

        def _user_data_dir() -> Path:
            # Use the standard application support directory
            from ..utils.macos_paths import get_application_support_dir

            return get_application_support_dir()

        if database_url.startswith("sqlite:///"):
            raw_path_str = database_url[10:]  # after 'sqlite:///'
            # Special case: in-memory database
            if raw_path_str == ":memory:":
                resolved_url = database_url  # Keep as-is
                db_path = None
            else:
                raw_path = Path(raw_path_str)
                if not raw_path.is_absolute():
                    # Use per-user app data directory for relative defaults
                    db_path = _user_data_dir() / "knowledge_system.db"
                    db_path.parent.mkdir(parents=True, exist_ok=True)
                    resolved_url = f"sqlite:///{db_path}"
                else:
                    db_path = raw_path
                    db_path.parent.mkdir(parents=True, exist_ok=True)
        elif database_url.startswith("sqlite://"):
            raw_path = Path(database_url[9:])  # after 'sqlite://'
            if not raw_path.is_absolute():
                db_path = _user_data_dir() / "knowledge_system.db"
                db_path.parent.mkdir(parents=True, exist_ok=True)
                resolved_url = f"sqlite:///{db_path}"
            else:
                db_path = raw_path
                db_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            # Non-sqlite URLs: leave as-is
            db_path = None

        self.database_url = resolved_url
        logger.info(
            f"Resolved database location: url={self.database_url} path={db_path}"
        )
        self.engine = create_database_engine(self.database_url)
        self.Session = sessionmaker(bind=self.engine)

        # Extract database path for SQLite URLs
        if self.database_url.startswith("sqlite:///"):
            self.db_path = Path(self.database_url[10:])  # Remove 'sqlite:///' prefix
        elif self.database_url.startswith("sqlite://"):
            self.db_path = Path(self.database_url[9:])  # Remove 'sqlite://' prefix
        else:
            self.db_path = Path("knowledge_system.db")  # Default fallback

        # Create tables if they don't exist
        create_all_tables(self.engine)

        # Run System 2 migration if needed
        self._run_system2_migration()

        # Ensure unified HCE schema (tables, indexes, FTS) exists in main DB
        self._ensure_unified_hce_schema()

        # Apply incremental schema migrations
        self._apply_incremental_migrations()

        logger.info(f"Database service initialized with {self.database_url}")

    def get_session(self) -> Session:
        """Get a new database session."""
        return self.Session()

    def close(self) -> None:
        """Close the database connection and dispose of the engine.

        This should be called when the database service is no longer needed,
        typically in test teardown or application shutdown.
        """
        if hasattr(self, 'engine') and self.engine:
            self.engine.dispose()

    def _run_system2_migration(self):
        """Run System 2 migration if needed."""
        try:
            from .migrations.system2_migration import migrate_to_system2

            with self.get_session() as session:
                # Check if migration is needed by looking for new tables
                result = session.execute(
                    text(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='job'"
                    )
                )
                if not result.first():
                    logger.info("Running System 2 migration...")
                    migrate_to_system2(session)
                else:
                    # Ensure WAL mode is enabled even if tables exist
                    session.execute(text("PRAGMA journal_mode=WAL"))
                    session.commit()
        except Exception as e:
            logger.error(f"Failed to run System 2 migration: {e}")
            # Don't fail initialization if migration fails

    def _ensure_unified_hce_schema(self) -> None:
        """Apply the unified HCE schema SQL into the main SQLite DB if needed.

        This executes the idempotent SQL at
        `src/knowledge_system/database/migrations/unified_schema.sql` to create
        the HCE tables (claims, evidence_spans, relations, people, concepts,
        jargon, structured_categories), FTS virtual tables, views, and indexes.
        """
        try:
            # Only applicable for SQLite
            if not (
                self.database_url.startswith("sqlite:///")
                or self.database_url.startswith("sqlite://")
            ):
                return

            schema_path = Path(__file__).parent / "migrations" / "unified_schema.sql"
            if not schema_path.exists():
                logger.warning(
                    f"Unified HCE schema file not found at {schema_path}; skipping"
                )
                return

            sql_text = schema_path.read_text()
            with self.engine.connect() as conn:
                # Execute as a single script; safe due to IF NOT EXISTS guards
                conn.connection.executescript(sql_text)
                conn.commit()
            logger.info("Unified HCE schema ensured in main database")
        except Exception as e:
            logger.error(f"Failed to ensure unified HCE schema: {e}")

    def _apply_incremental_migrations(self) -> None:
        """Apply incremental schema migrations that aren't part of unified_schema.sql.
        
        This applies migrations for schema changes like adding new columns to existing
        tables. Each migration is idempotent and can be safely re-run.
        """
        try:
            # Only applicable for SQLite
            if not (
                self.database_url.startswith("sqlite:///")
                or self.database_url.startswith("sqlite://")
            ):
                return

            migrations_dir = Path(__file__).parent / "migrations"
            
            # List of incremental migrations to apply (in order)
            # These are migrations that add columns or indexes to existing tables
            incremental_migrations = [
                "2025_11_16_add_user_notes_to_claims.sql",
                "add_pdf_transcript_support.sql",  # Add quality tracking and PDF support
                "add_transcript_source.sql",  # Add transcript_source column
                # Note: verification_status fix requires table rebuild, apply manually if needed
                # Add new migrations here as needed
            ]
            
            for migration_file in incremental_migrations:
                migration_path = migrations_dir / migration_file
                if not migration_path.exists():
                    logger.warning(f"Migration file not found: {migration_path}")
                    continue
                
                try:
                    sql_text = migration_path.read_text()
                    with self.engine.connect() as conn:
                        # Execute the migration (should be idempotent with IF NOT EXISTS, etc.)
                        conn.connection.executescript(sql_text)
                        conn.commit()
                    logger.debug(f"Applied migration: {migration_file}")
                except Exception as e:
                    # Log but don't fail - migration might already be applied
                    logger.debug(f"Migration {migration_file} skipped or already applied: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to apply incremental migrations: {e}")

    # =============================================================================
    # SOURCE OPERATIONS (MediaSource table)
    # =============================================================================

    def create_source(
        self, source_id: str, title: str, url: str, **metadata
    ) -> MediaSource | None:
        """Create a new source record or update existing one for re-runs."""
        try:
            with self.get_session() as session:
                # Extract tags and categories from metadata (they use normalized tables)
                tags_json = metadata.pop("tags_json", None)
                categories_json = metadata.pop("categories_json", None)
                source_type = metadata.get("source_type", "youtube")

                # Check for existing source using claim-centric schema (source_id)
                existing_source = (
                    session.query(MediaSource)
                    .filter(MediaSource.source_id == source_id)
                    .first()
                )

                if existing_source:
                    # Update existing source for re-runs
                    logger.info(f"Updating existing source record: {source_id}")

                    # Update core fields
                    existing_source.title = title
                    existing_source.url = url
                    existing_source.processed_at = datetime.utcnow()

                    # Update metadata fields (excluding tags_json, categories_json, and invalid fields)
                    # Filter out fields that don't exist in MediaSource model
                    invalid_fields = {"extraction_method"}  # Fields not in MediaSource
                    for key, value in metadata.items():
                        if key not in invalid_fields and hasattr(existing_source, key):
                            setattr(existing_source, key, value)

                    session.commit()

                    # Store tags and categories in normalized tables
                    if tags_json:
                        self._store_platform_tags(
                            session, source_id, tags_json, source_type
                        )
                    if categories_json:
                        self._store_platform_categories(
                            session, source_id, categories_json, source_type
                        )

                    session.commit()
                    logger.info(f"Updated source record: {source_id}")
                    return existing_source
                else:
                    # Create new source with claim-centric schema
                    # Filter out invalid fields before creating MediaSource
                    invalid_fields = {"extraction_method"}  # Fields not in MediaSource
                    filtered_metadata = {
                        k: v for k, v in metadata.items() if k not in invalid_fields
                    }
                    source = MediaSource(
                        source_id=source_id, title=title, url=url, **filtered_metadata
                    )
                    session.add(source)
                    session.commit()

                    # Store tags and categories in normalized tables
                    if tags_json:
                        self._store_platform_tags(
                            session, source_id, tags_json, source_type
                        )
                    if categories_json:
                        self._store_platform_categories(
                            session, source_id, categories_json, source_type
                        )

                    session.commit()
                    logger.info(f"Created source record: {source_id}")
                    return source
        except Exception as e:
            logger.error(f"Failed to create/update source {source_id}: {e}")
            return None

    def _store_platform_tags(
        self, session: Session, source_id: str, tags: list[str] | None, platform: str
    ) -> None:
        """Store platform tags in normalized tables."""
        if not tags:
            return

        # Ensure tags is a list
        if not isinstance(tags, list):
            logger.warning(f"tags_json is not a list for source {source_id}, skipping")
            return

        # Clear existing tags for this source
        session.query(SourcePlatformTag).filter(
            SourcePlatformTag.source_id == source_id
        ).delete()

        # Store each tag
        for tag_name in tags:
            if not tag_name or not isinstance(tag_name, str):
                continue

            sanitized_tag = self._sanitize_tag_name(tag_name)
            if not sanitized_tag:
                continue

            # Get or create platform tag
            platform_tag = (
                session.query(PlatformTag)
                .filter(
                    PlatformTag.platform == platform,
                    PlatformTag.tag_name == sanitized_tag,
                )
                .first()
            )

            if not platform_tag:
                platform_tag = PlatformTag(platform=platform, tag_name=sanitized_tag)
                session.add(platform_tag)
                session.flush()  # Get the tag_id

            # Create source-platform tag relationship
            source_tag = SourcePlatformTag(
                source_id=source_id, tag_id=platform_tag.tag_id
            )
            session.add(source_tag)

    def _store_platform_categories(
        self,
        session: Session,
        source_id: str,
        categories: list[str] | None,
        platform: str,
    ) -> None:
        """Store platform categories in normalized tables."""
        if not categories:
            return

        # Ensure categories is a list
        if not isinstance(categories, list):
            logger.warning(
                f"categories_json is not a list for source {source_id}, skipping"
            )
            return

        # Clear existing categories for this source
        session.query(SourcePlatformCategory).filter(
            SourcePlatformCategory.source_id == source_id
        ).delete()

        # Store each category
        for category_name in categories:
            if not category_name or not isinstance(category_name, str):
                continue

            # Get or create platform category
            platform_category = (
                session.query(PlatformCategory)
                .filter(
                    PlatformCategory.platform == platform,
                    PlatformCategory.category_name == category_name,
                )
                .first()
            )

            if not platform_category:
                platform_category = PlatformCategory(
                    platform=platform, category_name=category_name
                )
                session.add(platform_category)
                session.flush()  # Get the category_id

            # Create source-platform category relationship
            source_category = SourcePlatformCategory(
                source_id=source_id, category_id=platform_category.category_id
            )
            session.add(source_category)

    def _sanitize_tag_name(self, tag_name: str) -> str:
        """Normalize tag names by replacing spaces/dots with underscores."""
        if not isinstance(tag_name, str):
            return ""

        sanitized = tag_name.strip()
        if not sanitized:
            return ""

        sanitized = re.sub(r"[\.\s]+", "_", sanitized)
        sanitized = re.sub(r"_+", "_", sanitized)
        return sanitized

    def _normalize_platform_tag(
        self, session: Session, tag: PlatformTag
    ) -> PlatformTag | None:
        """Ensure stored platform tags use sanitized naming (merging duplicates)."""
        if not tag or not tag.tag_name:
            return tag

        sanitized = self._sanitize_tag_name(tag.tag_name)
        if not sanitized or sanitized == tag.tag_name:
            return tag

        existing = (
            session.query(PlatformTag)
            .filter(
                PlatformTag.platform == tag.platform,
                PlatformTag.tag_name == sanitized,
            )
            .first()
        )

        if existing:
            session.query(SourcePlatformTag).filter(
                SourcePlatformTag.tag_id == tag.tag_id
            ).update(
                {SourcePlatformTag.tag_id: existing.tag_id}, synchronize_session=False
            )
            session.delete(tag)
            session.flush()
            return existing

        tag.tag_name = sanitized
        session.flush()
        return tag

    def get_source(self, source_id: str) -> MediaSource | None:
        """Get source by ID (using claim-centric schema with source_id)."""
        try:
            with self.get_session() as session:
                # Use claim_models MediaSource (has source_id)
                source = (
                    session.query(MediaSource)
                    .filter(MediaSource.source_id == source_id)
                    .first()
                )

                # Add platform categories/tags as dynamic properties
                if source:
                    categories = self._get_platform_categories_for_source(
                        session, source_id
                    )
                    tags = self._get_platform_tags_for_source(session, source_id)
                    # Store as dynamic attributes (not persisted to DB)
                    source.categories_json = categories if categories else []
                    source.tags_json = tags if tags else []

                return source
        except Exception as e:
            logger.error(f"Failed to get source {source_id}: {e}")
            return None

    def get_sources_batch(self, source_ids: list[str]) -> list[MediaSource]:
        """
        Get multiple sources in a single query (optimized for batch lookups).

        Args:
            source_ids: List of source IDs to fetch

        Returns:
            List of MediaSource objects (may be shorter than input if some don't exist)
        """
        if not source_ids:
            return []

        try:
            with self.get_session() as session:
                sources = (
                    session.query(MediaSource)
                    .filter(MediaSource.source_id.in_(source_ids))
                    .all()
                )

                # Add platform categories/tags for each source
                for source in sources:
                    categories = self._get_platform_categories_for_source(
                        session, source.source_id
                    )
                    tags = self._get_platform_tags_for_source(session, source.source_id)
                    source.categories_json = categories if categories else []
                    source.tags_json = tags if tags else []

                return sources
        except Exception as e:
            logger.error(f"Failed to batch get sources: {e}")
            return []

    def get_source_by_file_path(self, file_path: str) -> MediaSource | None:
        """Get source by audio file path (database-centric lookup).

        This is the preferred method for looking up metadata during transcription,
        as it doesn't require extracting source_id from filename.
        """
        try:
            from pathlib import Path

            # Normalize path for comparison
            file_path_normalized = str(Path(file_path).resolve())

            with self.get_session() as session:
                # Query all videos with audio_file_path set
                videos = (
                    session.query(MediaSource)
                    .filter(MediaSource.audio_file_path.isnot(None))
                    .all()
                )

                # Check each video's audio_file_path (handle path variations)
                for video in videos:
                    if video.audio_file_path:
                        try:
                            stored_path = str(Path(video.audio_file_path).resolve())
                            if stored_path == file_path_normalized:
                                # Add platform categories as a dynamic property
                                categories = self._get_platform_categories_for_source(
                                    session, video.source_id
                                )
                                tags = self._get_platform_tags_for_source(
                                    session, video.source_id
                                )
                                # Store as dynamic attributes (not persisted to DB)
                                video.categories_json = categories if categories else []
                                video.tags_json = tags if tags else []
                                return video
                        except (OSError, ValueError):
                            # Handle invalid paths gracefully
                            continue

                # Not found
                return None
        except Exception as e:
            logger.error(f"Failed to get video by file path {file_path}: {e}")
            return None

    def _get_platform_tags_for_source(self, session, source_id: str) -> list[str]:
        """Get platform tags for a source from the normalized tables."""
        try:
            tag_records = (
                session.query(PlatformTag)
                .join(
                    SourcePlatformTag,
                    PlatformTag.tag_id == SourcePlatformTag.tag_id,
                )
                .filter(SourcePlatformTag.source_id == source_id)
                .all()
            )

            sanitized_tags: list[str] = []
            dirty = False

            for tag in tag_records:
                normalized = self._normalize_platform_tag(session, tag)
                if normalized is None:
                    continue
                sanitized_tags.append(normalized.tag_name)
                if normalized.tag_name != tag.tag_name:
                    dirty = True

            if dirty:
                try:
                    session.commit()
                except Exception as commit_error:
                    session.rollback()
                    logger.error(
                        f"Failed to normalize tags for {source_id}: {commit_error}"
                    )

            return sanitized_tags
        except Exception as e:
            logger.debug(f"Could not retrieve platform tags for {source_id}: {e}")
            return []

    def _get_platform_categories_for_source(self, session, source_id: str) -> list[str]:
        """Get platform categories for a source from the normalized tables."""
        try:
            # Query the junction table and join with platform_categories
            results = (
                session.query(PlatformCategory.category_name)
                .join(
                    SourcePlatformCategory,
                    PlatformCategory.category_id == SourcePlatformCategory.category_id,
                )
                .filter(SourcePlatformCategory.source_id == source_id)
                .all()
            )
            return [r[0] for r in results] if results else []
        except Exception as e:
            logger.debug(f"Could not retrieve platform categories for {source_id}: {e}")
            return []

    def update_source(self, source_id: str, **updates) -> bool:
        """Update source record."""
        try:
            with self.get_session() as session:
                source = (
                    session.query(MediaSource)
                    .filter(MediaSource.source_id == source_id)
                    .first()
                )
                if not source:
                    return False

                for key, value in updates.items():
                    if hasattr(source, key):
                        setattr(source, key, value)

                session.commit()
                logger.info(f"Updated source {source_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to update source {source_id}: {e}")
            return False

    # ========================================================================
    # Source ID Alias Management (Multi-Source Deduplication)
    # ========================================================================

    def create_source_alias(
        self,
        primary_source_id: str,
        alias_source_id: str,
        alias_type: str,
        match_confidence: float,
        match_method: str,
        match_metadata: dict | None = None,
        verified_by: str = "system",
    ) -> bool:
        """
        Create an alias linking two source_ids that refer to the same content.

        Args:
            primary_source_id: The primary source_id (e.g., YouTube video ID)
            alias_source_id: The alias source_id (e.g., podcast source_id)
            alias_type: Type of alias ('youtube_to_podcast', 'podcast_to_youtube', 'manual')
            match_confidence: Confidence score (0-1) for the match
            match_method: Method used to match ('title_fuzzy', 'title_exact', 'date_proximity', 'manual', 'guid')
            match_metadata: Additional metadata about the match (JSON)
            verified_by: Who verified this alias ('system' or user ID)

        Returns:
            True if alias created successfully
        """
        try:
            import uuid

            from .models import SourceIDAlias

            with self.get_session() as session:
                # Check if alias already exists
                existing = (
                    session.query(SourceIDAlias)
                    .filter(
                        SourceIDAlias.primary_source_id == primary_source_id,
                        SourceIDAlias.alias_source_id == alias_source_id,
                    )
                    .first()
                )

                if existing:
                    logger.debug(
                        f"Alias already exists: {primary_source_id} ↔ {alias_source_id}"
                    )
                    return True

                # Create new alias
                alias = SourceIDAlias(
                    alias_id=str(uuid.uuid4()),
                    primary_source_id=primary_source_id,
                    alias_source_id=alias_source_id,
                    alias_type=alias_type,
                    match_confidence=match_confidence,
                    match_method=match_method,
                    match_metadata=match_metadata or {},
                    verified_by=verified_by,
                )

                session.add(alias)
                session.commit()

                logger.info(
                    f"Created source alias: {primary_source_id} ↔ {alias_source_id} "
                    f"(confidence={match_confidence:.2f}, method={match_method})"
                )
                return True

        except Exception as e:
            logger.error(f"Failed to create source alias: {e}")
            return False

    def get_source_aliases(self, source_id: str) -> list[str]:
        """
        Get all source_ids that are aliases of the given source_id.

        Args:
            source_id: Source ID to look up

        Returns:
            List of related source_ids (bidirectional lookup)
        """
        try:
            from .models import SourceIDAlias

            with self.get_session() as session:
                # Find all aliases where this source_id is either primary or alias
                aliases_as_primary = (
                    session.query(SourceIDAlias.alias_source_id)
                    .filter(SourceIDAlias.primary_source_id == source_id)
                    .all()
                )

                aliases_as_alias = (
                    session.query(SourceIDAlias.primary_source_id)
                    .filter(SourceIDAlias.alias_source_id == source_id)
                    .all()
                )

                # Combine and flatten
                related_ids = [a[0] for a in aliases_as_primary] + [
                    a[0] for a in aliases_as_alias
                ]

                return related_ids

        except Exception as e:
            logger.error(f"Failed to get source aliases for {source_id}: {e}")
            return []

    def source_exists_or_has_alias(self, source_id: str) -> tuple[bool, str | None]:
        """
        Check if a source exists, or if an alias exists for it.

        Args:
            source_id: Source ID to check

        Returns:
            (exists, existing_source_id) where existing_source_id is the source_id
            that already exists in the database (either the original or an alias)
        """
        try:
            # Check if source exists directly
            source = self.get_source(source_id)
            if source:
                return (True, source_id)

            # Check if any aliases exist
            aliases = self.get_source_aliases(source_id)
            for alias_id in aliases:
                alias_source = self.get_source(alias_id)
                if alias_source:
                    return (True, alias_id)

            return (False, None)

        except Exception as e:
            logger.error(f"Failed to check source existence for {source_id}: {e}")
            return (False, None)

    def has_segments_for_source(self, source_id: str) -> bool:
        """
        Check if a source has segments (transcription completed).

        Args:
            source_id: Source ID to check

        Returns:
            True if source has segments, False otherwise
        """
        try:
            with self.get_session() as session:
                segment_count = (
                    session.query(Segment)
                    .filter(Segment.source_id == source_id)
                    .count()
                )
                return segment_count > 0
        except Exception as e:
            logger.error(f"Failed to check segments for {source_id}: {e}")
            return False

    def source_is_fully_processed(self, source_id: str) -> tuple[bool, str | None]:
        """
        Check if a source has been fully downloaded and transcribed.

        A source is considered fully processed if:
        1. It exists in the database (or has an alias)
        2. The audio file exists on disk
        3. It has segments (transcription completed)

        Args:
            source_id: Source ID to check

        Returns:
            (is_complete, existing_source_id) where existing_source_id is the source_id
            that already exists in the database (either the original or an alias)
        """
        from pathlib import Path

        try:
            # First check if source exists
            exists, existing_source_id = self.source_exists_or_has_alias(source_id)
            if not exists or not existing_source_id:
                return (False, None)

            # Get the source
            source = self.get_source(existing_source_id)
            if not source:
                return (False, None)

            # Check if audio file exists on disk
            if source.audio_file_path:
                audio_path = Path(source.audio_file_path)
                if not audio_path.exists():
                    logger.info(
                        f"Source {existing_source_id} exists in DB but audio file missing: {audio_path}"
                    )
                    return (False, existing_source_id)
            else:
                logger.info(
                    f"Source {existing_source_id} exists in DB but has no audio_file_path"
                )
                return (False, existing_source_id)

            # Check if source has segments (transcription completed)
            if not self.has_segments_for_source(existing_source_id):
                logger.info(
                    f"Source {existing_source_id} exists with audio but has no segments (not transcribed)"
                )
                return (False, existing_source_id)

            # All checks passed - source is fully processed
            return (True, existing_source_id)

        except Exception as e:
            logger.error(
                f"Failed to check if source is fully processed for {source_id}: {e}"
            )
            return (False, None)

    def merge_source_metadata(
        self,
        primary_source_id: str,
        secondary_source_id: str,
        prefer_primary: bool = True,
    ) -> bool:
        """
        Merge metadata from two sources that are aliases of each other.

        Args:
            primary_source_id: Primary source ID
            secondary_source_id: Secondary source ID
            prefer_primary: If True, keep primary values when both exist.
                           If False, prefer secondary values.

        Returns:
            True if merge successful
        """
        try:
            with self.get_session() as session:
                primary = (
                    session.query(MediaSource)
                    .filter(MediaSource.source_id == primary_source_id)
                    .first()
                )
                secondary = (
                    session.query(MediaSource)
                    .filter(MediaSource.source_id == secondary_source_id)
                    .first()
                )

                if not primary or not secondary:
                    logger.warning(
                        f"Cannot merge: one or both sources not found "
                        f"({primary_source_id}, {secondary_source_id})"
                    )
                    return False

                # Merge logic: fill in missing fields
                fields_to_merge = [
                    "description",
                    "uploader",
                    "uploader_id",
                    "author",
                    "organization",
                    "upload_date",
                    "recorded_at",
                    "published_at",
                    "duration_seconds",
                    "view_count",
                    "like_count",
                    "comment_count",
                    "language",
                ]

                for field in fields_to_merge:
                    primary_val = getattr(primary, field, None)
                    secondary_val = getattr(secondary, field, None)

                    if prefer_primary:
                        # Keep primary unless it's None
                        if primary_val is None and secondary_val is not None:
                            setattr(primary, field, secondary_val)
                    else:
                        # Prefer secondary
                        if secondary_val is not None:
                            setattr(primary, field, secondary_val)

                session.commit()
                logger.info(
                    f"Merged metadata: {secondary_source_id} → {primary_source_id}"
                )
                return True

        except Exception as e:
            logger.error(f"Failed to merge source metadata: {e}")
            return False

    def get_all_source_metadata(self, source_id: str) -> dict:
        """
        Get metadata from source and all aliased sources (non-destructive).

        Returns metadata from the primary source and all aliased sources,
        preserving provenance and allowing LLMs to reason across multiple
        metadata sets.

        Args:
            source_id: Primary source ID to retrieve metadata for

        Returns:
            Dictionary with structure:
            {
                'primary_source': {
                    'source_id': str,
                    'source_type': str,
                    'title': str,
                    'description': str,
                    'uploader': str,
                    'channel_id': str,
                    'url': str,
                    ... (all relevant fields)
                },
                'aliased_sources': [
                    {
                        'source_id': str,
                        'source_type': str,
                        'title': str,
                        'description': str,
                        ... (all relevant fields)
                    },
                    ...
                ]
            }

        Example:
            For an RSS podcast episode with a YouTube alias:
            {
                'primary_source': {
                    'source_id': 'podcast_xyz789',
                    'source_type': 'podcast',
                    'title': 'Dr. Andrew Huberman: Sleep',
                    'description': 'Episode 123',  # Minimal
                    'url': 'https://lexfridman.com/feed'
                },
                'aliased_sources': [
                    {
                        'source_id': 'video_abc123',
                        'source_type': 'youtube',
                        'title': 'Dr. Andrew Huberman: Sleep & Focus',
                        'description': 'In this episode...',  # Rich!
                        'channel_id': 'UCSHZKyawb77ixDdsGog4iWA',
                        'view_count': 1500000
                    }
                ]
            }
        """
        try:
            # Get primary source
            source = self.get_source(source_id)
            if not source:
                logger.warning(f"Source {source_id} not found")
                return {"primary_source": None, "aliased_sources": []}

            # Convert primary source to dict
            primary_metadata = {
                "source_id": source.source_id,
                "source_type": source.source_type,
                "title": source.title,
                "description": source.description,
                "uploader": source.uploader,
                "uploader_id": source.uploader_id,
                "author": source.author,
                "organization": source.organization,
                "channel_id": getattr(source, "channel_id", None),
                "upload_date": source.upload_date,
                "recorded_at": source.recorded_at,
                "published_at": source.published_at,
                "duration_seconds": source.duration_seconds,
                "view_count": source.view_count,
                "like_count": source.like_count,
                "comment_count": source.comment_count,
                "language": source.language,
                "url": source.url,
            }

            # Get all aliases
            alias_ids = self.get_source_aliases(source_id)
            aliased_metadata = []

            for alias_id in alias_ids:
                alias = self.get_source(alias_id)
                if alias:
                    aliased_metadata.append(
                        {
                            "source_id": alias.source_id,
                            "source_type": alias.source_type,
                            "title": alias.title,
                            "description": alias.description,
                            "uploader": alias.uploader,
                            "uploader_id": alias.uploader_id,
                            "author": alias.author,
                            "organization": alias.organization,
                            "channel_id": getattr(alias, "channel_id", None),
                            "upload_date": alias.upload_date,
                            "recorded_at": alias.recorded_at,
                            "published_at": alias.published_at,
                            "duration_seconds": alias.duration_seconds,
                            "view_count": alias.view_count,
                            "like_count": alias.like_count,
                            "comment_count": alias.comment_count,
                            "language": alias.language,
                            "url": alias.url,
                        }
                    )

            if aliased_metadata:
                logger.info(
                    f"📚 Retrieved metadata from {len(aliased_metadata)} aliased source(s) for {source_id}"
                )
                for alias in aliased_metadata:
                    logger.debug(
                        f"   → {alias['source_type']}: {alias['title'][:50]}..."
                    )

            return {
                "primary_source": primary_metadata,
                "aliased_sources": aliased_metadata,
            }

        except Exception as e:
            logger.error(f"Failed to get all source metadata for {source_id}: {e}")
            return {"primary_source": None, "aliased_sources": []}

    def source_exists(self, source_id: str) -> bool:
        """Check if source exists in database."""
        try:
            with self.get_session() as session:
                return (
                    session.query(MediaSource)
                    .filter(MediaSource.source_id == source_id)
                    .first()
                    is not None
                )
        except Exception as e:
            logger.error(f"Failed to check source existence {source_id}: {e}")
            return False

    def search_videos(
        self,
        query: str | None = None,
        uploader: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[MediaSource]:
        """Search videos with filters."""
        try:
            with self.get_session() as session:
                q = session.query(MediaSource)

                if query:
                    q = q.filter(
                        or_(
                            MediaSource.title.contains(query),
                            MediaSource.description.contains(query),
                        )
                    )

                if uploader:
                    q = q.filter(MediaSource.uploader.contains(uploader))

                if status:
                    q = q.filter(MediaSource.status == status)

                return q.order_by(desc(MediaSource.processed_at)).limit(limit).all()
        except Exception as e:
            logger.error(f"Failed to search videos: {e}")
            return []

    # =============================================================================
    # PARTIAL DOWNLOAD TRACKING (Audio vs Metadata)
    # =============================================================================

    def update_audio_status(
        self,
        source_id: str,
        audio_file_path: str | Path | None,
        audio_downloaded: bool,
        audio_file_size_bytes: int | None = None,
        audio_format: str | None = None,
    ) -> bool:
        """Update audio download status for a source."""
        try:
            with self.get_session() as session:
                source = (
                    session.query(MediaSource)
                    .filter(MediaSource.source_id == source_id)
                    .first()
                )
                if not source:
                    logger.warning(
                        f"Cannot update audio status: source {source_id} not found"
                    )
                    return False

                source.audio_file_path = (
                    str(audio_file_path) if audio_file_path else None
                )
                source.audio_downloaded = audio_downloaded
                source.audio_file_size_bytes = audio_file_size_bytes
                source.audio_format = audio_format

                # Clear audio retry flag if successful
                if audio_downloaded:
                    source.needs_audio_retry = False

                session.commit()
                logger.debug(
                    f"Updated audio status for {source_id}: downloaded={audio_downloaded}"
                )
                return True
        except Exception as e:
            logger.error(f"Failed to update audio status for {source_id}: {e}")
            return False

    def update_metadata_status(self, source_id: str, metadata_complete: bool) -> bool:
        """Update metadata completion status for a source."""
        try:
            with self.get_session() as session:
                source = (
                    session.query(MediaSource)
                    .filter(MediaSource.source_id == source_id)
                    .first()
                )
                if not source:
                    logger.warning(
                        f"Cannot update metadata status: source {source_id} not found"
                    )
                    return False

                source.metadata_complete = metadata_complete

                # Clear metadata retry flag if successful
                if metadata_complete:
                    source.needs_metadata_retry = False

                session.commit()
                logger.debug(
                    f"Updated metadata status for {source_id}: complete={metadata_complete}"
                )
                return True
        except Exception as e:
            logger.error(f"Failed to update metadata status for {source_id}: {e}")
            return False

    def link_audio_to_source(
        self,
        source_id: str,
        audio_file_path: str | Path,
        audio_metadata: dict[str, Any] | None = None
    ) -> bool:
        """
        Link downloaded audio file to existing source metadata.
        
        Validates:
        - Source exists in database
        - Audio file exists on disk
        - File size is reasonable (> 200KB)
        - Updates audio_downloaded, audio_file_path, audio_file_size_bytes
        
        Args:
            source_id: Source identifier
            audio_file_path: Path to downloaded audio file
            audio_metadata: Optional metadata about audio file
        
        Returns:
            True if successful, False otherwise
        """
        try:
            audio_path = Path(audio_file_path)
            
            # Validate audio file exists
            if not audio_path.exists():
                logger.error(f"Audio file not found: {audio_path}")
                return False
            
            # Validate file size
            file_size = audio_path.stat().st_size
            MIN_AUDIO_SIZE = 200 * 1024  # 200 KB
            if file_size < MIN_AUDIO_SIZE:
                logger.error(
                    f"Audio file too small ({file_size} bytes): {audio_path.name}"
                )
                return False
            
            # Validate source exists
            source = self.get_source(source_id)
            if not source:
                logger.error(f"Source not found: {source_id}")
                return False
            
            # Extract audio format from file extension
            audio_format = audio_path.suffix.lstrip('.')
            
            # Update source with audio information
            success = self.update_audio_status(
                source_id=source_id,
                audio_file_path=str(audio_path),
                audio_downloaded=True,
                audio_file_size_bytes=file_size,
                audio_format=audio_format
            )
            
            if success:
                logger.info(
                    f"✅ Linked audio to source {source_id}: "
                    f"{audio_path.name} ({file_size / (1024*1024):.1f} MB)"
                )
            
            return success
        
        except Exception as e:
            logger.error(f"Failed to link audio to source {source_id}: {e}")
            return False

    def verify_audio_metadata_link(self, source_id: str) -> dict[str, Any]:
        """
        Verify that audio file and metadata are properly linked.
        
        Checks:
        - Source record exists
        - audio_file_path is set
        - File exists on disk
        - File size matches database
        - Metadata is complete
        
        Args:
            source_id: Source identifier
        
        Returns:
            Diagnostic dict with status and issues
        """
        result = {
            "source_id": source_id,
            "valid": True,
            "issues": [],
            "warnings": [],
        }
        
        try:
            # Check source exists
            source = self.get_source(source_id)
            if not source:
                result["valid"] = False
                result["issues"].append("Source record not found in database")
                return result
            
            # Check audio_file_path is set
            if not source.audio_file_path:
                result["valid"] = False
                result["issues"].append("audio_file_path not set")
                return result
            
            # Check file exists on disk
            audio_path = Path(source.audio_file_path)
            if not audio_path.exists():
                result["valid"] = False
                result["issues"].append(f"Audio file not found: {audio_path}")
                return result
            
            # Check file size
            actual_size = audio_path.stat().st_size
            db_size = source.audio_file_size_bytes
            
            if db_size and abs(actual_size - db_size) > 1024:  # Allow 1KB difference
                result["warnings"].append(
                    f"File size mismatch: disk={actual_size}, db={db_size}"
                )
            
            # Check audio_downloaded flag
            if not source.audio_downloaded:
                result["warnings"].append("audio_downloaded flag is False")
            
            # Check metadata complete
            if not source.metadata_complete:
                result["warnings"].append("metadata_complete flag is False")
            
            # Check minimum file size
            MIN_SIZE = 200 * 1024  # 200 KB
            if actual_size < MIN_SIZE:
                result["warnings"].append(
                    f"Audio file very small: {actual_size} bytes"
                )
            
            result["file_size"] = actual_size
            result["audio_format"] = source.audio_format
            result["audio_path"] = str(audio_path)
            
            if result["warnings"]:
                logger.info(
                    f"⚠️ Audio link verification has warnings for {source_id}: "
                    f"{len(result['warnings'])} warnings"
                )
            else:
                logger.debug(f"✅ Audio link verified for {source_id}")
        
        except Exception as e:
            result["valid"] = False
            result["issues"].append(f"Verification error: {str(e)}")
            logger.error(f"Failed to verify audio link for {source_id}: {e}")
        
        return result

    def mark_for_retry(
        self,
        source_id: str,
        needs_metadata_retry: bool = False,
        needs_audio_retry: bool = False,
        failure_reason: str | None = None,
    ) -> bool:
        """Mark a source for retry (metadata, audio, or both)."""
        try:
            with self.get_session() as session:
                source = (
                    session.query(MediaSource)
                    .filter(MediaSource.source_id == source_id)
                    .first()
                )
                if not source:
                    logger.warning(
                        f"Cannot mark for retry: source {source_id} not found"
                    )
                    return False

                source.needs_metadata_retry = needs_metadata_retry
                source.needs_audio_retry = needs_audio_retry
                source.retry_count += 1
                source.last_retry_at = datetime.utcnow()

                if failure_reason:
                    source.failure_reason = failure_reason

                # Check if max retries exceeded (3 attempts)
                if source.retry_count >= 3:
                    source.max_retries_exceeded = True
                    source.status = "failed"
                    logger.warning(f"Source {source_id} exceeded max retries (3)")

                session.commit()
                logger.info(
                    f"Marked {source_id} for retry (attempt {source.retry_count}): "
                    f"metadata={needs_metadata_retry}, audio={needs_audio_retry}"
                )
                return True
        except Exception as e:
            logger.error(f"Failed to mark {source_id} for retry: {e}")
            return False

    def get_videos_needing_retry(
        self, metadata_only: bool = False, audio_only: bool = False
    ) -> list[MediaSource]:
        """Get videos that need retry (not exceeded max attempts)."""
        try:
            with self.get_session() as session:
                q = session.query(MediaSource).filter(
                    MediaSource.max_retries_exceeded == False,  # noqa: E712
                    or_(
                        MediaSource.needs_metadata_retry == True,
                        MediaSource.needs_audio_retry == True,
                    ),  # noqa: E712
                )

                if metadata_only:
                    q = q.filter(MediaSource.needs_metadata_retry == True)  # noqa: E712
                if audio_only:
                    q = q.filter(MediaSource.needs_audio_retry == True)  # noqa: E712

                return q.order_by(desc(MediaSource.last_retry_at)).all()
        except Exception as e:
            logger.error(f"Failed to get videos needing retry: {e}")
            return []

    def get_failed_videos(self) -> list[MediaSource]:
        """Get videos that exceeded max retry attempts."""
        try:
            with self.get_session() as session:
                return (
                    session.query(MediaSource)
                    .filter(MediaSource.max_retries_exceeded == True)  # noqa: E712
                    .order_by(desc(MediaSource.last_retry_at))
                    .all()
                )
        except Exception as e:
            logger.error(f"Failed to get failed videos: {e}")
            return []

    def get_incomplete_videos(self) -> list[MediaSource]:
        """Get videos with partial downloads (missing audio or metadata)."""
        try:
            with self.get_session() as session:
                return (
                    session.query(MediaSource)
                    .filter(
                        or_(
                            MediaSource.audio_downloaded == False,  # noqa: E712
                            MediaSource.metadata_complete == False,  # noqa: E712
                        ),
                        MediaSource.max_retries_exceeded == False,  # noqa: E712
                    )
                    .order_by(desc(MediaSource.updated_at))
                    .all()
                )
        except Exception as e:
            logger.error(f"Failed to get incomplete videos: {e}")
            return []

    def is_video_complete(self, source_id: str) -> bool:
        """Check if source has both audio and metadata complete."""
        try:
            with self.get_session() as session:
                source = (
                    session.query(MediaSource)
                    .filter(MediaSource.source_id == source_id)
                    .first()
                )
                if not source:
                    return False
                return source.audio_downloaded and source.metadata_complete
        except Exception as e:
            logger.error(f"Failed to check if source {source_id} is complete: {e}")
            return False

    def validate_audio_file_exists(self, source_id: str) -> bool:
        """Validate that the audio file path in database actually exists on disk."""
        try:
            with self.get_session() as session:
                source = (
                    session.query(MediaSource)
                    .filter(MediaSource.source_id == source_id)
                    .first()
                )
                if not source or not source.audio_file_path:
                    return False

                audio_path = Path(source.audio_file_path)
                exists = audio_path.exists()

                # If file doesn't exist but database says it does, mark for retry
                if not exists and source.audio_downloaded:
                    logger.warning(
                        f"Audio file missing for {source_id}: {source.audio_file_path}"
                    )
                    source.audio_downloaded = False
                    source.needs_audio_retry = True
                    session.commit()

                return exists
        except Exception as e:
            logger.error(f"Failed to validate audio file for {source_id}: {e}")
            return False

    # =============================================================================
    # TRANSCRIPT OPERATIONS
    # =============================================================================

    def create_transcript(
        self,
        source_id: str,
        language: str,
        is_manual: bool,
        transcript_text: str,
        transcript_segments: list[dict[str, Any]],
        **metadata,
    ) -> Transcript | None:
        """Create a new transcript record or update existing one for re-runs."""
        try:
            with self.get_session() as session:
                # Check for existing transcript for this source_id and language
                existing_transcript = (
                    session.query(Transcript)
                    .filter(
                        Transcript.source_id == source_id,
                        Transcript.language == language,
                    )
                    .order_by(desc(Transcript.created_at))
                    .first()
                )

                if existing_transcript:
                    # Update existing transcript for re-runs
                    logger.info(
                        f"Updating existing transcript for {source_id} (language: {language})"
                    )

                    # Update fields
                    existing_transcript.transcript_text = transcript_text
                    existing_transcript.transcript_segments_json = transcript_segments
                    existing_transcript.segment_count = len(transcript_segments)
                    existing_transcript.is_manual = is_manual
                    existing_transcript.created_at = (
                        datetime.utcnow()
                    )  # Update timestamp

                    # Update metadata fields
                    for key, value in metadata.items():
                        if hasattr(existing_transcript, key):
                            setattr(existing_transcript, key, value)

                    session.commit()
                    # Ensure all attributes are loaded before detaching
                    _ = existing_transcript.transcript_id  # Force attribute loading
                    session.expunge(
                        existing_transcript
                    )  # Detach from session to prevent refresh errors
                    logger.info(
                        f"Updated transcript: {existing_transcript.transcript_id}"
                    )
                    return existing_transcript
                else:
                    # Create new transcript
                    transcript_id = f"{source_id}_{language}_{uuid.uuid4().hex[:8]}"

                    transcript = Transcript(
                        transcript_id=transcript_id,
                        source_id=source_id,
                        language=language,
                        is_manual=is_manual,
                        transcript_text=transcript_text,
                        transcript_segments_json=transcript_segments,
                        segment_count=len(transcript_segments),
                        **metadata,
                    )
                    session.add(transcript)
                    session.commit()
                    # Ensure all attributes are loaded before detaching
                    _ = transcript.transcript_id  # Force attribute loading
                    session.expunge(
                        transcript
                    )  # Detach from session to prevent refresh errors
                    logger.info(f"Created transcript: {transcript_id}")
                    return transcript
        except Exception as e:
            logger.error(f"Failed to create/update transcript for {source_id}: {e}")
            return None

    def get_transcripts_for_video(self, source_id: str) -> list[Transcript]:
        """Get all transcripts for a source."""
        try:
            with self.get_session() as session:
                return (
                    session.query(Transcript)
                    .filter(Transcript.source_id == source_id)
                    .order_by(desc(Transcript.created_at))
                    .all()
                )
        except Exception as e:
            logger.error(f"Failed to get transcripts for {source_id}: {e}")
            return []

    def get_transcript(self, transcript_id: str) -> Transcript | None:
        """Get transcript by ID."""
        try:
            with self.get_session() as session:
                return (
                    session.query(Transcript)
                    .filter(Transcript.transcript_id == transcript_id)
                    .first()
                )
        except Exception as e:
            logger.error(f"Failed to get transcript {transcript_id}: {e}")
            return None

    def update_transcript(
        self,
        transcript_id: str,
        transcript_text: str | None = None,
        transcript_segments_json: list[dict[str, Any]] | None = None,
        speaker_assignments: dict[str, str] | None = None,
        speaker_assignment_completed: bool = False,
        **metadata,
    ) -> bool:
        """Update an existing transcript with new data."""
        try:
            with self.get_session() as session:
                transcript = (
                    session.query(Transcript)
                    .filter(Transcript.transcript_id == transcript_id)
                    .first()
                )

                if not transcript:
                    logger.error(f"Transcript {transcript_id} not found for update")
                    return False

                # Update fields if provided
                if transcript_text is not None:
                    transcript.transcript_text = transcript_text

                if transcript_segments_json is not None:
                    transcript.transcript_segments_json = transcript_segments_json
                    transcript.segment_count = len(transcript_segments_json)

                if speaker_assignments is not None:
                    # Store speaker assignments as metadata
                    transcript.speaker_assignments = speaker_assignments

                if speaker_assignment_completed:
                    transcript.speaker_assignment_completed = True
                    transcript.speaker_assignment_completed_at = datetime.utcnow()

                # Update any additional metadata fields
                for key, value in metadata.items():
                    if hasattr(transcript, key):
                        setattr(transcript, key, value)

                session.commit()
                logger.info(f"Updated transcript {transcript_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to update transcript {transcript_id}: {e}")
            return False

    def get_transcript_by_type(
        self,
        source_id: str,
        transcript_type: str
    ) -> Transcript | None:
        """Get specific transcript type for source."""
        try:
            with self.get_session() as session:
                return (
                    session.query(Transcript)
                    .filter(
                        Transcript.source_id == source_id,
                        Transcript.transcript_type == transcript_type
                    )
                    .first()
                )
        except Exception as e:
            logger.error(
                f"Failed to get transcript type {transcript_type} for source {source_id}: {e}"
            )
            return None

    def set_preferred_transcript(
        self,
        source_id: str,
        transcript_id: str
    ) -> bool:
        """Set which transcript to use for processing."""
        try:
            with self.get_session() as session:
                source = (
                    session.query(MediaSource)
                    .filter(MediaSource.source_id == source_id)
                    .first()
                )
                
                if not source:
                    logger.error(f"Source not found: {source_id}")
                    return False
                
                source.preferred_transcript_id = transcript_id
                session.commit()
                
                logger.info(f"Set preferred transcript for {source_id}: {transcript_id}")
                return True
        
        except Exception as e:
            logger.error(f"Failed to set preferred transcript: {e}")
            return False

    def get_preferred_transcript(self, source_id: str) -> Transcript | None:
        """Get the preferred transcript for a source."""
        try:
            with self.get_session() as session:
                source = (
                    session.query(MediaSource)
                    .filter(MediaSource.source_id == source_id)
                    .first()
                )
                
                if not source or not source.preferred_transcript_id:
                    return None
                
                return (
                    session.query(Transcript)
                    .filter(Transcript.transcript_id == source.preferred_transcript_id)
                    .first()
                )
        
        except Exception as e:
            logger.error(f"Failed to get preferred transcript for {source_id}: {e}")
            return None

    def calculate_transcript_quality(self, transcript: Transcript) -> float:
        """
        Calculate quality score for transcript.
        
        Factors:
        - Has speaker labels: +0.3
        - Has timestamps: +0.2
        - Formatting quality: +0.3
        - Length/completeness: +0.2
        """
        score = 0.0
        
        # Speaker labels
        if transcript.has_speaker_labels:
            score += 0.3
        
        # Timestamps
        if transcript.has_timestamps:
            score += 0.2
        
        # Formatting quality (check segment count)
        if transcript.segment_count and transcript.segment_count > 10:
            score += 0.15
        
        # Length/completeness
        if transcript.transcript_text:
            word_count = len(transcript.transcript_text.split())
            if word_count > 1000:
                score += 0.2
            elif word_count > 500:
                score += 0.1
        
        # PDF provided transcripts get bonus
        if transcript.transcript_type == "pdf_provided":
            score += 0.15
        
        return min(score, 1.0)  # Cap at 1.0

    def get_transcript_path_for_regeneration(
        self, transcript_id: str
    ) -> tuple[Path | None, dict | None]:
        """Get file path and metadata needed to regenerate transcript markdown."""
        try:
            with self.get_session() as session:
                transcript = (
                    session.query(Transcript)
                    .filter(Transcript.transcript_id == transcript_id)
                    .first()
                )

                if not transcript:
                    return None, None

                # Find the most recent generated markdown file
                generated_file = (
                    session.query(GeneratedFile)
                    .filter(
                        GeneratedFile.transcript_id == transcript_id,
                        GeneratedFile.file_type == "transcript_md",
                    )
                    .order_by(GeneratedFile.created_at.desc())
                    .first()
                )

                if not generated_file:
                    return None, None

                # Get video metadata for markdown generation
                # Use claim_models MediaSource (has source_id)
                source = (
                    session.query(MediaSource)
                    .filter(MediaSource.source_id == transcript.source_id)
                    .first()
                )

                video_metadata = None
                if source:
                    video_metadata = {
                        "source_id": source.source_id,
                        "title": source.title,
                        "url": source.url,
                        "uploader": getattr(source, "uploader", None),
                        "upload_date": getattr(source, "upload_date", None),
                        "duration": getattr(source, "duration_seconds", None),
                        # Claim-centric schema doesn't have tags_json column
                        "tags": [],
                    }

                return Path(generated_file.file_path), video_metadata

        except Exception as e:
            logger.error(f"Failed to get transcript path: {e}")
            return None, None

    # =============================================================================
    # SUMMARY OPERATIONS
    # =============================================================================

    def _update_transcript_summary_section(
        self,
        session: Session,
        source_id: str,
        summary_text: str,
        summary_id: str,
    ) -> None:
        """Append or update the summary section within the transcript markdown file."""
        try:
            transcript_record = (
                session.query(GeneratedFile)
                .filter(
                    GeneratedFile.source_id == source_id,
                    GeneratedFile.file_type == "transcript_md",
                    GeneratedFile.file_format == "md",
                )
                .order_by(desc(GeneratedFile.created_at))
                .first()
            )

            if not transcript_record:
                logger.debug(
                    f"No tracked transcript markdown found for {source_id}; skipping summary append"
                )
                return

            transcript_path = Path(transcript_record.file_path)
            if not transcript_path.exists():
                logger.debug(
                    f"Tracked transcript path missing for {source_id}: {transcript_path}"
                )
                return

            additional_yaml_fields = {
                "latest_summary_id": summary_id,
                "summary_last_updated": datetime.utcnow().isoformat(),
            }

            overwrite_or_insert_summary_section(
                transcript_path,
                summary_text.strip(),
                additional_yaml_fields=additional_yaml_fields,
            )

            transcript_record.summary_id = summary_id
            transcript_record.last_modified = datetime.utcnow()
            session.commit()

            logger.info(
                f"Appended summary section to transcript markdown: {transcript_path}"
            )
        except Exception as exc:
            logger.error(
                f"Failed to append summary section to transcript for {source_id}: {exc}"
            )

    def create_summary(
        self,
        source_id: str,
        summary_text: str,
        llm_provider: str,
        llm_model: str,
        transcript_id: str | None = None,
        **metadata,
    ) -> Summary | None:
        """Create a new summary record."""
        try:
            summary_id = f"{source_id}_{llm_model}_{uuid.uuid4().hex[:8]}"

            with self.get_session() as session:
                summary = Summary(
                    summary_id=summary_id,
                    source_id=source_id,
                    transcript_id=transcript_id,
                    summary_text=summary_text,
                    llm_provider=llm_provider,
                    llm_model=llm_model,
                    summary_length=len(summary_text),
                    **metadata,
                )
                session.add(summary)
                session.commit()
                logger.info(f"Created summary: {summary_id}")
                self._update_transcript_summary_section(
                    session, source_id, summary_text, summary_id
                )
                return summary
        except Exception as e:
            logger.error(f"Failed to create summary for {source_id}: {e}")
            return None

    def get_summaries_for_video(self, source_id: str) -> list[Summary]:
        """Get all summaries for a source."""
        try:
            with self.get_session() as session:
                return (
                    session.query(Summary)
                    .filter(Summary.source_id == source_id)
                    .order_by(desc(Summary.created_at))
                    .all()
                )
        except Exception as e:
            logger.error(f"Failed to get summaries for {source_id}: {e}")
            return []

    def get_latest_summary(self, source_id: str) -> Summary | None:
        """Get the most recent summary for a source."""
        try:
            with self.get_session() as session:
                return (
                    session.query(Summary)
                    .filter(Summary.source_id == source_id)
                    .order_by(desc(Summary.created_at))
                    .first()
                )
        except Exception as e:
            logger.error(f"Failed to get latest summary for {source_id}: {e}")
            return None

    # =============================================================================
    # HCE OPERATIONS
    # =============================================================================

    def save_hce_data(self, source_id: str, hce_outputs) -> bool:
        """
        DEPRECATED: Save HCE pipeline outputs to database tables.

        This method is deprecated in favor of the claim-centric architecture.
        Use ClaimStore.upsert_pipeline_outputs() instead.

        The Episode model has been removed. This method now returns False
        and logs a deprecation warning.
        """
        logger.warning(
            "save_hce_data() is deprecated. Use ClaimStore.upsert_pipeline_outputs() instead."
        )
        return False

    # =============================================================================
    # MOC OPERATIONS
    # =============================================================================

    def create_moc_extraction(
        self,
        source_id: str,
        people: list[dict] | None = None,
        tags: list[dict] | None = None,
        mental_models: list[dict] | None = None,
        jargon: list[dict] | None = None,
        beliefs: list[dict] | None = None,
        **metadata,
    ) -> MOCExtraction | None:
        """Create a new MOC extraction record."""
        try:
            moc_id = f"{source_id}_moc_{uuid.uuid4().hex[:8]}"

            with self.get_session() as session:
                moc = MOCExtraction(
                    moc_id=moc_id,
                    source_id=source_id,
                    people_json=people or [],
                    tags_json=tags or [],
                    mental_models_json=mental_models or [],
                    jargon_json=jargon or [],
                    beliefs_json=beliefs or [],
                    **metadata,
                )
                session.add(moc)
                session.commit()
                logger.info(f"Created MOC extraction: {moc_id}")
                return moc
        except Exception as e:
            logger.error(f"Failed to create MOC extraction for {source_id}: {e}")
            return None

    # =============================================================================
    # BRIGHT DATA SESSION OPERATIONS
    # =============================================================================

    def create_bright_data_session(
        self, session_id: str, source_id: str, session_type: str, **metadata
    ) -> BrightDataSession | None:
        """Create a new Bright Data session record."""
        try:
            with self.get_session() as session:
                bd_session = BrightDataSession(
                    session_id=session_id,
                    source_id=source_id,
                    session_type=session_type,
                    **metadata,
                )
                session.add(bd_session)
                session.commit()
                logger.info(f"Created Bright Data session: {session_id}")
                return bd_session
        except Exception as e:
            logger.error(f"Failed to create Bright Data session {session_id}: {e}")
            return None

    def update_bright_data_session_cost(
        self,
        session_id: str,
        requests_count: int = 0,
        data_downloaded_bytes: int = 0,
        cost: float = 0.0,
    ) -> bool:
        """Update Bright Data session usage and cost."""
        try:
            with self.get_session() as session:
                bd_session = (
                    session.query(BrightDataSession)
                    .filter(BrightDataSession.session_id == session_id)
                    .first()
                )

                if not bd_session:
                    return False

                bd_session.requests_count += requests_count
                bd_session.data_downloaded_bytes += data_downloaded_bytes
                bd_session.total_cost += cost

                session.commit()
                logger.info(f"Updated Bright Data session {session_id} cost: +${cost}")
                return True
        except Exception as e:
            logger.error(f"Failed to update Bright Data session {session_id}: {e}")
            return False

    # =============================================================================
    # PROCESSING JOB OPERATIONS
    # =============================================================================

    def create_processing_job(
        self, job_type: str, input_urls: list[str], config: dict[str, Any], **metadata
    ) -> ProcessingJob | None:
        """Create a new processing job."""
        try:
            job_id = f"{job_type}_{uuid.uuid4().hex[:8]}"

            with self.get_session() as session:
                job = ProcessingJob(
                    job_id=job_id,
                    job_type=job_type,
                    input_urls_json=input_urls,
                    config_json=config,
                    total_items=len(input_urls),
                    **metadata,
                )
                session.add(job)
                session.commit()
                logger.info(f"Created processing job: {job_id}")
                return job
        except Exception as e:
            logger.error(f"Failed to create processing job: {e}")
            return None

    def update_job_progress(
        self,
        job_id: str,
        completed_items: int | None = None,
        failed_items: int | None = None,
        status: str | None = None,
        **updates,
    ) -> bool:
        """Update processing job progress."""
        try:
            with self.get_session() as session:
                job = (
                    session.query(ProcessingJob)
                    .filter(ProcessingJob.job_id == job_id)
                    .first()
                )

                if not job:
                    return False

                if completed_items is not None:
                    job.completed_items = completed_items
                if failed_items is not None:
                    job.failed_items = failed_items
                if status:
                    job.status = status
                    if status == "completed":
                        job.completed_at = datetime.utcnow()

                for key, value in updates.items():
                    if hasattr(job, key):
                        setattr(job, key, value)

                session.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to update job {job_id}: {e}")
            return False

    # =============================================================================
    # FILE GENERATION TRACKING
    # =============================================================================

    def track_generated_file(
        self,
        source_id: str,
        file_path: str,
        file_type: str,
        file_format: str,
        **metadata,
    ) -> GeneratedFile | None:
        """Track a generated output file."""
        try:
            file_id = f"{source_id}_{file_type}_{uuid.uuid4().hex[:8]}"

            with self.get_session() as session:
                file_size = 0
                if Path(file_path).exists():
                    file_size = Path(file_path).stat().st_size

                generated_file = GeneratedFile(
                    file_id=file_id,
                    source_id=source_id,
                    file_path=file_path,
                    file_type=file_type,
                    file_format=file_format,
                    file_size_bytes=file_size,
                    **metadata,
                )
                session.add(generated_file)
                session.commit()
                logger.info(f"Tracked generated file: {file_path}")
                return generated_file
        except Exception as e:
            logger.error(f"Failed to track generated file {file_path}: {e}")
            return None

    # =============================================================================
    # ANALYTICS AND REPORTING
    # =============================================================================

    def get_processing_stats(self) -> dict[str, Any]:
        """Get comprehensive processing statistics."""
        try:
            with self.get_session() as session:
                # Video statistics
                total_videos = session.query(MediaSource).count()
                completed_videos = (
                    session.query(MediaSource)
                    .filter(MediaSource.status == "completed")
                    .count()
                )

                # Cost statistics
                total_cost = (
                    session.query(func.sum(BrightDataSession.total_cost)).scalar()
                    or 0.0
                )

                # Token statistics
                total_tokens = (
                    session.query(func.sum(Summary.total_tokens)).scalar() or 0
                )

                # Processing time statistics
                total_processing_time = (
                    session.query(func.sum(Summary.processing_time_seconds)).scalar()
                    or 0.0
                )

                return {
                    "total_videos": total_videos,
                    "completed_videos": completed_videos,
                    "completion_rate": (
                        completed_videos / total_videos if total_videos > 0 else 0
                    ),
                    "total_bright_data_cost": total_cost,
                    "total_tokens_consumed": total_tokens,
                    "total_processing_time_hours": total_processing_time / 3600,
                    "average_cost_per_video": (
                        total_cost / completed_videos if completed_videos > 0 else 0
                    ),
                }
        except Exception as e:
            logger.error(f"Failed to get processing stats: {e}")
            return {}

    def get_cost_breakdown(self) -> dict[str, Any]:
        """Get detailed cost breakdown by session type."""
        try:
            with self.get_session() as session:
                # Bright Data costs by session type
                bd_costs = (
                    session.query(
                        BrightDataSession.session_type,
                        func.sum(BrightDataSession.total_cost),
                        func.count(BrightDataSession.session_id),
                    )
                    .group_by(BrightDataSession.session_type)
                    .all()
                )

                # LLM costs by provider
                llm_costs = (
                    session.query(
                        Summary.llm_provider,
                        func.sum(Summary.processing_cost),
                        func.sum(Summary.total_tokens),
                    )
                    .group_by(Summary.llm_provider)
                    .all()
                )

                return {
                    "bright_data_costs": [
                        {
                            "session_type": session_type,
                            "total_cost": total_cost,
                            "session_count": session_count,
                        }
                        for session_type, total_cost, session_count in bd_costs
                    ],
                    "llm_costs": [
                        {
                            "provider": provider,
                            "total_cost": total_cost,
                            "total_tokens": total_tokens,
                        }
                        for provider, total_cost, total_tokens in llm_costs
                    ],
                }
        except Exception as e:
            logger.error(f"Failed to get cost breakdown: {e}")
            return {}

    # =============================================================================
    # DATABASE MAINTENANCE
    # =============================================================================

    def cleanup_old_sessions(self, days_old: int = 30) -> int:
        """Clean up old Bright Data sessions."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)

            with self.get_session() as session:
                old_sessions = (
                    session.query(BrightDataSession)
                    .filter(BrightDataSession.created_at < cutoff_date)
                    .all()
                )

                count = len(old_sessions)
                for session_obj in old_sessions:
                    session.delete(session_obj)

                session.commit()
                logger.info(f"Cleaned up {count} old Bright Data sessions")
                return count
        except Exception as e:
            logger.error(f"Failed to cleanup old sessions: {e}")
            return 0

    def vacuum_database(self) -> bool:
        """Vacuum the SQLite database to reclaim space."""
        try:
            with self.engine.connect() as connection:
                connection.execute("VACUUM")
            logger.info("Database vacuumed successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to vacuum database: {e}")
            return False

    def optimize_database(self) -> bool:
        """Optimize database performance by adding indexes and running maintenance.

        Returns:
            True if optimization was successful
        """
        try:
            with self.engine.connect() as connection:
                # Create performance indexes for common queries
                indexes = [
                    # Video table indexes
                    "CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status)",
                    "CREATE INDEX IF NOT EXISTS idx_videos_uploader ON videos(uploader)",
                    "CREATE INDEX IF NOT EXISTS idx_videos_created_at ON videos(created_at)",
                    "CREATE INDEX IF NOT EXISTS idx_videos_title_search ON videos(title)",
                    # Transcript table indexes
                    "CREATE INDEX IF NOT EXISTS idx_transcripts_video_id ON transcripts(source_id)",
                    "CREATE INDEX IF NOT EXISTS idx_transcripts_created_at ON transcripts(created_at)",
                    # Summary table indexes
                    "CREATE INDEX IF NOT EXISTS idx_summaries_video_id ON summaries(source_id)",
                    "CREATE INDEX IF NOT EXISTS idx_summaries_processing_type ON summaries(processing_type)",
                    "CREATE INDEX IF NOT EXISTS idx_summaries_llm_provider ON summaries(llm_provider)",
                    "CREATE INDEX IF NOT EXISTS idx_summaries_created_at ON summaries(created_at)",
                    # BrightData session indexes
                    "CREATE INDEX IF NOT EXISTS idx_brightdata_created_at ON bright_data_sessions(created_at)",
                    "CREATE INDEX IF NOT EXISTS idx_brightdata_status ON bright_data_sessions(status)",
                    # Processing job indexes
                    "CREATE INDEX IF NOT EXISTS idx_processing_jobs_status ON processing_jobs(status)",
                    "CREATE INDEX IF NOT EXISTS idx_processing_jobs_created_at ON processing_jobs(created_at)",
                    # HCE-specific indexes for claim searches
                    "CREATE INDEX IF NOT EXISTS idx_claims_video_id ON claims(source_id)",
                    "CREATE INDEX IF NOT EXISTS idx_claims_tier ON claims(tier)",
                    "CREATE INDEX IF NOT EXISTS idx_claims_claim_type ON claims(claim_type)",
                    "CREATE INDEX IF NOT EXISTS idx_people_video_id ON people(source_id)",
                    "CREATE INDEX IF NOT EXISTS idx_concepts_video_id ON concepts(source_id)",
                ]

                # Execute index creation
                for index_sql in indexes:
                    try:
                        connection.execute(index_sql)
                    except Exception as e:
                        # Some indexes might fail if tables don't exist yet (HCE tables)
                        logger.debug(f"Index creation skipped: {e}")

                # Run SQLite optimization commands
                optimization_commands = [
                    "PRAGMA optimize",  # SQLite query planner optimization
                    "PRAGMA analysis_limit=1000",  # Analyze table statistics
                    "ANALYZE",  # Update table statistics for query planner
                ]

                for command in optimization_commands:
                    connection.execute(command)

                logger.info("Database optimization completed successfully")
                return True

        except Exception as e:
            logger.error(f"Database optimization failed: {e}")
            return False

    # =============================================================================
    # CLAIM TIER VALIDATION METHODS
    # =============================================================================

    def save_claim_tier_validation(
        self,
        claim_id: str,
        episode_id: str,
        original_tier: str,
        validated_tier: str,
        claim_text: str,
        claim_type: str = None,
        validated_by_user: str = None,
        original_scores: dict = None,
        model_used: str = None,
        evidence_spans: list = None,
        validation_session_id: str = None,
    ) -> str:
        """Save a claim tier validation."""
        try:
            validation_id = str(uuid.uuid4())
            is_modified = original_tier != validated_tier

            validation = ClaimTierValidation(
                validation_id=validation_id,
                claim_id=claim_id,
                episode_id=episode_id,
                original_tier=original_tier,
                validated_tier=validated_tier,
                is_modified=is_modified,
                claim_text=claim_text,
                claim_type=claim_type,
                validated_by_user=validated_by_user,
                original_scores=original_scores,
                model_used=model_used,
                evidence_spans=evidence_spans,
                validation_session_id=validation_session_id,
            )

            with self.get_session() as session:
                session.add(validation)
                session.commit()

            logger.info(f"Saved claim tier validation: {validation_id}")
            return validation_id

        except Exception as e:
            logger.error(f"Failed to save claim tier validation: {e}")
            raise

    def get_claim_tier_validation(self, validation_id: str) -> dict | None:
        """Get a specific claim tier validation."""
        try:
            with self.get_session() as session:
                validation = (
                    session.query(ClaimTierValidation)
                    .filter_by(validation_id=validation_id)
                    .first()
                )

                if validation:
                    return {
                        "validation_id": validation.validation_id,
                        "claim_id": validation.claim_id,
                        "episode_id": validation.episode_id,
                        "original_tier": validation.original_tier,
                        "validated_tier": validation.validated_tier,
                        "is_modified": validation.is_modified,
                        "claim_text": validation.claim_text,
                        "claim_type": validation.claim_type,
                        "validated_by_user": validation.validated_by_user,
                        "validated_at": validation.validated_at,
                        "original_scores": validation.original_scores,
                        "model_used": validation.model_used,
                        "evidence_spans": validation.evidence_spans,
                        "validation_session_id": validation.validation_session_id,
                    }
                return None

        except Exception as e:
            logger.error(f"Failed to get claim tier validation {validation_id}: {e}")
            return None

    def get_validations_for_claim(self, claim_id: str) -> list[dict]:
        """Get all validations for a specific claim."""
        try:
            with self.get_session() as session:
                validations = (
                    session.query(ClaimTierValidation)
                    .filter_by(claim_id=claim_id)
                    .order_by(desc(ClaimTierValidation.validated_at))
                    .all()
                )

                return [
                    {
                        "validation_id": v.validation_id,
                        "original_tier": v.original_tier,
                        "validated_tier": v.validated_tier,
                        "is_modified": v.is_modified,
                        "validated_by_user": v.validated_by_user,
                        "validated_at": v.validated_at,
                        "validation_session_id": v.validation_session_id,
                    }
                    for v in validations
                ]

        except Exception as e:
            logger.error(f"Failed to get validations for claim {claim_id}: {e}")
            return []

    def get_validation_session_summary(self, session_id: str) -> dict:
        """Get summary statistics for a validation session."""
        try:
            with self.get_session() as session:
                validations = (
                    session.query(ClaimTierValidation)
                    .filter_by(validation_session_id=session_id)
                    .all()
                )

                if not validations:
                    return {}

                total_validations = len(validations)
                modified_count = sum(1 for v in validations if v.is_modified)
                confirmed_count = total_validations - modified_count

                # Tier-specific statistics
                tier_stats = {}
                for tier in ["A", "B", "C"]:
                    tier_validations = [
                        v for v in validations if v.original_tier == tier
                    ]
                    tier_correct = sum(1 for v in tier_validations if not v.is_modified)
                    tier_stats[f"tier_{tier.lower()}"] = {
                        "total": len(tier_validations),
                        "correct": tier_correct,
                        "accuracy": (
                            tier_correct / len(tier_validations)
                            if tier_validations
                            else 0
                        ),
                    }

                return {
                    "session_id": session_id,
                    "total_validations": total_validations,
                    "confirmed_count": confirmed_count,
                    "modified_count": modified_count,
                    "accuracy_rate": (
                        confirmed_count / total_validations if total_validations else 0
                    ),
                    "tier_statistics": tier_stats,
                    "session_start": min(v.validated_at for v in validations),
                    "session_end": max(v.validated_at for v in validations),
                }

        except Exception as e:
            logger.error(f"Failed to get validation session summary {session_id}: {e}")
            return {}

    def get_claim_validation_analytics(self, days: int = 30) -> dict:
        """Get claim validation analytics for the specified time period."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            with self.get_session() as session:
                validations = (
                    session.query(ClaimTierValidation)
                    .filter(ClaimTierValidation.validated_at >= cutoff_date)
                    .all()
                )

                if not validations:
                    return {"total_validations": 0}

                total_validations = len(validations)
                modified_count = sum(1 for v in validations if v.is_modified)

                # Overall accuracy
                accuracy_rate = (total_validations - modified_count) / total_validations

                # Tier-specific accuracy
                tier_accuracy = {}
                for tier in ["A", "B", "C"]:
                    tier_validations = [
                        v for v in validations if v.original_tier == tier
                    ]
                    if tier_validations:
                        tier_correct = sum(
                            1 for v in tier_validations if not v.is_modified
                        )
                        tier_accuracy[tier] = {
                            "total": len(tier_validations),
                            "correct": tier_correct,
                            "accuracy": tier_correct / len(tier_validations),
                        }

                # Common correction patterns
                correction_patterns = {}
                for v in validations:
                    if v.is_modified:
                        pattern = f"{v.original_tier}_to_{v.validated_tier}"
                        correction_patterns[pattern] = (
                            correction_patterns.get(pattern, 0) + 1
                        )

                # Model performance
                model_performance = {}
                for v in validations:
                    if v.model_used:
                        if v.model_used not in model_performance:
                            model_performance[v.model_used] = {"total": 0, "correct": 0}
                        model_performance[v.model_used]["total"] += 1
                        if not v.is_modified:
                            model_performance[v.model_used]["correct"] += 1

                # Calculate accuracy for each model
                for model_data in model_performance.values():
                    model_data["accuracy"] = model_data["correct"] / model_data["total"]

                return {
                    "total_validations": total_validations,
                    "modified_count": modified_count,
                    "confirmed_count": total_validations - modified_count,
                    "overall_accuracy": accuracy_rate,
                    "tier_accuracy": tier_accuracy,
                    "correction_patterns": correction_patterns,
                    "model_performance": model_performance,
                    "period_days": days,
                }

        except Exception as e:
            logger.error(f"Failed to get claim validation analytics: {e}")
            return {"error": str(e)}

    def export_claim_validation_data(self, output_path: Path, days: int = None) -> bool:
        """Export claim validation data to CSV."""
        try:
            import csv

            with self.get_session() as session:
                query = session.query(ClaimTierValidation)

                if days:
                    cutoff_date = datetime.utcnow() - timedelta(days=days)
                    query = query.filter(
                        ClaimTierValidation.validated_at >= cutoff_date
                    )

                validations = query.order_by(
                    desc(ClaimTierValidation.validated_at)
                ).all()

                with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
                    fieldnames = [
                        "validation_id",
                        "claim_id",
                        "episode_id",
                        "original_tier",
                        "validated_tier",
                        "is_modified",
                        "claim_text",
                        "claim_type",
                        "validated_by_user",
                        "validated_at",
                        "model_used",
                        "validation_session_id",
                    ]

                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()

                    for v in validations:
                        writer.writerow(
                            {
                                "validation_id": v.validation_id,
                                "claim_id": v.claim_id,
                                "episode_id": v.episode_id,
                                "original_tier": v.original_tier,
                                "validated_tier": v.validated_tier,
                                "is_modified": v.is_modified,
                                "claim_text": v.claim_text,
                                "claim_type": v.claim_type,
                                "validated_by_user": v.validated_by_user,
                                "validated_at": (
                                    v.validated_at.isoformat()
                                    if v.validated_at
                                    else None
                                ),
                                "model_used": v.model_used,
                                "validation_session_id": v.validation_session_id,
                            }
                        )

                logger.info(
                    f"Exported {len(validations)} claim validations to {output_path}"
                )
                return True

        except Exception as e:
            logger.error(f"Failed to export claim validation data: {e}")
            return False

    def bulk_insert_json(
        self,
        table_name: str,
        records: list[dict[str, Any]],
        conflict_resolution: str = "REPLACE",
    ) -> int:
        """
        High-performance bulk insert from JSON data.

        This method bypasses ORM for maximum speed while maintaining parameter safety.
        Use this for inserting 100+ records at once.

        WHEN TO USE:
        - Bulk data imports (CSV, API responses)
        - High-volume entity storage
        - Batch processing results

        WHEN NOT TO USE:
        - Single record inserts (use ORM)
        - Need relationship handling (use ORM)
        - Need validation/hooks (use ORM)

        PERFORMANCE:
        - ~80% faster than row-by-row ORM inserts
        - ~20% faster than ORM with bulk_save_objects()
        - Nearly as fast as raw cursor.execute() but safer

        Args:
            table_name: Target table name (must exist in schema)
            records: List of dicts with column: value mappings
                    All records must have same keys (validated from first record)
            conflict_resolution:
                - "REPLACE": Update on conflict (INSERT OR REPLACE)
                - "IGNORE": Skip on conflict (INSERT OR IGNORE)
                - "FAIL": Raise on conflict (INSERT)

        Returns:
            Number of records inserted

        Raises:
            Exception: On SQL errors (logged and re-raised)

        Example:
            >>> claims_data = [
            ...     {"episode_id": "ep1", "claim_id": "c1", "text": "..."},
            ...     {"episode_id": "ep1", "claim_id": "c2", "text": "..."},
            ... ]
            >>> count = db.bulk_insert_json("hce_claims", claims_data)
            >>> print(f"Inserted {count} claims")
        """
        if not records:
            return 0

        try:
            with self.get_session() as session:
                # Extract columns from first record
                columns = list(records[0].keys())
                placeholders = ", ".join([f":{col}" for col in columns])
                columns_str = ", ".join(columns)

                # Build appropriate INSERT statement
                if conflict_resolution == "REPLACE":
                    sql = f"INSERT OR REPLACE INTO {table_name} ({columns_str}) VALUES ({placeholders})"
                elif conflict_resolution == "IGNORE":
                    sql = f"INSERT OR IGNORE INTO {table_name} ({columns_str}) VALUES ({placeholders})"
                else:
                    sql = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"

                # Execute bulk insert
                session.execute(text(sql), records)
                session.commit()

                logger.info(f"Bulk inserted {len(records)} records into {table_name}")
                return len(records)

        except Exception as e:
            logger.error(f"Bulk insert failed for {table_name}: {e}")
            raise

    # =============================================================================
    # QUEUE STAGE STATUS OPERATIONS
    # =============================================================================

    def upsert_stage_status(
        self,
        source_id: str,
        stage: str,
        status: str,
        priority: int = 5,
        progress_percent: float = 0.0,
        assigned_worker: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        Create or update stage status for queue visibility.

        Args:
            source_id: Source ID
            stage: Pipeline stage ('download', 'transcription', 'summarization', 'hce_mining', 'flagship_evaluation')
            status: Status ('pending', 'queued', 'scheduled', 'in_progress', 'completed', 'failed', 'blocked', 'not_applicable', 'skipped')
            priority: Priority 1-10 (lower is higher priority)
            progress_percent: Progress 0-100
            assigned_worker: Worker/account assigned
            metadata: Stage-specific metadata

        Returns:
            True if successful
        """
        import os

        queue_debug = os.getenv("QUEUE_DEBUG", "").lower() in ("1", "true", "yes")

        from sqlalchemy.exc import IntegrityError

        try:
            with self.get_session() as session:
                from .models import MediaSource, SourceStageStatus

                if queue_debug:
                    logger.debug(
                        f"[QUEUE_DB] upsert_stage_status: source_id={source_id}, "
                        f"stage={stage}, status={status}, progress={progress_percent:.1f}%, "
                        f"metadata={metadata}"
                    )

                # Ensure MediaSource exists before creating stage status
                # This prevents foreign key constraint failures
                media_source = (
                    session.query(MediaSource)
                    .filter(MediaSource.source_id == source_id)
                    .first()
                )

                if not media_source:
                    # Create a minimal MediaSource record
                    # Extract URL from metadata if available
                    url = (
                        metadata.get("url", f"youtube://{source_id}")
                        if metadata
                        else f"youtube://{source_id}"
                    )

                    media_source = MediaSource(
                        source_id=source_id,
                        source_type="youtube",  # Default to youtube, can be updated later
                        title=f"Queued: {source_id}",  # Placeholder title
                        url=url,
                    )
                    session.add(media_source)
                    session.flush()  # Ensure it's written before stage status

                    if queue_debug:
                        logger.debug(
                            f"[QUEUE_DB] Created placeholder MediaSource for {source_id}"
                        )

                # Check if stage status record exists
                existing = (
                    session.query(SourceStageStatus)
                    .filter(
                        SourceStageStatus.source_id == source_id,
                        SourceStageStatus.stage == stage,
                    )
                    .first()
                )

                if existing:
                    # Update existing record
                    existing.status = status
                    existing.priority = priority
                    existing.progress_percent = progress_percent
                    existing.assigned_worker = assigned_worker
                    if metadata:
                        existing.metadata_json = metadata

                    # Update timestamps based on status
                    if (
                        status in ("in_progress", "scheduled")
                        and not existing.started_at
                    ):
                        existing.started_at = datetime.utcnow()
                    elif status in ("completed", "failed", "blocked"):
                        existing.completed_at = datetime.utcnow()
                else:
                    # Create new record
                    new_status = SourceStageStatus(
                        source_id=source_id,
                        stage=stage,
                        status=status,
                        priority=priority,
                        progress_percent=progress_percent,
                        assigned_worker=assigned_worker,
                        metadata_json=metadata,
                    )

                    # Set timestamps based on initial status
                    if status in ("in_progress", "scheduled"):
                        new_status.started_at = datetime.utcnow()
                    elif status in ("completed", "failed", "blocked"):
                        new_status.started_at = datetime.utcnow()
                        new_status.completed_at = datetime.utcnow()

                    session.add(new_status)

                try:
                    session.commit()
                except IntegrityError:
                    # Race condition: another transaction inserted the record
                    # Roll back and retry with an update
                    session.rollback()
                    existing = (
                        session.query(SourceStageStatus)
                        .filter(
                            SourceStageStatus.source_id == source_id,
                            SourceStageStatus.stage == stage,
                        )
                        .first()
                    )

                    if existing:
                        # Update the record that was inserted by the other transaction
                        existing.status = status
                        existing.priority = priority
                        existing.progress_percent = progress_percent
                        existing.assigned_worker = assigned_worker
                        if metadata:
                            existing.metadata_json = metadata

                        # Update timestamps based on status
                        if (
                            status in ("in_progress", "scheduled")
                            and not existing.started_at
                        ):
                            existing.started_at = datetime.utcnow()
                        elif status in ("completed", "failed", "blocked"):
                            existing.completed_at = datetime.utcnow()

                        session.commit()
                    else:
                        # This shouldn't happen, but log it if it does
                        logger.warning(
                            f"IntegrityError occurred but no existing record found for "
                            f"{source_id}/{stage}"
                        )
                        return False

                logger.debug(
                    f"Updated stage status: source_id={source_id}, stage={stage}, "
                    f"status={status}, progress={progress_percent:.1f}%"
                )
                return True

        except Exception as e:
            logger.error(f"Failed to upsert stage status for {source_id}/{stage}: {e}")
            return False

    def get_source_stage_statuses(self, source_id: str) -> list[dict[str, Any]]:
        """
        Get all stage statuses for a source.

        Returns:
            List of stage status dicts
        """
        try:
            with self.get_session() as session:
                from .models import SourceStageStatus

                statuses = (
                    session.query(SourceStageStatus)
                    .filter(SourceStageStatus.source_id == source_id)
                    .order_by(SourceStageStatus.stage)
                    .all()
                )

                return [
                    {
                        "source_id": s.source_id,
                        "stage": s.stage,
                        "status": s.status,
                        "priority": s.priority,
                        "created_at": s.created_at,
                        "started_at": s.started_at,
                        "completed_at": s.completed_at,
                        "last_updated": s.last_updated,
                        "progress_percent": s.progress_percent,
                        "assigned_worker": s.assigned_worker,
                        "metadata": s.metadata_json,
                    }
                    for s in statuses
                ]

        except Exception as e:
            logger.error(f"Failed to get stage statuses for {source_id}: {e}")
            return []

    def get_queue_by_stage(
        self,
        stage: str,
        status_filter: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Get queue items for a specific stage.

        Args:
            stage: Pipeline stage to query
            status_filter: Optional list of statuses to include
            limit: Max results
            offset: Pagination offset

        Returns:
            List of queue items with source and status info
        """
        try:
            with self.get_session() as session:
                from .models import MediaSource, SourceStageStatus

                query = (
                    session.query(SourceStageStatus, MediaSource)
                    .join(
                        MediaSource,
                        MediaSource.source_id == SourceStageStatus.source_id,
                    )
                    .filter(SourceStageStatus.stage == stage)
                )

                if status_filter:
                    query = query.filter(SourceStageStatus.status.in_(status_filter))

                results = (
                    query.order_by(
                        SourceStageStatus.priority, SourceStageStatus.created_at
                    )
                    .limit(limit)
                    .offset(offset)
                    .all()
                )

                return [
                    {
                        "source_id": status.source_id,
                        "title": source.title,
                        "url": source.url,
                        "stage": status.stage,
                        "status": status.status,
                        "priority": status.priority,
                        "progress_percent": status.progress_percent,
                        "assigned_worker": status.assigned_worker,
                        "created_at": status.created_at,
                        "started_at": status.started_at,
                        "metadata": status.metadata_json,
                    }
                    for status, source in results
                ]

        except Exception as e:
            logger.error(f"Failed to get queue for stage {stage}: {e}")
            return []

    # ==========================================
    # QUESTIONS SYSTEM METHODS
    # ==========================================

    def create_question(
        self,
        question_text: str,
        question_type: str,
        domain: str | None = None,
        description: str | None = None,
        scope: str | None = None,
        importance_score: float | None = None,
        **kwargs,
    ) -> str:
        """Create a new question in the database.

        Args:
            question_text: The question text (must be unique)
            question_type: Type of question (factual, causal, etc.)
            domain: Optional domain/topic area
            description: Optional detailed description
            scope: Optional scope clarification
            importance_score: Optional importance score (0-1)
            **kwargs: Additional fields (status, user_priority, notes, etc.)

        Returns:
            The generated question_id

        Raises:
            ValueError: If question_text already exists
        """
        try:
            with self.get_session() as session:
                from .models import Question

                # Check for duplicate
                existing = (
                    session.query(Question)
                    .filter_by(question_text=question_text)
                    .first()
                )
                if existing:
                    raise ValueError(
                        f"Question already exists: {existing.question_id}"
                    )

                # Generate ID
                question_id = f"q_{uuid.uuid4().hex[:12]}"

                # Create normalized text for matching
                normalized = self._normalize_question_text(question_text)

                # Create question
                question = Question(
                    question_id=question_id,
                    question_text=question_text,
                    normalized_text=normalized,
                    question_type=question_type,
                    domain=domain,
                    description=description,
                    scope=scope,
                    importance_score=importance_score,
                    **kwargs,
                )

                session.add(question)
                session.commit()

                logger.info(f"Created question {question_id}: {question_text[:60]}")
                return question_id

        except Exception as e:
            logger.error(f"Failed to create question: {e}")
            raise

    def get_question(self, question_id: str) -> dict[str, Any] | None:
        """Get a question by ID.

        Returns:
            Question dict or None if not found
        """
        try:
            with self.get_session() as session:
                from .models import Question

                q = session.query(Question).filter_by(question_id=question_id).first()
                if not q:
                    return None

                return {
                    "question_id": q.question_id,
                    "question_text": q.question_text,
                    "question_type": q.question_type,
                    "domain": q.domain,
                    "description": q.description,
                    "scope": q.scope,
                    "status": q.status,
                    "answer_confidence": q.answer_confidence,
                    "answer_completeness": q.answer_completeness,
                    "has_consensus": q.has_consensus,
                    "importance_score": q.importance_score,
                    "user_priority": q.user_priority,
                    "reviewed": q.reviewed,
                    "notes": q.notes,
                    "created_at": q.created_at,
                    "updated_at": q.updated_at,
                }

        except Exception as e:
            logger.error(f"Failed to get question {question_id}: {e}")
            return None

    def get_questions_by_domain(
        self, domain: str, status_filter: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Get all questions in a domain.

        Args:
            domain: Domain to filter by
            status_filter: Optional list of statuses to include

        Returns:
            List of question dicts
        """
        try:
            with self.get_session() as session:
                from .models import Question

                query = session.query(Question).filter_by(domain=domain)

                if status_filter:
                    query = query.filter(Question.status.in_(status_filter))

                questions = query.order_by(
                    Question.importance_score.desc().nulls_last(),
                    Question.created_at,
                ).all()

                return [
                    {
                        "question_id": q.question_id,
                        "question_text": q.question_text,
                        "question_type": q.question_type,
                        "domain": q.domain,
                        "status": q.status,
                        "importance_score": q.importance_score,
                        "reviewed": q.reviewed,
                    }
                    for q in questions
                ]

        except Exception as e:
            logger.error(f"Failed to get questions for domain {domain}: {e}")
            return []

    def assign_claim_to_question(
        self,
        claim_id: str,
        question_id: str,
        relation_type: str,
        relevance_score: float,
        rationale: str | None = None,
    ) -> bool:
        """Assign a claim to a question with relation type.

        Args:
            claim_id: Claim to assign
            question_id: Question to assign to
            relation_type: How claim relates (answers, supports, etc.)
            relevance_score: Relevance score (0-1)
            rationale: Optional explanation of relationship

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_session() as session:
                from .models import QuestionClaim

                # Check for duplicate assignment
                existing = (
                    session.query(QuestionClaim)
                    .filter_by(claim_id=claim_id, question_id=question_id)
                    .first()
                )

                if existing:
                    # Update existing
                    existing.relation_type = relation_type
                    existing.relevance_score = relevance_score
                    existing.rationale = rationale
                    existing.assigned_at = datetime.utcnow()
                    logger.debug(
                        f"Updated claim-question assignment: "
                        f"{claim_id} -> {question_id}"
                    )
                else:
                    # Create new
                    assignment = QuestionClaim(
                        claim_id=claim_id,
                        question_id=question_id,
                        relation_type=relation_type,
                        relevance_score=relevance_score,
                        rationale=rationale,
                    )
                    session.add(assignment)
                    logger.debug(
                        f"Created claim-question assignment: "
                        f"{claim_id} -> {question_id} ({relation_type})"
                    )

                session.commit()
                return True

        except Exception as e:
            logger.error(f"Failed to assign claim to question: {e}")
            return False

    def get_claims_for_question(
        self, question_id: str, relation_filter: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Get all claims assigned to a question.

        Args:
            question_id: Question to get claims for
            relation_filter: Optional filter by relation types

        Returns:
            List of claim dicts with assignment metadata
        """
        try:
            with self.get_session() as session:
                from .models import Claim, QuestionClaim

                query = (
                    session.query(Claim, QuestionClaim)
                    .join(QuestionClaim, Claim.claim_id == QuestionClaim.claim_id)
                    .filter(QuestionClaim.question_id == question_id)
                )

                if relation_filter:
                    query = query.filter(
                        QuestionClaim.relation_type.in_(relation_filter)
                    )

                results = query.order_by(
                    QuestionClaim.relevance_score.desc()
                ).all()

                return [
                    {
                        "claim_id": claim.claim_id,
                        "claim_text": claim.claim_text,
                        "relation_type": assignment.relation_type,
                        "relevance_score": assignment.relevance_score,
                        "rationale": assignment.rationale,
                        "assigned_at": assignment.assigned_at,
                    }
                    for claim, assignment in results
                ]

        except Exception as e:
            logger.error(f"Failed to get claims for question {question_id}: {e}")
            return []

    def get_questions_for_claim(self, claim_id: str) -> list[dict[str, Any]]:
        """Get all questions a claim is assigned to.

        Args:
            claim_id: Claim to get questions for

        Returns:
            List of question dicts with assignment metadata
        """
        try:
            with self.get_session() as session:
                from .models import Question, QuestionClaim

                results = (
                    session.query(Question, QuestionClaim)
                    .join(
                        QuestionClaim,
                        Question.question_id == QuestionClaim.question_id,
                    )
                    .filter(QuestionClaim.claim_id == claim_id)
                    .order_by(QuestionClaim.relevance_score.desc())
                    .all()
                )

                return [
                    {
                        "question_id": q.question_id,
                        "question_text": q.question_text,
                        "question_type": q.question_type,
                        "relation_type": assignment.relation_type,
                        "relevance_score": assignment.relevance_score,
                    }
                    for q, assignment in results
                ]

        except Exception as e:
            logger.error(f"Failed to get questions for claim {claim_id}: {e}")
            return []

    def get_unreviewed_questions(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get questions pending review.

        Args:
            limit: Maximum number to return

        Returns:
            List of question dicts ordered by importance
        """
        try:
            with self.get_session() as session:
                from .models import Question

                questions = (
                    session.query(Question)
                    .filter_by(reviewed=False)
                    .filter(Question.status != "merged")
                    .order_by(
                        Question.importance_score.desc().nulls_last(),
                        Question.created_at,
                    )
                    .limit(limit)
                    .all()
                )

                return [
                    {
                        "question_id": q.question_id,
                        "question_text": q.question_text,
                        "question_type": q.question_type,
                        "domain": q.domain,
                        "importance_score": q.importance_score,
                        "created_at": q.created_at,
                    }
                    for q in questions
                ]

        except Exception as e:
            logger.error(f"Failed to get unreviewed questions: {e}")
            return []

    def update_question_status(
        self, question_id: str, reviewed: bool = True, **kwargs
    ) -> bool:
        """Update question review status and other fields.

        Args:
            question_id: Question to update
            reviewed: Mark as reviewed
            **kwargs: Additional fields to update (status, user_priority, notes, etc.)

        Returns:
            True if successful
        """
        try:
            with self.get_session() as session:
                from .models import Question

                question = (
                    session.query(Question).filter_by(question_id=question_id).first()
                )

                if not question:
                    logger.warning(f"Question not found: {question_id}")
                    return False

                question.reviewed = reviewed
                question.updated_at = datetime.utcnow()

                for key, value in kwargs.items():
                    if hasattr(question, key):
                        setattr(question, key, value)

                session.commit()
                logger.info(f"Updated question {question_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to update question {question_id}: {e}")
            return False

    def merge_questions(
        self, source_question_id: str, target_question_id: str
    ) -> bool:
        """Merge one question into another.

        Args:
            source_question_id: Question to merge (will be marked as merged)
            target_question_id: Question to merge into (receives all assignments)

        Returns:
            True if successful
        """
        try:
            with self.get_session() as session:
                from .models import Question, QuestionClaim

                # Verify both questions exist
                source = (
                    session.query(Question)
                    .filter_by(question_id=source_question_id)
                    .first()
                )
                target = (
                    session.query(Question)
                    .filter_by(question_id=target_question_id)
                    .first()
                )

                if not source or not target:
                    logger.error("Source or target question not found for merge")
                    return False

                # Migrate claim assignments
                assignments = (
                    session.query(QuestionClaim)
                    .filter_by(question_id=source_question_id)
                    .all()
                )

                for assignment in assignments:
                    # Check if target already has this claim
                    existing = (
                        session.query(QuestionClaim)
                        .filter_by(
                            claim_id=assignment.claim_id,
                            question_id=target_question_id,
                        )
                        .first()
                    )

                    if existing:
                        # Keep higher relevance score
                        if assignment.relevance_score > existing.relevance_score:
                            existing.relevance_score = assignment.relevance_score
                            existing.relation_type = assignment.relation_type
                            existing.rationale = assignment.rationale
                        session.delete(assignment)
                    else:
                        # Move to target
                        assignment.question_id = target_question_id

                # Mark source as merged
                source.status = "merged"
                source.merged_into_question_id = target_question_id
                source.updated_at = datetime.utcnow()

                session.commit()
                logger.info(
                    f"Merged question {source_question_id} into {target_question_id}"
                )
                return True

        except Exception as e:
            logger.error(f"Failed to merge questions: {e}")
            return False

    def _normalize_question_text(self, text: str) -> str:
        """Normalize question text for matching.

        Lowercases, removes punctuation, standardizes whitespace.
        """
        # Lowercase
        text = text.lower()
        # Remove punctuation except spaces
        text = re.sub(r"[^\w\s]", "", text)
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    # =============================================================================
    # EXTRACTION CHECKPOINT OPERATIONS (for auth failure recovery)
    # =============================================================================

    def save_extraction_checkpoint(self, checkpoint: dict[str, Any]) -> bool:
        """
        Save extraction checkpoint for auth failure recovery.
        
        Args:
            checkpoint: Dict with batch_id, last_successful_source_id, 
                       episodes_remaining, auth_failure_reason, etc.
        
        Returns:
            True if successful
        """
        try:
            with self.get_session() as session:
                # Use raw SQL for simplicity - table may not exist in older schemas
                from sqlalchemy import text
                
                # Check if table exists
                result = session.execute(text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='extraction_checkpoints'"
                )).fetchone()
                
                if not result:
                    # Create table if it doesn't exist
                    session.execute(text("""
                        CREATE TABLE IF NOT EXISTS extraction_checkpoints (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            batch_id TEXT UNIQUE NOT NULL,
                            device_id TEXT,
                            last_successful_source_id TEXT,
                            episodes_remaining TEXT,
                            auth_failure_reason TEXT,
                            auth_failure_time TEXT,
                            status TEXT DEFAULT 'paused',
                            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                    session.commit()
                
                # Check if checkpoint already exists
                existing = session.execute(text(
                    "SELECT id FROM extraction_checkpoints WHERE batch_id = :batch_id"
                ), {"batch_id": checkpoint.get("batch_id")}).fetchone()
                
                import json
                episodes_json = json.dumps(checkpoint.get("episodes_remaining", []))
                
                if existing:
                    # Update
                    session.execute(text("""
                        UPDATE extraction_checkpoints SET
                            last_successful_source_id = :last_successful_source_id,
                            episodes_remaining = :episodes_remaining,
                            auth_failure_reason = :auth_failure_reason,
                            auth_failure_time = :auth_failure_time,
                            status = :status,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE batch_id = :batch_id
                    """), {
                        "batch_id": checkpoint.get("batch_id"),
                        "last_successful_source_id": checkpoint.get("last_successful_source_id"),
                        "episodes_remaining": episodes_json,
                        "auth_failure_reason": checkpoint.get("auth_failure_reason"),
                        "auth_failure_time": checkpoint.get("auth_failure_time"),
                        "status": checkpoint.get("status", "paused"),
                    })
                else:
                    # Insert
                    session.execute(text("""
                        INSERT INTO extraction_checkpoints 
                        (batch_id, last_successful_source_id, episodes_remaining, 
                         auth_failure_reason, auth_failure_time, status)
                        VALUES (:batch_id, :last_successful_source_id, :episodes_remaining,
                                :auth_failure_reason, :auth_failure_time, :status)
                    """), {
                        "batch_id": checkpoint.get("batch_id"),
                        "last_successful_source_id": checkpoint.get("last_successful_source_id"),
                        "episodes_remaining": episodes_json,
                        "auth_failure_reason": checkpoint.get("auth_failure_reason"),
                        "auth_failure_time": checkpoint.get("auth_failure_time"),
                        "status": checkpoint.get("status", "paused"),
                    })
                
                session.commit()
                logger.info(f"Saved extraction checkpoint: {checkpoint.get('batch_id')}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to save extraction checkpoint: {e}")
            return False

    def get_extraction_checkpoint(self, batch_id: str | None = None) -> dict | None:
        """
        Get extraction checkpoint for resumption.
        
        Args:
            batch_id: Optional batch_id. If None, returns most recent paused checkpoint.
        
        Returns:
            Checkpoint dict or None
        """
        try:
            with self.get_session() as session:
                from sqlalchemy import text
                
                # Check if table exists
                result = session.execute(text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='extraction_checkpoints'"
                )).fetchone()
                
                if not result:
                    return None
                
                if batch_id:
                    row = session.execute(text(
                        "SELECT * FROM extraction_checkpoints WHERE batch_id = :batch_id"
                    ), {"batch_id": batch_id}).fetchone()
                else:
                    row = session.execute(text(
                        "SELECT * FROM extraction_checkpoints WHERE status = 'paused' ORDER BY created_at DESC LIMIT 1"
                    )).fetchone()
                
                if not row:
                    return None
                
                import json
                
                # Convert row to dict
                return {
                    "batch_id": row.batch_id,
                    "last_successful_source_id": row.last_successful_source_id,
                    "episodes_remaining": json.loads(row.episodes_remaining) if row.episodes_remaining else [],
                    "auth_failure_reason": row.auth_failure_reason,
                    "auth_failure_time": row.auth_failure_time,
                    "status": row.status,
                }
                
        except Exception as e:
            logger.error(f"Failed to get extraction checkpoint: {e}")
            return None

    def update_extraction_checkpoint_status(self, batch_id: str, status: str) -> bool:
        """
        Update checkpoint status.
        
        Args:
            batch_id: Batch ID
            status: New status ('paused', 'resuming', 'completed', 'cancelled')
        
        Returns:
            True if successful
        """
        try:
            with self.get_session() as session:
                from sqlalchemy import text
                
                session.execute(text("""
                    UPDATE extraction_checkpoints 
                    SET status = :status, updated_at = CURRENT_TIMESTAMP
                    WHERE batch_id = :batch_id
                """), {"batch_id": batch_id, "status": status})
                
                session.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to update checkpoint status: {e}")
            return False
