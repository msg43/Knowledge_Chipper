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
        # Lazy initialization of YouTube download processor
        self._youtube_download_processor = None

    @property
    def youtube_download_processor(self):
        """Lazy initialization of YouTube download processor."""
        if self._youtube_download_processor is None:
            from ..processors.youtube_download import YouTubeDownloadProcessor

            self._youtube_download_processor = YouTubeDownloadProcessor()
        return self._youtube_download_processor

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
        """Download YouTube audio and transcribe it."""
        logger.info(f"Starting YouTube download and transcription for: {url}")

        try:
            # First download the audio
            download_result = self.youtube_download_processor.process(
                url,
                output_dir=output_dir,
                download_thumbnails=download_thumbnails,
            )

            if not download_result.success:
                return {
                    "success": False,
                    "error": download_result.errors[0] if download_result.errors else "Download failed",
                    "source": url,
                }

            # Get the downloaded audio file path
            downloaded_files = download_result.data.get("files", [])
            if not downloaded_files:
                return {
                    "success": False,
                    "error": "No audio file was downloaded",
                    "source": url,
                }

            audio_file = downloaded_files[0]
            logger.info(f"Downloaded audio file: {audio_file}")

            # Now transcribe the audio file
            transcribe_result = self.audio_processor.process(
                audio_file,
                output_dir=output_dir,
                include_timestamps=include_timestamps,
                enable_diarization=enable_diarization,
                require_diarization=require_diarization,
            )

            if transcribe_result.success:
                # Success - extract data from result
                transcript_text = transcribe_result.data.get("text", "")
                output_files = []
                if transcribe_result.metadata.get("saved_markdown_file"):
                    output_files.append(transcribe_result.metadata["saved_markdown_file"])
                
                # Get thumbnail info from download result
                thumbnails = download_result.data.get("thumbnails", [])
                
                return {
                    "success": True,
                    "transcript": transcript_text,
                    "language": transcribe_result.data.get("language", "unknown"),
                    "duration": transcribe_result.data.get("duration"),
                    "source": url,
                    "output_files": output_files,
                    "metadata": transcribe_result.metadata,
                    "method": "download_and_transcribe",
                    "thumbnails": thumbnails,
                }

            else:
                # Transcription failed
                errors = (
                    transcribe_result.errors
                    if transcribe_result.errors
                    else ["Unknown transcription error"]
                )
                error_msg = "; ".join(errors)
                
                return {
                    "success": False,
                    "error": f"Transcription failed: {error_msg}",
                    "source": url,
                }

        except Exception as e:
            logger.error(f"YouTube download/transcription failed for {url}: {e}")
            return {
                "success": False,
                "error": f"YouTube processing error: {str(e)}",
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
