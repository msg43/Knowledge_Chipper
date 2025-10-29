"""
Database service layer for Knowledge System.

Provides high-level CRUD operations, query builders, and transaction management
for the SQLite database with comprehensive video processing tracking.
"""

import os
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import desc, func, or_, text
from sqlalchemy.orm import Session, sessionmaker

from ..logger import get_logger
from .models import (
    BrightDataSession,
    Claim,
    ClaimRelation,
    ClaimTierValidation,
    Concept,
    Episode,
    EvidenceSpan,
    GeneratedFile,
    JargonTerm,
    MediaSource,
    MOCExtraction,
    Person,
    ProcessingJob,
    QualityMetrics,
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

        logger.info(f"Database service initialized with {self.database_url}")

    def get_session(self) -> Session:
        """Get a new database session."""
        return self.Session()

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

    # =============================================================================
    # VIDEO OPERATIONS
    # =============================================================================

    def create_video(
        self, video_id: str, title: str, url: str, **metadata
    ) -> MediaSource | None:
        """Create a new video record or update existing one for re-runs."""
        try:
            with self.get_session() as session:
                # Check for existing video using claim-centric schema (source_id)
                existing_video = (
                    session.query(MediaSource)
                    .filter(MediaSource.source_id == video_id)
                    .first()
                )

                if existing_video:
                    # Update existing video for re-runs
                    logger.info(f"Updating existing video record: {video_id}")

                    # Update core fields
                    existing_video.title = title
                    existing_video.url = url
                    existing_video.processed_at = datetime.utcnow()

                    # Update metadata fields
                    for key, value in metadata.items():
                        if hasattr(existing_video, key):
                            setattr(existing_video, key, value)

                    session.commit()
                    logger.info(f"Updated video record: {video_id}")
                    return existing_video
                else:
                    # Create new video with claim-centric schema
                    video = MediaSource(
                        source_id=video_id, title=title, url=url, **metadata
                    )
                    session.add(video)
                    session.commit()
                    logger.info(f"Created video record: {video_id}")
                    return video
        except Exception as e:
            logger.error(f"Failed to create/update video {video_id}: {e}")
            return None

    def get_video(self, video_id: str) -> MediaSource | None:
        """Get video by ID (using claim-centric schema with source_id)."""
        try:
            with self.get_session() as session:
                # Use claim_models MediaSource (has source_id)
                video = (
                    session.query(MediaSource)
                    .filter(MediaSource.source_id == video_id)
                    .first()
                )
                return video
        except Exception as e:
            logger.error(f"Failed to get video {video_id}: {e}")
            return None

    def update_video(self, video_id: str, **updates) -> bool:
        """Update video record."""
        try:
            with self.get_session() as session:
                video = (
                    session.query(MediaSource)
                    .filter(MediaSource.source_id == video_id)
                    .first()
                )
                if not video:
                    return False

                for key, value in updates.items():
                    if hasattr(video, key):
                        setattr(video, key, value)

                session.commit()
                logger.info(f"Updated video {video_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to update video {video_id}: {e}")
            return False

    def video_exists(self, video_id: str) -> bool:
        """Check if video exists in database."""
        try:
            with self.get_session() as session:
                return (
                    session.query(MediaSource)
                    .filter(MediaSource.source_id == video_id)
                    .first()
                    is not None
                )
        except Exception as e:
            logger.error(f"Failed to check video existence {video_id}: {e}")
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
        video_id: str,
        audio_file_path: str | Path | None,
        audio_downloaded: bool,
        audio_file_size_bytes: int | None = None,
        audio_format: str | None = None,
    ) -> bool:
        """Update audio download status for a video."""
        try:
            with self.get_session() as session:
                video = (
                    session.query(MediaSource)
                    .filter(MediaSource.source_id == video_id)
                    .first()
                )
                if not video:
                    logger.warning(
                        f"Cannot update audio status: video {video_id} not found"
                    )
                    return False

                video.audio_file_path = (
                    str(audio_file_path) if audio_file_path else None
                )
                video.audio_downloaded = audio_downloaded
                video.audio_file_size_bytes = audio_file_size_bytes
                video.audio_format = audio_format

                # Clear audio retry flag if successful
                if audio_downloaded:
                    video.needs_audio_retry = False

                session.commit()
                logger.debug(
                    f"Updated audio status for {video_id}: downloaded={audio_downloaded}"
                )
                return True
        except Exception as e:
            logger.error(f"Failed to update audio status for {video_id}: {e}")
            return False

    def update_metadata_status(self, video_id: str, metadata_complete: bool) -> bool:
        """Update metadata completion status for a video."""
        try:
            with self.get_session() as session:
                video = (
                    session.query(MediaSource)
                    .filter(MediaSource.source_id == video_id)
                    .first()
                )
                if not video:
                    logger.warning(
                        f"Cannot update metadata status: video {video_id} not found"
                    )
                    return False

                video.metadata_complete = metadata_complete

                # Clear metadata retry flag if successful
                if metadata_complete:
                    video.needs_metadata_retry = False

                session.commit()
                logger.debug(
                    f"Updated metadata status for {video_id}: complete={metadata_complete}"
                )
                return True
        except Exception as e:
            logger.error(f"Failed to update metadata status for {video_id}: {e}")
            return False

    def mark_for_retry(
        self,
        video_id: str,
        needs_metadata_retry: bool = False,
        needs_audio_retry: bool = False,
        failure_reason: str | None = None,
    ) -> bool:
        """Mark a video for retry (metadata, audio, or both)."""
        try:
            with self.get_session() as session:
                video = (
                    session.query(MediaSource)
                    .filter(MediaSource.source_id == video_id)
                    .first()
                )
                if not video:
                    logger.warning(f"Cannot mark for retry: video {video_id} not found")
                    return False

                video.needs_metadata_retry = needs_metadata_retry
                video.needs_audio_retry = needs_audio_retry
                video.retry_count += 1
                video.last_retry_at = datetime.utcnow()

                if failure_reason:
                    video.failure_reason = failure_reason

                # Check if max retries exceeded (3 attempts)
                if video.retry_count >= 3:
                    video.max_retries_exceeded = True
                    video.status = "failed"
                    logger.warning(f"Video {video_id} exceeded max retries (3)")

                session.commit()
                logger.info(
                    f"Marked {video_id} for retry (attempt {video.retry_count}): "
                    f"metadata={needs_metadata_retry}, audio={needs_audio_retry}"
                )
                return True
        except Exception as e:
            logger.error(f"Failed to mark {video_id} for retry: {e}")
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

    def is_video_complete(self, video_id: str) -> bool:
        """Check if video has both audio and metadata complete."""
        try:
            with self.get_session() as session:
                video = (
                    session.query(MediaSource)
                    .filter(MediaSource.source_id == video_id)
                    .first()
                )
                if not video:
                    return False
                return video.audio_downloaded and video.metadata_complete
        except Exception as e:
            logger.error(f"Failed to check if video {video_id} is complete: {e}")
            return False

    def validate_audio_file_exists(self, video_id: str) -> bool:
        """Validate that the audio file path in database actually exists on disk."""
        try:
            with self.get_session() as session:
                video = (
                    session.query(MediaSource)
                    .filter(MediaSource.source_id == video_id)
                    .first()
                )
                if not video or not video.audio_file_path:
                    return False

                audio_path = Path(video.audio_file_path)
                exists = audio_path.exists()

                # If file doesn't exist but database says it does, mark for retry
                if not exists and video.audio_downloaded:
                    logger.warning(
                        f"Audio file missing for {video_id}: {video.audio_file_path}"
                    )
                    video.audio_downloaded = False
                    video.needs_audio_retry = True
                    session.commit()

                return exists
        except Exception as e:
            logger.error(f"Failed to validate audio file for {video_id}: {e}")
            return False

    # =============================================================================
    # TRANSCRIPT OPERATIONS
    # =============================================================================

    def create_transcript(
        self,
        video_id: str,
        language: str,
        is_manual: bool,
        transcript_text: str,
        transcript_segments: list[dict[str, Any]],
        **metadata,
    ) -> Transcript | None:
        """Create a new transcript record or update existing one for re-runs."""
        try:
            with self.get_session() as session:
                # Check for existing transcript for this video_id and language
                existing_transcript = (
                    session.query(Transcript)
                    .filter(
                        Transcript.video_id == video_id,
                        Transcript.language == language,
                    )
                    .order_by(desc(Transcript.created_at))
                    .first()
                )

                if existing_transcript:
                    # Update existing transcript for re-runs
                    logger.info(
                        f"Updating existing transcript for {video_id} (language: {language})"
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
                    transcript_id = f"{video_id}_{language}_{uuid.uuid4().hex[:8]}"

                    transcript = Transcript(
                        transcript_id=transcript_id,
                        video_id=video_id,
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
            logger.error(f"Failed to create/update transcript for {video_id}: {e}")
            return None

    def get_transcripts_for_video(self, video_id: str) -> list[Transcript]:
        """Get all transcripts for a video."""
        try:
            with self.get_session() as session:
                return (
                    session.query(Transcript)
                    .filter(Transcript.video_id == video_id)
                    .order_by(desc(Transcript.created_at))
                    .all()
                )
        except Exception as e:
            logger.error(f"Failed to get transcripts for {video_id}: {e}")
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
                video = (
                    session.query(MediaSource)
                    .filter(MediaSource.source_id == transcript.video_id)
                    .first()
                )

                video_metadata = None
                if video:
                    video_metadata = {
                        "video_id": video.source_id,
                        "title": video.title,
                        "url": video.url,
                        "uploader": getattr(video, "uploader", None),
                        "upload_date": getattr(video, "upload_date", None),
                        "duration": getattr(video, "duration_seconds", None),
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

    def create_summary(
        self,
        video_id: str,
        summary_text: str,
        llm_provider: str,
        llm_model: str,
        transcript_id: str | None = None,
        **metadata,
    ) -> Summary | None:
        """Create a new summary record."""
        try:
            summary_id = f"{video_id}_{llm_model}_{uuid.uuid4().hex[:8]}"

            with self.get_session() as session:
                summary = Summary(
                    summary_id=summary_id,
                    video_id=video_id,
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
                return summary
        except Exception as e:
            logger.error(f"Failed to create summary for {video_id}: {e}")
            return None

    def get_summaries_for_video(self, video_id: str) -> list[Summary]:
        """Get all summaries for a video."""
        try:
            with self.get_session() as session:
                return (
                    session.query(Summary)
                    .filter(Summary.video_id == video_id)
                    .order_by(desc(Summary.created_at))
                    .all()
                )
        except Exception as e:
            logger.error(f"Failed to get summaries for {video_id}: {e}")
            return []

    def get_latest_summary(self, video_id: str) -> Summary | None:
        """Get the most recent summary for a video."""
        try:
            with self.get_session() as session:
                return (
                    session.query(Summary)
                    .filter(Summary.video_id == video_id)
                    .order_by(desc(Summary.created_at))
                    .first()
                )
        except Exception as e:
            logger.error(f"Failed to get latest summary for {video_id}: {e}")
            return None

    # =============================================================================
    # HCE OPERATIONS
    # =============================================================================

    def save_hce_data(self, video_id: str, hce_outputs) -> bool:
        """Save HCE pipeline outputs to database tables."""
        try:
            with self.get_session() as session:
                # Create or get episode
                episode = (
                    session.query(Episode).filter(Episode.source_id == video_id).first()
                )
                if not episode:
                    # Create new episode with claim-centric schema
                    video = self.get_video(video_id)
                    episode = Episode(
                        episode_id=hce_outputs.episode_id,
                        source_id=video_id,
                        title=video.title if video else hce_outputs.episode_id,
                    )
                    session.add(episode)

                # Save claims
                for claim in hce_outputs.claims:
                    db_claim = Claim(
                        episode_id=episode.episode_id,
                        claim_id=claim.claim_id,
                        canonical=claim.canonical,
                        claim_type=claim.claim_type,
                        tier=claim.tier,
                        scores_json=claim.scores,
                    )
                    session.add(db_claim)

                    # Save evidence spans
                    for i, evidence in enumerate(claim.evidence):
                        span = EvidenceSpan(
                            episode_id=episode.episode_id,
                            claim_id=claim.claim_id,
                            seq=i,
                            t0=evidence.t0,
                            t1=evidence.t1,
                            quote=evidence.quote,
                            segment_id=evidence.segment_id,
                        )
                        session.add(span)

                # Save relations
                for relation in hce_outputs.relations:
                    db_relation = ClaimRelation(
                        source_claim_id=relation.source_claim_id,
                        target_claim_id=relation.target_claim_id,
                        relation_type=relation.type,
                        strength=relation.strength,
                        rationale=relation.rationale,
                    )
                    session.add(db_relation)

                # Save people
                for person in hce_outputs.people:
                    db_person = Person(
                        episode_id=episode.episode_id,
                        mention_id=person.mention_id,
                        span_segment_id=person.span_segment_id,
                        t0=person.t0,
                        t1=person.t1,
                        surface=person.surface,
                        normalized=person.normalized,
                        entity_type=person.entity_type,
                        external_ids_json=person.external_ids,
                        confidence=person.confidence,
                    )
                    session.add(db_person)

                # Save concepts
                for concept in hce_outputs.concepts:
                    db_concept = Concept(
                        episode_id=episode.episode_id,
                        model_id=concept.model_id,
                        name=concept.name,
                        definition=concept.definition,
                        first_mention_ts=concept.first_mention_ts,
                        aliases_json=concept.aliases,
                        evidence_json=[e.model_dump() for e in concept.evidence_spans],
                    )
                    session.add(db_concept)

                # Save jargon
                for jargon in hce_outputs.jargon:
                    db_jargon = JargonTerm(
                        episode_id=episode.episode_id,
                        term_id=jargon.term_id,
                        term=jargon.term,
                        category=jargon.category,
                        definition=jargon.definition,
                        evidence_json=[e.model_dump() for e in jargon.evidence_spans],
                    )
                    session.add(db_jargon)

                # Update FTS tables
                session.execute(
                    """INSERT INTO claims_fts (episode_id, claim_id, canonical, claim_type)
                       SELECT episode_id, claim_id, canonical, claim_type FROM claims
                       WHERE episode_id = :episode_id""",
                    {"episode_id": episode.episode_id},
                )

                session.commit()
                logger.info(f"Saved HCE data for episode {episode.episode_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to save HCE data: {e}")
            return False

    # =============================================================================
    # MOC OPERATIONS
    # =============================================================================

    def create_moc_extraction(
        self,
        video_id: str,
        people: list[dict] | None = None,
        tags: list[dict] | None = None,
        mental_models: list[dict] | None = None,
        jargon: list[dict] | None = None,
        beliefs: list[dict] | None = None,
        **metadata,
    ) -> MOCExtraction | None:
        """Create a new MOC extraction record."""
        try:
            moc_id = f"{video_id}_moc_{uuid.uuid4().hex[:8]}"

            with self.get_session() as session:
                moc = MOCExtraction(
                    moc_id=moc_id,
                    video_id=video_id,
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
            logger.error(f"Failed to create MOC extraction for {video_id}: {e}")
            return None

    # =============================================================================
    # BRIGHT DATA SESSION OPERATIONS
    # =============================================================================

    def create_bright_data_session(
        self, session_id: str, video_id: str, session_type: str, **metadata
    ) -> BrightDataSession | None:
        """Create a new Bright Data session record."""
        try:
            with self.get_session() as session:
                bd_session = BrightDataSession(
                    session_id=session_id,
                    video_id=video_id,
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
        video_id: str,
        file_path: str,
        file_type: str,
        file_format: str,
        **metadata,
    ) -> GeneratedFile | None:
        """Track a generated output file."""
        try:
            file_id = f"{video_id}_{file_type}_{uuid.uuid4().hex[:8]}"

            with self.get_session() as session:
                file_size = 0
                if Path(file_path).exists():
                    file_size = Path(file_path).stat().st_size

                generated_file = GeneratedFile(
                    file_id=file_id,
                    video_id=video_id,
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
                    "CREATE INDEX IF NOT EXISTS idx_transcripts_video_id ON transcripts(video_id)",
                    "CREATE INDEX IF NOT EXISTS idx_transcripts_created_at ON transcripts(created_at)",
                    # Summary table indexes
                    "CREATE INDEX IF NOT EXISTS idx_summaries_video_id ON summaries(video_id)",
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
                    "CREATE INDEX IF NOT EXISTS idx_claims_video_id ON claims(video_id)",
                    "CREATE INDEX IF NOT EXISTS idx_claims_tier ON claims(tier)",
                    "CREATE INDEX IF NOT EXISTS idx_claims_claim_type ON claims(claim_type)",
                    "CREATE INDEX IF NOT EXISTS idx_people_video_id ON people(video_id)",
                    "CREATE INDEX IF NOT EXISTS idx_concepts_video_id ON concepts(video_id)",
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
