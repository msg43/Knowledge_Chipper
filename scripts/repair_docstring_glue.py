#!/usr/bin/env python3
"""Repair lines where a docstring opening is glued to code.

Example pattern this fixes:
    triple-quote + space + code + trailing dot
e.g.:
    [triple-quote] if condition:.

This script splits such lines into a proper closing docstring line and moves
the code to the next line, removing the trailing artifact dot.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "knowledge_system"

PATTERNS = [
    re.compile(r'^(?P<indent>\s*)(?P<q>"""|\'\'\')\s+(?P<code>.+?)\.(?P<trail>\s*)$')
]


def repair_file(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return False

    lines = text.splitlines(keepends=True)
    changed = False
    for i, line in enumerate(lines):
        for pat in PATTERNS:
            m = pat.match(line)
            if m:
                indent = m.group("indent")
                quote = m.group("q")
                code = m.group("code").rstrip()
                # Replace current line with a clean docstring terminator
                lines[i] = f"{indent}{quote}\n"
                # Insert the code line after, without the trailing artifact dot
                lines.insert(i + 1, f"{indent}{code}\n")
                changed = True
                break

    if changed:
        try:
            path.write_text("".join(lines), encoding="utf-8")
            return True
        except Exception:
            return False
    return False


def main() -> int:
    if not SRC.exists():
        print(f"Source directory not found: {SRC}")
        return 1

    total = 0
    fixed = 0
    for py in SRC.rglob("*.py"):
        # skip egg-info etc.
        if "egg-info" in py.parts:
            continue
        total += 1
        if repair_file(py):
            print(f"fixed: {py.relative_to(ROOT)}")
            fixed += 1
    print(f"Repair complete. Files scanned: {total}, fixed: {fixed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
