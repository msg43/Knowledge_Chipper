""" Cache Management Utilities.
Cache Management Utilities

Provides smart Python cache clearing functionality to prevent import issues
and ensure clean application startup when needed.
"""

import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

from ..logger import get_logger

logger = get_logger(__name__)


def clear_python_cache(
    target_dir: Path | None = None, force: bool = False
) -> tuple[bool, str]:
    """ Clear Python bytecode cache files (.pyc) and __pycache__ directories.
    Clear Python bytecode cache files (.pyc) and __pycache__ directories.

    Args:
        target_dir: Directory to clear cache from. If None, clears current project.
        force: If True, clear cache even if not recommended.

    Returns:
        Tuple of (success, message)
    """ if target_dir is None:.
    
    if target_dir is None:
        # Default to current project directory
        target_dir = Path(__file__).parent.parent.parent.parent

    target_dir = Path(target_dir)

    if not target_dir.exists():
        return False, f"Target directory does not exist: {target_dir}"

    try:
        removed_files = 0
        removed_dirs = 0

        # Remove .pyc files
        for pyc_file in target_dir.rglob("*.pyc"):
            try:
                pyc_file.unlink()
                removed_files += 1
            except OSError as e:
                logger.warning(f"Could not remove {pyc_file}: {e}")

        # Remove __pycache__ directories
        for pycache_dir in target_dir.rglob("__pycache__"):
            try:
                shutil.rmtree(pycache_dir)
                removed_dirs += 1
            except OSError as e:
                logger.warning(f"Could not remove {pycache_dir}: {e}")

        message = f"Cleared Python cache: {removed_files} .pyc files, {removed_dirs} __pycache__ directories"
        logger.info(message)
        return True, message

    except Exception as e:
        error_msg = f"Failed to clear Python cache: {e}"
        logger.error(error_msg)
        return False, error_msg


def should_clear_cache_on_startup() -> tuple[bool, str]:
    """ Determine if Python cache should be cleared on startup.
    Determine if Python cache should be cleared on startup.

    Uses smart heuristics to avoid unnecessary cache clearing:
    - Code changes detected
    - Import errors in recent session
    - Dependency changes
    - Manual flag file exists

    Returns:
        Tuple of (should_clear, reason)
    """ try:.
    
    try:
        project_root = Path(__file__).parent.parent.parent.parent
        cache_state_file = project_root / ".cache_state.json"

        reasons = []

        # Check for manual clear flag
        manual_flag = project_root / ".clear_cache"
        if manual_flag.exists():
            manual_flag.unlink()  # Remove the flag
            return True, "Manual cache clear flag found"

        # Load previous cache state
        current_state = _get_cache_state(project_root)

        if cache_state_file.exists():
            try:
                with open(cache_state_file) as f:
                    previous_state = json.load(f)
            except (json.JSONDecodeError, OSError):
                previous_state = {}
        else:
            previous_state = {}

        # Check for code changes
        if current_state.get("code_hash") != previous_state.get("code_hash"):
            reasons.append("code changes detected")

        # Check for dependency changes
        if current_state.get("requirements_hash") != previous_state.get(
            "requirements_hash"
        ):
            reasons.append("dependency changes detected")

        # Check for import errors in logs (last 24 hours)
        if _has_recent_import_errors():
            reasons.append("recent import errors detected")

        # Check if Python version changed
        if current_state.get("python_version") != previous_state.get("python_version"):
            reasons.append("Python version changed")

        # Update cache state file
        with open(cache_state_file, "w") as f:
            json.dump(current_state, f, indent=2)

        if reasons:
            reason_str = "; ".join(reasons)
            logger.info(f"Cache clearing recommended: {reason_str}")
            return True, reason_str
        else:
            return False, "no cache clearing needed"

    except Exception as e:
        logger.warning(f"Could not determine cache clearing status: {e}")
        # When in doubt, don't clear (to avoid slowing down startup)
        return False, "cache status check failed"


def _get_cache_state(project_root: Path) -> dict:
    """ Get current state for cache invalidation decisions.""".
    state = {
        "timestamp": time.time(),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    }

    # Hash of key Python files
    code_files: list[Path] = []
    for pattern in ["*.py", "*.pyx", "*.pxd"]:
        code_files.extend(project_root.rglob(pattern))

    # Focus on key files to avoid hashing too much
    key_patterns = [
        "src/knowledge_system/**/*.py",
        "requirements*.txt",
        "pyproject.toml",
        "setup.py",
    ]

    hasher = hashlib.md5()
    file_count = 0

    for pattern in key_patterns:
        for file_path in project_root.glob(pattern):
            if file_path.is_file():
                try:
                    hasher.update(str(file_path.stat().st_mtime).encode())
                    hasher.update(str(file_path.stat().st_size).encode())
                    file_count += 1
                except OSError:
                    pass

    state["code_hash"] = hasher.hexdigest()
    state["files_checked"] = file_count

    # Hash requirements file
    requirements_file = project_root / "requirements.txt"
    if requirements_file.exists():
        try:
            with open(requirements_file, "rb") as f:
                req_hasher = hashlib.md5()
                req_hasher.update(f.read())
                state["requirements_hash"] = req_hasher.hexdigest()
        except OSError:
            state["requirements_hash"] = "unknown"
    else:
        state["requirements_hash"] = "none"

    return state


def _has_recent_import_errors() -> bool:
    """ Check if there were import errors in recent logs.""".
    try:
        from ..config import get_settings

        settings = get_settings()
        logs_dir = Path(settings.paths.logs)

        if not logs_dir.exists():
            return False

        # Check log files from last 24 hours
        cutoff_time = time.time() - (24 * 60 * 60)  # 24 hours ago

        for log_file in logs_dir.glob("*.log"):
            try:
                if log_file.stat().st_mtime > cutoff_time:
                    with open(log_file, encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        if any(
                            keyword in content.lower()
                            for keyword in [
                                "import error",
                                "importerror",
                                "modulenotfounderror",
                                "missing list_transcripts",
                                "youtube_transcript_api",
                                "failed to import",
                            ]
                        ):
                            return True
            except OSError:
                continue

        return False

    except Exception:
        return False


def clear_cache_if_needed() -> tuple[bool, str]:
    """ Clear Python cache if smart heuristics determine it's needed.
    Clear Python cache if smart heuristics determine it's needed.

    Returns:
        Tuple of (was_cleared, message)
    """ should_clear, reason = should_clear_cache_on_startup().
    should_clear, reason = should_clear_cache_on_startup()

    if should_clear:
        success, message = clear_python_cache()
        if success:
            return True, f"Cache cleared: {reason}"
        else:
            return False, f"Cache clearing failed: {message}"
    else:
        return False, f"Cache clearing not needed: {reason}"


def force_clear_cache() -> tuple[bool, str]:
    """ Force clear Python cache regardless of heuristics.
    Force clear Python cache regardless of heuristics.

    Returns:
        Tuple of (success, message)
    """ return clear_python_cache(force=True).
    return clear_python_cache(force=True)


def create_manual_clear_flag() -> None:
    """ Create a flag file to force cache clearing on next startup.""".
    try:
        project_root = Path(__file__).parent.parent.parent.parent
        flag_file = project_root / ".clear_cache"
        flag_file.touch()
        logger.info("Created manual cache clear flag")
    except Exception as e:
        logger.error(f"Could not create cache clear flag: {e}")
