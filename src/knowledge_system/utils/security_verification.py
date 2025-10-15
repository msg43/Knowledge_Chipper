"""
Security and Authorization Verification for Skip the Podcast Desktop

This module verifies that the app has been properly authorized and that
bundled dependencies are accessible. Critical for preventing transcription
failures on remote machines.
"""

import os
import subprocess
import sys
from pathlib import Path

from knowledge_system.logger import get_logger

logger = get_logger(__name__)


class SecurityVerificationError(Exception):
    """Raised when security verification fails."""


class AuthorizationVerifier:
    """Verifies proper app authorization and dependency access."""

    def __init__(self):
        self.is_macos = sys.platform == "darwin"
        self.app_path = self._get_app_path()

    def _get_app_path(self) -> Path | None:
        """Get the path to the app bundle if we're running from one."""
        if not self.is_macos:
            return None

        try:
            exe_path = Path(sys.executable)
            current = exe_path

            # Walk up the directory tree looking for .app bundle
            while current.parent != current:
                if current.suffix == ".app":
                    return current
                current = current.parent

            return None
        except Exception as e:
            logger.debug(f"Could not determine app path: {e}")
            return None

    def check_authorization_status(self) -> tuple[bool, str]:
        """
        Check if the app has been properly authorized.

        Returns:
            Tuple of (is_authorized, status_message)
        """
        if not self.is_macos:
            return True, "Not macOS - authorization not required"

        if not self.app_path:
            return True, "Not running from app bundle - authorization not required"

        # Check for authorization marker
        auth_marker = Path.home() / ".skip_the_podcast_desktop_authorized"
        if auth_marker.exists():
            return True, "App properly authorized"

        # Check for clean install marker (legacy)
        clean_install_marker = Path.home() / ".skip_podcast_clean_install"
        if clean_install_marker.exists():
            return True, "App installed via clean installer"

        # Check if app still has quarantine attribute
        if self._has_quarantine_attribute():
            return False, "App still has quarantine attribute - authorization required"

        return False, "App authorization status unclear - may need reauthorization"

    def _has_quarantine_attribute(self) -> bool:
        """Check if the app bundle has quarantine attribute."""
        if not self.app_path:
            return False

        try:
            result = subprocess.run(
                ["xattr", "-p", "com.apple.quarantine", str(self.app_path)],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except Exception:
            return False

    def verify_bundled_dependencies(self) -> tuple[bool, list[str]]:
        """
        Verify that bundled dependencies are accessible.

        Returns:
            Tuple of (all_accessible, list_of_issues)
        """
        if not self.app_path:
            return True, []  # Not bundled, dependencies handled elsewhere

        issues = []
        macos_path = self.app_path / "Contents" / "MacOS"

        # Check Python executable
        python_path = macos_path / "venv" / "bin" / "python"
        if not self._check_executable_access(python_path):
            issues.append(f"Python executable not accessible: {python_path}")

        # Check FFmpeg binaries
        ffmpeg_bin_dir = (
            macos_path / "Library" / "Application Support" / "Knowledge_Chipper" / "bin"
        )
        if ffmpeg_bin_dir.exists():
            for binary in ["ffmpeg", "ffprobe"]:
                binary_path = ffmpeg_bin_dir / binary
                if binary_path.exists() and not self._check_executable_access(
                    binary_path
                ):
                    issues.append(f"FFmpeg binary not accessible: {binary_path}")

        # Check whisper.cpp binary
        whisper_path = macos_path / "bin" / "whisper"
        if whisper_path.exists() and not self._check_executable_access(whisper_path):
            issues.append(f"Whisper.cpp binary not accessible: {whisper_path}")

        # Check bundled models
        models_dir = macos_path / "models"
        if models_dir.exists():
            try:
                # Just try to list the directory
                list(models_dir.iterdir())
            except PermissionError:
                issues.append(f"Bundled models directory not accessible: {models_dir}")

        return len(issues) == 0, issues

    def _check_executable_access(self, path: Path) -> bool:
        """Check if an executable is accessible and can be run."""
        if not path.exists():
            return True  # Not bundled, handled elsewhere

        try:
            # Check if we can read the file
            with open(path, "rb") as f:
                f.read(1)

            # Check if it's executable
            if not os.access(path, os.X_OK):
                return False

            # For critical binaries, try a quick execution test
            if path.name == "python":
                result = subprocess.run(
                    [str(path), "--version"], capture_output=True, timeout=5
                )
                return result.returncode == 0
            elif path.name in ["ffmpeg", "ffprobe"]:
                result = subprocess.run(
                    [str(path), "-version"], capture_output=True, timeout=5
                )
                return result.returncode == 0
            elif path.name == "whisper":
                # Just check if we can execute it (will show help)
                result = subprocess.run([str(path)], capture_output=True, timeout=5)
                # whisper returns non-zero when no args, but should not crash
                return True

            return True
        except (PermissionError, FileNotFoundError, subprocess.TimeoutExpired) as e:
            logger.debug(f"Executable access check failed for {path}: {e}")
            return False
        except Exception as e:
            logger.warning(f"Unexpected error checking {path}: {e}")
            return True  # Don't fail on unexpected errors

    def get_comprehensive_status(self) -> dict[str, any]:
        """Get comprehensive security and dependency status."""
        is_authorized, auth_msg = self.check_authorization_status()
        deps_ok, dep_issues = self.verify_bundled_dependencies()

        return {
            "is_authorized": is_authorized,
            "authorization_message": auth_msg,
            "dependencies_accessible": deps_ok,
            "dependency_issues": dep_issues,
            "app_path": str(self.app_path) if self.app_path else None,
            "running_from_bundle": self.app_path is not None,
            "platform": sys.platform,
        }


def verify_app_security() -> tuple[bool, str]:
    """
    Quick verification that app is properly authorized for transcription.

    Returns:
        Tuple of (is_secure, error_message_if_not)
    """
    verifier = AuthorizationVerifier()

    # Check authorization
    is_authorized, auth_msg = verifier.check_authorization_status()
    if not is_authorized:
        return False, f"App not properly authorized: {auth_msg}"

    # Check dependencies
    deps_ok, dep_issues = verifier.verify_bundled_dependencies()
    if not deps_ok:
        issues_str = "; ".join(dep_issues[:3])  # Show first 3 issues
        return False, f"Bundled dependencies not accessible: {issues_str}"

    return True, "App properly authorized and dependencies accessible"


def log_security_status():
    """Log comprehensive security status for debugging."""
    verifier = AuthorizationVerifier()
    status = verifier.get_comprehensive_status()

    logger.info("=== Security Status ===")
    logger.info(f"Platform: {status['platform']}")
    logger.info(f"Running from bundle: {status['running_from_bundle']}")
    logger.info(f"App path: {status['app_path']}")
    logger.info(
        f"Authorized: {status['is_authorized']} - {status['authorization_message']}"
    )
    logger.info(f"Dependencies accessible: {status['dependencies_accessible']}")

    if status["dependency_issues"]:
        logger.warning("Dependency issues found:")
        for issue in status["dependency_issues"]:
            logger.warning(f"  - {issue}")

    logger.info("=== End Security Status ===")


def ensure_secure_before_transcription() -> None:
    """
    Ensure app is properly secured before attempting transcription.
    Raises SecurityVerificationError if not properly authorized.
    """
    is_secure, error_msg = verify_app_security()
    if not is_secure:
        logger.error(f"Security verification failed: {error_msg}")
        raise SecurityVerificationError(error_msg)

    logger.debug("Security verification passed - ready for transcription")
