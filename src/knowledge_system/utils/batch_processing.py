"""
Batch processing utilities for Knowledge Chipper.

This module provides efficient batch processing of multiple audio files,
reusing loaded models and optimizing resource utilization across the batch.
"""

import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from knowledge_system.logger import get_logger

logger = get_logger(__name__)


class BatchStrategy(Enum):
    """Strategies for batch processing."""

    SEQUENTIAL = "sequential"
    PARALLEL_FILES = "parallel_files"
    PIPELINE_PARALLEL = "pipeline_parallel"


@dataclass
class BatchItem:
    """Represents a single item in a batch."""

    file_path: Path
    item_id: str
    priority: int = 0
    estimated_duration: float | None = None
    metadata: dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class BatchResult:
    """Result from processing a batch item."""

    item_id: str
    file_path: Path
    success: bool
    processing_time: float
    transcription_result: Any | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = None
    hce_analytics: dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.hce_analytics is None:
            self.hce_analytics = {}


class BatchProcessor:
    """Efficient batch processing of audio files."""

    def __init__(
        self,
        max_concurrent_files: int = 3,
        strategy: BatchStrategy = BatchStrategy.PIPELINE_PARALLEL,
        progress_callback: Callable | None = None,
        enable_diarization: bool = True,
    ):
        """Initialize batch processor."""
        self.max_concurrent_files = max_concurrent_files
        self.strategy = strategy
        self.progress_callback = progress_callback
        self.enable_diarization = enable_diarization

        # Processing state
        self.total_files = 0
        self.completed_files = 0
        self.failed_files = 0
        self.start_time = 0.0

        # Thread safety
        self.lock = threading.RLock()

        logger.info(
            f"Batch processor initialized: strategy={strategy.value}, max_concurrent={max_concurrent_files}"
        )

    def _estimate_file_duration(self, file_path: Path) -> float:
        """Estimate audio file duration using ffprobe."""
        try:
            import subprocess

            cmd = [
                "ffprobe",
                "-v",
                "quiet",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                str(file_path),
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
            else:
                return 300.0  # Default 5 minutes

        except Exception:
            return 300.0  # Default 5 minutes

    def _sort_batch_items(self, items: list[BatchItem]) -> list[BatchItem]:
        """Sort batch items for optimal processing order."""
        # Estimate durations for items that don't have them
        for item in items:
            if item.estimated_duration is None:
                item.estimated_duration = self._estimate_file_duration(item.file_path)

        # Sort by priority (high to low), then by duration (short to long)
        sorted_items = sorted(
            items, key=lambda x: (-x.priority, x.estimated_duration or 0)
        )

        logger.info(f"Sorted {len(items)} batch items by priority and duration")
        return sorted_items

    def _update_progress(self, message: str, current: int = None, total: int = None):
        """Update progress callback with completion percentage and remaining count."""
        if self.progress_callback:
            if current is not None and total is not None:
                percent = (current / total) * 100 if total > 0 else 0
                remaining = total - current
                remaining_str = f", {remaining} left" if remaining > 0 else ""
                self.progress_callback(
                    f"{message} ({current}/{total}{remaining_str}, {percent:.1f}%)"
                )
            else:
                self.progress_callback(message)

    def process_batch(
        self,
        items: list[BatchItem],
        audio_processor,
        transcription_kwargs: dict[str, Any] = None,
        diarization_kwargs: dict[str, Any] = None,
    ) -> list[BatchResult]:
        """Process a batch of audio files."""
        if not items:
            return []

        transcription_kwargs = transcription_kwargs or {}
        diarization_kwargs = diarization_kwargs or {}

        # Initialize processing state
        with self.lock:
            self.total_files = len(items)
            self.completed_files = 0
            self.failed_files = 0
            self.start_time = time.time()

        logger.info(
            f"Starting batch processing: {len(items)} files, strategy={self.strategy.value}"
        )
        self._update_progress(
            f"Starting batch processing of {len(items)} files", 0, len(items)
        )

        # Sort items for optimal processing
        sorted_items = self._sort_batch_items(items)

        # Process based on strategy
        if self.strategy == BatchStrategy.SEQUENTIAL:
            return self._process_sequential(
                sorted_items, audio_processor, transcription_kwargs, diarization_kwargs
            )
        else:  # Both parallel strategies use same implementation for now
            return self._process_parallel_files(
                sorted_items, audio_processor, transcription_kwargs, diarization_kwargs
            )

    def _process_sequential(
        self,
        items: list[BatchItem],
        audio_processor,
        transcription_kwargs: dict[str, Any],
        diarization_kwargs: dict[str, Any],
    ) -> list[BatchResult]:
        """Process files sequentially (one at a time)."""
        results = []

        for i, item in enumerate(items):
            result = self._process_single_item(
                item, audio_processor, transcription_kwargs, diarization_kwargs
            )
            results.append(result)

            with self.lock:
                self.completed_files += 1
                if not result.success:
                    self.failed_files += 1

            self._update_progress(
                f"Completed {item.file_path.name}",
                self.completed_files,
                self.total_files,
            )

        return results

    def _process_parallel_files(
        self,
        items: list[BatchItem],
        audio_processor,
        transcription_kwargs: dict[str, Any],
        diarization_kwargs: dict[str, Any],
    ) -> list[BatchResult]:
        """Process multiple files in parallel with dynamic memory monitoring."""
        results = []
        active_futures = {}

        with ThreadPoolExecutor(
            max_workers=self.max_concurrent_files, thread_name_prefix="BatchProcessor"
        ) as executor:
            # Submit initial batch of items
            items_to_process = items.copy()

            # Start with first batch
            initial_batch_size = min(self.max_concurrent_files, len(items_to_process))
            for _ in range(initial_batch_size):
                if items_to_process:
                    item = items_to_process.pop(0)
                    future = executor.submit(
                        self._process_single_item,
                        item,
                        audio_processor,
                        transcription_kwargs,
                        diarization_kwargs,
                    )
                    active_futures[future] = item

            # Process with dynamic memory monitoring
            while active_futures or items_to_process:
                # Check for completed futures
                if active_futures:
                    completed_futures = []
                    for future in list(active_futures.keys()):
                        if future.done():
                            completed_futures.append(future)

                    # Process completed results
                    for future in completed_futures:
                        item = active_futures.pop(future)
                        try:
                            result = future.result()
                            results.append(result)

                            with self.lock:
                                self.completed_files += 1
                                if not result.success:
                                    self.failed_files += 1

                            self._update_progress(
                                f"Completed {item.file_path.name}",
                                self.completed_files,
                                self.total_files,
                            )

                        except Exception as e:
                            logger.error(f"Error processing {item.file_path}: {e}")
                            error_result = BatchResult(
                                item_id=item.item_id,
                                file_path=item.file_path,
                                success=False,
                                processing_time=0.0,
                                error_message=str(e),
                            )
                            results.append(error_result)

                            with self.lock:
                                self.completed_files += 1
                                self.failed_files += 1

                # Check memory pressure before starting new tasks
                if items_to_process and len(active_futures) < self.max_concurrent_files:
                    should_start_new = self._check_memory_before_new_task()

                    if should_start_new:
                        # Start next item
                        item = items_to_process.pop(0)
                        future = executor.submit(
                            self._process_single_item,
                            item,
                            audio_processor,
                            transcription_kwargs,
                            diarization_kwargs,
                        )
                        active_futures[future] = item
                    else:
                        # Wait a bit before checking again
                        import time

                        time.sleep(2)

                # Small delay to prevent busy waiting
                if active_futures:
                    import time

                    time.sleep(0.5)

        # Sort results by original item order
        item_order = {item.item_id: i for i, item in enumerate(items)}
        results.sort(key=lambda r: item_order.get(r.item_id, 999999))

        return results

    def _check_memory_before_new_task(self) -> bool:
        """
        Check if it's safe to start a new processing task based on current memory pressure.

        Returns:
            True if safe to start new task, False otherwise
        """
        import psutil

        current_memory = psutil.virtual_memory()
        current_usage = current_memory.percent / 100.0

        # Dynamic thresholds based on current load
        if current_usage > 0.90:  # 90%+ usage - EMERGENCY
            logger.warning(
                f"CRITICAL memory pressure ({current_usage:.1%}), attempting emergency cleanup"
            )
            # Try emergency cleanup
            new_usage = self._emergency_memory_cleanup()
            if new_usage > 0.88:  # Still too high after cleanup
                logger.error(
                    f"Emergency cleanup failed to free enough memory ({new_usage:.1%}), pausing new tasks"
                )
                return False
            else:
                logger.info("Emergency cleanup successful, proceeding with caution")
                return True
        elif current_usage > 0.85:  # 85-90% usage - High pressure
            logger.warning(
                f"High memory pressure ({current_usage:.1%}), waiting before new tasks"
            )
            return False
        elif current_usage > 0.80:  # 80-85% usage - Moderate pressure
            # Only start if we have very few active tasks
            active_count = len(getattr(self, "_active_futures", {}))
            if active_count >= 2:
                logger.info(
                    f"Moderate memory pressure ({current_usage:.1%}), limiting active tasks"
                )
                return False
        elif current_usage > 0.75:  # 75-80% usage - Some pressure
            # Prefer to keep some buffer
            active_count = len(getattr(self, "_active_futures", {}))
            if active_count >= 3:
                logger.debug(
                    f"Some memory pressure ({current_usage:.1%}), conservative task start"
                )
                return False

        # Memory looks good
        return True

    def _emergency_memory_cleanup(self):
        """
        Perform emergency memory cleanup when approaching critical levels.
        """
        import gc

        logger.warning("Performing emergency memory cleanup")

        # Force garbage collection
        collected = gc.collect()
        logger.info(f"Garbage collector freed {collected} objects")

        # Clear model cache if available
        try:
            from knowledge_system.utils.model_cache import clear_model_cache

            clear_model_cache()
            logger.info("Cleared model cache to free memory")
        except ImportError:
            pass

        # Force another GC pass
        gc.collect()

        # Check memory after cleanup
        import psutil

        current_memory = psutil.virtual_memory()
        current_usage = current_memory.percent / 100.0
        logger.info(f"Memory usage after cleanup: {current_usage:.1%}")

        return current_usage

    def _process_single_item(
        self,
        item: BatchItem,
        audio_processor,
        transcription_kwargs: dict[str, Any],
        diarization_kwargs: dict[str, Any],
    ) -> BatchResult:
        """Process a single batch item."""
        start_time = time.time()

        try:
            logger.info(f"Processing {item.file_path}")

            # Prepare processing arguments
            process_kwargs = transcription_kwargs.copy()
            process_kwargs.update(diarization_kwargs)
            process_kwargs["diarization"] = self.enable_diarization

            # Process the file
            result = audio_processor.process(item.file_path, **process_kwargs)

            processing_time = time.time() - start_time

            if result.success:
                logger.info(
                    f"✅ Successfully processed {item.file_path} in {processing_time:.1f}s"
                )
            else:
                logger.error(f"❌ Failed to process {item.file_path}: {result.errors}")

            return BatchResult(
                item_id=item.item_id,
                file_path=item.file_path,
                success=result.success,
                processing_time=processing_time,
                transcription_result=result,
                error_message="; ".join(result.errors) if result.errors else None,
                metadata={
                    "estimated_duration": item.estimated_duration,
                    "priority": item.priority,
                    **item.metadata,
                },
            )

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"❌ Error processing {item.file_path}: {e}")

            return BatchResult(
                item_id=item.item_id,
                file_path=item.file_path,
                success=False,
                processing_time=processing_time,
                error_message=str(e),
                metadata={
                    "estimated_duration": item.estimated_duration,
                    "priority": item.priority,
                    **item.metadata,
                },
            )


