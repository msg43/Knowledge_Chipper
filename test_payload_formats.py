#!/usr/bin/env python3
"""
Test different payload formats for the Bright Data API.
"""

import json

import requests


def test_payload_formats():
    """Test different payload formats."""

    api_key = "ed14d427de1f0186066bbbc3d948808642f1a43c57c79d6259a2438f54e8de51"
    endpoint = "https://api.brightdata.com/dca/trigger"
    test_url = "https://www.youtube.com/watch?v=ksHkSuNTIKo"

    print("🧪 Testing Different Payload Formats")
    print("=" * 50)
    print(f"Endpoint: {endpoint}")
    print(f"Test URL: {test_url}")
    print()

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Different payload formats to try
    payload_formats = [
        {
            "name": "Simple collector format",
            "payload": {"collector": "youtube", "url": test_url},
        },
        {
            "name": "Collector with inputs array",
            "payload": {"collector": "youtube", "inputs": [{"url": test_url}]},
        },
        {
            "name": "Collector with discover_by",
            "payload": {"collector": "youtube", "url": test_url, "discover_by": "url"},
        },
        {
            "name": "Dataset collection format",
            "payload": {
                "dataset_id": "youtube",
                "inputs": [{"url": test_url}],
                "format": "json",
            },
        },
        {"name": "Zone-based format", "payload": {"zone": "youtube", "url": test_url}},
        {
            "name": "Scraper ID format",
            "payload": {"scraper_id": "youtube", "url": test_url},
        },
        {
            "name": "Collection format",
            "payload": {"collection": "youtube", "urls": [test_url]},
        },
        {"name": "Minimal format - just URL", "payload": {"url": test_url}},
        {
            "name": "Webshare style format",
            "payload": {"urls": [test_url], "format": "json"},
        },
    ]

    working_formats = []

    for i, test_case in enumerate(payload_formats, 1):
        print(f"{i}. Testing: {test_case['name']}")
        print(f"   Payload: {json.dumps(test_case['payload'], indent=2)}")

        try:
            response = requests.post(
                endpoint, headers=headers, json=test_case["payload"], timeout=15
            )

            print(f"   Status: {response.status_code}")

            if response.status_code == 200:
                print(f"   ✅ SUCCESS!")
                working_formats.append(test_case["name"])
                try:
                    data = response.json()
                    print(
                        f"   Response keys: {list(data.keys()) if isinstance(data, dict) else type(data)}"
                    )
                except:
                    print(f"   Response: {response.text[:150]}...")

            elif response.status_code == 400:
                try:
                    error = response.json()
                    print(f"   ❌ Error: {error}")
                except:
                    print(f"   ❌ Error: {response.text[:150]}")

            elif response.status_code == 401:
                print(f"   🔑 Auth error")

            elif response.status_code == 403:
                print(f"   🚫 Forbidden")

            else:
                print(f"   ⚠️  Status {response.status_code}")
                try:
                    error = response.json()
                    print(f"   Response: {error}")
                except:
                    print(f"   Response: {response.text[:100]}")

        except Exception as e:
            print(f"   ❌ Exception: {str(e)[:100]}")

        print()

    print(f"📊 Results:")
    if working_formats:
        print(f"   ✅ Working formats: {working_formats}")
    else:
        print(f"   ❌ No working payload formats found")
        print(f"   💡 This suggests:")
        print(
            f"     - You may need to set up collectors in Bright Data dashboard first"
        )
        print(f"     - The API might require account-specific collector IDs")
        print(f"     - YouTube scraping might need special permissions")


if __name__ == "__main__":
    test_payload_formats()
