#!/usr/bin/env python3
"""Silent FFMPEG installer for .dmg build process.

This is a standalone version of the FFmpegInstaller that can run during
the .dmg build process without requiring PyQt6 GUI components.
"""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FFmpegRelease:
    url: str
    sha256: str
    ffmpeg_name: str = "ffmpeg"
    ffprobe_name: str = "ffprobe"


def get_default_ffmpeg_release() -> FFmpegRelease:
    """Return an appropriate FFmpeg release for the current platform/arch."""
    system = platform.system().lower()

    if system == "darwin":
        # Evermeet.cx provides the latest FFmpeg release (currently 8.x)
        # This URL automatically serves the newest version available
        # Works for both Intel and Apple Silicon architectures
        return FFmpegRelease(
            url="https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip",
            sha256="",  # Skip checksum for trusted source with dynamic versions
            ffmpeg_name="ffmpeg",
            ffprobe_name="ffprobe",
        )

    # For non-macOS systems, would need different source
    raise NotImplementedError(f"FFmpeg installation not implemented for {system}")


class SilentFFmpegInstaller:
    """Silent FFMPEG installer for build processes."""

    def __init__(
        self,
        app_support_dir: Path | None = None,
        progress_callback: Callable[[str, int], None] | None = None,
    ):
        """Initialize silent installer.

        Args:
            app_support_dir: Custom app support directory. If None, uses default.
            progress_callback: Optional callback for progress updates (message, percentage)
        """
        self.app_support_dir = app_support_dir or (
            Path.home() / "Library" / "Application Support" / "Knowledge_Chipper"
        )
        self.bin_dir = self.app_support_dir / "bin"
        self.progress_callback = progress_callback or self._default_progress

    def _default_progress(self, message: str, percentage: int) -> None:
        """Default progress callback that prints to stdout."""
        print(f"[{percentage:3d}%] {message}")

    def _download(self, url: str, dest: Path) -> None:
        """Download a URL to dest with progress updates."""
        self.progress_callback("⬇️ Downloading FFmpeg…", 20)
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
                        self.progress_callback(
                            f"⬇️ Downloading FFmpeg… ({downloaded // (1024*1024)} MiB)",
                            min(pct, 50),
                        )
                        next_emit = pct + 5
                else:
                    if downloaded - next_emit >= 8 * 1024 * 1024:
                        self.progress_callback(
                            f"⬇️ Downloading FFmpeg… ({downloaded // (1024*1024)} MiB)",
                            30,
                        )
                        next_emit = downloaded

    def _sha256(self, path: Path) -> str:
        """Calculate SHA256 checksum of a file."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def install(self, release: FFmpegRelease | None = None) -> bool:
        """Install FFMPEG silently.

        Returns:
            True if installation successful, False otherwise
        """
        try:
            # Step 1: Setup directories (10%)
            self.progress_callback("📁 Setting up installation directories...", 10)
            self.app_support_dir.mkdir(parents=True, exist_ok=True)
            self.bin_dir.mkdir(parents=True, exist_ok=True)

            # Check if already installed
            ffmpeg_dst = self.bin_dir / "ffmpeg"
            if ffmpeg_dst.exists():
                try:
                    result = subprocess.run(
                        [str(ffmpeg_dst), "-version"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if result.returncode == 0:
                        self.progress_callback(
                            "✅ FFmpeg already installed and working", 100
                        )
                        return True
                except Exception:
                    pass  # Existing installation broken, continue with fresh install

            # Prepare candidate releases (primary + fallback)
            primary_release = release or get_default_ffmpeg_release()
            releases: list[FFmpegRelease] = [primary_release]

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
                if primary_release.url != evermeet.url:
                    releases.append(evermeet)

            last_error: Exception | None = None

            for idx, current_release in enumerate(releases):
                try:
                    with tempfile.TemporaryDirectory() as tmpdir:
                        # Step 2: Download (20-50%)
                        archive_name = (
                            Path(urllib.parse.urlparse(current_release.url).path).name
                            or "ffmpeg_download"
                        )
                        tmp_path = Path(tmpdir) / archive_name
                        phase = (
                            "⬇️ Downloading FFmpeg..."
                            if idx == 0
                            else "⬇️ Downloading FFmpeg (fallback source)..."
                        )
                        self.progress_callback(phase, 20)
                        self._download(current_release.url, tmp_path)

                        # Step 3: Verify (60%)
                        self.progress_callback("🔍 Verifying download integrity...", 60)
                        if current_release.sha256:
                            digest = self._sha256(tmp_path)
                            if digest.lower() != current_release.sha256.lower():
                                raise RuntimeError(
                                    "FFmpeg checksum verification failed"
                                )
                        else:
                            self.progress_callback(
                                "🔍 Using trusted source - skipping checksum", 60
                            )

                        # Step 4: Extract (70%)
                        self.progress_callback("📦 Extracting FFmpeg files...", 70)
                        extract_dir = Path(tmpdir) / "extract"
                        extract_dir.mkdir(parents=True, exist_ok=True)
                        try:
                            shutil.unpack_archive(str(tmp_path), str(extract_dir))
                        except Exception:
                            shutil.copy2(
                                tmp_path, extract_dir / current_release.ffmpeg_name
                            )

                        # Find ffmpeg and ffprobe in extracted content
                        ffmpeg_src: Path | None = None
                        ffprobe_src: Path | None = None
                        for p in extract_dir.rglob("*"):
                            if p.is_file():
                                if p.name == current_release.ffmpeg_name and os.access(
                                    p, os.X_OK
                                ):
                                    ffmpeg_src = p
                                elif (
                                    p.name == current_release.ffprobe_name
                                    and os.access(p, os.X_OK)
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
                                # Use 'file' command which is more reliable than lipo
                                file_result = subprocess.run(
                                    ["file", str(ffmpeg_src)],
                                    capture_output=True,
                                    text=True,
                                )
                                file_output = (file_result.stdout or "").strip().lower()

                                if machine == "arm64":
                                    if (
                                        "arm64" not in file_output
                                        and "aarch64" not in file_output
                                    ):
                                        if (
                                            "x86_64" in file_output
                                            or "i386" in file_output
                                        ):
                                            raise RuntimeError(
                                                "Incompatible architecture: x86_64-only candidate on arm64"
                                            )
                                        # If we can't determine arch, proceed with runtime validation
                                elif machine == "x86_64":
                                    if (
                                        "x86_64" not in file_output
                                        and "i386" not in file_output
                                    ):
                                        if (
                                            "arm64" in file_output
                                            or "aarch64" in file_output
                                        ):
                                            raise RuntimeError(
                                                "Incompatible architecture: arm64-only candidate on x86_64"
                                            )
                            except FileNotFoundError:
                                # 'file' command not available; rely on run-time validation below
                                pass

                        # Step 5: Install (80%)
                        self.progress_callback("🔧 Installing FFmpeg...", 80)
                        # Copy without metadata to avoid quarantine propagation or slow xattrs
                        self.progress_callback("📄 Copying binary...", 80)
                        with (
                            open(ffmpeg_src, "rb") as _src,
                            open(ffmpeg_dst, "wb") as _dst,
                        ):
                            shutil.copyfileobj(_src, _dst, length=1024 * 1024)
                        # Permissions
                        self.progress_callback("🔑 Setting permissions...", 82)
                        ffmpeg_dst.chmod(0o755)

                        if ffprobe_src:
                            ffprobe_dst = self.bin_dir / "ffprobe"
                            with (
                                open(ffprobe_src, "rb") as _src,
                                open(ffprobe_dst, "wb") as _dst,
                            ):
                                shutil.copyfileobj(_src, _dst, length=1024 * 1024)
                            ffprobe_dst.chmod(0o755)

                        # Step 6: Final setup (90%)
                        self.progress_callback(
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
                        self.progress_callback(
                            "✅ Validating FFmpeg installation...", 95
                        )
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
                        self.progress_callback(
                            "🎉 FFmpeg installation completed successfully!", 100
                        )
                        return True

                except Exception as e:  # Try next release
                    last_error = e
                    self.progress_callback(f"❌ Release {idx+1} failed: {str(e)}", 50)
                    if idx < len(releases) - 1:
                        self.progress_callback(
                            "↩️ Candidate failed, trying next source…", 60
                        )
                        continue
                    # All candidates failed
                    raise RuntimeError(
                        f"All FFMPEG sources failed. Last error: {str(e)}"
                    ) from last_error

        except Exception as e:
            self.progress_callback(f"❌ FFmpeg installation failed: {e}", 0)
            return False

        return False


def install_ffmpeg_for_dmg(app_bundle_path: Path, quiet: bool = False) -> bool:
    """Install FFMPEG into an app bundle during .dmg build.

    Args:
        app_bundle_path: Path to the .app bundle being built
        quiet: If True, suppress all output except errors

    Returns:
        True if installation successful, False otherwise
    """
    try:
        # Calculate paths for app bundle - use the standard macOS app structure
        contents_path = app_bundle_path / "Contents"
        macos_path = contents_path / "MacOS"

        # Create a local bin directory within the app bundle for FFMPEG
        # This mirrors the current user-space installation location but within the app
        app_support_path = (
            macos_path / "Library" / "Application Support" / "Knowledge_Chipper"
        )

        def progress_func(message: str, percentage: int) -> None:
            if not quiet:
                print(f"[FFMPEG] [{percentage:3d}%] {message}")

        installer = SilentFFmpegInstaller(
            app_support_dir=app_support_path, progress_callback=progress_func
        )

        success = installer.install()

        if success:
            if not quiet:
                print("✅ FFMPEG successfully installed in app bundle")
                print(f"   Location: {app_support_path / 'bin'}")

            # Create a simple script to help the app find the bundled FFMPEG
            bin_dir = app_support_path / "bin"
            if bin_dir.exists():
                setup_script = macos_path / "setup_bundled_ffmpeg.sh"
                with open(setup_script, "w") as f:
                    f.write("#!/bin/bash\n")
                    f.write("# Setup script to add bundled FFMPEG to PATH\n")
                    f.write("# Get the directory where this script is located\n")
                    f.write(
                        'APP_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"\n'
                    )
                    f.write(
                        'export FFMPEG_PATH="$APP_DIR/Library/Application Support/Knowledge_Chipper/bin/ffmpeg"\n'
                    )
                    f.write(
                        'export FFPROBE_PATH="$APP_DIR/Library/Application Support/Knowledge_Chipper/bin/ffprobe"\n'
                    )
                    f.write(
                        'export PATH="$APP_DIR/Library/Application Support/Knowledge_Chipper/bin:$PATH"\n'
                    )
                setup_script.chmod(0o755)

                if not quiet:
                    print(f"   Setup script: {setup_script}")
        else:
            print("❌ FFMPEG installation failed", file=sys.stderr)

        return success

    except Exception as e:
        print(f"❌ Error installing FFMPEG: {e}", file=sys.stderr)
        return False


def main() -> int:
    """CLI entry point for testing the silent installer."""
    import argparse

    parser = argparse.ArgumentParser(description="Silent FFMPEG installer for macOS")
    parser.add_argument(
        "--app-bundle",
        type=Path,
        help="Install FFMPEG into specified .app bundle (for .dmg build)",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Suppress output except errors"
    )
    parser.add_argument(
        "--test", action="store_true", help="Test installation to default user location"
    )

    args = parser.parse_args()

    if args.app_bundle:
        success = install_ffmpeg_for_dmg(args.app_bundle, args.quiet)
    elif args.test:
        installer = SilentFFmpegInstaller()
        success = installer.install()
    else:
        parser.print_help()
        return 1

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
