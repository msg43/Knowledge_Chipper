import platform
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from knowledge_system.logger import get_logger
from knowledge_system.processors.base import BaseProcessor, ProcessorResult
from knowledge_system.utils.model_cache import cache_whisper_model

logger = get_logger(__name__)


class WhisperCppTranscribeProcessor(BaseProcessor):
    """Transcribes audio files using whisper.cpp with Core ML support on macOS."""

    def __init__(
        self,
        model: str = "medium",
        use_coreml: bool | None = None,
        progress_callback=None,
    ) -> None:
        self.model_name = model
        self.use_coreml = use_coreml
        self._model_path = None
        self.progress_callback = progress_callback
        self._current_subprocess = None  # Track current subprocess for termination

        # Auto-detect Core ML usage based on platform
        if self.use_coreml is None:
            self.use_coreml = (
                platform.system() == "Darwin" and platform.machine() == "arm64"
            )

        # Model size mapping - simplified and optimized
        self.model_sizes = {
            "tiny": "ggml-tiny",
            "base": "ggml-base",
            "small": "ggml-small",
            "medium": "ggml-medium.en",  # English-only model (faster, smaller)
            "large": "ggml-large-v3",  # Latest large model (best quality)
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

    def _validate_model_file(
        self, model_path: Path, model_name: str
    ) -> tuple[bool, str]:
        """
        Validate that a model file is not corrupted.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not model_path.exists():
            return False, "Model file does not exist"

        # Expected minimum sizes (in MB) - set to ~90% of typical size to catch corruption
        # while allowing for compression variations
        # Truly corrupted files will be MUCH smaller (like 6MB instead of 3000MB)
        expected_min_sizes = {
            "tiny": 65,  # ~90% of 75MB
            "base": 120,  # ~90% of 142MB
            "small": 400,  # ~90% of 466MB
            "medium": 1200,  # ~90% of 1400MB
            "large": 2700,  # ~90% of 3094MB - allows for 2951MB to pass
        }

        file_size_mb = model_path.stat().st_size / (1024 * 1024)
        min_size = expected_min_sizes.get(model_name, 50)

        if file_size_mb < min_size:
            return (
                False,
                f"Model file appears corrupted: {file_size_mb:.1f}MB (expected >{min_size}MB)",
            )

        logger.debug(f"Model {model_name} validated: {file_size_mb:.1f}MB")
        return True, ""

    def _download_model(self, model_name: str, progress_callback=None) -> Path:
        """Download the whisper.cpp model if not already present."""
        # First check local models directory
        local_models_dir = Path("models")
        if local_models_dir.exists():
            model_filename = f"{self.model_sizes.get(model_name, 'ggml-base')}.bin"
            local_model_path = local_models_dir / model_filename
            if local_model_path.exists():
                # Validate the model file
                is_valid, error_msg = self._validate_model_file(
                    local_model_path, model_name
                )
                if is_valid:
                    logger.info(f"✅ Using local whisper.cpp model: {local_model_path}")
                    return local_model_path
                else:
                    logger.warning(
                        f"Local model invalid: {error_msg}. Will try cache directory."
                    )

        # Fall back to cache directory
        models_dir = Path.home() / ".cache" / "whisper-cpp"
        models_dir.mkdir(parents=True, exist_ok=True)

        model_filename = f"{self.model_sizes.get(model_name, 'ggml-base')}.bin"
        model_path = models_dir / model_filename

        # Check if file exists and validate it
        if model_path.exists():
            is_valid, error_msg = self._validate_model_file(model_path, model_name)
            if is_valid:
                logger.info(f"✅ Using cached whisper.cpp model: {model_path}")
                return model_path
            else:
                logger.warning(f"⚠️ Cached model corrupted: {error_msg}")
                logger.info(f"🗑️ Deleting corrupted model file: {model_path}")
                try:
                    model_path.unlink()
                    logger.info("✅ Corrupted model deleted, will redownload")
                except Exception as e:
                    logger.error(f"Failed to delete corrupted model: {e}")

        if not model_path.exists():
            logger.info(f"📥 Downloading whisper.cpp model: {model_name}")
            url = f"https://huggingface.co/ggerganov/whisper.cpp/resolve/main/{model_filename}"

            # Model sizes for progress estimation (approximate)
            model_sizes_mb = {
                "ggml-tiny.bin": 75,
                "ggml-base.bin": 142,
                "ggml-small.bin": 466,
                "ggml-medium.en.bin": 769,  # English-only medium model (smaller than multilingual)
                "ggml-large-v3.bin": 3094,  # Latest large model
            }

            # Note: Expected size available in model_sizes_mb if needed for
            # validation

            # Download with progress tracking and timeout

            # Check available memory before downloading large models
            if model_name == "large":
                try:
                    import psutil

                    available_gb = psutil.virtual_memory().available / (1024**3)
                    if available_gb < 6.0:
                        logger.error(
                            f"Not enough memory for large model. Available: {available_gb:.1f}GB, Required: 6GB+"
                        )
                        if progress_callback:
                            progress_callback(
                                {
                                    "status": "error",
                                    "model": model_name,
                                    "message": f"Not enough memory: {available_gb:.1f}GB available, need 6GB+",
                                }
                            )
                        return None
                except Exception as e:
                    logger.warning(f"Could not check memory: {e}")

            try:
                if progress_callback:
                    progress_callback(
                        {
                            "status": "starting_download",
                            "model": model_name,
                            "message": f"Starting download of {model_name} model (~{model_sizes_mb.get(model_filename, 100)} MB)...",
                        }
                    )

                # Use safe downloader
                from ..utils.safe_download import download_with_retry

                # Wrap callback to add model info
                def wrapped_callback(info):
                    if progress_callback and isinstance(info, dict):
                        info["model"] = model_name
                        progress_callback(info)

                # Download with retry
                success = download_with_retry(
                    url, model_path, max_retries=3, progress_callback=wrapped_callback
                )

                if success:
                    if progress_callback:
                        progress_callback(
                            {
                                "status": "download_complete",
                                "model": model_name,
                                "message": f"Successfully downloaded {model_name} model",
                            }
                        )
                else:
                    return None

            except Exception as e:
                logger.error(f"Failed to download model: {e}")
                if progress_callback:
                    progress_callback(
                        {
                            "status": "error",
                            "model": model_name,
                            "message": f"Download failed: {str(e)}",
                        }
                    )
                return None

        return model_path

    def _validate_transcription_quality(
        self,
        text: str,
        audio_duration_seconds: float | None = None,
        language: str | None = None,
    ) -> dict:
        """Validate transcription quality and detect common failure patterns."""
        if not text or len(text.strip()) < 10:
            return {"is_valid": False, "issue": "Transcription too short or empty"}

        text_lower = text.lower().strip()
        words = text_lower.split()

        if len(words) < 3:
            return {"is_valid": False, "issue": "Very few words transcribed"}

        # Duration-based quality validation
        if (
            audio_duration_seconds and audio_duration_seconds > 30
        ):  # Only for audio longer than 30 seconds
            duration_minutes = audio_duration_seconds / 60.0
            word_count = len(words)
            words_per_minute = word_count / duration_minutes

            # Expected speaking rates (words per minute) - ADJUSTED FOR REAL-WORLD CONTENT
            # Audiobooks/content with pauses: 5-30 WPM (lots of silence, music, dramatic pauses)
            # Very slow: 30-80 WPM (lectures with pauses, technical content, meditation)
            # Normal: 80-150 WPM (conversation, presentations)
            # Fast: 150-250 WPM (news, fast speakers)
            # Audio with music/silence/long pauses is still valid content

            if (
                words_per_minute < 5
            ):  # Less than 5 WPM suggests major failure (almost no speech)
                return {
                    "is_valid": False,
                    "issue": f"Transcription appears to contain no speech ({word_count:,} words in {duration_minutes:.1f} min = {words_per_minute:.1f} WPM, expected >2 WPM)",
                }
            # REMOVED: The 15-40 WPM rejection - this is too strict for real-world content like audiobooks,
            # meditation, lectures with long pauses, or content with background music
            elif (
                words_per_minute > 300
            ):  # >300 WPM suggests gibberish or processing error
                return {
                    "is_valid": False,
                    "issue": f"Extremely high word density suggests transcription error ({words_per_minute:.1f} WPM, expected <300 WPM)",
                }

        # Check for repetitive patterns (like "you you you")
        if len(words) >= 10:
            # Count consecutive repeated words
            max_consecutive = 1
            current_consecutive = 1

            for i in range(1, len(words)):
                if words[i] == words[i - 1]:
                    current_consecutive += 1
                    max_consecutive = max(max_consecutive, current_consecutive)
                else:
                    current_consecutive = 1

            # If more than 7 consecutive identical words, likely a failure
            # Increased from 5 to 7 to reduce false positives on natural speech patterns
            if max_consecutive >= 7:
                return {
                    "is_valid": False,
                    "issue": f"Repetitive pattern detected ('{words[0]}' repeated {max_consecutive} times)",
                }

            # Check for high percentage of repeated words overall
            word_counts = {}
            for word in words:
                word_counts[word] = word_counts.get(word, 0) + 1

            # Find most common word
            most_common_word = max(word_counts, key=word_counts.get)
            most_common_count = word_counts[most_common_word]

            # If one word makes up more than 50% of the transcription, likely a failure
            if most_common_count / len(words) > 0.5:
                return {
                    "is_valid": False,
                    "issue": f"Single word '{most_common_word}' dominates transcription ({most_common_count}/{len(words)} occurrences)",
                }

        # Check for repeated phrases (n-grams) that may have survived cleanup
        # This catches scattered repetitions or cases where threshold was too lenient
        if len(words) >= 20:  # Need enough words to detect patterns
            from collections import Counter

            # Check n-grams of various sizes (longer phrases first)
            for n in [10, 8, 6, 4, 3]:
                if len(words) < n * 3:  # Need at least 3 occurrences to be meaningful
                    continue

                # Build n-grams
                ngrams = []
                for i in range(len(words) - n + 1):
                    ngram = tuple(words[i : i + n])
                    ngrams.append(ngram)

                if not ngrams:
                    continue

                # Count phrase frequencies
                ngram_counts = Counter(ngrams)

                if ngram_counts:
                    most_common_ngram, count = ngram_counts.most_common(1)[0]
                    phrase_ratio = count / len(ngrams)

                    # If a phrase appears frequently (>30% of content), flag it
                    # Lower threshold than single words (50%) since phrases are more specific
                    if count >= 5 and phrase_ratio > 0.3:
                        phrase_text = " ".join(most_common_ngram)
                        return {
                            "is_valid": False,
                            "issue": f"Repeated {n}-word phrase detected: '{phrase_text[:80]}...' appears {count} times ({phrase_ratio*100:.1f}% of content)",
                        }

        # Check for gibberish patterns (too many single-character words)
        single_char_words = sum(1 for word in words if len(word) == 1)
        if single_char_words / len(words) > 0.3:
            return {
                "is_valid": False,
                "issue": f"Too many single-character words ({single_char_words}/{len(words)})",
            }

        # Only check for English words if we're expecting English
        # Skip this check for other languages or when language is unknown
        if language in [
            "en",
            "english",
            None,
        ]:  # None means auto-detect, which might detect English
            common_english_words = {
                "the",
                "and",
                "a",
                "an",
                "is",
                "are",
                "was",
                "were",
                "have",
                "has",
                "had",
                "will",
                "would",
                "could",
                "should",
                "can",
                "may",
                "might",
                "do",
                "does",
                "did",
                "get",
                "got",
                "go",
                "went",
                "come",
                "came",
                "see",
                "saw",
                "know",
                "think",
                "want",
                "like",
                "time",
                "people",
                "way",
                "day",
                "man",
                "woman",
                "year",
                "work",
                "life",
                "hand",
                "part",
                "place",
                "case",
                "point",
                "government",
                "company",
            }
            # Strip punctuation from words before checking against common words
            english_word_count = sum(
                1
                for word in words
                if word.strip(".,!?;:\"'()[]{}") in common_english_words
            )
            # Only flag as error if we detected a language mismatch
            if len(words) > 50 and english_word_count / len(words) < 0.1:
                # Check if this might be a different language by looking for common patterns
                # High frequency of certain characters might indicate non-English
                non_english_indicators = (
                    any(char in text for char in "àâäçèéêëîïôùûüÿœæ")  # French accents
                    or text.count("ñ") > 2
                )  # Spanish

                if non_english_indicators or english_word_count < 5:
                    return {
                        "is_valid": False,
                        "issue": f"Language mismatch: Expected English but detected foreign language ({english_word_count}/{len(words)} English words)",
                    }

        return {"is_valid": True, "issue": None}

    def _remove_sequential_repetitions(
        self, segments: list[dict], threshold: int = 3
    ) -> tuple[list[dict], dict]:
        """
        Remove consecutive identical segments (Whisper hallucination cleanup).

        Large Whisper models sometimes get "stuck" repeating the same phrase
        over and over, especially when encountering silence, background noise,
        or content that's difficult to parse. This function detects and removes
        these hallucinated repetitions.

        Args:
            segments: List of transcript segments with 'text', 'start', 'end' fields
            threshold: Number of consecutive identical segments to trigger removal (default: 3)

        Returns:
            Tuple of (cleaned_segments, cleanup_stats)

        Example:
            Input: [
                {"text": "The Hungarian Central Bank...", "start": 725.0, "end": 726.0},
                {"text": "The Hungarian Central Bank...", "start": 726.0, "end": 727.0},
                {"text": "The Hungarian Central Bank...", "start": 727.0, "end": 728.0},
                ... (38 times)
            ]
            Output: ([{"text": "The Hungarian Central Bank...", "start": 725.0, "end": 726.0}],
                    {"removed_count": 37, "patterns_found": [...]})
        """
        if not segments or len(segments) < threshold:
            return segments, {"removed_count": 0, "patterns_found": []}

        cleaned = []
        removed_count = 0
        patterns_found = []
        i = 0

        while i < len(segments):
            current_text = segments[i].get("text", "").strip().lower()

            # Skip empty segments
            if not current_text:
                cleaned.append(segments[i])
                i += 1
                continue

            # Look ahead to count consecutive identical segments
            consecutive_count = 1
            j = i + 1

            while j < len(segments):
                next_text = segments[j].get("text", "").strip().lower()

                # Check if text is identical
                if next_text == current_text:
                    # Additional check: timestamps should be sequential (typically 1-second increments)
                    # This helps distinguish hallucinations from legitimate repeated phrases
                    current_end = segments[j - 1].get("end", 0)
                    next_start = segments[j].get("start", 0)

                    # Allow small gaps (up to 2 seconds) for timestamp rounding
                    time_gap = abs(next_start - current_end)
                    if time_gap <= 2.0:
                        consecutive_count += 1
                        j += 1
                    else:
                        # Timestamps not sequential - likely legitimate repetition
                        break
                else:
                    break

            # If we found threshold+ repetitions, keep only the first occurrence
            if consecutive_count >= threshold:
                cleaned.append(segments[i])  # Keep first occurrence
                removed_count += consecutive_count - 1

                # Record pattern for logging
                pattern_info = {
                    "text": current_text[:100] + "..."
                    if len(current_text) > 100
                    else current_text,
                    "repetitions": consecutive_count,
                    "start_time": segments[i].get("start"),
                    "end_time": segments[j - 1].get("end")
                    if j > 0
                    else segments[i].get("end"),
                }
                patterns_found.append(pattern_info)

                logger.warning(
                    f"🧹 Removed {consecutive_count - 1} consecutive repetitions of: "
                    f"'{current_text[:50]}...' (from {pattern_info['start_time']:.1f}s to {pattern_info['end_time']:.1f}s)"
                )

                i = j  # Skip past all the repetitions
            else:
                # No repetition pattern, keep segment
                cleaned.append(segments[i])
                i += 1

        cleanup_stats = {
            "removed_count": removed_count,
            "patterns_found": patterns_found,
            "original_count": len(segments),
            "cleaned_count": len(cleaned),
        }

        if removed_count > 0:
            logger.info(
                f"✅ Hallucination cleanup: Removed {removed_count} repetitions across "
                f"{len(patterns_found)} pattern(s), kept {len(cleaned)} segments"
            )

        return cleaned, cleanup_stats

    def _load_model(self):
        """Download whisper.cpp model if needed (for subprocess usage)."""
        # We're using subprocess approach, so just ensure model is downloaded
        if self._model_path is None:
            # Use cached model path loading
            def model_loader():
                return self._download_model(self.model_name, self.progress_callback)

            # Cache the model path (the actual file path, not the model itself)
            self._model_path = cache_whisper_model(
                model_name=self.model_name,
                device="disk",  # Special device name for file paths
                loader_func=model_loader,
                use_coreml=self.use_coreml,
            )

    def _is_16khz_mono_wav(self, input_path: Path) -> bool:
        """Check if audio file is already 16kHz mono WAV format."""
        if input_path.suffix.lower() != ".wav":
            return False

        try:
            import subprocess

            # Use ffprobe to check format
            probe_cmd = [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_streams",
                str(input_path),
            ]

            result = subprocess.run(probe_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return False

            import json

            data = json.loads(result.stdout)

            # Check first audio stream
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "audio":
                    sample_rate = int(stream.get("sample_rate", 0))
                    channels = int(stream.get("channels", 0))
                    codec_name = stream.get("codec_name", "")

                    # Check if it's 16kHz mono PCM
                    is_16khz_mono = (
                        sample_rate == 16000
                        and channels == 1
                        and codec_name in ["pcm_s16le", "pcm_s16be", "pcm_s8", "pcm_u8"]
                    )

                    if is_16khz_mono:
                        logger.info(
                            f"Audio already in 16kHz mono WAV format: {input_path}"
                        )

                    return is_16khz_mono

            return False

        except Exception as e:
            logger.debug(f"Could not probe audio format: {e}")
            return False

    def _convert_to_wav(self, input_path: Path) -> Path:
        """Convert audio to 16kHz WAV format required by whisper.cpp."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            output_path = Path(tmp_file.name)

        try:
            # Use ffmpeg to convert to 16kHz mono WAV
            cmd = [
                "ffmpeg",
                "-i",
                str(input_path),
                "-ar",
                "16000",  # 16kHz sample rate
                "-ac",
                "1",  # Mono
                "-c:a",
                "pcm_s16le",  # 16-bit PCM
                "-y",  # Overwrite output
                str(output_path),
            ]

            # Use non-blocking subprocess execution
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            stdout, stderr = process.communicate()

            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, cmd, stderr)
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg conversion failed: {e}")
            output_path.unlink(missing_ok=True)
            raise

    def _find_whisper_binary(self) -> str | None:
        """Find whisper.cpp binary, checking bundled location first, then system PATH."""
        import os

        # Check for bundled whisper.cpp first (for DMG distribution)
        if os.environ.get("WHISPER_CPP_BUNDLED") == "true":
            bundled_path = os.environ.get("WHISPER_CPP_PATH")
            if bundled_path and Path(bundled_path).is_file():
                try:
                    subprocess.run(
                        [bundled_path, "--help"],
                        capture_output=True,
                        check=True,
                        timeout=3,
                    )
                    logger.info(f"Found bundled whisper binary: {bundled_path}")
                    return bundled_path
                except (
                    subprocess.CalledProcessError,
                    FileNotFoundError,
                    subprocess.TimeoutExpired,
                ):
                    logger.warning(
                        f"Bundled whisper binary not working: {bundled_path}"
                    )

        # Check for whisper.cpp in app bundle (alternative bundled location)
        try:
            # Get the current script's directory to find app bundle
            current_dir = Path(__file__).parent
            # Navigate up to find potential app bundle structure
            for parent in [current_dir] + list(current_dir.parents):
                potential_whisper = parent / "bin" / "whisper"
                if potential_whisper.is_file():
                    try:
                        subprocess.run(
                            [str(potential_whisper), "--help"],
                            capture_output=True,
                            check=True,
                            timeout=3,
                        )
                        logger.info(
                            f"Found app bundle whisper binary: {potential_whisper}"
                        )
                        return str(potential_whisper)
                    except (
                        subprocess.CalledProcessError,
                        FileNotFoundError,
                        subprocess.TimeoutExpired,
                    ):
                        continue
        except Exception:
            pass  # Continue to system PATH check

        # Fall back to system PATH
        for cmd_candidate in ["whisper-cli", "whisper-cpp", "whisper"]:
            try:
                subprocess.run(
                    [cmd_candidate, "--help"],
                    capture_output=True,
                    check=True,
                    timeout=5,
                )
                logger.info(f"Found system whisper binary: {cmd_candidate}")
                return cmd_candidate
            except (
                subprocess.CalledProcessError,
                FileNotFoundError,
                subprocess.TimeoutExpired,
            ):
                continue

        logger.warning(
            "No whisper.cpp binary found in bundled locations or system PATH"
        )
        return None

    def _get_audio_duration(self, input_path: Path) -> float | None:
        """Get audio duration in seconds using ffprobe."""
        try:
            import subprocess

            probe_cmd = [
                "ffprobe",
                "-v",
                "quiet",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                str(input_path),
            ]
            probe_result = subprocess.run(
                probe_cmd, capture_output=True, text=True, timeout=10
            )
            if probe_result.returncode == 0 and probe_result.stdout.strip():
                duration = float(probe_result.stdout.strip())
                return duration
            else:
                logger.warning(f"Could not extract audio duration from {input_path}")
                return None
        except Exception as e:
            logger.warning(f"Failed to get audio duration: {e}")
            return None

    def process(
        self, input_data: Any, dry_run: bool = False, **kwargs: Any
    ) -> ProcessorResult:
        # Extract parameters from kwargs for backwards compatibility
        kwargs.get("device", None)

        # Handle input_data as input_path for backwards compatibility
        input_path = input_data
        path = Path(input_path)

        if not self.validate_input(path):
            return ProcessorResult(
                success=False, errors=[f"Invalid input: {input_path}"]
            )

        # Process with native whisper.cpp
        return self._process_audio(path, **kwargs)

    def _process_audio(self, input_path: Path, **kwargs: Any) -> ProcessorResult:
        """Process audio using native whisper.cpp CLI."""
        import time

        start_time = time.time()

        # Initialize variables that may be used in exception handlers
        audio_duration_seconds = None

        # Get file info for better logging context
        filename = input_path.name
        file_size_mb = input_path.stat().st_size / (1024 * 1024)
        logger.info(
            f"🎤 Starting transcription of '{filename}' ({file_size_mb:.1f}MB) with whisper.cpp"
        )

        # Emit initial progress with file context
        if self.progress_callback:
            self.progress_callback(
                f"🎤 Initializing transcription for {filename} ({file_size_mb:.1f}MB)...",
                5,
            )

        # Extract audio duration for quality validation
        audio_duration_seconds = self._get_audio_duration(input_path)
        if audio_duration_seconds:
            duration_str = f"{audio_duration_seconds:.1f}s"
            if audio_duration_seconds >= 60:
                duration_str += f" ({audio_duration_seconds/60:.1f}min)"
            logger.info(
                f"📊 Audio analysis: {duration_str} duration, {file_size_mb:.1f}MB file"
            )
            if self.progress_callback:
                self.progress_callback(
                    f"📊 Analyzed {filename}: {duration_str}, ready for transcription",
                    8,
                )
        else:
            logger.warning(f"⚠️ Could not determine duration for {filename}")
            if self.progress_callback:
                self.progress_callback(
                    f"⚠️ Duration unknown for {filename}, proceeding with transcription",
                    8,
                )

        temp_wav = None
        try:
            # Try to find whisper.cpp binary (bundled first, then system)
            whisper_cmd = self._find_whisper_binary()

            if not whisper_cmd:
                # Graceful fallback - don't crash the entire app
                error_msg = (
                    "Local transcription unavailable: whisper.cpp binary not found. "
                    "Please install whisper.cpp or use cloud transcription instead."
                )
                logger.error(error_msg)
                return ProcessorResult(
                    success=False,
                    errors=[error_msg],
                    metadata={"fallback_suggestion": "Use cloud transcription"},
                )

            if self.progress_callback:
                self.progress_callback(
                    f"✅ Using {whisper_cmd} for {filename} transcription", 10
                )

            # Check if conversion is needed
            if self._is_16khz_mono_wav(input_path):
                # Already in the correct format, skip conversion
                audio_path = input_path
                if self.progress_callback:
                    self.progress_callback(
                        f"✅ {filename} already in optimal 16kHz mono WAV format", 20
                    )
                logger.info(
                    f"📁 Skipping conversion for {filename} - already optimized format"
                )
            else:
                # Need to convert to 16kHz mono WAV
                if self.progress_callback:
                    self.progress_callback(
                        f"🔄 Converting {filename} to 16kHz mono WAV format...", 15
                    )
                temp_wav = self._convert_to_wav(input_path)
                audio_path = temp_wav
                if self.progress_callback:
                    self.progress_callback(
                        f"✅ Audio conversion of {filename} completed", 25
                    )

            # Download model if needed
            if self.progress_callback:
                self.progress_callback(
                    f"📥 Ensuring Whisper '{self.model_name}' model is available for {filename}...",
                    30,
                )
            model_path = self._download_model(self.model_name)
            if self.progress_callback:
                model_size_mb = (
                    model_path.stat().st_size / (1024 * 1024)
                    if model_path.exists()
                    else 0
                )
                self.progress_callback(
                    f"✅ Whisper '{self.model_name}' model ready ({model_size_mb:.0f}MB)",
                    40,
                )

            # Create temp directory for output
            import tempfile

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dir_path = Path(temp_dir)
                output_base = temp_dir_path / "output"

                # Run whisper.cpp with proper parameters
                cmd = [
                    whisper_cmd,
                    "-m",
                    str(model_path),
                    str(audio_path),
                ]

                # Add threading and batch size parameters if provided
                omp_threads = kwargs.get("omp_threads")
                if omp_threads:
                    cmd.extend(["-t", str(omp_threads)])
                else:
                    # Default to 8 threads if not specified
                    cmd.extend(["-t", "8"])

                batch_size = kwargs.get("batch_size")
                if batch_size:
                    cmd.extend(["-bs", str(batch_size)])
                else:
                    # Default batch size
                    cmd.extend(["-bs", "8"])

                # Add hallucination prevention parameters
                # These parameters help prevent Whisper from getting "stuck" and repeating phrases

                # Entropy threshold: Higher = more aggressive at stopping hallucinations
                # Default is 2.40, we increase it for large models which are more prone to hallucinations
                entropy_thold = kwargs.get("entropy_thold")
                if entropy_thold is None:
                    # Use higher threshold for large models (more aggressive hallucination prevention)
                    # self.model_name is "large" but actual model file is "ggml-large-v3"
                    if self.model_name == "large":
                        entropy_thold = 2.8  # More aggressive for large models
                        logger.info(
                            "🎯 Using aggressive hallucination prevention for large model"
                        )
                    else:
                        entropy_thold = (
                            2.6  # Slightly higher than default for medium/small
                        )
                cmd.extend(["--entropy-thold", str(entropy_thold)])

                # Log probability threshold: Higher (less negative) = more likely to reject low-confidence segments
                # Default is -1.00, we make it less strict to catch hallucinations
                logprob_thold = kwargs.get("logprob_thold", -0.8)
                cmd.extend(["--logprob-thold", str(logprob_thold)])

                # Maximum segment length: Prevents extremely long repetitive segments
                # 0 = no limit, we set a reasonable limit to catch runaway hallucinations
                max_len = kwargs.get("max_len", 200)  # 200 characters max per segment
                cmd.extend(["--max-len", str(max_len)])

                # Temperature: 0 = deterministic, higher = more random
                # Keep at 0 for consistency, but allow override
                temperature = kwargs.get("temperature", 0.0)
                cmd.extend(["--temperature", str(temperature)])

                logger.info(
                    f"🛡️ Hallucination prevention: entropy={entropy_thold}, "
                    f"logprob={logprob_thold}, max_len={max_len}, temp={temperature}"
                )

                # CRITICAL: Add GPU acceleration for Apple Silicon (remove -ng flag which DISABLES GPU)
                # Note: By default, whisper.cpp uses GPU when available unless -ng (--no-gpu) is specified
                # We simply don't add the -ng flag to enable GPU acceleration

                # Note: Flash attention (-fa) causes exit code 3 errors on some whisper.cpp builds
                # Disabled for now - GPU acceleration is still enabled by default
                # if platform.system() == "Darwin" and platform.machine() == "arm64":
                #     cmd.extend(["-fa"])  # Enable flash attention
                #     logger.info("🚀 Enabled flash attention for Apple Silicon")

                logger.info("🚀 GPU acceleration enabled (default whisper.cpp behavior)")

                # Add output options
                # CRITICAL: Always enable timestamps in whisper.cpp to prevent hallucinations
                # Timestamps act as temporal anchors that keep the model synchronized with audio
                # Without them, the model can "drift" and start hallucinating/repeating on longer files
                # We can still choose whether to display timestamps in the formatted output
                # Add output options
                cmd.extend(
                    [
                        "--output-json",
                        # DO NOT use --no-timestamps - it causes hallucinations on long audio
                        "--output-file",
                        str(output_base),
                        "--print-progress",  # Enable progress output
                    ]
                )

                # Add language if specified (otherwise whisper will auto-detect)
                language = kwargs.get("language")
                if language and language != "auto":
                    cmd.extend(["--language", language])
                    logger.info(f"🌐 Transcribing in language: {language}")
                else:
                    logger.info(
                        f"🌐 Auto-detecting language (may be unreliable, consider setting explicitly)"
                    )

                # Add initial prompt with YouTube metadata to provide context
                # This helps prevent hallucinations by giving the model domain knowledge
                video_metadata = kwargs.get("video_metadata")
                if video_metadata:
                    # Build contextual prompt from YouTube tags/keywords
                    prompt_parts = ["This is a video in English"]

                    tags = video_metadata.get("tags", [])
                    if tags and len(tags) > 0:
                        # Use first 5-10 tags to provide context without overwhelming the model
                        context_tags = tags[:10]
                        keywords_str = ", ".join(context_tags)
                        prompt_parts.append(f"about {keywords_str}")
                        logger.info(
                            f"📝 Using context prompt with {len(context_tags)} keywords"
                        )

                    # Add title as additional context if available
                    title = video_metadata.get("title")
                    if title and not tags:
                        # Only add title if we don't have tags (avoid redundancy)
                        prompt_parts.append(f"titled '{title[:100]}'")

                    prompt = " ".join(prompt_parts) + "."
                    cmd.extend(["--prompt", prompt])
                    logger.debug(f"Initial prompt: {prompt}")

                if self.progress_callback:
                    transcription_msg = (
                        f"🎯 Running whisper.cpp transcription on {filename}"
                    )
                    if audio_duration_seconds:
                        transcription_msg += (
                            f" ({audio_duration_seconds/60:.1f}min audio)"
                        )
                    self.progress_callback(transcription_msg + "...", 50)

                logger.info(f"Running command: {' '.join(cmd)}")

                # Use real-time progress monitoring instead of blocking subprocess.run
                result = self._run_whisper_with_progress(cmd, audio_duration_seconds)

                if self.progress_callback:
                    transcription_time = time.time() - start_time
                    speed_info = ""
                    if audio_duration_seconds and transcription_time > 0:
                        speed_ratio = audio_duration_seconds / transcription_time
                        speed_info = f" ({speed_ratio:.1f}x realtime)"
                    self.progress_callback(
                        f"✅ Whisper.cpp transcription of {filename} completed{speed_info}",
                        80,
                    )

                # Look for JSON output file
                json_file = output_base.with_suffix(".json")
                if json_file.exists():
                    if self.progress_callback:
                        self.progress_callback(
                            "📄 Processing transcription results...", 85
                        )

                    import json

                    try:
                        with open(json_file, encoding="utf-8") as f:
                            output_data = json.load(f)
                        logger.info(f"Successfully loaded JSON output from {json_file}")
                    except (json.JSONDecodeError, UnicodeDecodeError) as e:
                        logger.warning(
                            f"JSON parsing failed: {e}, falling back to stdout"
                        )
                        # Fall back to stdout parsing if JSON is corrupted
                        if result.stdout.strip():
                            full_text = result.stdout.strip()
                        else:
                            raise Exception("No valid output generated by whisper.cpp")

                        formatted_result = {
                            "text": full_text,
                            "segments": [{"start": 0, "end": 0, "text": full_text}],
                            "language": "unknown",
                        }

                        if self.progress_callback:
                            self.progress_callback(
                                "✅ Transcription text extracted from stdout", 100
                            )

                        return ProcessorResult(
                            success=True,
                            data=formatted_result,
                            metadata={
                                "model": self.model_name,
                                "processor": "whisper.cpp",
                                "language": formatted_result.get("language", "unknown"),
                                "text_length": len(formatted_result.get("text", "")),
                            },
                        )

                    # Extract text from transcription
                    if "transcription" in output_data:
                        if self.progress_callback:
                            self.progress_callback(
                                "🔍 Extracting transcription segments...", 90
                            )

                        transcription = output_data["transcription"]
                        if isinstance(transcription, list):
                            # Format: [{"timestamps": {...}, "offsets": {...}, "text": "..."}]
                            # More robust text joining with validation
                            text_segments = []
                            for segment in transcription:
                                if isinstance(segment, dict) and "text" in segment:
                                    text = segment.get("text", "").strip()
                                    if text:  # Only add non-empty text
                                        text_segments.append(text)

                            full_text = " ".join(text_segments)
                            logger.info(
                                f"Joined {len(text_segments)} text segments, total length: {len(full_text)}"
                            )
                            segments = []
                            for segment in transcription:
                                # Parse timestamps from offsets (in
                                # milliseconds) or timestamps
                                offsets = segment.get("offsets", {})
                                start_time = offsets.get("from", 0)
                                end_time = offsets.get("to", 0)

                                # Convert from milliseconds to seconds if
                                # needed
                                if (
                                    isinstance(start_time, (int, float))
                                    and start_time > 1000
                                ):
                                    start_time = start_time / 1000.0
                                if (
                                    isinstance(end_time, (int, float))
                                    and end_time > 1000
                                ):
                                    end_time = end_time / 1000.0

                                segments.append(
                                    {
                                        "start": (
                                            float(start_time) if start_time else 0.0
                                        ),
                                        "end": float(end_time) if end_time else 0.0,
                                        "text": segment.get("text", "").strip(),
                                    }
                                )

                            # Clean up sequential repetitions (hallucinations)
                            if segments:
                                (
                                    segments,
                                    cleanup_stats,
                                ) = self._remove_sequential_repetitions(segments)

                                # If we removed repetitions, rebuild full_text from cleaned segments
                                if cleanup_stats["removed_count"] > 0:
                                    text_segments = [
                                        seg["text"]
                                        for seg in segments
                                        if seg.get("text", "").strip()
                                    ]
                                    full_text = " ".join(text_segments)
                                    logger.info(
                                        f"Rebuilt text after cleanup: {len(text_segments)} segments, {len(full_text)} characters"
                                    )

                                    # Store cleanup stats for later use in retry logic
                                    if not hasattr(self, "_last_cleanup_stats"):
                                        self._last_cleanup_stats = cleanup_stats
                        else:
                            # Simple text format
                            full_text = str(transcription).strip()
                            segments = [{"start": 0.0, "end": 0.0, "text": full_text}]
                    else:
                        # Try to extract from other possible formats
                        full_text = output_data.get("text", str(output_data)).strip()
                        segments = [{"start": 0.0, "end": 0.0, "text": full_text}]

                    formatted_result = {
                        "text": full_text.strip(),
                        "segments": segments,
                        "language": output_data.get("language", "unknown"),
                    }

                    # Validate transcription for common failure patterns
                    # Get the language that was used for transcription
                    detected_language = output_data.get("language", "unknown")
                    requested_language = kwargs.get("language", "auto")

                    validation_result = self._validate_transcription_quality(
                        full_text,
                        audio_duration_seconds,
                        language=requested_language
                        if requested_language != "auto"
                        else detected_language,
                    )
                    if not validation_result["is_valid"]:
                        logger.warning(
                            f"Transcription quality issue detected: {validation_result['issue']}"
                        )
                        if self.progress_callback:
                            self.progress_callback(
                                f"⚠️ Quality issue: {validation_result['issue']}", 95
                            )

                    if self.progress_callback:
                        self.progress_callback(
                            f"✅ Extracted {len(full_text):,} characters of transcription",
                            100,
                        )

                else:
                    # If no JSON file, try to parse stdout
                    if self.progress_callback:
                        self.progress_callback("📄 Processing stdout output...", 90)

                    if result.stdout.strip():
                        full_text = result.stdout.strip()
                    else:
                        raise Exception("No output generated by whisper.cpp")

                    formatted_result = {
                        "text": full_text,
                        "segments": [{"start": 0, "end": 0, "text": full_text}],
                        "language": "unknown",
                    }

                    # Validate transcription for common failure patterns
                    # Since we couldn't get language from JSON, use the requested language
                    requested_language = kwargs.get("language", "auto")

                    validation_result = self._validate_transcription_quality(
                        full_text,
                        audio_duration_seconds,
                        language=requested_language
                        if requested_language != "auto"
                        else None,
                    )
                    if not validation_result["is_valid"]:
                        logger.warning(
                            f"Transcription quality issue detected: {validation_result['issue']}"
                        )
                        if self.progress_callback:
                            self.progress_callback(
                                f"⚠️ Quality issue: {validation_result['issue']}", 95
                            )

                    if self.progress_callback:
                        self.progress_callback(
                            f"✅ Extracted {len(full_text):,} characters from stdout",
                            100,
                        )

                return ProcessorResult(
                    success=True,
                    data=formatted_result,
                    metadata={
                        "model": self.model_name,
                        "processor": "whisper.cpp",
                        "language": formatted_result.get("language", "unknown"),
                        "text_length": len(formatted_result.get("text", "")),
                    },
                )

        except Exception as e:
            error_msg = str(e)

            # Check for corrupted model indicators
            if (
                "exit status 3" in error_msg
                or "failed to initialize whisper context" in error_msg
            ):
                logger.error(
                    f"Whisper model file may be corrupted (exit code 3). "
                    f"Automatic validation will trigger redownload on next attempt."
                )
                friendly_error = (
                    "Corrupted model file detected. The model will be automatically "
                    "redownloaded on the next transcription attempt. Please try again."
                )
                if self.progress_callback:
                    self.progress_callback(f"❌ {friendly_error}", 0)
                return ProcessorResult(success=False, errors=[friendly_error])
            else:
                logger.error(f"Whisper.cpp subprocess error: {e}")
                if self.progress_callback:
                    self.progress_callback(f"❌ Transcription failed: {str(e)}", 0)
                return ProcessorResult(
                    success=False, errors=[f"Subprocess transcription failed: {e}"]
                )
        finally:
            if temp_wav and temp_wav.exists():
                temp_wav.unlink(missing_ok=True)

    def _run_whisper_with_progress(
        self, cmd, audio_duration_seconds=None
    ) -> subprocess.CompletedProcess:
        """Run whisper.cpp with real-time progress monitoring."""
        import queue
        import threading
        import time

        start_time = time.time()

        # Track actual whisper.cpp progress (0-100%) for accurate speed calculation
        self._last_whisper_progress = 0  # Last reported progress from whisper.cpp
        self._audio_duration = audio_duration_seconds  # Store for speed calculation
        self._start_time = start_time  # Store for speed calculation

        # Get audio duration before starting the process to avoid subprocess in thread
        # Use the passed audio_duration_seconds if available, otherwise probe
        if audio_duration_seconds:
            estimated_duration = audio_duration_seconds
            logger.debug(f"Using provided audio duration: {estimated_duration}s")
        else:
            estimated_duration = 120  # Default 2 minutes if unknown
            try:
                # Try to get actual audio duration using ffprobe
                # The audio file is typically at index 2 in whisper.cpp commands:
                # cmd = [whisper_binary, "-m", model_path, audio_path, ...]
                audio_file = None
                if len(cmd) > 2:
                    # Check if element at index 2 looks like a file path (not a flag)
                    if not cmd[2].startswith("-"):
                        audio_file = cmd[2]

                if audio_file:
                    probe_cmd = [
                        "ffprobe",
                        "-v",
                        "quiet",
                        "-show_entries",
                        "format=duration",
                        "-o",
                        "csv=p=0",
                        audio_file,
                    ]
                    probe_result = subprocess.run(
                        probe_cmd, capture_output=True, text=True, timeout=5
                    )
                    if probe_result.returncode == 0 and probe_result.stdout.strip():
                        estimated_duration = float(probe_result.stdout.strip())
                        logger.debug(
                            f"Audio duration from ffprobe: {estimated_duration}s"
                        )
            except (subprocess.SubprocessError, ValueError, OSError) as e:
                # Fallback to default if ffprobe fails
                logger.debug(f"Failed to get audio duration with ffprobe: {e}")

        # Store the duration for speed calculations
        self._audio_duration = estimated_duration

        # Log full command for debugging
        logger.info(f"Full whisper command: {' '.join(cmd)}")

        # Check if the whisper binary exists and is executable
        import os
        import shutil

        # If the command doesn't include a path, check if it's in PATH
        whisper_binary = cmd[0]
        if not os.path.isabs(whisper_binary) and os.sep not in whisper_binary:
            # Look for the binary in PATH
            full_path = shutil.which(whisper_binary)
            if not full_path:
                raise FileNotFoundError(
                    f"Whisper binary not found in PATH: {whisper_binary}"
                )
            # Update the command with the full path for clarity
            cmd[0] = full_path
            whisper_binary = full_path

        # Now check if it exists and is executable
        if not os.path.exists(whisper_binary):
            raise FileNotFoundError(f"Whisper binary not found: {whisper_binary}")
        if not os.access(whisper_binary, os.X_OK):
            raise PermissionError(f"Whisper binary not executable: {whisper_binary}")

        # Use Popen for real-time monitoring
        # Note: Some versions of whisper.cpp may buffer output, so we use unbuffered mode
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,  # Prevent hanging on input prompts
            text=True,
            bufsize=0,  # Unbuffered for real-time output
            universal_newlines=True,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},  # Force unbuffered output
        )

        # Use queues to safely collect output from threads
        stdout_queue = queue.Queue()
        stderr_queue = queue.Queue()

        # Track recent segments for repetition detection
        recent_segments = []
        repetition_warning_shown = False

        def read_stream(stream, output_queue, stream_name):
            """Read from a stream and put lines into a queue."""
            nonlocal recent_segments, repetition_warning_shown

            try:
                while True:
                    line = stream.readline()
                    if not line:  # EOF
                        break
                    output_queue.put(line)
                    # Log the output for debugging - use INFO for visibility
                    line_stripped = line.strip()
                    if line_stripped:  # Only log non-empty lines
                        logger.info(f"[whisper.cpp {stream_name}] {line_stripped}")

                    # Real-time repetition detection for stdout segments
                    # Format: [00:12:05.320 --> 00:12:06.320]   The Hungarian Central Bank...
                    if (
                        stream_name == "stdout"
                        and line_stripped
                        and "-->" in line_stripped
                    ):
                        # Extract the text portion after the timestamp
                        try:
                            parts = line_stripped.split("]", 1)
                            if len(parts) == 2:
                                segment_text = parts[1].strip().lower()

                                # Track last 5 segments
                                recent_segments.append(segment_text)
                                if len(recent_segments) > 5:
                                    recent_segments.pop(0)

                                # Check if last 5 segments are all identical
                                if (
                                    len(recent_segments) == 5
                                    and len(set(recent_segments)) == 1
                                ):
                                    if not repetition_warning_shown:
                                        logger.warning(
                                            "⚠️ Repetition detected in transcription output - "
                                            "will be automatically cleaned up"
                                        )
                                        if self.progress_callback:
                                            self.progress_callback(
                                                "⚠️ Repetition detected, will be cleaned automatically",
                                                None,
                                            )
                                        repetition_warning_shown = True
                        except Exception:
                            pass  # Don't let parsing errors interrupt streaming

                    # Parse progress from the line (check both stdout and stderr)
                    if self.progress_callback and line_stripped:
                        try:
                            # whisper.cpp may output progress to either stdout or stderr
                            elapsed = time.time() - start_time
                            self._parse_whisper_output_for_progress(
                                line_stripped, elapsed
                            )
                        except Exception:
                            pass  # Don't let progress parsing errors interrupt streaming
            except Exception as e:
                logger.error(f"Error reading {stream_name}: {e}", exc_info=True)
            finally:
                try:
                    stream.close()
                except:
                    pass

        # Start threads to read stdout and stderr
        stdout_thread = threading.Thread(
            target=read_stream,
            args=(process.stdout, stdout_queue, "stdout"),
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=read_stream,
            args=(process.stderr, stderr_queue, "stderr"),
            daemon=True,
        )

        stdout_thread.start()
        stderr_thread.start()

        # Store subprocess reference for external termination
        self._current_subprocess = process

        # Log process info
        logger.info(f"Whisper process started with PID: {process.pid}")

        # Add a timeout mechanism
        max_runtime = 3600  # 1 hour max for any transcription
        check_interval = 0.5
        elapsed_checks = 0
        max_checks = int(max_runtime / check_interval)
        last_output_time = time.time()
        no_output_logged = False

        # Monitor progress while process runs
        while process.poll() is None:
            elapsed = time.time() - start_time
            elapsed_checks += 1

            # Check for timeout
            if elapsed_checks >= max_checks:
                logger.error(f"Whisper.cpp process timed out after {elapsed:.0f}s")
                process.terminate()
                time.sleep(2)
                if process.poll() is None:
                    process.kill()
                raise TimeoutError(f"Transcription timed out after {max_runtime}s")

            # Check if process is producing output
            try:
                current_queue_sizes = stdout_queue.qsize() + stderr_queue.qsize()
                if current_queue_sizes > 0:
                    last_output_time = time.time()
                    no_output_logged = False
                else:
                    # Log periodic status if no output
                    time_since_output = time.time() - last_output_time
                    if not no_output_logged and time_since_output > 30:
                        logger.info(
                            f"Whisper process (PID {process.pid}) - no output for {time_since_output:.0f}s, still running..."
                        )
                        no_output_logged = True

                if time.time() - last_output_time > 300:  # 5 minutes without output
                    logger.error(
                        "Whisper.cpp process appears stuck (no output for 5 minutes)"
                    )
                    logger.error(
                        f"Process state: returncode={process.poll()}, pid={process.pid}"
                    )

                    # Try to get any partial output before terminating
                    partial_stdout = []
                    partial_stderr = []
                    while not stdout_queue.empty():
                        try:
                            partial_stdout.append(stdout_queue.get_nowait())
                        except:
                            break
                    while not stderr_queue.empty():
                        try:
                            partial_stderr.append(stderr_queue.get_nowait())
                        except:
                            break

                    if partial_stdout:
                        logger.error(f"Partial stdout: {''.join(partial_stdout[:10])}")
                    if partial_stderr:
                        logger.error(f"Partial stderr: {''.join(partial_stderr[:10])}")

                    process.terminate()
                    time.sleep(2)
                    if process.poll() is None:
                        process.kill()
                    raise TimeoutError("Transcription stuck - no output for 5 minutes")
            except Exception as e:
                logger.error(f"Error checking output queues: {e}")

            # Note: We no longer provide time-based progress estimation here.
            # Progress is now only reported when whisper.cpp outputs actual progress via
            # _parse_whisper_output_for_progress(), which provides accurate percentages
            # and realtime speed calculations based on actual audio processed.

            time.sleep(check_interval)  # Check every 500ms

        # Process has finished, wait for it
        return_code = process.wait()

        # Give threads time to finish reading
        stdout_thread.join(timeout=2)
        stderr_thread.join(timeout=2)

        # Collect all output
        stdout_lines = []
        stderr_lines = []

        while not stdout_queue.empty():
            stdout_lines.append(stdout_queue.get_nowait())

        while not stderr_queue.empty():
            stderr_lines.append(stderr_queue.get_nowait())

        full_stdout = "".join(stdout_lines)
        full_stderr = "".join(stderr_lines)

        if return_code != 0:
            error_msg = f"Whisper.cpp failed with return code {return_code}"
            if full_stderr:
                error_msg += f"\nStderr: {full_stderr}"
            raise subprocess.CalledProcessError(
                return_code, cmd, full_stdout, full_stderr
            )

        # Clear subprocess reference
        self._current_subprocess = None

        return subprocess.CompletedProcess(
            args=cmd, returncode=return_code, stdout=full_stdout, stderr=full_stderr
        )

    def _parse_whisper_output_for_progress(self, line: str, elapsed_time: float):
        """Parse whisper.cpp output for progress indicators."""
        import re

        line_stripped = line.strip()
        line_lower = line_stripped.lower()

        # whisper.cpp with --print-progress outputs various formats:
        # - "progress = 0%"
        # - "[00:00:00.000 --> 00:00:05.000]" (timestamp-based progress)
        # - Or just percentage indicators

        # Try to extract percentage from any line containing %
        if "%" in line_stripped:
            # Extract percentage from various formats: "progress = X%", "X%", etc.
            match = re.search(r"(\d+)%", line_stripped)
            if match:
                whisper_progress = int(match.group(1))
                # Sanity check: progress should be 0-100
                if 0 <= whisper_progress <= 100:
                    self._last_whisper_progress = whisper_progress

                    # Calculate realtime speed based on actual audio processed
                    speed_info = ""
                    if self._audio_duration and elapsed_time > 2:
                        audio_processed_seconds = self._audio_duration * (
                            whisper_progress / 100.0
                        )
                        if elapsed_time > 0:
                            realtime_speed = audio_processed_seconds / elapsed_time
                            if realtime_speed >= 1.0:
                                speed_info = f" ({realtime_speed:.1f}x Realtime)"
                            elif realtime_speed > 0:
                                speed_info = (
                                    f" ({1/realtime_speed:.1f}x slower than realtime)"
                                )

                    # Report actual progress (0-100%) with accurate speed
                    if self.progress_callback:
                        self.progress_callback(
                            f"Transcribing... {whisper_progress}%{speed_info}",
                            whisper_progress,
                        )
                    return

        # Check for timestamp-based progress (whisper.cpp outputs timestamps as it processes)
        # Format: [00:00:00.000 --> 00:00:05.000]
        timestamp_match = re.search(
            r"\[(\d{2}):(\d{2}):(\d{2})\.\d{3}\s*-->", line_stripped
        )
        if timestamp_match and self._audio_duration:
            # Calculate progress from timestamp
            hours = int(timestamp_match.group(1))
            minutes = int(timestamp_match.group(2))
            seconds = int(timestamp_match.group(3))
            current_seconds = hours * 3600 + minutes * 60 + seconds

            if self._audio_duration > 0:
                timestamp_progress = int((current_seconds / self._audio_duration) * 100)
                # Only report if it's a meaningful update (at least 5% increment)
                if timestamp_progress > self._last_whisper_progress + 4:
                    self._last_whisper_progress = timestamp_progress

                    speed_info = ""
                    if elapsed_time > 2:
                        realtime_speed = current_seconds / elapsed_time
                        if realtime_speed >= 1.0:
                            speed_info = f" ({realtime_speed:.1f}x Realtime)"
                        elif realtime_speed > 0:
                            speed_info = (
                                f" ({1/realtime_speed:.1f}x slower than realtime)"
                            )

                    if self.progress_callback:
                        self.progress_callback(
                            f"Transcribing... {timestamp_progress}%{speed_info}",
                            timestamp_progress,
                        )
                    return

        # Fallback: Look for other progress indicators (less precise)
        if self.progress_callback:
            if "processing" in line_lower or "transcribing" in line_lower:
                # Found processing indicator without percentage
                self.progress_callback(f"🎯 {line_stripped}", None)
            elif (
                "done" in line_lower
                or "finished" in line_lower
                or "complete" in line_lower
            ):
                # Completion indicator
                self.progress_callback("🎯 Finalizing transcription...", 95)

    def terminate_subprocess(self):
        """Terminate any running subprocess."""
        if self._current_subprocess:
            try:
                logger.info(
                    f"Terminating whisper subprocess (PID: {self._current_subprocess.pid})"
                )
                self._current_subprocess.terminate()
                # Give it a moment to terminate gracefully
                import time

                time.sleep(0.5)
                if self._current_subprocess.poll() is None:
                    # Force kill if still running
                    logger.warning("Force killing whisper subprocess")
                    self._current_subprocess.kill()
                self._current_subprocess = None
            except Exception as e:
                logger.error(f"Error terminating subprocess: {e}")

    def process_batch(
        self, inputs: list[Any], dry_run: bool = False, **kwargs: Any
    ) -> list[ProcessorResult]:
        # Extract device from kwargs
        device = kwargs.get("device", None)
        return [
            self.process(input_item, dry_run=dry_run, device=device)
            for input_item in inputs
        ]


def fetch_transcript(
    audio_path: str | Path, model: str = "medium", use_coreml: bool | None = None
) -> str | None:
    """Convenience function to transcribe an audio file using whisper.cpp."""
    proc = WhisperCppTranscribeProcessor(model=model, use_coreml=use_coreml)
    result = proc.process(audio_path)
    return result.data.get("text") if result.success else None
