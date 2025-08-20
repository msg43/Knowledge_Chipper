"""
Global resource coordination to prevent conflicts between concurrent processing operations.

This module provides a singleton coordinator that tracks active processing across
all tabs and prevents resource conflicts when running multiple operations simultaneously.
"""

import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from queue import Empty, Queue
from typing import Any, Optional

from ..logger import get_logger

logger = get_logger(__name__)


class ProcessingType(Enum):
    """Types of processing operations."""

    TRANSCRIPTION = "transcription"
    YOUTUBE_DOWNLOAD = "youtube_download"
    SUMMARIZATION = "summarization"
    MOC_GENERATION = "moc_generation"


@dataclass
class ActiveOperation:
    """Represents an active processing operation."""

    tab_name: str
    processing_type: ProcessingType
    concurrent_limit: int
    start_time: float
    estimated_duration: float | None = None


@dataclass
class QueuedOperation:
    """Represents a queued operation waiting for authorization."""

    operation_id: str
    tab_name: str
    processing_type: ProcessingType
    requested_concurrent: int
    estimated_duration: float | None
    authorization_callback: Callable[
        [int, str], None
    ]  # Called with (granted_concurrent, operation_id)
    queued_at: float = field(default_factory=time.time)

    def authorize_with_limit(self, granted_concurrent: int, operation_id: str) -> None:
        """Authorize the operation with the granted concurrent limit."""
        self.authorization_callback(granted_concurrent, operation_id)


