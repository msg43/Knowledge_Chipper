#!/usr/bin/env python3
"""
Smoke Test: Preflight Homebrew Detection

This test would have caught Bug #1: FFmpeg PATH issue that prevented app launch.

What it tests:
- FFmpeg detection when only in Homebrew (/opt/homebrew/bin or /usr/local/bin)
- Automatic PATH modification when FFmpeg found in Homebrew
- yt-dlp detection

Why it's important:
- macOS users often have Homebrew binaries not in their system PATH
- App must auto-detect and add Homebrew bin to PATH
- Preflight checks must run in production mode (no TESTING_MODE bypass)

Runtime: ~5 seconds
"""

import os
import shutil
import pytest


@pytest.mark.smoke
@pytest.mark.production
class TestPreflightHomebrewDetection:
    """Test preflight checks detect Homebrew-installed dependencies."""

    def test_ffmpeg_detected_in_homebrew_location(self):
        """Verify FFmpeg is detected even when not in PATH."""
        # This test validates the fix we made for the FFmpeg PATH bug

        # Save original PATH
        original_path = os.environ.get("PATH", "")
        original_testing_mode = os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE")

        try:
            # Remove TESTING_MODE to ensure preflight runs
            if "KNOWLEDGE_CHIPPER_TESTING_MODE" in os.environ:
                del os.environ["KNOWLEDGE_CHIPPER_TESTING_MODE"]

            # Remove Homebrew directories from PATH to simulate user environment
            # where FFmpeg is installed but not in PATH
            filtered_path = ":".join([
                p for p in original_path.split(":")
                if "/homebrew/bin" not in p.lower() and "/usr/local/bin" not in p
            ])
            os.environ["PATH"] = filtered_path

            # Import check_ffmpeg (this will trigger the detection logic)
            from knowledge_system.utils.preflight import check_ffmpeg

            # Check should succeed by detecting Homebrew location
            check_ffmpeg()  # Should not raise PreflightError

            # Verify that PATH was modified to include Homebrew
            current_path = os.environ.get("PATH", "")
            assert "/opt/homebrew/bin" in current_path or "/usr/local/bin" in current_path, \
                "FFmpeg detection should have added Homebrew bin to PATH"

        finally:
            # Restore original environment
            os.environ["PATH"] = original_path
            if original_testing_mode is not None:
                os.environ["KNOWLEDGE_CHIPPER_TESTING_MODE"] = original_testing_mode

    def test_ffmpeg_in_path_after_preflight(self):
        """Verify FFmpeg is available in PATH after preflight check."""
        original_testing_mode = os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE")

        try:
            # Remove TESTING_MODE
            if "KNOWLEDGE_CHIPPER_TESTING_MODE" in os.environ:
                del os.environ["KNOWLEDGE_CHIPPER_TESTING_MODE"]

            # Run preflight check
            from knowledge_system.utils.preflight import check_ffmpeg
            check_ffmpeg()

            # Verify FFmpeg is now in PATH
            ffmpeg_path = shutil.which("ffmpeg")
            assert ffmpeg_path is not None, "FFmpeg should be in PATH after preflight"
            assert os.path.exists(ffmpeg_path), f"FFmpeg path should exist: {ffmpeg_path}"

        finally:
            if original_testing_mode is not None:
                os.environ["KNOWLEDGE_CHIPPER_TESTING_MODE"] = original_testing_mode

    def test_yt_dlp_detected(self):
        """Verify yt-dlp is available in environment."""
        original_testing_mode = os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE")

        try:
            # Remove TESTING_MODE
            if "KNOWLEDGE_CHIPPER_TESTING_MODE" in os.environ:
                del os.environ["KNOWLEDGE_CHIPPER_TESTING_MODE"]

            # Run preflight check for yt-dlp
            from knowledge_system.utils.preflight import check_yt_dlp
            check_yt_dlp()  # Should not raise PreflightError

            # Verify yt-dlp is available
            yt_dlp_path = shutil.which("yt-dlp")
            assert yt_dlp_path is not None, "yt-dlp should be available"

        finally:
            if original_testing_mode is not None:
                os.environ["KNOWLEDGE_CHIPPER_TESTING_MODE"] = original_testing_mode

    def test_full_preflight_passes_in_production(self):
        """Verify all preflight checks pass in production mode."""
        original_testing_mode = os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE")

        try:
            # Remove TESTING_MODE to simulate production
            if "KNOWLEDGE_CHIPPER_TESTING_MODE" in os.environ:
                del os.environ["KNOWLEDGE_CHIPPER_TESTING_MODE"]

            # Run full preflight check
            from knowledge_system.utils.preflight import quick_preflight
            quick_preflight()  # Should not raise any errors

        finally:
            if original_testing_mode is not None:
                os.environ["KNOWLEDGE_CHIPPER_TESTING_MODE"] = original_testing_mode

    def test_homebrew_paths_exist(self):
        """Verify Homebrew installation paths exist (macOS-specific)."""
        import platform

        if platform.system() != "Darwin":  # macOS
            pytest.skip("Homebrew test only relevant on macOS")

        # Check if either Homebrew location exists
        homebrew_paths = [
            "/opt/homebrew/bin",      # Apple Silicon
            "/usr/local/bin",          # Intel Mac
        ]

        homebrew_exists = any(os.path.exists(p) for p in homebrew_paths)
        assert homebrew_exists, \
            f"At least one Homebrew path should exist on macOS: {homebrew_paths}"
