"""Helpers for optional runtime dependencies.

Use require() when importing optional modules so we can present clear messages
instead of raw ImportError stack traces.
"""

from __future__ import annotations


def require(module_name: str, install_hint: str):
    try:
        return __import__(module_name)
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            f"Optional dependency '{module_name}' is required for this feature.\n"
            f"Install with: {install_hint}"
        ) from exc
