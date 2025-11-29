"""
Queue Snapshot Service

Provides unified view of pipeline status by composing data from multiple sources.
"""

import json
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from ..database.models import (
    MediaSource,
    ProcessingJob,
    SourceStageStatus,
    Summary,
    Transcript,
)
from ..database.service import DatabaseService
from ..logger import get_logger

logger = get_logger(__name__)


class QueueSnapshot:
    """Represents a point-in-time view of an item in the processing queue."""

    def __init__(self, source_id: str, source: MediaSource):
        self.source_id = source_id
        self.source = source
        self.title = source.title
        self.url = source.url
        self.created_at = source.created_at

        # Stage statuses keyed by stage name
        self.stage_statuses: dict[str, SourceStageStatus] = {}

        # Derived fields
        self.current_stage: str | None = None
        self.overall_status: str = "pending"
        self.elapsed_time: timedelta | None = None
        self.eta: datetime | None = None
        self.retry_count: int = 0

    def add_stage_status(self, stage_status: SourceStageStatus):
        """Add a stage status to this snapshot."""
        self.stage_statuses[stage_status.stage] = stage_status
        self._update_derived_fields()

    def _update_derived_fields(self):
        """Update derived fields based on stage statuses."""
        # Determine current stage (first non-completed stage in order)
        stage_order = [
            "download",
            "transcription",
            "summarization",
            "hce_mining",
            "flagship_evaluation",
        ]

        for stage in stage_order:
            if stage in self.stage_statuses:
                status = self.stage_statuses[stage]
                if status.status not in ("completed", "not_applicable", "skipped"):
                    self.current_stage = stage
                    self.overall_status = status.status

                    # Calculate elapsed time
                    if status.started_at:
                        self.elapsed_time = datetime.utcnow() - status.started_at

                    # Get retry count from metadata
                    if status.metadata_json:
                        self.retry_count = status.metadata_json.get("retry_count", 0)
                    break
        else:
            # All stages completed or not applicable
            self.current_stage = None
            self.overall_status = "completed"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "source_id": self.source_id,
            "title": self.title,
            "url": self.url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "current_stage": self.current_stage,
            "overall_status": self.overall_status,
            "elapsed_time": str(self.elapsed_time) if self.elapsed_time else None,
            "eta": self.eta.isoformat() if self.eta else None,
            "retry_count": self.retry_count,
            "stages": {
                stage: {
                    "status": status.status,
                    "progress_percent": status.progress_percent,
                    "started_at": status.started_at.isoformat()
                    if status.started_at
                    else None,
                    "completed_at": status.completed_at.isoformat()
                    if status.completed_at
                    else None,
                    "assigned_worker": status.assigned_worker,
                    "metadata": status.metadata_json,
                }
                for stage, status in self.stage_statuses.items()
            },
        }


