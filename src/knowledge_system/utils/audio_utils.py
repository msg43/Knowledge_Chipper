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

    def convert_audio(
        self,
        input_path: str | Path,
        output_path: str | Path,
        target_format: str = "wav",
        normalize: bool = False,
        sample_rate: int | None = None,
        channels: int | None = None,
        progress_callback: callable = None,
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

        Returns:
            True if conversion successful, False otherwise
        """

        try:
            input_path = Path(input_path)
            output_path = Path(output_path)

            # Build FFmpeg command
            ffmpeg = self._ffmpeg_path or self._resolve_binary("ffmpeg") or "ffmpeg"
            cmd = [ffmpeg, "-i", str(input_path)]

            # Add progress reporting for FFmpeg
            cmd.extend(["-progress", "pipe:1"])

            # Add audio filters for normalization
            if normalize:
                cmd.extend(["-af", "loudnorm"])

            # Add sample rate conversion
            if sample_rate:
                cmd.extend(["-ar", str(sample_rate)])

            # Add channel conversion
            if channels:
                cmd.extend(["-ac", str(channels)])

            # Add output format and file
            cmd.extend(["-y", str(output_path)])  # -y to overwrite

            # Run FFmpeg with non-blocking approach
            import threading
            import time

            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )

            # Simple approach: wait for completion with timeout and periodic progress updates
            start_time = time.time()

            # Provide initial progress update
            if progress_callback:
                progress_callback("Starting audio conversion...", 0)

            # Calculate reasonable timeout based on input duration
            total_duration = self._get_audio_duration_quick(input_path)
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
                # Wait for process completion with calculated timeout
                stdout, stderr = process.communicate(timeout=timeout_seconds)

                # Success progress update
                if progress_callback:
                    elapsed = time.time() - start_time
                    progress_callback(f"Conversion completed in {elapsed:.1f}s", 100)

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
                return False

            if output_path.exists() and output_path.stat().st_size > 0:
                logger.info(f"Successfully converted {input_path} to {output_path}")
                return True
            else:
                logger.error(
                    "FFmpeg conversion failed: output file is empty or missing"
                )
                return False

        except Exception as e:
            logger.error(f"Audio conversion error: {e}")
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
) -> bool:
    """Convenience function for audio conversion."""
    return ffmpeg_processor.convert_audio(
        input_path,
        output_path,
        target_format,
        normalize,
        sample_rate,
        channels,
        progress_callback,
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
