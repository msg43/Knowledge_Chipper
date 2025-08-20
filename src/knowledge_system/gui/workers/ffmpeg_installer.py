"""Worker to download, verify, and install a user-space FFmpeg for macOS."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from ...logger import get_logger

logger = get_logger(__name__)


APP_SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "Knowledge_Chipper"
BIN_DIR = APP_SUPPORT_DIR / "bin"


@dataclass
class FFmpegRelease:
    url: str
    sha256: str
    ffmpeg_name: str = "ffmpeg"
    ffprobe_name: str = "ffprobe"


# Default FFmpeg release for macOS ARM64
DEFAULT_FFMPEG_RELEASE = FFmpegRelease(
    url="https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip",
    sha256="",  # Will be skipped for evermeet releases
    ffmpeg_name="ffmpeg",
    ffprobe_name="ffprobe"
)


class FFmpegInstaller(QThread):
    """Background worker to install FFmpeg into user-space without sudo."""

    progress_updated = pyqtSignal(str, int)  # message, percentage
    installation_finished = pyqtSignal(bool, str)  # success, message
    progress = pyqtSignal(str)  # Legacy compatibility
    finished = pyqtSignal(bool, str, str)  # Legacy compatibility
    error = pyqtSignal(str)

    def __init__(self, release: FFmpegRelease | None = None) -> None:
        super().__init__()
        self.release = release or DEFAULT_FFMPEG_RELEASE

    def _download(self, url: str, dest: Path) -> None:
        self.progress.emit("Downloading FFmpeg…")
        with urllib.request.urlopen(url) as r, open(dest, "wb") as f:
            shutil.copyfileobj(r, f)

    def _sha256(self, path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def run(self) -> None:
        try:
            # Step 1: Setup directories (10%)
            self.progress_updated.emit("📁 Setting up installation directories...", 10)
            APP_SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
            BIN_DIR.mkdir(parents=True, exist_ok=True)

            with tempfile.TemporaryDirectory() as tmpdir:
                # Step 2: Download (20-50%)
                archive_name = (
                    Path(urllib.parse.urlparse(self.release.url).path).name
                    or "ffmpeg_download"
                )
                tmp_path = Path(tmpdir) / archive_name
                self.progress_updated.emit("⬇️ Downloading FFmpeg...", 20)
                self._download(self.release.url, tmp_path)

                # Step 3: Verify (60%)
                self.progress_updated.emit("🔍 Verifying download integrity...", 60)
                if self.release.sha256:  # Only verify if checksum is provided
                    digest = self._sha256(tmp_path)
                    if digest.lower() != self.release.sha256.lower():
                        raise RuntimeError("FFmpeg checksum verification failed")
                else:
                    # Skip verification for trusted sources like evermeet.cx
                    self.progress_updated.emit("🔍 Using trusted source - skipping checksum", 60)

                # Step 4: Extract (70%)
                self.progress_updated.emit("📦 Extracting FFmpeg files...", 70)
                # Try to extract known archive formats (.zip, .tar, .tar.gz, .tar.xz, etc.)
                extract_dir = Path(tmpdir) / "extract"
                extract_dir.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.unpack_archive(str(tmp_path), str(extract_dir))
                except Exception:
                    # Not a recognized archive - treat as raw binary
                    shutil.copy2(tmp_path, extract_dir / self.release.ffmpeg_name)

                # Find ffmpeg and ffprobe in extracted content
                ffmpeg_src: Path | None = None
                ffprobe_src: Path | None = None
                for p in extract_dir.rglob("*"):
                    if p.is_file():
                        if p.name == self.release.ffmpeg_name and os.access(p, os.X_OK):
                            ffmpeg_src = p
                        elif p.name == self.release.ffprobe_name and os.access(
                            p, os.X_OK
                        ):
                            ffprobe_src = p

                if not ffmpeg_src:
                    # Make binaries executable if necessary and select likely files
                    for p in extract_dir.rglob("ffmpeg"):
                        try:
                            p.chmod(0o755)
                            ffmpeg_src = p
                            break
                        except Exception:
                            pass

                if not ffmpeg_src:
                    raise RuntimeError("FFmpeg binary not found in archive")

                # Step 5: Install (80%)
                self.progress_updated.emit("🔧 Installing FFmpeg...", 80)
                ffmpeg_dst = BIN_DIR / "ffmpeg"
                shutil.copy2(ffmpeg_src, ffmpeg_dst)
                ffmpeg_dst.chmod(0o755)

                if ffprobe_src:
                    ffprobe_dst = BIN_DIR / "ffprobe"
                    shutil.copy2(ffprobe_src, ffprobe_dst)
                    ffprobe_dst.chmod(0o755)

                # Step 6: Final setup (90%)
                self.progress_updated.emit("🛡️ Configuring security permissions...", 90)
                try:
                    subprocess.run(
                        ["xattr", "-d", "com.apple.quarantine", str(ffmpeg_dst)],
                        check=False,
                    )
                except Exception:
                    pass

                # Step 7: Validate (95%)
                self.progress_updated.emit("✅ Validating FFmpeg installation...", 95)
                result = subprocess.run(
                    [str(ffmpeg_dst), "-version"], capture_output=True, text=True
                )
                if result.returncode != 0:
                    raise RuntimeError(f"FFmpeg validation failed: {result.stderr}")

                # Step 8: Complete (100%)
                self.progress_updated.emit("🎉 FFmpeg installation completed successfully!", 100)
                msg = f"FFmpeg installed successfully!\n\nEnabled features:\n• YouTube video downloads\n• Audio format conversions\n• Video file processing\n\nInstalled to: {BIN_DIR}"
                
                # Emit both new and legacy signals for compatibility
                self.installation_finished.emit(True, msg)
                self.finished.emit(True, "FFmpeg installed successfully", str(ffmpeg_dst))

        except Exception as e:
            error_msg = f"FFmpeg installation failed: {e}"
            logger.error(error_msg)
            
            # Emit both new and legacy signals for compatibility
            self.installation_finished.emit(False, error_msg)
            self.finished.emit(False, str(e), "")
