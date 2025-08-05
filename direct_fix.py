#!/usr/bin/env python3
"""Direct fix for the tag processing lines."""

from pathlib import Path


def direct_fix():
    """Directly fix the indentation issues."""
    youtube_file = Path("src/knowledge_system/processors/youtube_transcript.py")

    if not youtube_file.exists():
        print(f"❌ File not found: {youtube_file}")
        return False

    # Read the file
    with open(youtube_file, encoding="utf-8") as f:
        lines = f.readlines()

    # Find and fix the specific lines
    for i, line in enumerate(lines):
        # Fix line 174 - should be properly indented comment
        if (
            line.strip()
            == "# Format tags as a YAML array, escaping quotes in tag names"
            and i > 170
        ):
            lines[
                i
            ] = "                # Format tags as a YAML array, escaping quotes in tag names\n"
        # Fix line 175 - safe_tags assignment
        elif (
            "safe_tags = [tag.replace" in line and "sanitized_tags" not in lines[i - 3]
        ):
            lines[
                i
            ] = "                safe_tags = [tag.replace('\"', '\\\\\"') for tag in tags_subset]\n"
        # Fix line 176 - tags_yaml assignment (this one has wrong indentation)
        elif line.strip().startswith("tags_yaml = ") and "safe_tags" in lines[i - 1]:
            lines[
                i
            ] = '                tags_yaml = "[" + ", ".join(f\'"{tag}"\' for tag in safe_tags) + "]"\n'
        # Fix line 177 - lines.append for tags
        elif (
            'lines.append(f"tags: {tags_yaml}")' in line and "tags_yaml" in lines[i - 1]
        ):
            lines[i] = '                lines.append(f"tags: {tags_yaml}")\n'
        # Fix line 178 - if statement for more tags
        elif "if len(sanitized_tags) > 10:" in line and "tags:" in lines[i - 1]:
            lines[i] = "                if len(sanitized_tags) > 10:\n"
        # Fix line 179 - lines.append for more tags comment
        elif "more sanitized tags" in line and "len(sanitized_tags)" in lines[i - 1]:
            lines[
                i
            ] = '                    lines.append(f"# ... and {len(sanitized_tags) - 10} more sanitized tags")\n'

    # Write back to file
    with open(youtube_file, "w", encoding="utf-8") as f:
        f.writelines(lines)

    print("✅ Applied direct fix to tag processing indentation")
    return True


if __name__ == "__main__":
    direct_fix()
