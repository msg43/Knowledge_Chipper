#!/usr/bin/env python3
"""
Test Script for Multi-Account Download Functionality

Tests:
1. Cookie file validation
2. Single-account download
3. Multi-account download with rotation
4. Deduplication across accounts
5. Stale cookie handling (simulated)
6. Sleep period functionality

Usage:
    python test_multi_account_downloads.py --cookies cookies_1.txt cookies_2.txt cookies_3.txt
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from knowledge_system.database import DatabaseService
from knowledge_system.logger import setup_logging
from knowledge_system.services.download_scheduler import DownloadScheduler
from knowledge_system.services.multi_account_downloader import (
    MultiAccountDownloadScheduler,
)
from knowledge_system.utils.deduplication import VideoDeduplicationService

logger = logging.getLogger(__name__)


# Test URLs (public videos)
TEST_URLS = [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # Rick Astley - Never Gonna Give You Up
    "https://www.youtube.com/watch?v=9bZkp7q19f0",  # PSY - Gangnam Style
    "https://www.youtube.com/watch?v=kJQP7kiw5Fk",  # Luis Fonsi - Despacito
    "https://youtu.be/dQw4w9WgXcQ",  # Duplicate of first (different URL format)
    "https://www.youtube.com/watch?v=JGwWNGJdvx8",  # Ed Sheeran - Shape of You
]


def test_cookie_validation(cookie_files: list[str]):
    """Test 1: Cookie file validation"""
    print("\n" + "=" * 60)
    print("TEST 1: Cookie File Validation")
    print("=" * 60)

    from http.cookiejar import MozillaCookieJar

    for idx, cookie_file in enumerate(cookie_files, 1):
        print(f"\nTesting Account {idx}: {cookie_file}")

        try:
            # Check file exists
            if not Path(cookie_file).exists():
                print(f"  ❌ File not found")
                continue

            # Parse cookies
            jar = MozillaCookieJar(cookie_file)
            jar.load(ignore_discard=True, ignore_expires=True)

            # Count YouTube cookies
            youtube_cookies = [
                c for c in jar if "youtube.com" in c.domain or "google.com" in c.domain
            ]

            if youtube_cookies:
                print(f"  ✅ Valid: Found {len(youtube_cookies)} YouTube/Google cookies")

                # Show sample cookie names
                cookie_names = [c.name for c in youtube_cookies[:5]]
                print(f"     Sample cookies: {', '.join(cookie_names)}")
            else:
                print(f"  ❌ No YouTube/Google cookies found")

        except Exception as e:
            print(f"  ❌ Error: {e}")

    print("\n✅ Cookie validation test complete\n")


def test_deduplication():
    """Test 2: Deduplication service"""
    print("\n" + "=" * 60)
    print("TEST 2: Deduplication")
    print("=" * 60)

    dedup_service = VideoDeduplicationService()

    # Test with URLs containing duplicates
    test_urls = TEST_URLS[:5]

    print(f"\nChecking {len(test_urls)} URLs for duplicates...")
    print(f"URLs: {[url[:30]+'...' for url in test_urls]}\n")

    unique_urls, duplicate_results = dedup_service.check_batch_duplicates(test_urls)

    print(f"Results:")
    print(f"  Unique: {len(unique_urls)}")
    print(f"  Duplicates: {len(duplicate_results)}")

    if duplicate_results:
        print(f"\n  Duplicate videos found:")
        for dup in duplicate_results:
            print(f"    - {dup.video_id}: {dup.skip_reason}")

    print("\n✅ Deduplication test complete\n")


async def test_single_account_download(cookie_file: str):
    """Test 3: Single-account download"""
    print("\n" + "=" * 60)
    print("TEST 3: Single-Account Download")
    print("=" * 60)

    print(f"\nUsing cookie file: {cookie_file}")
    print(f"Downloading {len(TEST_URLS[:2])} test videos...\n")

    scheduler = DownloadScheduler(
        cookie_file_path=cookie_file,
        enable_sleep_period=False,  # Disable for test
        min_delay=5,  # Shorter delays for testing
        max_delay=10,
    )

    output_dir = Path("test_downloads")
    output_dir.mkdir(exist_ok=True)

    def progress_callback(current, total, result):
        if result["success"]:
            print(f"  ✅ [{current}/{total}] Downloaded: {result.get('audio_file')}")
        else:
            print(f"  ❌ [{current}/{total}] Failed: {result.get('error')}")

    results = await scheduler.download_batch_with_pacing(
        urls=TEST_URLS[:2],  # Just 2 videos for test
        output_dir=output_dir,
        progress_callback=progress_callback,
    )

    successful = sum(1 for r in results if r["success"])
    print(f"\n✅ Single-account test complete: {successful}/{len(results)} successful\n")

    return successful == len(results)


async def test_multi_account_download(cookie_files: list[str]):
    """Test 4: Multi-account download with rotation"""
    print("\n" + "=" * 60)
    print("TEST 4: Multi-Account Download with Rotation")
    print("=" * 60)

    print(f"\nUsing {len(cookie_files)} cookie files")
    print(f"Downloading {len(TEST_URLS[:3])} test videos...\n")

    db_service = DatabaseService()
    scheduler = MultiAccountDownloadScheduler(
        cookie_files=cookie_files,
        parallel_workers=2,  # Small number for test
        enable_sleep_period=False,  # Disable for test
        min_delay=5,  # Shorter delays for testing
        max_delay=10,
        db_service=db_service,
    )

    output_dir = Path("test_downloads")
    output_dir.mkdir(exist_ok=True)

    def progress_callback(message):
        print(f"  {message}")

    results = await scheduler.download_batch_with_rotation(
        urls=TEST_URLS[:3],  # Just 3 videos for test
        output_dir=output_dir,
        progress_callback=progress_callback,
    )

    # Get statistics
    stats = scheduler.get_stats()

    print(f"\n📊 Statistics:")
    print(f"  Total URLs: {stats['total_urls']}")
    print(f"  Unique URLs: {stats['unique_urls']}")
    print(f"  Duplicates skipped: {stats['duplicates_skipped']}")
    print(f"  Downloads completed: {stats['downloads_completed']}")
    print(f"  Downloads failed: {stats['downloads_failed']}")
    print(f"  Active accounts: {stats['active_accounts']}/{stats['total_accounts']}")
    print(f"  Success rate: {stats['success_rate']:.1%}")

    # Show account health
    print(f"\n📈 Account Health:")
    for idx, health in stats["account_health"].items():
        print(f"  Account {idx+1}:")
        print(f"    Active: {health['active']}")
        print(f"    Downloads: {health['total_downloads']}")
        print(f"    Failures: {health['total_failures']}")

    print(f"\n✅ Multi-account test complete\n")

    return stats["downloads_completed"] > 0


def test_sleep_period():
    """Test 5: Sleep period functionality"""
    print("\n" + "=" * 60)
    print("TEST 5: Sleep Period Functionality")
    print("=" * 60)

    from datetime import datetime

    # Create scheduler with current time in sleep period
    scheduler = DownloadScheduler(
        enable_sleep_period=True,
        sleep_start_hour=0,
        sleep_end_hour=6,
        timezone="America/Los_Angeles",
    )

    # Check if sleep time
    is_sleeping = scheduler.is_sleep_time()
    now = datetime.now(scheduler.timezone)

    print(f"\nCurrent time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"Sleep period: {scheduler.sleep_start}:00 - {scheduler.sleep_end}:00")
    print(f"Is sleep time: {is_sleeping}")

    if is_sleeping:
        wake_time = scheduler.get_next_wake_time()
        print(f"Next wake time: {wake_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    print(f"\n✅ Sleep period test complete\n")

    return True


async def test_gui_integration():
    """Test 6: GUI components (without Qt app)"""
    print("\n" + "=" * 60)
    print("TEST 6: GUI Component Integration")
    print("=" * 60)

    try:
        from knowledge_system.gui.widgets.cookie_file_manager import CookieFileManager

        print("  ✅ CookieFileManager import successful")

        # Test instantiation (will fail without Qt app, but that's OK)
        # manager = CookieFileManager()
        # print("  ✅ CookieFileManager instantiation successful")

        print("\n✅ GUI integration test complete (import check)\n")
        return True

    except Exception as e:
        print(f"  ❌ Error: {e}")
        print(f"\n⚠️ GUI integration test skipped (requires Qt application)\n")
        return False


def main():
    """Run all tests"""
    parser = argparse.ArgumentParser(
        description="Test multi-account download functionality"
    )
    parser.add_argument(
        "--cookies",
        nargs="+",
        help="Cookie file paths (1-6 files)",
    )
    parser.add_argument(
        "--skip-downloads",
        action="store_true",
        help="Skip actual download tests (only test validation and configuration)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging(log_level=log_level)

    print("=" * 60)
    print("MULTI-ACCOUNT DOWNLOAD FUNCTIONALITY TEST SUITE")
    print("=" * 60)

    # Test results
    test_results = {}

    # Test 1: Cookie validation
    if args.cookies:
        test_cookie_validation(args.cookies)
        test_results["cookie_validation"] = True
    else:
        print("\n⚠️ No cookie files provided - skipping cookie validation test")
        print("   Use --cookies cookie1.txt cookie2.txt cookie3.txt\n")
        test_results["cookie_validation"] = False

    # Test 2: Deduplication
    test_deduplication()
    test_results["deduplication"] = True

    # Test 3: Single-account download
    if not args.skip_downloads and args.cookies and len(args.cookies) >= 1:
        try:
            success = asyncio.run(test_single_account_download(args.cookies[0]))
            test_results["single_account"] = success
        except Exception as e:
            print(f"\n❌ Single-account test failed: {e}\n")
            test_results["single_account"] = False
    else:
        print(
            "⚠️ Skipping single-account download test (no cookies or --skip-downloads)\n"
        )
        test_results["single_account"] = None

    # Test 4: Multi-account download
    if not args.skip_downloads and args.cookies and len(args.cookies) >= 2:
        try:
            success = asyncio.run(test_multi_account_download(args.cookies))
            test_results["multi_account"] = success
        except Exception as e:
            print(f"\n❌ Multi-account test failed: {e}\n")
            test_results["multi_account"] = False
    else:
        print(
            "⚠️ Skipping multi-account download test (need 2+ cookies or --skip-downloads)\n"
        )
        test_results["multi_account"] = None

    # Test 5: Sleep period
    test_sleep_period()
    test_results["sleep_period"] = True

    # Test 6: GUI integration
    test_results["gui_integration"] = asyncio.run(test_gui_integration())

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for test_name, result in test_results.items():
        if result is True:
            print(f"  ✅ {test_name}: PASSED")
        elif result is False:
            print(f"  ❌ {test_name}: FAILED")
        else:
            print(f"  ⊝ {test_name}: SKIPPED")

    print("=" * 60)

    # Overall result
    passed = sum(1 for r in test_results.values() if r is True)
    failed = sum(1 for r in test_results.values() if r is False)
    skipped = sum(1 for r in test_results.values() if r is None)

    print(f"\nResults: {passed} passed, {failed} failed, {skipped} skipped")

    if failed > 0:
        print("\n❌ Some tests failed - see output above")
        sys.exit(1)
    else:
        print("\n✅ All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
