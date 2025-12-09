"""
Whisper.cpp Transcription Processor using pywhispercpp

This module provides audio transcription using whisper.cpp through the pywhispercpp
Python binding. It enables DTW word-level timestamps for accurate speaker attribution.
"""

import platform
import time
from pathlib import Path
from typing import Any

from knowledge_system.logger import get_logger
from knowledge_system.processors.base import BaseProcessor, ProcessorResult

logger = get_logger(__name__)

# Lazy load pywhispercpp to avoid import errors if not installed
PYWHISPERCPP_AVAILABLE = False
Model = None


def _check_pywhispercpp():
    """Check if pywhispercpp is available and import it."""
    global PYWHISPERCPP_AVAILABLE, Model
    if PYWHISPERCPP_AVAILABLE:
        return True
    try:
        from pywhispercpp.model import Model as WhisperModel
        Model = WhisperModel
        PYWHISPERCPP_AVAILABLE = True
        logger.info("✅ pywhispercpp is available")
        return True
    except ImportError as e:
        logger.warning(f"pywhispercpp not available: {e}")
        logger.info("Install with: pip install pywhispercpp>=1.2.0")
        return False


class WhisperCppTranscribeProcessor(BaseProcessor):
    """Transcribes audio files using pywhispercpp (Python binding for whisper.cpp).
    
    This processor uses the pywhispercpp library for fast transcription with
    DTW-based word-level timestamps, which are essential for accurate speaker
    attribution when combined with pyannote diarization.
    """

    def __init__(
        self,
        model: str = "medium",
        use_coreml: bool | None = None,
        progress_callback=None,
        n_threads: int = 8,
    ) -> None:
        self.model_name = model
        self.use_coreml = use_coreml
        self.progress_callback = progress_callback
        self.n_threads = n_threads
        self._model = None
        self._model_loaded = False

        # Auto-detect Core ML usage based on platform
        if self.use_coreml is None:
            self.use_coreml = (
                platform.system() == "Darwin" and platform.machine() == "arm64"
            )

        # Model size mapping for pywhispercpp
        # pywhispercpp uses model names like 'base', 'medium', 'large-v3'
        self.model_mapping = {
            "tiny": "tiny",
            "base": "base",
            "small": "small",
            "medium": "medium.en",  # English-only model (faster, smaller)
            "large": "large-v3",  # Latest large model (best quality)
        }

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

    def validate_input(self, input_path: str | Path) -> bool:
        path = Path(input_path)
        return (
            path.exists()
            and path.is_file()
            and path.suffix.lower() in self.supported_formats
        )

    def can_process(self, input_path: str | Path) -> bool:
        return Path(input_path).suffix.lower() in self.supported_formats

    def _load_model(self) -> bool:
        """Load the pywhispercpp model lazily."""
        if self._model_loaded:
            return self._model is not None

        if not _check_pywhispercpp():
            return False

        try:
            model_name = self.model_mapping.get(self.model_name, self.model_name)
            
            if self.progress_callback:
                self.progress_callback(
                    f"📥 Loading Whisper '{model_name}' model...", 20
                )

            # Initialize pywhispercpp model with word timestamps enabled
            self._model = Model(
                model_name,
                n_threads=self.n_threads,
                print_progress=False,  # We handle progress ourselves
            )
            
            self._model_loaded = True
            logger.info(f"✅ Loaded pywhispercpp model: {model_name}")
            
            if self.progress_callback:
                self.progress_callback(
                    f"✅ Whisper '{model_name}' model loaded", 30
                )
            
            return True

        except Exception as e:
            logger.error(f"Failed to load pywhispercpp model: {e}")
            self._model_loaded = True  # Mark as attempted
            return False

    def _convert_to_wav(self, input_path: Path) -> Path:
        """Convert audio to 16kHz mono WAV format for optimal transcription."""
        import subprocess
        import tempfile

        temp_fd, temp_path = tempfile.mkstemp(suffix=".wav")
        temp_wav = Path(temp_path)

        try:
            # Use ffmpeg to convert to 16kHz mono WAV
            cmd = [
                "ffmpeg",
                "-y",  # Overwrite output
                "-i", str(input_path),
                "-ar", "16000",  # 16kHz sample rate
                "-ac", "1",  # Mono
                "-f", "wav",
                str(temp_wav),
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )
            
            if result.returncode != 0:
                logger.warning(f"FFmpeg conversion warning: {result.stderr}")
            
            return temp_wav

        except Exception as e:
            logger.error(f"Audio conversion failed: {e}")
            raise

    def _is_16khz_mono_wav(self, path: Path) -> bool:
        """Check if file is already 16kHz mono WAV."""
        if path.suffix.lower() != ".wav":
            return False
        
        try:
            import subprocess
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "error",
                    "-select_streams", "a:0",
                    "-show_entries", "stream=sample_rate,channels",
                    "-of", "csv=p=0",
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            if result.returncode == 0:
                parts = result.stdout.strip().split(",")
                if len(parts) >= 2:
                    sample_rate = int(parts[0])
                    channels = int(parts[1])
                    return sample_rate == 16000 and channels == 1
        except Exception:
            pass
        
        return False

    def _get_audio_duration(self, input_path: Path) -> float | None:
        """Get audio duration in seconds using ffprobe."""
        try:
            import subprocess
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "csv=p=0",
                    str(input_path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            if result.returncode == 0:
                return float(result.stdout.strip())
        except Exception as e:
            logger.warning(f"Failed to get audio duration: {e}")
        
        return None

    def process(
        self, input_data: Any, dry_run: bool = False, **kwargs: Any
    ) -> ProcessorResult:
        """Process audio file and return transcription with word-level timestamps.
        
        Args:
            input_data: Path to audio file
            dry_run: If True, skip actual processing
            **kwargs: Additional parameters:
                - language: Language code (e.g., "en") or "auto"
                - entropy_thold: Entropy threshold for hallucination prevention
                - logprob_thold: Log probability threshold
                - temperature: Decoding temperature (0.0 = deterministic)
                
        Returns:
            ProcessorResult with transcription data including word-level timestamps
        """
        input_path = Path(input_data)

        if not self.validate_input(input_path):
            return ProcessorResult(
                success=False, errors=[f"Invalid input: {input_data}"]
            )

        if dry_run:
            return ProcessorResult(
                success=True,
                data={"text": "[DRY RUN]", "segments": [], "words": []},
            )

        return self._process_audio(input_path, **kwargs)

    def _process_audio(self, input_path: Path, **kwargs: Any) -> ProcessorResult:
        """Process audio using pywhispercpp with DTW word timestamps."""
        start_time = time.time()
        temp_wav = None

        # Get file info for logging
        filename = input_path.name
        file_size_mb = input_path.stat().st_size / (1024 * 1024)
        
        logger.info(
            f"🎤 Starting transcription of '{filename}' ({file_size_mb:.1f}MB) with pywhispercpp"
        )

        if self.progress_callback:
            self.progress_callback(
                f"🎤 Initializing transcription for {filename}...", 5
            )

        # Get audio duration for validation
        audio_duration_seconds = self._get_audio_duration(input_path)
        if audio_duration_seconds:
            duration_str = f"{audio_duration_seconds:.1f}s"
            if audio_duration_seconds >= 60:
                duration_str += f" ({audio_duration_seconds/60:.1f}min)"
            logger.info(f"📊 Audio duration: {duration_str}")

        try:
            # Load model if not already loaded
            if not self._load_model():
                return ProcessorResult(
                    success=False,
                    errors=["Failed to load pywhispercpp model. Install with: pip install pywhispercpp>=1.2.0"],
                )

            # Convert audio if needed
            if self._is_16khz_mono_wav(input_path):
                audio_path = input_path
                logger.info(f"✅ Using original file (already 16kHz mono WAV)")
            else:
                if self.progress_callback:
                    self.progress_callback(
                        f"🔄 Converting {filename} to 16kHz mono WAV...", 35
                    )
                temp_wav = self._convert_to_wav(input_path)
                audio_path = temp_wav
                if self.progress_callback:
                    self.progress_callback("✅ Audio conversion completed", 40)

            # Extract transcription parameters
            language = kwargs.get("language", "en")
            if language == "auto":
                language = None  # pywhispercpp uses None for auto-detect

            # Hallucination prevention parameters
            entropy_thold = kwargs.get("entropy_thold")
            if entropy_thold is None:
                entropy_thold = 2.8 if self.model_name == "large" else 2.6
            
            logprob_thold = kwargs.get("logprob_thold", -0.8)
            temperature = kwargs.get("temperature", 0.0)

            logger.info(
                f"🛡️ Hallucination prevention: entropy={entropy_thold}, "
                f"logprob={logprob_thold}, temp={temperature}"
            )

            if self.progress_callback:
                self.progress_callback(
                    f"🎯 Transcribing {filename} with token timestamps...", 50
                )

            # Run transcription with token timestamps (pywhispercpp uses 'token_timestamps', not 'word_timestamps')
            logger.info(f"📝 Running pywhispercpp transcription with token timestamps enabled")
            
            segments = self._model.transcribe(
                str(audio_path),
                language=language,
                token_timestamps=True,  # Enable DTW token-level timestamps (pywhispercpp API)
                entropy_thold=entropy_thold,
                logprob_thold=logprob_thold,
                temperature=temperature,
            )

            if self.progress_callback:
                self.progress_callback("✅ Transcription completed, processing results...", 85)

            # Convert results to our format
            full_text_parts = []
            output_segments = []
            output_words = []

            for segment in segments:
                segment_text = segment.text.strip()
                full_text_parts.append(segment_text)
                
                # Build segment data
                segment_data = {
                    "start": segment.t0 / 100.0,  # Convert centiseconds to seconds
                    "end": segment.t1 / 100.0,
                    "text": segment_text,
                }
                
                # Extract word-level timestamps
                # pywhispercpp uses 'start'/'end' in seconds (newer API) or 't0'/'t1' in centiseconds (older API)
                segment_words = []
                if hasattr(segment, 'words') and segment.words:
                    for word in segment.words:
                        # Get word text
                        word_text = word.text.strip() if hasattr(word, 'text') else str(word).strip()
                        
                        # Get timestamps - try both API formats
                        if hasattr(word, 'start') and hasattr(word, 'end'):
                            # Newer pywhispercpp API: start/end in seconds
                            word_start = float(word.start)
                            word_end = float(word.end)
                        elif hasattr(word, 't0') and hasattr(word, 't1'):
                            # Older pywhispercpp API: t0/t1 in centiseconds
                            word_start = word.t0 / 100.0
                            word_end = word.t1 / 100.0
                        else:
                            # Fallback to segment times
                            word_start = segment_data["start"]
                            word_end = segment_data["end"]
                        
                        word_data = {
                            "word": word_text,
                            "start": word_start,
                            "end": word_end,
                        }
                        segment_words.append(word_data)
                        output_words.append(word_data)
                
                segment_data["words"] = segment_words
                output_segments.append(segment_data)

            full_text = " ".join(full_text_parts)

            # Validate transcription quality
            validation = self._validate_transcription(
                full_text, audio_duration_seconds, language
            )
            
            if not validation.get("is_valid", True):
                logger.warning(f"⚠️ Transcription validation warning: {validation.get('issue')}")

            # Calculate processing stats
            processing_time = time.time() - start_time
            if audio_duration_seconds:
                rtf = audio_duration_seconds / processing_time
                logger.info(
                    f"✅ Transcription completed in {processing_time:.1f}s "
                    f"({rtf:.1f}x real-time)"
                )
            else:
                logger.info(f"✅ Transcription completed in {processing_time:.1f}s")

            if self.progress_callback:
                self.progress_callback(
                    f"✅ Transcription complete: {len(output_words)} words extracted", 100
                )

            logger.info(f"📝 Extracted {len(output_words)} word-level timestamps via DTW")

            return ProcessorResult(
                success=True,
                data={
                    "text": full_text,
                    "segments": output_segments,
                    "words": output_words,
                    "language": language or "auto",
                },
                metadata={
                    "model": self.model_name,
                    "processing_time_seconds": processing_time,
                    "audio_duration_seconds": audio_duration_seconds,
                    "word_count": len(output_words),
                    "segment_count": len(output_segments),
                    "validation": validation,
                },
            )

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return ProcessorResult(
                success=False,
                errors=[f"Transcription failed: {str(e)}"],
            )

        finally:
            # Cleanup temp file
            if temp_wav and temp_wav.exists():
                try:
                    temp_wav.unlink()
                except Exception:
                    pass

    def _validate_transcription(
        self,
        text: str,
        audio_duration_seconds: float | None,
        language: str | None,
    ) -> dict:
        """Validate transcription quality to detect hallucinations."""
        if not text or len(text.strip()) < 10:
            return {"is_valid": False, "issue": "Transcription too short or empty"}

        text_lower = text.lower().strip()
        words = text_lower.split()

        if len(words) < 3:
            return {"is_valid": False, "issue": "Very few words transcribed"}

        # Duration-based validation
        if audio_duration_seconds and audio_duration_seconds > 30:
            duration_minutes = audio_duration_seconds / 60.0
            word_count = len(words)
            words_per_minute = word_count / duration_minutes

            if words_per_minute < 5:
                return {
                    "is_valid": False,
                    "issue": f"Very low word density ({words_per_minute:.1f} WPM)",
                }
            elif words_per_minute > 300:
                return {
                    "is_valid": False,
                    "issue": f"Extremely high word density ({words_per_minute:.1f} WPM)",
                }

        # Check for repetitive patterns
        if len(words) >= 10:
            max_consecutive = 1
            current_consecutive = 1

            for i in range(1, len(words)):
                if words[i] == words[i - 1]:
                    current_consecutive += 1
                    max_consecutive = max(max_consecutive, current_consecutive)
                else:
                    current_consecutive = 1

            if max_consecutive >= 7:
                return {
                    "is_valid": False,
                    "issue": f"Repetitive pattern detected ({max_consecutive} consecutive repeats)",
                }

        return {"is_valid": True, "issue": None}

    def terminate(self):
        """Cleanup resources."""
        self._model = None
        self._model_loaded = False
        logger.info("WhisperCppTranscribeProcessor terminated")
