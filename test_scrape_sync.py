#!/usr/bin/env python3
"""
Test the synchronous /scrape endpoint for immediate YouTube metadata.
"""

import json
import time

import requests


def test_scrape_sync():
    """Test the synchronous scrape endpoint for immediate results."""

    api_key = "ed14d427de1f0186066bbbc3d948808642f1a43c57c79d6259a2438f54e8de51"
    dataset_id = "gd_lk538t2k2p1k3oos71"
    test_url = "https://www.youtube.com/watch?v=ksHkSuNTIKo"

    print("⚡ Testing Synchronous /scrape Endpoint")
    print("=" * 50)
    print(f"Dataset ID: {dataset_id}")
    print(f"Test video: {test_url}")
    print(f"Expected: Immediate results (5-30 seconds)")
    print()

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Test different payload formats for /scrape
    scrape_tests = [
        {
            "name": "Scrape - Array format",
            "url": f"https://api.brightdata.com/datasets/v3/scrape?dataset_id={dataset_id}&format=json",
            "payload": [{"url": test_url}],
        },
        {
            "name": "Scrape - Input wrapper",
            "url": f"https://api.brightdata.com/datasets/v3/scrape?dataset_id={dataset_id}&format=json",
            "payload": {"input": [{"url": test_url}]},
        },
        {
            "name": "Scrape - Single object",
            "url": f"https://api.brightdata.com/datasets/v3/scrape?dataset_id={dataset_id}&format=json",
            "payload": {"url": test_url},
        },
        {
            "name": "Scrape - URL in query param",
            "url": f"https://api.brightdata.com/datasets/v3/scrape?dataset_id={dataset_id}&format=json&url={test_url}",
            "payload": {},
        },
        {
            "name": "Scrape - Different format",
            "url": f"https://api.brightdata.com/datasets/v3/scrape?dataset_id={dataset_id}&format=csv",
            "payload": [{"url": test_url}],
        },
    ]

    for i, test in enumerate(scrape_tests, 1):
        print(f"{i}. Testing: {test['name']}")
        print(f"   URL: {test['url']}")
        if test["payload"]:
            print(f"   Payload: {json.dumps(test['payload'])}")
        else:
            print(f"   Payload: (empty - URL in query)")

        start_time = time.time()

        try:
            # Make synchronous request with reasonable timeout
            response = requests.post(
                test["url"],
                headers=headers,
                json=test["payload"],
                timeout=60,  # 60 seconds max for sync
            )

            elapsed = time.time() - start_time
            print(f"   Response time: {elapsed:.2f} seconds")
            print(f"   Status: {response.status_code}")

            # Check for policy errors
            policy_code = response.headers.get("x-brd-err-code")
            policy_msg = response.headers.get("x-brd-err-msg")

            if policy_code:
                print(f"   🚫 POLICY ERROR:")
                print(f"      Code: {policy_code}")
                print(f"      Message: {policy_msg}")
                if "policy_20050" in str(policy_code):
                    print(f"   💡 Solution: Complete KYC verification")

            elif response.status_code == 200:
                print(f"   ✅ SUCCESS! Synchronous response received!")

                # Check response size
                response_size = len(response.text)
                print(f"   Response size: {response_size} bytes")

                if response.text.strip():
                    try:
                        # Try JSON first
                        data = response.json()
                        print(f"   📊 JSON Response type: {type(data)}")

                        if isinstance(data, list) and len(data) > 0:
                            video_item = data[0]
                            if isinstance(video_item, dict):
                                print(f"   🎬 VIDEO METADATA FOUND!")
                                print(
                                    f"   Fields ({len(video_item)}): {list(video_item.keys())[:10]}..."
                                )

                                # Show key YouTube fields
                                key_fields = [
                                    "title",
                                    "video_id",
                                    "youtuber",
                                    "views",
                                    "description",
                                ]
                                print(f"\n   🎯 Key YouTube Data:")
                                for field in key_fields:
                                    if field in video_item:
                                        value = video_item[field]
                                        if isinstance(value, str) and len(value) > 50:
                                            print(f"      ✅ {field}: {value[:50]}...")
                                        else:
                                            print(f"      ✅ {field}: {value}")
                                    else:
                                        print(f"      ❌ {field}: Not found")

                                print(f"\n   🎊 SCRAPE ENDPOINT WORKING!")
                                return True

                        elif isinstance(data, dict):
                            print(f"   📊 Dict response: {list(data.keys())}")

                    except json.JSONDecodeError:
                        # Try as CSV or plain text
                        print(f"   📄 Non-JSON response")
                        lines = response.text.split("\n")
                        print(f"   Lines: {len(lines)}")
                        print(f"   Sample: {lines[0][:100] if lines else 'Empty'}...")

                        if "youtube.com" in response.text:
                            print(f"   ✅ Contains YouTube data!")

                else:
                    print(f"   ⚠️  Empty response body")

            elif response.status_code == 202:
                print(f"   ⏳ Fell back to async (too complex for sync)")
                try:
                    data = response.json()
                    if "snapshot_id" in data:
                        print(f"   📊 Snapshot ID: {data['snapshot_id']}")
                except:
                    pass

            elif response.status_code == 400:
                try:
                    error = response.json()
                    print(f"   ❌ Bad Request: {error}")

                    # Look for specific clues
                    error_str = str(error).lower()
                    if "empty" in error_str or "snapshot" in error_str:
                        print(f"   💡 Likely dataset issue - wrong dataset type")
                    elif "collector" in error_str:
                        print(f"   💡 Wrong API format - this isn't a collector")
                    elif "input" in error_str:
                        print(f"   💡 Input format issue")

                except:
                    print(f"   ❌ Bad Request: {response.text[:200]}")

            elif response.status_code == 401:
                print(f"   🔑 Authentication failed")

            elif response.status_code == 403:
                print(f"   🚫 Forbidden - check dataset access")

            elif response.status_code == 404:
                print(f"   ❌ Dataset not found")

            else:
                print(f"   ⚠️  Status {response.status_code}")
                print(f"   Response: {response.text[:150]}")

        except requests.exceptions.Timeout:
            elapsed = time.time() - start_time
            print(f"   ⏱️  Timeout after {elapsed:.1f} seconds")

        except Exception as e:
            elapsed = time.time() - start_time
            print(f"   ❌ Error after {elapsed:.1f}s: {str(e)[:100]}")

        print()

    print(f"📊 Synchronous /scrape Test Summary:")
    print(f"   ⚡ Should be much faster than /trigger for single videos")
    print(f"   🎯 If all fail, the dataset might be wrong or inactive")
    print(f"   💡 Success would prove the concept works immediately")


if __name__ == "__main__":
    test_scrape_sync()
