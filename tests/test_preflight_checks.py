#!/usr/bin/env python3
"""Test preflight checks without bypassing them.

These tests verify that the app's preflight checks work correctly
and catch common environment issues before the app tries to start.
"""

import os
import pytest


class TestPreflightChecks:
    """Test preflight checks that run before app startup."""

    def test_ffmpeg_check_passes(self):
        """Verify FFmpeg is available and passes preflight check."""
        # Temporarily clear testing mode to run actual preflight
        old_val = os.environ.pop("KNOWLEDGE_CHIPPER_TESTING_MODE", None)
        try:
            from knowledge_system.utils.preflight import check_ffmpeg

            # Should not raise
            check_ffmpeg()
        finally:
            if old_val:
                os.environ["KNOWLEDGE_CHIPPER_TESTING_MODE"] = old_val

    def test_yt_dlp_check_passes(self):
        """Verify yt-dlp is available and passes preflight check."""
        old_val = os.environ.pop("KNOWLEDGE_CHIPPER_TESTING_MODE", None)
        try:
            from knowledge_system.utils.preflight import check_yt_dlp

            # Should not raise
            check_yt_dlp()
        finally:
            if old_val:
                os.environ["KNOWLEDGE_CHIPPER_TESTING_MODE"] = old_val

    def test_full_preflight_passes(self):
        """Verify full preflight check suite passes."""
        old_val = os.environ.pop("KNOWLEDGE_CHIPPER_TESTING_MODE", None)
        try:
            from knowledge_system.utils.preflight import quick_preflight

            # Should not raise
            quick_preflight()
        finally:
            if old_val:
                os.environ["KNOWLEDGE_CHIPPER_TESTING_MODE"] = old_val

    def test_ffmpeg_in_path_or_homebrew(self):
        """Verify FFmpeg is either in PATH or in Homebrew locations."""
        import shutil

        ffmpeg_path = shutil.which("ffmpeg")

        if not ffmpeg_path:
            # Check Homebrew locations
            homebrew_paths = [
                "/opt/homebrew/bin/ffmpeg",  # Apple Silicon
                "/usr/local/bin/ffmpeg",  # Intel Mac
            ]
            for path in homebrew_paths:
                if os.path.exists(path):
                    ffmpeg_path = path
                    break

        assert (
            ffmpeg_path is not None
        ), "FFmpeg not found in PATH or Homebrew locations"
        assert os.path.exists(ffmpeg_path), f"FFmpeg path does not exist: {ffmpeg_path}"
        assert os.access(
            ffmpeg_path, os.X_OK
        ), f"FFmpeg is not executable: {ffmpeg_path}"