def create_batch_from_files(
    file_paths: list[Path], priorities: list[int] | None = None
) -> list[BatchItem]:
    """Create a batch from a list of file paths."""
    if priorities and len(priorities) != len(file_paths):
        raise ValueError("Priorities list must be same length as file_paths")

    items = []
    for i, file_path in enumerate(file_paths):
        priority = priorities[i] if priorities else 0
        item = BatchItem(
            file_path=Path(file_path),
            item_id=f"item_{i:04d}",
            priority=priority,
            metadata={"original_index": i},
        )
        items.append(item)

    return items


def determine_optimal_batch_strategy(
    file_count: int,
    average_file_duration: float,
    available_cores: int,
    available_memory_gb: float,
) -> tuple[BatchStrategy, int]:
    """Determine optimal batch processing strategy and concurrency with memory-aware limits."""
    # Single file or very few files - use sequential
    if file_count <= 1:
        return BatchStrategy.SEQUENTIAL, 1

    # For very short files, sequential might be faster due to overhead
    if average_file_duration < 60:  # Less than 1 minute
        return BatchStrategy.SEQUENTIAL, 1

    # For longer files, consider parallel processing
    if file_count <= 3:
        # Few files - use pipeline parallel for each file
        return BatchStrategy.PIPELINE_PARALLEL, 1

    # Memory-aware concurrent processing calculation
    max_concurrent = calculate_memory_safe_concurrency(
        available_memory_gb, available_cores
    )
    max_concurrent = min(file_count, max_concurrent)

    if max_concurrent > 1:
        return BatchStrategy.PARALLEL_FILES, max_concurrent
    else:
        return BatchStrategy.SEQUENTIAL, 1


