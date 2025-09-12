#!/usr/bin/env python3
"""
Test if PacketStream provides different IPs for concurrent sessions
"""
import concurrent.futures
import sys
import time
from pathlib import Path

import requests

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from src.knowledge_system.utils.packetstream_proxy import PacketStreamProxyManager


def get_ip_with_session(session_id):
    """Get external IP using a specific session"""
    try:
        proxy_manager = PacketStreamProxyManager()
        proxy_url = proxy_manager.get_proxy_url()

        if not proxy_url:
            return session_id, "No proxy URL", None

        # Create session with proxy
        session = requests.Session()
        session.proxies = {"http": proxy_url, "https": proxy_url}
        session.timeout = 10

        # Get external IP
        response = session.get("https://httpbin.org/ip")
        ip_data = response.json()
        external_ip = ip_data.get("origin", "Unknown")

        return session_id, external_ip, None

    except Exception as e:
        return session_id, None, str(e)


def test_concurrent_ips():
    """Test if multiple concurrent sessions get different IPs"""
    print("Testing PacketStream IP Distribution")
    print("=" * 50)

    proxy_manager = PacketStreamProxyManager()
    if not proxy_manager.credentials_available:
        print("❌ PacketStream credentials not configured")
        print(
            "   Set PACKETSTREAM_USERNAME and PACKETSTREAM_AUTH_KEY environment variables"
        )
        return

    print(f"✅ PacketStream credentials configured")
    print(f"🧪 Testing IP allocation across multiple concurrent sessions...")
    print("-" * 50)

    # Test with different numbers of concurrent sessions
    session_counts = [3, 5, 8, 12]

    for num_sessions in session_counts:
        print(f"\nTesting {num_sessions} concurrent sessions:")

        # Create session IDs
        session_ids = [
            f"test_session_{i}_{int(time.time())}" for i in range(num_sessions)
        ]

        # Get IPs concurrently
        ips = {}
        errors = []

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=num_sessions
        ) as executor:
            # Submit all requests at once
            future_to_session = {
                executor.submit(get_ip_with_session, session_id): session_id
                for session_id in session_ids
            }

            # Collect results
            for future in concurrent.futures.as_completed(future_to_session):
                session_id, ip, error = future.result()
                if error:
                    errors.append(f"{session_id}: {error}")
                elif ip:
                    ips[session_id] = ip

        # Analyze results
        unique_ips = set(ips.values())

        print(f"   Sessions attempted: {num_sessions}")
        print(f"   Successful responses: {len(ips)}")
        print(f"   Unique IPs obtained: {len(unique_ips)}")
        print(f"   Errors: {len(errors)}")

        if len(ips) > 0:
            print(f"   IP distribution:")
            ip_counts = {}
            for ip in ips.values():
                ip_counts[ip] = ip_counts.get(ip, 0) + 1

            for ip, count in ip_counts.items():
                print(f"     {ip}: {count} session(s)")

        if errors:
            print(f"   Error details:")
            for error in errors[:3]:  # Show first 3 errors
                print(f"     {error}")

        # Analysis
        if len(unique_ips) == len(ips):
            print(f"   ✅ Perfect: Each session got a different IP")
        elif len(unique_ips) > 1:
            print(
                f"   ⚠️  Partial: Got {len(unique_ips)} different IPs for {len(ips)} sessions"
            )
        elif len(unique_ips) == 1:
            print(f"   ❌ Poor: All sessions got the same IP ({list(unique_ips)[0]})")
        else:
            print(f"   ❌ Failed: No successful IP retrievals")

        # Small delay between tests
        time.sleep(2)


def test_sequential_vs_concurrent():
    """Compare IP allocation between sequential and concurrent requests"""
    print("\n" + "=" * 50)
    print("Sequential vs Concurrent IP Allocation Test")
    print("=" * 50)

    proxy_manager = PacketStreamProxyManager()
    if not proxy_manager.credentials_available:
        return

    # Test 1: Sequential requests
    print("\n1. Sequential requests (5 requests, 2 seconds apart):")
    sequential_ips = []
    for i in range(5):
        session_id, ip, error = get_ip_with_session(f"sequential_{i}")
        if ip:
            sequential_ips.append(ip)
            print(f"   Request {i+1}: {ip}")
        else:
            print(f"   Request {i+1}: Error - {error}")
        time.sleep(2)

    seq_unique = len(set(sequential_ips))
    print(f"   Sequential unique IPs: {seq_unique}/{len(sequential_ips)}")

    # Test 2: Concurrent requests
    print("\n2. Concurrent requests (5 requests at once):")
    session_ids = [f"concurrent_{i}" for i in range(5)]
    concurrent_ips = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(get_ip_with_session, sid) for sid in session_ids]
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            session_id, ip, error = future.result()
            if ip:
                concurrent_ips.append(ip)
                print(f"   Request {i+1}: {ip}")
            else:
                print(f"   Request {i+1}: Error - {error}")

    conc_unique = len(set(concurrent_ips))
    print(f"   Concurrent unique IPs: {conc_unique}/{len(concurrent_ips)}")

    # Comparison
    print(f"\n📊 Comparison:")
    print(f"   Sequential: {seq_unique}/5 unique IPs")
    print(f"   Concurrent: {conc_unique}/5 unique IPs")

    if conc_unique >= seq_unique:
        print("   ✅ Concurrent requests get at least as many unique IPs")
    else:
        print(
            "   ⚠️  Sequential requests get more unique IPs - PacketStream may have concurrency limits"
        )


if __name__ == "__main__":
    test_concurrent_ips()
    test_sequential_vs_concurrent()

    print("\n" + "=" * 50)
    print("Summary:")
    print(
        "- If you see mostly the same IP: PacketStream may not rotate IPs as expected"
    )
    print("- If you see different IPs: PacketStream IP rotation is working")
    print(
        "- Compare concurrent vs sequential to understand their IP allocation strategy"
    )
    print("=" * 50)
