#!/usr/bin/env python3
"""Fix the syntax error in the tag processing."""

from pathlib import Path


def fix_syntax():
    """Fix the syntax error in lines 175-176."""
    youtube_file = Path("src/knowledge_system/processors/youtube_transcript.py")

    if not youtube_file.exists():
        print(f"❌ File not found: {youtube_file}")
        return False

    # Read the file
    with open(youtube_file, encoding="utf-8") as f:
        lines = f.readlines()

    # Find and fix the problematic lines
    for i, line in enumerate(lines):
        # Fix line 175 - should be properly indented
        if "safe_tags = [tag.replace" in line and not line.startswith(
            "                "
        ):
            lines[
                i
            ] = "                safe_tags = [tag.replace('\"', '\\\\\"') for tag in tags_subset]\n"
            print(f"Fixed line {i+1}: safe_tags assignment")
        # Fix line 176 - should be properly indented
        elif "tags_yaml = " in line and not line.startswith("                "):
            lines[
                i
            ] = '                tags_yaml = "[" + ", ".join(f\'"{tag}"\' for tag in safe_tags) + "]"\n'
            print(f"Fixed line {i+1}: tags_yaml assignment")

    # Write back to file
    with open(youtube_file, "w", encoding="utf-8") as f:
        f.writelines(lines)

    print("✅ Fixed syntax errors in tag processing")
    return True


if __name__ == "__main__":
    fix_syntax()
