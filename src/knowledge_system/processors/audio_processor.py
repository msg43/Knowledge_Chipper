import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil

from knowledge_system.logger import get_logger
from knowledge_system.processors.base import BaseProcessor, ProcessorResult
from knowledge_system.processors.whisper_cpp_transcribe import (
    WhisperCppTranscribeProcessor,
)
from knowledge_system.utils.apple_silicon_optimizations import (
    apply_memory_pressure_mitigations,
    check_memory_pressure,
    optimize_transcription_for_apple_silicon,
)
from knowledge_system.utils.async_processing import (
    AsyncTranscriptionManager,
    estimate_parallel_speedup,
    should_use_parallel_processing,
)
from knowledge_system.utils.audio_utils import (
    convert_audio_file,
    ffmpeg_processor,
    get_audio_duration,
)
from knowledge_system.utils.batch_processing import (
    BatchProcessor,
    create_batch_from_files,
    determine_optimal_batch_strategy,
)
from knowledge_system.utils.streaming_processing import (
    StreamingProcessor,
    should_use_streaming_processing,
)

logger = get_logger(__name__)

# whisper.cpp processor is now the default and only transcriber

# Check if FFmpeg is available for audio processing
FFMPEG_AVAILABLE = ffmpeg_processor._check_ffmpeg_available()

if not FFMPEG_AVAILABLE:
    logger.warning("FFmpeg not available. Audio processing will be limited.")
    logger.info("To enable full audio processing, install FFmpeg: brew install ffmpeg")


