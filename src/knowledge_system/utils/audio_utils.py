"""
FFmpeg-based audio processing utilities to replace pydub functionality.
Compatible with Python 3.13+ and provides the same core functionality.
"""

import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, Union
import json
from knowledge_system.logger import get_logger

logger = get_logger(__name__)


class FFmpegAudioProcessor:
    """FFmpeg-based audio processor to replace pydub functionality."""
    
    def __init__(self):
        self._check_ffmpeg_available()
    
    def _check_ffmpeg_available(self) -> bool:
        """Check if FFmpeg is available on the system."""
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.error("FFmpeg not found. Please install FFmpeg: brew install ffmpeg")
            return False
    
    def convert_audio(
        self, 
        input_path: Union[str, Path], 
        output_path: Union[str, Path],
        target_format: str = "wav",
        normalize: bool = False,
        sample_rate: Optional[int] = None,
        channels: Optional[int] = None
    ) -> bool:
        """
        Convert audio file to target format using FFmpeg.
        
        Args:
            input_path: Input audio file path
            output_path: Output audio file path
            target_format: Target format (wav, mp3, flac, etc.)
            normalize: Whether to normalize audio levels
            sample_rate: Target sample rate (default: keep original)
            channels: Target number of channels (default: keep original)
        
        Returns:
            True if conversion successful, False otherwise
        """
        try:
            input_path = Path(input_path)
            output_path = Path(output_path)
            
            # Build FFmpeg command
            cmd = ["ffmpeg", "-i", str(input_path)]
            
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
            
            # Run FFmpeg
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            if output_path.exists() and output_path.stat().st_size > 0:
                logger.info(f"Successfully converted {input_path} to {output_path}")
                return True
            else:
                logger.error(f"FFmpeg conversion failed: output file is empty or missing")
                return False
                
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg conversion failed: {e}")
            logger.error(f"FFmpeg stderr: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Audio conversion error: {e}")
            return False
    
    def get_audio_metadata(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Extract audio metadata using ffprobe.
        
        Args:
            file_path: Path to audio file
            
        Returns:
            Dictionary containing audio metadata
        """
        try:
            file_path = Path(file_path)
            
            # Get format information
            format_cmd = [
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_format", "-show_streams", str(file_path)
            ]
            
            result = subprocess.run(format_cmd, capture_output=True, text=True, check=True)
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
                metadata.update({
                    "duration": format_info.get("duration"),
                    "bit_rate": format_info.get("bit_rate"),
                    "format_name": format_info.get("format_name"),
                    "format_long_name": format_info.get("format_long_name"),
                    "tags": format_info.get("tags", {}),
                })
            
            # Extract audio stream information
            if "streams" in data:
                audio_streams = [
                    s for s in data["streams"] if s.get("codec_type") == "audio"
                ]
                
                if audio_streams:
                    audio = audio_streams[0]  # First audio stream
                    metadata.update({
                        "audio_codec": audio.get("codec_name"),
                        "audio_codec_long": audio.get("codec_long_name"),
                        "sample_rate": audio.get("sample_rate"),
                        "channels": audio.get("channels"),
                        "channel_layout": audio.get("channel_layout"),
                        "bits_per_sample": audio.get("bits_per_sample"),
                        "audio_bit_rate": audio.get("bit_rate"),
                    })
            
            return metadata
            
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to extract metadata from {file_path}: {e}")
            return {}
        except Exception as e:
            logger.warning(f"Error extracting metadata from {file_path}: {e}")
            return {}
    
    def get_audio_duration(self, file_path: Union[str, Path]) -> Optional[float]:
        """
        Get audio duration in seconds using ffprobe.
        
        Args:
            file_path: Path to audio file
            
        Returns:
            Duration in seconds, or None if extraction failed
        """
        try:
            file_path = Path(file_path)
            
            cmd = [
                "ffprobe", "-v", "quiet", "-show_entries", 
                "format=duration", "-of", "csv=p=0", str(file_path)
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
    
    def normalize_audio(
        self, 
        input_path: Union[str, Path], 
        output_path: Union[str, Path]
    ) -> bool:
        """
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
            cmd = [
                "ffmpeg", "-i", str(input_path),
                "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",  # Standard normalization
                "-y", str(output_path)
            ]
            
            subprocess.run(cmd, capture_output=True, check=True)
            
            if output_path.exists() and output_path.stat().st_size > 0:
                logger.info(f"Successfully normalized {input_path} to {output_path}")
                return True
            else:
                logger.error("Audio normalization failed: output file is empty or missing")
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
    input_path: Union[str, Path],
    output_path: Union[str, Path],
    target_format: str = "wav",
    normalize: bool = False,
    sample_rate: Optional[int] = None,
    channels: Optional[int] = None
) -> bool:
    """Convenience function for audio conversion."""
    return ffmpeg_processor.convert_audio(
        input_path, output_path, target_format, normalize, sample_rate, channels
    )


def get_audio_metadata(file_path: Union[str, Path]) -> Dict[str, Any]:
    """Convenience function for getting audio metadata."""
    return ffmpeg_processor.get_audio_metadata(file_path)


def get_audio_duration(file_path: Union[str, Path]) -> Optional[float]:
    """Convenience function for getting audio duration."""
    return ffmpeg_processor.get_audio_duration(file_path)


def normalize_audio_file(
    input_path: Union[str, Path],
    output_path: Union[str, Path]
) -> bool:
    """Convenience function for audio normalization."""
    return ffmpeg_processor.normalize_audio(input_path, output_path) 