#!/usr/bin/env python3
"""
Quick script to fix Obsidian tag issues in your markdown files.

Usage:
    python fix_obsidian_tags.py /path/to/your/obsidian/vault
    python fix_obsidian_tags.py /path/to/single/file.md
    python fix_obsidian_tags.py /path/to/directory --dry-run
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from knowledge_system.utils.fix_obsidian_tags import main

if __name__ == "__main__":
    main()
