#!/usr/bin/env python3
"""
Transcript Acquisition Orchestrator

Two-phase workflow for acquiring transcripts from YouTube videos:
1. Phase 1: Rapid metadata + transcript fetch (1-3 second delays)
2. Phase 2: Whisper fallback for videos without transcripts (3-5 minute delays)

This replaces the fragmented download logic with a clean, unified orchestrator.
"""

import asyncio
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from ..database.service import DatabaseService
from ..logger import get_logger
from ..processors.audio_processor import AudioProcessor
from ..processors.youtube_download import YouTubeDownloadProcessor
from ..utils.video_id_extractor import VideoIDExtractor

logger = get_logger(__name__)


class TranscriptResult:
    """Result from transcript acquisition attempt."""

    def __init__(
        self,
        success: bool,
        video_id: str,
        url: str,
        metadata: dict[str, Any] | None = None,
        transcript: str | None = None,
        needs_whisper: bool = False,
        error: str | None = None,
    ):
        self.success = success
        self.video_id = video_id
        self.url = url
        self.metadata = metadata or {}
        self.transcript = transcript
        self.needs_whisper = needs_whisper
        self.error = error


class TranscriptAcquisitionOrchestrator:
    """
    Unified orchestrator for acquiring transcripts from YouTube videos.

    Two-phase approach:
    - Phase 1: Rapid metadata + transcript fetch using YouTube API (fast)
    - Phase 2: Whisper fallback for videos without transcripts (slow, careful)
    """

    def __init__(
        self,
        db_service: DatabaseService | None = None,
        output_dir: Path | str | None = None,
        cookie_file_path: str | None = None,
        whisper_model: str = "base",
        whisper_device: str = "cpu",
    ):
        """
        Initialize orchestrator.

        Args:
            db_service: Database service for storing metadata and transcripts
            output_dir: Directory for downloaded audio files
            cookie_file_path: Path to cookies file for YouTube authentication
            whisper_model: Whisper model to use for transcription
            whisper_device: Device for Whisper (cpu/cuda/mps)
        """
        self.db_service = db_service or DatabaseService()
        self.output_dir = Path(output_dir) if output_dir else Path.home() / "Downloads"
        self.cookie_file_path = cookie_file_path
        self.whisper_model = whisper_model
        self.whisper_device = whisper_device

        # Phase 1 pacing (rapid)
        self.phase1_min_delay = 1.0  # 1 second
        self.phase1_max_delay = 3.0  # 3 seconds
        self.phase1_burst_size = 20  # Pause after N videos
        self.phase1_burst_pause_min = 30  # 30 seconds
        self.phase1_burst_pause_max = 60  # 60 seconds

        # Phase 2 pacing (slow, anti-bot)
        self.phase2_min_delay = 180.0  # 3 minutes
        self.phase2_max_delay = 300.0  # 5 minutes

        logger.info(
            f"TranscriptAcquisitionOrchestrator initialized: "
            f"Phase 1 (rapid): {self.phase1_min_delay}-{self.phase1_max_delay}s, "
            f"Phase 2 (slow): {self.phase2_min_delay/60:.1f}-{self.phase2_max_delay/60:.1f}min"
        )

    async def acquire_transcripts(
        self,
        urls: list[str],
        force_whisper: bool = False,
        progress_callback: Callable[[str], None] | None = None,
    ) -> dict[str, TranscriptResult]:
        """
        Acquire transcripts for a batch of YouTube URLs.

        Args:
            urls: List of YouTube video URLs
            force_whisper: Skip Phase 1 and force Whisper transcription
            progress_callback: Optional callback for progress updates

        Returns:
            Dict mapping video_id to TranscriptResult
        """
        logger.info(
            f"🚀 Starting transcript acquisition for {len(urls)} URLs "
            f"(force_whisper={force_whisper})"
        )

        if force_whisper:
            logger.info("⚡ Force Whisper mode: Skipping Phase 1, going straight to audio download")
            # Skip Phase 1, go straight to Phase 2
            results = {}
            for url in urls:
                video_id = self._extract_video_id(url)
                if video_id:
                    # Get metadata first
                    metadata = await self._fetch_metadata(video_id)
                    if metadata:
                        results[video_id] = TranscriptResult(
                            success=False,
                            video_id=video_id,
                            url=url,
                            metadata=metadata,
                            needs_whisper=True,
                        )

            phase2_results = await self._phase2_whisper_fallback(
                list(results.values()), progress_callback
            )
            return phase2_results

        # Normal two-phase workflow
        phase1_results = await self._phase1_rapid_fetch(urls, progress_callback)

        # Separate successes from failures
        successful = [r for r in phase1_results.values() if r.transcript and not r.needs_whisper]
        needs_whisper = [r for r in phase1_results.values() if r.needs_whisper]

        logger.info(
            f"✅ Phase 1 complete: "
            f"{len(successful)} transcripts obtained, "
            f"{len(needs_whisper)} need Whisper fallback"
        )

        # Phase 2: Whisper fallback for videos without transcripts
        if needs_whisper:
            logger.info(
                f"🔄 Phase 2: Whisper fallback for {len(needs_whisper)} videos "
                f"(slow pacing: {self.phase2_min_delay/60:.1f}-{self.phase2_max_delay/60:.1f} min delays)"
            )
            phase2_results = await self._phase2_whisper_fallback(
                needs_whisper, progress_callback
            )

            # Merge Phase 2 results back into Phase 1 results
            for video_id, result in phase2_results.items():
                phase1_results[video_id] = result

        # Final summary
        total_success = sum(1 for r in phase1_results.values() if r.success and r.transcript)
        logger.info(
            f"🎉 Transcript acquisition complete: "
            f"{total_success}/{len(urls)} transcripts obtained"
        )

        return phase1_results

    async def _phase1_rapid_fetch(
        self,
        urls: list[str],
        progress_callback: Callable[[str], None] | None = None,
    ) -> dict[str, TranscriptResult]:
        """
        Phase 1: Rapid metadata + transcript fetch using YouTube API.

        Fast pacing: 1-3 seconds between requests, 30-60 second pause every 20 videos.
        """
        logger.info(f"📥 Phase 1: Rapid fetch for {len(urls)} videos")
        results = {}

        for idx, url in enumerate(urls, 1):
            video_id = self._extract_video_id(url)
            if not video_id:
                logger.warning(f"⚠️ Could not extract video ID from URL: {url}")
                continue

            if progress_callback:
                progress_callback(
                    f"Phase 1: [{idx}/{len(urls)}] Fetching metadata + transcript for {video_id}..."
                )

            # Fetch metadata and transcript
            result = await self._fetch_metadata_and_transcript(video_id, url)
            results[video_id] = result

            # Log result
            if result.transcript:
                logger.info(
                    f"✅ [{idx}/{len(urls)}] {video_id}: Got transcript via YouTube API"
                )
            else:
                logger.info(
                    f"⚠️ [{idx}/{len(urls)}] {video_id}: No transcript available, needs Whisper"
                )

            # Apply pacing (except for last video)
            if idx < len(urls):
                await self._apply_phase1_pacing(idx)

        return results

    async def _phase2_whisper_fallback(
        self,
        failed_videos: list[TranscriptResult],
        progress_callback: Callable[[str], None] | None = None,
    ) -> dict[str, TranscriptResult]:
        """
        Phase 2: Download audio and transcribe with Whisper for videos without transcripts.

        Slow pacing: 3-5 minutes between downloads to avoid bot detection.
        """
        logger.info(f"📥 Phase 2: Whisper fallback for {len(failed_videos)} videos")
        results = {}

        for idx, video_result in enumerate(failed_videos, 1):
            video_id = video_result.video_id
            url = video_result.url

            if progress_callback:
                progress_callback(
                    f"Phase 2 (Whisper): [{idx}/{len(failed_videos)}] Downloading + transcribing {video_id}..."
                )

            try:
                # Download audio
                audio_file = await self._download_audio(url, video_id)

                if not audio_file:
                    results[video_id] = TranscriptResult(
                        success=False,
                        video_id=video_id,
                        url=url,
                        metadata=video_result.metadata,
                        error="Audio download failed",
                    )
                    continue

                # Transcribe with Whisper (NO diarization)
                transcript = await self._transcribe_with_whisper(audio_file, video_id)

                if transcript:
                    # Merge transcript with existing metadata in database
                    await self._merge_transcript_with_metadata(
                        video_id, transcript, "whisper_fallback"
                    )

                    results[video_id] = TranscriptResult(
                        success=True,
                        video_id=video_id,
                        url=url,
                        metadata=video_result.metadata,
                        transcript=transcript,
                        needs_whisper=False,
                    )

                    logger.info(
                        f"✅ [{idx}/{len(failed_videos)}] {video_id}: Transcribed with Whisper"
                    )
                else:
                    results[video_id] = TranscriptResult(
                        success=False,
                        video_id=video_id,
                        url=url,
                        metadata=video_result.metadata,
                        error="Whisper transcription failed",
                    )

            except Exception as e:
                logger.error(f"❌ Failed to process {video_id}: {e}")
                results[video_id] = TranscriptResult(
                    success=False,
                    video_id=video_id,
                    url=url,
                    metadata=video_result.metadata,
                    error=str(e),
                )

            # Apply slow pacing (except for last video)
            if idx < len(failed_videos):
                await self._apply_phase2_pacing(idx, len(failed_videos))

        return results

    async def _fetch_metadata_and_transcript(
        self, video_id: str, url: str
    ) -> TranscriptResult:
        """
        Fetch metadata and transcript for a single video.

        Returns TranscriptResult with metadata and transcript (if available).
        """
        try:
            # Fetch metadata
            metadata = await self._fetch_metadata(video_id)
            if not metadata:
                return TranscriptResult(
                    success=False,
                    video_id=video_id,
                    url=url,
                    error="Failed to fetch metadata",
                    needs_whisper=True,
                )

            # Store metadata in database immediately
            await self._store_metadata(video_id, metadata, url)

            # Try to get YouTube transcript
            transcript = await self._fetch_youtube_transcript(video_id)

            if transcript:
                # Store transcript in database
                await self._store_transcript(video_id, transcript, "youtube_api")

                return TranscriptResult(
                    success=True,
                    video_id=video_id,
                    url=url,
                    metadata=metadata,
                    transcript=transcript,
                    needs_whisper=False,
                )
            else:
                # No transcript available, needs Whisper
                return TranscriptResult(
                    success=False,
                    video_id=video_id,
                    url=url,
                    metadata=metadata,
                    needs_whisper=True,
                )

        except Exception as e:
            logger.error(f"Failed to fetch metadata/transcript for {video_id}: {e}")
            return TranscriptResult(
                success=False,
                video_id=video_id,
                url=url,
                error=str(e),
                needs_whisper=True,
            )

    async def _fetch_metadata(self, video_id: str) -> dict[str, Any] | None:
        """Fetch rich metadata using yt-dlp (fast, no download)."""
        try:
            import yt_dlp

            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": True,
                "skip_download": True,
                "socket_timeout": 30,
            }

            url = f"https://www.youtube.com/watch?v={video_id}"

            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(
                None, lambda: self._extract_info_sync(url, ydl_opts)
            )

            if not info:
                return None

            return {
                "video_id": video_id,
                "title": info.get("title"),
                "channel_id": info.get("channel_id"),
                "channel_name": info.get("channel") or info.get("uploader"),
                "description": info.get("description"),
                "upload_date": info.get("upload_date"),
                "duration_seconds": info.get("duration"),
                "view_count": info.get("view_count"),
                "like_count": info.get("like_count"),
                "tags": info.get("tags", []),
                "thumbnail_url": info.get("thumbnail"),
            }

        except Exception as e:
            logger.error(f"Failed to fetch metadata for {video_id}: {e}")
            return None

    def _extract_info_sync(self, url: str, ydl_opts: dict) -> dict | None:
        """Synchronous wrapper for yt-dlp extraction."""
        import yt_dlp

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)

    async def _fetch_youtube_transcript(self, video_id: str) -> str | None:
        """
        Fetch official YouTube transcript using youtube_transcript_api.

        Returns formatted transcript with timestamps, or None if unavailable.
        """
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            from youtube_transcript_api._errors import (
                NoTranscriptFound,
                TranscriptsDisabled,
            )

            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            transcript_list = await loop.run_in_executor(
                None,
                lambda: YouTubeTranscriptApi.get_transcript(
                    video_id, languages=["en", "en-US", "en-GB"]
                ),
            )

            # Format with timestamps
            formatted = []
            for entry in transcript_list:
                start = entry["start"]
                minutes = int(start // 60)
                seconds = int(start % 60)
                text = entry["text"]
                formatted.append(f"[{minutes:02d}:{seconds:02d}] {text}")

            return "\n".join(formatted)

        except (TranscriptsDisabled, NoTranscriptFound) as e:
            logger.debug(f"No YouTube transcript for {video_id}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Failed to fetch YouTube transcript for {video_id}: {e}")
            return None

    async def _store_metadata(
        self, video_id: str, metadata: dict[str, Any], url: str
    ) -> None:
        """Store metadata in media_sources table."""
        try:
            self.db_service.create_or_update_source(
                source_id=video_id,
                title=metadata.get("title"),
                url=url,
                source_type="youtube",
                uploader=metadata.get("channel_name"),
                upload_date=metadata.get("upload_date"),
                description=metadata.get("description"),
                duration_seconds=metadata.get("duration_seconds"),
                view_count=metadata.get("view_count"),
                thumbnail_url=metadata.get("thumbnail_url"),
                tags_json=metadata.get("tags", []),
                status="metadata_fetched",
            )
            logger.debug(f"✅ Stored metadata for {video_id}")
        except Exception as e:
            logger.error(f"Failed to store metadata for {video_id}: {e}")

    async def _store_transcript(
        self, video_id: str, transcript: str, transcript_source: str
    ) -> None:
        """Store transcript in transcripts table."""
        try:
            # Generate transcript_id
            transcript_id = f"{video_id}_transcript_{int(time.time())}"

            # Create transcript segments from formatted text
            segments = []
            for line in transcript.split("\n"):
                if line.strip():
                    # Parse timestamp if present
                    if line.startswith("["):
                        timestamp_end = line.find("]")
                        if timestamp_end > 0:
                            timestamp_str = line[1:timestamp_end]
                            text = line[timestamp_end + 1 :].strip()
                            # Parse MM:SS format
                            parts = timestamp_str.split(":")
                            if len(parts) == 2:
                                start = int(parts[0]) * 60 + int(parts[1])
                                segments.append({"start": start, "text": text})

            self.db_service.create_transcript(
                transcript_id=transcript_id,
                source_id=video_id,
                transcript_text=transcript,
                language="en",
                is_manual=False,
                transcript_type=transcript_source,
                transcript_segments_json=segments,
            )

            # Update source status
            self.db_service.update_source_status(video_id, "transcript_available")

            logger.debug(f"✅ Stored transcript for {video_id} (source: {transcript_source})")
        except Exception as e:
            logger.error(f"Failed to store transcript for {video_id}: {e}")

    async def _download_audio(self, url: str, video_id: str) -> Path | None:
        """Download audio file from YouTube."""
        try:
            output_dir = self.output_dir / "downloads" / "youtube"
            output_dir.mkdir(parents=True, exist_ok=True)

            downloader = YouTubeDownloadProcessor(
                enable_cookies=bool(self.cookie_file_path),
                cookie_file_path=self.cookie_file_path,
                download_thumbnails=False,
            )

            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: downloader.process(
                    url, output_dir=str(output_dir), db_service=self.db_service
                ),
            )

            if result.success and result.data:
                audio_path = result.data.get("audio_path")
                if audio_path:
                    return Path(audio_path)

            return None

        except Exception as e:
            logger.error(f"Failed to download audio for {video_id}: {e}")
            return None

    async def _transcribe_with_whisper(
        self, audio_file: Path, video_id: str
    ) -> str | None:
        """Transcribe audio file with Whisper (NO diarization)."""
        try:
            processor = AudioProcessor(
                model=self.whisper_model,
                device=self.whisper_device,
                use_whisper_cpp=True,
                enable_diarization=False,  # NO diarization for fallback
                db_service=self.db_service,
            )

            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, lambda: processor.process(str(audio_file))
            )

            if result.success and result.data:
                transcript = result.data.get("transcript")
                return transcript

            return None

        except Exception as e:
            logger.error(f"Failed to transcribe {video_id} with Whisper: {e}")
            return None

    async def _merge_transcript_with_metadata(
        self, video_id: str, transcript: str, transcript_source: str
    ) -> None:
        """
        Merge Whisper transcript with existing metadata in database.
        Metadata was already stored in Phase 1.
        """
        await self._store_transcript(video_id, transcript, transcript_source)

    async def _apply_phase1_pacing(self, current_index: int) -> None:
        """Apply Phase 1 pacing: 1-3 second delays with burst pauses."""
        # Regular delay
        delay = random.uniform(self.phase1_min_delay, self.phase1_max_delay)
        await asyncio.sleep(delay)

        # Burst pause every N videos
        if current_index % self.phase1_burst_size == 0:
            pause = random.uniform(
                self.phase1_burst_pause_min, self.phase1_burst_pause_max
            )
            logger.info(
                f"🛑 Burst pause: {pause:.1f}s after {current_index} videos (mimicking human browsing)"
            )
            await asyncio.sleep(pause)

    async def _apply_phase2_pacing(
        self, current_index: int, total: int
    ) -> None:
        """Apply Phase 2 pacing: 3-5 minute delays (anti-bot)."""
        delay = random.uniform(self.phase2_min_delay, self.phase2_max_delay)
        logger.info(
            f"⏳ Waiting {delay/60:.1f} minutes before next download "
            f"[{current_index}/{total}] (anti-bot pacing)"
        )
        await asyncio.sleep(delay)

    def _extract_video_id(self, url: str) -> str | None:
        """Extract YouTube video ID from URL."""
        return VideoIDExtractor.extract_video_id(url)

