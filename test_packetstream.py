#!/usr/bin/env python3
"""
Test PacketStream proxy effectiveness with YouTube
"""
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

import yt_dlp

from src.knowledge_system.utils.packetstream_proxy import PacketStreamProxyManager


def test_single_download():
    """Test a single download with PacketStream proxy"""
    # Test URL - a short public domain video
    test_url = "https://www.youtube.com/watch?v=aqz-KE-bpKQ"  # Big Buck Bunny trailer

    # Initialize proxy
    proxy_manager = PacketStreamProxyManager()

    if not proxy_manager.credentials_available:
        print("❌ PacketStream credentials not configured")
        print(
            "   Set PACKETSTREAM_USERNAME and PACKETSTREAM_AUTH_KEY environment variables"
        )
        return False

    proxy_url = proxy_manager.get_proxy_url()
    print(f"✅ PacketStream proxy configured")
    print(f"🌐 Testing download with proxy...")

    # Test with yt-dlp
    ydl_opts = {
        "quiet": False,
        "no_warnings": False,
        "extract_flat": True,  # Just get metadata, don't download
        "proxy": proxy_url,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(test_url, download=False)
            if info:
                print(f"✅ Successfully accessed video: {info.get('title', 'Unknown')}")
                print(f"   Duration: {info.get('duration', 0)} seconds")
                print(f"   Channel: {info.get('channel', 'Unknown')}")
                return True
            else:
                print("❌ Failed to extract video info")
                return False

    except Exception as e:
        print(f"❌ Error: {e}")
        if "Sign in to confirm" in str(e):
            print("   YouTube detected bot activity - PacketStream IPs may be flagged")
        elif "429" in str(e):
            print("   Rate limited - too many requests")
        elif "403" in str(e):
            print("   Access forbidden - proxy may be blocked")
        return False


def test_multiple_sequential():
    """Test multiple downloads sequentially to check consistency"""
    test_urls = [
        "https://www.youtube.com/watch?v=aqz-KE-bpKQ",  # Big Buck Bunny
        "https://www.youtube.com/watch?v=jNQXAC9IVRw",  # Me at the zoo (first YouTube video)
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # Rick Roll (testing popular video)
    ]

    proxy_manager = PacketStreamProxyManager()
    if not proxy_manager.credentials_available:
        print("❌ PacketStream not configured")
        return

    proxy_url = proxy_manager.get_proxy_url()
    success_count = 0

    print("🧪 Testing multiple sequential downloads...")
    print("-" * 50)

    for i, url in enumerate(test_urls, 1):
        print(f"\nTest {i}/3: {url}")

        ydl_opts = {
            "quiet": True,
            "extract_flat": True,
            "proxy": proxy_url,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info:
                    print(f"✅ Success: {info.get('title', 'Unknown')[:50]}...")
                    success_count += 1
                else:
                    print("❌ Failed to get info")
        except Exception as e:
            error_msg = str(e)[:100]
            print(f"❌ Error: {error_msg}")

        # Small delay between requests
        import time

        time.sleep(2)

    print("\n" + "=" * 50)
    print(f"Results: {success_count}/3 successful")

    if success_count == 0:
        print("🚫 PacketStream appears to be completely blocked by YouTube")
    elif success_count < len(test_urls):
        print("⚠️  PacketStream partially working but unreliable")
    else:
        print("✅ PacketStream working well with YouTube")


if __name__ == "__main__":
    print("PacketStream YouTube Compatibility Test")
    print("=" * 50)

    # Test 1: Single download
    if test_single_download():
        print("\n✅ Basic test passed, trying multiple downloads...")
        # Test 2: Multiple sequential
        test_multiple_sequential()
    else:
        print("\n❌ Basic test failed - PacketStream may be blocked")

    print("\n" + "=" * 50)
    print("Test complete. Check results above.")
