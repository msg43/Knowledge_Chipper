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

from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session, sessionmaker

from ..logger import get_logger
from .models import BrightDataSession, ClaimTierValidation, GeneratedFile
from .models import MediaSource as Video  # Back-compat alias
from .models import (
    MOCExtraction,
    ProcessingJob,
    QualityMetrics,
    QualityRating,
    Summary,
    Transcript,
    create_all_tables,
    create_database_engine,
)

logger = get_logger(__name__)


class DatabaseService:
    """High-level database service for Knowledge System operations."""

    def __init__(self, database_url: str = "sqlite:///knowledge_system.db"):
        """Initialize database service with connection.

        Defaults to a per-user writable SQLite database location to avoid
        permission issues when launching from /Applications.
        """
        # Resolve default/writable database path for SQLite
        resolved_url = database_url
        db_path: Path | None = None

        def _user_data_dir() -> Path:
            if sys.platform == "darwin":
                return (
                    Path.home() / "Library" / "Application Support" / "KnowledgeChipper"
                )
            elif os.name == "nt":
                appdata = os.environ.get(
                    "APPDATA", str(Path.home() / "AppData" / "Roaming")
                )
                return Path(appdata) / "KnowledgeChipper"
            else:
                return Path.home() / ".knowledge_chipper"

        if database_url.startswith("sqlite:///"):
            raw_path = Path(database_url[10:])  # after 'sqlite:///'
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

        logger.info(f"Database service initialized with {database_url}")

    def get_session(self) -> Session:
        """Get a new database session."""
        return self.Session()

    # =============================================================================
    # VIDEO OPERATIONS
    # =============================================================================

    def create_video(
        self, video_id: str, title: str, url: str, **metadata
    ) -> Video | None:
        """Create a new video record or update existing one for re-runs."""
        try:
            with self.get_session() as session:
                # Check for existing video
                existing_video = (
                    session.query(Video).filter(Video.video_id == video_id).first()
                )

                if existing_video:
                    # Update existing video for re-runs
                    logger.info(f"Updating existing video record: {video_id}")

                    # Update core fields
                    existing_video.title = title
                    existing_video.url = url
                    existing_video.processed_at = (
                        datetime.utcnow()
                    )  # Update processing timestamp

                    # Update metadata fields
                    for key, value in metadata.items():
                        if hasattr(existing_video, key):
                            setattr(existing_video, key, value)

                    session.commit()
                    logger.info(f"Updated video record: {video_id}")
                    return existing_video
                else:
                    # Create new video
                    video = Video(video_id=video_id, title=title, url=url, **metadata)
                    session.add(video)
                    session.commit()
                    logger.info(f"Created video record: {video_id}")
                    return video
        except Exception as e:
            logger.error(f"Failed to create/update video {video_id}: {e}")
            return None

    def get_video(self, video_id: str) -> Video | None:
        """Get video by ID."""
        try:
            with self.get_session() as session:
                return session.query(Video).filter(Video.video_id == video_id).first()
        except Exception as e:
            logger.error(f"Failed to get video {video_id}: {e}")
            return None

    def update_video(self, video_id: str, **updates) -> bool:
        """Update video record."""
        try:
            with self.get_session() as session:
                video = session.query(Video).filter(Video.video_id == video_id).first()
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
                    session.query(Video).filter(Video.video_id == video_id).first()
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
    ) -> list[Video]:
        """Search videos with filters."""
        try:
            with self.get_session() as session:
                q = session.query(Video)

                if query:
                    q = q.filter(
                        or_(
                            Video.title.contains(query),
                            Video.description.contains(query),
                        )
                    )

                if uploader:
                    q = q.filter(Video.uploader.contains(uploader))

                if status:
                    q = q.filter(Video.status == status)

                return q.order_by(desc(Video.processed_at)).limit(limit).all()
        except Exception as e:
            logger.error(f"Failed to search videos: {e}")
            return []

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

    # =============================================================================
    # HCE OPERATIONS
    # =============================================================================

    def save_hce_data(self, video_id: str, hce_outputs) -> bool:
        """Save HCE pipeline outputs to database tables."""
        try:
            from .hce_models import (
                Claim,
                Concept,
                Episode,
                EvidenceSpan,
                JargonTerm,
                Person,
                Relation,
            )

            with self.get_session() as session:
                # Create or get episode
                episode = (
                    session.query(Episode).filter(Episode.video_id == video_id).first()
                )
                if not episode:
                    episode = Episode(
                        episode_id=hce_outputs.episode_id,
                        video_id=video_id,
                        title=session.query(Video)
                        .filter(Video.video_id == video_id)
                        .first()
                        .title,
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
                    db_relation = Relation(
                        episode_id=episode.episode_id,
                        source_claim_id=relation.source_claim_id,
                        target_claim_id=relation.target_claim_id,
                        type=relation.type,
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
                total_videos = session.query(Video).count()
                completed_videos = (
                    session.query(Video).filter(Video.status == "completed").count()
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
    # QUALITY RATING OPERATIONS
    # =============================================================================

    def save_quality_rating(
        self,
        content_type: str,
        content_id: str,
        user_rating: float,
        criteria_scores: dict,
        user_feedback: str = "",
        llm_rating: float | None = None,
        is_user_corrected: bool = True,
        model_used: str | None = None,
        prompt_template: str | None = None,
        input_characteristics: dict | None = None,
        rated_by_user: str = "default_user",
    ) -> str:
        """Save a quality rating to the database.

        Args:
            content_type: Type of content ('summary', 'transcript', 'moc_extraction')
            content_id: Unique identifier for the content
            user_rating: User's overall rating (0.0-1.0)
            criteria_scores: Dictionary of criteria scores
            user_feedback: Optional text feedback
            llm_rating: Original LLM rating (optional)
            is_user_corrected: Whether this is a user correction
            model_used: Model that generated the content
            prompt_template: Template used for generation
            input_characteristics: Input metadata
            rated_by_user: User identifier

        Returns:
            Rating ID of the saved rating
        """
        try:
            with self.get_session() as session:
                # Generate unique rating ID
                rating_id = f"rating_{content_type}_{content_id}_{int(datetime.now().timestamp())}"

                # Create rating record
                rating = QualityRating(
                    rating_id=rating_id,
                    content_type=content_type,
                    content_id=content_id,
                    llm_rating=llm_rating,
                    user_rating=user_rating,
                    is_user_corrected=is_user_corrected,
                    criteria_scores=criteria_scores,
                    user_feedback=user_feedback,
                    rating_reason="",  # Could be added as parameter
                    rated_by_user=rated_by_user,
                    model_used=model_used,
                    prompt_template=prompt_template,
                    input_characteristics=input_characteristics or {},
                )

                session.add(rating)
                session.commit()

                # Update aggregated metrics
                self._update_quality_metrics(
                    session, content_type, model_used or "unknown"
                )

                logger.info(f"Saved quality rating: {rating_id}")
                return rating_id

        except Exception as e:
            logger.error(f"Failed to save quality rating: {e}")
            raise

    def get_quality_rating(self, rating_id: str) -> QualityRating | None:
        """Get a quality rating by ID."""
        try:
            with self.get_session() as session:
                return (
                    session.query(QualityRating)
                    .filter(QualityRating.rating_id == rating_id)
                    .first()
                )
        except Exception as e:
            logger.error(f"Failed to get quality rating {rating_id}: {e}")
            return None

    def get_ratings_for_content(
        self, content_type: str, content_id: str
    ) -> list[QualityRating]:
        """Get all ratings for specific content."""
        try:
            with self.get_session() as session:
                return (
                    session.query(QualityRating)
                    .filter(
                        QualityRating.content_type == content_type,
                        QualityRating.content_id == content_id,
                    )
                    .order_by(desc(QualityRating.rated_at))
                    .all()
                )
        except Exception as e:
            logger.error(f"Failed to get ratings for {content_type} {content_id}: {e}")
            return []

    def get_quality_statistics(self) -> dict[str, Any]:
        """Get overall quality rating statistics."""
        try:
            with self.get_session() as session:
                # Total ratings
                total_ratings = session.query(QualityRating).count()

                # User corrections
                user_corrections = (
                    session.query(QualityRating)
                    .filter(QualityRating.is_user_corrected.is_(True))
                    .count()
                )

                # Calculate average drift where both ratings exist
                ratings_with_both = (
                    session.query(QualityRating)
                    .filter(
                        QualityRating.llm_rating.isnot(None),
                        QualityRating.user_rating.isnot(None),
                    )
                    .all()
                )

                if ratings_with_both:
                    drifts = [
                        abs(r.user_rating - r.llm_rating) for r in ratings_with_both
                    ]
                    avg_drift = sum(drifts) / len(drifts)
                else:
                    avg_drift = 0.0

                # Average ratings
                avg_user_rating = (
                    session.query(func.avg(QualityRating.user_rating))
                    .filter(QualityRating.user_rating.isnot(None))
                    .scalar()
                    or 0.0
                )

                avg_llm_rating = (
                    session.query(func.avg(QualityRating.llm_rating))
                    .filter(QualityRating.llm_rating.isnot(None))
                    .scalar()
                    or 0.0
                )

                return {
                    "total_ratings": total_ratings,
                    "user_corrections": user_corrections,
                    "correction_percentage": (
                        (user_corrections / total_ratings * 100)
                        if total_ratings > 0
                        else 0
                    ),
                    "avg_drift": avg_drift,
                    "avg_user_rating": avg_user_rating,
                    "avg_llm_rating": avg_llm_rating,
                    "ratings_with_both": len(ratings_with_both),
                }

        except Exception as e:
            logger.error(f"Failed to get quality statistics: {e}")
            return {
                "total_ratings": 0,
                "user_corrections": 0,
                "correction_percentage": 0,
                "avg_drift": 0.0,
                "avg_user_rating": 0.0,
                "avg_llm_rating": 0.0,
                "ratings_with_both": 0,
            }

    def get_model_performance_metrics(self) -> list[dict[str, Any]]:
        """Get performance metrics by model and content type."""
        try:
            with self.get_session() as session:
                # Query ratings grouped by model and content type
                results = (
                    session.query(
                        QualityRating.model_used,
                        QualityRating.content_type,
                        func.count(QualityRating.rating_id).label("total_ratings"),
                        func.count(QualityRating.user_rating).label("user_ratings"),
                        func.avg(QualityRating.llm_rating).label("avg_llm_rating"),
                        func.avg(QualityRating.user_rating).label("avg_user_rating"),
                    )
                    .filter(QualityRating.model_used.isnot(None))
                    .group_by(QualityRating.model_used, QualityRating.content_type)
                    .all()
                )

                metrics = []
                for result in results:
                    avg_llm = result.avg_llm_rating or 0.0
                    avg_user = result.avg_user_rating or 0.0
                    drift = (
                        abs(avg_user - avg_llm) if avg_llm > 0 and avg_user > 0 else 0.0
                    )

                    metrics.append(
                        {
                            "model": result.model_used or "unknown",
                            "content_type": result.content_type,
                            "total_ratings": result.total_ratings,
                            "user_ratings": result.user_ratings,
                            "avg_llm_rating": avg_llm,
                            "avg_user_rating": avg_user,
                            "drift": drift,
                            "sample_size": result.user_ratings,
                        }
                    )

                return metrics

        except Exception as e:
            logger.error(f"Failed to get model performance metrics: {e}")
            return []

    def get_quality_trends(self, days: int = 30) -> dict[str, Any]:
        """Get quality trends over time."""
        try:
            with self.get_session() as session:
                # Get ratings from the last N days
                cutoff_date = datetime.now() - timedelta(days=days)

                ratings = (
                    session.query(QualityRating)
                    .filter(QualityRating.rated_at >= cutoff_date)
                    .order_by(QualityRating.rated_at)
                    .all()
                )

                # Group by day
                daily_stats = {}
                for rating in ratings:
                    day = rating.rated_at.date()
                    if day not in daily_stats:
                        daily_stats[day] = {
                            "count": 0,
                            "user_ratings": [],
                            "llm_ratings": [],
                            "drifts": [],
                        }

                    daily_stats[day]["count"] += 1
                    if rating.user_rating is not None:
                        daily_stats[day]["user_ratings"].append(rating.user_rating)
                    if rating.llm_rating is not None:
                        daily_stats[day]["llm_ratings"].append(rating.llm_rating)
                    if rating.user_rating is not None and rating.llm_rating is not None:
                        daily_stats[day]["drifts"].append(
                            abs(rating.user_rating - rating.llm_rating)
                        )

                # Calculate daily averages
                trends = []
                for day, stats in sorted(daily_stats.items()):
                    avg_user = (
                        sum(stats["user_ratings"]) / len(stats["user_ratings"])
                        if stats["user_ratings"]
                        else 0
                    )
                    avg_llm = (
                        sum(stats["llm_ratings"]) / len(stats["llm_ratings"])
                        if stats["llm_ratings"]
                        else 0
                    )
                    avg_drift = (
                        sum(stats["drifts"]) / len(stats["drifts"])
                        if stats["drifts"]
                        else 0
                    )

                    trends.append(
                        {
                            "date": day.isoformat(),
                            "count": stats["count"],
                            "avg_user_rating": avg_user,
                            "avg_llm_rating": avg_llm,
                            "avg_drift": avg_drift,
                        }
                    )

                return {
                    "period_days": days,
                    "total_ratings": len(ratings),
                    "daily_trends": trends,
                }

        except Exception as e:
            logger.error(f"Failed to get quality trends: {e}")
            return {"period_days": days, "total_ratings": 0, "daily_trends": []}

    def export_quality_data(self, format: str = "dict") -> list[dict[str, Any]] | str:
        """Export quality rating data for analysis."""
        try:
            with self.get_session() as session:
                ratings = (
                    session.query(QualityRating)
                    .order_by(desc(QualityRating.rated_at))
                    .all()
                )

                data = []
                for rating in ratings:
                    data.append(
                        {
                            "rating_id": rating.rating_id,
                            "content_type": rating.content_type,
                            "content_id": rating.content_id,
                            "llm_rating": rating.llm_rating,
                            "user_rating": rating.user_rating,
                            "is_user_corrected": rating.is_user_corrected,
                            "criteria_scores": rating.criteria_scores,
                            "user_feedback": rating.user_feedback,
                            "rated_by_user": rating.rated_by_user,
                            "rated_at": (
                                rating.rated_at.isoformat() if rating.rated_at else None
                            ),
                            "model_used": rating.model_used,
                            "prompt_template": rating.prompt_template,
                            "input_characteristics": rating.input_characteristics,
                        }
                    )

                if format == "csv":
                    import csv
                    import io

                    output = io.StringIO()
                    if data:
                        writer = csv.DictWriter(output, fieldnames=data[0].keys())
                        writer.writeheader()
                        writer.writerows(data)
                    return output.getvalue()

                return data

        except Exception as e:
            logger.error(f"Failed to export quality data: {e}")
            return [] if format == "dict" else ""

    def _update_quality_metrics(
        self, session: Session, content_type: str, model_name: str
    ):
        """Update aggregated quality metrics for a model/content type combination."""
        try:
            # Calculate metrics for this model/content type
            ratings = (
                session.query(QualityRating)
                .filter(
                    QualityRating.content_type == content_type,
                    QualityRating.model_used == model_name,
                )
                .all()
            )

            if not ratings:
                return

            # Calculate aggregated statistics
            total_ratings = len(ratings)
            user_corrected_count = sum(1 for r in ratings if r.is_user_corrected)

            user_ratings = [r.user_rating for r in ratings if r.user_rating is not None]
            llm_ratings = [r.llm_rating for r in ratings if r.llm_rating is not None]

            avg_user_rating = (
                sum(user_ratings) / len(user_ratings) if user_ratings else None
            )
            avg_llm_rating = (
                sum(llm_ratings) / len(llm_ratings) if llm_ratings else None
            )

            # Calculate drift for ratings that have both
            drifts = []
            for rating in ratings:
                if rating.user_rating is not None and rating.llm_rating is not None:
                    drifts.append(abs(rating.user_rating - rating.llm_rating))

            rating_drift = sum(drifts) / len(drifts) if drifts else None

            # Calculate criteria performance
            criteria_performance = {}
            for rating in ratings:
                if rating.criteria_scores:
                    for criterion, score in rating.criteria_scores.items():
                        if criterion not in criteria_performance:
                            criteria_performance[criterion] = []
                        criteria_performance[criterion].append(score)

            # Average criteria scores
            for criterion in criteria_performance:
                scores = criteria_performance[criterion]
                criteria_performance[criterion] = sum(scores) / len(scores)

            # Create or update metrics record
            metric_id = f"metrics_{model_name}_{content_type}"

            existing_metric = (
                session.query(QualityMetrics)
                .filter(QualityMetrics.metric_id == metric_id)
                .first()
            )

            if existing_metric:
                # Update existing
                existing_metric.total_ratings = total_ratings
                existing_metric.user_corrected_count = user_corrected_count
                existing_metric.avg_llm_rating = avg_llm_rating
                existing_metric.avg_user_rating = avg_user_rating
                existing_metric.rating_drift = rating_drift
                existing_metric.criteria_performance = criteria_performance
                existing_metric.last_updated = datetime.now()
            else:
                # Create new
                metric = QualityMetrics(
                    metric_id=metric_id,
                    model_name=model_name,
                    content_type=content_type,
                    total_ratings=total_ratings,
                    user_corrected_count=user_corrected_count,
                    avg_llm_rating=avg_llm_rating,
                    avg_user_rating=avg_user_rating,
                    rating_drift=rating_drift,
                    criteria_performance=criteria_performance,
                    period_start=min(r.rated_at for r in ratings if r.rated_at),
                    period_end=max(r.rated_at for r in ratings if r.rated_at),
                )
                session.add(metric)

            session.commit()

        except Exception as e:
            logger.error(f"Failed to update quality metrics: {e}")

    def delete_quality_rating(self, rating_id: str) -> bool:
        """Delete a quality rating."""
        try:
            with self.get_session() as session:
                rating = (
                    session.query(QualityRating)
                    .filter(QualityRating.rating_id == rating_id)
                    .first()
                )

                if rating:
                    session.delete(rating)
                    session.commit()
                    logger.info(f"Deleted quality rating: {rating_id}")
                    return True

                return False

        except Exception as e:
            logger.error(f"Failed to delete quality rating {rating_id}: {e}")
            return False

    # Claim Tier Validation Methods

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
