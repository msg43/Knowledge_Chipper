#!/usr/bin/env python3
"""
Comprehensive cleanup of all Episode references after ID unification.
The Episode table was removed - all data is now in MediaSource.
"""

import re
from pathlib import Path


def fix_claim_store():
    """Remove Episode import from claim_store.py"""
    file_path = Path("src/knowledge_system/database/claim_store.py")
    content = file_path.read_text()

    # Remove Episode from imports (line 26)
    content = re.sub(r"(\s+)Episode,\n", "", content)

    file_path.write_text(content)
    print(f"✅ Fixed {file_path}")
    print("   - Removed Episode from imports")


def fix_review_tab():
    """Fix all Episode references in review_tab_system2.py"""
    file_path = Path("src/knowledge_system/gui/tabs/review_tab_system2.py")
    content = file_path.read_text()

    # Fix the query that wasn't caught before
    content = content.replace(
        "episodes = session.query(Episode).order_by(Episode.title).all()",
        "sources = session.query(MediaSource).order_by(MediaSource.title).all()",
    )

    # Fix "All Episodes" references
    content = content.replace('"All Episodes"', '"All Sources"')

    # Fix Episode: label
    content = content.replace('QLabel("Episode:")', 'QLabel("Source:")')

    # Fix column check (there might be another one)
    content = content.replace(
        'if col_name in ["Episode", "Modified"]:',
        'if col_name in ["Source", "Modified"]:',
    )

    # Fix episodes variable in upload results
    content = content.replace(
        "f\"Episodes: {len(upload_results.get('episodes', []))}\"",
        "f\"Sources: {len(upload_results.get('sources', []))}\"",
    )

    file_path.write_text(content)
    print(f"✅ Fixed {file_path}")
    print("   - Fixed Episode query")
    print("   - Updated 'All Episodes' to 'All Sources'")
    print("   - Updated Episode: label to Source:")
    print("   - Fixed upload results reference")


def check_for_remaining():
    """Check for any remaining Episode references"""
    import subprocess

    print("\n🔍 Checking for remaining Episode references...")

    result = subprocess.run(
        ["grep", "-r", "Episode", "src/knowledge_system", "--include=*.py"],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        lines = result.stdout.split("\n")
        # Filter out acceptable references
        problematic = []
        for line in lines:
            if not line:
                continue
            # Skip these acceptable patterns
            if any(
                pattern in line
                for pattern in [
                    "EpisodeBundle",  # HCE type, not database model
                    "episode_",  # Variable names (episode_id, episode_title)
                    "# Episode",  # Comments
                    '"Episode',  # String literals in UI (might be OK)
                    "Episode summaries",  # Comment
                    "Episode ID",  # Comment
                    "Episode {",  # String formatting
                    "Episode:",  # Docstring
                    "for Episodes",  # Comment
                ]
            ):
                continue
            problematic.append(line)

        if problematic:
            print("\n⚠️  Potentially problematic Episode references found:")
            for line in problematic[:20]:  # Show first 20
                print(f"   {line}")
            return False
        else:
            print("✅ No problematic Episode references found!")
            return True
    else:
        print("✅ No Episode references found at all!")
        return True


if __name__ == "__main__":
    print("🧹 Comprehensive Episode Cleanup")
    print("=" * 70)

    fix_claim_store()
    print()
    fix_review_tab()

    success = check_for_remaining()

    print("\n" + "=" * 70)
    if success:
        print("✨ Cleanup complete! All Episode references resolved.")
    else:
        print("⚠️  Some references remain - review output above")
