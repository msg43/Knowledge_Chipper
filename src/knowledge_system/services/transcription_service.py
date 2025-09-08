"""
Transcription Service
Transcription Service

Provides transcription capabilities for audio files and YouTube URLs using Whisper.
Supports batch processing, multiple output formats, and configurable settings.
"""

from pathlib import Path
from typing import Any

from ..logger import get_logger
from ..processors.audio_processor import AudioProcessor
from ..processors.youtube_download import YouTubeDownloadProcessor

logger = get_logger(__name__)


class TranscriptionService:
    """Service for transcribing audio files and YouTube URLs."""

    def __init__(
        self,
        whisper_model: str = "base",
        normalize_audio: bool = True,
        download_thumbnails: bool = True,
        prefer_transcripts: bool = True,
        temp_dir: str | Path | None = None,
        use_whisper_cpp: bool = False,
    ) -> None:
        """
        Initialize the transcription service

        Args:
            whisper_model: Whisper model to use
            normalize_audio: Whether to normalize audio
            download_thumbnails: Whether to download thumbnails
            prefer_transcripts: Whether to prefer YouTube transcripts over audio transcription
            temp_dir: Temporary directory for downloads
            use_whisper_cpp: Whether to use whisper.cpp with Core ML acceleration
        """
        self.whisper_model = whisper_model

        self.whisper_model = whisper_model
        self.normalize_audio = normalize_audio
        self.download_thumbnails = download_thumbnails
        self.prefer_transcripts = prefer_transcripts
        self.temp_dir = temp_dir
        self.use_whisper_cpp = use_whisper_cpp

        # Get HuggingFace token for diarization
        from ..config import get_settings

        settings = get_settings()
        hf_token = getattr(settings.api_keys, "huggingface_token", None)

        # Initialize processors
        self.audio_processor = AudioProcessor(
            normalize_audio=normalize_audio,
            temp_dir=temp_dir,
            use_whisper_cpp=use_whisper_cpp,
            model=whisper_model,
            hf_token=hf_token,
        )
        self.youtube_downloader = YouTubeDownloadProcessor()
        # Lazy initialization of YouTube transcript processor to handle missing API keys gracefully
        self._youtube_transcript_processor = None

    @property
    def youtube_transcript_processor(self):
        """Lazy initialization of YouTube transcript processor."""
        if self._youtube_transcript_processor is None:
            from ..processors.youtube_transcript import YouTubeTranscriptProcessor

            self._youtube_transcript_processor = YouTubeTranscriptProcessor()
        return self._youtube_transcript_processor

    def set_progress_callback(self, callback):
        """Set a progress callback for model downloads and other progress updates."""
        if hasattr(self.audio_processor, "transcriber") and hasattr(
            self.audio_processor.transcriber, "progress_callback"
        ):
            self.audio_processor.transcriber.progress_callback = callback

    def transcribe_audio_file(self, audio_file: str | Path) -> dict[str, Any]:
        """Transcribe an audio file using Whisper."""
        logger.info(f"Starting transcription of audio file: {audio_file}")

        try:
            result = self.audio_processor.process(audio_file)

            if result.success:
                return {
                    "success": True,
                    "transcript": result.data.get("transcript", ""),
                    "language": result.data.get("language", "unknown"),
                    "duration": result.data.get("duration"),
                    "source": str(audio_file),
                    "metadata": result.metadata,
                }
            else:
                return {
                    "success": False,
                    "error": (
                        result.errors[0] if result.errors else "Transcription failed"
                    ),
                    "source": str(audio_file),
                }

        except Exception as e:
            logger.error(f"Audio transcription failed for {audio_file}: {e}")
            return {"success": False, "error": str(e), "source": str(audio_file)}

    def transcribe_youtube_url(
        self,
        url: str,
        download_thumbnails: bool | None = None,
        output_dir: str | Path | None = None,
        include_timestamps: bool = True,
        enable_diarization: bool = False,
        require_diarization: bool = False,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Extract transcript from a YouTube URL."""
        logger.info(f"Starting transcript extraction from YouTube URL: {url}")

        try:
            # Require Bright Data credentials for YouTube processing
            from ..config import get_settings

            settings = get_settings()

            # Bright Data API key is required for transcript extraction via Bright Data's API,
            # but proxy credentials (BD_CUST/BD_ZONE/BD_PASS) are NOT required here.
            # We only validate the presence/format of the API key and proceed.
            bright_data_api_key = getattr(
                settings.api_keys, "bright_data_api_key", None
            )
            if not bright_data_api_key:
                return {
                    "success": False,
                    "error": "Bright Data API key is required for YouTube processing. Please configure your Bright Data API Key in Settings.",
                    "source": url,
                }

            # If diarization is required, skip YouTube transcript API and use audio processing
            if enable_diarization:
                logger.info(
                    f"Diarization requested - using audio processing instead of YouTube API for: {url}"
                )

                # Use YouTube transcript processor but force diarization mode
                from ..processors.youtube_transcript import YouTubeTranscriptProcessor

                processor = YouTubeTranscriptProcessor(
                    preferred_language="en",
                    prefer_manual=True,
                    fallback_to_auto=True,
                    force_diarization=True,  # Force diarization mode
                    require_diarization=require_diarization,  # Strict mode
                )
            else:
                from ..processors.youtube_transcript import YouTubeTranscriptProcessor

                processor = YouTubeTranscriptProcessor(
                    preferred_language="en",
                    prefer_manual=True,
                    fallback_to_auto=True,
                )

            transcript_result = processor.process(
                url,
                output_dir=output_dir,
                include_timestamps=include_timestamps,
                include_analysis=True,
                enable_diarization=enable_diarization,
                overwrite=overwrite,
            )

            if transcript_result.success and transcript_result.data.get("transcripts"):
                # Success - extract data from result
                transcripts = transcript_result.data["transcripts"]
                output_files = transcript_result.data.get("output_files", [])
                thumbnails = []

                # Handle thumbnail download if requested - download for each video individually
                if download_thumbnails and transcripts:
                    from ..utils.youtube_utils import download_thumbnail

                    output_path = Path(output_dir) if output_dir else Path.cwd()

                    # Create Thumbnails subdirectory for consistent organization
                    thumbnails_dir = output_path / "Thumbnails"
                    thumbnails_dir.mkdir(exist_ok=True)

                    for transcript in transcripts:
                        video_url = transcript.get(
                            "url", url
                        )  # Use video URL if available, fallback to original
                        thumbnail_url = transcript.get(
                            "thumbnail_url"
                        )  # Use thumbnail URL if available from metadata

                        try:
                            thumbnail_path = download_thumbnail(
                                video_url, thumbnails_dir, thumbnail_url=thumbnail_url
                            )
                            if thumbnail_path:
                                thumbnails.append(thumbnail_path)
                                logger.info(
                                    f"Downloaded thumbnail for video: {transcript.get('title', 'Unknown')}"
                                )
                            else:
                                logger.warning(
                                    f"Failed to download thumbnail for video: {transcript.get('title', 'Unknown')}"
                                )
                        except Exception as e:
                            logger.warning(
                                f"Error downloading thumbnail for {video_url}: {e}"
                            )

                    logger.info(
                        f"Downloaded {len(thumbnails)} thumbnails out of {len(transcripts)} videos"
                    )

                if transcripts:
                    transcript = transcripts[0]  # Use first transcript
                    return {
                        "success": True,
                        "transcript": transcript.get("transcript_text", ""),
                        "language": transcript.get("language", "unknown"),
                        "is_manual": transcript.get("is_manual", False),
                        "duration": transcript.get("duration"),
                        "source": url,
                        "output_files": output_files,
                        "metadata": transcript_result.metadata,
                        "method": "bright_data_proxy",
                        "thumbnails": thumbnails,
                    }

            # If we get here, transcript extraction failed
            errors = (
                transcript_result.errors
                if transcript_result.errors
                else ["Unknown transcript extraction error"]
            )
            error_msg = "; ".join(errors)

            proxy_service = "Bright Data"
            return {
                "success": False,
                "error": f"YouTube transcript extraction failed with {proxy_service} proxy: {error_msg}.",
                "source": url,
            }

        except Exception as e:
            logger.error(f"YouTube transcript extraction failed for {url}: {e}")
            proxy_service = "Bright Data"
            return {
                "success": False,
                "error": f"YouTube processing error with {proxy_service} proxy: {str(e)}.",
                "source": url,
            }

    def transcribe_input(
        self,
        input_path_or_url: str | Path,
        download_thumbnails: bool | None = None,
        output_dir: str | Path | None = None,
        include_timestamps: bool = True,
    ) -> dict[str, Any]:
        """Transcribe any supported input (audio file or YouTube URL)."""
        input_str = str(input_path_or_url)

        # Check if it's a YouTube URL
        if "youtube.com" in input_str or "youtu.be" in input_str:
            return self.transcribe_youtube_url(
                input_str,
                download_thumbnails=download_thumbnails,
                output_dir=output_dir,
                include_timestamps=include_timestamps,
            )
        else:
            return self.transcribe_audio_file(input_str)

    def transcribe_batch(
        self,
        inputs: list[str | Path],
        download_thumbnails: bool | None = None,
        output_dir: str | Path | None = None,
        include_timestamps: bool = True,
    ) -> list[dict[str, Any]]:
        """Transcribe multiple inputs in batch."""
        logger.info(f"Starting batch transcription of {len(inputs)} items")

        results = []
        for i, input_item in enumerate(inputs, 1):
            logger.info(f"Processing item {i}/{len(inputs)}: {input_item}")
            result = self.transcribe_input(
                input_item,
                download_thumbnails=download_thumbnails,
                output_dir=output_dir,
                include_timestamps=include_timestamps,
            )
            result["index"] = i
            result["total"] = len(inputs)
            results.append(result)

        return results

    def get_supported_formats(self) -> dict[str, list[str] | str]:
        """Get information about supported input formats."""
        return {
            "audio_formats": self.audio_processor.supported_formats,
            "youtube_urls": ["youtube.com", "youtu.be"],
            "whisper_model": self.whisper_model,
        }


def transcribe_audio(
    audio_file: str | Path,
    model: str = "base",
    normalize: bool = True,
    temp_dir: str | Path | None = None,
) -> str | None:
    """Convenience function to transcribe an audio file."""
    service = TranscriptionService(
        whisper_model=model, normalize_audio=normalize, temp_dir=temp_dir
    )
    result = service.transcribe_audio_file(audio_file)
    return result.get("transcript") if result["success"] else None


def transcribe_youtube(
    url: str,
    normalize: bool = True,
    download_thumbnails: bool = True,
    prefer_transcripts: bool = True,
    temp_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
    include_timestamps: bool = True,
) -> str | None:
    """Convenience function to extract transcript from a YouTube URL."""
    service = TranscriptionService(
        normalize_audio=normalize,
        download_thumbnails=download_thumbnails,
        prefer_transcripts=prefer_transcripts,
        temp_dir=temp_dir,
    )
    result = service.transcribe_youtube_url(
        url, output_dir=output_dir, include_timestamps=include_timestamps
    )
    return result.get("transcript") if result["success"] else None


def transcribe_file(
    input_path: str | Path,
    model: str = "base",
    normalize: bool = True,
    download_thumbnails: bool | None = None,
    output_dir: str | Path | None = None,
    include_timestamps: bool = True,
    temp_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Convenience function to transcribe any supported input (audio file or YouTube URL)."""
    service = TranscriptionService(
        whisper_model=model,
        normalize_audio=normalize,
        download_thumbnails=(
            download_thumbnails if download_thumbnails is not None else True
        ),
        temp_dir=temp_dir,
    )
    return service.transcribe_input(
        input_path,
        download_thumbnails=download_thumbnails,
        output_dir=output_dir,
        include_timestamps=include_timestamps,
    )
