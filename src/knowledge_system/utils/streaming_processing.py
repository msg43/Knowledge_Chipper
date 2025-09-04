"""
Streaming processing utilities for real-time transcription and diarization.

This module provides utilities for processing very long audio files in chunks,
allowing transcription and diarization to work on segments simultaneously
instead of waiting for complete files.
"""

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from knowledge_system.logger import get_logger
from knowledge_system.processors.base import ProcessorResult

logger = get_logger(__name__)


@dataclass
class AudioChunk:
    """Represents a chunk of audio with timing information."""

    chunk_id: int
    start_time: float
    end_time: float
    file_path: Path
    duration: float


@dataclass
class ProcessingResult:
    """Result from processing an audio chunk."""

    chunk_id: int
    transcription: dict[str, Any] | None = None
    diarization: list[dict[str, Any]] | None = None
    success: bool = True
    errors: list[str] = None


class StreamingProcessor:
    """Manages streaming processing of long audio files."""

    def __init__(
        self,
        chunk_duration: float = 30.0,  # 30-second chunks
        overlap_duration: float = 5.0,  # 5-second overlap
        max_workers: int = 3,  # transcription, diarization, and coordination
        progress_callback: Callable | None = None,
    ):
        """
        Initialize streaming processor.

        Args:
            chunk_duration: Duration of each audio chunk in seconds
            overlap_duration: Overlap between chunks to ensure continuity
            max_workers: Maximum number of concurrent processing threads
            progress_callback: Optional callback for progress updates
        """
        self.chunk_duration = chunk_duration
        self.overlap_duration = overlap_duration
        self.max_workers = max_workers
        self.progress_callback = progress_callback
        self.executor = None

        # Processing state
        self.chunks: list[AudioChunk] = []
        self.results: dict[int, ProcessingResult] = {}
        self.completed_chunks: list[int] = []

    def __enter__(self):
        self.executor = ThreadPoolExecutor(
            max_workers=self.max_workers, thread_name_prefix="StreamingProcessor"
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.executor:
            self.executor.shutdown(wait=True)

    def create_audio_chunks(
        self, audio_path: Path, total_duration: float
    ) -> list[AudioChunk]:
        """
        Create audio chunk specifications for streaming processing.

        Args:
            audio_path: Path to the audio file
            total_duration: Total duration of the audio file in seconds

        Returns:
            List of AudioChunk objects
        """
        chunks = []
        chunk_id = 0
        current_time = 0.0

        while current_time < total_duration:
            end_time = min(current_time + self.chunk_duration, total_duration)

            chunk = AudioChunk(
                chunk_id=chunk_id,
                start_time=current_time,
                end_time=end_time,
                file_path=audio_path,
                duration=end_time - current_time,
            )

            chunks.append(chunk)

            # Move to next chunk with overlap
            current_time = end_time - self.overlap_duration
            if current_time >= total_duration - self.overlap_duration:
                break

            chunk_id += 1

        logger.info(
            f"Created {len(chunks)} chunks for {total_duration/60:.1f} minute audio"
        )
        return chunks

    def extract_audio_chunk(self, chunk: AudioChunk, output_dir: Path) -> Path | None:
        """
        Extract a specific chunk from the audio file using FFmpeg.

        Args:
            chunk: AudioChunk specification
            output_dir: Directory to save the extracted chunk

        Returns:
            Path to the extracted chunk file, or None if extraction failed
        """
        try:
            output_path = output_dir / f"chunk_{chunk.chunk_id:04d}.wav"

            # Use FFmpeg to extract the chunk
            import subprocess

            cmd = [
                "ffmpeg",
                "-y",  # Overwrite output files
                "-i",
                str(chunk.file_path),
                "-ss",
                str(chunk.start_time),
                "-t",
                str(chunk.duration),
                "-acodec",
                "pcm_s16le",  # Use uncompressed audio for best quality
                "-ar",
                "16000",  # 16kHz sample rate (good for speech)
                "-ac",
                "1",  # Mono
                str(output_path),
            ]

            # Use non-blocking subprocess execution with timeout
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                stdout, stderr = process.communicate(timeout=60)  # 1 minute timeout
                result = type('obj', (object,), {'returncode': process.returncode, 'stderr': stderr})
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                result = type('obj', (object,), {'returncode': -1, 'stderr': 'Process timed out'})

            if result.returncode == 0 and output_path.exists():
                logger.debug(
                    f"Extracted chunk {chunk.chunk_id}: {chunk.start_time:.1f}s - {chunk.end_time:.1f}s"
                )
                return output_path
            else:
                logger.error(
                    f"FFmpeg extraction failed for chunk {chunk.chunk_id}: {result.stderr}"
                )
                return None

        except Exception as e:
            logger.error(f"Error extracting chunk {chunk.chunk_id}: {e}")
            return None

    def process_chunk_streaming(
        self,
        chunk: AudioChunk,
        transcriber,
        diarizer,
        transcription_kwargs: dict[str, Any],
        diarization_kwargs: dict[str, Any],
        temp_dir: Path,
    ) -> ProcessingResult:
        """
        Process a single chunk with both transcription and diarization.

        Args:
            chunk: AudioChunk to process
            transcriber: Transcription processor
            diarizer: Diarization processor
            transcription_kwargs: Arguments for transcription
            diarization_kwargs: Arguments for diarization
            temp_dir: Temporary directory for chunk files

        Returns:
            ProcessingResult with transcription and diarization data
        """
        result = ProcessingResult(chunk_id=chunk.chunk_id)

        try:
            # Extract audio chunk
            chunk_path = self.extract_audio_chunk(chunk, temp_dir)
            if not chunk_path:
                result.success = False
                result.errors = ["Failed to extract audio chunk"]
                return result

            # Process transcription and diarization in parallel for this chunk
            transcription_future = self.executor.submit(
                self._process_transcription_chunk,
                transcriber,
                chunk_path,
                transcription_kwargs,
            )

            diarization_future = self.executor.submit(
                self._process_diarization_chunk,
                diarizer,
                chunk_path,
                diarization_kwargs,
            )

            # Wait for both to complete
            try:
                transcription_result = transcription_future.result(
                    timeout=300
                )  # 5 min timeout
                diarization_result = diarization_future.result(
                    timeout=300
                )  # 5 min timeout

                result.transcription = (
                    transcription_result.data if transcription_result.success else None
                )
                result.diarization = (
                    diarization_result.data if diarization_result.success else None
                )

                if not transcription_result.success or not diarization_result.success:
                    result.success = False
                    result.errors = []
                    if not transcription_result.success:
                        result.errors.extend(
                            transcription_result.errors or ["Transcription failed"]
                        )
                    if not diarization_result.success:
                        result.errors.extend(
                            diarization_result.errors or ["Diarization failed"]
                        )

            except TimeoutError:
                result.success = False
                result.errors = ["Chunk processing timed out"]

            # Clean up chunk file
            if chunk_path.exists():
                chunk_path.unlink()

        except Exception as e:
            logger.error(f"Error processing chunk {chunk.chunk_id}: {e}")
            result.success = False
            result.errors = [str(e)]

        return result

    def _process_transcription_chunk(
        self, transcriber, chunk_path: Path, kwargs: dict[str, Any]
    ) -> ProcessorResult:
        """Process transcription for a single chunk."""
        try:
            return transcriber.process(chunk_path, **kwargs)
        except Exception as e:
            logger.error(f"Transcription chunk error: {e}")
            return ProcessorResult(success=False, errors=[str(e)])

    def _process_diarization_chunk(
        self, diarizer, chunk_path: Path, kwargs: dict[str, Any]
    ) -> ProcessorResult:
        """Process diarization for a single chunk."""
        try:
            return diarizer.process(chunk_path, **kwargs)
        except Exception as e:
            logger.error(f"Diarization chunk error: {e}")
            return ProcessorResult(success=False, errors=[str(e)])

    def process_streaming(
        self,
        audio_path: Path,
        total_duration: float,
        transcriber,
        diarizer,
        transcription_kwargs: dict[str, Any],
        diarization_kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Process entire audio file using streaming chunks.

        Args:
            audio_path: Path to audio file
            total_duration: Total duration in seconds
            transcriber: Transcription processor
            diarizer: Diarization processor
            transcription_kwargs: Arguments for transcription
            diarization_kwargs: Arguments for diarization

        Returns:
            Combined results from all chunks
        """
        import tempfile

        if not self.executor:
            raise RuntimeError("StreamingProcessor not properly initialized")

        logger.info(
            f"Starting streaming processing of {total_duration/60:.1f} minute audio"
        )

        # Create chunks
        self.chunks = self.create_audio_chunks(audio_path, total_duration)

        # Create temporary directory for chunks
        with tempfile.TemporaryDirectory(prefix="streaming_chunks_") as temp_dir:
            temp_path = Path(temp_dir)

            # Submit all chunks for processing
            futures: dict[int, Future] = {}

            for chunk in self.chunks:
                future = self.executor.submit(
                    self.process_chunk_streaming,
                    chunk,
                    transcriber,
                    diarizer,
                    transcription_kwargs,
                    diarization_kwargs,
                    temp_path,
                )
                futures[chunk.chunk_id] = future

                if self.progress_callback:
                    self.progress_callback(
                        f"Submitted chunk {chunk.chunk_id + 1}/{len(self.chunks)} for processing"
                    )

            # Collect results as they complete
            completed = 0
            for chunk_id, future in futures.items():
                try:
                    result = future.result(timeout=600)  # 10 minute timeout per chunk
                    self.results[chunk_id] = result
                    completed += 1

                    if self.progress_callback:
                        progress = (completed / len(self.chunks)) * 100
                        self.progress_callback(
                            f"Completed chunk {completed}/{len(self.chunks)} ({progress:.1f}%)"
                        )

                    logger.info(
                        f"Completed chunk {chunk_id} ({completed}/{len(self.chunks)})"
                    )

                except Exception as e:
                    logger.error(f"Chunk {chunk_id} failed: {e}")
                    self.results[chunk_id] = ProcessingResult(
                        chunk_id=chunk_id, success=False, errors=[str(e)]
                    )

        # Combine results
        return self._combine_chunk_results()

    def _combine_chunk_results(self) -> dict[str, Any]:
        """Combine results from all processed chunks."""
        combined_transcription = {"text": "", "segments": [], "language": "unknown"}

        combined_diarization = []

        successful_chunks = 0
        total_chunks = len(self.chunks)

        # Sort chunks by ID to maintain order
        sorted_chunk_ids = sorted(self.results.keys())

        for chunk_id in sorted_chunk_ids:
            result = self.results[chunk_id]
            chunk = self.chunks[chunk_id]

            if result.success:
                successful_chunks += 1

                # Combine transcription
                if result.transcription:
                    text = result.transcription.get("text", "")
                    combined_transcription["text"] += text + " "

                    # Adjust segment timestamps to global timeline
                    segments = result.transcription.get("segments", [])
                    for segment in segments:
                        if "start" in segment:
                            segment["start"] += chunk.start_time
                        if "end" in segment:
                            segment["end"] += chunk.start_time
                        segment["chunk_id"] = chunk_id

                    combined_transcription["segments"].extend(segments)

                    # Use language from first successful chunk
                    if combined_transcription["language"] == "unknown":
                        combined_transcription["language"] = result.transcription.get(
                            "language", "unknown"
                        )

                # Combine diarization (adjust timestamps)
                if result.diarization:
                    for speaker_segment in result.diarization:
                        adjusted_segment = speaker_segment.copy()
                        if "start" in adjusted_segment:
                            adjusted_segment["start"] += chunk.start_time
                        if "end" in adjusted_segment:
                            adjusted_segment["end"] += chunk.start_time
                        adjusted_segment["chunk_id"] = chunk_id
                        combined_diarization.append(adjusted_segment)

        # Clean up combined text
        combined_transcription["text"] = combined_transcription["text"].strip()

        logger.info(
            f"Combined results: {successful_chunks}/{total_chunks} chunks successful"
        )
        logger.info(
            f"Total text length: {len(combined_transcription['text'])} characters"
        )
        logger.info(
            f"Total segments: {len(combined_transcription['segments'])} transcription, {len(combined_diarization)} diarization"
        )

        return {
            "transcription": combined_transcription,
            "diarization": combined_diarization,
            "chunks_processed": total_chunks,
            "chunks_successful": successful_chunks,
            "success_rate": successful_chunks / total_chunks if total_chunks > 0 else 0,
        }


def should_use_streaming_processing(
    audio_duration_seconds: float,
    memory_gb: float,
    min_duration_for_streaming: float = 1800,  # 30 minutes
) -> bool:
    """
    Determine if streaming processing should be used based on file duration and available memory.

    Args:
        audio_duration_seconds: Duration of audio file
        memory_gb: Available system memory in GB
        min_duration_for_streaming: Minimum duration to consider streaming (seconds)

    Returns:
        True if streaming processing is recommended
    """
    # Only use streaming for long files
    if audio_duration_seconds < min_duration_for_streaming:
        return False

    # Use streaming for very long files regardless of memory
    if audio_duration_seconds > 7200:  # 2 hours
        return True

    # For medium-length files, consider memory
    if memory_gb < 16 and audio_duration_seconds > 3600:  # 1 hour on systems with <16GB
        return True

    logger.info(
        f"Streaming processing recommended for {audio_duration_seconds/60:.1f} minute file"
    )
    return False


# Testing and example usage
def test_streaming_processing():
    """Test the streaming processing utilities."""
    print("🌊 Streaming Processing Test")
    print("=" * 30)

    # Test chunk creation
    test_duration = 3600  # 1 hour

    with StreamingProcessor(chunk_duration=30, overlap_duration=5) as processor:
        # Simulate audio file
        fake_path = Path("/tmp/test_audio.wav")
        chunks = processor.create_audio_chunks(fake_path, test_duration)

        print(f"✅ Created {len(chunks)} chunks for {test_duration/60:.0f} minute file")
        print(f"   Chunk duration: {processor.chunk_duration}s")
        print(f"   Overlap: {processor.overlap_duration}s")

        # Test streaming decision
        should_stream = should_use_streaming_processing(test_duration, 16.0)
        print(f"✅ Should use streaming: {should_stream}")

        # Show first few chunks
        for i, chunk in enumerate(chunks[:3]):
            print(
                f"   Chunk {chunk.chunk_id}: {chunk.start_time:.1f}s - {chunk.end_time:.1f}s"
            )
        if len(chunks) > 3:
            print(f"   ... and {len(chunks) - 3} more chunks")


if __name__ == "__main__":
    test_streaming_processing()
