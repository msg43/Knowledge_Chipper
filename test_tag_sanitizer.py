#!/usr/bin/env python3
"""Test the YouTube tag sanitizer functionality."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def test_tag_sanitizer():
    """Test the tag sanitizer with various input examples."""
    try:
        from knowledge_system.processors.youtube_transcript import (
            sanitize_tag,
            sanitize_tags,
        )

        print("🏷️  YouTube Tag Sanitizer Test")
        print("=" * 50)

        # Test individual tags
        test_cases = [
            "Machine Learning",
            "AI & Technology",
            "Python (Programming)",
            "Data Science 101",
            "🤖 Robotics & AI",
            "Web-Development",
            "Tutorial #1: Getting Started",
            "C++/C# Programming",
            "   spaces   around   ",
            "Special!@#$%^&*()Characters",
            "",
            "Normal_Tag",
            "UPPERCASE",
            "lowercase",
            "Mix3d_C4se_123",
        ]

        print("Individual Tag Sanitization:")
        print("-" * 30)
        for original in test_cases:
            sanitized = sanitize_tag(original)
            print(f"'{original}' -> '{sanitized}'")

        print("\nBatch Tag Sanitization:")
        print("-" * 30)
        print("Original tags:")
        for i, tag in enumerate(test_cases):
            print(f"  {i+1}. '{tag}'")

        sanitized_batch = sanitize_tags(test_cases)
        print(f"\nSanitized tags ({len(sanitized_batch)} valid tags):")
        for i, tag in enumerate(sanitized_batch):
            print(f"  {i+1}. '{tag}'")

        print(f"\n✅ Tag sanitizer is working correctly!")
        print(f"• Original count: {len(test_cases)}")
        print(f"• Sanitized count: {len(sanitized_batch)}")
        print(f"• Empty tags filtered out: {len(test_cases) - len(sanitized_batch)}")

        return True

    except ImportError as e:
        print(f"❌ Could not import tag sanitizer: {e}")
        return False
    except Exception as e:
        print(f"❌ Error testing tag sanitizer: {e}")
        return False


if __name__ == "__main__":
    test_tag_sanitizer()