class QueueSnapshotService:
    """
    Service that composes queue data from multiple sources.

    Provides filtering, sorting, pagination, and caching for efficient access.
    """

    def __init__(self, db_service: DatabaseService | None = None):
        self.db_service = db_service or DatabaseService()
        self._cache: dict[str, Any] = {}
        self._cache_timestamp: float = 0
        self._cache_ttl: float = 2.0  # 2 second cache TTL

    def get_full_queue(
        self,
        status_filter: list[str] | None = None,
        stage_filter: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "created_at",
        ascending: bool = True,
    ) -> tuple[list[QueueSnapshot], int]:
        """
        Get full queue with filtering and pagination.

        Args:
            status_filter: Filter by status values
            stage_filter: Filter by stage names
            limit: Max results to return
            offset: Pagination offset
            sort_by: Field to sort by
            ascending: Sort order

        Returns:
            (snapshots, total_count)
        """
        # Check cache
        cache_key = f"full_queue:{status_filter}:{stage_filter}:{limit}:{offset}:{sort_by}:{ascending}"
        if self._is_cache_valid() and cache_key in self._cache:
            return self._cache[cache_key]

        try:
            with self.db_service.get_session() as session:
                # Base query - get all sources with stage statuses
                query = (
                    session.query(MediaSource)
                    .join(
                        SourceStageStatus,
                        MediaSource.source_id == SourceStageStatus.source_id,
                    )
                    .distinct()
                )

                # Apply filters
                if stage_filter:
                    query = query.filter(SourceStageStatus.stage.in_(stage_filter))

                if status_filter:
                    query = query.filter(SourceStageStatus.status.in_(status_filter))

                # Get total count
                total_count = query.count()

                # Apply sorting
                if sort_by == "created_at":
                    query = query.order_by(
                        MediaSource.created_at.asc()
                        if ascending
                        else MediaSource.created_at.desc()
                    )
                elif sort_by == "title":
                    query = query.order_by(
                        MediaSource.title.asc()
                        if ascending
                        else MediaSource.title.desc()
                    )

                # Apply pagination
                sources = query.limit(limit).offset(offset).all()

                # Build snapshots
                snapshots = []
                for source in sources:
                    snapshot = QueueSnapshot(source.source_id, source)

                    # Add all stage statuses for this source
                    for stage_status in source.stage_statuses:
                        snapshot.add_stage_status(stage_status)

                    # Enrich with authoritative data from Summary/Transcript tables
                    # This ensures status reflects actual completion even if SourceStageStatus is stale
                    self._enrich_snapshot(snapshot, session)

                    snapshots.append(snapshot)

                result = (snapshots, total_count)

                # Update cache
                self._cache[cache_key] = result
                self._cache_timestamp = time.time()

                return result

        except Exception as e:
            logger.error(f"Failed to get queue snapshot: {e}")
            return ([], 0)

    def get_source_timeline(self, source_id: str) -> QueueSnapshot | None:
        """
        Get detailed timeline for a single source.

        Returns:
            QueueSnapshot with all stage information
        """
        cache_key = f"source_timeline:{source_id}"
        if self._is_cache_valid() and cache_key in self._cache:
            return self._cache[cache_key]

        try:
            with self.db_service.get_session() as session:
                # Get source with all relationships
                source = (
                    session.query(MediaSource)
                    .filter(MediaSource.source_id == source_id)
                    .first()
                )

                if not source:
                    return None

                snapshot = QueueSnapshot(source_id, source)

                # Add stage statuses
                for stage_status in source.stage_statuses:
                    snapshot.add_stage_status(stage_status)

                # Add additional context from other tables
                self._enrich_snapshot(snapshot, session)

                # Update cache
                self._cache[cache_key] = snapshot
                self._cache_timestamp = time.time()

                return snapshot

        except Exception as e:
            logger.error(f"Failed to get source timeline for {source_id}: {e}")
            return None

    def get_stage_summary(self) -> dict[str, dict[str, int]]:
        """
        Get summary counts by stage and status.

        Returns:
            {stage: {status: count}}
        """
        cache_key = "stage_summary"
        if self._is_cache_valid() and cache_key in self._cache:
            return self._cache[cache_key]

        try:
            with self.db_service.get_session() as session:
                # Get all stage statuses
                statuses = session.query(SourceStageStatus).all()

                # Build summary
                summary = defaultdict(lambda: defaultdict(int))
                for status in statuses:
                    summary[status.stage][status.status] += 1

                result = dict(summary)

                # Update cache
                self._cache[cache_key] = result
                self._cache_timestamp = time.time()

                return result

        except Exception as e:
            logger.error(f"Failed to get stage summary: {e}")
            return {}

    def get_throughput_metrics(self, time_window_hours: int = 24) -> dict[str, Any]:
        """
        Get throughput metrics for the specified time window.

        Returns:
            Metrics including items/hour by stage
        """
        cache_key = f"throughput:{time_window_hours}"
        if self._is_cache_valid() and cache_key in self._cache:
            return self._cache[cache_key]

        try:
            with self.db_service.get_session() as session:
                cutoff_time = datetime.utcnow() - timedelta(hours=time_window_hours)

                # Get completed items by stage in time window
                completed_by_stage = defaultdict(int)

                statuses = (
                    session.query(SourceStageStatus)
                    .filter(
                        SourceStageStatus.status == "completed",
                        SourceStageStatus.completed_at >= cutoff_time,
                    )
                    .all()
                )

                for status in statuses:
                    completed_by_stage[status.stage] += 1

                # Calculate rates
                metrics = {
                    "time_window_hours": time_window_hours,
                    "items_per_hour_by_stage": {
                        stage: count / time_window_hours
                        for stage, count in completed_by_stage.items()
                    },
                    "total_completed": sum(completed_by_stage.values()),
                    "average_items_per_hour": sum(completed_by_stage.values())
                    / time_window_hours,
                }

                # Update cache
                self._cache[cache_key] = metrics
                self._cache_timestamp = time.time()

                return metrics

        except Exception as e:
            logger.error(f"Failed to get throughput metrics: {e}")
            return {}

    def clear_cache(self):
        """Force clear the cache."""
        self._cache = {}
        self._cache_timestamp = 0

    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid."""
        return time.time() - self._cache_timestamp < self._cache_ttl

    def _enrich_snapshot(self, snapshot: QueueSnapshot, session):
        """Add additional context to snapshot from related tables.
        
        This method syncs status from authoritative sources (MediaSource, Summary, Transcript tables)
        to ensure the queue displays accurate status even if SourceStageStatus is stale.
        """
        # Check download status from MediaSource (authoritative source)
        # The source is already loaded in the snapshot, so we can check audio_downloaded directly
        if snapshot.source.audio_downloaded:
            # Override status if audio is downloaded (authoritative source)
            # This fixes cases where SourceStageStatus is stale or shows "queued"
            if "download" not in snapshot.stage_statuses:
                # Create synthetic stage status from MediaSource
                snapshot.stage_statuses["download"] = type(
                    "obj",
                    (object,),
                    {
                        "stage": "download",
                        "status": "completed",
                        "progress_percent": 100.0,
                        "started_at": snapshot.source.created_at,
                        "completed_at": snapshot.source.created_at,
                        "metadata_json": {
                            "audio_file_path": snapshot.source.audio_file_path,
                            "audio_file_size_bytes": snapshot.source.audio_file_size_bytes,
                            "audio_format": snapshot.source.audio_format,
                            "synced_from_media_source": True,
                        },
                    },
                )()
            else:
                # Update existing status to completed if audio is downloaded
                existing = snapshot.stage_statuses["download"]
                if existing.status not in ("completed", "not_applicable", "skipped"):
                    existing.status = "completed"
                    existing.progress_percent = 100.0
                    if not existing.completed_at:
                        existing.completed_at = snapshot.source.created_at
                    # Sync to database so future queries don't need enrichment
                    try:
                        self.db_service.upsert_stage_status(
                            source_id=snapshot.source_id,
                            stage="download",
                            status="completed",
                            progress_percent=100.0,
                            metadata={
                                "audio_file_path": snapshot.source.audio_file_path,
                                "audio_file_size_bytes": snapshot.source.audio_file_size_bytes,
                                "audio_format": snapshot.source.audio_format,
                                "synced_from_media_source": True,
                            },
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to sync download status to database for {snapshot.source_id}: {e}"
                        )
        elif snapshot.source.max_retries_exceeded:
            # Handle failed downloads
            if "download" not in snapshot.stage_statuses:
                # Create synthetic stage status for failed download
                snapshot.stage_statuses["download"] = type(
                    "obj",
                    (object,),
                    {
                        "stage": "download",
                        "status": "failed",
                        "progress_percent": 0.0,
                        "started_at": snapshot.source.first_failure_at or snapshot.source.created_at,
                        "completed_at": snapshot.source.last_retry_at,
                        "metadata_json": {
                            "failure_reason": snapshot.source.failure_reason,
                            "retry_count": snapshot.source.retry_count,
                            "synced_from_media_source": True,
                        },
                    },
                )()
            else:
                # Update existing status to failed if max retries exceeded
                existing = snapshot.stage_statuses["download"]
                if existing.status not in ("failed", "completed"):
                    existing.status = "failed"
                    if snapshot.source.failure_reason:
                        if not existing.metadata_json:
                            existing.metadata_json = {}
                        existing.metadata_json["failure_reason"] = snapshot.source.failure_reason
                        existing.metadata_json["retry_count"] = snapshot.source.retry_count
                    # Sync to database
                    try:
                        self.db_service.upsert_stage_status(
                            source_id=snapshot.source_id,
                            stage="download",
                            status="failed",
                            metadata={
                                "failure_reason": snapshot.source.failure_reason,
                                "retry_count": snapshot.source.retry_count,
                                "synced_from_media_source": True,
                            },
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to sync failed download status to database for {snapshot.source_id}: {e}"
                        )
        
        # Check for transcript
        transcript = (
            session.query(Transcript)
            .filter(Transcript.source_id == snapshot.source_id)
            .first()
        )

        if transcript:
            # Override status if transcript exists (authoritative source)
            # This fixes cases where SourceStageStatus is stale
            if "transcription" not in snapshot.stage_statuses:
                # Create synthetic stage status from transcript
                snapshot.stage_statuses["transcription"] = type(
                    "obj",
                    (object,),
                    {
                        "stage": "transcription",
                        "status": "completed",
                        "progress_percent": 100.0,
                        "started_at": transcript.created_at,
                        "completed_at": transcript.created_at,
                        "metadata_json": {
                            "whisper_model": transcript.whisper_model,
                            "processing_time_seconds": transcript.processing_time_seconds,
                        },
                    },
                )()
            else:
                # Update existing status to completed if transcript exists
                existing = snapshot.stage_statuses["transcription"]
                if existing.status != "completed":
                    existing.status = "completed"
                    existing.progress_percent = 100.0
                    if not existing.completed_at:
                        existing.completed_at = transcript.created_at

        # Check for summary
        summary = (
            session.query(Summary)
            .filter(Summary.source_id == snapshot.source_id)
            .first()
        )

        if summary:
            # Override status if summary exists (authoritative source)
            # This fixes cases where SourceStageStatus is stale or shows "queued"
            if "summarization" not in snapshot.stage_statuses:
                # Create synthetic stage status from summary
                snapshot.stage_statuses["summarization"] = type(
                    "obj",
                    (object,),
                    {
                        "stage": "summarization",
                        "status": "completed",
                        "progress_percent": 100.0,
                        "started_at": summary.created_at,
                        "completed_at": summary.created_at,
                        "metadata_json": {
                            "llm_provider": summary.llm_provider,
                            "llm_model": summary.llm_model,
                            "total_tokens": summary.total_tokens,
                            "processing_cost": summary.processing_cost,
                        },
                    },
                )()
            else:
                # Update existing status to completed if summary exists
                existing = snapshot.stage_statuses["summarization"]
                if existing.status != "completed":
                    existing.status = "completed"
                    existing.progress_percent = 100.0
                    if not existing.completed_at:
                        existing.completed_at = summary.created_at
                    # Sync to database so future queries don't need enrichment
                    try:
                        self.db_service.upsert_stage_status(
                            source_id=snapshot.source_id,
                            stage="summarization",
                            status="completed",
                            progress_percent=100.0,
                            metadata={
                                "llm_provider": summary.llm_provider,
                                "llm_model": summary.llm_model,
                                "total_tokens": summary.total_tokens,
                                "processing_cost": summary.processing_cost,
                                "synced_from_summary_table": True,
                                "summary_created_at": summary.created_at.isoformat() if summary.created_at else None,
                            },
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to sync summarization status to database for {snapshot.source_id}: {e}"
                        )
        
        # Recalculate derived fields after all enrichment is complete
        # This ensures overall_status and current_stage reflect the updated stage statuses
        snapshot._update_derived_fields()
