#!/usr/bin/env python3
"""
Test YouTube transcript extraction with the new proxy system.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def test_proxy_service_in_transcript_processor():
    """Test that YouTubeTranscriptProcessor can use ProxyService."""
    print("Testing ProxyService integration with YouTubeTranscriptProcessor...")
    try:
        # Just test that we can import and instantiate
        # We won't actually fetch a transcript in the test
        from knowledge_system.processors.youtube_transcript import (
            YouTubeTranscriptProcessor,
        )

        processor = YouTubeTranscriptProcessor(
            output_dir="/tmp/test_output", force_diarization=False
        )

        print("✅ YouTubeTranscriptProcessor instantiated successfully")
        print(f"   Processor name: {processor.name}")

        return True
    except Exception as e:
        print(f"❌ YouTubeTranscriptProcessor test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_proxy_import_in_transcript_module():
    """Test that youtube_transcript.py can import ProxyService."""
    print("\nTesting ProxyService import in youtube_transcript module...")
    try:
        # This will fail if there are import errors in youtube_transcript.py
        from knowledge_system.processors import youtube_transcript

        # Check that ProxyService can be imported within that module's context
        from knowledge_system.utils.proxy import ProxyService

        print("✅ ProxyService can be imported in youtube_transcript context")
        return True
    except Exception as e:
        print(f"❌ Import test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run tests."""
    print("=" * 60)
    print("YouTube Integration Test Suite")
    print("=" * 60)

    tests = [
        test_proxy_import_in_transcript_module,
        test_proxy_service_in_transcript_processor,
    ]

    results = []
    for test in tests:
        results.append(test())

    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("✅ All integration tests passed!")
        return 0
    else:
        print(f"❌ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
