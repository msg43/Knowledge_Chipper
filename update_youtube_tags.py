#!/usr/bin/env python3
"""
Script to add tag sanitization to YouTube transcript processor.
"""

from pathlib import Path


def add_sanitizer_functions():
    """Add the sanitizer functions to the YouTube transcript processor."""
    youtube_file = Path("src/knowledge_system/processors/youtube_transcript.py")

    if not youtube_file.exists():
        print(f"❌ File not found: {youtube_file}")
        return False

    # Read the file
    with open(youtube_file, encoding="utf-8") as f:
        content = f.read()

    # Check if sanitizer is already added
    if "def sanitize_tag(" in content:
        print("✅ Tag sanitizer functions already exist")
        return True

    # Find where to insert the sanitizer functions (after the logger line)
    logger_line = "logger = get_logger(__name__)"
    if logger_line not in content:
        print("❌ Could not find logger line to insert after")
        return False

    # Define the sanitizer functions
    sanitizer_functions = '''

def sanitize_tag(tag: str) -> str:
    """
    Sanitize YouTube tags by replacing spaces with underscores and removing/converting non-alphanumeric characters.

    Args:
        tag: Original tag string

    Returns:
        Sanitized tag string suitable for YAML and general use
    """
    if not tag or not isinstance(tag, str):
        return ""

    # Replace spaces with underscores
    sanitized = tag.replace(" ", "_")

    # Keep only alphanumeric characters and underscores
    # This removes special characters like punctuation, emojis, etc.
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '', sanitized)

    # Remove leading/trailing underscores and collapse multiple underscores
    sanitized = re.sub(r'_+', '_', sanitized).strip('_')

    # Return empty string if nothing valid remains
    return sanitized if sanitized else ""


def sanitize_tags(tags: List[str]) -> List[str]:
    """
    Sanitize a list of YouTube tags.

    Args:
        tags: List of original tag strings

    Returns:
        List of sanitized tag strings with empty strings filtered out
    """
    if not tags:
        return []

    sanitized_tags = []
    for tag in tags:
        sanitized = sanitize_tag(tag)
        if sanitized:  # Only add non-empty sanitized tags
            sanitized_tags.append(sanitized)

    return sanitized_tags'''

    # Insert the sanitizer functions after the logger line
    content = content.replace(logger_line, logger_line + sanitizer_functions)

    # Write back to file
    with open(youtube_file, "w", encoding="utf-8") as f:
        f.write(content)

    print("✅ Added tag sanitizer functions")
    return True