class ResourceCoordinator:
    """
    Singleton coordinator to manage concurrent processing across tabs.

    Prevents resource conflicts by:
    1. Tracking active operations across all tabs
    2. Adjusting concurrent limits based on total system load
    3. Providing warnings when resource conflicts are likely
    """

    _instance: Optional["ResourceCoordinator"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "ResourceCoordinator":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return

        self._initialized = True
        self.active_operations: dict[str, ActiveOperation] = {}
        self.operation_queue: Queue[QueuedOperation] = Queue()
        self.operation_lock = threading.RLock()

        # Start queue processing thread
        self.queue_processor_thread = threading.Thread(
            target=self._process_queue, daemon=True, name="ResourceCoordinatorQueue"
        )
        self.queue_processor_thread.start()

        logger.debug("ResourceCoordinator initialized with queue processing")

    def request_operation(
        self,
        tab_name: str,
        processing_type: ProcessingType,
        requested_concurrent: int,
        authorization_callback: Callable[[int, str], None],
        estimated_duration: float | None = None,
    ) -> str:
        """
        Request authorization for a new processing operation.

        Args:
            tab_name: Name of the tab requesting the operation
            processing_type: Type of processing operation
            requested_concurrent: Requested concurrent limit
            authorization_callback: Called when operation is authorized with (granted_concurrent, operation_id)
            estimated_duration: Estimated duration in seconds

        Returns:
            Request ID for tracking
        """
        request_id = str(uuid.uuid4())

        with self.operation_lock:
            # Check if we can authorize immediately
            granted_limit = self._calculate_safe_concurrent_limit(
                processing_type, requested_concurrent
            )

            if granted_limit > 0:
                # Authorize immediately
                operation_id = self._authorize_operation(
                    tab_name, processing_type, granted_limit, estimated_duration
                )

                # Call authorization callback immediately
                try:
                    authorization_callback(granted_limit, operation_id)
                except Exception as e:
                    logger.error(f"Error in authorization callback: {e}")

                logger.info(
                    f"🎯 Immediate Authorization: {tab_name} {processing_type.value} "
                    f"granted {granted_limit}/{requested_concurrent} concurrent"
                )

                return request_id
            else:
                # Queue the operation
                queued_op = QueuedOperation(
                    operation_id=request_id,
                    tab_name=tab_name,
                    processing_type=processing_type,
                    requested_concurrent=requested_concurrent,
                    estimated_duration=estimated_duration,
                    authorization_callback=authorization_callback,
                )

                self.operation_queue.put(queued_op)

                logger.info(
                    f"🚦 Queued: {tab_name} {processing_type.value} "
                    f"requesting {requested_concurrent} concurrent (queue size: {self.operation_queue.qsize()})"
                )

                return request_id

    def _authorize_operation(
        self,
        tab_name: str,
        processing_type: ProcessingType,
        granted_concurrent: int,
        estimated_duration: float | None = None,
    ) -> str:
        """Internal method to authorize and register an operation."""
        operation_id = f"{tab_name}_{processing_type.value}_{int(time.time())}_{uuid.uuid4().hex[:8]}"

        operation = ActiveOperation(
            tab_name=tab_name,
            processing_type=processing_type,
            concurrent_limit=granted_concurrent,
            start_time=time.time(),
            estimated_duration=estimated_duration,
        )

        self.active_operations[operation_id] = operation

        return operation_id

    def unregister_operation(self, operation_id: str) -> None:
        """Unregister a completed processing operation and process queue."""
        with self.operation_lock:
            if operation_id in self.active_operations:
                operation = self.active_operations.pop(operation_id)
                duration = time.time() - operation.start_time
                logger.info(
                    f"📊 Completed: {operation.tab_name} {operation.processing_type.value} "
                    f"({duration:.1f}s, {operation.concurrent_limit} concurrent)"
                )

                # Trigger queue processing since we freed up resources
                self._trigger_queue_processing()

    def _trigger_queue_processing(self) -> None:
        """Signal the queue processor to check for operations that can be authorized."""
        # Add a special signal to the queue to wake up the processor
        try:
            self.operation_queue.put(
                QueuedOperation(
                    operation_id="__PROCESS_SIGNAL__",
                    tab_name="",
                    processing_type=ProcessingType.TRANSCRIPTION,  # Dummy value
                    requested_concurrent=0,
                    estimated_duration=None,
                    authorization_callback=lambda x, y: None,  # No-op callback
                ),
                timeout=1,
            )
        except:
            pass  # Queue might be full, processor will wake up eventually

    def _process_queue(self) -> None:
        """Background thread to process the operation queue."""
        while True:
            try:
                # Wait for queued operations (blocking)
                queued_op = self.operation_queue.get(timeout=5.0)

                # Skip processing signals
                if queued_op.operation_id == "__PROCESS_SIGNAL__":
                    continue

                with self.operation_lock:
                    # Check if we can authorize this operation now
                    granted_limit = self._calculate_safe_concurrent_limit(
                        queued_op.processing_type, queued_op.requested_concurrent
                    )

                    if granted_limit > 0:
                        # Authorize the operation
                        operation_id = self._authorize_operation(
                            queued_op.tab_name,
                            queued_op.processing_type,
                            granted_limit,
                            queued_op.estimated_duration,
                        )

                        wait_time = time.time() - queued_op.queued_at
                        logger.info(
                            f"✅ Authorized from queue: {queued_op.tab_name} {queued_op.processing_type.value} "
                            f"granted {granted_limit}/{queued_op.requested_concurrent} "
                            f"(waited {wait_time:.1f}s)"
                        )

                        # Call the authorization callback
                        try:
                            queued_op.authorize_with_limit(granted_limit, operation_id)
                        except Exception as e:
                            logger.error(f"Error in queued authorization callback: {e}")
                    else:
                        # Still can't authorize, put it back in queue
                        self.operation_queue.put(queued_op)

            except Empty:
                # Timeout - check queue again
                continue
            except Exception as e:
                logger.error(f"Error in queue processor: {e}")
                time.sleep(1)  # Prevent tight error loops

    def _calculate_safe_concurrent_limit(
        self, processing_type: ProcessingType, requested: int
    ) -> int:
        """Calculate safe concurrent limit based on current system load."""

        # Get current total concurrent operations
        current_total = sum(
            op.concurrent_limit for op in self.active_operations.values()
        )

        # Get hardware specs for baseline limits
        from .hardware_detection import get_hardware_detector

        detector = get_hardware_detector()
        specs = detector.detect_hardware()

        # Calculate system-wide safe limits based on memory and CPU
        max_system_concurrent = specs.max_concurrent_transcriptions

        # FIXED: Proper memory-aware allocation
        if len(self.active_operations) == 0:
            # First operation gets full allocation
            return min(requested, max_system_concurrent)

        elif len(self.active_operations) == 1:
            # Second operation: share remaining capacity fairly
            remaining = max(0, max_system_concurrent - current_total)
            # Give at most half the remaining, but at least 1
            return max(1, min(requested, remaining // 2))

        else:
            # Third+ operation: minimal allocation from remaining capacity
            remaining = max(0, max_system_concurrent - current_total)
            # Give at most 1/3 remaining, but guarantee at least 1 if any capacity exists
            if remaining > 0:
                return max(1, min(requested, max(1, remaining // 3)))
            else:
                # System at capacity: Operations must wait or process sequentially
                logger.warning(
                    f"⚠️ System at memory capacity ({current_total}/{max_system_concurrent} concurrent processes). "
                    f"New operations will be queued or run sequentially."
                )
                return 0  # Signal that operation should wait

    def get_system_load_info(self) -> dict[str, Any]:
        """Get current system load information."""
        with self.operation_lock:
            total_concurrent = sum(
                op.concurrent_limit for op in self.active_operations.values()
            )

            # Group by processing type
            by_type = {}
            for op in self.active_operations.values():
                ptype = op.processing_type.value
                if ptype not in by_type:
                    by_type[ptype] = {"count": 0, "concurrent": 0, "tabs": []}
                by_type[ptype]["count"] += 1
                by_type[ptype]["concurrent"] += op.concurrent_limit
                by_type[ptype]["tabs"].append(op.tab_name)

            return {
                "active_operations": len(self.active_operations),
                "total_concurrent_processes": total_concurrent,
                "by_type": by_type,
                "operations": [
                    {
                        "tab": op.tab_name,
                        "type": op.processing_type.value,
                        "concurrent": op.concurrent_limit,
                        "duration": time.time() - op.start_time,
                    }
                    for op in self.active_operations.values()
                ],
            }

    def warn_if_resource_conflict(
        self, tab_name: str, processing_type: ProcessingType
    ) -> str | None:
        """
        Check if starting a new operation would cause resource conflicts.

        Returns warning message if conflict detected, None if safe.
        """
        with self.operation_lock:
            if not self.active_operations:
                return None

            # Check for potential conflicts
            conflicts = []

            # Memory-intensive operations
            memory_intensive = {
                ProcessingType.TRANSCRIPTION,
                ProcessingType.YOUTUBE_DOWNLOAD,
            }
            if processing_type in memory_intensive:
                active_memory_ops = [
                    op
                    for op in self.active_operations.values()
                    if op.processing_type in memory_intensive
                ]
                if active_memory_ops:
                    total_concurrent = sum(
                        op.concurrent_limit for op in active_memory_ops
                    )
                    conflicts.append(
                        f"Memory: {len(active_memory_ops)} active transcription/download operations "
                        f"using {total_concurrent} concurrent processes"
                    )

            # API rate limiting conflicts
            if processing_type == ProcessingType.SUMMARIZATION:
                active_api_ops = [
                    op
                    for op in self.active_operations.values()
                    if op.processing_type == ProcessingType.SUMMARIZATION
                ]
                if active_api_ops:
                    conflicts.append(
                        f"API: {len(active_api_ops)} active summarization operations may hit rate limits"
                    )

            if conflicts:
                return f"⚠️ Resource conflicts detected: {'; '.join(conflicts)}"

            return None


# Global instance
_resource_coordinator: ResourceCoordinator | None = None


def get_resource_coordinator() -> ResourceCoordinator:
    """Get the global resource coordinator instance."""
    global _resource_coordinator
    if _resource_coordinator is None:
        _resource_coordinator = ResourceCoordinator()
    return _resource_coordinator