class AudioProcessor(BaseProcessor):
    """Processes audio files for transcription pipeline with automatic retry and failure logging."""

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
        require_diarization: bool = False,
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
        self.require_diarization = require_diarization

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
        """Convert audio file to target format using FFmpeg."""
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

    def _perform_diarization(
        self, audio_path: Path, **diarization_kwargs
    ) -> list | None:
        """Run speaker diarization on the audio file with optional optimization parameters."""
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
            diarizer = SpeakerDiarizationProcessor(
                hf_token=self.hf_token,
                device=self.device,
                progress_callback=self.progress_callback,
            )
            result = diarizer.process(audio_path, **diarization_kwargs)
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

    def _process_with_streaming(
        self,
        audio_path: Path,
        converted_audio_path: Path,
        audio_duration: float,
        diarization_enabled: bool,
        optimized_kwargs: dict,
        diarization_config: dict,
        under_pressure: bool,
        mitigations: dict,
    ) -> ProcessorResult:
        """Process very long audio files using streaming chunks."""
        try:
            logger.info(
                f"🌊 Starting streaming processing for {audio_duration/60:.1f} minute file"
            )

            # Prepare processors
            transcriber = self.transcriber
            diarizer = None

            if diarization_enabled:
                from .diarization import (
                    SpeakerDiarizationProcessor,
                    is_diarization_available,
                )

                if is_diarization_available():
                    diarizer = SpeakerDiarizationProcessor(
                        hf_token=self.hf_token,
                        device=self.device,
                        progress_callback=self.progress_callback,
                    )
                else:
                    logger.warning("Diarization not available for streaming processing")
                    diarization_enabled = False

            # Prepare kwargs
            streaming_diarization_kwargs = diarization_config.copy()
            if under_pressure:
                streaming_diarization_kwargs.update(mitigations.get("diarization", {}))

            # Use smaller chunks for very long files to manage memory
            chunk_duration = (
                20.0 if audio_duration > 7200 else 30.0
            )  # 20s for 2+ hour files
            overlap_duration = (
                3.0 if audio_duration > 7200 else 5.0
            )  # 3s for 2+ hour files

            # Process with streaming
            with StreamingProcessor(
                chunk_duration=chunk_duration,
                overlap_duration=overlap_duration,
                max_workers=3,
                progress_callback=self.progress_callback,
            ) as streaming_processor:
                results = streaming_processor.process_streaming(
                    audio_path=converted_audio_path,
                    total_duration=audio_duration,
                    transcriber=transcriber,
                    diarizer=diarizer if diarization_enabled else None,
                    transcription_kwargs=optimized_kwargs,
                    diarization_kwargs=streaming_diarization_kwargs,
                )

            # Convert streaming results to standard format
            if results["success_rate"] > 0.5:  # At least 50% of chunks succeeded
                # Merge diarization into transcription segments
                final_data = results["transcription"]

                if diarization_enabled and results["diarization"]:
                    final_data = self._merge_diarization(
                        results["transcription"], results["diarization"]
                    )

                # Enhanced metadata for streaming
                model_name = getattr(transcriber, "model_name", "unknown")
                enhanced_metadata = {
                    "original_format": audio_path.suffix,
                    "transcription_model": model_name,
                    "diarization_enabled": diarization_enabled,
                    "processing_mode": "streaming",
                    "chunks_processed": results["chunks_processed"],
                    "chunks_successful": results["chunks_successful"],
                    "success_rate": results["success_rate"],
                    "chunk_duration": chunk_duration,
                    "overlap_duration": overlap_duration,
                    "duration_seconds": audio_duration,
                }

                logger.info(
                    f"✅ Streaming processing completed: {results['chunks_successful']}/{results['chunks_processed']} chunks successful"
                )

                return ProcessorResult(
                    success=True, data=final_data, metadata=enhanced_metadata
                )
            else:
                error_msg = f"Streaming processing failed: only {results['success_rate']:.1%} of chunks succeeded"
                logger.error(error_msg)
                return ProcessorResult(
                    success=False,
                    errors=[error_msg],
                    metadata={"processing_mode": "streaming_failed"},
                )

        except Exception as e:
            logger.error(f"Streaming processing error: {e}")
            return ProcessorResult(
                success=False,
                errors=[f"Streaming processing failed: {e}"],
                metadata={"processing_mode": "streaming_error"},
            )

    def _merge_diarization(
        self, transcription_data: dict, diarization_segments: list
    ) -> dict:
        """Merge speaker labels into transcription segments."""
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
        """Find the speaker with the most overlap in the given time range."""
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

    def _handle_speaker_assignment(
        self, 
        transcript_data: dict, 
        diarization_segments: list, 
        recording_path: str, 
        kwargs: dict
    ) -> dict:
        """
        Handle speaker assignment workflow after diarization completion.
        
        Args:
            transcript_data: Transcription data with speaker segments
            diarization_segments: Raw diarization segments
            recording_path: Path to the recording file
            kwargs: Processing kwargs that may contain GUI settings
            
        Returns:
            Updated transcript data with real speaker names
        """
        try:
            # Check if speaker assignment is enabled
            enable_speaker_assignment = kwargs.get("enable_speaker_assignment", True)
            if not enable_speaker_assignment:
                logger.info("Speaker assignment disabled, keeping generic speaker IDs")
                return transcript_data
            
            # Import speaker processing components
            from .speaker_processor import SpeakerProcessor
            
            # Prepare speaker data for assignment
            speaker_processor = SpeakerProcessor()
            
            # Extract transcript segments for processing
            transcript_segments = transcript_data.get("segments", [])
            
            # Prepare speaker data
            speaker_data_list = speaker_processor.prepare_speaker_data(
                diarization_segments, transcript_segments
            )
            
            if not speaker_data_list:
                logger.warning("No speaker data prepared for assignment")
                return transcript_data
            
            logger.info(f"🎭 Found {len(speaker_data_list)} speakers for assignment")
            
            # Check if we're in GUI mode and can show dialog
            show_dialog = kwargs.get("show_speaker_dialog", True)
            gui_mode = kwargs.get("gui_mode", False)
            
            if show_dialog and gui_mode:
                # Show speaker assignment dialog with metadata for auto-assignment
                metadata = kwargs.get("metadata", {})
                assignments = self._show_speaker_assignment_dialog(
                    speaker_data_list, recording_path, metadata
                )
                
                if assignments:
                    # Apply assignments to transcript data
                    updated_data = speaker_processor.apply_speaker_assignments(
                        transcript_data, assignments
                    )
                    
                    logger.info(f"✅ Applied speaker assignments: {assignments}")
                    return updated_data
                else:
                    logger.info("Speaker assignment cancelled or no assignments made")
                    return transcript_data
            else:
                # Non-GUI mode: try to load existing assignments or use suggestions
                assignments = self._get_automatic_speaker_assignments(
                    speaker_data_list, recording_path
                )
                
                if assignments:
                    updated_data = speaker_processor.apply_speaker_assignments(
                        transcript_data, assignments
                    )
                    logger.info(f"Applied automatic speaker assignments: {assignments}")
                    return updated_data
                else:
                    logger.info("No automatic speaker assignments available")
                    return transcript_data
            
        except Exception as e:
            logger.error(f"Error in speaker assignment workflow: {e}")
            # Return original data if speaker assignment fails
            return transcript_data
    
    def _show_speaker_assignment_dialog(
        self, 
        speaker_data_list: list, 
        recording_path: str,
        metadata: dict = None
    ) -> dict | None:
        """
        Show the speaker assignment dialog.
        
        Args:
            speaker_data_list: List of SpeakerData objects
            recording_path: Path to the recording file
            metadata: Optional metadata for auto-assignment
            
        Returns:
            Dictionary of speaker assignments or None if cancelled
        """
        try:
            from ..gui.dialogs.speaker_assignment_dialog import show_speaker_assignment_dialog
            
            # Show the dialog with metadata for podcast auto-assignment
            assignments = show_speaker_assignment_dialog(
                speaker_data_list, recording_path, metadata
            )
            
            return assignments
            
        except ImportError as e:
            logger.warning(f"Speaker assignment dialog not available: {e}")
            return None
        except Exception as e:
            logger.error(f"Error showing speaker assignment dialog: {e}")
            return None
    
    def _get_automatic_speaker_assignments(
        self, 
        speaker_data_list: list, 
        recording_path: str
    ) -> dict | None:
        """
        Get automatic speaker assignments for non-GUI mode.
        
        Args:
            speaker_data_list: List of SpeakerData objects
            recording_path: Path to the recording file
            
        Returns:
            Dictionary of automatic assignments or None
        """
        try:
            from ..database.speaker_models import get_speaker_db_service
            
            # Check for existing assignments in database
            db_service = get_speaker_db_service()
            existing_assignments = db_service.get_assignments_for_recording(recording_path)
            
            if existing_assignments:
                # Use existing assignments
                assignments = {}
                for assignment in existing_assignments:
                    assignments[assignment.speaker_id] = assignment.assigned_name
                
                logger.info(f"Found existing speaker assignments: {assignments}")
                return assignments
            
            # Use AI suggestions as fallback
            assignments = {}
            for speaker_data in speaker_data_list:
                if speaker_data.suggested_name and speaker_data.confidence_score > 0.6:
                    assignments[speaker_data.speaker_id] = speaker_data.suggested_name
                else:
                    # Generate generic name
                    speaker_num = speaker_data.speaker_id.replace("SPEAKER_", "")
                    try:
                        num = int(speaker_num) + 1
                        assignments[speaker_data.speaker_id] = f"Speaker {num}"
                    except ValueError:
                        assignments[speaker_data.speaker_id] = speaker_data.speaker_id
            
            if assignments:
                logger.info(f"Generated automatic speaker assignments: {assignments}")
                return assignments
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting automatic speaker assignments: {e}")
            return None
    
    def _save_color_coded_transcript(
        self,
        transcript_data: dict,
        audio_path: Path,
        output_dir: Path,
        include_timestamps: bool = True
    ) -> Path | None:
        """
        Save color-coded transcript with speaker identification.
        
        Args:
            transcript_data: Transcript data with speaker assignments
            audio_path: Original audio file path
            output_dir: Output directory
            include_timestamps: Whether to include timestamps
            
        Returns:
            Path to saved color-coded transcript or None if failed
        """
        try:
            from ..utils.color_transcript import save_color_coded_transcript
            
            # Create output filename for color-coded transcript
            base_name = audio_path.stem
            safe_name = "".join(
                c for c in base_name if c.isalnum() or c in (" ", "-", "_")
            ).rstrip()
            safe_name = safe_name.replace(" ", "_")
            
            # Save both HTML and enhanced markdown versions
            html_path = output_dir / f"{safe_name}_transcript_color_coded.html"
            md_path = output_dir / f"{safe_name}_transcript_enhanced.md"
            
            # Get speaker assignments from transcript data
            speaker_assignments = transcript_data.get("speaker_assignments", {})
            
            # Prepare kwargs for transcript generation
            transcript_kwargs = {
                "source_name": audio_path.name,
                "model": transcript_data.get("transcription_model", "unknown"),
                "device": "auto",  # Could be extracted from metadata
                "include_timestamps": include_timestamps,
                "use_html_colors": True
            }
            
            # Save HTML version
            html_success = save_color_coded_transcript(
                transcript_data,
                html_path,
                speaker_assignments,
                **transcript_kwargs
            )
            
            # Save enhanced markdown version
            md_success = save_color_coded_transcript(
                transcript_data,
                md_path,
                speaker_assignments,
                **transcript_kwargs
            )
            
            if html_success:
                logger.info(f"✅ Color-coded HTML transcript saved: {html_path}")
                
            if md_success:
                logger.info(f"✅ Enhanced markdown transcript saved: {md_path}")
            
            # Return the HTML path as primary color-coded transcript
            return html_path if html_success else (md_path if md_success else None)
            
        except Exception as e:
            logger.error(f"Error saving color-coded transcript: {e}")
            return None

    def _log_transcription_failure(
        self,
        file_path: Path,
        failure_reason: str,
        model_used: str,
        audio_duration: float | None = None,
    ) -> None:
        """Log transcription failure to a dedicated failure log file."""
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
        """Extract metadata from audio file."""
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
        """Format duration in seconds to MM:SS or HH:MM:SS format."""
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
        """Create markdown content from transcription data and metadata."""
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
            lines.append("diarization_enabled: true")
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
        """Save transcription result to a markdown file."""
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
        """Process audio with automatic retry and failure logging."""
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
        audio_metadata.get("duration_seconds")

        # Try transcription with retry logic
        return self._transcribe_with_retry(path, audio_metadata, device, **kwargs)

    def _transcribe_with_retry(
        self, path: Path, audio_metadata: dict, device: str | None, **kwargs: Any
    ) -> ProcessorResult:
        """Attempt transcription with automatic retry using better model if quality validation fails."""
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

                # Apply Apple Silicon optimizations if available
                audio_duration = audio_metadata.get("duration_seconds", 3600.0)
                optimized_kwargs = kwargs.copy()

                # Get optimized settings for Apple Silicon
                (
                    whisper_config,
                    diarization_config,
                ) = optimize_transcription_for_apple_silicon(
                    model_size=current_model,
                    audio_duration_seconds=audio_duration,
                    enable_diarization=kwargs.get(
                        "diarization", self.enable_diarization
                    ),
                )

                # Apply whisper optimizations
                optimized_kwargs.update(whisper_config)

                # Check for memory pressure and apply mitigations if needed
                under_pressure, usage = check_memory_pressure()
                if under_pressure:
                    logger.warning(
                        f"Memory pressure detected ({usage:.1%} usage), applying conservative settings"
                    )
                    mitigations = apply_memory_pressure_mitigations()
                    optimized_kwargs.update(mitigations.get("whisper", {}))

                # Determine processing strategy based on file characteristics
                diarization_enabled = kwargs.get("diarization", self.enable_diarization)
                memory_gb = psutil.virtual_memory().total / (1024**3)

                # Check if we should use streaming processing for very long files
                use_streaming = should_use_streaming_processing(
                    audio_duration, memory_gb
                )

                if use_streaming:
                    logger.info(
                        f"🌊 Using streaming processing for {audio_duration/60:.1f} minute file"
                    )
                    return self._process_with_streaming(
                        path,
                        output_path,
                        audio_duration,
                        diarization_enabled,
                        optimized_kwargs,
                        diarization_config,
                        under_pressure,
                        mitigations,
                    )

                # For shorter files, determine if we should use parallel processing
                use_parallel = should_use_parallel_processing(
                    diarization_enabled,
                    audio_duration,
                    psutil.cpu_count(logical=False) or 4,
                )

                if use_parallel and diarization_enabled:
                    # Run transcription and diarization in parallel
                    logger.info(
                        "🚀 Using parallel processing for transcription + diarization"
                    )
                    speedup_estimates = estimate_parallel_speedup(audio_duration)
                    logger.info(
                        f"Expected speedup: {speedup_estimates['speedup_factor']:.1f}x "
                        f"(saving {speedup_estimates['time_saved']:.1f}s)"
                    )

                    with AsyncTranscriptionManager(max_workers=2) as async_manager:
                        # Prepare diarization processor and kwargs
                        from .diarization import (
                            SpeakerDiarizationProcessor,
                            is_diarization_available,
                        )

                        diarization_kwargs = diarization_config.copy()
                        if under_pressure:
                            diarization_kwargs.update(
                                mitigations.get("diarization", {})
                            )

                        if is_diarization_available():
                            diarizer = SpeakerDiarizationProcessor(
                                hf_token=self.hf_token,
                                device=self.device,
                                progress_callback=self.progress_callback,
                            )

                            # Run both in parallel
                            (
                                transcription_result,
                                diarization_result,
                            ) = async_manager.process_parallel(
                                audio_path=output_path,
                                transcriber=self.transcriber,
                                diarizer=diarizer,
                                transcription_kwargs={
                                    "device": device or self.device,
                                    **optimized_kwargs,
                                },
                                diarization_kwargs=diarization_kwargs,
                                progress_callback=self.progress_callback,
                            )
                        else:
                            # Fallback to transcription only if diarization not available
                            logger.warning(
                                "Diarization not available, running transcription only"
                            )
                            transcription_result = self.transcriber.process(
                                output_path,
                                device=device or self.device,
                                **optimized_kwargs,
                            )
                            diarization_result = None
                else:
                    # Sequential processing (original behavior)
                    logger.info("Using sequential processing")
                    transcription_result = self.transcriber.process(
                        output_path, device=device or self.device, **optimized_kwargs
                    )
                    diarization_result = None

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

                        # Process diarization results
                        final_data = transcription_result.data
                        diarization_segments = None

                        if diarization_enabled:
                            diarization_successful = False

                            if diarization_result and diarization_result.success:
                                # Store diarization segments for speaker assignment
                                diarization_segments = diarization_result.data
                                # Merge parallel diarization results
                                final_data = self._merge_diarization(
                                    transcription_result.data, diarization_result.data
                                )
                                logger.info(
                                    "✅ Successfully merged transcription and diarization results"
                                )
                                diarization_successful = True
                            elif not use_parallel:
                                # Fallback to sequential diarization if parallel wasn't used
                                diarization_kwargs = diarization_config.copy()
                                if under_pressure:
                                    diarization_kwargs.update(
                                        mitigations.get("diarization", {})
                                    )

                                sequential_diarization = self._perform_diarization(
                                    output_path, **diarization_kwargs
                                )
                                if sequential_diarization:
                                    diarization_segments = sequential_diarization
                                    final_data = self._merge_diarization(
                                        transcription_result.data,
                                        sequential_diarization,
                                    )
                                    diarization_successful = True

                            # Trigger speaker assignment dialog if diarization was successful
                            if diarization_successful and diarization_segments:
                                final_data = self._handle_speaker_assignment(
                                    final_data, diarization_segments, str(path), kwargs
                                )

                            # Check if diarization was required but failed
                            if self.require_diarization and not diarization_successful:
                                error_msg = "Diarization was required but failed - no transcript will be saved to allow re-processing"
                                logger.error(f"STRICT DIARIZATION FAILURE: {error_msg}")
                                self._log_transcription_failure(
                                    path, error_msg, current_model, audio_duration
                                )
                                return ProcessorResult(
                                    success=False,
                                    errors=[error_msg],
                                    metadata={
                                        "original_format": path.suffix,
                                        "diarization_required": True,
                                        "diarization_failed": True,
                                        "transcription_successful": True,
                                        "retry_count": attempt,
                                        "duration_seconds": audio_duration,
                                    },
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
                        enable_color_coding = kwargs.get("enable_color_coding", True)
                        saved_file = None
                        
                        if output_dir:
                            temp_result = ProcessorResult(
                                success=True,
                                data=final_data,
                                metadata=enhanced_metadata,
                            )
                            
                            # Save regular markdown transcript
                            saved_file = self.save_transcript_to_markdown(
                                temp_result,
                                path,
                                output_dir,
                                include_timestamps=include_timestamps,
                            )
                            
                            # Save color-coded transcript if speakers are identified and color coding is enabled
                            if (enable_color_coding and 
                                diarization_successful and 
                                final_data.get("speaker_assignments")):
                                
                                color_coded_file = self._save_color_coded_transcript(
                                    final_data, path, output_dir, include_timestamps
                                )
                                
                                if color_coded_file:
                                    enhanced_metadata["saved_color_coded_file"] = str(color_coded_file)
                            
                            if saved_file:
                                enhanced_metadata["saved_markdown_file"] = str(saved_file)

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
        """
        Process multiple audio files efficiently using batch optimization.

        Args:
            inputs: List of audio file paths
            dry_run: Whether this is a dry run
            **kwargs: Additional processing arguments

        Returns:
            List of ProcessorResult objects
        """
        if not inputs:
            return []

        if len(inputs) == 1:
            # Single file - use regular processing
            return [self.process(inputs[0], dry_run=dry_run, **kwargs)]

        # Convert inputs to Path objects
        file_paths = [Path(input_item) for input_item in inputs]

        # Determine optimal batch strategy
        memory_gb = psutil.virtual_memory().total / (1024**3)
        cpu_cores = psutil.cpu_count(logical=False) or 4

        # Estimate average file duration (rough estimate)
        avg_duration = (
            300.0  # Default 5 minutes, could be improved with actual estimation
        )

        strategy, max_concurrent = determine_optimal_batch_strategy(
            file_count=len(file_paths),
            average_file_duration=avg_duration,
            available_cores=cpu_cores,
            available_memory_gb=memory_gb,
        )

        logger.info(
            f"Batch processing {len(file_paths)} files with strategy: {strategy.value}"
        )

        # Create batch items
        batch_items = create_batch_from_files(file_paths)

        # Setup batch processor
        batch_processor = BatchProcessor(
            max_concurrent_files=max_concurrent,
            strategy=strategy,
            progress_callback=self.progress_callback,
            enable_diarization=kwargs.get("diarization", self.enable_diarization),
        )

        # Process the batch
        batch_results = batch_processor.process_batch(
            items=batch_items,
            audio_processor=self,
            transcription_kwargs=kwargs,
            diarization_kwargs={},
        )

        # Convert batch results to ProcessorResult objects
        processor_results = []
        for batch_result in batch_results:
            if batch_result.transcription_result:
                processor_results.append(batch_result.transcription_result)
            else:
                # Create failed result
                error_result = ProcessorResult(
                    success=False,
                    errors=[
                        batch_result.error_message or "Unknown batch processing error"
                    ],
                    metadata={
                        "batch_processing": True,
                        "file_path": str(batch_result.file_path),
                    },
                    dry_run=dry_run,
                )
                processor_results.append(error_result)

        # Log batch statistics
        successful = sum(1 for r in processor_results if r.success)
        logger.info(
            f"Batch processing completed: {successful}/{len(processor_results)} files successful"
        )

        return processor_results


def process_audio_for_transcription(
    audio_path: str | Path,
    normalize: bool = True,
    device: str | None = None,
    temp_dir: str | Path | None = None,
    model: str = "base",
    use_whisper_cpp: bool = False,
) -> str | None:
    """Convenience function to process audio and get transcription."""
    processor = AudioProcessor(
        normalize_audio=normalize,
        device=device,
        temp_dir=temp_dir,
        model=model,
        use_whisper_cpp=use_whisper_cpp,
    )
    result = processor.process(audio_path, device=device)
    return result.data if result.success else None
