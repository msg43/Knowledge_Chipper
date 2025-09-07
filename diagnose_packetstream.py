#!/usr/bin/env python3
"""
Comprehensive PacketStream diagnosis to find the exact issue.
"""

import socket
import time

import requests


def diagnose_packetstream():
    """Run comprehensive PacketStream diagnostics."""

    print("🔬 PacketStream Comprehensive Diagnosis")
    print("=" * 45)

    # Get credentials
    try:
        from src.knowledge_system.config import get_settings

        settings = get_settings()
        username = getattr(settings.api_keys, "packetstream_username", None)
        auth_key = getattr(settings.api_keys, "packetstream_auth_key", None)

        if not username or not auth_key:
            print("❌ No credentials found")
            return False

        print(f"Using credentials: {username}:{'*' * len(auth_key)}")

    except Exception as e:
        print(f"❌ Error getting credentials: {e}")
        return False

    # Test 1: DNS resolution
    print("\n1. Testing DNS resolution...")
    try:
        ip = socket.gethostbyname("proxy.packetstream.io")
        print(f"   ✅ proxy.packetstream.io resolves to: {ip}")
    except Exception as e:
        print(f"   ❌ DNS resolution failed: {e}")
        return False

    # Test 2: Port connectivity
    print("\n2. Testing port connectivity...")
    ports_to_test = [31111, 31112, 31113, 8080, 3128]

    for port in ports_to_test:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex(("proxy.packetstream.io", port))
            sock.close()

            if result == 0:
                print(f"   ✅ Port {port}: OPEN")
            else:
                print(f"   ❌ Port {port}: CLOSED/FILTERED")
        except Exception as e:
            print(f"   ❌ Port {port}: ERROR - {e}")

    # Test 3: Different proxy URL formats
    print("\n3. Testing different proxy URL formats...")

    formats_to_test = [
        f"http://{username}:{auth_key}@proxy.packetstream.io:31111",
        f"http://{username}:{auth_key}@proxy.packetstream.io:31112",
        f"http://{username}:{auth_key}@proxy.packetstream.io:31113",
        f"socks5://{username}:{auth_key}@proxy.packetstream.io:31111",
        f"socks5://{username}:{auth_key}@proxy.packetstream.io:31113",
        f"http://{auth_key}:{username}@proxy.packetstream.io:31111",  # Reversed auth
        f"http://{username}@proxy.packetstream.io:31111",  # No password
    ]

    for i, proxy_url in enumerate(formats_to_test, 1):
        print(f"\n   Format {i}: {proxy_url.split('@')[0]}@***")

        try:
            proxies = {"http": proxy_url, "https": proxy_url}
            response = requests.get(
                "http://httpbin.org/ip", proxies=proxies, timeout=10
            )

            if response.status_code == 200:
                ip_data = response.json()
                print(f"   ✅ SUCCESS! Proxy IP: {ip_data.get('origin', 'Unknown')}")

                # If this format works, test YouTube
                print(f"   🎬 Testing YouTube with this format...")
                try:
                    youtube_response = requests.get(
                        "https://www.youtube.com/watch?v=TU3VHYDTE10",
                        proxies=proxies,
                        headers={
                            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                        },
                        timeout=15,
                    )
                    if youtube_response.status_code == 200:
                        print(f"   ✅ YouTube also works with this format!")
                        return proxy_url  # Return working format
                    else:
                        print(f"   ⚠️ YouTube failed: {youtube_response.status_code}")
                except Exception as yt_e:
                    print(f"   ⚠️ YouTube test failed: {yt_e}")

            else:
                print(f"   ❌ Failed: HTTP {response.status_code}")

        except requests.exceptions.ProxyError as e:
            print(f"   ❌ Proxy error: {e}")
        except requests.exceptions.ConnectTimeout:
            print(f"   ❌ Connection timeout")
        except requests.exceptions.ConnectionError as e:
            print(f"   ❌ Connection error: {e}")
        except Exception as e:
            print(f"   ❌ Other error: {e}")

    # Test 4: Alternative PacketStream endpoints
    print("\n4. Testing alternative endpoints...")

    alt_endpoints = [
        "proxy-us.packetstream.io",
        "proxy-eu.packetstream.io",
        "proxy1.packetstream.io",
        "proxy2.packetstream.io",
        "residential.packetstream.io",
    ]

    for endpoint in alt_endpoints:
        print(f"\n   Testing {endpoint}:31111...")
        try:
            # Test DNS first
            ip = socket.gethostbyname(endpoint)
            print(f"   DNS: {endpoint} → {ip}")

            # Test connection
            proxy_url = f"http://{username}:{auth_key}@{endpoint}:31111"
            proxies = {"http": proxy_url, "https": proxy_url}

            response = requests.get("http://httpbin.org/ip", proxies=proxies, timeout=8)
            if response.status_code == 200:
                ip_data = response.json()
                print(f"   ✅ {endpoint} WORKS! IP: {ip_data.get('origin')}")
                return proxy_url
            else:
                print(f"   ❌ HTTP {response.status_code}")

        except socket.gaierror:
            print(f"   ❌ DNS lookup failed for {endpoint}")
        except Exception as e:
            print(f"   ❌ {endpoint} failed: {e}")

    # Test 5: Check if it's a session/timing issue
    print("\n5. Testing session persistence...")

    proxy_url = f"http://{username}:{auth_key}@proxy.packetstream.io:31111"
    session = requests.Session()
    session.proxies = {"http": proxy_url, "https": proxy_url}

    for attempt in range(3):
        print(f"\n   Attempt {attempt + 1}:")
        try:
            response = session.get("http://httpbin.org/ip", timeout=10)
            if response.status_code == 200:
                ip_data = response.json()
                print(
                    f"   ✅ Session attempt {attempt + 1} successful: {ip_data.get('origin')}"
                )
                return proxy_url
            else:
                print(f"   ❌ Attempt {attempt + 1} failed: HTTP {response.status_code}")
        except Exception as e:
            print(f"   ❌ Attempt {attempt + 1} error: {e}")

        if attempt < 2:
            time.sleep(2)

    print("\n❌ All PacketStream tests failed!")
    print("\n💡 Possible issues:")
    print("   • Account not properly activated")
    print("   • Wrong credential format")
    print("   • Service temporarily down")
    print("   • Network/firewall blocking")
    print("   • PacketStream changed their endpoints")

    return False


if __name__ == "__main__":
    working_format = diagnose_packetstream()
    if working_format:
        print(f"\n🎉 Found working format: {working_format}")
        print(f"📝 Update your proxy configuration to use this format!")
    else:
        print(f"\n📞 Contact PacketStream support with these test results.")
