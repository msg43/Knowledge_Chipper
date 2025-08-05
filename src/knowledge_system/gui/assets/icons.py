"""
Icon management for Knowledge Chipper GUI.
Provides centralized access to application icons.
"""

from pathlib import Path
from typing import Optional, Union

from PyQt6.QtGui import QIcon, QPixmap


def get_icon_paths() -> list[Path]:
    """Get all possible icon file paths in order of preference."""
    base_paths = [
        Path(__file__).parent.parent.parent.parent.parent,  # Project root
        Path(__file__).parent,  # This assets directory
    ]

    icon_names = [
        "chipper.png",
        "chipper.ico",
    ]  # PNG first for better macOS compatibility

    paths = []
    for base in base_paths:
        for name in icon_names:
            paths.append(base / name)

    return paths


def get_app_icon() -> QIcon | None:
    """Get the application icon as a QIcon."""
    for icon_path in get_icon_paths():
        if icon_path.exists():
            try:
                return QIcon(str(icon_path))
            except Exception:
                continue
    return None


def get_app_pixmap(size: tuple[int, int] | None = None) -> QPixmap | None:
    """Get the application icon as a QPixmap."""
    for icon_path in get_icon_paths():
        if icon_path.exists():
            try:
                pixmap = QPixmap(str(icon_path))
                if size:
                    pixmap = pixmap.scaled(*size)
                return pixmap
            except Exception:
                continue
    return None


def get_icon_path() -> Path | None:
    """Get the first available icon file path."""
    for icon_path in get_icon_paths():
        if icon_path.exists():
            return icon_path
    return None
