#!/usr/bin/env python3
"""Auto-fix common docstring issues in the codebase.

This script performs conservative, mechanical edits to address:
- D212: Move the summary to the first line of a multi-line docstring
- D415: Ensure the first line ends with a period
- D205: Ensure a blank line between summary and description (when description exists)
- D103/D107: Add minimal docstrings for public functions and __init__ methods that lack one

Scope: operates on files under 'src/knowledge_system/'.

Limitations:
- Keeps edits minimal; does not rewrite prose or argument docs
- Skips files that cannot be parsed as UTF-8
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src" / "knowledge_system"

TRIPLE_QUOTE_RE = re.compile(r"^(?P<indent>\s*)(?P<q>\"\"\"|'''\s*)(?P<rest>.*)$")
OPEN_ONLY_RE = re.compile(r"^(?P<indent>\s*)(?P<q>\"\"\"|''')\s*$")
CLOSE_ONLY_RE = re.compile(r"^(?P<indent>\s*)(?P<q>\"\"\"|''')\s*$")


def _ends_with_punct(s: str) -> bool:
    return bool(s.rstrip().endswith((".", "?", "!")))


def fix_docstring_block(lines: list[str], start_idx: int) -> int:
    """Fix a docstring block starting at line index start_idx.

    Returns the next index to continue from (may change due to inserted blank lines).
    """
    i = start_idx
    m_open_only = OPEN_ONLY_RE.match(lines[i])
    if m_open_only:
        indent = m_open_only.group("indent")
        quote = m_open_only.group("q").strip()
        if i + 1 >= len(lines):
            return i + 1
        summary_line = lines[i + 1].rstrip("\n")
        if CLOSE_ONLY_RE.match(lines[i + 1]):
            return i + 1
        summary_text = summary_line.strip()
        if summary_text == "":
            return i + 1
        if not _ends_with_punct(summary_text):
            summary_text += "."
        lines[i] = f"{indent}{quote} {summary_text}\n"
        if i + 2 < len(lines):
            next_line = lines[i + 2]
            if not CLOSE_ONLY_RE.match(next_line) and next_line.strip() != "":
                if lines[i + 1].strip() != "":
                    lines.insert(i + 1, f"{indent}\n")
                    return i + 2
        return i + 1
    else:
        m = TRIPLE_QUOTE_RE.match(lines[i])
        if not m:
            return i + 1
        indent = m.group("indent")
        quote = m.group("q").strip()
        rest = m.group("rest").rstrip("\n")
        if rest.strip():
            parts = rest.split("\n")
            first = parts[0].strip()
            if not _ends_with_punct(first):
                first += "."
            parts[0] = first
            new_rest = "\n".join(parts)
            lines[i] = f"{indent}{quote} {new_rest}\n"
        return i + 1


def add_minimal_docstrings(source: str) -> str:
    """Add minimal docstrings to public functions and __init__ without one.

    Heuristic-based regex approach to avoid heavy AST rewriting.
    """
    def repl_init(match: re.Match[str]) -> str:
        indent = match.group("indent")
        header = match.group("header")
        return f"{header}\n{indent}    \"\"\"Initialize the instance.\"\"\"\n"

    init_pat = re.compile(
        r"^(?P<header>(?P<indent>\s*)def\s+__init__\s*\([^\)]*\)\s*:\s*)\n(?!\s*\"\"\"|\s*''')",
        re.MULTILINE,
    )
    source = init_pat.sub(repl_init, source)

    def repl_func(match: re.Match[str]) -> str:
        indent = match.group("indent")
        name = match.group("name")
        return f"{match.group('header')}\n{indent}    \"\"\"{name.replace('_', ' ').capitalize()}.\"\"\"\n"

    func_pat = re.compile(
        r"^(?P<header>(?P<indent>\s*)def\s+(?P<name>[a-zA-Z][a-zA-Z0-9_]*)\s*\([^\)]*\)\s*:\s*)\n(?!\s*\"\"\"|\s*''')",
        re.MULTILINE,
    )
    source = func_pat.sub(repl_func, source)

    return source


def process_file(path: Path) -> bool:
    changed = False
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return False

    new_text = add_minimal_docstrings(text)

    lines = new_text.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        line = lines[i]
        if OPEN_ONLY_RE.match(line) or TRIPLE_QUOTE_RE.match(line):
            i = fix_docstring_block(lines, i)
            changed = True
        else:
            i += 1

    updated = "".join(lines)
    if updated != text:
        path.write_text(updated, encoding="utf-8")
        changed = True
    return changed


def main() -> int:
    if not SRC_ROOT.exists():
        print(f"Source root not found: {SRC_ROOT}")
        return 1

    total = 0
    changed = 0
    for py_path in SRC_ROOT.rglob("*.py"):
        if "egg-info" in py_path.parts:
            continue
        total += 1
        if process_file(py_path):
            print(f"fixed: {py_path.relative_to(PROJECT_ROOT)}")
            changed += 1
    print(f"Docstring fix complete. Files scanned: {total}, changed: {changed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())


