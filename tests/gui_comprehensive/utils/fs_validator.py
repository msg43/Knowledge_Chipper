"""
Filesystem (Markdown/YAML) validation helpers for tests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

import yaml


def read_markdown_with_frontmatter(path: Path) -> Tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}, text
    try:
        parts = text.split("\n---\n", 1)
        fm_text = parts[0][4:]
        body = parts[1] if len(parts) > 1 else ""
        frontmatter = yaml.safe_load(fm_text) or {}
        return frontmatter, body
    except Exception:
        return {}, text


def assert_markdown_has_sections(path: Path, sections: list[str]) -> bool:
    _, body = read_markdown_with_frontmatter(path)
    body_low = body.lower()
    return all(section.lower() in body_low for section in sections)


