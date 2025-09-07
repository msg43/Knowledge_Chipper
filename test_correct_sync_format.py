#!/usr/bin/env python3
"""
Test the correct synchronous scraper format based on validation errors.
"""

import json

import requests


def test_correct_sync_format():
    """Test the correct flat structure for synchronous scraping."""

    api_key = "ed14d427de1f0186066bbbc3d948808642f1a43c57c79d6259a2438f54e8de51"
    dataset_id = "gd_lk538t2k2p1k3oos71"
    test_url = "https://www.youtube.com/watch?v=ksHkSuNTIKo"

    print("🎯 Testing Correct Synchronous Scraper Format")
    print("=" * 50)
    print(f"Based on validation errors: expects flat 'url' field")
    print()

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Based on the error messages, try flat structures
    format_tests = [
        {"name": "Flat URL field only", "payload": {"url": test_url}},
        {"name": "Newline-delimited JSON", "payload": f'{{"url": "{test_url}"}}'},
        {
            "name": "URL in query parameter instead",
            "url_suffix": f"&url={test_url}",
            "payload": {},
        },
    ]

    base_url = f"https://api.brightdata.com/datasets/v3/scrape?dataset_id={dataset_id}&format=json"

    for i, test_case in enumerate(format_tests, 1):
        print(f"{i}. Testing: {test_case['name']}")

        # Determine URL and payload
        if "url_suffix" in test_case:
            url = base_url + test_case["url_suffix"]
            payload = test_case["payload"]
            print(f"   URL: {url}")
            print(f"   Payload: {json.dumps(payload)}")
        else:
            url = base_url
            payload = test_case["payload"]
            print(f"   URL: {url}")
            if isinstance(payload, str):
                print(f"   Payload (raw): {payload}")
            else:
                print(f"   Payload: {json.dumps(payload, indent=6)}")

        try:
            if isinstance(payload, str):
                # Send as raw string for NDJSON format
                response = requests.post(
                    url,
                    headers={**headers, "Content-Type": "application/json"},
                    data=payload,
                    timeout=60,
                )
            else:
                response = requests.post(url, headers=headers, json=payload, timeout=60)

            print(f"   Status: {response.status_code}")

            if response.status_code == 200:
                print(f"   ✅ SUCCESS!")

                try:
                    data = response.json()
                    print(f"   Response type: {type(data)}")

                    if isinstance(data, list) and len(data) > 0:
                        video_item = data[0]
                        if isinstance(video_item, dict):
                            print(f"   🎉 YOUTUBE METADATA FOUND!")
                            print(f"   Fields: {list(video_item.keys())[:10]}...")

                            # Show key fields
                            key_fields = [
                                "title",
                                "video_id",
                                "youtuber",
                                "views",
                                "description",
                            ]
                            for field in key_fields:
                                if field in video_item:
                                    value = video_item[field]
                                    if isinstance(value, str) and len(value) > 40:
                                        print(f"      ✅ {field}: {value[:40]}...")
                                    else:
                                        print(f"      ✅ {field}: {value}")

                            print(f"\n   🎊 SYNCHRONOUS YOUTUBE API WORKING!")
                            return True

                    elif isinstance(data, dict):
                        print(f"   Response keys: {list(data.keys())}")

                except Exception as e:
                    print(f"   ❌ JSON parsing error: {e}")
                    print(f"   Raw response: {response.text[:300]}...")

            elif response.status_code == 202:
                print(f"   ⏳ Async processing initiated")
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
                except:
                    print(f"   ❌ Bad Request: {response.text[:200]}")

            else:
                print(f"   ⚠️  Status {response.status_code}")
                try:
                    error = response.json()
                    print(f"   Response: {error}")
                except:
                    print(f"   Response: {response.text[:100]}")

        except Exception as e:
            print(f"   ❌ Error: {str(e)[:100]}")

        print()

    print(
        f"💡 If synchronous doesn't work, the async /trigger approach we tested earlier"
    )
    print(f"   should be used as the reliable method for YouTube metadata extraction.")

    return False


if __name__ == "__main__":
    success = test_correct_sync_format()

    if not success:
        print(f"\n🔄 Recommendation: Use async /trigger approach")
        print(f"   ✅ We know /trigger works (gets snapshot_ids)")
        print(f"   ✅ We know polling works (gets 200 responses)")
        print(f"   🔧 Just need to fix the data format parsing")
        print(f"   ⚡ This gives reliable YouTube metadata extraction")
