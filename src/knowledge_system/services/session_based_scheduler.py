#!/usr/bin/env python3
"""
Session-Based Download Scheduler

Implements duty-cycle scheduling for YouTube downloads with per-account independent schedules.
Tracks source_ids for all downloads with state persistence for crash recovery.
"""

import asyncio
import json
import logging
import random
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ..config import get_settings
from ..database.service import DatabaseService
from ..logger import get_logger
from .multi_account_downloader import MultiAccountDownloadScheduler

logger = get_logger(__name__)


class SessionBasedScheduler:
    """
    Duty-cycle scheduler for YouTube downloads with per-account independent schedules.

    Features:
    - Per-account randomized schedules (2-4 sessions/day, staggered)
    - Per-account session parameters (60-180 min duration, 100-250 videos/session)
    - Persistent state for crash recovery
    - Individual account cooldowns (rate-limited account pauses, others continue)
    - Idle gap management (downloads pause, transcription continues)
    - Tracks source_ids for all downloads
    """

    def __init__(
        self,
        cookie_files: list[str],
        urls_with_source_ids: dict[str, str],  # {url: source_id}
        output_dir: Path,
        state_file: Path | None = None,
        db_service: DatabaseService | None = None,
        progress_callback=None,
    ):
        """
        Initialize session-based scheduler.

        Args:
            cookie_files: List of cookie file paths (one per account)
            urls_with_source_ids: Mapping of YouTube URLs to their source_ids
            output_dir: Directory to save downloaded audio files
            state_file: Path to state file for persistence
            db_service: Database service for deduplication
            progress_callback: Callback for progress updates
        """
        self.cookie_files = cookie_files
        self.urls_with_source_ids = urls_with_source_ids
        self.output_dir = Path(output_dir)
        self.db_service = db_service or DatabaseService()
        self.progress_callback = progress_callback

        # State file for crash recovery
        if state_file is None:
            state_file = Path("~/.knowledge_system/session_state.json").expanduser()
        self.state_file = Path(state_file)

        # Load configuration
        self.config = get_settings()
        self.yt_config = self.config.youtube_processing

        # Load or initialize state
        self.state = self._load_state()

        # Generate per-account schedules if not loaded from state
        if not self.state.get("accounts"):
            self._initialize_accounts()

        logger.info(
            f"SessionBasedScheduler initialized: "
            f"{len(self.cookie_files)} accounts, "
            f"{len(urls_with_source_ids)} URLs, "
            f"state_file={self.state_file}"
        )

        # Initialize download stage status for all URLs
        self._init_download_stage_statuses()

    def start(self) -> list[tuple[Path, str]]:
        """
        Start scheduler (blocking).

        Runs all scheduled sessions across all accounts until all URLs are downloaded.

        Returns:
            [(audio_file_path, source_id), ...]
        """
        logger.info("🚀 Starting session-based download scheduler")

        all_downloaded_files = []

        # Get list of remaining URLs
        remaining_urls = self._get_remaining_urls()

        if not remaining_urls:
            logger.info("✅ All URLs already downloaded")
            return []

        logger.info(
            f"📊 Remaining URLs: {len(remaining_urls)}/{len(self.urls_with_source_ids)}"
        )

        # Run sessions until all URLs are downloaded
        while remaining_urls:
            # Find next account ready to run a session
            result = self._get_next_ready_session()

            if result is None:
                # No accounts ready - wait for next session or cooldown to end
                wait_time = self._get_next_session_wait_time()
                logger.info(
                    f"⏳ All accounts idle or cooling down. Waiting {wait_time/60:.1f} minutes..."
                )

                if self.progress_callback:
                    self.progress_callback(
                        f"⏳ Idle period: waiting {wait_time/60:.0f} minutes for next session"
                    )

                time.sleep(wait_time)
                continue

            # Unpack the result
            account_idx, session = result

            # Run session for this account
            logger.info(
                f"▶️ Starting session for Account {account_idx+1}/{len(self.cookie_files)}: "
                f"duration={session['duration_min']}min, max_downloads={session['max_downloads']}"
            )

            if self.progress_callback:
                self.progress_callback(
                    f"▶️ Account {account_idx+1} session started "
                    f"({session['duration_min']}min, up to {session['max_downloads']} videos)"
                )

            # Get URLs for this session
            session_urls = remaining_urls[: session["max_downloads"]]
            session_urls_with_ids = {
                url: self.urls_with_source_ids[url] for url in session_urls
            }

            # Update stage status for URLs in this session
            for url in session_urls:
                source_id = self.urls_with_source_ids[url]
                self.db_service.upsert_stage_status(
                    source_id=source_id,
                    stage="download",
                    status="in_progress",
                    assigned_worker=f"Account_{account_idx+1}",
                    metadata={
                        "url": url,
                        "session_start": datetime.now().isoformat(),
                        "session_duration_min": session["duration_min"],
                        "account_idx": account_idx,
                    },
                )

            # Run session
            downloaded_files = self._run_account_session(
                account_idx, session, session_urls_with_ids
            )

            all_downloaded_files.extend(downloaded_files)

            # Update state
            self._update_session_complete(account_idx, session, downloaded_files)

            # Get updated remaining URLs
            remaining_urls = self._get_remaining_urls()

            logger.info(
                f"✅ Session complete: {len(downloaded_files)} downloads, "
                f"{len(remaining_urls)} URLs remaining"
            )

        logger.info(f"🎉 All downloads complete: {len(all_downloaded_files)} files")
        return all_downloaded_files

    def _initialize_accounts(self) -> None:
        """Initialize account schedules and state."""
        self.state["accounts"] = []

        for idx, cookie_file in enumerate(self.cookie_files):
            # Generate randomized schedule for this account
            schedule = self._generate_account_schedule(idx)

            account_state = {
                "account_idx": idx,
                "cookie_file": cookie_file,
                "schedule": schedule,
                "sessions_completed": 0,
                "next_session_idx": 0,
                "cooldown_until": None,
                "total_downloads": 0,
                "completed_source_ids": [],
            }

            self.state["accounts"].append(account_state)

        self._save_state()

    def _init_download_stage_statuses(self) -> None:
        """Initialize download stage status for all URLs."""
        for url, source_id in self.urls_with_source_ids.items():
            # Check if already downloaded
            completed_source_ids = set()
            for account in self.state.get("accounts", []):
                completed_source_ids.update(account.get("completed_source_ids", []))

            if source_id in completed_source_ids:
                status = "completed"
            else:
                status = "queued"

            # Create initial stage status
            self.db_service.upsert_stage_status(
                source_id=source_id,
                stage="download",
                status=status,
                metadata={
                    "url": url,
                    "scheduler": "session_based",
                    "total_accounts": len(self.cookie_files),
                },
            )

    def _generate_account_schedule(self, account_idx: int) -> list[dict]:
        """
        Generate randomized session schedule for one account.

        Schedules are staggered across accounts to avoid correlation.

        Args:
            account_idx: Account index

        Returns:
            List of session dicts with start_time, duration_min, max_downloads
        """
        # Randomize number of sessions per day for this account
        sessions_per_day = random.randint(
            self.yt_config.sessions_per_day_min, self.yt_config.sessions_per_day_max
        )

        # Generate sessions over next 7 days
        schedule = []
        current_time = datetime.now()

        for day in range(7):  # Generate 7 days of schedule
            day_start = current_time + timedelta(days=day)

            # Generate random session times for this day
            # Stagger by account index to avoid all accounts starting together
            base_offset_hours = (account_idx * 6) % 24  # Stagger accounts by 6 hours

            for session_num in range(sessions_per_day):
                # Random time within the day, offset by account
                hour_offset = random.randint(0, 23 - sessions_per_day * 4)
                hour = (base_offset_hours + hour_offset) % 24
                minute = random.randint(0, 59)

                start_time = day_start.replace(
                    hour=hour, minute=minute, second=0, microsecond=0
                )

                # Randomize session parameters
                duration_min = random.randint(
                    self.yt_config.session_duration_min,
                    self.yt_config.session_duration_max,
                )

                max_downloads = random.randint(
                    self.yt_config.max_downloads_per_session_min,
                    self.yt_config.max_downloads_per_session_max,
                )

                schedule.append(
                    {
                        "start_time": start_time.isoformat(),
                        "duration_min": duration_min,
                        "max_downloads": max_downloads,
                        "status": "pending",
                    }
                )

        # Sort by start time
        schedule.sort(key=lambda s: s["start_time"])

        logger.debug(
            f"Generated schedule for Account {account_idx}: "
            f"{len(schedule)} sessions over 7 days"
        )

        return schedule

    def _get_next_ready_session(self) -> tuple[int, dict] | None:
        """
        Find next account ready to run a session.

        Returns:
            (account_idx, session_dict) or None if no account ready
        """
        current_time = datetime.now()

        for account in self.state["accounts"]:
            account_idx = account["account_idx"]

            # Skip if account is cooling down
            if account["cooldown_until"]:
                cooldown_end = datetime.fromisoformat(account["cooldown_until"])
                if current_time < cooldown_end:
                    continue
                else:
                    # Cooldown ended
                    account["cooldown_until"] = None
                    self._save_state()

            # Get next pending session
            next_session_idx = account["next_session_idx"]
            if next_session_idx >= len(account["schedule"]):
                # All sessions completed for this account
                continue

            session = account["schedule"][next_session_idx]

            # Check if session start time has arrived
            session_start = datetime.fromisoformat(session["start_time"])
            if current_time >= session_start:
                return (account_idx, session)

        return None

    def _get_next_session_wait_time(self) -> float:
        """
        Calculate wait time until next session or cooldown end.

        Returns:
            Wait time in seconds
        """
        current_time = datetime.now()
        min_wait = float("inf")

        for account in self.state["accounts"]:
            # Check cooldown
            if account["cooldown_until"]:
                cooldown_end = datetime.fromisoformat(account["cooldown_until"])
                wait = (cooldown_end - current_time).total_seconds()
                if wait > 0:
                    min_wait = min(min_wait, wait)

            # Check next session
            next_session_idx = account["next_session_idx"]
            if next_session_idx < len(account["schedule"]):
                session = account["schedule"][next_session_idx]
                session_start = datetime.fromisoformat(session["start_time"])
                wait = (session_start - current_time).total_seconds()
                if wait > 0:
                    min_wait = min(min_wait, wait)

        # Default to 1 hour if no sessions found
        return min(min_wait, 3600) if min_wait != float("inf") else 3600

    def _run_account_session(
        self, account_idx: int, session: dict, urls_with_source_ids: dict[str, str]
    ) -> list[tuple[Path, str]]:
        """
        Run one session for one account.

        Args:
            account_idx: Account index
            session: Session dict
            urls_with_source_ids: URLs to download with their source_ids

        Returns:
            [(audio_file_path, source_id), ...]
        """
        account = self.state["accounts"][account_idx]
        cookie_file = account["cookie_file"]

        # Create multi-account scheduler with single account
        scheduler = MultiAccountDownloadScheduler(
            cookie_files=[cookie_file],
            parallel_workers=self.yt_config.concurrent_downloads_max,
            enable_sleep_period=False,  # Session-based scheduler handles timing
            db_service=self.db_service,
            disable_proxies_with_cookies=self.yt_config.disable_proxies_with_cookies,
        )

        # Set progress callback
        if self.progress_callback:
            scheduler.progress_callback = self.progress_callback

        # Download URLs
        try:
            # Run async download
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            results = loop.run_until_complete(
                scheduler.download_batch_with_rotation(
                    urls=list(urls_with_source_ids.keys()),
                    output_dir=self.output_dir,
                )
            )

            loop.close()

            # Extract downloaded files with source_ids
            downloaded_files = []
            for result in results:
                if result.get("success") and result.get("audio_file"):
                    audio_file = Path(result["audio_file"])
                    url = result["url"]
                    source_id = urls_with_source_ids[url]
                    downloaded_files.append((audio_file, source_id))

                    # Update account state
                    account["completed_source_ids"].append(source_id)
                    account["total_downloads"] += 1

                    # Update stage status to completed
                    self.db_service.upsert_stage_status(
                        source_id=source_id,
                        stage="download",
                        status="completed",
                        progress_percent=100.0,
                        metadata={
                            "url": url,
                            "audio_file": str(audio_file),
                            "file_size_bytes": audio_file.stat().st_size
                            if audio_file.exists()
                            else 0,
                            "completed_at": datetime.now().isoformat(),
                        },
                    )
                else:
                    # Mark failed downloads
                    url = result.get("url")
                    if url and url in urls_with_source_ids:
                        source_id = urls_with_source_ids[url]
                        self.db_service.upsert_stage_status(
                            source_id=source_id,
                            stage="download",
                            status="failed",
                            metadata={
                                "url": url,
                                "error": result.get("error", "Unknown error"),
                                "failed_at": datetime.now().isoformat(),
                            },
                        )

            return downloaded_files

        except Exception as e:
            import traceback

            error_details = traceback.format_exc()
            logger.error(f"Session failed for Account {account_idx}: {e}")
            logger.error(f"Full traceback:\n{error_details}")

            # Check if rate limiting error
            error_str = str(e).lower()
            if any(
                keyword in error_str
                for keyword in ["429", "403", "rate limit", "throttl"]
            ):
                self._handle_rate_limiting(account_idx)
            else:
                # For non-rate-limiting errors, re-raise to propagate to GUI
                raise

            return []

    def _handle_rate_limiting(self, account_idx: int) -> None:
        """
        Trigger cooldown for rate-limited account.

        Args:
            account_idx: Account index
        """
        account = self.state["accounts"][account_idx]

        # Calculate cooldown duration
        cooldown_minutes = random.randint(
            self.yt_config.cooldown_min_minutes, self.yt_config.cooldown_max_minutes
        )

        cooldown_end = datetime.now() + timedelta(minutes=cooldown_minutes)
        account["cooldown_until"] = cooldown_end.isoformat()

        logger.warning(
            f"🛑 Account {account_idx+1} rate limited - cooling down for {cooldown_minutes} minutes "
            f"(until {cooldown_end.strftime('%H:%M')})"
        )

        if self.progress_callback:
            self.progress_callback(
                f"🛑 Account {account_idx+1} rate limited - cooldown {cooldown_minutes}min"
            )

        # Update URLs assigned to this account as blocked
        for source_id in account.get("completed_source_ids", []):
            continue  # Skip already completed

        # Mark pending URLs for this account as blocked
        self.db_service.upsert_stage_status(
            source_id="placeholder",  # We need to track which URLs were assigned to this account
            stage="download",
            status="blocked",
            assigned_worker=f"Account_{account_idx+1}",
            metadata={
                "reason": "rate_limited",
                "cooldown_until": cooldown_end.isoformat(),
                "cooldown_minutes": cooldown_minutes,
            },
        )

        self._save_state()

    def _update_session_complete(
        self, account_idx: int, session: dict, downloaded_files: list[tuple[Path, str]]
    ) -> None:
        """
        Update state after session completes.

        Args:
            account_idx: Account index
            session: Session dict
            downloaded_files: Downloaded files with source_ids
        """
        account = self.state["accounts"][account_idx]

        # Mark session as complete
        session["status"] = "completed"
        session["downloads_completed"] = len(downloaded_files)
        session["completed_at"] = datetime.now().isoformat()

        # Move to next session
        account["next_session_idx"] += 1
        account["sessions_completed"] += 1

        # Update global state
        self.state["youtube_downloads_completed"] = self.state.get(
            "youtube_downloads_completed", 0
        ) + len(downloaded_files)

        self._save_state()

    def _get_remaining_urls(self) -> list[str]:
        """
        Get list of URLs that haven't been downloaded yet.

        Returns:
            List of remaining URLs
        """
        # Collect all completed source_ids
        completed_source_ids = set()
        for account in self.state.get("accounts", []):
            completed_source_ids.update(account.get("completed_source_ids", []))

        # Filter out completed URLs
        remaining = [
            url
            for url, source_id in self.urls_with_source_ids.items()
            if source_id not in completed_source_ids
        ]

        return remaining

    def _load_state(self) -> dict:
        """
        Load state from disk.

        Returns:
            State dict
        """
        if not self.state_file.exists():
            logger.info("No existing state file found, starting fresh")
            return {
                "total_urls": len(self.urls_with_source_ids),
                "youtube_downloads_completed": 0,
                "rss_downloads_completed": 0,
                "accounts": [],
            }

        try:
            with open(self.state_file) as f:
                state = json.load(f)
            logger.info(f"Loaded state from {self.state_file}")
            return state
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
            return {
                "total_urls": len(self.urls_with_source_ids),
                "youtube_downloads_completed": 0,
                "rss_downloads_completed": 0,
                "accounts": [],
            }

    def _save_state(self) -> None:
        """Save state to disk."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)

            # Write to temp file first (atomic write)
            temp_file = self.state_file.with_suffix(".tmp")
            with open(temp_file, "w") as f:
                json.dump(self.state, f, indent=2)

            # Rename to actual file (atomic on POSIX)
            temp_file.replace(self.state_file)

            logger.debug(f"Saved state to {self.state_file}")
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
