#!/usr/bin/env python3
"""Fix indentation in the tag processing section."""

from pathlib import Path


def fix_indentation():
    """Fix the indentation in the YouTube transcript processor."""
    youtube_file = Path("src/knowledge_system/processors/youtube_transcript.py")

    if not youtube_file.exists():
        print(f"❌ File not found: {youtube_file}")
        return False

    # Read the file
    with open(youtube_file, encoding="utf-8") as f:
        lines = f.readlines()

    # Fix the indentation around lines 170-180
    fixed_lines = []
    for i, line in enumerate(lines):
        # Check for the specific problematic lines and fix indentation
        if "# Sanitize tags before processing" in line:
            fixed_lines.append("            # Sanitize tags before processing\n")
        elif "sanitized_tags = sanitize_tags(self.tags)" in line:
            fixed_lines.append(
                "            sanitized_tags = sanitize_tags(self.tags)\n"
            )
        elif "if sanitized_tags:" in line and "tags_subset" not in line:
            fixed_lines.append("            if sanitized_tags:\n")
        elif "tags_subset = sanitized_tags[:10]" in line:
            fixed_lines.append("                tags_subset = sanitized_tags[:10]\n")
        elif (
            "# Format tags as a YAML array" in line
            and "tags_subset" not in lines[i - 1]
        ):
            fixed_lines.append(
                "                # Format tags as a YAML array, escaping quotes in tag names\n"
            )
        elif (
            line.strip().startswith("safe_tags = [tag.replace")
            and "sanitized_tags" not in lines[i - 2]
        ):
            fixed_lines.append(
                "                safe_tags = [tag.replace('\"', '\\\\\"') for tag in tags_subset]\n"
            )
        elif line.strip().startswith('tags_yaml = "["') and "safe_tags" in lines[i - 1]:
            fixed_lines.append(
                '                tags_yaml = "[" + ", ".join(f\'"{tag}"\' for tag in safe_tags) + "]"\n'
            )
        elif 'lines.append(f"tags: {tags_yaml}")' in line:
            fixed_lines.append('                lines.append(f"tags: {tags_yaml}")\n')
        elif "if len(sanitized_tags) > 10:" in line:
            fixed_lines.append("                if len(sanitized_tags) > 10:\n")
        elif "more sanitized tags" in line:
            fixed_lines.append(
                '                    lines.append(f"# ... and {len(sanitized_tags) - 10} more sanitized tags")\n'
            )
        else:
            fixed_lines.append(line)

    # Write back to file
    with open(youtube_file, "w", encoding="utf-8") as f:
        f.writelines(fixed_lines)

    print("✅ Fixed indentation in tag processing section")
    return True


if __name__ == "__main__":
    fix_indentation()
