"""
Database service layer for Knowledge System.

Provides high-level CRUD operations, query builders, and transaction management
for the SQLite database with comprehensive video processing tracking.
"""

import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import desc, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from ..logger import get_logger
from .models import (
    BrightDataSession,
    GeneratedFile,
    MOCExtraction,
    ProcessingJob,
    Summary,
    Transcript,
    Video,
    create_all_tables,
    create_database_engine,
)

logger = get_logger(__name__)


class DatabaseService:
    """High-level database service for Knowledge System operations."""

    def __init__(self, database_url: str = "sqlite:///knowledge_system.db"):
        """Initialize database service with connection."""
        self.database_url = database_url
        self.engine = create_database_engine(database_url)
        self.Session = sessionmaker(bind=self.engine)

        # Extract database path for SQLite URLs
        if database_url.startswith("sqlite:///"):
            self.db_path = Path(database_url[10:])  # Remove 'sqlite:///' prefix
        elif database_url.startswith("sqlite://"):
            self.db_path = Path(database_url[9:])  # Remove 'sqlite://' prefix
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
        """Create a new video record."""
        try:
            with self.get_session() as session:
                video = Video(video_id=video_id, title=title, url=url, **metadata)
                session.add(video)
                session.commit()
                logger.info(f"Created video record: {video_id}")
                return video
        except IntegrityError:
            logger.warning(f"Video {video_id} already exists")
            return self.get_video(video_id)
        except Exception as e:
            logger.error(f"Failed to create video {video_id}: {e}")
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
        """Create a new transcript record."""
        try:
            transcript_id = f"{video_id}_{language}_{uuid.uuid4().hex[:8]}"

            with self.get_session() as session:
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
                logger.info(f"Created transcript: {transcript_id}")
                return transcript
        except Exception as e:
            logger.error(f"Failed to create transcript for {video_id}: {e}")
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
