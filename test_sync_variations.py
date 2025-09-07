#!/usr/bin/env python3
"""
Test different payload structures for the synchronous scraper API.
"""

import json

import requests


def test_sync_variations():
    """Test different payload formats for synchronous scraping."""

    api_key = "ed14d427de1f0186066bbbc3d948808642f1a43c57c79d6259a2438f54e8de51"
    dataset_id = "gd_lk538t2k2p1k3oos71"
    test_url = "https://www.youtube.com/watch?v=ksHkSuNTIKo"

    print("🔍 Testing Different Synchronous Scraper Payload Formats")
    print("=" * 65)

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Different payload formats to try
    payload_variations = [
        {
            "name": "Standard input array",
            "url": f"https://api.brightdata.com/datasets/v3/scrape?dataset_id={dataset_id}&format=json",
            "payload": {"input": [{"url": test_url}]},
        },
        {
            "name": "Inputs array (like trigger)",
            "url": f"https://api.brightdata.com/datasets/v3/scrape?dataset_id={dataset_id}&format=json",
            "payload": {"inputs": [{"url": test_url}]},
        },
        {
            "name": "Direct URL array",
            "url": f"https://api.brightdata.com/datasets/v3/scrape?dataset_id={dataset_id}&format=json",
            "payload": [{"url": test_url}],
        },
        {
            "name": "Simple URL string",
            "url": f"https://api.brightdata.com/datasets/v3/scrape?dataset_id={dataset_id}&format=json",
            "payload": {"url": test_url},
        },
        {
            "name": "Data wrapper",
            "url": f"https://api.brightdata.com/datasets/v3/scrape?dataset_id={dataset_id}&format=json",
            "payload": {"data": [{"url": test_url}]},
        },
        {
            "name": "Alternative sync endpoint",
            "url": f"https://api.brightdata.com/datasets/v3/sync?dataset_id={dataset_id}&format=json",
            "payload": {"input": [{"url": test_url}]},
        },
    ]

    successful_calls = []

    for i, test_case in enumerate(payload_variations, 1):
        print(f"\n{i}. Testing: {test_case['name']}")
        print(f"   URL: {test_case['url']}")
        print(f"   Payload: {json.dumps(test_case['payload'], indent=6)}")

        try:
            response = requests.post(
                test_case["url"], headers=headers, json=test_case["payload"], timeout=60
            )

            print(f"   Status: {response.status_code}")

            # Check for policy errors
            policy_code = response.headers.get("x-brd-err-code")
            policy_msg = response.headers.get("x-brd-err-msg")

            if policy_code:
                print(f"   🚫 Policy: {policy_code} - {policy_msg}")
                successful_calls.append(f"{test_case['name']} (needs KYC)")

            elif response.status_code == 200:
                print(f"   ✅ SUCCESS!")
                successful_calls.append(test_case["name"])

                try:
                    data = response.json()
                    print(f"   Response type: {type(data)}")

                    if isinstance(data, list) and len(data) > 0:
                        video_item = data[0]
                        if isinstance(video_item, dict):
                            print(f"   🎬 Video data found!")
                            print(f"   Fields: {list(video_item.keys())[:10]}...")

                            # Check for key YouTube fields
                            key_fields = ["title", "video_id", "youtuber", "views"]
                            found_fields = [f for f in key_fields if f in video_item]
                            if found_fields:
                                print(f"   ✅ YouTube metadata: {found_fields}")

                                # Show sample values
                                for field in found_fields[:3]:  # Show first 3
                                    value = video_item[field]
                                    if isinstance(value, str) and len(value) > 40:
                                        print(f"      {field}: {value[:40]}...")
                                    else:
                                        print(f"      {field}: {value}")

                                return True  # Found working solution!

                except Exception as e:
                    print(f"   ⚠️  Response parsing error: {e}")
                    print(f"   Raw response: {response.text[:200]}...")

            elif response.status_code == 202:
                print(f"   ⏳ Async processing (fell back to async)")
                successful_calls.append(f"{test_case['name']} (async)")

            elif response.status_code == 400:
                try:
                    error = response.json()
                    print(f"   ❌ Bad Request: {error}")

                    # Analyze error message
                    error_str = str(error).lower()
                    if "empty" in error_str:
                        print(f"   💡 Empty response - may need different input format")
                    elif "input" in error_str:
                        print(f"   💡 Input format issue")
                    elif "dataset" in error_str:
                        print(f"   💡 Dataset configuration issue")

                except:
                    print(f"   ❌ Bad Request: {response.text[:150]}")

            elif response.status_code == 404:
                print(f"   ❌ Endpoint not found")

            elif response.status_code == 401:
                print(f"   🔑 Auth failed")

            elif response.status_code == 403:
                print(f"   🚫 Forbidden")

            else:
                print(f"   ⚠️  Status {response.status_code}")
                try:
                    error = response.json()
                    print(f"   Response: {error}")
                except:
                    print(f"   Response: {response.text[:100]}")

        except requests.exceptions.Timeout:
            print(f"   ⏱️  Timeout (>60s)")
            successful_calls.append(f"{test_case['name']} (timeout)")

        except Exception as e:
            print(f"   ❌ Error: {str(e)[:100]}")

    print(f"\n📊 Results Summary:")
    if successful_calls:
        print(f"   Responses received from:")
        for call in successful_calls:
            print(f"     - {call}")
    else:
        print(f"   ❌ No successful payload formats found")

    print(f"\n💡 Analysis:")
    print(f"   - 'Snapshot is empty' suggests the dataset expects different input")
    print(f"   - May need to use async /trigger approach instead")
    print(f"   - Could be account/dataset configuration issue")


if __name__ == "__main__":
    test_sync_variations()
