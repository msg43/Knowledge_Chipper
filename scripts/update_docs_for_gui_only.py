#!/usr/bin/env python3
"""
Automatically update documentation to remove CLI references.

This script updates README and CHANGELOG to reflect GUI-only application.
"""

from datetime import datetime
from pathlib import Path


def update_readme():
    """Update README.md to remove CLI references."""
    readme = Path("README.md")

    if not readme.exists():
        print("README.md not found, skipping")
        return

    content = readme.read_text()
    original_content = content

    # Add GUI-only notice at top if not present
    gui_notice = """
## Application Type

**Knowledge Chipper is a GUI-only application.** All functionality is available through the graphical interface.

The CLI interface has been removed to maintain a single, well-tested code path. If you need automation/scripting capabilities, please use the GUI's batch processing and folder monitoring features.

"""

    if "GUI-only application" not in content:
        # Insert after first heading
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("# "):
                lines.insert(i + 2, gui_notice)
                break
        content = "\n".join(lines)

    # Save if changed
    if content != original_content:
        readme.write_text(content)
        print("✅ Updated README.md")
    else:
        print("ℹ️  README.md already up to date")


def update_changelog():
    """Update CHANGELOG.md with CLI removal entry."""
    changelog = Path("CHANGELOG.md")

    if not changelog.exists():
        print("CHANGELOG.md not found, creating")
        changelog.touch()

    content = (
        changelog.read_text()
        if changelog.exists() and changelog.stat().st_size > 0
        else ""
    )

    # Create entry
    today = datetime.now().strftime("%Y-%m-%d")
    entry = f"""## [Unreleased] - {today}

### Breaking Changes
- Removed CLI interface - application is now GUI-only
- All functionality available through enhanced GUI with System2 architecture

### Added
- Comprehensive System2Orchestrator tests (async job processing)
- LLM adapter async behavior tests (event loop cleanup validation)
- GUI integration tests using automated workflows
- Direct logic tests for complete coverage
- Automated test suite with zero human intervention

### Changed
- Monitor tab now uses System2Orchestrator (consistent with Summarization tab)
- Unified code path: all operations use System2Orchestrator architecture
- Single implementation strategy eliminates CLI/GUI divergence

### Removed
- CLI commands (transcribe, summarize, moc, process, database, upload, voice_test)
- CLI-specific processors (SummarizerProcessor, MOCProcessor, summarizer_legacy.py, summarizer_unified.py)
- Duplicate implementation paths
- commands/ directory
- cli.py entry point

### Fixed
- Transcript files now load correctly in summarization tab after transcription
- Event loop closure errors during async HTTP client cleanup
- Monitor tab uses same tested code path as rest of GUI

---

"""

    # Only add if not already present
    if "Removed CLI interface" not in content:
        content = entry + content
        changelog.write_text(content)
        print("✅ Updated CHANGELOG.md")
    else:
        print("ℹ️  CHANGELOG.md already up to date")


def main():
    """Run all documentation updates."""
    print("Updating documentation for GUI-only application...")
    print("")

    update_readme()
    update_changelog()

    print("")
    print("✅ Documentation updated successfully")
    print("   - README.md: Added GUI-only notice")
    print("   - CHANGELOG.md: Added CLI removal entry")


if __name__ == "__main__":
    main()
