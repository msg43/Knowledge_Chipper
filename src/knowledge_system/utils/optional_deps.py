"""Utilities for managing optional dependencies at runtime.

Installs optional packages into a per-user vendor directory and ensures the
directory is on sys.path. This allows the app to be installed for all users
while lazily fetching optional features without requiring terminal usage.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def get_vendor_dir() -> str:
    """Return per-user vendor site-packages directory.

    On macOS: ~/Library/Application Support/Knowledge Chipper/vendor/py{major}.{minor}
    On Windows: %APPDATA%/Knowledge Chipper/vendor/py{major}.{minor}
    On Linux: ~/.knowledge_chipper/vendor/py{major}.{minor}
    """
    from .macos_paths import get_application_support_dir

    major, minor = sys.version_info[:2]
    py_tag = f"py{major}.{minor}"

    # Use the standard application support directory
    base = get_application_support_dir() / "vendor" / py_tag
    base.mkdir(parents=True, exist_ok=True)
    return str(base)


def add_vendor_to_sys_path() -> None:
    """Ensure vendor directory is included in sys.path early at runtime."""
    vendor = get_vendor_dir()
    if vendor not in sys.path:
        # Prepend so user-installed optional deps take precedence
        sys.path.insert(0, vendor)


def install_package(package_spec: str) -> bool:
    """Install a package into the vendor directory using pip.

    Returns True on success, False otherwise.
    """
    vendor = get_vendor_dir()
    env = os.environ.copy()
    # Avoid writing bytecode in app bundle; vendor is user-writable
    env.setdefault("PYTHONNOUSERSITE", "1")

    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "--disable-pip-version-check",
        "--no-input",
        "--target",
        vendor,
        package_spec,
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            check=False,
            env=env,
        )
        return proc.returncode == 0
    except Exception:
        return False


def ensure_module(module_name: str, package_spec: str | None = None):
    """Ensure a module is importable; install it into vendor if missing.

    - module_name: import path (e.g., "supabase")
    - package_spec: pip spec (e.g., "supabase" or "supabase>=2.0.0"). Defaults
      to module_name if not provided.
    """
    add_vendor_to_sys_path()
    try:
        __import__(module_name)
        return sys.modules[module_name]
    except Exception:
        pkg = package_spec or module_name
        if install_package(pkg):
            __import__(module_name)
            return sys.modules[module_name]
        raise
