#!/usr/bin/env python3
"""
Test script for proxy-based YouTube transcript extraction.
Make sure to set your Webshare credentials as environment variables first.
"""

import os
import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from knowledge_system.processors.youtube_transcript import YouTubeTranscriptProcessor


def test_proxy_youtube_transcript():
    """Test the proxy-based YouTube transcript extraction."""

    # Check if credentials are set
    username = os.getenv("WEBSHARE_USERNAME")
    password = os.getenv("WEBSHARE_PASSWORD")

    if not username or not password:
        print("❌ Error: Webshare credentials not found!")
        print("Please set the following environment variables:")
        print("  export WEBSHARE_USERNAME='your-username-rotate'")
        print("  export WEBSHARE_PASSWORD='your-password-here'")
        return False

    print("✅ Webshare credentials found")
    print(f"Username: {username}")
    print("Note: Webshare handles IP rotation automatically")
    print()

    # Test URLs (known to have transcripts)
    test_urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # Rick Roll - should have captions
        "https://youtu.be/PqS4-DmN5kY",  # Your previous failing video
    ]

    # Initialize processor
    processor = YouTubeTranscriptProcessor(
        preferred_language="en", prefer_manual=True, fallback_to_auto=True
    )

    print("🔄 Testing Webshare proxy transcript extraction...")
    print("(Webshare automatically rotates IP addresses)")
    print("-" * 50)

    for i, url in enumerate(test_urls, 1):
        print(f"\n[{i}] Testing: {url}")

        try:
            # Test the transcript extraction
            result = processor.process(
                url, output_dir="test_output", output_format="md"
            )

            if result.success:
                print("✅ Success!")
                if result.data.get("transcripts"):
                    transcript = result.data["transcripts"][0]
                    print(f"   Title: {transcript.get('title', 'N/A')}")
                    print(f"   Language: {transcript.get('language', 'N/A')}")
                    print(
                        f"   Length: {len(transcript.get('transcript_text', ''))} characters"
                    )
                    print(f"   Output: {result.data.get('output_files', ['N/A'])[0]}")
                else:
                    print("   No transcript data found")
            else:
                print("❌ Failed!")
                if result.data.get("errors"):
                    for error in result.data["errors"]:
                        print(f"   Error: {error}")

        except Exception as e:
            print(f"❌ Exception: {e}")

    print("\n" + "=" * 50)
    print("Test completed!")
    return True


if __name__ == "__main__":
    test_proxy_youtube_transcript()