def update_tag_processing():
    """Update the tag processing in the YAML generation method."""
    youtube_file = Path("src/knowledge_system/processors/youtube_transcript.py")

    if not youtube_file.exists():
        print(f"❌ File not found: {youtube_file}")
        return False

    # Read the file
    with open(youtube_file, encoding="utf-8") as f:
        content = f.read()

    # Find and replace the tag processing section
    # Look for the exact pattern from the file
    old_pattern = """        # Add tags if available (limit to first 10 to keep YAML manageable)
        if self.tags:
            tags_subset = self.tags[:10]
            # Format tags as a YAML array, escaping quotes in tag names
            safe_tags = [tag.replace('"', '\\"') for tag in tags_subset]
            tags_yaml = "[" + ", ".join(f'"{tag}"' for tag in safe_tags) + "]"
            lines.append(f"tags: {tags_yaml}")
            if len(self.tags) > 10:
                lines.append(f"# ... and {len(self.tags) - 10} more tags")"""

    new_pattern = """        # Add tags if available (limit to first 10 to keep YAML manageable)
        if self.tags:
            # Sanitize tags before processing
            sanitized_tags = sanitize_tags(self.tags)
            if sanitized_tags:
                tags_subset = sanitized_tags[:10]
                # Format tags as a YAML array, escaping quotes in tag names (though sanitized tags shouldn't need it)
                safe_tags = [tag.replace('"', '\\"') for tag in tags_subset]
                tags_yaml = "[" + ", ".join(f'"{tag}"' for tag in safe_tags) + "]"
                lines.append(f"tags: {tags_yaml}")
                if len(sanitized_tags) > 10:
                    lines.append(f"# ... and {len(sanitized_tags) - 10} more sanitized tags")"""

    if old_pattern in content:
        content = content.replace(old_pattern, new_pattern)

        # Write back to file
        with open(youtube_file, "w", encoding="utf-8") as f:
            f.write(content)

        print("✅ Updated tag processing in YAML generation")
        return True
    else:
        print("❌ Could not find exact tag processing pattern to update")
        # Let's try a more flexible approach

        # Look for the specific lines we want to change
        lines = content.split("\n")
        modified = False
        new_lines = []

        i = 0
        while i < len(lines):
            line = lines[i]

            # Look for the start of the tag processing block
            if (
                "# Add tags if available (limit to first 10 to keep YAML manageable)"
                in line
            ):
                # Add the comment line
                new_lines.append(line)
                i += 1

                # Next line should be "if self.tags:"
                if i < len(lines) and "if self.tags:" in lines[i]:
                    new_lines.append(lines[i])  # Add the if line
                    i += 1

                    # Add the sanitization code
                    indent = "            "  # Match the existing indentation
                    new_lines.append(f"{indent}# Sanitize tags before processing")
                    new_lines.append(
                        f"{indent}sanitized_tags = sanitize_tags(self.tags)"
                    )
                    new_lines.append(f"{indent}if sanitized_tags:")

                    # Skip the old "tags_subset = self.tags[:10]" line and replace with sanitized version
                    if i < len(lines) and "tags_subset = self.tags[:10]" in lines[i]:
                        new_lines.append(
                            f"{indent}    tags_subset = sanitized_tags[:10]"
                        )
                        i += 1

                    # Keep the rest of the tag processing but update references
                    while (
                        i < len(lines)
                        and lines[i].strip()
                        and not lines[i].startswith("        #")
                        and not lines[i].startswith("        # Add transcript")
                    ):
                        current_line = lines[i]
                        # Update references to self.tags to use sanitized_tags
                        if "len(self.tags)" in current_line:
                            current_line = current_line.replace(
                                "len(self.tags)", "len(sanitized_tags)"
                            )
                            current_line = current_line.replace(
                                "more tags", "more sanitized tags"
                            )
                        new_lines.append(current_line)
                        i += 1

                    modified = True
                    continue

            new_lines.append(line)
            i += 1

        if modified:
            # Write back to file
            with open(youtube_file, "w", encoding="utf-8") as f:
                f.write("\n".join(new_lines))

            print("✅ Updated tag processing using line-by-line approach")
            return True
        else:
            print("❌ Could not locate tag processing section")
            return False


def test_sanitizer():
    """Test the tag sanitizer with sample data."""
    test_tags = [
        "Machine Learning",
        "AI & Technology",
        "Python (Programming)",
        "Data Science 101",
        "🤖 Robotics",
        "Web-Development",
        "Tutorial #1",
        "C++/C# Programming",
        "   spaces   ",
        "",
        "Normal_Tag",
    ]

    print("\n🧪 Test cases for tag sanitizer:")
    print("Input -> Expected Output")
    print("-" * 40)

    expected_results = [
        ("Machine Learning", "Machine_Learning"),
        ("AI & Technology", "AI_Technology"),
        ("Python (Programming)", "Python_Programming"),
        ("Data Science 101", "Data_Science_101"),
        ("🤖 Robotics", "Robotics"),
        ("Web-Development", "Web_Development"),
        ("Tutorial #1", "Tutorial_1"),
        ("C++/C# Programming", "C_C_Programming"),
        ("   spaces   ", "spaces"),
        ("", ""),
        ("Normal_Tag", "Normal_Tag"),
    ]

    for original, expected in expected_results:
        print(f"'{original}' -> '{expected}'")


def main():
    """Main function to add tag sanitization."""
    print("🏷️  Adding YouTube Tag Sanitizer...")
    print("=" * 50)

    success_count = 0

    # Step 1: Add sanitizer functions
    if add_sanitizer_functions():
        success_count += 1

    # Step 2: Update tag processing
    if update_tag_processing():
        success_count += 1

    print("=" * 50)
    print(f"✅ Completed {success_count}/2 updates")

    if success_count == 2:
        print("\n🎉 YouTube tag sanitizer successfully added!")
        print("\n📝 What this does:")
        print("• Replaces spaces with underscores in YouTube tags")
        print("• Removes special characters, punctuation, and emojis")
        print("• Keeps only alphanumeric characters and underscores")
        print("• Filters out empty tags after sanitization")
        print("• Applies to tags in YAML frontmatter of transcript files")

        test_sanitizer()

        print("\n📋 Next steps:")
        print("1. The YouTube tab will now sanitize tags automatically")
        print("2. Extract any YouTube video to test the new tag sanitization")
        print("3. Check the YAML frontmatter in the generated transcript files")

    else:
        print("\n⚠️  Some updates failed. Manual intervention may be needed.")


if __name__ == "__main__":
    main()
