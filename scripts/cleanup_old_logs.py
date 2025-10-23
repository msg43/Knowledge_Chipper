#!/usr/bin/env python3
"""Clean up outdated log files from the project directory."""

import os
import shutil
from datetime import datetime
from pathlib import Path

# Logs to preserve (build and deployment related)
PRESERVE_PATTERNS = [
    "build_*.log",
    "notarize*.log",
    "signed_notarize*.log",
    "pip_install*.log",
]

# Log directory
LOG_DIR = Path("logs")


def should_preserve(filename: str) -> bool:
    """Check if a log file should be preserved."""
    for pattern in PRESERVE_PATTERNS:
        if pattern.replace("*", "") in filename:
            return True
    return False


def main():
    """Clean up old log files."""
    if not LOG_DIR.exists():
        print("No logs directory found.")
        return

    # Create archive directory for important logs
    archive_dir = LOG_DIR / "archive"
    archive_dir.mkdir(exist_ok=True)

    # Track what we're doing
    removed_files = []
    archived_files = []
    preserved_files = []

    # Process each file in logs directory
    for file_path in LOG_DIR.iterdir():
        if file_path.is_file() and file_path.suffix in [".log", ".csv", ".json", ".txt", ".md"]:
            if should_preserve(file_path.name):
                # Move build/deployment logs to archive
                if file_path.parent == LOG_DIR:  # Only move files in root logs dir
                    archive_path = archive_dir / file_path.name
                    shutil.move(str(file_path), str(archive_path))
                    archived_files.append(file_path.name)
            else:
                # Remove old runtime logs
                file_path.unlink()
                removed_files.append(file_path.name)

    # Create a cleanup summary
    summary_path = LOG_DIR / "CLEANUP_SUMMARY.txt"
    with open(summary_path, "w") as f:
        f.write(f"Log Cleanup Summary - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 60 + "\n\n")
        
        f.write(f"Removed {len(removed_files)} outdated log files:\n")
        for name in sorted(removed_files):
            f.write(f"  - {name}\n")
        
        f.write(f"\nArchived {len(archived_files)} build/deployment logs to logs/archive/:\n")
        for name in sorted(archived_files):
            f.write(f"  - {name}\n")
        
        f.write("\nNote: Runtime logs are now stored in the OS-appropriate location:\n")
        f.write("  - macOS: ~/Library/Logs/Knowledge Chipper/\n")
        f.write("  - Linux: ~/.local/share/knowledge_chipper/logs/\n")
        f.write("  - Windows: %LOCALAPPDATA%\\Knowledge Chipper\\Logs\\\n")

    # Print summary
    print(f"✨ Log cleanup complete!")
    print(f"📁 Removed {len(removed_files)} outdated log files")
    print(f"📦 Archived {len(archived_files)} build/deployment logs to logs/archive/")
    print(f"📝 Summary written to {summary_path}")


if __name__ == "__main__":
    main()
