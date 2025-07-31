import platform
import subprocess
import tempfile
from pathlib import Path
from typing import Any, List, Optional, Union

from knowledge_system.logger import get_logger
from knowledge_system.processors.base import BaseProcessor, ProcessorResult

logger = get_logger(__name__)


class WhisperCppTranscribeProcessor(BaseProcessor):
    """Transcribes audio files using whisper.cpp with Core ML support on macOS."""

    def __init__(
        self,
        model: str = "base",
        use_coreml: bool | None = None,
        progress_callback=None,
    ) -> None:
        self.model_name = model
        self.use_coreml = use_coreml
        self._model_path = None
        self.progress_callback = progress_callback

        # Auto-detect Core ML usage based on platform
        if self.use_coreml is None:
            self.use_coreml = (
                platform.system() == "Darwin" and platform.machine() == "arm64"
            )

        # Model size mapping
        self.model_sizes = {
            "tiny": "ggml-tiny",
            "base": "ggml-base",
            "small": "ggml-small",
            "medium": "ggml-medium",
            "large": "ggml-large-v3",
            "large-v3": "ggml-large-v3",
        }

    @property
    def supported_formats(self) -> list[str]:
        return [".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".mp4", ".webm"]

    def validate_input(self, input_path: str | Path) -> bool:
        path = Path(input_path)
        return (
            path.exists()
            and path.is_file()
            and path.suffix.lower() in self.supported_formats
        )

    def can_process(self, input_path: str | Path) -> bool:
        return Path(input_path).suffix.lower() in self.supported_formats

    def _download_model(self, model_name: str, progress_callback=None) -> Path:
        """Download the whisper.cpp model if not already present."""
        # First check local models directory
        local_models_dir = Path("models")
        if local_models_dir.exists():
            model_filename = f"{self.model_sizes.get(model_name, 'ggml-base')}.bin"
            local_model_path = local_models_dir / model_filename
            if local_model_path.exists():
                logger.info(f"Using local whisper.cpp model: {local_model_path}")
                return local_model_path

        # Fall back to cache directory
        models_dir = Path.home() / ".cache" / "whisper-cpp"
        models_dir.mkdir(parents=True, exist_ok=True)

        model_filename = f"{self.model_sizes.get(model_name, 'ggml-base')}.bin"
        model_path = models_dir / model_filename

        if not model_path.exists():
            logger.info(f"Downloading whisper.cpp model: {model_name}")
            url = f"https://huggingface.co/ggerganov/whisper.cpp/resolve/main/{model_filename}"

            # Model sizes for progress estimation
            model_sizes_mb = {
                "ggml-tiny.bin": 75,
                "ggml-base.bin": 142,
                "ggml-small.bin": 466,
                "ggml-medium.bin": 1533,
                "ggml-large-v3.bin": 3094,
            }

            # Note: Expected size available in model_sizes_mb if needed for
            # validation

            # Download with progress tracking
            import time
            import urllib.request

            def download_with_progress(url, dest_path, callback=None):
                start_time = time.time()

                def report_progress(block_num, block_size, total_size):
                    downloaded = block_num * block_size
                    percent = (
                        min(100, (downloaded / total_size) * 100)
                        if total_size > 0
                        else 0
                    )
                    elapsed = time.time() - start_time
                    speed = downloaded / elapsed if elapsed > 0 else 0
                    speed_mb = speed / (1024 * 1024)

                    if callback:
                        callback(
                            {
                                "status": "downloading",
                                "model": model_name,
                                "percent": percent,
                                "downloaded_mb": downloaded / (1024 * 1024),
                                "total_mb": total_size / (1024 * 1024),
                                "speed_mbps": speed_mb,
                                "message": f"Downloading {model_name} model: {percent:.1f}% ({speed_mb:.1f} MB/s)",
                            }
                        )

                urllib.request.urlretrieve(url, dest_path, reporthook=report_progress)

            try:
                if progress_callback:
                    progress_callback(
                        {
                            "status": "starting_download",
                            "model": model_name,
                            "message": f"Starting download of {model_name} model (~{model_sizes_mb.get(model_filename, 100)} MB)...",
                        }
                    )

                download_with_progress(url, str(model_path), progress_callback)

                if progress_callback:
                    progress_callback(
                        {
                            "status": "download_complete",
                            "model": model_name,
                            "message": f"Successfully downloaded {model_name} model",
                        }
                    )

            except Exception as e:
                if model_path.exists():
                    model_path.unlink()  # Remove partial download
                raise Exception(f"Failed to download model: {e}")

        return model_path

    def _validate_transcription_quality(
        self, text: str, audio_duration_seconds: float | None = None
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

            # Expected speaking rates (words per minute)
            # Very slow: 80-120 WPM (lectures with pauses, technical content)
            # Normal: 120-180 WPM (conversation, presentations)
            # Fast: 180-250 WPM (news, fast speakers)
            # Audio with music/silence should still have some speech

            if words_per_minute < 15:  # Less than 15 WPM suggests major failure
                return {
                    "is_valid": False,
                    "issue": f"Transcription too short for audio duration ({word_count:,} words in {duration_minutes:.1f} min = {words_per_minute:.1f} WPM, expected >15 WPM)",
                }
            elif (
                words_per_minute < 40
            ):  # 15-40 WPM suggests partial failure or mostly silence
                return {
                    "is_valid": False,
                    "issue": f"Low word density suggests partial transcription failure or mostly silent audio ({words_per_minute:.1f} WPM, expected >40 WPM for speech)",
                }
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

            # If more than 5 consecutive identical words, likely a failure
            if max_consecutive >= 5:
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

        # Check for gibberish patterns (too many single-character words)
        single_char_words = sum(1 for word in words if len(word) == 1)
        if single_char_words / len(words) > 0.3:
            return {
                "is_valid": False,
                "issue": f"Too many single-character words ({single_char_words}/{len(words)})",
            }

        # Check for likely foreign language when expecting English
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
        english_word_count = sum(1 for word in words if word in common_english_words)
        if len(words) > 50 and english_word_count / len(words) < 0.1:
            return {
                "is_valid": False,
                "issue": f"Very few common English words detected ({english_word_count}/{len(words)}), possible language mismatch",
            }

        return {"is_valid": True, "issue": None}

    def _load_model(self):
        """Download whisper.cpp model if needed (for subprocess usage)."""
        # We're using subprocess approach, so just ensure model is downloaded
        if self._model_path is None:
            self._model_path = self._download_model(
                self.model_name, self.progress_callback
            )

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

            subprocess.run(cmd, check=True, capture_output=True)
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg conversion failed: {e}")
            output_path.unlink(missing_ok=True)
            raise

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
        device = kwargs.get("device", None)

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
        logger.info("Processing audio with native whisper.cpp")

        # Emit initial progress
        if self.progress_callback:
            self.progress_callback("🎤 Initializing whisper.cpp transcription...", 5)

        # Extract audio duration for quality validation
        audio_duration_seconds = self._get_audio_duration(input_path)
        if audio_duration_seconds:
            logger.info(
                f"Audio duration: {audio_duration_seconds:.1f} seconds ({audio_duration_seconds/60:.1f} minutes)"
            )

        temp_wav = None
        try:
            # Try multiple common whisper.cpp binary names
            whisper_cmd = None
            for cmd_candidate in ["whisper-cli", "whisper-cpp", "whisper"]:
                try:
                    subprocess.run(
                        [cmd_candidate, "--help"], capture_output=True, check=True
                    )
                    whisper_cmd = cmd_candidate
                    logger.info(f"Found whisper binary: {whisper_cmd}")
                    break
                except (subprocess.CalledProcessError, FileNotFoundError):
                    continue

            if not whisper_cmd:
                raise Exception(
                    "No whisper.cpp binary found. Please install whisper.cpp and ensure one of these binaries is in your PATH: "
                    "whisper-cli, whisper-cpp, or whisper"
                )

            if self.progress_callback:
                self.progress_callback(f"✅ Using {whisper_cmd} for transcription", 10)

            # Convert to WAV if needed
            if input_path.suffix.lower() != ".wav":
                if self.progress_callback:
                    self.progress_callback("🔄 Converting audio to WAV format...", 15)
                temp_wav = self._convert_to_wav(input_path)
                audio_path = temp_wav
                if self.progress_callback:
                    self.progress_callback("✅ Audio conversion completed", 25)
            else:
                audio_path = input_path
                if self.progress_callback:
                    self.progress_callback("✅ Audio already in WAV format", 20)

            # Download model if needed
            if self.progress_callback:
                self.progress_callback(
                    f"📥 Ensuring model '{self.model_name}' is available...", 30
                )
            model_path = self._download_model(self.model_name)
            if self.progress_callback:
                self.progress_callback(f"✅ Model '{self.model_name}' ready", 40)

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
                    "-f",
                    str(audio_path),
                ]

                # Add threading and batch size parameters if provided
                omp_threads = kwargs.get("omp_threads")
                if omp_threads:
                    cmd.extend(["-t", str(omp_threads)])

                batch_size = kwargs.get("batch_size")
                if batch_size:
                    cmd.extend(["-bs", str(batch_size)])

                # Add output options
                cmd.extend(
                    [
                        "--output-json",
                        "--no-timestamps",
                        "--output-file",
                        str(output_base),
                    ]
                )

                if self.progress_callback:
                    self.progress_callback("🎯 Running whisper.cpp transcription...", 50)

                logger.info(f"Running command: {' '.join(cmd)}")

                # Use real-time progress monitoring instead of blocking subprocess.run
                result = self._run_whisper_with_progress(cmd)

                if self.progress_callback:
                    self.progress_callback("✅ Whisper.cpp processing completed", 80)

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
                    validation_result = self._validate_transcription_quality(
                        full_text, audio_duration_seconds
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
                    validation_result = self._validate_transcription_quality(
                        full_text, audio_duration_seconds
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
            logger.error(f"Whisper.cpp subprocess error: {e}")
            if self.progress_callback:
                self.progress_callback(f"❌ Transcription failed: {str(e)}", 0)
            return ProcessorResult(
                success=False, errors=[f"Subprocess transcription failed: {e}"]
            )
        finally:
            if temp_wav and temp_wav.exists():
                temp_wav.unlink(missing_ok=True)

    def _run_whisper_with_progress(self, cmd) -> subprocess.CompletedProcess:
        """Run whisper.cpp with real-time progress monitoring."""
        import threading
        import time
        from collections import namedtuple

        # Create a simple result container
        CompletedProcess = namedtuple(
            "CompletedProcess", ["stdout", "stderr", "returncode"]
        )

        start_time = time.time()
        progress_start = 50  # We start monitoring from 50%
        progress_end = 80  # We end monitoring at 80%
        progress_range = progress_end - progress_start

        # Use Popen for real-time monitoring
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
            universal_newlines=True,
        )

        stdout_lines = []
        stderr_lines = []

        def monitor_progress():
            """Monitor progress in a separate thread."""
            nonlocal stdout_lines, stderr_lines

            # Monitor both stdout and stderr for progress indicators
            while process.poll() is None:
                elapsed = time.time() - start_time

                # Read available output without blocking
                try:
                    # Check if there's stdout data
                    if process.stdout and process.stdout.readable():
                        line = process.stdout.readline()
                        if line:
                            stdout_lines.append(line)
                            # Look for progress indicators in output
                            if self.progress_callback:
                                self._parse_whisper_output_for_progress(line, elapsed)

                    # Check if there's stderr data
                    if process.stderr and process.stderr.readable():
                        line = process.stderr.readline()
                        if line:
                            stderr_lines.append(line)
                            # Look for progress indicators in stderr
                            if self.progress_callback:
                                self._parse_whisper_output_for_progress(line, elapsed)

                except:
                    # Handle any read errors gracefully
                    pass

                # Estimate progress based on elapsed time (fallback)
                # Rough estimate: most audio files take 0.1x - 0.3x real-time to process
                estimated_duration = 120  # Default 2 minutes if unknown
                try:
                    # Try to get actual audio duration using ffprobe
                    import subprocess

                    probe_cmd = [
                        "ffprobe",
                        "-v",
                        "quiet",
                        "-show_entries",
                        "format=duration",
                        "-of",
                        "csv=p=0",
                        cmd[cmd.index("-f") + 1],
                    ]
                    probe_result = subprocess.run(
                        probe_cmd, capture_output=True, text=True, timeout=5
                    )
                    if probe_result.returncode == 0 and probe_result.stdout.strip():
                        estimated_duration = float(probe_result.stdout.strip())
                except:
                    # Fallback to default if ffprobe fails
                    pass

                # Estimate progress: assume processing takes 0.2x real-time on average
                processing_speed = 0.2  # 20% of real-time
                estimated_completion_time = estimated_duration * processing_speed

                if estimated_completion_time > 0:
                    time_progress = min(1.0, elapsed / estimated_completion_time)
                    current_progress = progress_start + (time_progress * progress_range)

                    if (
                        self.progress_callback and elapsed > 2
                    ):  # Don't spam early progress
                        self.progress_callback(
                            f"🎯 Processing audio ({elapsed:.0f}s elapsed, ~{current_progress:.0f}% complete)...",
                            int(current_progress),
                        )

                time.sleep(0.5)  # Check every 500ms

        # Start progress monitoring in background
        progress_thread = threading.Thread(target=monitor_progress, daemon=True)
        progress_thread.start()

        # Wait for process completion
        try:
            stdout, stderr = process.communicate(timeout=3600)  # 1 hour timeout
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            raise Exception("Whisper.cpp process timed out")

        # Combine all output
        full_stdout = "".join(stdout_lines) + stdout
        full_stderr = "".join(stderr_lines) + stderr

        # Wait for progress thread to finish
        progress_thread.join(timeout=1)

        if process.returncode != 0:
            error_msg = f"Whisper.cpp failed with return code {process.returncode}"
            if full_stderr:
                error_msg += f"\nStderr: {full_stderr}"
            raise subprocess.CalledProcessError(
                process.returncode, cmd, full_stdout, full_stderr
            )

        return CompletedProcess(full_stdout, full_stderr, process.returncode)

    def _parse_whisper_output_for_progress(self, line: str, elapsed_time: float):
        """Parse whisper.cpp output for progress indicators."""
        line = line.strip().lower()

        # Look for common progress indicators in whisper.cpp output
        if "processing" in line or "transcribing" in line:
            # Found processing indicator
            progress = 55 + min(
                20, int(elapsed_time / 2)
            )  # Gradual increase from 55% to 75%
            self.progress_callback(f"🎯 {line.capitalize()}", progress)
        elif "segment" in line or "frame" in line:
            # Processing segments/frames
            progress = 60 + min(
                15, int(elapsed_time / 3)
            )  # Gradual increase from 60% to 75%
            self.progress_callback(f"🎯 Processing segments...", progress)
        elif "done" in line or "finished" in line or "complete" in line:
            # Near completion
            self.progress_callback("🎯 Finalizing transcription...", 75)

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
    audio_path: str | Path, model: str = "base", use_coreml: bool | None = None
) -> str | None:
    """Convenience function to transcribe an audio file using whisper.cpp."""
    proc = WhisperCppTranscribeProcessor(model=model, use_coreml=use_coreml)
    result = proc.process(audio_path)
    return result.data.get("text") if result.success else None
