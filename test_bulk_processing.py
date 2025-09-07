#!/usr/bin/env python3
"""
Test bulk processing capabilities of the YouTube dataset.
"""

import json

import requests


def test_bulk_processing():
    """Test if the dataset supports bulk URL processing."""

    api_key = "ed14d427de1f0186066bbbc3d948808642f1a43c57c79d6259a2438f54e8de51"
    dataset_id = "gd_lk538t2k2p1k3oos71"

    # Test with multiple URLs to see if bulk processing is supported
    test_urls = [
        "https://www.youtube.com/watch?v=ksHkSuNTIKo",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/watch?v=kJQP7kiw5Fk",
        "https://www.youtube.com/watch?v=9bZkp7q19f0",
        "https://www.youtube.com/watch?v=oHg5SJYRHA0",
    ]

    print("🧪 Testing Bulk Processing Capabilities")
    print("=" * 50)
    print(f"Dataset ID: {dataset_id}")
    print(f"Test URLs: {len(test_urls)} videos")
    print()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Test 1: Multiple URLs in one trigger
    trigger_url = f"https://api.brightdata.com/datasets/v3/trigger?dataset_id={dataset_id}&format=json"

    # Payload with multiple URLs
    bulk_payload = [{"url": url} for url in test_urls]

    print(f"🚀 Test 1: Bulk Trigger ({len(test_urls)} URLs in one request)")
    print(f"   Endpoint: {trigger_url}")
    print(f"   Payload size: {len(bulk_payload)} items")

    try:
        response = requests.post(
            trigger_url, headers=headers, json=bulk_payload, timeout=30
        )

        print(f"   Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            snapshot_id = data.get("snapshot_id")
            print(f"   ✅ SUCCESS! Bulk trigger accepted")
            print(f"   📊 Snapshot ID: {snapshot_id}")

            # Check snapshot status to understand processing
            status_url = (
                f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}"
            )

            print(f"\n📊 Checking bulk processing status...")
            status_response = requests.get(status_url, headers=headers, timeout=15)
            print(f"   Status check: {status_response.status_code}")

            if status_response.status_code in [200, 202]:
                print(f"   ✅ Bulk processing initiated successfully!")
                print(f"   💡 This means you CAN process multiple URLs in one request")

                # Estimate processing time
                estimated_time = len(test_urls) * 45  # 45 seconds per video
                print(
                    f"   ⏱️  Estimated processing time: {estimated_time} seconds ({estimated_time/60:.1f} minutes)"
                )

                return True
            else:
                print(f"   ⚠️  Status check failed: {status_response.text[:100]}")

        elif response.status_code == 400:
            error = response.json()
            print(f"   ❌ Bad Request: {error}")
            if "too many" in str(error).lower() or "limit" in str(error).lower():
                print(f"   💡 There may be a limit on bulk size")

        else:
            print(f"   ❌ Failed: {response.status_code}")
            try:
                error = response.json()
                print(f"   Error: {error}")
            except:
                print(f"   Response: {response.text[:200]}")

    except Exception as e:
        print(f"   ❌ Exception: {str(e)}")

    print(f"\n🔄 Test 2: Individual Triggers (for comparison)")

    # Test individual triggers to compare
    individual_snapshots = []
    for i, url in enumerate(test_urls[:2]):  # Test just 2 for speed
        print(f"   {i+1}. Triggering: {url}")

        try:
            single_payload = [{"url": url}]
            response = requests.post(
                trigger_url, headers=headers, json=single_payload, timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                snapshot_id = data.get("snapshot_id")
                individual_snapshots.append(snapshot_id)
                print(f"      ✅ Snapshot: {snapshot_id}")
            else:
                print(f"      ❌ Failed: {response.status_code}")

        except Exception as e:
            print(f"      ❌ Error: {str(e)[:50]}")

    print(f"\n📊 Analysis:")
    print(f"   Individual snapshots created: {len(individual_snapshots)}")

    if len(individual_snapshots) > 0:
        print(f"   💡 For 1000 URLs using individual calls:")
        print(f"     - 1000 separate API requests")
        print(f"     - ~45 seconds processing per video")
        print(f"     - Sequential: ~12.5 hours total")
        print(f"     - Parallel (10 concurrent): ~75 minutes")
        print(f"     - Parallel (20 concurrent): ~38 minutes")

    return False


if __name__ == "__main__":
    supports_bulk = test_bulk_processing()

    print(f"\n💡 Recommendations for 1000 URLs:")

    if supports_bulk:
        print(f"   🚀 BULK PROCESSING SUPPORTED:")
        print(f"     - Submit all 1000 URLs in one request")
        print(f"     - Wait for bulk processing to complete")
        print(f"     - Much more efficient than individual calls")
    else:
        print(f"   ⚡ PARALLEL PROCESSING RECOMMENDED:")
        print(f"     - Process 10-20 videos concurrently")
        print(f"     - Use asyncio or threading")
        print(f"     - Monitor rate limits")
        print(f"     - Total time: 30-75 minutes")

    print(f"\n🎯 Implementation Strategy:")
    print(f"   1. Test with 10-20 URLs first")
    print(f"   2. Monitor processing times and success rates")
    print(f"   3. Optimize batch size based on results")
    print(f"   4. Scale up to full 1000 URL processing")
