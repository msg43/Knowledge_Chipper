"""
Auto-update checker for GetReceipts Daemon.

Checks GitHub releases for new daemon versions and handles automatic updates.
- Checks every 24 hours
- Checks on daemon startup
- Downloads and installs updates automatically
- LaunchAgent handles daemon restart
"""

import asyncio
import hashlib
import json
import logging
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.request import urlopen, urlretrieve

logger = logging.getLogger(__name__)

# Configuration
GITHUB_API_URL = "https://api.github.com/repos/msg43/Knowledge_Chipper/releases/latest"
CHECK_INTERVAL_HOURS = 24  # Check every 24 hours
INSTALL_DIR = Path("/Users/Shared/GetReceipts")
BINARY_NAME = "GetReceiptsDaemon"


class DaemonUpdateChecker:
    """Handles daemon auto-update checks and installations."""
    
    def __init__(self, current_version: str):
        """
        Initialize update checker.
        
        Args:
            current_version: Current daemon version (e.g., "1.0.0")
        """
        self.current_version = current_version
        self.last_check: Optional[datetime] = None
        self.update_available = False
        self.latest_version: Optional[str] = None
        self._checking = False
        
    async def check_for_updates(self) -> tuple[bool, Optional[str]]:
        """
        Check GitHub API for daemon updates.
        
        Returns:
            (update_available, latest_version)
        """
        if self._checking:
            logger.debug("Update check already in progress")
            return self.update_available, self.latest_version
            
        self._checking = True
        
        try:
            logger.info(f"Checking for daemon updates (current: {self.current_version})")
            
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, self._fetch_latest_release)
            
            if not data:
                return False, None
            
            latest_tag = data.get("tag_name", "").lstrip("v")
            self.latest_version = latest_tag
            self.last_check = datetime.now()
            
            if self._is_newer_version(latest_tag):
                logger.info(f"Update available: {self.current_version} → {latest_tag}")
                self.update_available = True
                return True, latest_tag
            else:
                logger.info(f"Already on latest version: {self.current_version}")
                self.update_available = False
                return False, None
                
        except Exception as e:
            logger.error(f"Failed to check for updates: {e}")
            return False, None
        finally:
            self._checking = False
    
    def _fetch_latest_release(self) -> Optional[dict]:
        """Fetch latest release data from GitHub API (synchronous)."""
        try:
            with urlopen(GITHUB_API_URL, timeout=10) as response:
                if response.status != 200:
                    logger.error(f"GitHub API returned {response.status}")
                    return None
                    
                return json.loads(response.read().decode())
        except Exception as e:
            logger.error(f"Failed to fetch latest release: {e}")
            return None
    
    def _is_newer_version(self, new_version: str) -> bool:
        """
        Compare semantic versions.
        
        Args:
            new_version: Version string to compare (e.g., "1.0.1")
            
        Returns:
            True if new_version is newer than current_version
        """
        try:
            def version_tuple(v: str) -> tuple:
                # Handle versions like "1.0.0" or "1.0.0-beta"
                base_version = v.split("-")[0]
                return tuple(map(int, base_version.split(".")))
            
            current = version_tuple(self.current_version)
            new = version_tuple(new_version)
            
            return new > current
        except Exception as e:
            logger.warning(f"Version comparison failed: {e}")
            return False
    
    async def download_and_install_update(self) -> bool:
        """
        Download new daemon binary and install it.
        
        Process:
        1. Download daemon binary from GitHub release
        2. Verify download integrity
        3. Backup current binary
        4. Install new binary
        5. Create update marker for verification
        
        The LaunchAgent will automatically restart the daemon after installation.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.latest_version:
                logger.error("No latest version available")
                return False
            
            logger.info(f"Starting update installation to version {self.latest_version}")
            
            # Run download and install in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(None, self._install_update_sync)
            
            return success
            
        except Exception as e:
            logger.error(f"Update installation failed: {e}", exc_info=True)
            return False
    
    def _install_update_sync(self) -> bool:
        """Synchronous update installation (runs in thread pool)."""
        try:
            # Step 1: Find daemon binary in release assets
            data = self._fetch_latest_release()
            if not data:
                logger.error("Could not fetch release data")
                return False
            
            daemon_asset = None
            for asset in data.get("assets", []):
                name_lower = asset["name"].lower()
                if "daemon" in name_lower and (name_lower.endswith(".tar.gz") or name_lower.endswith(".zip")):
                    daemon_asset = asset
                    logger.info(f"Found daemon asset: {asset['name']}")
                    break
            
            if not daemon_asset:
                logger.error("No daemon binary found in release assets")
                logger.info(f"Available assets: {[a['name'] for a in data.get('assets', [])]}")
                return False
            
            download_url = daemon_asset["browser_download_url"]
            expected_size = daemon_asset["size"]
            
            logger.info(f"Downloading daemon from: {download_url}")
            
            # Step 2: Download to temp directory
            temp_dir = Path(tempfile.mkdtemp(prefix="daemon_update_"))
            archive_path = temp_dir / daemon_asset["name"]
            
            try:
                urlretrieve(download_url, archive_path)
            except Exception as e:
                logger.error(f"Download failed: {e}")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return False
            
            # Step 3: Verify download
            actual_size = archive_path.stat().st_size
            if actual_size != expected_size:
                logger.error(f"Download size mismatch: expected {expected_size}, got {actual_size}")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return False
            
            logger.info(f"Download verified ({actual_size} bytes)")
            
            # Step 4: Extract binary
            try:
                if archive_path.suffix == ".gz" or archive_path.name.endswith(".tar.gz"):
                    import tarfile
                    with tarfile.open(archive_path, "r:gz") as tar:
                        tar.extractall(temp_dir)
                else:
                    import zipfile
                    with zipfile.ZipFile(archive_path, "r") as zip_file:
                        zip_file.extractall(temp_dir)
            except Exception as e:
                logger.error(f"Extraction failed: {e}")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return False
            
            # Step 5: Find extracted binary
            new_binary = temp_dir / BINARY_NAME
            if not new_binary.exists():
                # Check subdirectories
                for item in temp_dir.rglob(BINARY_NAME):
                    if item.is_file() and os.access(item, os.X_OK):
                        new_binary = item
                        logger.info(f"Found binary at: {new_binary}")
                        break
            
            if not new_binary.exists():
                logger.error(f"Could not find {BINARY_NAME} in extracted files")
                logger.info(f"Contents of temp_dir: {list(temp_dir.rglob('*'))}")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return False
            
            # Step 6: Backup current binary
            current_binary = INSTALL_DIR / BINARY_NAME
            backup_binary = INSTALL_DIR / f"{BINARY_NAME}.backup"
            
            if current_binary.exists():
                try:
                    shutil.copy2(current_binary, backup_binary)
                    logger.info(f"Backed up current binary to {backup_binary}")
                except Exception as e:
                    logger.warning(f"Failed to backup current binary: {e}")
            
            # Step 7: Install new binary
            try:
                shutil.copy2(new_binary, current_binary)
                os.chmod(current_binary, 0o755)
                logger.info(f"Installed new daemon binary: {current_binary}")
            except Exception as e:
                logger.error(f"Failed to install new binary: {e}")
                # Try to restore backup
                if backup_binary.exists():
                    try:
                        shutil.copy2(backup_binary, current_binary)
                        logger.info("Restored backup binary")
                    except Exception as restore_error:
                        logger.error(f"Failed to restore backup: {restore_error}")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return False
            
            # Step 8: Create update marker for verification after restart
            marker_file = INSTALL_DIR / ".update_completed"
            try:
                marker_data = {
                    "version": self.latest_version,
                    "timestamp": datetime.now().isoformat(),
                    "previous_version": self.current_version
                }
                marker_file.write_text(json.dumps(marker_data, indent=2))
                logger.info("Created update marker")
            except Exception as e:
                logger.warning(f"Failed to create update marker: {e}")
            
            # Step 9: Cleanup
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            logger.info(f"Update to version {self.latest_version} installed successfully")
            logger.info("Daemon will restart automatically via LaunchAgent")
            return True
            
        except Exception as e:
            logger.error(f"Update installation error: {e}", exc_info=True)
            return False
    
    async def perform_update_if_available(self) -> bool:
        """
        Check for updates and install if available.
        
        Returns:
            True if update was installed, False otherwise
        """
        has_update, version = await self.check_for_updates()
        
        if has_update:
            logger.info(f"Installing update to version {version}")
            success = await self.download_and_install_update()
            
            if success:
                logger.info("Update installed successfully - daemon will restart")
                return True
            else:
                logger.error("Update installation failed")
                return False
        
        return False


class UpdateScheduler:
    """Schedules periodic update checks."""
    
    def __init__(self, checker: DaemonUpdateChecker):
        """
        Initialize update scheduler.
        
        Args:
            checker: DaemonUpdateChecker instance
        """
        self.checker = checker
        self.task: Optional[asyncio.Task] = None
        self.running = False
    
    async def start(self):
        """Start the update check scheduler."""
        if self.running:
            logger.warning("Update scheduler already running")
            return
            
        self.running = True
        self.task = asyncio.create_task(self._check_loop())
        logger.info(f"Update scheduler started (checks every {CHECK_INTERVAL_HOURS} hours)")
    
    async def stop(self):
        """Stop the update check scheduler."""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None
        logger.info("Update scheduler stopped")
    
    async def _check_loop(self):
        """Periodic update check loop."""
        # Initial check on startup (after 5 minute delay to avoid startup issues)
        logger.info("Scheduling initial update check in 5 minutes...")
        await asyncio.sleep(300)  # 5 minutes
        
        while self.running:
            try:
                logger.info("Running scheduled update check...")
                needs_restart = await self.checker.perform_update_if_available()
                
                if needs_restart:
                    # Exit daemon - LaunchAgent will restart it with new version
                    logger.info("Update installed - exiting for restart")
                    await asyncio.sleep(2)  # Brief delay for log flush
                    os._exit(0)  # Clean exit
                    
            except Exception as e:
                logger.error(f"Update check failed: {e}", exc_info=True)
            
            # Wait for next check interval
            logger.debug(f"Next update check in {CHECK_INTERVAL_HOURS} hours")
            await asyncio.sleep(CHECK_INTERVAL_HOURS * 3600)


# Global instance
_update_checker: Optional[DaemonUpdateChecker] = None
_update_scheduler: Optional[UpdateScheduler] = None


def get_update_checker(version: str) -> DaemonUpdateChecker:
    """Get or create global update checker instance."""
    global _update_checker
    if _update_checker is None:
        _update_checker = DaemonUpdateChecker(version)
    return _update_checker


def get_update_scheduler(version: str) -> UpdateScheduler:
    """Get or create global update scheduler instance."""
    global _update_scheduler
    if _update_scheduler is None:
        checker = get_update_checker(version)
        _update_scheduler = UpdateScheduler(checker)
    return _update_scheduler

