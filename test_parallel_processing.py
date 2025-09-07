#!/usr/bin/env python3
"""
Test if Bright Data processes batch URLs in parallel or sequentially.
"""

import json
import time
from datetime import datetime

import requests


def test_parallel_vs_sequential():
    """Test processing behavior to determine if batches run in parallel."""

    api_key = "ed14d427de1f0186066bbbc3d948808642f1a43c57c79d6259a2438f54e8de51"
    dataset_id = "gd_lk538t2k2p1k3oos71"

    # Test URLs of different complexity
    test_urls = [
        "https://www.youtube.com/watch?v=ksHkSuNTIKo",  # Test video 1
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # Rick Roll (famous, likely cached)
        "https://www.youtube.com/watch?v=kJQP7kiw5Fk",  # Test video 2
        "https://www.youtube.com/watch?v=9bZkp7q19f0",  # Test video 3
    ]

    print("🧪 Testing Parallel vs Sequential Processing")
    print("=" * 60)
    print(f"Dataset ID: {dataset_id}")
    print()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    trigger_url = f"https://api.brightdata.com/datasets/v3/trigger?dataset_id={dataset_id}&format=json"

    # Test 1: Single URL processing time
    print("🕐 Test 1: Single URL Processing Time")
    print("-" * 40)

    single_times = []
    for i, url in enumerate(test_urls[:2], 1):  # Test 2 URLs individually
        print(f"   {i}. Processing: {url}")

        start_time = time.time()

        try:
            # Trigger single URL
            single_payload = [{"url": url}]
            response = requests.post(
                trigger_url, headers=headers, json=single_payload, timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                snapshot_id = data.get("snapshot_id")
                print(f"      Snapshot: {snapshot_id}")

                # Poll until completion
                status_url = (
                    f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}"
                )

                while True:
                    time.sleep(5)  # Check every 5 seconds

                    poll_response = requests.get(
                        status_url, headers=headers, timeout=15
                    )

                    if poll_response.status_code == 200 and poll_response.text.strip():
                        # Data ready
                        processing_time = time.time() - start_time
                        single_times.append(processing_time)
                        print(f"      ✅ Completed in {processing_time:.1f} seconds")
                        break
                    elif poll_response.status_code == 404:
                        print(f"      ❌ Snapshot expired")
                        break
                    elif time.time() - start_time > 180:  # 3 minute timeout
                        print(f"      ⏱️  Timeout after 3 minutes")
                        break

            else:
                print(f"      ❌ Trigger failed: {response.status_code}")

        except Exception as e:
            print(f"      ❌ Error: {str(e)[:50]}")

    # Test 2: Batch processing time
    print(f"\n🕐 Test 2: Batch Processing Time ({len(test_urls)} URLs)")
    print("-" * 40)

    batch_start_time = time.time()

    try:
        # Trigger batch
        batch_payload = [{"url": url} for url in test_urls]
        print(f"   Triggering batch of {len(test_urls)} URLs...")

        response = requests.post(
            trigger_url, headers=headers, json=batch_payload, timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            snapshot_id = data.get("snapshot_id")
            print(f"   📊 Batch snapshot: {snapshot_id}")

            # Poll until completion
            status_url = (
                f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}"
            )

            poll_count = 0
            while True:
                time.sleep(10)  # Check every 10 seconds for batch
                poll_count += 1

                current_time = time.time() - batch_start_time
                print(f"   ⏱️  Polling {poll_count}: {current_time:.1f}s elapsed...")

                poll_response = requests.get(status_url, headers=headers, timeout=15)

                if poll_response.status_code == 200 and poll_response.text.strip():
                    # Data ready
                    batch_processing_time = time.time() - batch_start_time
                    print(
                        f"   ✅ Batch completed in {batch_processing_time:.1f} seconds"
                    )

                    # Try to parse and count results
                    try:
                        batch_data = poll_response.json()
                        if isinstance(batch_data, list):
                            results_count = len(batch_data)
                            print(
                                f"   📊 Results received: {results_count}/{len(test_urls)} videos"
                            )
                        else:
                            print(f"   📊 Batch data type: {type(batch_data)}")
                    except:
                        print(f"   📊 Data parsing info: Response received")

                    break
                elif poll_response.status_code == 404:
                    print(f"   ❌ Batch snapshot expired")
                    break
                elif time.time() - batch_start_time > 300:  # 5 minute timeout
                    batch_processing_time = time.time() - batch_start_time
                    print(
                        f"   ⏱️  Batch timeout after {batch_processing_time:.1f} seconds"
                    )
                    break

        else:
            print(f"   ❌ Batch trigger failed: {response.status_code}")

    except Exception as e:
        print(f"   ❌ Batch error: {str(e)[:100]}")
        batch_processing_time = None

    # Analysis
    print(f"\n📊 Processing Analysis:")
    print("=" * 40)

    if single_times and len(single_times) >= 2:
        avg_single_time = sum(single_times) / len(single_times)
        print(f"   Average single URL time: {avg_single_time:.1f} seconds")

        expected_sequential_time = avg_single_time * len(test_urls)
        print(
            f"   Expected sequential time for {len(test_urls)} URLs: {expected_sequential_time:.1f} seconds"
        )

        if "batch_processing_time" in locals() and batch_processing_time:
            print(f"   Actual batch time: {batch_processing_time:.1f} seconds")

            if batch_processing_time < expected_sequential_time * 0.7:
                print(f"\n   🚀 PARALLEL PROCESSING DETECTED!")
                print(
                    f"      Batch is {expected_sequential_time/batch_processing_time:.1f}x faster than sequential"
                )
                print(f"      ✅ Your 1000 URLs could process in parallel!")

                # Estimate for 1000 URLs
                parallel_factor = expected_sequential_time / batch_processing_time
                estimated_1000_time = (avg_single_time * 1000) / parallel_factor
                print(f"\n   📈 1000 URL Estimates:")
                print(f"      Sequential: {(avg_single_time * 1000)/3600:.1f} hours")
                print(f"      Parallel: {estimated_1000_time/3600:.1f} hours")

            else:
                print(f"\n   📅 SEQUENTIAL PROCESSING DETECTED")
                print(f"      Batch time ≈ sum of individual times")
                print(f"      ⚠️  Your 1000 URLs will process one by one")

                print(f"\n   📈 1000 URL Estimates:")
                print(f"      Full batch: {(avg_single_time * 1000)/3600:.1f} hours")
                print(f"      💡 Consider smaller batches with manual parallelization")

        else:
            print(
                f"   ⚠️  Batch test incomplete - couldn't determine processing pattern"
            )
    else:
        print(f"   ⚠️  Insufficient single URL data for comparison")

    print(f"\n💡 Recommendations:")
    if "batch_processing_time" in locals() and batch_processing_time and single_times:
        if batch_processing_time < sum(single_times) * 0.7:
            print(f"   🎯 Use large batches (100-500 URLs) - parallel processing works!")
            print(f"   🚀 Your 1000 URLs could be done in 2-4 large batches")
        else:
            print(
                f"   🎯 Use smaller batches (10-50 URLs) with your own parallelization"
            )
            print(f"   ⚡ Process 5-10 batches concurrently for faster results")
    else:
        print(f"   🧪 Run a longer test with more URLs to get clearer results")


if __name__ == "__main__":
    test_parallel_vs_sequential()
