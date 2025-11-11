import os
import tempfile
from datetime import date, datetime
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
        require_diarization: bool = False,
        speaker_assignment_callback=None,
        preloaded_transcriber=None,
        preloaded_diarizer=None,
        db_service=None,
        remove_silence: bool = True,
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
        self.speaker_assignment_callback = speaker_assignment_callback
        self.require_diarization = require_diarization
        self.db_service = db_service
        self.remove_silence = remove_silence

        # Store preloaded models
        self.preloaded_diarizer = preloaded_diarizer

        # Use preloaded transcriber if available, otherwise create new one
        if preloaded_transcriber:
            self.transcriber = preloaded_transcriber
            logger.info("✅ Using preloaded transcription model")
        else:
            # Use whisper.cpp as the default transcriber with acceleration
            self.transcriber = WhisperCppTranscribeProcessor(
                model=model, use_coreml=True, progress_callback=progress_callback
            )
            logger.info("🔄 Created new transcription model instance")

        # Model progression for smart recovery (from smaller to larger for better accuracy)
        self.retry_models = {
            "tiny": "base",
            "base": "small",
            "small": "medium",
            "medium": "large",
            "large": "large",  # No upgrade from large (already the best)
        }

        # Track recovery attempts to prevent infinite loops
        self.recovery_attempt = 0

    @property
    def supported_formats(self) -> list[str]:
        return [
            ".mp3",
            ".wav",
            ".m4a",
            ".flac",
            ".ogg",
            ".aac",
            ".mp4",
            ".webm",
            ".opus",
        ]

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
            # Report conversion start
            if self.progress_callback:
                input_size_mb = input_path.stat().st_size / (1024 * 1024)
                self.progress_callback(
                    f"🔄 Converting {input_path.name} ({input_size_mb:.1f}MB) to 16kHz mono format...",
                    0,
                )

            # Convert audio to 16kHz mono - optimal for both whisper and pyannote
            # Also remove long silence periods to prevent hallucinations
            success = convert_audio_file(
                input_path=input_path,
                output_path=output_path,
                target_format=self.target_format,
                normalize=self.normalize_audio,
                sample_rate=16000,  # 16kHz for both whisper and pyannote
                channels=1,  # Mono for both processors
                progress_callback=self.progress_callback,
                remove_silence=self.remove_silence,  # Prevent hallucinations from long silence
            )

            if success:
                if self.progress_callback:
                    output_size_mb = output_path.stat().st_size / (1024 * 1024)
                    self.progress_callback(
                        f"✅ Conversion of {input_path.name} complete ({output_size_mb:.1f}MB output)",
                        100,
                    )
                logger.info(
                    f"Successfully converted {input_path} to 16kHz mono {output_path}"
                )
                return True
            else:
                if self.progress_callback:
                    self.progress_callback(
                        f"❌ Conversion to 16kHz mono .{self.target_format} failed", 0
                    )
                logger.error(
                    f"Failed to convert {input_path} to 16kHz mono {output_path}"
                )
                return False

        except Exception as e:
            if self.progress_callback:
                self.progress_callback(
                    f"❌ Conversion error for {input_path.name}: {str(e)}", 0
                )
            logger.error(f"Audio conversion error: {e}")
            return False

    def _perform_diarization(
        self, audio_path: Path, **diarization_kwargs
    ) -> list | None:
        """Run speaker diarization on the audio file with optional optimization parameters."""
        # Safety check: Never run diarization during testing mode
        testing_mode = os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE") == "1"
        if testing_mode:
            logger.info(
                "🧪 Testing mode: Skipping diarization entirely (safety override)"
            )
            return None

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

            # Get diarization sensitivity from settings
            from ..config import get_settings

            settings = get_settings()
            sensitivity = getattr(
                settings.speaker_identification,
                "diarization_sensitivity",
                "conservative",
            )

            diarizer = SpeakerDiarizationProcessor(
                hf_token=self.hf_token,
                device=self.device,
                progress_callback=self.progress_callback,
                sensitivity=sensitivity,
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
        kwargs: dict,
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

            # Get metadata from all sources (non-destructive multi-source approach)
            source_id = kwargs.get("source_id")
            if source_id and self.db_service:
                logger.info(f"🔍 Retrieving metadata from all sources for {source_id}")
                all_metadata = self.db_service.get_all_source_metadata(source_id)

                # Log what we found
                primary = all_metadata.get("primary_source")
                aliases = all_metadata.get("aliased_sources", [])
                if primary:
                    logger.info(
                        f"   Primary: {primary.get('source_type')} - {primary.get('title', '')[:50]}..."
                    )
                for i, alias in enumerate(aliases, 1):
                    logger.info(
                        f"   Alias #{i}: {alias.get('source_type')} - {alias.get('title', '')[:50]}..."
                    )
            else:
                # Fallback for non-database sources (local files, etc.)
                logger.debug("No source_id or db_service, using metadata from kwargs")
                all_metadata = {
                    "primary_source": kwargs.get("metadata", {}),
                    "aliased_sources": [],
                }

            # Prepare speaker data with multi-source metadata for enhanced suggestions
            speaker_data_list = speaker_processor.prepare_speaker_data(
                diarization_segments, transcript_segments, all_metadata, recording_path
            )

            if not speaker_data_list:
                logger.warning("No speaker data prepared for assignment")
                return transcript_data

            logger.info(f"✅ Found {len(speaker_data_list)} speakers for assignment")

            # Check if MVP LLM is already available (quick check, no downloads)
            mvp_available = False
            try:
                from ..utils.mvp_llm_setup import get_mvp_llm_setup

                mvp_setup = get_mvp_llm_setup()
                if mvp_setup.is_mvp_ready():
                    # LLM is already set up - use it!
                    mvp_available = True
                    logger.info("✅ MVP LLM is ready - will use AI speaker suggestions")
                    if self.progress_callback:
                        self.progress_callback("🤖 Using AI-powered speaker suggestions")
                else:
                    # LLM not ready - don't block to install it
                    logger.info(
                        "MVP LLM not ready - using basic suggestions to avoid delays"
                    )
                    if self.progress_callback:
                        self.progress_callback(
                            "💡 Using basic speaker suggestions (LLM not available)"
                        )
            except Exception as e:
                logger.debug(f"Could not check MVP LLM status: {e}")
                if self.progress_callback:
                    self.progress_callback("💡 Using basic speaker suggestions")

            # Prepare metadata dictionary for speaker assignment
            metadata = (
                all_metadata.get("primary_source", {}).copy() if all_metadata else {}
            )

            # Store MVP availability for speaker processor to use
            if mvp_available:
                metadata["mvp_llm_available"] = True

            # CRITICAL: Store output_dir in metadata so speaker assignment can regenerate markdown
            output_dir = kwargs.get("output_dir")
            if output_dir:
                metadata["output_dir"] = output_dir

            # Check if we're in GUI mode and can show dialog
            show_dialog = kwargs.get("show_speaker_dialog", True)
            gui_mode = kwargs.get("gui_mode", False)
            testing_mode = os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE") == "1"

            # ADDITIONAL SAFETY: Check if GUI mode is False (testing indicator)
            if not gui_mode:
                logger.info("🧪 GUI mode disabled - skipping speaker assignment dialog")
                show_dialog = False

            # NEVER show dialogs during testing mode, regardless of other flags
            if testing_mode:
                logger.info(
                    "🧪 Testing mode: Skipping speaker assignment dialog (forced)"
                )
                show_dialog = False

            # IMPORTANT: For non-blocking speaker assignment, queue the task
            # and return immediately with generic speaker IDs
            if (
                show_dialog
                and gui_mode
                and not testing_mode
                and not os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE")
            ):
                # Queue speaker assignment task for later processing
                from knowledge_system.utils.speaker_assignment_queue import (
                    get_speaker_assignment_queue,
                )

                queue = get_speaker_assignment_queue()

                # Get video_id and transcript_id from kwargs or enhanced_metadata
                video_id = (
                    kwargs.get("video_id")
                    or kwargs.get("source_id")
                    or kwargs.get("database_media_id")
                )
                transcript_id = kwargs.get("transcript_id") or kwargs.get(
                    "database_transcript_id"
                )

                if video_id and transcript_id:
                    # Queue the assignment task
                    task_id = queue.add_task(
                        video_id=video_id,
                        transcript_id=transcript_id,
                        speaker_data_list=speaker_data_list,
                        recording_path=recording_path,
                        metadata=metadata,
                    )

                    logger.info(
                        f"Queued speaker assignment task {task_id} for {recording_path}. "
                        f"Processing will continue without blocking."
                    )

                    # If we have a callback, use it to trigger the dialog non-blocking
                    if self.speaker_assignment_callback:
                        # Pass task_id and multi-source metadata to the dialog
                        # Use all_metadata (multi-source) instead of metadata (single-source)
                        enhanced_metadata = (
                            all_metadata.copy()
                            if isinstance(all_metadata, dict)
                            else {}
                        )
                        enhanced_metadata["task_id"] = task_id

                        # This should be non-blocking - just emit a signal
                        self.speaker_assignment_callback(
                            speaker_data_list, recording_path, enhanced_metadata
                        )
                else:
                    logger.warning(
                        f"Cannot queue speaker assignment without video_id ({video_id}) "
                        f"and transcript_id ({transcript_id})"
                    )

                # Return transcript with generic speaker IDs immediately
                logger.info(
                    "Returning transcript with generic speaker IDs. "
                    "Speaker names will be updated when user completes assignment."
                )
                return transcript_data
            else:
                if testing_mode:
                    logger.info("🧪 Testing mode: Skipping speaker assignment dialog")

                # Non-GUI mode or testing: try to load existing assignments or use suggestions
                assignments = self._get_automatic_speaker_assignments(
                    speaker_data_list, recording_path
                )

                if assignments:
                    updated_data = speaker_processor.apply_speaker_assignments(
                        transcript_data, assignments, recording_path, speaker_data_list
                    )
                    logger.info(f"Applied automatic speaker assignments: {assignments}")
                    return updated_data
                else:
                    # Save AI suggestions even if no assignments made (for learning)
                    speaker_processor.save_speaker_processing_session(
                        recording_path, speaker_data_list
                    )
                    logger.info(
                        "No automatic speaker assignments available, but saved AI suggestions for learning"
                    )
                    return transcript_data

        except Exception as e:
            logger.error(f"Error in speaker assignment workflow: {e}")
            # Return original data if speaker assignment fails
            return transcript_data

    def _show_speaker_assignment_dialog(
        self, speaker_data_list: list, recording_path: str, metadata: dict = None
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
        # Double-check for testing mode as a safety net
        testing_mode = os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE") == "1"
        if testing_mode:
            logger.info(
                "🧪 Testing mode: Refusing to show speaker assignment dialog (safety net)"
            )
            return None

        try:
            from ..gui.dialogs.speaker_assignment_dialog import (
                show_speaker_assignment_dialog,
            )

            # Show the dialog with metadata for podcast auto-assignment
            assignments = show_speaker_assignment_dialog(
                speaker_data_list, recording_path, metadata
            )

            return assignments

        except RuntimeError as e:
            if "testing mode" in str(e):
                logger.info(
                    "🧪 Testing mode: Speaker assignment dialog blocked (as expected)"
                )
                return None
            else:
                logger.error(f"Speaker assignment dialog runtime error: {e}")
                return None
        except ImportError as e:
            logger.warning(f"Speaker assignment dialog not available: {e}")
            return None
        except Exception as e:
            logger.error(f"Error showing speaker assignment dialog: {e}")
            return None

    def _should_queue_speaker_review(self, kwargs: dict) -> bool:
        """
        Determine if speaker assignment should be queued for manual review.

        Returns True only if:
        1. Dialog is explicitly requested (show_speaker_dialog=True)
        2. Running in GUI mode (gui_mode=True)
        3. NOT in testing mode (KNOWLEDGE_CHIPPER_TESTING_MODE != "1")
        """
        show_dialog = kwargs.get("show_speaker_dialog", True)
        gui_mode = kwargs.get("gui_mode", False)
        testing_mode = os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE") == "1"

        return show_dialog and gui_mode and not testing_mode

    def _get_automatic_speaker_assignments(
        self, speaker_data_list: list, recording_path: str
    ) -> dict | None:
        """
        Get automatic speaker assignments for non-GUI mode.

        Priority order:
        1. Existing user-confirmed assignments from database
        2. AI suggestions from previous processing sessions (stored in database)
        3. AI suggestions from current speaker_data_list
        4. Generic fallback names

        Args:
            speaker_data_list: List of SpeakerData objects
            recording_path: Path to the recording file

        Returns:
            Dictionary of automatic assignments or None
        """
        try:
            from ..database.speaker_models import get_speaker_db_service

            db_service = get_speaker_db_service()

            # PRIORITY 1: Check for existing user-confirmed assignments in database
            existing_assignments = db_service.get_assignments_for_recording(
                recording_path
            )

            if existing_assignments:
                # Use existing assignments
                assignments = {}
                for assignment in existing_assignments:
                    assignments[assignment.speaker_id] = assignment.assigned_name

                logger.info(f"✅ Found existing speaker assignments: {assignments}")
                return assignments

            # PRIORITY 2: Check for AI suggestions from previous processing sessions
            # This is the missing piece! AI suggestions are stored but not loaded
            try:
                import json

                from sqlalchemy import desc

                from ..database.speaker_models import SpeakerProcessingSession

                # Query for the most recent processing session for this recording
                with db_service.session_scope() as session:
                    latest_session = (
                        session.query(SpeakerProcessingSession)
                        .filter(
                            SpeakerProcessingSession.recording_path
                            == str(recording_path)
                        )
                        .order_by(desc(SpeakerProcessingSession.created_at))
                        .first()
                    )

                    if latest_session and latest_session.ai_suggestions_json:
                        ai_suggestions = json.loads(latest_session.ai_suggestions_json)

                        # Extract high-confidence suggestions
                        assignments = {}
                        for speaker_id, suggestion_data in ai_suggestions.items():
                            if isinstance(suggestion_data, dict):
                                suggested_name = suggestion_data.get("suggested_name")
                                confidence = suggestion_data.get("confidence", 0)

                                # Use high-confidence suggestions (>0.6)
                                if suggested_name and confidence > 0.6:
                                    assignments[speaker_id] = suggested_name
                                    logger.info(
                                        f"🤖 Using AI suggestion from database: {speaker_id} -> '{suggested_name}' "
                                        f"(confidence: {confidence:.2f})"
                                    )

                        if assignments:
                            logger.info(
                                f"✅ Loaded {len(assignments)} AI suggestions from database"
                            )
                            return assignments

            except Exception as e:
                logger.debug(f"Could not load AI suggestions from database: {e}")

            # PRIORITY 3: Use AI suggestions from current speaker_data_list
            # 🚨 ALWAYS use LLM suggestions regardless of confidence
            # The LLM provides best-guess names even with low confidence
            assignments = {}
            for speaker_data in speaker_data_list:
                if speaker_data.suggested_name:
                    assignments[speaker_data.speaker_id] = speaker_data.suggested_name
                    confidence_indicator = (
                        "✅" if speaker_data.confidence_score > 0.7 else "⚠️"
                    )
                    logger.info(
                        f"{confidence_indicator} Using LLM suggestion: {speaker_data.speaker_id} -> "
                        f"'{speaker_data.suggested_name}' (confidence: {speaker_data.confidence_score:.2f})"
                    )
                else:
                    # This should never happen - LLM must always provide a name
                    logger.error(
                        f"❌ CRITICAL: No LLM suggestion for {speaker_data.speaker_id} - LLM failed to provide name"
                    )
                    # Emergency fallback only if LLM completely failed
                    # Use letter-based naming
                    speaker_num = speaker_data.speaker_id.replace("SPEAKER_", "")
                    try:
                        num = int(speaker_num)
                        letter = chr(65 + num)  # A, B, C, ...
                        assignments[
                            speaker_data.speaker_id
                        ] = f"Unknown Speaker {letter}"
                        logger.error(
                            f"Emergency fallback: {speaker_data.speaker_id} -> 'Unknown Speaker {letter}'"
                        )
                    except ValueError:
                        # speaker_num not a valid integer
                        logger.debug(
                            f"Could not parse speaker number from {speaker_data.speaker_id}"
                        )
                        assignments[speaker_data.speaker_id] = speaker_data.speaker_id
                    except (IndexError, OverflowError):
                        # chr(65 + num) out of range (too many speakers)
                        logger.debug(f"Speaker number out of letter range")
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
        include_timestamps: bool = True,
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
                "use_html_colors": True,
            }

            # Save HTML version
            html_success = save_color_coded_transcript(
                transcript_data, html_path, speaker_assignments, **transcript_kwargs
            )

            # Save enhanced markdown version
            md_success = save_color_coded_transcript(
                transcript_data, md_path, speaker_assignments, **transcript_kwargs
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
        source_metadata: dict | None = None,
    ) -> str:
        """Create markdown content from transcription data and metadata."""

        def _escape_quotes(value: str | None) -> str:
            if value is None:
                return ""
            sanitized = str(value).replace('"', '\\"')
            sanitized = sanitized.replace("\r\n", "\n").replace("\r", "\n")
            sanitized = sanitized.replace("\n", "\\n")
            return sanitized

        def _format_human_date(value: Any) -> str | None:
            if value is None:
                return None
            if isinstance(value, datetime):
                return value.strftime("%B %d, %Y")
            if isinstance(value, date):
                return value.strftime("%B %d, %Y")
            if isinstance(value, str):
                cleaned = value.strip()
                if not cleaned:
                    return None
                try:
                    if cleaned.isdigit() and len(cleaned) == 8:
                        parsed = datetime.strptime(cleaned, "%Y%m%d")
                    else:
                        parsed = datetime.fromisoformat(cleaned)
                    return parsed.strftime("%B %d, %Y")
                except ValueError:
                    return cleaned
            return str(value)

        frontmatter: list[str] = ["---"]

        # Add source_id FIRST (critical for ID extraction by Process Tab)
        source_id = None
        if source_metadata and source_metadata.get("source_id"):
            source_id = str(source_metadata["source_id"])
            frontmatter.append(f'source_id: "{_escape_quotes(source_id)}"')

        # Determine source type
        source_type = "Local Audio"
        if source_metadata is not None:
            raw_type = source_metadata.get("source_type") or ""
            raw_type_str = str(raw_type).lower()
            source_type_map = {
                "youtube": "YouTube",
                "youtube_video": "YouTube",
                "rss": "RSS",
                "podcast": "Podcast",
                "upload": "Upload",
                "vimeo": "Vimeo",
            }
            if raw_type_str in source_type_map:
                source_type = source_type_map[raw_type_str]
            elif raw_type_str:
                source_type = str(raw_type).replace("_", " ").title()
            else:
                source_type = "YouTube"

        display_title: str | None = None
        formatted_upload_date: str | None = None
        video_duration_seconds: int | None = None
        tags_list: list[str] = []
        categories_list: list[str] = []
        thumbnail_path: str | None = None
        thumbnail_url: str | None = None
        video_url: str = ""
        video_id: str = ""
        description_text: str | None = None
        view_count_value: int | None = None
        like_count_value: int | None = None
        comment_count_value: int | None = None
        uploader_value: str | None = None
        uploader_id_value: str | None = None

        if source_metadata is not None:
            raw_title = source_metadata.get("title") or "Unknown"
            display_title = str(raw_title)
            frontmatter.append(f'title: "{_escape_quotes(display_title)}"')

            video_url = str(source_metadata.get("url") or "")
            if video_url:
                frontmatter.append(f'source: "{_escape_quotes(video_url)}"')

            if source_metadata.get("video_id"):
                video_id = str(source_metadata.get("video_id"))
                frontmatter.append(f'video_id: "{_escape_quotes(video_id)}"')

            uploader_value = source_metadata.get("uploader")
            if uploader_value:
                frontmatter.append(f'uploader: "{_escape_quotes(str(uploader_value))}"')

            uploader_id_value = source_metadata.get("uploader_id")
            if uploader_id_value:
                frontmatter.append(
                    f'uploader_id: "{_escape_quotes(str(uploader_id_value))}"'
                )

            channel_id_value = source_metadata.get("channel_id")
            if channel_id_value:
                frontmatter.append(
                    f'channel_id: "{_escape_quotes(str(channel_id_value))}"'
                )

            upload_date_raw = source_metadata.get("upload_date")
            formatted_upload_date = _format_human_date(upload_date_raw)
            if formatted_upload_date:
                frontmatter.append(
                    f'upload_date: "{_escape_quotes(formatted_upload_date)}"'
                )

            duration_raw = source_metadata.get("duration")
            if duration_raw is None:
                duration_raw = source_metadata.get("duration_seconds")
            if duration_raw is not None:
                try:
                    video_duration_seconds = int(float(duration_raw))
                except (TypeError, ValueError):
                    video_duration_seconds = None
            if video_duration_seconds is not None:
                frontmatter.append(
                    f'duration: "{self._format_duration(video_duration_seconds)}"'
                )

            view_count = source_metadata.get("view_count")
            if view_count is not None:
                try:
                    view_count_value = int(view_count)
                    frontmatter.append(f"view_count: {view_count_value}")
                except (TypeError, ValueError):
                    view_count_value = None

            like_count = source_metadata.get("like_count")
            if like_count is not None:
                try:
                    like_count_value = int(like_count)
                    frontmatter.append(f"like_count: {like_count_value}")
                except (TypeError, ValueError):
                    like_count_value = None

            comment_count = source_metadata.get("comment_count")
            if comment_count is not None:
                try:
                    comment_count_value = int(comment_count)
                    frontmatter.append(f"comment_count: {comment_count_value}")
                except (TypeError, ValueError):
                    comment_count_value = None

            tags = source_metadata.get("tags") or []
            if isinstance(tags, str):
                tags_list = [tags]
            elif isinstance(tags, list):
                tags_list = [str(tag) for tag in tags if tag]
            if tags_list:
                safe_tags = ", ".join(f'"{_escape_quotes(tag)}"' for tag in tags_list)
                frontmatter.append(f"tags: [{safe_tags}]")
                frontmatter.append(f"tags_count: {len(tags_list)}")

            categories = source_metadata.get("categories") or source_metadata.get(
                "youtube_categories"
            )
            if isinstance(categories, str):
                categories_list = [categories]
            elif isinstance(categories, list):
                categories_list = [str(cat) for cat in categories if cat]
            if categories_list:
                safe_categories = ", ".join(
                    f'"{_escape_quotes(cat)}"' for cat in categories_list
                )
                frontmatter.append(f"categories: [{safe_categories}]")
                frontmatter.append(f"categories_count: {len(categories_list)}")

            description_text = source_metadata.get("description")
            if description_text:
                trimmed_description = description_text.strip()
                if trimmed_description:
                    # Fix: Ensure we don't accidentally skip the first character
                    # The issue was [:277].rstrip() could remove the first char if it was whitespace
                    if len(trimmed_description) > 280:
                        preview = trimmed_description[:277] + "..."
                    else:
                        preview = trimmed_description
                    frontmatter.append(
                        f'description_preview: "{_escape_quotes(preview)}"'
                    )

            raw_thumbnail_path = source_metadata.get("thumbnail_local_path")
            if raw_thumbnail_path:
                try:
                    thumb_posix = Path(raw_thumbnail_path).as_posix()
                    thumbnail_path = thumb_posix
                    frontmatter.append(
                        f'thumbnail_path: "{_escape_quotes(thumb_posix)}"'
                    )
                except Exception:
                    thumbnail_path = str(raw_thumbnail_path)

            thumbnail_url_raw = source_metadata.get("thumbnail_url")
            if thumbnail_url_raw:
                thumbnail_url = str(thumbnail_url_raw)
                frontmatter.append(f'thumbnail_url: "{_escape_quotes(thumbnail_url)}"')
        else:
            raw_filename = audio_metadata.get("filename", "Unknown")
            clean_title = (
                raw_filename.rsplit(".", 1)[0] if "." in raw_filename else raw_filename
            )
            display_title = clean_title.replace("_", " ").strip() or clean_title
            frontmatter.append(f'title: "{_escape_quotes(display_title)}"')
            frontmatter.append(f'source_file: "{_escape_quotes(raw_filename)}"')
            frontmatter.append(f'source: "{source_type}"')

            file_format_value = audio_metadata.get("file_format")
            if file_format_value:
                frontmatter.append(
                    f'file_format: "{_escape_quotes(str(file_format_value))}"'
                )

            if audio_metadata.get("file_size_mb"):
                frontmatter.append(
                    f'file_size_mb: {audio_metadata["file_size_mb"]:.2f}'
                )

            duration_formatted = audio_metadata.get("duration_formatted")
            if duration_formatted:
                frontmatter.append(f'duration: "{duration_formatted}"')

            created_date_value = audio_metadata.get("created_date")
            if created_date_value:
                frontmatter.append(
                    f'created_date: "{_escape_quotes(str(created_date_value))}"'
                )

            modified_date_value = audio_metadata.get("modified_date")
            if modified_date_value:
                frontmatter.append(
                    f'modified_date: "{_escape_quotes(str(modified_date_value))}"'
                )

        frontmatter.append(f'source_type: "{source_type}"')

        trans_date = datetime.now()
        frontmatter.append(f'transcription_date: "{trans_date.strftime("%B %d, %Y")}"')
        frontmatter.append(f'transcription_type: "{source_type}"')

        # Language detection (try to get real language instead of "unknown")
        language = transcription_data.get("language", "unknown") or "unknown"
        if language == "unknown" and transcription_data.get("text"):
            text_sample = transcription_data.get("text", "")[:500].lower()
            if any(word in text_sample for word in [" the ", " and ", " is ", " are "]):
                language = "en"
        frontmatter.append(f'language: "{language}"')

        frontmatter.append(
            f'transcription_model: "{_escape_quotes(str(model_metadata.get("model", "unknown")))}"'
        )

        if model_metadata.get("device"):
            frontmatter.append(
                f'device: "{_escape_quotes(str(model_metadata.get("device")))}"'
            )

        frontmatter.append(f'text_length: {len(transcription_data.get("text", ""))}')
        frontmatter.append(
            f'segments_count: {len(transcription_data.get("segments", []))}'
        )

        if model_metadata.get("diarization_enabled"):
            frontmatter.append("diarization_enabled: true")

        frontmatter.append(
            f"include_timestamps: {'true' if include_timestamps else 'false'}"
        )
        frontmatter.append("---")

        lines = frontmatter + [""]

        # Note: We don't add an H1 heading here because Obsidian and similar markdown viewers
        # automatically display the YAML title field as the document heading.
        # Adding a redundant H1 would create duplicate titles in the UI.

        # Insert thumbnail imagery for rich context
        if source_metadata is not None:
            thumbnail_rendered = False
            if thumbnail_path:
                thumb_candidate = Path(thumbnail_path)
                if thumb_candidate.exists():
                    # 🔧 FIX: Use relative path instead of absolute path for portability
                    # Extract just the relative portion (e.g., "downloads/youtube/Thumbnails/filename.jpg")
                    # or "Thumbnails/filename.jpg" depending on structure
                    thumb_path_str = str(thumb_candidate)

                    # Try to find common base directories to make path relative
                    if "downloads/youtube/Thumbnails" in thumb_path_str:
                        # Extract from "downloads/youtube/Thumbnails" onwards
                        relative_path = thumb_path_str[
                            thumb_path_str.find("downloads/youtube/Thumbnails") :
                        ]
                    elif "Thumbnails" in thumb_path_str:
                        # Extract from "Thumbnails" onwards
                        relative_path = thumb_path_str[
                            thumb_path_str.find("Thumbnails") :
                        ]
                    else:
                        # Fallback: just use filename
                        relative_path = f"Thumbnails/{thumb_candidate.name}"

                    lines.append(f"![Thumbnail]({relative_path})")
                    lines.append("")
                    thumbnail_rendered = True
            if not thumbnail_rendered and thumbnail_url:
                lines.append(f"![Thumbnail]({thumbnail_url})")
                lines.append("")

        if source_metadata is not None:
            if description_text:
                # Use "YouTube Description" for YouTube videos, "Description" for others
                if source_type == "YouTube":
                    lines.append("## YouTube Description")
                else:
                    lines.append("## Description")
                lines.append("")
                for desc_line in description_text.strip().splitlines():
                    if desc_line:
                        lines.append(f"> {desc_line}")
                    else:
                        lines.append(">")
                lines.append("")
        else:
            lines.append("## File Metadata")
            lines.append("")
            lines.append(
                f"- **Source File:** {audio_metadata.get('filename', 'Unknown')}"
            )
            if audio_metadata.get("file_format"):
                lines.append(
                    f"- **Format:** {audio_metadata.get('file_format', 'unknown').upper()}"
                )
            if audio_metadata.get("file_size_mb"):
                lines.append(f"- **Size:** {audio_metadata['file_size_mb']:.2f} MB")
            if audio_metadata.get("duration_formatted"):
                lines.append(f"- **Duration:** {audio_metadata['duration_formatted']}")
            lines.append("")

        # Full transcript section
        lines.append("## Full Transcript")
        lines.append("")

        segments = transcription_data.get("segments", [])
        if segments:
            # Optimized for better markdown readability:
            # - Shorter paragraphs for easier scanning
            # - More aggressive breaking on pauses for natural flow
            # - Prioritize sentence boundaries for clean breaks
            pause_threshold_seconds = 3.0  # Break on shorter pauses (was 7.0)
            max_paragraph_chars = 500  # Shorter paragraphs for readability (was 900)
            force_break_chars = 700  # Force break at reasonable length (was 1200)
            current_paragraph: list[str] = []
            current_speaker = ""
            paragraph_start_time: float | None = None
            last_end_time: float | None = None
            last_flushed_speaker = ""  # Track last speaker label written

            def flush_paragraph() -> None:
                nonlocal current_paragraph, paragraph_start_time, current_speaker, last_flushed_speaker
                if not current_paragraph:
                    return
                paragraph_text = " ".join(current_paragraph).strip()
                if not paragraph_text:
                    current_paragraph = []
                    paragraph_start_time = None
                    return

                # Format with speaker and timestamp on header line for readability
                speaker_label = current_speaker.strip()

                # Only show speaker label if it changed from last paragraph (for readability in monologues)
                if speaker_label and speaker_label != last_flushed_speaker:
                    if include_timestamps and paragraph_start_time is not None:
                        # Format: **Speaker** [timestamp]
                        timestamp_str = self._format_duration(
                            int(round(paragraph_start_time))
                        )
                        lines.append(f"**{speaker_label}** [{timestamp_str}]")
                    else:
                        # Format: **Speaker**
                        lines.append(f"**{speaker_label}**")
                    last_flushed_speaker = speaker_label
                elif include_timestamps and paragraph_start_time is not None:
                    # Same speaker or no speaker, just show timestamp
                    timestamp_str = self._format_duration(
                        int(round(paragraph_start_time))
                    )
                    lines.append(f"[{timestamp_str}]")

                # Add paragraph text
                lines.append(paragraph_text)
                lines.append("")  # Blank line between paragraphs

                current_paragraph = []
                paragraph_start_time = None

            def ends_with_sentence_boundary(text: str) -> bool:
                """Check if text ends with a sentence boundary (period, !, ?, etc.)"""
                text = text.rstrip()
                return text.endswith(
                    (".", "!", "?", '."', '!"', '?"', '.")', '!")', '?")')
                )

            for segment in segments:
                text = (segment.get("text") or "").strip()
                if not text:
                    continue

                start_time = segment.get("start")
                end_time = segment.get("end")
                normalized_speaker = (segment.get("speaker") or "").strip()

                long_pause = (
                    last_end_time is not None
                    and start_time is not None
                    and (float(start_time) - float(last_end_time))
                    >= pause_threshold_seconds
                )

                paragraph_candidate_length = len(" ".join(current_paragraph + [text]))

                needs_new_paragraph = False
                if current_paragraph:
                    # Always break on speaker change
                    if normalized_speaker != current_speaker:
                        needs_new_paragraph = True
                    # Break on long pauses (now more sensitive - 3s instead of 7s)
                    elif long_pause:
                        needs_new_paragraph = True
                    # For length-based breaks, prioritize sentence boundaries
                    elif paragraph_candidate_length >= max_paragraph_chars:
                        # Check if the last segment ended with a sentence boundary
                        if current_paragraph and ends_with_sentence_boundary(
                            current_paragraph[-1]
                        ):
                            needs_new_paragraph = True
                        # If we're way over the limit, force a break
                        elif paragraph_candidate_length >= force_break_chars:
                            needs_new_paragraph = True
                    # Break on explicit paragraph markers
                    elif "\n\n" in text:
                        needs_new_paragraph = True

                if needs_new_paragraph:
                    flush_paragraph()

                if not current_paragraph:
                    current_speaker = normalized_speaker
                    paragraph_start_time = (
                        float(start_time) if start_time is not None else None
                    )

                current_paragraph.append(text)

                if end_time is not None:
                    last_end_time = float(end_time)
                elif start_time is not None:
                    last_end_time = float(start_time)

            flush_paragraph()
        else:
            text = transcription_data.get("text", "").strip()
            if text:
                lines.append(text)

        return "\n".join(lines)

    def save_transcript_to_markdown(
        self,
        transcription_result: ProcessorResult,
        audio_path: Path,
        output_dir: str | Path | None = None,
        include_timestamps: bool = True,
        source_metadata: dict | None = None,
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

            # Create filename - use clean title from metadata if available
            if source_metadata and source_metadata.get("title"):
                # Use the clean title from metadata (preferred for YouTube videos)
                import re

                raw_title = str(source_metadata.get("title", ""))
                # Remove video ID pattern [11 chars] if present
                clean_title = re.sub(
                    r"\s*\[[a-zA-Z0-9_-]{11}\]\s*$", "", raw_title
                ).strip()
                # Sanitize for filename - keep spaces for better readability in file browsers
                safe_name = "".join(
                    c for c in clean_title if c.isalnum() or c in (" ", "-", "_")
                ).rstrip()
                # Keep spaces in filename for natural display in Obsidian and file browsers
            else:
                # Fallback to audio filename for local files
                base_name = audio_path.stem
                safe_name = "".join(
                    c for c in base_name if c.isalnum() or c in (" ", "-", "_")
                ).rstrip()
                # Keep spaces in filename for natural display

            # Don't append "_transcript" suffix - use clean title as-is
            filename = f"{safe_name}.md"
            output_path = output_dir / filename

            logger.debug(f"Attempting to save transcript to: {output_path}")

            # Get metadata
            audio_metadata = self._get_audio_metadata(audio_path)
            model_metadata = transcription_result.metadata or {}

            # Create markdown content with timestamps preference and video metadata if available
            markdown_content = self._create_markdown(
                transcription_result.data,
                audio_metadata,
                model_metadata,
                include_timestamps=include_timestamps,
                source_metadata=source_metadata,
            )

            # Write file with detailed error handling
            try:
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(markdown_content)

                # Verify file was written
                if output_path.exists() and output_path.stat().st_size > 0:
                    logger.info(
                        f"📝 Transcript markdown file saved: {output_path} ({len(markdown_content):,} characters)"
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
        # SECURITY CHECK: Verify app authorization before transcription
        # Add timeout to prevent indefinite hanging
        try:
            import threading

            from knowledge_system.utils.security_verification import (
                ensure_secure_before_transcription,
            )

            # Create a timeout mechanism for security verification
            security_result: list[bool | None] = [None]
            security_error: list[Exception | None] = [None]

            def security_check():
                try:
                    ensure_secure_before_transcription()
                    security_result[0] = True
                except Exception as e:
                    security_error[0] = e

            # Run security check with 10 second timeout
            security_thread = threading.Thread(target=security_check, daemon=True)
            security_thread.start()
            security_thread.join(timeout=10)

            if security_thread.is_alive():
                logger.warning(
                    "Security verification timed out - proceeding with transcription"
                )
            elif security_error[0]:
                logger.error(f"Security verification failed: {security_error[0]}")
                return ProcessorResult(
                    success=False,
                    errors=[
                        f"App not properly authorized for transcription: {security_error[0]}. Please restart the app and complete the authorization process."
                    ],
                    dry_run=dry_run,
                )
            elif security_result[0]:
                logger.debug("Security verification passed")

        except ImportError:
            logger.warning(
                "Security verification module not available - proceeding with transcription"
            )
        except Exception as e:
            logger.error(f"Security verification failed: {e}")
            return ProcessorResult(
                success=False,
                errors=[
                    f"App not properly authorized for transcription: {e}. Please restart the app and complete the authorization process."
                ],
                dry_run=dry_run,
            )

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
        """
        Attempt transcription with smart quality recovery.

        Recovery strategy:
        1. Transcribe with selected model
        2. If severe quality issues detected -> retry with next larger model
        3. If still failing -> return special error code for re-download + large model
        4. If still failing after re-download -> permanent failure
        """
        current_model = self.model
        audio_duration = audio_metadata.get("duration_seconds")
        output_path = None  # Track temp file for cleanup

        # Initialize diarization variables at function scope to avoid scope issues
        diarization_segments = None
        diarization_successful = False

        # Get source_id for queue tracking
        source_id = kwargs.get("source_id")

        # Update queue status to in_progress
        if source_id and self.db_service:
            self.db_service.upsert_stage_status(
                source_id=source_id,
                stage="transcription",
                status="in_progress",
                progress_percent=0.0,
                metadata={
                    "model": current_model,
                    "audio_duration_seconds": audio_duration,
                    "audio_file": str(path),
                },
            )

        # Smart recovery: try current model, then one upgrade
        max_attempts = 2
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
                    # Create new transcriber with better model and acceleration
                    self.transcriber = WhisperCppTranscribeProcessor(
                        model=current_model,
                        use_coreml=True,
                        progress_callback=self.progress_callback,
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
                    # Clean up temp file before returning
                    if output_path and output_path.exists():
                        output_path.unlink(missing_ok=True)
                    return ProcessorResult(success=False, errors=[error_msg])

                # Apply Apple Silicon optimizations if available
                audio_duration = audio_metadata.get("duration_seconds") or 3600.0
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

                # Force disable diarization during testing mode to prevent GUI threading issues
                testing_mode = os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE") == "1"
                if testing_mode:
                    logger.info(
                        "🧪 Testing mode: Force disabling diarization to prevent GUI threading issues"
                    )
                    diarization_enabled = False
                memory_gb = psutil.virtual_memory().total / (1024**3)

                # Check if we should use streaming processing for very long files
                use_streaming = should_use_streaming_processing(
                    audio_duration, memory_gb
                )

                if use_streaming:
                    duration_str = (
                        f"{audio_duration/60:.1f}"
                        if audio_duration
                        else "unknown duration"
                    )
                    logger.info(
                        f"🌊 Using streaming processing for {duration_str} minute file"
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
                            # Use preloaded diarizer if available, otherwise create new one
                            if (
                                hasattr(self, "preloaded_diarizer")
                                and self.preloaded_diarizer
                            ):
                                diarizer = self.preloaded_diarizer
                                logger.info("✅ Using preloaded diarization model")
                            else:
                                diarizer = SpeakerDiarizationProcessor(
                                    hf_token=self.hf_token,
                                    device=self.device,
                                    progress_callback=self.progress_callback,
                                )
                                logger.info("🔄 Created new diarization model instance")

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

                # Note: Don't clean up temporary file yet - diarization might need it
                # Cleanup will happen after all processing is complete

                if transcription_result.success:
                    # Check for cleanup stats from hallucination removal
                    cleanup_stats = getattr(
                        self.transcriber, "_last_cleanup_stats", None
                    )
                    if cleanup_stats and cleanup_stats.get("removed_count", 0) > 0:
                        removed = cleanup_stats["removed_count"]
                        patterns = len(cleanup_stats.get("patterns_found", []))

                        # Categorize severity
                        if removed >= 20 or patterns >= 2:
                            # Heavy repetition - log warning and consider retry
                            logger.warning(
                                f"⚠️ Heavy hallucination detected: {removed} repetitions across "
                                f"{patterns} pattern(s) - cleaned automatically"
                            )
                            if self.progress_callback:
                                self.progress_callback(
                                    f"⚠️ Cleaned {removed} hallucinated repetitions",
                                    None,
                                )
                        elif removed >= 10:
                            # Moderate repetition - log info
                            logger.info(
                                f"Moderate hallucination cleaned: {removed} repetitions"
                            )
                        # Light repetition (3-9) - already logged by cleanup function

                        # Clear cleanup stats for next transcription
                        if hasattr(self.transcriber, "_last_cleanup_stats"):
                            delattr(self.transcriber, "_last_cleanup_stats")

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

                                # Smart recovery logic
                                if attempt == 0:
                                    # First attempt failed - try next larger model
                                    if self.progress_callback:
                                        self.progress_callback(
                                            f"⚠️ Quality issue detected, retrying with better model...",
                                            0,
                                        )
                                    logger.info(
                                        "Attempting retry with better model due to quality issues..."
                                    )
                                    # Clean up temp file before retry
                                    if output_path and output_path.exists():
                                        output_path.unlink(missing_ok=True)
                                    continue
                                else:
                                    # Second attempt also failed - signal need for re-download
                                    logger.error(
                                        f"Quality issues persist after model upgrade: {failure_reason}"
                                    )
                                    if self.progress_callback:
                                        self.progress_callback(
                                            f"⚠️ Audio may be corrupted, attempting re-download...",
                                            0,
                                        )
                                    self._log_transcription_failure(
                                        path,
                                        failure_reason,
                                        current_model,
                                        audio_duration,
                                    )
                                    # Clean up temporary file before returning
                                    if output_path and output_path.exists():
                                        output_path.unlink(missing_ok=True)

                                    # Return special error code to trigger re-download
                                    return ProcessorResult(
                                        success=False,
                                        errors=[
                                            f"AUDIO_CORRUPTION_SUSPECTED: {failure_reason}"
                                        ],
                                        metadata={
                                            "needs_redownload": True,
                                            "failure_reason": failure_reason,
                                            "models_tried": [self.model, current_model],
                                        },
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

                        # Initialize result data
                        final_data = transcription_result.data
                        # Reset diarization variables for this attempt
                        diarization_segments = None
                        diarization_successful = False

                        if diarization_enabled:
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

                                # Verify speaker labels are actually in segments
                                speaker_count = len(
                                    {
                                        seg.get("speaker")
                                        for seg in final_data.get("segments", [])
                                        if seg.get("speaker")
                                    }
                                )
                                if speaker_count > 0:
                                    logger.info(
                                        f"✅ Detected {speaker_count} unique speakers in merged segments"
                                    )
                                else:
                                    logger.warning(
                                        "⚠️ Diarization completed but no speaker labels found in segments"
                                    )
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

                                    # Verify speaker labels are actually in segments
                                    speaker_count = len(
                                        {
                                            seg.get("speaker")
                                            for seg in final_data.get("segments", [])
                                            if seg.get("speaker")
                                        }
                                    )
                                    if speaker_count > 0:
                                        logger.info(
                                            f"✅ Detected {speaker_count} unique speakers in merged segments (sequential)"
                                        )
                                    else:
                                        logger.warning(
                                            "⚠️ Sequential diarization completed but no speaker labels found in segments"
                                        )

                            # Note: Speaker assignment will be handled after database save
                            # to enable non-blocking processing

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

                        # CRITICAL: Apply automatic speaker assignments BEFORE saving markdown
                        # This ensures the markdown file has real names, not SPEAKER_00
                        if diarization_successful and diarization_segments:
                            logger.info(
                                "🎯 Applying automatic speaker assignments before saving..."
                            )
                            logger.info(
                                f"   Diarization successful: {diarization_successful}"
                            )
                            logger.info(
                                f"   Diarization segments count: {len(diarization_segments) if diarization_segments else 0}"
                            )
                            try:
                                from .speaker_processor import SpeakerProcessor

                                speaker_processor = SpeakerProcessor()
                                transcript_segments = final_data.get("segments", [])

                                # Get metadata from all sources (non-destructive multi-source approach)
                                source_id = kwargs.get("source_id")
                                if source_id and self.db_service:
                                    logger.info(
                                        f"🔍 Retrieving metadata from all sources for {source_id}"
                                    )
                                    all_metadata = (
                                        self.db_service.get_all_source_metadata(
                                            source_id
                                        )
                                    )
                                else:
                                    # Fallback for non-database sources (local files, etc.)
                                    logger.debug(
                                        "No source_id or db_service, using metadata from kwargs"
                                    )
                                    metadata_for_speaker = kwargs.get(
                                        "source_metadata"
                                    ) or kwargs.get("metadata", {})
                                    all_metadata = {
                                        "primary_source": metadata_for_speaker,
                                        "aliased_sources": [],
                                    }

                                # Prepare speaker data with multi-source metadata for enhanced suggestions
                                speaker_data_list = speaker_processor.prepare_speaker_data(
                                    diarization_segments,
                                    transcript_segments,
                                    all_metadata,
                                    str(
                                        output_path
                                    ),  # Pass converted WAV path for voice fingerprinting (same file used for diarization)
                                )

                                if speaker_data_list:
                                    # Get automatic assignments (from DB, AI, or fallback)
                                    assignments = (
                                        self._get_automatic_speaker_assignments(
                                            speaker_data_list, str(path)
                                        )
                                    )

                                    if assignments:
                                        # Apply assignments to transcript data
                                        final_data = (
                                            speaker_processor.apply_speaker_assignments(
                                                final_data,
                                                assignments,
                                                str(path),
                                                speaker_data_list,
                                            )
                                        )
                                        logger.info(
                                            f"✅ Applied automatic speaker assignments: {assignments}"
                                        )
                                        # Store assignments for reference
                                        final_data["speaker_assignments"] = assignments
                                    else:
                                        logger.warning(
                                            "⚠️ No automatic speaker assignments could be generated"
                                        )
                                else:
                                    logger.warning(
                                        "⚠️ No speaker data prepared for automatic assignment"
                                    )
                            except Exception as e:
                                logger.error(
                                    f"❌ Failed to apply automatic speaker assignments: {e}",
                                    exc_info=True,
                                )
                                # Add failure info to metadata so user can see what happened
                                enhanced_metadata["speaker_assignment_failed"] = True
                                enhanced_metadata["speaker_assignment_error"] = str(e)
                                # Continue anyway - markdown will have generic SPEAKER_00 labels
                        else:
                            # 🚨 CRITICAL: This block should NOT be reached if diarization was enabled!
                            if diarization_enabled:
                                logger.error(
                                    f"🚨 CRITICAL: Diarization was enabled but speaker assignment skipped!"
                                )
                                logger.error(
                                    f"   diarization_successful: {diarization_successful}"
                                )
                                logger.error(
                                    f"   diarization_segments: {diarization_segments is not None}"
                                )
                                logger.error(
                                    f"   This means diarization failed or segments are missing"
                                )

                        # Save to markdown if output directory is specified AND format is not "none"
                        output_dir = kwargs.get("output_dir")
                        output_format = kwargs.get(
                            "format", "md"
                        )  # Default to markdown if not specified
                        include_timestamps = kwargs.get("timestamps", True)
                        enable_color_coding = kwargs.get("enable_color_coding", True)
                        saved_file = None

                        if output_dir and output_format != "none":
                            # Ensure output_dir is a Path object
                            output_dir = Path(output_dir)
                            temp_result = ProcessorResult(
                                success=True,
                                data=final_data,
                                metadata=enhanced_metadata,
                            )

                            # Save regular markdown transcript
                            # Extract source_metadata from kwargs if this is a YouTube video
                            source_metadata = kwargs.get("source_metadata")

                            # Debug log: Check if segments have speaker info
                            if final_data.get("segments"):
                                segments_with_speakers = [
                                    s
                                    for s in final_data["segments"]
                                    if s.get("speaker")
                                ]
                                logger.info(
                                    f"Saving markdown with {len(segments_with_speakers)}/{len(final_data['segments'])} segments having speaker labels"
                                )

                            saved_file = self.save_transcript_to_markdown(
                                temp_result,
                                path,
                                output_dir,
                                include_timestamps=include_timestamps,
                                source_metadata=source_metadata,
                            )

                            # Save color-coded transcript if speakers are identified and color coding is enabled
                            if (
                                enable_color_coding
                                and diarization_successful
                                and final_data.get("speaker_assignments")
                            ):
                                color_coded_file = self._save_color_coded_transcript(
                                    final_data, path, output_dir, include_timestamps
                                )

                                if color_coded_file:
                                    enhanced_metadata["saved_color_coded_file"] = str(
                                        color_coded_file
                                    )

                            if saved_file:
                                enhanced_metadata["saved_markdown_file"] = str(
                                    saved_file
                                )
                        elif output_format == "none":
                            logger.info(
                                "📝 Output format set to 'none' - skipping file creation, will save to database only"
                            )
                        else:
                            logger.debug(
                                f"Skipping file creation: output_dir={output_dir}, format={output_format}"
                            )

                        # Save to database - db_service is required for claim-centric architecture
                        db_service = kwargs.get("db_service")
                        if not db_service:
                            # Database service is required - don't create fallback
                            logger.error(
                                "❌ db_service not provided - cannot save to database (required for claim-centric architecture)"
                            )
                            enhanced_metadata["database_save_failed"] = True
                            enhanced_metadata[
                                "database_error"
                            ] = "db_service parameter not provided"

                        if db_service and final_data:
                            try:
                                # Create consistent media ID from file path for re-runs
                                import hashlib
                                from datetime import datetime

                                # Check if source_id is provided (e.g., from YouTube download)
                                source_metadata = kwargs.get("source_metadata")
                                source_id = None
                                if source_metadata and source_metadata.get("source_id"):
                                    source_id = source_metadata["source_id"]
                                    logger.info(
                                        f"Using existing source_id from metadata: {source_id}"
                                    )

                                # If no source_id provided, generate one from file path
                                if not source_id:
                                    # Use hash of absolute path for consistent ID across re-runs
                                    path_hash = hashlib.md5(
                                        str(path.absolute()).encode(),
                                        usedforsecurity=False,
                                    ).hexdigest()[:8]
                                    source_id = f"audio_{path.stem}_{path_hash}"
                                    logger.info(
                                        f"Generated new source_id from file path: {source_id}"
                                    )

                                # Check if media source already exists (for re-runs or YouTube downloads)
                                existing_source = db_service.get_source(source_id)
                                if existing_source:
                                    # Update existing source with latest data
                                    logger.info(
                                        f"Using existing media source: {source_id}"
                                    )
                                    db_service.update_source(
                                        source_id=source_id,
                                        duration_seconds=audio_duration,
                                        status="completed",
                                        processed_at=datetime.now(),
                                    )
                                else:
                                    # Create new media source record only for local files
                                    # (YouTube videos should already have MediaSource from download phase)
                                    title = (
                                        source_metadata.get("title")
                                        if source_metadata
                                        else path.stem.replace("_", " ").title()
                                    )
                                    file_url = (
                                        source_metadata.get("url")
                                        if source_metadata
                                        else f"file://{path.absolute()}"
                                    )
                                    source_type = (
                                        source_metadata.get("source_type")
                                        if source_metadata
                                        else "document"
                                    )

                                    logger.info(
                                        f"Creating new media source record: {source_id}"
                                    )
                                    db_service.create_source(
                                        source_id=source_id,
                                        title=title,
                                        url=file_url,
                                        source_type=source_type,  # Valid: 'episode', 'document', 'youtube', 'pdf', 'article', 'podcast', 'rss'
                                        duration_seconds=audio_duration,
                                        upload_date=datetime.now().strftime(
                                            "%Y%m%d"
                                        ),  # YYYYMMDD format
                                        description=f"Audio file: {path.name}",
                                        status="completed",
                                    )
                                    logger.info(
                                        f"Created media source record: {source_id}"
                                    )

                                    # Mark download stage as skipped for local files
                                    if source_type == "document":
                                        db_service.upsert_stage_status(
                                            source_id=source_id,
                                            stage="download",
                                            status="skipped",
                                            progress_percent=100.0,
                                            metadata={
                                                "reason": "local_file",
                                                "file_path": str(path.absolute()),
                                            },
                                        )

                                # Extract transcript data
                                transcript_text = final_data.get("text", "")
                                segments = final_data.get("segments", [])
                                language = final_data.get("language", "en")

                                # Prepare diarization segments if available
                                diarization_segments_json = None
                                if diarization_enabled and segments:
                                    # Check if segments have speaker information
                                    if any(seg.get("speaker") for seg in segments):
                                        diarization_segments_json = segments

                                # Create transcript record (overwrites existing for re-runs)
                                transcript_record = db_service.create_transcript(
                                    source_id=source_id,
                                    language=language,
                                    is_manual=False,
                                    transcript_text=transcript_text,
                                    transcript_segments=segments,
                                    transcript_type="whisper",
                                    whisper_model=model_name,
                                    device_used=device or self.device,
                                    diarization_enabled=diarization_enabled,
                                    diarization_segments_json=diarization_segments_json,
                                    include_timestamps=include_timestamps,
                                    processing_time_seconds=enhanced_metadata.get(
                                        "processing_time_seconds"
                                    ),
                                )

                                if transcript_record:
                                    logger.info(
                                        f"💾 Transcript saved to database: {transcript_record.transcript_id}"
                                    )
                                    enhanced_metadata[
                                        "database_transcript_id"
                                    ] = transcript_record.transcript_id
                                    enhanced_metadata["database_media_id"] = source_id

                                    # Log final success - both markdown and database saved
                                    logger.info(
                                        f"✅ Transcription complete: markdown + database saved successfully"
                                    )

                                    # Queue for manual review if speaker dialog is enabled
                                    # Note: Automatic assignments were already applied before saving
                                    if diarization_successful and diarization_segments:
                                        # Determine if manual review should be queued
                                        should_queue_review = (
                                            self._should_queue_speaker_review(kwargs)
                                        )

                                        if should_queue_review:
                                            # Pass the transcript_id and source_id for speaker assignment
                                            kwargs_with_ids = kwargs.copy()
                                            kwargs_with_ids[
                                                "transcript_id"
                                            ] = transcript_record.transcript_id
                                            kwargs_with_ids["video_id"] = source_id
                                            kwargs_with_ids[
                                                "database_transcript_id"
                                            ] = transcript_record.transcript_id
                                            kwargs_with_ids[
                                                "database_media_id"
                                            ] = source_id

                                            # Queue for manual review (automatic assignments already applied)
                                            logger.info(
                                                "Queueing speaker assignment for manual review..."
                                            )
                                            self._handle_speaker_assignment(
                                                final_data,
                                                diarization_segments,
                                                str(path),
                                                kwargs_with_ids,
                                            )
                                        else:
                                            logger.info(
                                                "Automatic speaker assignments complete - skipping manual review queue"
                                            )
                                else:
                                    logger.warning(
                                        "Failed to save transcript to database"
                                    )

                            except Exception as e:
                                logger.error(
                                    f"❌ Failed to save transcript to database: {e}"
                                )
                                logger.error(f"Database error type: {type(e).__name__}")
                                logger.error(f"Database error details: {str(e)}")
                                logger.error(
                                    "⚠️  CRITICAL: Markdown file saved but database save FAILED"
                                )
                                logger.error(
                                    "⚠️  This transcription will be marked as FAILED (database is required)"
                                )
                                # IMPORTANT: Database save failure should affect success reporting
                                # Based on memory requirement: all transcriptions must write to database
                                enhanced_metadata["database_save_failed"] = True
                                enhanced_metadata["database_error"] = str(e)

                        # Clean up temporary file before returning success
                        if output_path and output_path.exists():
                            output_path.unlink(missing_ok=True)

                        # Check if database save failed - affects success status
                        database_save_failed = enhanced_metadata.get(
                            "database_save_failed", False
                        )

                        if database_save_failed:
                            # Based on memory requirement: all transcriptions must write to database
                            logger.error(
                                "❌ TRANSCRIPTION FAILED: Database save required but failed"
                            )
                            return ProcessorResult(
                                success=False,
                                errors=[
                                    "Database save failed (required for claim-centric architecture)"
                                ],
                                data=None,  # Don't include data if we're reporting failure
                                metadata=enhanced_metadata,
                            )
                        else:
                            # Update queue status to completed
                            if source_id and self.db_service:
                                self.db_service.upsert_stage_status(
                                    source_id=source_id,
                                    stage="transcription",
                                    status="completed",
                                    progress_percent=100.0,
                                    metadata={
                                        "model": current_model,
                                        "transcript_id": enhanced_metadata.get(
                                            "database_transcript_id"
                                        ),
                                        "processing_time_seconds": enhanced_metadata.get(
                                            "processing_time_seconds"
                                        ),
                                    },
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
                        # Clean up temporary file before returning
                        if output_path and output_path.exists():
                            output_path.unlink(missing_ok=True)

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
                    # Clean up temporary file before returning
                    if output_path and output_path.exists():
                        output_path.unlink(missing_ok=True)

                    return ProcessorResult(success=False, errors=[str(e)])
                else:
                    # Clean up temp file before retry
                    if output_path and output_path.exists():
                        output_path.unlink(missing_ok=True)
                    # Try retry
                    continue

        # If we get here, all attempts failed
        final_error = f"All transcription attempts failed for {path}"
        self._log_transcription_failure(
            path, final_error, current_model, audio_duration
        )
        # Clean up temporary file before returning
        if output_path and output_path.exists():
            output_path.unlink(missing_ok=True)

        # Update queue status to failed
        if source_id and self.db_service:
            self.db_service.upsert_stage_status(
                source_id=source_id,
                stage="transcription",
                status="failed",
                metadata={
                    "error": final_error,
                    "retry_count": max_attempts,
                    "final_model": current_model,
                },
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

    def _show_mvp_llm_error(self, error: Exception):
        """Show user-friendly error dialog for MVP LLM setup issues."""
        try:
            # Import here to avoid circular imports
            from ..gui.components.enhanced_error_dialog import show_enhanced_error

            error_msg = str(error)

            # Determine error context for better categorization
            if "ollama" in error_msg.lower():
                context = "mvp_llm_setup"
            elif "permission" in error_msg.lower() or "denied" in error_msg.lower():
                context = "mvp_llm_setup"
            elif "connection" in error_msg.lower() or "service" in error_msg.lower():
                context = "mvp_llm_service"
            elif "model" in error_msg.lower():
                context = "mvp_llm_model"
            else:
                context = "mvp_llm_setup"

            # Show enhanced error dialog
            show_enhanced_error(
                parent=None,  # Will find active window
                title="MVP AI System Issue",
                message=f"The built-in AI system encountered an issue: {error_msg}",
                details=str(error),
                context=context,
            )

        except Exception as e:
            # Fallback to simple logging
            logger.warning(f"Could not show MVP LLM error dialog: {e}")


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
