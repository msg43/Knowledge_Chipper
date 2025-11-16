"""Lightweight runtime preflight checks.

These checks are intentionally fast (<200ms typical) and avoid any heavy
imports, network calls, or GPU/ML initialization. They are meant to catch the
most common "app starts but immediately crashes" issues on end-user machines.

Set SKIP_PREFLIGHT=1 to skip these checks in tests.
Legacy support: KC_SKIP_PREFLIGHT=1 or KNOWLEDGE_CHIPPER_TESTING_MODE=1 also work.
"""

from __future__ import annotations

import os
import shutil
import subprocess

# Import granular testing mode functions
try:
    from knowledge_system.utils.testing_mode import should_skip_preflight
except ImportError:
    # Fallback if testing_mode module is not available yet
    def should_skip_preflight() -> bool:
        return (
            os.environ.get("KC_SKIP_PREFLIGHT") == "1" or
            os.environ.get("SKIP_PREFLIGHT") == "1" or
            os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE") == "1"
        )


class PreflightError(RuntimeError):
    """Raised when a preflight check fails."""


def _run(cmd: list[str]) -> tuple[int, str, str]:
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    out, err = proc.communicate(timeout=5)
    return proc.returncode, out.strip(), err.strip()


def check_ffmpeg() -> None:
    """Verify ffmpeg is available on PATH and runnable."""
    ffmpeg_path = shutil.which("ffmpeg")

    # If not in PATH, check common Homebrew locations
    if not ffmpeg_path:
        homebrew_paths = [
            "/opt/homebrew/bin/ffmpeg",  # Apple Silicon
            "/usr/local/bin/ffmpeg",      # Intel Mac
        ]
        for path in homebrew_paths:
            if os.path.exists(path):
                ffmpeg_path = path
                # Add Homebrew bin to PATH for this session
                homebrew_bin = os.path.dirname(path)
                if homebrew_bin not in os.environ.get("PATH", ""):
                    os.environ["PATH"] = f"{homebrew_bin}:{os.environ.get('PATH', '')}"
                break

    if not ffmpeg_path:
        raise PreflightError(
            "FFmpeg not found. Install with: brew install ffmpeg, then relaunch."
        )

    code, _, err = _run([ffmpeg_path, "-version"])
    if code != 0:
        raise PreflightError(
            f"FFmpeg present but not runnable: {err or 'unknown error'}"
        )


def check_yt_dlp() -> None:
    """Verify yt_dlp is importable (no network)."""
    try:
        import yt_dlp  # noqa: F401
    except Exception as exc:  # pragma: no cover - environment specific
        raise PreflightError(
            "yt-dlp not installed. Install with: pip install yt-dlp"
        ) from exc


def quick_preflight() -> None:
    """Run minimal, fast checks. Raises PreflightError on problems."""
    # Skip preflight checks if configured
    # Uses granular testing mode controls (SKIP_PREFLIGHT=1)
    # Also supports legacy environment variables for backward compatibility
    if should_skip_preflight():
        return

    check_ffmpeg()
    check_yt_dlp()
