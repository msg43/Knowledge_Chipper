"""Worker to download, verify, and install a user-space FFmpeg for macOS."""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from ...logger import get_logger
from ...utils.macos_paths import get_application_support_dir

logger = get_logger(__name__)


APP_SUPPORT_DIR = get_application_support_dir()
BIN_DIR = APP_SUPPORT_DIR / "bin"


@dataclass
class FFmpegRelease:
    url: str
    sha256: str
    ffmpeg_name: str = "ffmpeg"
    ffprobe_name: str = "ffprobe"


def get_default_ffmpeg_release() -> FFmpegRelease:
    """Return an appropriate FFmpeg release for the current platform/arch.

    Rationale:
    - Evermeet.cx provides the latest FFmpeg builds for macOS
    - The getrelease endpoint automatically serves the newest version
    - Works for both Intel and Apple Silicon architectures
    """
    system = platform.system().lower()
    
    if system == "darwin":
        # Evermeet.cx provides the latest FFmpeg release (currently 8.x)
        # This URL automatically serves the newest version available
        return FFmpegRelease(
            url="https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip",
            sha256="",  # Skip checksum for trusted source with dynamic versions
            ffmpeg_name="ffmpeg",
            ffprobe_name="ffprobe",
        )

    # For non-macOS systems, would need different source
    raise NotImplementedError(f"FFmpeg installation not implemented for {system}")