def calculate_memory_safe_concurrency(
    available_memory_gb: float, available_cores: int
) -> int:
    """
    Calculate safe concurrent processing based on memory budget and real-time pressure.

    Args:
        available_memory_gb: Total system memory
        available_cores: Number of CPU cores

    Returns:
        Safe number of concurrent files to process
    """
    import psutil

    # Memory requirements per video (REALISTIC estimates for audio-only processing)
    memory_per_video = {
        "whisper_model": 0.14,  # whisper.cpp base model in RAM (~140MB)
        "diarization_model": 0.5,  # pyannote.audio model (~500MB)
        "audio_buffers": 0.1,  # Raw audio + converted formats (~100MB for 10min video)
        "processing_overhead": 0.2,  # Temporary buffers, etc. (~200MB)
        "safety_margin": 0.16,  # Additional buffer for spikes (~160MB)
    }

    total_memory_per_video = sum(
        memory_per_video.values()
    )  # ~1.1GB per video (REALISTIC)

    # System memory budget (conservative)
    memory_budget = {
        "system_os": min(20, available_memory_gb * 0.15),  # OS + system processes
        "user_apps": min(15, available_memory_gb * 0.12),  # Browser, IDE, etc.
        "memory_pressure_buffer": available_memory_gb * 0.08,  # Never go above 92%
    }

    reserved_memory = sum(memory_budget.values())
    usable_memory = available_memory_gb - reserved_memory

    # Calculate theoretical max based on memory
    memory_based_max = max(1, int(usable_memory // total_memory_per_video))

    # Calculate CPU-based limit for ML workloads (less CPU-intensive due to GPU/Neural Engine)
    if available_cores >= 20:  # High-end systems (M2 Ultra, etc.)
        cpu_based_max = min(
            12, available_cores // 2
        )  # Can handle more concurrent ML tasks
    elif available_cores >= 12:  # Mid-high systems
        cpu_based_max = min(8, available_cores // 2)
    elif available_cores >= 8:  # Standard systems
        cpu_based_max = min(6, available_cores // 2)
    else:  # Lower-end systems
        cpu_based_max = max(1, available_cores // 3)  # More conservative

    # Take the more conservative limit
    theoretical_max = min(memory_based_max, cpu_based_max)

    # Check current memory pressure using HYBRID approach (absolute + percentage)
    current_memory = psutil.virtual_memory()
    current_usage_percent = current_memory.percent / 100.0
    free_memory_gb = current_memory.available / (1024**3)

    # Calculate how many videos we can fit in FREE memory (with safety buffer)
    free_memory_budget = max(0, free_memory_gb - 8.0)  # Reserve 8GB for system
    free_memory_based_max = int(free_memory_budget // total_memory_per_video)

    # Use HYBRID logic: free memory capacity AND percentage pressure
    if free_memory_gb < 4.0:  # Critical: <4GB free regardless of percentage
        adjusted_max = 1
        logger.warning(
            f"CRITICAL: Only {free_memory_gb:.1f}GB free memory - limiting to sequential processing"
        )
    elif free_memory_gb < 8.0:  # Low: <8GB free
        adjusted_max = min(2, theoretical_max, free_memory_based_max)
        logger.info(
            f"LOW FREE MEMORY: {free_memory_gb:.1f}GB free ({current_usage_percent:.1%} used) - limiting to 2 concurrent"
        )
    elif (
        current_usage_percent > 0.90
    ):  # Very high percentage (but adequate free memory)
        adjusted_max = min(theoretical_max // 2, free_memory_based_max)  # Half capacity
        logger.info(
            f"HIGH MEMORY PRESSURE: {current_usage_percent:.1%} used, {free_memory_gb:.1f}GB free - limiting to {adjusted_max} concurrent"
        )
    elif current_usage_percent > 0.80:  # High percentage
        adjusted_max = min(
            int(theoretical_max * 0.75), free_memory_based_max
        )  # 75% capacity
        logger.info(
            f"MODERATE MEMORY PRESSURE: {current_usage_percent:.1%} used, {free_memory_gb:.1f}GB free - limiting to {adjusted_max} concurrent"
        )
    else:  # Good free memory AND reasonable percentage
        adjusted_max = min(theoretical_max, free_memory_based_max)
        logger.info(
            f"EXCELLENT MEMORY AVAILABILITY: {free_memory_gb:.1f}GB free ({current_usage_percent:.1%} used) - allowing {adjusted_max} concurrent"
        )

    # Apply realistic system-specific limits (updated for 1.1GB per video budget)
    if available_memory_gb >= 128:  # Ultra high-end systems (128GB+)
        final_max = min(adjusted_max, 12)  # Can handle 12+ concurrent with 1.1GB each
    elif available_memory_gb >= 64:  # High-end systems (64-128GB)
        final_max = min(adjusted_max, 8)  # Can handle 8+ concurrent
    elif available_memory_gb >= 32:  # Mid-high systems (32-64GB)
        final_max = min(adjusted_max, 6)  # Can handle 6+ concurrent
    elif available_memory_gb >= 16:  # Standard systems (16-32GB)
        final_max = min(adjusted_max, 3)  # Can handle 3+ concurrent
    else:  # Lower-end systems (<16GB)
        final_max = min(adjusted_max, 2)  # Conservative for low-end systems

    logger.info(
        f"Memory budget: {usable_memory:.1f}GB usable, {total_memory_per_video:.1f}GB per video"
    )
    logger.info(
        f"Concurrency limits: memory={memory_based_max}, cpu={cpu_based_max}, pressure={adjusted_max}, final={final_max}"
    )

    return max(1, final_max)


def batch_process_with_progress(
    items: list[str | Path],
    processor_class,
    processor_kwargs: dict[str, Any] = None,
    processing_kwargs: dict[str, Any] = None,
    max_concurrent: int = 2,
    strategy: BatchStrategy = BatchStrategy.PARALLEL_FILES,
    progress_callback: Callable | None = None,
) -> list[BatchResult]:
    """
    Process a batch of items with progress tracking.

    Args:
        items: List of file paths or URLs to process
        processor_class: Class to instantiate for processing (e.g., AudioProcessor)
        processor_kwargs: Arguments for processor initialization
        processing_kwargs: Arguments for processing each item
        max_concurrent: Maximum concurrent processing tasks
        strategy: Batch processing strategy
        progress_callback: Function to call for progress updates

    Returns:
        List of batch processing results
    """
    processor_kwargs = processor_kwargs or {}
    processing_kwargs = processing_kwargs or {}

    # Create batch items
    batch_items = create_batch_from_files([Path(item) for item in items])

    # Initialize processor
    processor = processor_class(**processor_kwargs)

    # Create batch processor
    batch_processor = BatchProcessor(
        max_concurrent_files=max_concurrent,
        strategy=strategy,
        progress_callback=progress_callback,
    )

    # Process the batch
    return batch_processor.process_batch(
        batch_items,
        processor,
        transcription_kwargs=processing_kwargs,
    )


def aggregate_hce_analytics(batch_results: list[BatchResult]) -> dict[str, Any]:
    """Aggregate HCE analytics across batch results for comprehensive reporting.

    Args:
        batch_results: List of batch processing results with HCE analytics

    Returns:
        Aggregated HCE analytics across the entire batch
    """
    aggregated = {
        "total_files_processed": len(batch_results),
        "successful_files": sum(1 for r in batch_results if r.success),
        "total_claims": 0,
        "tier_a_claims": 0,
        "tier_b_claims": 0,
        "tier_c_claims": 0,
        "total_people": 0,
        "total_concepts": 0,
        "total_relations": 0,
        "total_contradictions": 0,
        "unique_people": set(),
        "unique_concepts": set(),
        "cross_file_patterns": [],
        "processing_time_total": sum(r.processing_time for r in batch_results),
        "files_with_contradictions": 0,
        "avg_claims_per_file": 0,
    }

    # Aggregate analytics from successful results
    successful_results = [r for r in batch_results if r.success and r.hce_analytics]

    for result in successful_results:
        analytics = result.hce_analytics

        # Aggregate claim counts
        aggregated["total_claims"] += analytics.get("total_claims", 0)
        aggregated["tier_a_claims"] += analytics.get("tier_a_count", 0)
        aggregated["tier_b_claims"] += analytics.get("tier_b_count", 0)
        aggregated["tier_c_claims"] += analytics.get("tier_c_count", 0)

        # Aggregate entity counts
        aggregated["total_people"] += analytics.get("people_count", 0)
        aggregated["total_concepts"] += analytics.get("concepts_count", 0)
        aggregated["total_relations"] += analytics.get("relations_count", 0)
        aggregated["total_contradictions"] += analytics.get("contradictions_count", 0)

        # Track unique entities across files
        for person in analytics.get("top_people", []):
            if person:
                aggregated["unique_people"].add(person)

        for concept in analytics.get("top_concepts", []):
            if concept:
                aggregated["unique_concepts"].add(concept)

        # Track files with contradictions
        if analytics.get("contradictions_count", 0) > 0:
            aggregated["files_with_contradictions"] += 1

    # Calculate derived metrics
    if successful_results:
        aggregated["avg_claims_per_file"] = aggregated["total_claims"] / len(
            successful_results
        )
        aggregated["avg_processing_time"] = aggregated["processing_time_total"] / len(
            successful_results
        )

    # Convert sets to lists for JSON serialization
    aggregated["unique_people"] = list(aggregated["unique_people"])
    aggregated["unique_concepts"] = list(aggregated["unique_concepts"])

    # Identify cross-file patterns
    if len(aggregated["unique_people"]) < aggregated["total_people"]:
        aggregated["cross_file_patterns"].append(
            "People mentioned across multiple files"
        )

    if len(aggregated["unique_concepts"]) < aggregated["total_concepts"]:
        aggregated["cross_file_patterns"].append(
            "Concepts discussed across multiple files"
        )

    if aggregated["files_with_contradictions"] > 1:
        aggregated["cross_file_patterns"].append(
            "Contradictions found in multiple files"
        )

    logger.info(
        f"Aggregated HCE analytics: {aggregated['total_claims']} claims across {len(successful_results)} files"
    )
    return aggregated


# Testing
def test_batch_processing():
    """Test the batch processing utilities."""
    print("📦 Batch Processing Test")
    print("=" * 25)

    # Create mock batch items
    import tempfile

    tmp_dir = Path(tempfile.gettempdir())
    mock_files = [
        tmp_dir / "audio1.wav",
        tmp_dir / "audio2.wav",
        tmp_dir / "audio3.wav",
        tmp_dir / "audio4.wav",
    ]

    # Test batch creation
    items = create_batch_from_files(mock_files, priorities=[2, 1, 3, 1])
    print(f"✅ Created batch with {len(items)} items")

    # Test strategy determination
    strategy, max_concurrent = determine_optimal_batch_strategy(
        file_count=len(items),
        average_file_duration=300,  # 5 minutes
        available_cores=8,
        available_memory_gb=16,
    )

    print(
        f"✅ Recommended strategy: {strategy.value} with {max_concurrent} concurrent files"
    )

    # Test batch processor initialization
    processor = BatchProcessor(max_concurrent_files=max_concurrent, strategy=strategy)

    print("✅ Batch processor initialized")

    print("✅ All batch processing tests passed")


if __name__ == "__main__":
    test_batch_processing()
