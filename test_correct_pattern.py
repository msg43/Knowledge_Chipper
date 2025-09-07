#!/usr/bin/env python3
"""
Test the correct snapshot polling pattern (202 responses indicate correct URLs).
"""

import json
import time

import requests


def test_correct_pattern():
    """Test the snapshot URLs that returned 202 (processing)."""

    api_key = "ed14d427de1f0186066bbbc3d948808642f1a43c57c79d6259a2438f54e8de51"
    dataset_id = "gd_lk538t2k2p1k3oos71"
    test_url = "https://www.youtube.com/watch?v=ksHkSuNTIKo"

    print("🎬 Testing Correct Snapshot Pattern (202 = Processing)")
    print("=" * 60)

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Trigger a new collection
    trigger_url = f"https://api.brightdata.com/datasets/v3/trigger?dataset_id={dataset_id}&format=json"
    payload = [{"url": test_url}]

    print(f"🚀 Triggering collection...")

    try:
        response = requests.post(trigger_url, headers=headers, json=payload, timeout=30)

        if response.status_code == 200:
            data = response.json()
            snapshot_id = data.get("snapshot_id")
            print(f"   ✅ Snapshot ID: {snapshot_id}")

            # The URLs that returned 202 (processing)
            status_urls = [
                f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}?format=json",
                f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}",
            ]

            print(f"\n📊 Monitoring snapshot status...")

            max_attempts = 12  # 2 minutes of polling
            for attempt in range(max_attempts):
                print(f"\n⏱️  Attempt {attempt + 1}/{max_attempts}")

                for i, url in enumerate(status_urls, 1):
                    print(f"   {i}. Checking: {url}")

                    try:
                        status_response = requests.get(url, headers=headers, timeout=15)
                        print(f"      Status: {status_response.status_code}")

                        if status_response.status_code == 200:
                            # Success! Check what we got
                            try:
                                result_data = status_response.json()
                                print(f"      ✅ SUCCESS! Data received")
                                print(f"      Response type: {type(result_data)}")

                                if isinstance(result_data, dict):
                                    print(
                                        f"      Response keys: {list(result_data.keys())}"
                                    )

                                    # Check if this contains the actual video data
                                    if "data" in result_data:
                                        video_data = result_data["data"]
                                        print(f"      Data type: {type(video_data)}")

                                        if (
                                            isinstance(video_data, list)
                                            and len(video_data) > 0
                                        ):
                                            video_item = video_data[0]
                                            if isinstance(video_item, dict):
                                                print(f"      🎉 VIDEO METADATA FOUND!")
                                                print(
                                                    f"      Fields ({len(video_item)}): {list(video_item.keys())[:10]}..."
                                                )

                                                # Show key YouTube fields
                                                key_fields = {
                                                    "title": video_item.get("title"),
                                                    "video_id": video_item.get(
                                                        "video_id"
                                                    ),
                                                    "youtuber": video_item.get(
                                                        "youtuber"
                                                    ),
                                                    "views": video_item.get("views"),
                                                    "likes": video_item.get("likes"),
                                                    "description": video_item.get(
                                                        "description"
                                                    ),
                                                    "preview_image": video_item.get(
                                                        "preview_image"
                                                    ),
                                                    "transcript": "YES"
                                                    if video_item.get("transcript")
                                                    else "NO",
                                                }

                                                print(f"\n      📊 Key YouTube Data:")
                                                for field, value in key_fields.items():
                                                    if value:
                                                        if (
                                                            isinstance(value, str)
                                                            and len(value) > 50
                                                        ):
                                                            display_value = (
                                                                value[:50] + "..."
                                                            )
                                                        else:
                                                            display_value = value
                                                        print(
                                                            f"         ✅ {field}: {display_value}"
                                                        )
                                                    else:
                                                        print(
                                                            f"         ❌ {field}: Not found"
                                                        )

                                                print(
                                                    f"\n   🎉 COMPLETE SUCCESS! YouTube Posts API is working!"
                                                )
                                                print(
                                                    f"   📋 This proves the API can extract Rich Meta data"
                                                )
                                                return True  # Success!

                                    # Check for status info
                                    elif "status" in result_data:
                                        status = result_data["status"]
                                        print(f"      Status: {status}")
                                        if status == "completed":
                                            print(
                                                f"      ✅ Processing completed, but no data field found"
                                            )
                                        elif status == "running":
                                            print(f"      ⏳ Still running...")

                                elif isinstance(result_data, list):
                                    print(
                                        f"      List response with {len(result_data)} items"
                                    )
                                    if len(result_data) > 0:
                                        first_item = result_data[0]
                                        if isinstance(first_item, dict):
                                            print(
                                                f"      First item keys: {list(first_item.keys())[:10]}..."
                                            )

                            except json.JSONDecodeError:
                                print(f"      ❌ JSON parsing failed")
                                print(
                                    f"      Raw response: {status_response.text[:200]}..."
                                )

                        elif status_response.status_code == 202:
                            print(f"      ⏳ Still processing...")

                        elif status_response.status_code == 404:
                            print(f"      ❌ Not found")

                        else:
                            print(f"      ⚠️  Status {status_response.status_code}")

                    except Exception as e:
                        print(f"      ❌ Request error: {str(e)[:50]}")

                if attempt < max_attempts - 1:
                    wait_time = 10  # Wait 10 seconds between attempts
                    print(f"   💤 Waiting {wait_time} seconds...")
                    time.sleep(wait_time)

            print(f"\n   ⏱️  Timeout after {max_attempts} attempts")
            print(f"   💡 The collection may need more time to complete")

        else:
            print(f"   ❌ Trigger failed: {response.status_code}")
            try:
                error = response.json()
                print(f"   Error: {error}")
            except:
                print(f"   Response: {response.text[:200]}")

    except Exception as e:
        print(f"   ❌ Request error: {str(e)}")

    return False


if __name__ == "__main__":
    test_correct_pattern()