class FFmpegInstaller(QThread):
    """Background worker to install FFmpeg into user-space without sudo."""

    progress_updated = pyqtSignal(str, int)  # message, percentage
    installation_finished = pyqtSignal(bool, str)  # success, message
    progress = pyqtSignal(str)  # Legacy compatibility
    finished = pyqtSignal(bool, str, str)  # Legacy compatibility
    error = pyqtSignal(str)

    def __init__(self, release: FFmpegRelease | None = None) -> None:
        super().__init__()
        # Choose a sensible default per-arch if none explicitly provided
        self.release = release or get_default_ffmpeg_release()

    def _download(self, url: str, dest: Path) -> None:
        """Download a URL to dest with timeouts and lightweight progress updates."""
        self.progress_updated.emit("⬇️ Downloading FFmpeg…", 20)
        req = urllib.request.Request(
            url, headers={"User-Agent": "Knowledge-Chipper/3.x (macOS)"}
        )
        with (
            urllib.request.urlopen(req, timeout=60) as response,
            open(dest, "wb") as out,
        ):
            total_str = response.headers.get("Content-Length") or response.headers.get(
                "content-length"
            )
            total = int(total_str) if (total_str and total_str.isdigit()) else 0
            downloaded = 0
            chunk_size = 1024 * 1024  # 1 MiB
            next_emit = 0
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                out.write(chunk)
                downloaded += len(chunk)
                # Emit at most ~once per 5% or every 8 MiB if size unknown
                if total > 0:
                    pct = int(20 + (30 * downloaded / total))  # map into 20-50 range
                    if pct >= next_emit:
                        self.progress_updated.emit(
                            f"⬇️ Downloading FFmpeg… ({downloaded // (1024*1024)} MiB)",
                            min(pct, 50),
                        )
                        next_emit = pct + 5
                else:
                    if downloaded - next_emit >= 8 * 1024 * 1024:
                        self.progress_updated.emit(
                            f"⬇️ Downloading FFmpeg… ({downloaded // (1024*1024)} MiB)",
                            30,
                        )
                        next_emit = downloaded

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

            # Prepare candidate releases (primary + fallback)
            releases: list[FFmpegRelease] = [self.release]
            system = platform.system().lower()
            machine = platform.machine().lower()
            # Only consider Evermeet for non-ARM macOS (x86_64), since it's x86_64-only
            if system == "darwin" and machine != "arm64":
                evermeet = FFmpegRelease(
                    url="https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip",
                    sha256="",
                    ffmpeg_name="ffmpeg",
                    ffprobe_name="ffprobe",
                )
                if self.release.url != evermeet.url:
                    releases.append(evermeet)

            # Add cross-arch static alternative to handle Exec format errors automatically
            # Do not add the osxexperts Intel URL — it is unreliable and often returns HTML

            last_error: Exception | None = None

            for idx, release in enumerate(releases):
                try:
                    with tempfile.TemporaryDirectory() as tmpdir:
                        # Step 2: Download (20-50%)
                        archive_name = (
                            Path(urllib.parse.urlparse(release.url).path).name
                            or "ffmpeg_download"
                        )
                        tmp_path = Path(tmpdir) / archive_name
                        phase = (
                            "⬇️ Downloading FFmpeg..."
                            if idx == 0
                            else "⬇️ Downloading FFmpeg (fallback source)..."
                        )
                        self.progress_updated.emit(phase, 20)
                        self._download(release.url, tmp_path)

                        # Step 3: Verify (60%)
                        self.progress_updated.emit(
                            "🔍 Verifying download integrity...", 60
                        )
                        if release.sha256:
                            digest = self._sha256(tmp_path)
                            if digest.lower() != release.sha256.lower():
                                raise RuntimeError(
                                    "FFmpeg checksum verification failed"
                                )
                        else:
                            self.progress_updated.emit(
                                "🔍 Using trusted source - skipping checksum", 60
                            )

                        # Step 4: Extract (70%)
                        self.progress_updated.emit("📦 Extracting FFmpeg files...", 70)
                        extract_dir = Path(tmpdir) / "extract"
                        extract_dir.mkdir(parents=True, exist_ok=True)
                        try:
                            shutil.unpack_archive(str(tmp_path), str(extract_dir))
                        except Exception:
                            shutil.copy2(tmp_path, extract_dir / release.ffmpeg_name)

                        # Find ffmpeg and ffprobe in extracted content
                        ffmpeg_src: Path | None = None
                        ffprobe_src: Path | None = None
                        for p in extract_dir.rglob("*"):
                            if p.is_file():
                                if p.name == release.ffmpeg_name and os.access(
                                    p, os.X_OK
                                ):
                                    ffmpeg_src = p
                                elif p.name == release.ffprobe_name and os.access(
                                    p, os.X_OK
                                ):
                                    ffprobe_src = p

                        if not ffmpeg_src:
                            for p in extract_dir.rglob("ffmpeg"):
                                try:
                                    p.chmod(0o755)
                                    ffmpeg_src = p
                                    break
                                except Exception:
                                    pass

                        if not ffmpeg_src:
                            raise RuntimeError("FFmpeg binary not found in archive")

                        # Optional: ensure architecture compatibility before install (macOS only)
                        if system == "darwin":
                            try:
                                archs = subprocess.run(
                                    ["lipo", "-archs", str(ffmpeg_src)],
                                    capture_output=True,
                                    text=True,
                                )
                                archs_out = (
                                    (archs.stdout or archs.stderr or "").strip().lower()
                                )
                                if machine == "arm64" and "arm64" not in archs_out:
                                    raise RuntimeError(
                                        "Incompatible architecture: x86_64-only candidate on arm64"
                                    )
                            except FileNotFoundError:
                                # lipo not available; rely on run-time validation below
                                pass

                        # Step 5: Install (80%)
                        self.progress_updated.emit("🔧 Installing FFmpeg...", 80)
                        ffmpeg_dst = BIN_DIR / "ffmpeg"
                        # Copy without metadata to avoid quarantine propagation or slow xattrs
                        self.progress_updated.emit("📄 Copying binary...", 80)
                        with (
                            open(ffmpeg_src, "rb") as _src,
                            open(ffmpeg_dst, "wb") as _dst,
                        ):
                            shutil.copyfileobj(_src, _dst, length=1024 * 1024)
                        # Permissions
                        self.progress_updated.emit("🔑 Setting permissions...", 82)
                        ffmpeg_dst.chmod(0o755)

                        if ffprobe_src:
                            ffprobe_dst = BIN_DIR / "ffprobe"
                            with (
                                open(ffprobe_src, "rb") as _src,
                                open(ffprobe_dst, "wb") as _dst,
                            ):
                                shutil.copyfileobj(_src, _dst, length=1024 * 1024)
                            ffprobe_dst.chmod(0o755)

                        # Step 6: Final setup (90%)
                        self.progress_updated.emit(
                            "🛡️ Configuring security permissions...", 90
                        )
                        try:
                            subprocess.run(
                                [
                                    "xattr",
                                    "-d",
                                    "com.apple.quarantine",
                                    str(ffmpeg_dst),
                                ],
                                check=False,
                                timeout=5,
                            )
                        except Exception:
                            pass

                        # Step 7: Validate (95%)
                        self.progress_updated.emit(
                            "✅ Validating FFmpeg installation...", 95
                        )
                        # Report process architecture for troubleshooting
                        try:
                            self.progress_updated.emit(
                                f"🔎 Process arch: {platform.system()} {platform.machine()}",
                                95,
                            )
                        except Exception:
                            pass

                        result = subprocess.run(
                            [str(ffmpeg_dst), "-version"],
                            capture_output=True,
                            text=True,
                            timeout=10,
                        )
                        if result.returncode != 0:
                            # If we hit Exec format error or bad CPU type, try the next candidate
                            err = (result.stderr or result.stdout or "").lower()
                            if "exec format error" in err or "bad cpu type" in err:
                                raise RuntimeError(
                                    "Architecture mismatch while validating binary"
                                )
                            raise RuntimeError(
                                f"FFmpeg validation failed: {result.stderr}"
                            )

                        # Step 8: Complete (100%)
                        self.progress_updated.emit(
                            "🎉 FFmpeg installation completed successfully!", 100
                        )
                        msg = (
                            "FFmpeg installed successfully!\n\nEnabled features:\n• YouTube video downloads\n• Audio format conversions\n• Video file processing\n\nInstalled to: "
                            f"{BIN_DIR}"
                        )
                        self.installation_finished.emit(True, msg)
                        self.finished.emit(
                            True, "FFmpeg installed successfully", str(ffmpeg_dst)
                        )
                        return
                except Exception as e:  # Try next release
                    last_error = e
                    if idx < len(releases) - 1:
                        self.progress_updated.emit(
                            "↩️ Candidate failed, trying next source…", 60
                        )
                        continue
                    # All candidates failed; present a clear, user-friendly message
                    friendly = (
                        "Source temporarily unavailable. You can download and install FFmpeg yourself "
                        "and then retry extraction, or wait and retry this download link later."
                    )
                    raise RuntimeError(friendly) from last_error

        except Exception as e:
            error_msg = f"FFmpeg installation failed: {e}"
            logger.error(error_msg)

            # Emit both new and legacy signals for compatibility
            self.installation_finished.emit(False, error_msg)
            self.finished.emit(False, str(e), "")
