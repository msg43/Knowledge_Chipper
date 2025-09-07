#!/usr/bin/env python3
"""
Test PacketStream proxy connection to diagnose the connection issues.
"""

import time

import requests


def test_packetstream_connection():
    """Test PacketStream proxy connection and configuration."""

    print("🧪 Testing PacketStream Proxy Connection")
    print("=" * 45)

    try:
        from src.knowledge_system.utils.packetstream_proxy import (
            PacketStreamProxyManager,
        )

        # Test 1: Initialize proxy manager
        print("1. Testing proxy manager initialization...")
        try:
            proxy_manager = PacketStreamProxyManager()
            print(f"   ✅ Proxy manager initialized")
            print(f"   Username: {proxy_manager.username}")
            print(
                f"   Auth key: {'*' * len(proxy_manager.auth_key) if proxy_manager.auth_key else 'None'}"
            )
        except Exception as e:
            print(f"   ❌ Failed to initialize: {e}")
            return False

        # Test 2: Test proxy configuration
        print("\n2. Testing proxy configuration...")

        # Test HTTP proxy
        http_config = proxy_manager._get_proxy_config(use_socks5=False)
        print(f"   HTTP proxy config: {http_config}")

        # Test SOCKS5 proxy
        socks5_config = proxy_manager._get_proxy_config(use_socks5=True)
        print(f"   SOCKS5 proxy config: {socks5_config}")

        # Test 3: Test basic proxy connection
        print("\n3. Testing basic proxy connection...")

        test_urls = [
            "https://httpbin.org/ip",  # Simple IP check
            "https://www.google.com",  # Basic connectivity
        ]

        for i, test_url in enumerate(test_urls, 1):
            print(f"\n   Test {i}: {test_url}")

            try:
                # Test with HTTP proxy
                session = proxy_manager.create_session(session_id=f"test_{i}")
                response = session.get(test_url, timeout=10)

                if response.status_code == 200:
                    print(
                        f"   ✅ HTTP proxy connection successful (status: {response.status_code})"
                    )
                    if "httpbin" in test_url:
                        try:
                            ip_info = response.json()
                            print(f"   📍 Proxy IP: {ip_info.get('origin', 'Unknown')}")
                        except:
                            pass
                else:
                    print(f"   ⚠️ HTTP proxy returned status: {response.status_code}")

            except Exception as e:
                print(f"   ❌ HTTP proxy failed: {str(e)[:100]}")

        # Test 4: Test YouTube API endpoint specifically
        print("\n4. Testing YouTube API endpoint...")

        youtube_test_urls = [
            "https://www.youtube.com/watch?v=TU3VHYDTE10",
            "https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=TU3VHYDTE10&format=json",
        ]

        for i, test_url in enumerate(youtube_test_urls, 1):
            print(f"\n   YouTube Test {i}: {test_url[:50]}...")

            try:
                session = proxy_manager.create_session(session_id=f"yt_test_{i}")
                response = session.get(test_url, timeout=15)

                print(f"   Status: {response.status_code}")
                if response.status_code == 200:
                    print(f"   ✅ YouTube API accessible via proxy")
                    content_length = len(response.content)
                    print(f"   Content length: {content_length} bytes")
                else:
                    print(f"   ⚠️ YouTube API returned: {response.status_code}")
                    print(f"   Response: {response.text[:200]}")

            except Exception as e:
                print(f"   ❌ YouTube API test failed: {str(e)[:100]}")

        # Test 5: Test yt-dlp proxy format
        print("\n5. Testing yt-dlp proxy format...")

        try:
            proxy_config = proxy_manager._get_proxy_config(use_socks5=False)
            proxy_url = proxy_config["https"]

            print(f"   yt-dlp proxy URL: {proxy_url}")

            # Validate proxy URL format for yt-dlp
            if proxy_url.startswith("http://") and "@" in proxy_url:
                print(f"   ✅ Proxy URL format looks correct for yt-dlp")
            else:
                print(f"   ❌ Proxy URL format may be incorrect for yt-dlp")

        except Exception as e:
            print(f"   ❌ Proxy format test failed: {e}")

        print("\n🎉 PacketStream connection test completed!")
        return True

    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False


if __name__ == "__main__":
    test_packetstream_connection()
