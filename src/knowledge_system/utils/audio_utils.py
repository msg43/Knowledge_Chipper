"""
FFmpeg-based audio processing utilities to replace pydub functionality

FFmpeg-based audio processing utilities to replace pydub functionality.
Compatible with Python 3.13+ and provides the same core functionality.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from knowledge_system.logger import get_logger

logger = get_logger(__name__)


class FFmpegAudioProcessor:
    """FFmpeg-based audio processor to replace pydub functionality."""

    def __init__(self) -> None:
        self._ffmpeg_path: str | None = None
        self._ffprobe_path: str | None = None
        self._check_ffmpeg_available()

    def _resolve_binary(self, name: str) -> str | None:
        """
        Resolve absolute path to ffmpeg/ffprobe

        Resolution order:
        1) Environment variable FFMPEG_PATH/FFPROBE_PATH (absolute path)
        2) PATH lookup via shutil.which
        """
        # 1) Environment override

        # 1) Environment override
        env_key = "FFMPEG_PATH" if name == "ffmpeg" else "FFPROBE_PATH"
        env_path = os.environ.get(env_key)
        if env_path:
            candidate = Path(env_path).expanduser()
            if candidate.exists() and os.access(candidate, os.X_OK):
                return str(candidate)

        # 2) PATH search
        which_path = shutil.which(name)
        if which_path:
            return which_path

        return None

    def _check_ffmpeg_available(self) -> bool:
        """Check if FFmpeg is available on the system."""
        self._ffmpeg_path = self._resolve_binary("ffmpeg")
        self._ffprobe_path = self._resolve_binary("ffprobe")

        if self._ffmpeg_path and self._ffprobe_path:
            try:
                subprocess.run(
                    [self._ffmpeg_path, "-version"], capture_output=True, check=True
                )
                return True
            except Exception:
                pass

        logger.info(
            "FFmpeg not found. You can install it via Homebrew (brew install ffmpeg) or use Settings → FFmpeg to choose/install a binary."
        )
        return False

    def remove_silence(
        self,
        input_path: str | Path,
        output_path: str | Path,
        silence_threshold: str = "-50dB",
        min_silence_duration: float = 2.0,
        progress_callback: callable = None,
    ) -> bool:
        """
        Remove long silence periods from audio to prevent Whisper hallucinations.

        This preprocesses audio by removing extended silence/dead air that can cause
        the Whisper model to "wander" and start hallucinating repetitive phrases.

        Args:
            input_path: Input audio file path
            output_path: Output audio file path
            silence_threshold: Volume threshold for silence detection (default: -50dB)
            min_silence_duration: Minimum silence duration to remove in seconds (default: 2.0)
            progress_callback: Optional callback for progress updates

        Returns:
            True if silence removal successful, False otherwise

        Note:
            - Preserves natural pauses < min_silence_duration (breathing, speech gaps)
            - Only removes extended dead air that causes model drift
            - Helps prevent hallucination during long silence periods
        """
        if not self._ffmpeg_path:
            logger.warning("FFmpeg not available for silence removal")
            return False

        try:
            input_path = Path(input_path)
            output_path = Path(output_path)

            if progress_callback:
                progress_callback("🔇 Removing long silence periods...", None)

            # FFmpeg silenceremove filter
            # stop_periods=-1: Process all silence
            # stop_duration: Minimum silence duration to remove
            # stop_threshold: Volume level considered as silence
            cmd = [
                self._ffmpeg_path,
                "-i",
                str(input_path),
                "-af",
                f"silenceremove=stop_periods=-1:stop_duration={min_silence_duration}:stop_threshold={silence_threshold}",
                "-y",  # Overwrite output
                str(output_path),
            ]

            logger.debug(f"Running silence removal: {' '.join(cmd)}")

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300  # 5 minute timeout
            )

            if result.returncode == 0 and output_path.exists():
                logger.info(f"✅ Silence removal completed: {output_path}")
                return True
            else:
                logger.error(f"Silence removal failed: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("Silence removal timed out after 5 minutes")
            return False
        except Exception as e:
            logger.error(f"Error during silence removal: {e}")
            return False

    def convert_audio(
        self,
        input_path: str | Path,
        output_path: str | Path,
        target_format: str = "wav",
        normalize: bool = False,
        sample_rate: int | None = None,
        channels: int | None = None,
        progress_callback: callable = None,
        remove_silence: bool = False,
    ) -> bool:
        """
        Convert audio file to target format using FFmpeg with non-blocking execution.

        Args:
            input_path: Input audio file path
            output_path: Output audio file path
            target_format: Target format (wav, mp3, flac, etc.)
            normalize: Whether to normalize audio levels
            sample_rate: Target sample rate (default: keep original)
            channels: Target number of channels (default: keep original)
            progress_callback: Optional callback for progress updates
            remove_silence: Whether to remove long silence periods (helps prevent hallucinations)

        Returns:
            True if conversion successful, False otherwise
        """

        try:
            input_path = Path(input_path)
            output_path = Path(output_path)

            # If silence removal is requested, do it first in a temporary file
            temp_file = None
            if remove_silence:
                temp_file = (
                    output_path.parent / f"temp_silence_removed_{output_path.name}"
                )
                if self.remove_silence(
                    input_path, temp_file, progress_callback=progress_callback
                ):
                    input_path = temp_file
                    logger.info("✅ Silence removal preprocessing completed")
                else:
                    logger.warning(
                        "⚠️ Silence removal failed, continuing with original audio"
                    )

            # Build FFmpeg command with performance optimizations
            ffmpeg = self._ffmpeg_path or self._resolve_binary("ffmpeg") or "ffmpeg"
            cmd = [
                ffmpeg,
                "-threads", "0",  # Use all available CPU cores
                "-i", str(input_path),
            ]

            # Add progress reporting for FFmpeg (use stderr with stats)
            # Note: We'll parse stderr for time= progress instead of -progress
            cmd.extend(["-stats"])

            # Add audio filters for normalization
            if normalize:
                cmd.extend(["-af", "loudnorm"])

            # Add sample rate conversion
            if sample_rate:
                cmd.extend(["-ar", str(sample_rate)])

            # Add channel conversion
            if channels:
                cmd.extend(["-ac", str(channels)])

            # For WAV output, use explicit PCM codec for speed
            if target_format.lower() == "wav":
                cmd.extend(["-acodec", "pcm_s16le"])  # 16-bit PCM, fastest encoding

            # Add output format and file
            cmd.extend(["-y", str(output_path)])  # -y to overwrite

            # Run FFmpeg with real-time progress monitoring using threading
            import queue
            import threading
            import time

            # Create a queue for progress updates from the reader thread
            progress_queue = queue.Queue()

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
            )

            # Thread to read FFmpeg progress output without blocking
            def read_progress():
                """Read FFmpeg progress output from stderr in a separate thread."""
                try:
                    # FFmpeg outputs progress to stderr, not stdout
                    for line in process.stderr:
                        progress_queue.put(("line", line.strip()))
                except Exception as e:
                    progress_queue.put(("error", str(e)))
                finally:
                    progress_queue.put(("done", None))

            reader_thread = threading.Thread(target=read_progress, daemon=True)
            reader_thread.start()

            start_time = time.time()

            # Calculate audio duration for timeout and progress
            total_duration = self._get_audio_duration_quick(input_path)

            # Provide initial progress update
            if progress_callback:
                input_size_mb = input_path.stat().st_size / (1024 * 1024)
                if total_duration:
                    progress_callback(
                        f"🔄 Converting {input_path.name} ({input_size_mb:.1f}MB, {total_duration/60:.1f}min) to 16kHz mono...",
                        0,
                    )
                else:
                    progress_callback(
                        f"🔄 Converting {input_path.name} ({input_size_mb:.1f}MB) to 16kHz mono...",
                        0,
                    )

            # Calculate reasonable timeout based on input duration
            if total_duration:
                # Rule of thumb: FFmpeg typically converts at 10-50x real-time speed
                # Use very conservative estimate: 2x real-time + 5 minute buffer
                timeout_seconds = max(
                    600, total_duration * 2 + 300
                )  # Minimum 10 minutes
                logger.info(
                    f"Setting conversion timeout to {timeout_seconds/60:.1f} minutes for {total_duration/60:.1f} minute audio"
                )
            else:
                # Unknown duration - use generous default
                timeout_seconds = 3600  # 1 hour default
                logger.info("Could not determine audio duration, using 1 hour timeout")

            try:
                # Parse FFmpeg progress output in real-time from queue
                # Optimized: reduced polling frequency to minimize CPU overhead
                last_progress_time = time.time()
                last_progress_update = time.time()
                lines_received = 0
                progress_updates_sent = 0
                reader_done = False

                while True:
                    # Check if process has finished
                    poll_result = process.poll()
                    if poll_result is not None and reader_done:
                        break

                    # Try to get progress lines from queue
                    # Use 0.5s timeout to reduce polling overhead (was 0.1s)
                    try:
                        msg_type, msg_data = progress_queue.get(timeout=0.5)

                        if msg_type == "done":
                            reader_done = True
                            continue
                        elif msg_type == "error":
                            logger.warning(f"Progress reader error: {msg_data}")
                            continue
                        elif msg_type == "line":
                            line = msg_data

                            if line and "time=" in line:
                                lines_received += 1
                                try:
                                    # Extract time value (format: HH:MM:SS.MS or MM:SS.MS)
                                    time_match = line.split("time=")[1].split()[0]

                                    # Parse time string to seconds
                                    time_parts = time_match.split(":")
                                    if len(time_parts) == 3:  # HH:MM:SS.MS
                                        hours = float(time_parts[0])
                                        minutes = float(time_parts[1])
                                        seconds = float(time_parts[2])
                                        current_time = (
                                            hours * 3600 + minutes * 60 + seconds
                                        )
                                    elif len(time_parts) == 2:  # MM:SS.MS
                                        minutes = float(time_parts[0])
                                        seconds = float(time_parts[1])
                                        current_time = minutes * 60 + seconds
                                    else:
                                        continue

                                    if total_duration and total_duration > 0:
                                        percent = min(
                                            95,
                                            (current_time / total_duration) * 100,
                                        )

                                        # Only update every 5 seconds to reduce overhead (was 2s)
                                        if progress_callback and (
                                            time.time() - last_progress_time > 5.0
                                        ):
                                            progress_callback(
                                                f"🔄 Converting audio: {percent:.0f}% ({current_time:.0f}s / {total_duration:.0f}s)",
                                                int(percent),
                                            )
                                            last_progress_time = time.time()
                                            last_progress_update = time.time()
                                            progress_updates_sent += 1
                                except (
                                    ValueError,
                                    IndexError,
                                    AttributeError,
                                ):
                                    pass
                    except queue.Empty:
                        # No progress data available yet
                        pass

                    # Show periodic "still working" message if no progress updates (every 15s)
                    if progress_callback and (
                        time.time() - last_progress_update > 15.0
                    ):
                        elapsed = time.time() - start_time
                        if total_duration:
                            # Estimate progress based on typical FFmpeg speed (~30x realtime)
                            estimated_percent = min(95, (elapsed * 30 / total_duration) * 100)
                            remaining_time = max(0, (total_duration / 30) - elapsed)
                            progress_callback(
                                f"🔄 Converting audio... (~{estimated_percent:.0f}%, {elapsed:.0f}s elapsed)",
                                int(estimated_percent),
                            )
                        else:
                            progress_callback(
                                f"🔄 Converting audio... ({elapsed:.0f}s elapsed)", 0
                            )
                        last_progress_update = time.time()

                    # Check timeout
                    if time.time() - start_time > timeout_seconds:
                        raise subprocess.TimeoutExpired(cmd, timeout_seconds)

                # Get final stderr output
                _, stderr = process.communicate(timeout=5)

                # Success progress update
                if progress_callback:
                    elapsed = time.time() - start_time
                    progress_callback(f"✅ Conversion completed in {elapsed:.1f}s", 100)

                # Log progress parsing statistics
                logger.info(
                    f"FFmpeg progress stats: {lines_received} lines received, "
                    f"{progress_updates_sent} progress updates sent, "
                    f"elapsed: {elapsed:.1f}s"
                )

            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                timeout_mins = timeout_seconds / 60
                logger.error(
                    f"FFmpeg conversion timed out after {timeout_mins:.1f} minutes"
                )
                if progress_callback:
                    progress_callback(
                        f"Conversion timed out after {timeout_mins:.1f}min", 0
                    )
                return False

            if process.returncode != 0:
                logger.error(f"FFmpeg conversion failed with code {process.returncode}")
                logger.error(f"FFmpeg stderr: {stderr}")
                # Clean up temp file if it exists
                if temp_file and temp_file.exists():
                    temp_file.unlink()
                return False

            if output_path.exists() and output_path.stat().st_size > 0:
                logger.info(f"Successfully converted {input_path} to {output_path}")
                # Clean up temp file if it exists
                if temp_file and temp_file.exists():
                    temp_file.unlink()
                return True
            else:
                logger.error(
                    "FFmpeg conversion failed: output file is empty or missing"
                )
                # Clean up temp file if it exists
                if temp_file and temp_file.exists():
                    temp_file.unlink()
                return False

        except Exception as e:
            logger.error(f"Audio conversion error: {e}")
            # Clean up temp file if it exists
            if temp_file and temp_file.exists():
                temp_file.unlink()
            return False

    def _get_audio_duration_quick(self, file_path: Path) -> float | None:
        """Get audio duration quickly for progress calculation."""
        try:
            ffprobe = self._ffprobe_path or self._resolve_binary("ffprobe") or "ffprobe"
            cmd = [
                ffprobe,
                "-v",
                "quiet",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                str(file_path),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return float(result.stdout.strip())
        except Exception:
            pass
        return None

    def get_audio_metadata(self, file_path: str | Path) -> dict[str, Any]:
        """
        Extract audio metadata using ffprobe
        Extract audio metadata using ffprobe.

        Args:
            file_path: Path to audio file

        Returns:
            Dictionary containing audio metadata
        """

        try:
            file_path = Path(file_path)

            # Get format information
            ffprobe = self._ffprobe_path or self._resolve_binary("ffprobe") or "ffprobe"
            format_cmd = [
                ffprobe,
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(file_path),
            ]

            result = subprocess.run(
                format_cmd, capture_output=True, text=True, check=True
            )
            data = json.loads(result.stdout)

            metadata = {
                "filename": file_path.name,
                "file_path": str(file_path),
                "file_size": file_path.stat().st_size if file_path.exists() else 0,
                "file_extension": file_path.suffix.lower(),
            }

            # Extract format information
            if "format" in data:
                format_info = data["format"]
                metadata.update(
                    {
                        "duration": format_info.get("duration"),
                        "bit_rate": format_info.get("bit_rate"),
                        "format_name": format_info.get("format_name"),
                        "format_long_name": format_info.get("format_long_name"),
                        "tags": format_info.get("tags", {}),
                    }
                )

            # Extract audio stream information
            if "streams" in data:
                audio_streams = [
                    s for s in data["streams"] if s.get("codec_type") == "audio"
                ]

                if audio_streams:
                    audio = audio_streams[0]  # First audio stream
                    metadata.update(
                        {
                            "audio_codec": audio.get("codec_name"),
                            "audio_codec_long": audio.get("codec_long_name"),
                            "sample_rate": audio.get("sample_rate"),
                            "channels": audio.get("channels"),
                            "channel_layout": audio.get("channel_layout"),
                            "bits_per_sample": audio.get("bits_per_sample"),
                            "audio_bit_rate": audio.get("bit_rate"),
                        }
                    )

            return metadata

        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to extract metadata from {file_path}: {e}")
            return {}
        except Exception as e:
            logger.warning(f"Error extracting metadata from {file_path}: {e}")
            return {}

    def get_audio_duration(self, file_path: str | Path) -> float | None:
        """
        Get audio duration in seconds using ffprobe
        Get audio duration in seconds using ffprobe.

        Args:
            file_path: Path to audio file

        Returns:
            Duration in seconds, or None if extraction failed
        """

        try:
            file_path = Path(file_path)

            ffprobe = self._ffprobe_path or self._resolve_binary("ffprobe") or "ffprobe"
            cmd = [
                ffprobe,
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
                duration = float(result.stdout.strip())
                return duration
            else:
                logger.warning(f"Could not extract audio duration from {file_path}")
                return None

        except Exception as e:
            logger.warning(f"Failed to get audio duration: {e}")
            return None

    def normalize_audio(self, input_path: str | Path, output_path: str | Path) -> bool:
        """
        Normalize audio levels using FFmpeg
        Normalize audio levels using FFmpeg.

        Args:
            input_path: Input audio file path
            output_path: Output audio file path

        Returns:
            True if normalization successful, False otherwise
        """

        try:
            input_path = Path(input_path)
            output_path = Path(output_path)

            # Use FFmpeg's loudnorm filter for audio normalization
            ffmpeg = self._ffmpeg_path or self._resolve_binary("ffmpeg") or "ffmpeg"
            cmd = [
                ffmpeg,
                "-i",
                str(input_path),
                "-af",
                "loudnorm=I=-16:TP=-1.5:LRA=11",  # Standard normalization
                "-y",
                str(output_path),
            ]

            subprocess.run(cmd, capture_output=True, check=True)

            if output_path.exists() and output_path.stat().st_size > 0:
                logger.info(f"Successfully normalized {input_path} to {output_path}")
                return True
            else:
                logger.error(
                    "Audio normalization failed: output file is empty or missing"
                )
                return False

        except subprocess.CalledProcessError as e:
            logger.error(f"Audio normalization failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Audio normalization error: {e}")
            return False


# Global instance for easy access
ffmpeg_processor = FFmpegAudioProcessor()


def convert_audio_file(
    input_path: str | Path,
    output_path: str | Path,
    target_format: str = "wav",
    normalize: bool = False,
    sample_rate: int | None = None,
    channels: int | None = None,
    progress_callback: callable = None,
    remove_silence: bool = False,
) -> bool:
    """Convenience function for audio conversion with optional silence removal."""
    return ffmpeg_processor.convert_audio(
        input_path,
        output_path,
        target_format,
        normalize,
        sample_rate,
        channels,
        progress_callback,
        remove_silence,
    )


def get_audio_metadata(file_path: str | Path) -> dict[str, Any]:
    """Convenience function for getting audio metadata."""
    return ffmpeg_processor.get_audio_metadata(file_path)


def get_audio_duration(file_path: str | Path) -> float | None:
    """Convenience function for getting audio duration."""
    return ffmpeg_processor.get_audio_duration(file_path)


def normalize_audio_file(input_path: str | Path, output_path: str | Path) -> bool:
    """Convenience function for audio normalization."""
    return ffmpeg_processor.normalize_audio(input_path, output_path)
