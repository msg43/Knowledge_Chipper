"""
Speaker Assignment Queue Manager

Manages non-blocking speaker assignment dialogs that can stack up
while processing continues in the background.
"""

import queue
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..database import DatabaseService
from ..logger import get_logger
from ..processors.speaker_processor import SpeakerData

logger = get_logger(__name__)


@dataclass
class SpeakerAssignmentTask:
    """Represents a pending speaker assignment task."""

    task_id: str
    video_id: str
    transcript_id: str
    speaker_data_list: list[SpeakerData]
    recording_path: str
    metadata: dict[str, Any]
    created_at: datetime
    completed: bool = False
    assignments: dict[str, str] | None = None


class SpeakerAssignmentQueue:
    """
    Manages a queue of speaker assignment tasks that can be processed
    asynchronously without blocking the main processing pipeline.
    """

    def __init__(self, assignment_callback: Callable | None = None):
        """
        Initialize the speaker assignment queue.

        Args:
            assignment_callback: Callback to show speaker assignment dialog
        """
        self.tasks = queue.Queue()
        self.pending_tasks = {}  # task_id -> SpeakerAssignmentTask
        self.assignment_callback = assignment_callback
        self._lock = threading.Lock()

    def add_task(
        self,
        video_id: str,
        transcript_id: str,
        speaker_data_list: list[SpeakerData],
        recording_path: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Add a new speaker assignment task to the queue.

        Returns:
            Task ID for tracking
        """
        task_id = str(uuid.uuid4())

        task = SpeakerAssignmentTask(
            task_id=task_id,
            video_id=video_id,
            transcript_id=transcript_id,
            speaker_data_list=speaker_data_list,
            recording_path=recording_path,
            metadata=metadata or {},
            created_at=datetime.now(),
        )

        with self._lock:
            self.pending_tasks[task_id] = task
            self.tasks.put(task)

        logger.info(
            f"Added speaker assignment task {task_id} for {recording_path} "
            f"({len(speaker_data_list)} speakers)"
        )

        # Trigger assignment dialog if callback is available
        if self.assignment_callback:
            # This should emit a signal to show dialog on main thread
            self.assignment_callback(task)

        return task_id

    def complete_task(
        self,
        task_id: str,
        assignments: dict[str, str] | None,
    ) -> bool:
        """
        Mark a task as completed and update the database.

        Args:
            task_id: Task ID to complete
            assignments: Speaker assignments or None if cancelled

        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            task = self.pending_tasks.get(task_id)
            if not task:
                logger.error(f"Task {task_id} not found")
                return False

            task.completed = True
            task.assignments = assignments

        if assignments:
            # Update the database with speaker assignments
            try:
                db_service = DatabaseService()

                # Get the transcript
                transcript = db_service.get_transcript(task.transcript_id)
                if not transcript:
                    logger.error(f"Transcript {task.transcript_id} not found")
                    return False

                # Update segments with speaker names
                segments = transcript.transcript_segments_json or []
                updated_segments = []

                for segment in segments:
                    updated_segment = segment.copy()
                    speaker_id = segment.get("speaker", "")

                    if speaker_id in assignments:
                        # Replace generic speaker ID with assigned name
                        updated_segment["speaker"] = assignments[speaker_id]
                        updated_segment["original_speaker_id"] = speaker_id

                    updated_segments.append(updated_segment)

                # Update transcript text with speaker names
                transcript_text = transcript.transcript_text
                for speaker_id, assigned_name in assignments.items():
                    # Replace patterns like (SPEAKER_00) with assigned names
                    transcript_text = transcript_text.replace(
                        f"({speaker_id}):", f"({assigned_name}):"
                    )
                    # Also handle variations
                    transcript_text = transcript_text.replace(
                        f"(Speaker {speaker_id.replace('SPEAKER_', '').lstrip('0') or '0'}):",
                        f"({assigned_name}):",
                    )

                # Update the transcript in database
                db_service.update_transcript(
                    transcript_id=task.transcript_id,
                    transcript_text=str(transcript_text),
                    transcript_segments_json=updated_segments,
                    speaker_assignments=assignments,
                    speaker_assignment_completed=True,
                )

                logger.info(
                    f"Updated transcript {task.transcript_id} with speaker assignments"
                )

                # Save speaker assignments to speaker database
                from ..processors.speaker_processor import SpeakerProcessor

                speaker_processor = SpeakerProcessor()
                speaker_processor._save_assignments_to_database(
                    task.recording_path,
                    task.speaker_data_list,
                    assignments,
                )
                
                # CRITICAL: Regenerate the markdown file with speaker names
                logger.info(f"Regenerating markdown with assigned speaker names for {task.video_id}")

                try:
                    from pathlib import Path
                    
                    # Get transcript record to access segments with speakers
                    transcript = db_service.get_transcript(task.transcript_id) if hasattr(task, 'transcript_id') else None
                    
                    if transcript and transcript.transcript_segments_json:
                        # Apply speaker name assignments to segments
                        updated_segments = []
                        for seg in transcript.transcript_segments_json:
                            seg_copy = seg.copy()
                            speaker_id = seg.get("speaker")
                            if speaker_id and speaker_id in assignments:
                                seg_copy["speaker"] = assignments[speaker_id]
                            updated_segments.append(seg_copy)
                        
                        # Get the markdown file path
                        file_path, video_metadata = db_service.get_transcript_path_for_regeneration(transcript.transcript_id)
                        
                        if file_path and file_path.exists():
                            # Create updated transcript data
                            transcript_data = {
                                "text": transcript.transcript_text,
                                "segments": updated_segments,
                                "language": transcript.language,
                            }
                            
                            # Recreate the markdown with updated speaker names
                            from ..processors.audio_processor import AudioProcessor
                            from ..processors.base import ProcessorResult
                            
                            audio_processor = AudioProcessor()
                            updated_result = ProcessorResult(
                                success=True,
                                data=transcript_data,
                                metadata={
                                    "model": transcript.whisper_model or "unknown",
                                    "diarization_enabled": transcript.diarization_enabled,
                                }
                            )
                            
                            # Overwrite the existing markdown file
                            audio_path = Path(task.recording_path)
                            saved_file = audio_processor.save_transcript_to_markdown(
                                updated_result,
                                audio_path,
                                file_path.parent,
                                include_timestamps=True,
                                video_metadata=video_metadata,
                            )
                            
                            if saved_file:
                                logger.info(f"✅ Successfully regenerated markdown with speaker names: {saved_file}")
                            else:
                                logger.warning("⚠️ Markdown regeneration returned None")
                        else:
                            logger.warning(f"Markdown file not found for regeneration: {file_path}")
                    else:
                        logger.warning("Could not retrieve transcript segments for regeneration")
                        
                except Exception as e:
                    logger.error(f"Failed to regenerate markdown with speaker names: {e}")
                    import traceback
                    traceback.print_exc()

                return True

            except Exception as e:
                logger.error(f"Failed to update database with speaker assignments: {e}")
                return False
        else:
            logger.info(f"Speaker assignment task {task_id} was cancelled")
            return True

    def get_pending_count(self) -> int:
        """Get the number of pending speaker assignment tasks."""
        with self._lock:
            return sum(1 for task in self.pending_tasks.values() if not task.completed)

    def get_pending_tasks(self) -> list[SpeakerAssignmentTask]:
        """Get all pending tasks."""
        with self._lock:
            return [task for task in self.pending_tasks.values() if not task.completed]


# Global instance
_assignment_queue = None


def get_speaker_assignment_queue() -> SpeakerAssignmentQueue:
    """Get the global speaker assignment queue instance."""
    global _assignment_queue
    if _assignment_queue is None:
        _assignment_queue = SpeakerAssignmentQueue()
    return _assignment_queue
