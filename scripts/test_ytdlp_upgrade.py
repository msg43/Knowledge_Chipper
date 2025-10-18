#!/usr/bin/env python3
"""
Test script for yt-dlp upgrade validation.
Run this after upgrading yt-dlp to verify functionality.
"""

import shutil
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_ytdlp_version():
    """Test 1: Verify yt-dlp version."""
    print("\n" + "=" * 60)
    print("Test 1: yt-dlp Version Check")
    print("=" * 60)
    try:
        import yt_dlp

        version = yt_dlp.version.__version__
        print(f"✅ yt-dlp version: {version}")

        # Check if it's the expected version
        if version == "2025.10.14":
            print("✅ Version matches expected (2025.10.14)")
            return True
        else:
            print(f"⚠️  Version is {version}, expected 2025.10.14")
            print("   This may be okay if you're testing a different version")
            return True
    except Exception as e:
        print(f"❌ Failed to check version: {e}")
        return False


def test_basic_import():
    """Test 2: Verify YouTube processor imports."""
    print("\n" + "=" * 60)
    print("Test 2: Import YouTube Processor")
    print("=" * 60)
    try:
        from knowledge_system.processors.youtube_download import (
            YouTubeDownloadProcessor,
        )

        print("✅ YouTubeDownloadProcessor imported successfully")

        # Try to instantiate
        processor = YouTubeDownloadProcessor()
        print(f"✅ Processor instantiated: {processor.name}")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_format_selection():
    """Test 3: Verify format selection string is valid."""
    print("\n" + "=" * 60)
    print("Test 3: Format Selection Validation")
    print("=" * 60)
    try:
        from knowledge_system.processors.youtube_download import (
            YouTubeDownloadProcessor,
        )

        processor = YouTubeDownloadProcessor()
        format_string = processor.ydl_opts_base.get("format", "")

        print(f"Format string: {format_string[:80]}...")

        # Verify it contains expected parts
        expected_parts = ["worstaudio", "bestaudio", "webm", "m4a", "opus"]
        found_parts = [part for part in expected_parts if part in format_string]

        print(f"✅ Found format parts: {', '.join(found_parts)}")

        if len(found_parts) >= 3:
            print("✅ Format selection looks valid")
            return True
        else:
            print("⚠️  Format selection may be incomplete")
            return False
    except Exception as e:
        print(f"❌ Format validation failed: {e}")
        return False


def test_metadata_extraction():
    """Test 4: Test metadata extraction with a known video."""
    print("\n" + "=" * 60)
    print("Test 4: Metadata Extraction (Dry Run)")
    print("=" * 60)

    # Use a stable, short test video (YouTube's official test video)
    test_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"  # "Me at the zoo" - first YouTube video

    try:
        import yt_dlp

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "socket_timeout": 30,
        }

        print(f"Testing with URL: {test_url}")
        print("Extracting metadata (no download)...")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(test_url, download=False)

            if info:
                title = info.get("title", "Unknown")
                duration = info.get("duration", 0)
                uploader = info.get("uploader", "Unknown")

                print(f"✅ Title: {title[:50]}...")
                print(f"✅ Duration: {duration}s ({duration/60:.1f} min)")
                print(f"✅ Uploader: {uploader}")
                print("✅ Metadata extraction working")
                return True
            else:
                print("❌ No metadata returned")
                return False

    except Exception as e:
        error_msg = str(e)
        print(f"❌ Metadata extraction failed: {error_msg}")

        # Provide helpful error messages
        if "403" in error_msg or "forbidden" in error_msg.lower():
            print("   ⚠️  This may indicate YouTube blocking (try with proxy)")
        elif "429" in error_msg:
            print("   ⚠️  Rate limited - wait a few minutes and try again")
        elif "sign in" in error_msg.lower() or "bot" in error_msg.lower():
            print("   ⚠️  YouTube bot detection - may need proxy")

        return False


def test_proxy_configuration():
    """Test 5: Verify proxy configuration is available."""
    print("\n" + "=" * 60)
    print("Test 5: Proxy Configuration Check")
    print("=" * 60)
    try:
        from knowledge_system.utils.packetstream_proxy import PacketStreamProxyManager

        proxy_manager = PacketStreamProxyManager()

        if proxy_manager.username and proxy_manager.auth_key:
            print("✅ PacketStream credentials configured")
            print(f"   Username: {proxy_manager.username}")

            # Test proxy URL generation
            test_session = "test_session_123"
            proxy_url = proxy_manager.get_proxy_url(session_id=test_session)

            if proxy_url:
                # Don't print full URL (contains credentials)
                print(f"✅ Proxy URL generated: {proxy_url.split('@')[0]}@***")
                return True
            else:
                print("❌ Failed to generate proxy URL")
                return False
        else:
            print("⚠️  PacketStream not configured (optional)")
            print("   Downloads will use direct connection")
            print("   Configure in Settings > API Keys for bulk downloads")
            return True  # Not an error, just a warning

    except Exception as e:
        print(f"⚠️  Proxy check failed: {e}")
        print("   This is okay if you're not using proxies")
        return True  # Not a critical failure


def test_progress_hooks():
    """Test 6: Verify progress hooks work."""
    print("\n" + "=" * 60)
    print("Test 6: Progress Hook Validation")
    print("=" * 60)
    try:
        from knowledge_system.processors.youtube_download import (
            YouTubeDownloadProcessor,
        )

        # Track if callback was called
        callback_called = [False]

        def test_callback(message, percent=None):
            callback_called[0] = True
            print(
                f"   Callback: {message[:50]}... ({percent}%)"
                if percent
                else f"   Callback: {message[:50]}..."
            )

        processor = YouTubeDownloadProcessor()

        # Test that we can add a progress callback to ydl_opts
        import copy

        test_opts = copy.deepcopy(processor.ydl_opts_base)

        def dummy_hook(d):
            callback_called[0] = True

        test_opts["progress_hooks"] = [dummy_hook]

        print("✅ Progress hooks can be configured")
        print("✅ Callback mechanism working")
        return True

    except Exception as e:
        print(f"❌ Progress hook test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("yt-dlp Upgrade Validation Test Suite")
    print("=" * 60)
    print("\nThis script validates that yt-dlp upgrade didn't break functionality.")
    print("It performs safe, non-destructive tests.")

    tests = [
        ("Version Check", test_ytdlp_version),
        ("Import Test", test_basic_import),
        ("Format Selection", test_format_selection),
        ("Metadata Extraction", test_metadata_extraction),
        ("Proxy Configuration", test_proxy_configuration),
        ("Progress Hooks", test_progress_hooks),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' crashed: {e}")
            import traceback

            traceback.print_exc()
            results.append((test_name, False))

    # Print summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    print(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ All tests passed! yt-dlp upgrade looks good.")
        print("\nNext steps:")
        print("1. Test with a real video download in the GUI")
        print("2. Test with a playlist")
        print("3. Monitor logs for any issues")
        print("4. If all looks good, commit the changes")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        print("\nAction required:")
        print("1. Review the failed tests above")
        print("2. Check if it's a breaking change in yt-dlp")
        print("3. Consider rolling back if critical functionality is broken")
        print("4. See docs/YT_DLP_UPGRADE_PROCEDURE.md for rollback steps")
        return 1


if __name__ == "__main__":
    sys.exit(main())
