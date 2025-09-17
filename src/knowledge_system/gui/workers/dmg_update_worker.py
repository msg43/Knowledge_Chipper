"""DMG-based update worker for Knowledge Chipper."""

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.request import urlopen, urlretrieve

from PyQt6.QtCore import QThread, pyqtSignal

from ...__init__ import __version__
from ...logger import get_logger

logger = get_logger(__name__)


class DMGUpdateWorker(QThread):
    """Worker thread for handling DMG-based app updates."""

    # Signals
    update_progress = pyqtSignal(str)  # Status message
    update_progress_percent = pyqtSignal(int, str)  # Percent [0-100], message
    update_finished = pyqtSignal(bool, str, bool)  # Success, Message, Silent
    update_error = pyqtSignal(str)  # Error message

    def __init__(self, is_auto: bool = False) -> None:
        """Initialize the DMG update worker."""
        super().__init__()
        self.public_repo_url = (
            "https://api.github.com/repos/msg43/Skipthepodcast.com/releases/latest"
        )
        self.current_version = __version__
        self.is_auto = is_auto

    def _is_fresh_install(self) -> bool:
        """Check if this is a fresh installation that shouldn't auto-update."""
        import time
        from pathlib import Path

        # Check for markers that indicate this is a fresh install
        install_markers = [
            Path.home() / ".skip_the_podcast_desktop_installed",
            Path.home() / ".skip_the_podcast_desktop_authorized",
        ]

        # If any fresh install markers exist, this is a clean install
        for marker in install_markers:
            if marker.exists():
                logger.info(f"Fresh install detected: {marker}")
                return True

        # Additional check: if this is the EXACT same version, skip update
        # This prevents unnecessary "update" when someone just installed the current version
        try:
            latest_release = self._check_for_updates()
            if latest_release:
                new_version = latest_release["tag_name"].lstrip("v")
                if new_version == self.current_version:
                    logger.info(
                        f"Already on latest version {self.current_version} - skipping auto-update"
                    )
                    return True
        except Exception as e:
            logger.debug(f"Failed to check latest version: {e}")

        return False

    def run(self) -> None:
        """Run the DMG update process."""
        try:
            logger.info(
                f"Starting DMG update check from version {self.current_version}"
            )

            # Check if this is a fresh install - skip auto-updates for new installations
            if self.is_auto and self._is_fresh_install():
                logger.info("Skipping auto-update check for fresh installation")
                self.update_finished.emit(
                    True, "✅ Fresh installation - auto-update skipped", self.is_auto
                )
                return

            # Step 1: Check for updates
            self.update_progress.emit("🔍 Checking for updates...")
            self.update_progress_percent.emit(10, "Checking GitHub releases")

            latest_release = self._check_for_updates()
            if not latest_release:
                # Emit completion signal with silent flag for auto checks
                self.update_finished.emit(False, "No updates available", self.is_auto)
                return

            new_version = latest_release["tag_name"].lstrip("v")
            if not self._is_newer_version(new_version):
                # Emit success signal for "already on latest version" - this is not an error
                self.update_finished.emit(
                    True,
                    f"✅ Already on latest version ({self.current_version})",
                    self.is_auto,
                )
                return

            logger.info(f"Update available: {self.current_version} → {new_version}")

            # Step 2: Download DMG
            self.update_progress.emit(
                f"📥 Downloading Knowledge Chipper v{new_version}..."
            )
            self.update_progress_percent.emit(25, "Downloading update")

            dmg_url = self._get_dmg_download_url(latest_release)
            if not dmg_url:
                raise Exception("Could not find DMG download in release assets")

            dmg_path = self._download_dmg(dmg_url, new_version)

            # Step 3: Backup user data (minimal since data is in proper locations)
            self.update_progress.emit("💾 Preparing for installation...")
            self.update_progress_percent.emit(60, "Backing up settings")

            backup_info = self._prepare_update()

            # Step 4: Install DMG
            self.update_progress.emit("🔄 Installing update...")
            self.update_progress_percent.emit(80, "Installing new version")

            self._install_dmg(dmg_path)

            # Step 5: Complete installation
            self.update_progress.emit("✅ Finalizing installation...")
            self.update_progress_percent.emit(95, "Completing update")

            self._finalize_update(backup_info)

            # Step 6: Success
            self.update_progress_percent.emit(100, "Update complete")
            self.update_finished.emit(
                True,
                f"✅ Successfully updated to v{new_version}!\n\nThe app will restart automatically.",
                False,  # Success updates are never silent
            )

            # Schedule app restart
            self._schedule_restart()

        except Exception as e:
            logger.error(f"DMG update failed: {e}", exc_info=True)
            self.update_error.emit(f"Update failed: {str(e)}")

    def _check_for_updates(self) -> dict[str, Any] | None:
        """Check GitHub API for latest release."""
        try:
            with urlopen(self.public_repo_url, timeout=10) as response:
                if response.status != 200:
                    raise Exception(f"GitHub API returned status {response.status}")

                data = json.loads(response.read().decode())
                logger.info(f"Latest release: {data.get('tag_name', 'unknown')}")
                return data

        except Exception as e:
            logger.error(f"Failed to check for updates: {e}")
            raise Exception(f"Could not check for updates: {e}")

    def _is_newer_version(self, new_version: str) -> bool:
        """Check if new version is newer than current."""
        try:
            # Simple version comparison (assumes semantic versioning)
            def version_tuple(v: str) -> tuple:
                return tuple(map(int, v.split(".")))

            current_tuple = version_tuple(self.current_version)
            new_tuple = version_tuple(new_version)

            is_newer = new_tuple > current_tuple
            logger.info(
                f"Version comparison: {self.current_version} vs {new_version} -> newer: {is_newer}"
            )
            return is_newer

        except Exception as e:
            logger.warning(f"Version comparison failed: {e}, assuming update needed")
            return True

    def _get_dmg_download_url(self, release_data: dict[str, Any]) -> str | None:
        """Extract DMG download URL from release assets."""
        try:
            assets = release_data.get("assets", [])
            for asset in assets:
                if asset.get("name", "").endswith(".dmg"):
                    download_url = asset.get("browser_download_url")
                    logger.info(
                        f"Found DMG asset: {asset.get('name')} ({asset.get('size', 0)} bytes)"
                    )
                    return download_url

            logger.warning("No DMG asset found in release")
            return None

        except Exception as e:
            logger.error(f"Failed to find DMG download URL: {e}")
            return None

    def _download_dmg(self, download_url: str, version: str) -> Path:
        """Download the DMG file with progress tracking."""
        try:
            # Create temp directory for download
            temp_dir = Path(tempfile.mkdtemp(prefix="knowledge_chipper_update_"))
            dmg_filename = f"Skip_the_Podcast_Desktop-{version}.dmg"
            dmg_path = temp_dir / dmg_filename

            logger.info(f"Downloading DMG from: {download_url}")
            logger.info(f"Download destination: {dmg_path}")

            def progress_hook(block_num: int, block_size: int, total_size: int):
                if total_size > 0:
                    downloaded = block_num * block_size
                    percent = min(int((downloaded / total_size) * 100), 100)
                    mb_downloaded = downloaded / (1024 * 1024)
                    mb_total = total_size / (1024 * 1024)

                    # Update progress (25% base + 35% for download = 60% total)
                    progress_percent = 25 + int((percent * 35) / 100)
                    self.update_progress_percent.emit(
                        progress_percent,
                        f"Downloading: {mb_downloaded:.1f}/{mb_total:.1f} MB ({percent}%)",
                    )

            urlretrieve(download_url, dmg_path, reporthook=progress_hook)

            if not dmg_path.exists():
                raise Exception("Downloaded DMG file not found")

            file_size = dmg_path.stat().st_size
            logger.info(f"DMG downloaded successfully: {file_size} bytes")

            return dmg_path

        except Exception as e:
            logger.error(f"DMG download failed: {e}")
            raise Exception(f"Failed to download update: {e}")

    def _prepare_update(self) -> dict[str, Any]:
        """Prepare for update by creating minimal backup info."""
        try:
            # Since we're using proper macOS locations, we just need to track what's happening
            backup_info = {
                "timestamp": time.time(),
                "current_version": self.current_version,
                "app_path": "/Applications/Knowledge_Chipper.app",
                "backup_needed": False,  # Data is in proper locations, survives app replacement
            }

            logger.info("Update preparation complete - data in standard locations")
            return backup_info

        except Exception as e:
            logger.error(f"Update preparation failed: {e}")
            raise Exception(f"Failed to prepare for update: {e}")

    def _install_dmg(self, dmg_path: Path) -> None:
        """Install the new app from DMG."""
        try:
            logger.info(f"Installing DMG: {dmg_path}")

            # Mount the DMG and capture mount point from output
            mount_result = subprocess.run(
                [
                    "hdiutil",
                    "attach",
                    str(dmg_path),
                    "-nobrowse",
                    "-readonly",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if mount_result.returncode != 0:
                logger.error(
                    f"hdiutil attach failed with return code {mount_result.returncode}"
                )
                logger.error(f"stdout: {mount_result.stdout}")
                logger.error(f"stderr: {mount_result.stderr}")
                raise Exception(f"Failed to mount DMG: {mount_result.stderr}")

            # Parse mount point directly from hdiutil attach output
            mount_point = None
            logger.info(f"hdiutil attach output: {mount_result.stdout}")

            for line in mount_result.stdout.split("\n"):
                if "/Volumes/" in line:
                    # Extract mount point from output line
                    # Format: /dev/diskXsY          	Apple_HFS                 	/Volumes/Volume Name
                    parts = line.split("\t")
                    if len(parts) >= 3:
                        mount_path = parts[-1].strip()
                        if mount_path and Path(mount_path).exists():
                            mount_point = Path(mount_path)
                            logger.info(
                                f"Found mount point from hdiutil output: {mount_point}"
                            )
                            break

            # If we couldn't parse mount point from output, use fallback detection
            if not mount_point:
                logger.warning(
                    "Could not parse mount point from hdiutil output, using fallback detection"
                )
                mount_point = self._find_mount_point(dmg_path)

            if not mount_point:
                # Log additional debugging info
                logger.error("Mount point detection failed completely")
                logger.error(f"DMG path: {dmg_path}")
                logger.error(f"hdiutil attach stdout: {mount_result.stdout}")
                logger.error(f"hdiutil attach stderr: {mount_result.stderr}")

                # List all currently mounted volumes for debugging
                try:
                    volumes_result = subprocess.run(
                        ["ls", "-la", "/Volumes"], capture_output=True, text=True
                    )
                    logger.error(f"Current /Volumes contents: {volumes_result.stdout}")
                except Exception:
                    pass

                raise Exception(
                    "Could not determine DMG mount point - see logs for details"
                )

            logger.info(f"DMG mounted at: {mount_point}")

            try:
                # Find the app in the mounted DMG
                app_in_dmg = None
                for item in mount_point.iterdir():
                    if item.name.endswith(".app"):
                        app_in_dmg = item
                        break

                if not app_in_dmg:
                    raise Exception("No .app found in DMG")

                # Replace the existing app
                target_app = Path("/Applications/Knowledge_Chipper.app")

                # Remove old app if it exists
                if target_app.exists():
                    logger.info("Removing old app version")
                    shutil.rmtree(target_app)

                # Copy new app with selective copying for optional voice models
                logger.info(f"Installing new app: {app_in_dmg} → {target_app}")
                self._copy_app_with_fallbacks(app_in_dmg, target_app)

                # Set proper permissions
                os.chmod(target_app, 0o755)

                logger.info("App installation complete")

            finally:
                # Always unmount the DMG
                subprocess.run(
                    ["hdiutil", "detach", str(mount_point)],
                    capture_output=True,
                    timeout=30,
                )

                # Clean up downloaded DMG
                dmg_path.unlink(missing_ok=True)
                dmg_path.parent.rmdir()

        except Exception as e:
            logger.error(f"DMG installation failed: {e}")
            raise Exception(f"Failed to install update: {e}")

    def _find_mount_point(self, dmg_path: Path) -> Path | None:
        """Find where the DMG was mounted."""
        try:
            logger.info(f"Looking for mount point for DMG: {dmg_path}")

            # Method 1: Parse hdiutil attach output directly (most reliable)
            # Re-run hdiutil attach to get the mount point info
            attach_result = subprocess.run(
                ["hdiutil", "info", "-plist"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if attach_result.returncode == 0:
                try:
                    import plistlib

                    plist_data = plistlib.loads(attach_result.stdout.encode())

                    # Look through mounted images
                    for image in plist_data.get("images", []):
                        image_path = image.get("image-path", "")
                        if str(dmg_path) in image_path:
                            # Find mount point from system entities
                            for entity in image.get("system-entities", []):
                                mount_point = entity.get("mount-point")
                                if mount_point and Path(mount_point).exists():
                                    logger.info(
                                        f"Found mount point via plist: {mount_point}"
                                    )
                                    return Path(mount_point)
                except Exception as e:
                    logger.warning(f"Failed to parse hdiutil plist output: {e}")

            # Method 2: Use mount command to find all mounted volumes
            mount_result = subprocess.run(
                ["mount"], capture_output=True, text=True, timeout=10
            )

            if mount_result.returncode == 0:
                for line in mount_result.stdout.split("\n"):
                    if "/Volumes/" in line and (
                        "Skip" in line or "Podcast" in line or "Knowledge" in line
                    ):
                        # Extract mount point from mount output
                        # Format: /dev/diskXsY on /Volumes/VolumeName (hfs, local, nodev, nosuid, read-only, noowners, quarantine, mounted by uid=501)
                        parts = line.split(" on ")
                        if len(parts) >= 2:
                            mount_info = parts[1].split(" (")[0]
                            mount_path = Path(mount_info)
                            if mount_path.exists():
                                logger.info(
                                    f"Found mount point via mount command: {mount_path}"
                                )
                                return mount_path

            # Method 3: Check common mount point patterns
            common_mount_points = [
                "/Volumes/Skip the Podcast Desktop",
                "/Volumes/Knowledge Chipper",
                "/Volumes/Skip_the_Podcast_Desktop",
                "/Volumes/Knowledge_Chipper",
            ]

            for mount_point in common_mount_points:
                mount_path = Path(mount_point)
                if mount_path.exists():
                    logger.info(f"Found mount point via common patterns: {mount_path}")
                    return mount_path

            # Method 4: List all /Volumes and find the most recent one that looks relevant
            volumes_dir = Path("/Volumes")
            if volumes_dir.exists():
                for volume in volumes_dir.iterdir():
                    if volume.is_dir() and any(
                        keyword in volume.name.lower()
                        for keyword in ["skip", "podcast", "knowledge", "chipper"]
                    ):
                        logger.info(f"Found mount point via volume scan: {volume}")
                        return volume

            logger.error("Could not find mount point using any method")
            return None

        except Exception as e:
            logger.error(f"Failed to find mount point: {e}")
            return None

    def _finalize_update(self, backup_info: dict[str, Any]) -> None:
        """Finalize the update process."""
        try:
            logger.info("Finalizing update installation")

            # Since data is in proper macOS locations, no restoration needed
            # Just verify the new app exists
            target_app = Path("/Applications/Knowledge_Chipper.app")
            if not target_app.exists():
                raise Exception("New app installation not found")

            logger.info("Update finalization complete")

        except Exception as e:
            logger.error(f"Update finalization failed: {e}")
            raise Exception(f"Failed to finalize update: {e}")

    def _copy_app_with_fallbacks(self, source_app: Path, target_app: Path) -> None:
        """Copy app bundle with fallbacks for missing voice model files."""
        try:
            # First, try standard copytree
            shutil.copytree(source_app, target_app)
            logger.info("App copied successfully with all bundled files")
        except Exception as e:
            logger.warning(f"Standard copy failed, attempting selective copy: {e}")

            # Fallback: copy with error handling for individual files
            try:
                # Create target structure
                target_app.mkdir(parents=True, exist_ok=True)

                # Copy recursively with error handling
                self._copy_directory_selective(source_app, target_app)
                logger.info("App copied successfully with selective file copying")

            except Exception as e2:
                logger.error(f"Selective copy also failed: {e2}")
                raise Exception(f"Failed to copy app bundle: {e2}")

    def _copy_directory_selective(self, source: Path, target: Path) -> None:
        """Copy directory contents selectively, skipping problematic files."""
        for item in source.iterdir():
            source_item = source / item.name
            target_item = target / item.name

            try:
                if item.is_dir():
                    # Create directory and recurse
                    target_item.mkdir(exist_ok=True)
                    self._copy_directory_selective(source_item, target_item)
                else:
                    # Copy file
                    shutil.copy2(source_item, target_item)

            except Exception as e:
                # Handle specific error types and decide whether to skip or fail
                error_msg = str(e).lower()
                file_path_str = str(source_item).lower()

                # Skip these types of files/errors safely
                skip_patterns = [
                    "voice_models",
                    "speechbrain",
                    "ollama_auto_install.json",
                    ".config",
                    "operation not permitted",
                    "permission denied",
                    "access denied",
                ]

                should_skip = any(
                    pattern in file_path_str or pattern in error_msg
                    for pattern in skip_patterns
                )

                if should_skip:
                    logger.warning(
                        f"Skipping file due to permissions/optional content: {source_item} ({e})"
                    )
                else:
                    logger.error(f"Failed to copy essential file: {source_item} ({e})")
                    raise

    def _schedule_restart(self) -> None:
        """Schedule the app to restart after update."""
        try:
            # The GUI will handle the restart when it receives the update_finished signal
            logger.info("Update complete - restart will be handled by GUI")

        except Exception as e:
            logger.error(f"Failed to schedule restart: {e}")
            # Non-critical error, don't fail the update
