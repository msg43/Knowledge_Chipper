#!/usr/bin/env python3
"""
Test different snapshot data fetch URL patterns.
"""

import json
import time

import requests


def test_snapshot_fetch():
    """Test different ways to fetch snapshot data."""

    api_key = "ed14d427de1f0186066bbbc3d948808642f1a43c57c79d6259a2438f54e8de51"
    dataset_id = "gd_lk538t2k2p1k3oos71"
    test_url = "https://www.youtube.com/watch?v=ksHkSuNTIKo"

    print("🎬 Testing Snapshot Data Fetch with Different URL Patterns")
    print("=" * 70)

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # First trigger a new collection
    trigger_url = f"https://api.brightdata.com/datasets/v3/trigger?dataset_id={dataset_id}&format=json"
    payload = [{"url": test_url}]

    print(f"🚀 Triggering new collection...")
    print(f"   URL: {trigger_url}")

    try:
        response = requests.post(trigger_url, headers=headers, json=payload, timeout=30)

        if response.status_code == 200:
            data = response.json()
            snapshot_id = data.get("snapshot_id")
            print(f"   ✅ Success! Snapshot ID: {snapshot_id}")

            # Try different URL patterns for data fetching
            url_patterns = [
                f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}/data?format=json",
                f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}/data",
                f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}?format=json",
                f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}",
                f"https://api.brightdata.com/datasets/v3/{snapshot_id}/data?format=json",
                f"https://api.brightdata.com/datasets/v3/{snapshot_id}/data",
                f"https://api.brightdata.com/datasets/{snapshot_id}/data?format=json",
                f"https://api.brightdata.com/datasets/{snapshot_id}",
                f"https://api.brightdata.com/datasets/v3/snapshots/{snapshot_id}/data?format=json",
                f"https://api.brightdata.com/v3/datasets/snapshot/{snapshot_id}/data?format=json",
            ]

            print(f"\n📥 Testing different fetch URL patterns...")

            for i, url in enumerate(url_patterns, 1):
                print(f"\n{i:2d}. Testing: {url}")

                try:
                    data_response = requests.get(url, headers=headers, timeout=15)
                    print(f"     Status: {data_response.status_code}")

                    if data_response.status_code == 200:
                        if data_response.text.strip():
                            print(f"     ✅ SUCCESS! Data received!")
                            try:
                                video_data = data_response.json()
                                print(f"     Data type: {type(video_data)}")
                                if isinstance(video_data, list) and len(video_data) > 0:
                                    video_item = video_data[0]
                                    if isinstance(video_item, dict):
                                        print(
                                            f"     Video fields: {list(video_item.keys())[:10]}..."
                                        )  # Show first 10 fields
                                        # Check for key fields
                                        key_fields = [
                                            "title",
                                            "video_id",
                                            "youtuber",
                                            "views",
                                        ]
                                        found = [
                                            f for f in key_fields if f in video_item
                                        ]
                                        if found:
                                            print(
                                                f"     ✅ Key YouTube fields found: {found}"
                                            )
                                break  # Found working URL
                            except:
                                print(f"     Raw data: {data_response.text[:100]}...")
                        else:
                            print(f"     ⏳ Empty response (still processing)")

                    elif data_response.status_code == 202:
                        print(f"     ⏳ Still processing...")

                    elif data_response.status_code == 404:
                        print(f"     ❌ Not found")

                    else:
                        print(f"     ⚠️  Status {data_response.status_code}")

                except Exception as e:
                    print(f"     ❌ Error: {str(e)[:50]}")

            # If no immediate success, wait and try the first pattern a few more times
            if True:  # Try polling the first pattern
                print(f"\n⏱️  Waiting for data processing...")
                main_url = url_patterns[0]

                for attempt in range(5):
                    wait_time = 5 * (attempt + 1)  # 5, 10, 15, 20, 25 seconds
                    print(f"\n   Waiting {wait_time} seconds...")
                    time.sleep(wait_time)

                    print(f"   📥 Polling attempt {attempt + 1}/5: {main_url}")
                    try:
                        data_response = requests.get(
                            main_url, headers=headers, timeout=20
                        )
                        print(f"      Status: {data_response.status_code}")

                        if (
                            data_response.status_code == 200
                            and data_response.text.strip()
                        ):
                            print(f"   ✅ SUCCESS! Data is ready!")
                            try:
                                video_data = data_response.json()
                                print(f"   Data type: {type(video_data)}")
                                if isinstance(video_data, list) and len(video_data) > 0:
                                    video_item = video_data[0]
                                    if isinstance(video_item, dict):
                                        print(
                                            f"   📊 All video fields ({len(video_item)}):"
                                        )
                                        for field in sorted(video_item.keys()):
                                            value = video_item[field]
                                            if (
                                                isinstance(value, str)
                                                and len(value) > 40
                                            ):
                                                preview = value[:40] + "..."
                                            else:
                                                preview = str(value)
                                            print(f"      {field}: {preview}")
                                return  # Success!
                            except Exception as e:
                                print(f"   ❌ JSON parsing error: {e}")
                                print(f"   Raw response: {data_response.text[:200]}")
                        else:
                            print(f"      ⏳ Still processing or empty...")

                    except Exception as e:
                        print(f"      ❌ Polling error: {str(e)[:50]}")

                print(f"\n   ⏱️  Data not ready after extended polling")
                print(
                    f"   💡 The YouTube video processing may take longer than expected"
                )

        else:
            print(f"   ❌ Trigger failed: {response.status_code}")
            try:
                error = response.json()
                print(f"   Error: {error}")
            except:
                print(f"   Response: {response.text[:200]}")

    except Exception as e:
        print(f"   ❌ Request error: {str(e)}")


if __name__ == "__main__":
    test_snapshot_fetch()
