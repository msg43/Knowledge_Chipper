#!/usr/bin/env python3
"""Final fix for the tag processing section."""

from pathlib import Path


def final_fix():
    """Apply the final fix to the tag processing section."""
    youtube_file = Path("src/knowledge_system/processors/youtube_transcript.py")

    if not youtube_file.exists():
        print(f"❌ File not found: {youtube_file}")
        return False

    # Read the file
    with open(youtube_file, encoding="utf-8") as f:
        content = f.read()

    # Find and replace the broken tag processing section
    broken_section = """        # Add tags if available (limit to first 10 to keep YAML manageable)
        if self.tags:
            # Sanitize tags before processing
            sanitized_tags = sanitize_tags(self.tags)
            if sanitized_tags:
                tags_subset = sanitized_tags[:10]
            # Format tags as a YAML array, escaping quotes in tag names
            safe_tags = [tag.replace('"', '\\"') for tag in tags_subset]
                tags_yaml = "[" + ", ".join(f'"{tag}"' for tag in safe_tags) + "]"
                lines.append(f"tags: {tags_yaml}")
                if len(sanitized_tags) > 10:
                    lines.append(f"# ... and {len(sanitized_tags) - 10} more sanitized tags")"""

    fixed_section = """        # Add tags if available (limit to first 10 to keep YAML manageable)
        if self.tags:
            # Sanitize tags before processing
            sanitized_tags = sanitize_tags(self.tags)
            if sanitized_tags:
                tags_subset = sanitized_tags[:10]
                # Format tags as a YAML array, escaping quotes in tag names
                safe_tags = [tag.replace('"', '\\"') for tag in tags_subset]
                tags_yaml = "[" + ", ".join(f'"{tag}"' for tag in safe_tags) + "]"
                lines.append(f"tags: {tags_yaml}")
                if len(sanitized_tags) > 10:
                    lines.append(f"# ... and {len(sanitized_tags) - 10} more sanitized tags")"""

    if broken_section in content:
        content = content.replace(broken_section, fixed_section)

        # Write back to file
        with open(youtube_file, "w", encoding="utf-8") as f:
            f.write(content)

        print("✅ Applied final fix to tag processing section")
        return True
    else:
        print("❌ Could not find the broken section to fix")
        return False


if __name__ == "__main__":
    final_fix()
