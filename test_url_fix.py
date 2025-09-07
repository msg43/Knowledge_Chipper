#!/usr/bin/env python3
"""
Test the URL list fix to ensure it works correctly.
"""


def test_url_fix():
    """Test that the URL list issue is fixed."""

    print("🧪 Testing URL List Fix")
    print("=" * 30)

    try:
        from src.knowledge_system.utils.youtube_utils import extract_urls

        # Test cases that should now work
        test_cases = [
            # String URL (should work as before)
            ("String URL", "https://www.youtube.com/watch?v=TU3VHYDTE10"),
            # List with one URL (should extract the URL properly)
            ("List with one URL", ["https://www.youtube.com/watch?v=TU3VHYDTE10"]),
            # List with multiple URLs
            (
                "List with multiple URLs",
                [
                    "https://www.youtube.com/watch?v=TU3VHYDTE10",
                    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                ],
            ),
            # List with mixed content
            (
                "List with mixed content",
                [
                    "https://www.youtube.com/watch?v=TU3VHYDTE10",
                    "not a url",
                    "https://youtu.be/dQw4w9WgXcQ",
                ],
            ),
        ]

        for test_name, test_input in test_cases:
            print(f"Testing {test_name}:")
            print(f"  Input: {test_input} (type: {type(test_input)})")

            urls = extract_urls(test_input)
            print(f"  Output: {urls} (type: {type(urls)})")

            if urls:
                print(f"  First URL: {urls[0]} (type: {type(urls[0])})")
                # Verify it's a proper string URL
                assert isinstance(urls[0], str), f"Expected string, got {type(urls[0])}"
                assert not urls[0].startswith(
                    "["
                ), f"URL still contains list formatting: {urls[0]}"
                print(f"  ✅ Success - proper string URL")
            else:
                print(f"  ⚠️ No URLs found")
            print()

        print("🎉 All URL list fixes working correctly!")
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    test_url_fix()
