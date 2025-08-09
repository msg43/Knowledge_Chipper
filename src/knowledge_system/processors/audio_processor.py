import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional, Union

from knowledge_system.logger import get_logger
from knowledge_system.processors.base import BaseProcessor, ProcessorResult
from knowledge_system.processors.whisper_cpp_transcribe import (
    WhisperCppTranscribeProcessor,
)
from knowledge_system.utils.audio_utils import (
    convert_audio_file,
    ffmpeg_processor,
    get_audio_duration,
    get_audio_metadata,
    normalize_audio_file,
)
from knowledge_system.utils.validation import can_process_file, validate_audio_input

logger = get_logger(__name__)

# whisper.cpp processor is now the default and only transcriber

# Check if FFmpeg is available for audio processing
FFMPEG_AVAILABLE = ffmpeg_processor._check_ffmpeg_available()

if not FFMPEG_AVAILABLE:
    logger.warning("FFmpeg not available. Audio processing will be limited.")
    logger.info("To enable full audio processing, install FFmpeg: brew install ffmpeg")


class AudioProcessor(BaseProcessor):
    """ Processes audio files for transcription pipeline with automatic retry and failure logging.""".

    def __init__(
        self,
        normalize_audio: bool = True,
        target_format: str = "wav",
        device: str | None = None,
        temp_dir: str | Path | None = None,
        use_whisper_cpp: bool = False,
        model: str = "base",
        progress_callback=None,
        enable_diarization: bool = False,
        hf_token: str | None = None,
        enable_quality_retry: bool = True,
        max_retry_attempts: int = 1,
    ) -> None:
        self.normalize_audio = normalize_audio
        self.target_format = target_format
        self.device = device
        self.temp_dir = Path(temp_dir) if temp_dir else None
        self.use_whisper_cpp = use_whisper_cpp
        self.model = model
        self.progress_callback = progress_callback
        self.enable_diarization = enable_diarization
        self.hf_token = hf_token
        self.enable_quality_retry = enable_quality_retry
        self.max_retry_attempts = max_retry_attempts

        # Use whisper.cpp as the default transcriber
        self.transcriber = WhisperCppTranscribeProcessor(
            model=model, progress_callback=progress_callback
        )

        # Model progression for retries (from smaller to larger for better accuracy)
        self.retry_models = {
            "tiny": "base",
            "base": "small",
            "small": "medium",
            "medium": "large",
            "large": "large",  # No upgrade from large
        }

    @property
    def supported_formats(self) -> list[str]:
        return [".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".mp4", ".webm"]

    def validate_input(self, input_data: str | Path) -> bool:
        if isinstance(input_data, (str, Path)):
            path = Path(input_data)
            return path.exists() and path.suffix.lower() in self.supported_formats
        return False

    def _convert_audio(self, input_path: Path, output_path: Path) -> bool:
        """ Convert audio file to target format using FFmpeg.""".
        if not FFMPEG_AVAILABLE:
            logger.warning("Audio conversion skipped - FFmpeg not available")
            logger.info(
                "To enable audio conversion, install FFmpeg: brew install ffmpeg"
            )
            return input_path.suffix.lower() == f".{self.target_format}"

        try:
            # Convert audio using FFmpeg
            success = convert_audio_file(
                input_path=input_path,
                output_path=output_path,
                target_format=self.target_format,
                normalize=self.normalize_audio,
            )

            if success:
                logger.info(f"Successfully converted {input_path} to {output_path}")
                return True
            else:
                logger.error(f"Failed to convert {input_path} to {output_path}")
                return False

        except Exception as e:
            logger.error(f"Audio conversion error: {e}")
            return False

    def _perform_diarization(self, audio_path: Path) -> list | None:
        """ Run speaker diarization on the audio file.""".
        try:
            from .diarization import (
                SpeakerDiarizationProcessor,
                get_diarization_installation_instructions,
                is_diarization_available,
            )

            # Check if diarization is available
            if not is_diarization_available():
                logger.warning(
                    "Diarization not available. Skipping speaker identification."
                )
                logger.info(get_diarization_installation_instructions())
                return None

            logger.info("Running speaker diarization...")
            diarizer = SpeakerDiarizationProcessor(hf_token=self.hf_token)
            result = diarizer.process(audio_path)
            if result.success:
                logger.info(
                    f"Diarization completed with {len(result.data)} speaker segments"
                )
                return result.data
            else:
                logger.warning(f"Diarization failed: {result.errors}")
                return None
        except Exception as e:
            logger.warning(f"Diarization failed: {e}")
            return None

    def _merge_diarization(
        self, transcription_data: dict, diarization_segments: list
    ) -> dict:
        """ Merge speaker labels into transcription segments.""".
        if not diarization_segments or "segments" not in transcription_data:
            return transcription_data

        logger.info(
            f"Merging {len(diarization_segments)} speaker segments with {len(transcription_data['segments'])} transcription segments"
        )

        # For each transcription segment, find overlapping speaker segments
        for transcript_segment in transcription_data["segments"]:
            start = transcript_segment.get("start", 0)
            end = transcript_segment.get("end", 0)

            # Find the speaker with the most overlap in this time range
            speaker = self._find_dominant_speaker(start, end, diarization_segments)
            if speaker:
                transcript_segment["speaker"] = speaker

        return transcription_data

    def _find_dominant_speaker(
        self, start: float, end: float, diarization_segments: list
    ) -> str | None:
        """ Find the speaker with the most overlap in the given time range.""".
        if not diarization_segments:
            return None

        speaker_overlaps = {}
        for segment in diarization_segments:
            seg_start = segment.get("start", 0)
            seg_end = segment.get("end", 0)
            speaker = segment.get("speaker", "Unknown")

            # Calculate overlap
            overlap_start = max(start, seg_start)
            overlap_end = min(end, seg_end)
            overlap = max(0, overlap_end - overlap_start)

            if overlap > 0:
                speaker_overlaps[speaker] = speaker_overlaps.get(speaker, 0) + overlap

        if speaker_overlaps:
            return max(speaker_overlaps, key=speaker_overlaps.get)
        return None

    def _log_transcription_failure(
        self,
        file_path: Path,
        failure_reason: str,
        model_used: str,
        audio_duration: float | None = None,
    ) -> None:
        """ Log transcription failure to a dedicated failure log file.""".
        try:
            # Create logs directory if it doesn't exist
            logs_dir = Path("logs")
            logs_dir.mkdir(parents=True, exist_ok=True)

            # Failure log file
            failure_log_path = logs_dir / "transcription_failures.log"

            timestamp = datetime.now().isoformat()
            duration_str = (
                f"{audio_duration:.1f}s ({audio_duration/60:.1f}min)"
                if audio_duration
                else "unknown"
            )

            log_entry = (
                f"[{timestamp}] TRANSCRIPTION FAILURE\n"
                f"  File: {file_path}\n"
                f"  Duration: {duration_str}\n"
                f"  Model: {model_used}\n"
                f"  Reason: {failure_reason}\n"
                f"  File Size: {file_path.stat().st_size / (1024*1024):.2f} MB\n"
                f"  File Format: {file_path.suffix}\n"
                f"{'='*80}\n"
            )

            with open(failure_log_path, "a", encoding="utf-8") as f:
                f.write(log_entry)

            logger.info(f"Transcription failure logged to {failure_log_path}")

        except Exception as e:
            logger.error(f"Failed to log transcription failure: {e}")

    def _get_audio_metadata(self, audio_path: Path) -> dict:
        """ Extract metadata from audio file.""".
        try:
            stat = audio_path.stat()
            metadata = {
                "filename": audio_path.name,
                "file_size_mb": round(stat.st_size / (1024 * 1024), 2),
                "created_date": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified_date": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "file_format": audio_path.suffix.lower().lstrip("."),
            }

            # Try to get audio duration if FFmpeg is available
            if FFMPEG_AVAILABLE:
                try:
                    duration_seconds = get_audio_duration(audio_path)
                    metadata["duration_seconds"] = duration_seconds
                    metadata["duration_formatted"] = self._format_duration(
                        duration_seconds
                    )
                except Exception as e:
                    logger.warning(f"Could not extract audio duration: {e}")
                    metadata["duration_seconds"] = None
                    metadata["duration_formatted"] = "Unknown"

            return metadata
        except Exception as e:
            logger.warning(f"Could not extract audio metadata: {e}")
            return {"filename": audio_path.name, "error": str(e)}

    def _format_duration(self, seconds: float) -> str:
        """ Format duration in seconds to MM:SS or HH:MM:SS format.""".
        if seconds is None:
            return "Unknown"

        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"

    def _create_markdown(
        self,
        transcription_data: dict,
        audio_metadata: dict,
        model_metadata: dict,
        include_timestamps: bool = True,
    ) -> str:
        """ Create markdown content from transcription data and metadata.""".
        lines = []

        # YAML frontmatter
        lines.append("---")
        lines.append(
            f'title: "Audio Transcription - {audio_metadata.get("filename", "Unknown")}"'
        )
        lines.append(f'source_file: "{audio_metadata.get("filename", "Unknown")}"')
        lines.append(f'transcription_date: "{datetime.now().isoformat()}"')
        lines.append(f'file_format: "{audio_metadata.get("file_format", "unknown")}"')
        if audio_metadata.get("file_size_mb"):
            lines.append(f'file_size_mb: {audio_metadata["file_size_mb"]}')
        if audio_metadata.get("duration_formatted"):
            lines.append(f'duration: "{audio_metadata["duration_formatted"]}"')
        lines.append(f'transcription_model: "{model_metadata.get("model", "unknown")}"')
        lines.append(f'language: "{transcription_data.get("language", "unknown")}"')
        lines.append(f'text_length: {len(transcription_data.get("text", ""))}')
        lines.append(f'segments_count: {len(transcription_data.get("segments", []))}')
        if model_metadata.get("diarization_enabled"):
            lines.append(f"diarization_enabled: true")
        lines.append(f"include_timestamps: {include_timestamps}")
        lines.append("---")
        lines.append("")

        # Full transcript section
        lines.append("## Full Transcript")
        lines.append("")

        # Format transcript with segments if available and multiple segments exist
        segments = transcription_data.get("segments", [])
        if len(segments) > 1:
            for segment in segments:
                start_time = segment.get("start", 0)
                text = segment.get("text", "").strip()
                speaker = segment.get("speaker", "")

                if text:
                    if include_timestamps:
                        timestamp = self._format_duration(start_time)
                        if speaker:
                            lines.append(f"**{timestamp}** ({speaker}): {text}")
                        else:
                            lines.append(f"**{timestamp}**: {text}")
                    else:
                        # No timestamps - just speaker and text
                        if speaker:
                            lines.append(f"({speaker}): {text}")
                        else:
                            lines.append(text)
                    lines.append("")
        else:
            # Single segment or plain text
            text = transcription_data.get("text", "").strip()
            lines.append(text)

        return "\n".join(lines)

    def save_transcript_to_markdown(
        self,
        transcription_result: ProcessorResult,
        audio_path: Path,
        output_dir: str | Path | None = None,
        include_timestamps: bool = True,
    ) -> Path | None:
        """ Save transcription result to a markdown file.""".
        if not transcription_result.success:
            logger.error("Cannot save transcript - transcription failed")
            return None

        try:
            # Determine output directory
            if output_dir is None:
                output_dir = Path("Output/Transcripts")
            else:
                output_dir = Path(output_dir)

            # Ensure output directory exists and is writable
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Output directory confirmed: {output_dir}")
            except Exception as e:
                logger.error(f"Failed to create output directory {output_dir}: {e}")
                return None

            # Create filename
            base_name = audio_path.stem
            safe_name = "".join(
                c for c in base_name if c.isalnum() or c in (" ", "-", "_")
            ).rstrip()
            safe_name = safe_name.replace(" ", "_")
            filename = f"{safe_name}_transcript.md"
            output_path = output_dir / filename

            logger.debug(f"Attempting to save transcript to: {output_path}")

            # Get metadata
            audio_metadata = self._get_audio_metadata(audio_path)
            model_metadata = transcription_result.metadata or {}

            # Create markdown content with timestamps preference
            markdown_content = self._create_markdown(
                transcription_result.data,
                audio_metadata,
                model_metadata,
                include_timestamps=include_timestamps,
            )

            # Write file with detailed error handling
            try:
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(markdown_content)

                # Verify file was written
                if output_path.exists() and output_path.stat().st_size > 0:
                    logger.info(
                        f"✅ Transcript saved successfully: {output_path} ({len(markdown_content):,} characters)"
                    )
                    return output_path
                else:
                    logger.error(
                        f"❌ File was created but appears empty or missing: {output_path}"
                    )
                    return None

            except PermissionError as e:
                logger.error(f"❌ Permission denied writing to {output_path}: {e}")
                return None
            except OSError as e:
                logger.error(f"❌ OS error writing to {output_path}: {e}")
                return None

        except Exception as e:
            logger.error(f"❌ Unexpected error saving transcript for {audio_path}: {e}")
            return None

    def process(
        self, input_data: Any, dry_run: bool = False, **kwargs: Any
    ) -> ProcessorResult:
        """ Process audio with automatic retry and failure logging.""".
        # Extract parameters from kwargs for backwards compatibility
        device = kwargs.get("device", self.device)

        # Handle input_data as input_path for backwards compatibility
        input_path = input_data
        path = Path(input_path)
        if not self.validate_input(path):
            return ProcessorResult(
                success=False, errors=[f"Invalid input: {input_path}"], dry_run=dry_run
            )

        # Get audio metadata including duration for validation
        audio_metadata = self._get_audio_metadata(path)
        audio_duration = audio_metadata.get("duration_seconds")

        # Try transcription with retry logic
        return self._transcribe_with_retry(path, audio_metadata, device, **kwargs)

    def _transcribe_with_retry(
        self, path: Path, audio_metadata: dict, device: str | None, **kwargs: Any
    ) -> ProcessorResult:
        """ Attempt transcription with automatic retry using better model if quality validation fails.""".
        current_model = self.model
        audio_duration = audio_metadata.get("duration_seconds")

        # Determine max attempts based on settings
        max_attempts = self.max_retry_attempts + 1 if self.enable_quality_retry else 1

        for attempt in range(max_attempts):
            try:
                # Update transcriber model for this attempt
                if attempt > 0:
                    retry_model = self.retry_models.get(current_model, current_model)
                    if retry_model == current_model:
                        # No better model available, don't retry
                        break
                    current_model = retry_model
                    logger.info(
                        f"Retrying transcription with improved model: {current_model}"
                    )
                    # Create new transcriber with better model
                    self.transcriber = WhisperCppTranscribeProcessor(
                        model=current_model, progress_callback=self.progress_callback
                    )

                # Create temporary file for processed audio
                if self.temp_dir:
                    self.temp_dir.mkdir(parents=True, exist_ok=True)
                    with tempfile.NamedTemporaryFile(
                        suffix=f".{self.target_format}", delete=False, dir=self.temp_dir
                    ) as tmp_file:
                        output_path = Path(tmp_file.name)
                else:
                    with tempfile.NamedTemporaryFile(
                        suffix=f".{self.target_format}", delete=False
                    ) as tmp_file:
                        output_path = Path(tmp_file.name)

                # Convert audio
                if not self._convert_audio(path, output_path):
                    error_msg = "Audio conversion failed"
                    if attempt == max_attempts - 1:  # Last attempt
                        self._log_transcription_failure(
                            path, error_msg, current_model, audio_duration
                        )
                    output_path.unlink(missing_ok=True)
                    return ProcessorResult(success=False, errors=[error_msg])

                # Transcribe processed audio
                transcription_result = self.transcriber.process(
                    output_path, device=device or self.device, **kwargs
                )

                # Clean up temporary file
                output_path.unlink(missing_ok=True)

                if transcription_result.success:
                    # Quality validation with duration-based analysis
                    quality_passed = True
                    if transcription_result.data and isinstance(
                        transcription_result.data, dict
                    ):
                        text = transcription_result.data.get("text", "")
                        if text and hasattr(
                            self.transcriber, "_validate_transcription_quality"
                        ):
                            validation = (
                                self.transcriber._validate_transcription_quality(
                                    text, audio_duration
                                )
                            )
                            if not validation["is_valid"]:
                                quality_passed = False
                                failure_reason = validation["issue"]
                                logger.warning(
                                    f"Transcription quality issue for {path} (attempt {attempt + 1}): {failure_reason}"
                                )

                                if (
                                    attempt == 0 and self.enable_quality_retry
                                ):  # First attempt failed, retry enabled
                                    logger.info(
                                        "Attempting retry with better model due to quality issues..."
                                    )
                                    continue
                                else:  # Last attempt failed OR retries disabled
                                    if not self.enable_quality_retry:
                                        logger.info(
                                            "Quality retry disabled - returning failed transcription with warning"
                                        )
                                        # Still log as failure but return the result with quality warning
                                        enhanced_metadata = {
                                            "original_format": path.suffix,
                                            "transcription_model": current_model,
                                            "quality_warning": failure_reason,
                                            "retry_disabled": True,
                                            "retry_count": 0,
                                            "duration_seconds": audio_duration,
                                        }
                                        return ProcessorResult(
                                            success=True,  # Mark as success but with quality warning
                                            data=transcription_result.data,
                                            metadata=enhanced_metadata,
                                            errors=[
                                                f"Quality warning (retry disabled): {failure_reason}"
                                            ],
                                        )
                                    else:
                                        logger.error(
                                            f"Final transcription attempt failed quality validation: {failure_reason}"
                                        )
                                        self._log_transcription_failure(
                                            path,
                                            failure_reason,
                                            current_model,
                                            audio_duration,
                                        )
                                        return ProcessorResult(
                                            success=False,
                                            errors=[
                                                f"Transcription quality validation failed: {failure_reason}"
                                            ],
                                        )

                    # Quality validation passed, proceed with result processing
                    if quality_passed:
                        if attempt > 0:
                            logger.info(
                                f"Retry successful! Quality validation passed with model: {current_model}"
                            )

                        # Get model name
                        model_name = getattr(
                            self.transcriber, "model", None
                        ) or getattr(self.transcriber, "model_name", current_model)

                        # Add diarization if enabled
                        diarization_enabled = kwargs.get(
                            "diarization", self.enable_diarization
                        )
                        final_data = transcription_result.data

                        if diarization_enabled:
                            diarization_result = self._perform_diarization(path)
                            if diarization_result:
                                final_data = self._merge_diarization(
                                    transcription_result.data, diarization_result
                                )

                        # Enhanced metadata
                        enhanced_metadata = {
                            "original_format": path.suffix,
                            "processed_format": self.target_format,
                            "normalized": self.normalize_audio,
                            "transcription_model": model_name,
                            "diarization_enabled": diarization_enabled,
                            "model": model_name,
                            "original_file_path": str(path),
                            "retry_count": attempt,
                            "final_model_used": current_model,
                            "duration_seconds": audio_duration,
                        }

                        # Save to markdown if output directory is specified
                        output_dir = kwargs.get("output_dir")
                        include_timestamps = kwargs.get("timestamps", True)
                        saved_file = None
                        if output_dir:
                            temp_result = ProcessorResult(
                                success=True,
                                data=final_data,
                                metadata=enhanced_metadata,
                            )
                            saved_file = self.save_transcript_to_markdown(
                                temp_result,
                                path,
                                output_dir,
                                include_timestamps=include_timestamps,
                            )
                            if saved_file:
                                enhanced_metadata["saved_markdown_file"] = str(
                                    saved_file
                                )

                        return ProcessorResult(
                            success=True,
                            data=final_data,
                            metadata=enhanced_metadata,
                        )
                else:
                    # Transcription process failed
                    error_msg = (
                        "; ".join(transcription_result.errors)
                        if transcription_result.errors
                        else "Unknown transcription error"
                    )
                    logger.error(
                        f"Transcription failed for {path} (attempt {attempt + 1}): {error_msg}"
                    )

                    if attempt == max_attempts - 1:  # Last attempt
                        self._log_transcription_failure(
                            path, error_msg, current_model, audio_duration
                        )
                        return ProcessorResult(
                            success=False,
                            errors=transcription_result.errors,
                            metadata={
                                "original_format": path.suffix,
                                "retry_count": attempt,
                            },
                        )
                    else:
                        # Try retry with better model
                        continue

            except Exception as e:
                error_msg = f"Audio processing error: {e}"
                logger.error(
                    f"Exception during transcription (attempt {attempt + 1}): {error_msg}"
                )

                if attempt == max_attempts - 1:  # Last attempt
                    self._log_transcription_failure(
                        path, error_msg, current_model, audio_duration
                    )
                    return ProcessorResult(success=False, errors=[str(e)])
                else:
                    # Try retry
                    continue

        # If we get here, all attempts failed
        final_error = f"All transcription attempts failed for {path}"
        self._log_transcription_failure(
            path, final_error, current_model, audio_duration
        )
        return ProcessorResult(success=False, errors=[final_error])

    def process_batch(
        self, inputs: list[Any], dry_run: bool = False, **kwargs: Any
    ) -> list[ProcessorResult]:
        # Extract device from kwargs
        device = kwargs.get("device", None)
        return [
            self.process(input_item, dry_run=dry_run, device=device)
            for input_item in inputs
        ]


def process_audio_for_transcription(
    audio_path: str | Path,
    normalize: bool = True,
    device: str | None = None,
    temp_dir: str | Path | None = None,
    model: str = "base",
    use_whisper_cpp: bool = False,
) -> str | None:
    """ Convenience function to process audio and get transcription.""".
    processor = AudioProcessor(
        normalize_audio=normalize,
        device=device,
        temp_dir=temp_dir,
        model=model,
        use_whisper_cpp=use_whisper_cpp,
    )
    result = processor.process(audio_path, device=device)
    return result.data if result.success else None
