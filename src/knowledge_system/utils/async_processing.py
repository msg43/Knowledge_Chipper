"""
Async processing utilities for parallel transcription and diarization.

This module provides utilities to run transcription and diarization in parallel
on Apple Silicon, taking advantage of the Neural Engine for transcription
and GPU for diarization simultaneously.
"""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from knowledge_system.logger import get_logger
from knowledge_system.processors.base import ProcessorResult

logger = get_logger(__name__)


class AsyncTranscriptionManager:
    """Manages parallel transcription and diarization processing."""

    def __init__(self, max_workers: int = 2):
        """
        Initialize the async manager.

        Args:
            max_workers: Maximum number of parallel workers (usually 2: transcription + diarization)
        """
        self.max_workers = max_workers
        self.executor = None

    def __enter__(self):
        self.executor = ThreadPoolExecutor(
            max_workers=self.max_workers, thread_name_prefix="AsyncTranscription"
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.executor:
            self.executor.shutdown(wait=True)

    def process_parallel(
        self,
        audio_path: Path,
        transcriber,
        diarizer,
        transcription_kwargs: dict[str, Any],
        diarization_kwargs: dict[str, Any],
        progress_callback: Callable | None = None,
    ) -> tuple[ProcessorResult, ProcessorResult | None]:
        """
        Process transcription and diarization in parallel.

        Args:
            audio_path: Path to audio file
            transcriber: Transcription processor instance
            diarizer: Diarization processor instance
            transcription_kwargs: Arguments for transcription
            diarization_kwargs: Arguments for diarization
            progress_callback: Optional callback for progress updates

        Returns:
            Tuple of (transcription_result, diarization_result)
        """
        if not self.executor:
            raise RuntimeError(
                "AsyncTranscriptionManager not properly initialized. Use with context manager."
            )

        logger.info("Starting parallel transcription and diarization")

        # Submit both tasks to the executor
        transcription_future = self.executor.submit(
            self._run_transcription,
            transcriber,
            audio_path,
            transcription_kwargs,
            progress_callback,
        )

        diarization_future = self.executor.submit(
            self._run_diarization,
            diarizer,
            audio_path,
            diarization_kwargs,
            progress_callback,
        )

        # Wait for both to complete
        transcription_result = None
        diarization_result = None

        try:
            # Use as_completed to handle whichever finishes first
            # Reduced timeout from 3600s (1 hour) to 1800s (30 minutes) for better stuck detection
            for future in as_completed(
                [transcription_future, diarization_future], timeout=1800
            ):
                try:
                    result = future.result()
                    if future == transcription_future:
                        transcription_result = result
                        if progress_callback:
                            progress_callback(
                                "Transcription completed, waiting for diarization..."
                            )
                        logger.info("✅ Transcription completed")
                    elif future == diarization_future:
                        diarization_result = result
                        if progress_callback:
                            progress_callback(
                                "Diarization completed, waiting for transcription..."
                            )
                        logger.info("✅ Diarization completed")
                except Exception as e:
                    logger.error(f"Task failed: {e}")
                    if future == transcription_future:
                        transcription_result = ProcessorResult(
                            success=False, errors=[str(e)]
                        )
                    elif future == diarization_future:
                        diarization_result = ProcessorResult(
                            success=False, errors=[str(e)]
                        )

        except TimeoutError:
            logger.error("Parallel processing timed out")
            transcription_result = ProcessorResult(
                success=False, errors=["Transcription timed out"]
            )
            diarization_result = ProcessorResult(
                success=False, errors=["Diarization timed out"]
            )

        logger.info("Parallel processing completed")
        return transcription_result, diarization_result

    def _run_transcription(
        self,
        transcriber,
        audio_path: Path,
        kwargs: dict[str, Any],
        progress_callback: Callable | None = None,
    ) -> ProcessorResult:
        """Run transcription in a separate thread with heartbeat monitoring."""
        import threading
        import time

        try:
            logger.info("🎯 Starting transcription (Neural Engine)")
            if progress_callback:
                progress_callback("Running transcription on Neural Engine...")

            # Add heartbeat mechanism for stuck detection
            last_heartbeat = threading.Event()

            def heartbeat():
                while not last_heartbeat.is_set():
                    time.sleep(30)  # Heartbeat every 30 seconds
                    if not last_heartbeat.is_set():
                        logger.debug("🎯 Transcription heartbeat - still processing...")

            heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
            heartbeat_thread.start()

            try:
                result = transcriber.process(audio_path, **kwargs)
            finally:
                last_heartbeat.set()  # Stop heartbeat

            if result.success:
                logger.info(
                    f"✅ Transcription successful: {len(result.data.get('text', ''))} characters"
                )
            else:
                logger.error(f"❌ Transcription failed: {result.errors}")

            return result

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return ProcessorResult(success=False, errors=[str(e)])

    def _run_diarization(
        self,
        diarizer,
        audio_path: Path,
        kwargs: dict[str, Any],
        progress_callback: Callable | None = None,
    ) -> ProcessorResult:
        """Run diarization in a separate thread with heartbeat monitoring."""
        import threading
        import time

        try:
            logger.info("🎭 Starting diarization (GPU)")
            if progress_callback:
                progress_callback("Running diarization on GPU...")

            # Add heartbeat mechanism for stuck detection
            last_heartbeat = threading.Event()

            def heartbeat():
                while not last_heartbeat.is_set():
                    time.sleep(30)  # Heartbeat every 30 seconds
                    if not last_heartbeat.is_set():
                        logger.debug("🎭 Diarization heartbeat - still processing...")

            heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
            heartbeat_thread.start()

            try:
                result = diarizer.process(audio_path, **kwargs)
            finally:
                last_heartbeat.set()  # Stop heartbeat

            if result.success:
                logger.info(
                    f"✅ Diarization successful: {len(result.data)} speaker segments"
                )
            else:
                logger.error(f"❌ Diarization failed: {result.errors}")

            return result

        except Exception as e:
            logger.error(f"Diarization error: {e}")
            return ProcessorResult(success=False, errors=[str(e)])


def should_use_parallel_processing(
    enable_diarization: bool, audio_duration_seconds: float, system_cores: int = 8
) -> bool:
    """
    Determine if parallel processing should be used.

    Args:
        enable_diarization: Whether diarization is enabled
        audio_duration_seconds: Duration of audio file
        system_cores: Number of CPU cores available

    Returns:
        True if parallel processing should be used
    """
    # Only use parallel processing if diarization is enabled
    if not enable_diarization:
        return False

    # Only worth it for longer files (overhead of parallelization)
    if audio_duration_seconds < 120:  # Less than 2 minutes
        return False

    # Need sufficient cores to handle parallel processing
    if system_cores < 4:
        return False

    logger.info(
        f"Parallel processing recommended for {audio_duration_seconds/60:.1f} minute file"
    )
    return True


def estimate_parallel_speedup(
    audio_duration_seconds: float,
    transcription_speed_factor: float = 0.1,  # 10% of real-time for Core ML
    diarization_speed_factor: float = 0.3,  # 30% of real-time for GPU diarization
) -> dict[str, float]:
    """
    Estimate the speedup from parallel processing.

    Args:
        audio_duration_seconds: Duration of audio file
        transcription_speed_factor: Transcription speed as fraction of real-time
        diarization_speed_factor: Diarization speed as fraction of real-time

    Returns:
        Dictionary with timing estimates
    """
    transcription_time = audio_duration_seconds * transcription_speed_factor
    diarization_time = audio_duration_seconds * diarization_speed_factor

    # Sequential: transcription + diarization
    sequential_time = transcription_time + diarization_time

    # Parallel: max(transcription, diarization) + small overhead
    parallel_time = max(transcription_time, diarization_time) * 1.1  # 10% overhead

    speedup = sequential_time / parallel_time

    return {
        "transcription_time": transcription_time,
        "diarization_time": diarization_time,
        "sequential_total": sequential_time,
        "parallel_total": parallel_time,
        "speedup_factor": speedup,
        "time_saved": sequential_time - parallel_time,
    }


# Example usage and testing
def test_async_processing():
    """Test the async processing utilities."""
    import platform

    print("🔄 Async Processing Test")
    print("=" * 30)

    # Test scenarios
    test_cases = [
        (60, True, 8),  # 1 minute, diarization enabled, 8 cores
        (300, True, 8),  # 5 minutes, diarization enabled, 8 cores
        (1800, True, 8),  # 30 minutes, diarization enabled, 8 cores
        (300, False, 8),  # 5 minutes, no diarization, 8 cores
        (300, True, 2),  # 5 minutes, diarization enabled, 2 cores
    ]

    for duration, diarization, cores in test_cases:
        should_parallel = should_use_parallel_processing(diarization, duration, cores)
        estimates = estimate_parallel_speedup(duration)

        print(
            f"\nTest: {duration/60:.1f}min file, diarization={diarization}, {cores} cores"
        )
        print(f"  Use parallel: {should_parallel}")
        if should_parallel:
            print(f"  Sequential time: {estimates['sequential_total']:.1f}s")
            print(f"  Parallel time: {estimates['parallel_total']:.1f}s")
            print(f"  Speedup: {estimates['speedup_factor']:.1f}x")
            print(f"  Time saved: {estimates['time_saved']:.1f}s")

    print(f"\nSystem: {platform.system()} {platform.machine()}")


if __name__ == "__main__":
    test_async_processing()
