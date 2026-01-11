"""
Knowledge_Chipper - A comprehensive knowledge management system for macOS.

This package provides AI-powered tools for transcribing, summarizing, and organizing
videos, audio files, and documents into searchable knowledge.
"""

from __future__ import annotations

import re
import warnings
from importlib import metadata
from pathlib import Path

# Suppress common ML/audio library warnings early in application startup
# Import warning suppressions utility to handle PyTorch/TorchAudio/PyAnnote deprecations
try:
    from .utils.warning_suppressions import suppress_ml_library_warnings

    suppress_ml_library_warnings()
except ImportError:
    # Fallback to direct warning suppressions if utility import fails
    warnings.filterwarnings(
        "ignore", category=UserWarning, module="torchaudio._backend.utils"
    )
    warnings.filterwarnings(
        "ignore", category=UserWarning, module="pyannote.audio.models.blocks.pooling"
    )
    warnings.filterwarnings(
        "ignore", message=".*std\\(\\): degrees of freedom.*", category=UserWarning
    )
    # Suppress SyntaxWarnings from pyannote.database (invalid escape sequences)
    warnings.filterwarnings(
        "ignore", category=SyntaxWarning, module="pyannote.database.util"
    )
    warnings.filterwarnings(
        "ignore", category=SyntaxWarning, module="pyannote.database.loader"
    )


def _resolve_version() -> str:
    """Resolve package version with robust fallbacks.

    Order:
    1) Read from bundled Info.plist (DMG/app bundle truth)
    2) Read nearby pyproject.toml (development/source truth)
    3) importlib.metadata.version for installed/editable installs
    4) Fallback to "0.0.0"
    """
    # 1) Prefer Info.plist for DMG/app bundle runtime (most accurate for distributed apps)
    try:
        current = Path(__file__).resolve()
        # Look for Info.plist in app bundle structure
        # Path: /Applications/App.app/Contents/MacOS/src/knowledge_system/__init__.py
        # Target: /Applications/App.app/Contents/Info.plist
        for ancestor in current.parents:
            if ancestor.name == "MacOS":
                info_plist = ancestor.parent / "Info.plist"
                if info_plist.exists():
                    import plistlib

                    with open(info_plist, "rb") as f:
                        plist_data = plistlib.load(f)
                    version = plist_data.get("CFBundleShortVersionString")
                    if version and re.match(r"^\d+\.\d+\.\d+$", version):
                        return version
                break
    except (FileNotFoundError, PermissionError, ValueError, ImportError):
        pass

    # 2) Fallback to pyproject.toml nearby (development/source builds)
    try:
        current = Path(__file__).resolve()
        for ancestor in [current.parent, *current.parents]:
            candidate = ancestor / "pyproject.toml"
            if candidate.exists():
                text = candidate.read_text(encoding="utf-8")
                match = re.search(r"^version\s*=\s*\"(\d+\.\d+\.\d+)\"", text, re.M)
                if match:
                    return match.group(1)
                break
    except (FileNotFoundError, PermissionError, ValueError):
        pass

    # 3) Distribution metadata (pip installs / wheels)
    try:
        return metadata.version("knowledge-system")
    except (metadata.PackageNotFoundError, ImportError):
        pass

    # 4) Safe default
    return "0.0.0"


# Core imports
from .config import Settings, get_settings  # noqa: E402
from .logger import get_logger  # noqa: E402

__version__ = _resolve_version()
__author__ = "Skip the Podcast Desktop"
__email__ = "dev@knowledge-system.local"


# GUI functionality has been deprecated - daemon is now controlled via web interface
# See: DESKTOP_APP_DEPRECATION.md for details
# Legacy GUI code preserved in _deprecated/gui/ directory

__all__ = ["Settings", "get_settings", "get_logger", "__version__"]
