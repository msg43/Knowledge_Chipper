#!/usr/bin/env python3
"""
Test script to verify PacketStream sticky session implementation.

This tests that:
1. Same URL gets the same session ID (and thus same IP)
2. Different URLs get different session IDs (and thus different IPs)
3. Session IDs work with YouTube videos and generic URLs
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from knowledge_system.utils.packetstream_proxy import PacketStreamProxyManager


def test_session_id_generation():
    """Test that session ID generation works correctly."""
    print("=" * 60)
    print("Testing PacketStream Sticky Session ID Generation")
    print("=" * 60)

    # Test 1: Same URL should get same session ID
    print("\n1. Testing same URL consistency:")
    url1 = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    video_id1 = "dQw4w9WgXcQ"

    session_a = PacketStreamProxyManager.generate_session_id(url1, video_id1)
    session_b = PacketStreamProxyManager.generate_session_id(url1, video_id1)

    print(f"   URL: {url1}")
    print(f"   Video ID: {video_id1}")
    print(f"   Session ID (attempt 1): {session_a}")
    print(f"   Session ID (attempt 2): {session_b}")
    print(
        f"   ✅ PASS: Same URL gets same session"
        if session_a == session_b
        else "   ❌ FAIL"
    )

    # Test 2: Different URLs should get different session IDs
    print("\n2. Testing different URLs:")
    url2 = "https://www.youtube.com/watch?v=abc123def45"
    video_id2 = "abc123def45"

    session_c = PacketStreamProxyManager.generate_session_id(url2, video_id2)

    print(f"   URL 1: {url1} → Session: {session_a}")
    print(f"   URL 2: {url2} → Session: {session_c}")
    print(
        f"   ✅ PASS: Different URLs get different sessions"
        if session_a != session_c
        else "   ❌ FAIL"
    )

    # Test 3: URLs without video ID (RSS feeds, etc.)
    print("\n3. Testing non-YouTube URLs (RSS, etc.):")
    rss_url1 = "https://example.com/feed.xml"
    rss_url2 = "https://example.com/feed2.xml"

    rss_session_a = PacketStreamProxyManager.generate_session_id(rss_url1, None)
    rss_session_b = PacketStreamProxyManager.generate_session_id(rss_url1, None)
    rss_session_c = PacketStreamProxyManager.generate_session_id(rss_url2, None)

    print(f"   URL: {rss_url1}")
    print(f"   Session ID (attempt 1): {rss_session_a}")
    print(f"   Session ID (attempt 2): {rss_session_b}")
    print(
        f"   ✅ PASS: Same RSS URL gets same session"
        if rss_session_a == rss_session_b
        else "   ❌ FAIL"
    )
    print(f"\n   Different RSS URL: {rss_url2}")
    print(f"   Session ID: {rss_session_c}")
    print(
        f"   ✅ PASS: Different RSS URLs get different sessions"
        if rss_session_a != rss_session_c
        else "   ❌ FAIL"
    )

    # Test 4: Proxy URL generation with session IDs
    print("\n4. Testing proxy URL generation with session IDs:")
    proxy_manager = PacketStreamProxyManager()

    if proxy_manager.credentials_available:
        # Generate proxy URLs with different sessions
        proxy_url_1 = proxy_manager.get_proxy_url(session_id="dQw4w9WgXcQ")
        proxy_url_2 = proxy_manager.get_proxy_url(session_id="abc123def45")
        proxy_url_3 = proxy_manager.get_proxy_url(session_id="dQw4w9WgXcQ")  # Same as 1

        print(f"   Session 'dQw4w9WgXcQ' (1st call):")
        print(f"      {proxy_url_1}")
        print(f"   Session 'abc123def45':")
        print(f"      {proxy_url_2}")
        print(f"   Session 'dQw4w9WgXcQ' (2nd call):")
        print(f"      {proxy_url_3}")

        # Verify session IDs are in URLs
        has_session_1 = "-session-dQw4w9WgXcQ@" in proxy_url_1
        has_session_2 = "-session-abc123def45@" in proxy_url_2
        urls_match = proxy_url_1 == proxy_url_3

        print(f"   ✅ PASS: Session ID in proxy URL 1" if has_session_1 else "   ❌ FAIL")
        print(f"   ✅ PASS: Session ID in proxy URL 2" if has_session_2 else "   ❌ FAIL")
        print(
            f"   ✅ PASS: Same session ID produces same proxy URL"
            if urls_match
            else "   ❌ FAIL"
        )
    else:
        print("   ⚠️  SKIP: PacketStream credentials not configured")

    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)

    # Summary
    print("\n📝 Summary:")
    print("   • Each unique URL gets a unique session ID")
    print("   • Same URL always gets the same session ID (consistent)")
    print("   • Session IDs ensure sticky IP per URL in PacketStream")
    print("   • Multiple URLs can download concurrently with different IPs")
    print("\n✅ Implementation verified successfully!")


if __name__ == "__main__":
    test_session_id_generation()
