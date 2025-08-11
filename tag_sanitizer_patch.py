#!/usr/bin/env python3
"""
Patch to add tag sanitization to YouTube transcript processor.
This script will add a sanitize_tags function and update the tag processing.
"""

from pathlib import Path


def add_tag_sanitizer():
    """Add tag sanitizer function to the YouTube transcript processor."""
    youtube_file = Path("src/knowledge_system/processors/youtube_transcript.py")

    if not youtube_file.exists():
        print(f"❌ File not found: {youtube_file}")
        return False

    # Read the file
    with open(youtube_file, encoding="utf-8") as f:
        content = f.read()

    # Check if sanitizer is already added
    if "def sanitize_tag(" in content:
        print("✅ Tag sanitizer already exists")
        return True

    # Find where to insert the sanitizer function (after the logger line)
    logger_line = "logger = get_logger(__name__)"
    if logger_line not in content:
        print("❌ Could not find logger line to insert after")
        return False

    # Define the sanitizer function
    sanitizer_function = '''

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

    # Insert the sanitizer function after the logger line
    content = content.replace(logger_line, logger_line + sanitizer_function)

    # Now update the tag processing in the YAML generation (around line 122-124)
    old_tag_processing = """        # Add tags if available (limit to first 10 to keep YAML manageable)
        if self.tags:
            tags_subset = self.tags[:10]
            # Format tags as a YAML array, escaping quotes in tag names
            safe_tags = [tag.replace('"', '\\"') for tag in tags_subset]
            tags_yaml = "[" + ", ".join(f'"{tag}"' for tag in safe_tags) + "]"
            lines.append(f"tags: {tags_yaml}")
            if len(self.tags) > 10:
                lines.append(f"# ... and {len(self.tags) - 10} more tags")"""

    new_tag_processing = """        # Add tags if available (limit to first 10 to keep YAML manageable)
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

    if old_tag_processing in content:
        content = content.replace(old_tag_processing, new_tag_processing)
        print("✅ Updated tag processing in YAML generation")
    else:
        print("❌ Could not find tag processing section to update")
        return False

    # Write back to file
    with open(youtube_file, "w", encoding="utf-8") as f:
        f.write(content)

    print("✅ Added tag sanitizer and updated tag processing")
    return True


def test_tag_sanitizer():
    """Test the tag sanitizer function."""
    # Test cases
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
        "UPPERCASE",
        "lowercase",
        "Mix3d_C4se",
    ]

    print("🧪 Testing tag sanitizer...")
    print("Original Tag -> Sanitized Tag")
    print("-" * 40)

    # Import the sanitizer functions
    import sys

    sys.path.insert(0, "src")

    try:
        from knowledge_system.processors.youtube_transcript import (
            sanitize_tag,
            sanitize_tags,
        )

        for tag in test_tags:
            sanitized = sanitize_tag(tag)
            print(f"'{tag}' -> '{sanitized}'")

        print("\nBatch sanitization:")
        print(f"Original: {test_tags}")
        sanitized_batch = sanitize_tags(test_tags)
        print(f"Sanitized: {sanitized_batch}")

        return True

    except ImportError as e:
        print(f"❌ Could not import sanitizer functions: {e}")
        return False


def main():
    """Main function to add tag sanitizer."""
    print("🏷️  Adding YouTube Tag Sanitizer...")
    print("=" * 50)

    if add_tag_sanitizer():
        print("\n✅ Tag sanitizer successfully added!")
        print("\n📝 What this does:")
        print("• Replaces spaces with underscores in YouTube tags")
        print("• Removes special characters, punctuation, and emojis")
        print("• Keeps only alphanumeric characters and underscores")
        print("• Filters out empty tags after sanitization")
        print("• Applies to tags in YAML frontmatter of transcript files")

        # Test the sanitizer
        print("\n" + "=" * 50)
        test_tag_sanitizer()

    else:
        print("\n❌ Failed to add tag sanitizer")


if __name__ == "__main__":
    main()
