#!/usr/bin/env python3

"""
Version bump utility for Knowledge_Chipper.

Single source of truth: pyproject.toml [project.version]

Actions:
- Increment version (patch by default; supports minor/major)
- Sync README.md header line: "**Version:** X.Y.Z | **Build Date:** YYYY-MM-DD"

Design notes:
- Avoids any VCS actions; caller scripts handle git add/commit/push
- Idempotent per invocation: always bumps exactly once when run
"""

from __future__ import annotations

import argparse
import datetime as _dt
import pathlib
import re
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
PYPROJECT = PROJECT_ROOT / "pyproject.toml"
README = PROJECT_ROOT / "README.md"
OVERVIEW = PROJECT_ROOT / "Knowledge_Chipper_Codebase_Overview_for_Claude.md"


_VERSION_RE = re.compile(r"^version\s*=\s*\"(\d+)\.(\d+)\.(\d+)\"", re.M)
_README_VER_RE = re.compile(
    r"^(\*\*Version:\*\*)\s*\d+\.\d+\.\d+\s*\|\s*\*\*Build Date:\*\*\s*\d{4}-\d{2}-\d{2}\s*$"
)


def _read_text(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _write_text(path: pathlib.Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bump project version and sync docs")
    parser.add_argument(
        "--part",
        choices=["patch", "minor", "major"],
        default="patch",
        help="Which part of semver to bump (default: patch)",
    )
    return parser.parse_args()


def bump_semver(version: str, part: str) -> str:
    major, minor, patch = (int(x) for x in version.split("."))
    if part == "major":
        major += 1
        minor = 0
        patch = 0
    elif part == "minor":
        minor += 1
        patch = 0
    else:
        patch += 1
    return f"{major}.{minor}.{patch}"


def get_current_version(pyproject_text: str) -> str:
    m = _VERSION_RE.search(pyproject_text)
    if not m:
        raise SystemExit("❌ Could not find [project].version in pyproject.toml")
    return ".".join(m.groups())


def update_pyproject_version(py_text: str, new_version: str) -> str:
    return _VERSION_RE.sub(f'version = "{new_version}"', py_text, count=1)


def update_readme_version(rd_text: str, new_version: str, today: str) -> str:
    lines = rd_text.splitlines()
    for i, line in enumerate(lines):
        if _README_VER_RE.match(line):
            lines[i] = f"**Version:** {new_version} | **Build Date:** {today} "
            return "\n".join(lines) + ("\n" if rd_text.endswith("\n") else "")
    # If no header found, leave README unchanged
    return rd_text


def update_overview_version(text: str, new_version: str) -> str:
    # Pattern like: **Version**: X.Y.Z  (two spaces at EOL optional)
    pattern = re.compile(r"^(\*\*Version\*\*:)\s*\d+\.\d+\.\d+\s*$", re.M)
    return pattern.sub(rf"\\1 {new_version}", text)


def main() -> None:
    args = parse_args()

    py_text = _read_text(PYPROJECT)
    if not py_text:
        raise SystemExit(f"❌ pyproject.toml not found at {PYPROJECT}")

    current = get_current_version(py_text)
    new_version = bump_semver(current, args.part)

    # Update pyproject.toml
    new_py_text = update_pyproject_version(py_text, new_version)
    if new_py_text == py_text:
        print("ℹ️ Version unchanged in pyproject.toml (unexpected)")
    else:
        _write_text(PYPROJECT, new_py_text)

    # Update README.md version header if present
    rd_text = _read_text(README)
    if rd_text:
        today = _dt.date.today().strftime("%Y-%m-%d")
        new_rd_text = update_readme_version(rd_text, new_version, today)
        if new_rd_text != rd_text:
            _write_text(README, new_rd_text)

    # Update codebase overview doc if present
    ov_text = _read_text(OVERVIEW)
    if ov_text:
        new_ov_text = update_overview_version(ov_text, new_version)
        if new_ov_text != ov_text:
            _write_text(OVERVIEW, new_ov_text)

    print(f"✅ Bumped version: {current} → {new_version}")
    sys.exit(0)


if __name__ == "__main__":
    main()
