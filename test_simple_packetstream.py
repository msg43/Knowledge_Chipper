#!/usr/bin/env python3
"""
Simple test to isolate the actual PacketStream proxy issue.
"""

import os

import requests


def test_packetstream_basics():
    """Test PacketStream proxy connection directly without yt-dlp complexity."""

    print("🔍 Testing PacketStream Proxy - Root Cause Analysis")
    print("=" * 55)

    # Step 1: Get credentials the same way the app does
    print("1. Getting PacketStream credentials...")
    try:
        from src.knowledge_system.config import get_settings

        settings = get_settings()

        username = getattr(settings.api_keys, "packetstream_username", None)
        auth_key = getattr(settings.api_keys, "packetstream_auth_key", None)

        print(f"   Username: {username}")
        print(f"   Auth Key: {'*' * len(auth_key) if auth_key else 'None'}")

        if not username or not auth_key:
            print("   ❌ No credentials found in settings")
            return False

    except Exception as e:
        print(f"   ❌ Error getting credentials: {e}")
        return False

    # Step 2: Test the exact proxy URL format used by yt-dlp
    print("\n2. Testing proxy URL format...")

    proxy_url = f"http://{username}:{auth_key}@proxy.packetstream.io:31112"
    print(f"   Proxy URL: http://{username}:***@proxy.packetstream.io:31112")

    # Step 3: Test simple HTTP request through proxy
    print("\n3. Testing basic proxy connection...")

    proxies = {"http": proxy_url, "https": proxy_url}

    try:
        # Simple IP check
        response = requests.get("https://httpbin.org/ip", proxies=proxies, timeout=10)
        if response.status_code == 200:
            ip_data = response.json()
            print(f"   ✅ Proxy connection successful!")
            print(f"   Proxy IP: {ip_data.get('origin', 'Unknown')}")
        else:
            print(f"   ❌ Proxy returned status: {response.status_code}")
            return False

    except Exception as e:
        print(f"   ❌ Proxy connection failed: {e}")
        return False

    # Step 4: Test YouTube-specific request through proxy
    print("\n4. Testing YouTube access through proxy...")

    youtube_url = "https://www.youtube.com/watch?v=TU3VHYDTE10"

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        response = requests.get(
            youtube_url, proxies=proxies, headers=headers, timeout=15
        )
        print(f"   Status: {response.status_code}")

        if response.status_code == 200:
            print(f"   ✅ YouTube accessible through proxy!")
            content_size = len(response.content)
            print(f"   Content size: {content_size:,} bytes")

            # Check if we got actual video page content
            if "ytInitialData" in response.text or "videoDetails" in response.text:
                print(f"   ✅ Got YouTube video page data!")
            else:
                print(f"   ⚠️ Response doesn't look like video page")

        else:
            print(f"   ❌ YouTube returned: {response.status_code}")
            print(f"   Response preview: {response.text[:200]}")
            return False

    except Exception as e:
        print(f"   ❌ YouTube request failed: {e}")
        return False

    # Step 5: Test the exact yt-dlp scenario
    print("\n5. Testing yt-dlp with proxy...")

    try:
        import yt_dlp

        ydl_opts = {
            "quiet": True,
            "proxy": proxy_url,
            "socket_timeout": 30,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"   Testing yt-dlp extraction...")
            info = ydl.extract_info(youtube_url, download=False)

        if info:
            print(f"   ✅ yt-dlp extraction successful!")
            print(f"   Video title: {info.get('title', 'Unknown')}")
            print(f"   Video ID: {info.get('id', 'Unknown')}")
            return True
        else:
            print(f"   ❌ yt-dlp returned no info")
            return False

    except Exception as e:
        print(f"   ❌ yt-dlp failed: {e}")
        return False


if __name__ == "__main__":
    success = test_packetstream_basics()
    if success:
        print(f"\n🎉 PacketStream proxy is working correctly!")
        print(f"   The issue must be in how the app is using it.")
    else:
        print(f"\n❌ PacketStream proxy has a fundamental issue.")
        print(f"   Check credentials, account status, or proxy settings.")
