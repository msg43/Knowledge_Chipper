""" Worker to download, verify, and install a user-space FFmpeg for macOS.""".

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import urllib.request
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


class FFmpegInstaller(QThread):
    """ Background worker to install FFmpeg into user-space without sudo.""".

    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str, str)  # success, message, installed_path
    error = pyqtSignal(str)

    def __init__(self, release: FFmpegRelease) -> None:
        super().__init__()
        self.release = release

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
            APP_SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
            BIN_DIR.mkdir(parents=True, exist_ok=True)

            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir) / "ffmpeg.tar.xz"
                self._download(self.release.url, tmp_path)

                self.progress.emit("Verifying download…")
                digest = self._sha256(tmp_path)
                if digest.lower() != self.release.sha256.lower():
                    raise RuntimeError("FFmpeg checksum verification failed")

                self.progress.emit("Extracting…")
                # Try to extract tarballs; if a single binary was provided, just copy
                extract_dir = Path(tmpdir) / "extract"
                extract_dir.mkdir(parents=True, exist_ok=True)
                try:
                    subprocess.run(["tar", "-xf", str(tmp_path), "-C", str(extract_dir)], check=True)
                except Exception:
                    # Not a tarball - treat as raw binary
                    shutil.copy2(tmp_path, extract_dir / self.release.ffmpeg_name)

                # Find ffmpeg and ffprobe in extracted content
                ffmpeg_src: Optional[Path] = None
                ffprobe_src: Optional[Path] = None
                for p in extract_dir.rglob("*"):
                    if p.is_file():
                        if p.name == self.release.ffmpeg_name and os.access(p, os.X_OK):
                            ffmpeg_src = p
                        elif p.name == self.release.ffprobe_name and os.access(p, os.X_OK):
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

                # Install into BIN_DIR
                ffmpeg_dst = BIN_DIR / "ffmpeg"
                shutil.copy2(ffmpeg_src, ffmpeg_dst)
                ffmpeg_dst.chmod(0o755)

                if ffprobe_src:
                    ffprobe_dst = BIN_DIR / "ffprobe"
                    shutil.copy2(ffprobe_src, ffprobe_dst)
                    ffprobe_dst.chmod(0o755)

                # Remove quarantine if present
                try:
                    subprocess.run(["xattr", "-d", "com.apple.quarantine", str(ffmpeg_dst)], check=False)
                except Exception:
                    pass

                # Validate
                self.progress.emit("Validating installation…")
                result = subprocess.run([str(ffmpeg_dst), "-version"], capture_output=True, text=True)
                if result.returncode != 0:
                    raise RuntimeError(f"FFmpeg validation failed: {result.stderr}")

                self.finished.emit(True, "FFmpeg installed successfully", str(ffmpeg_dst))
        except Exception as e:
            logger.error(f"FFmpeg installation failed: {e}")
            self.finished.emit(False, str(e), "")


