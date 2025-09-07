#!/usr/bin/env python3
"""
Test the correct YouTube Web Scraper API based on official documentation.
"""

import json
import time

import requests


def test_correct_youtube_api():
    """Test the YouTube Web Scraper API with correct structure."""

    api_key = "ed14d427de1f0186066bbbc3d948808642f1a43c57c79d6259a2438f54e8de51"
    test_url = "https://www.youtube.com/watch?v=ksHkSuNTIKo"

    print("🧪 Testing Correct YouTube Web Scraper API")
    print("=" * 60)
    print(
        f"Based on: https://docs.brightdata.com/api-reference/web-scraper-api/social-media-apis/youtube"
    )
    print(f"Test URL: {test_url}")
    print()

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Test different YouTube API types from the documentation
    api_tests = [
        {
            "name": "Posts API - Collect by URL (Video Details)",
            "endpoint": "https://api.brightdata.com/datasets/v3/trigger",
            "payload": {
                "dataset": "gd_l7q8zkp1l8rwq7r",  # YouTube Posts dataset ID
                "inputs": [{"url": test_url}],
                "include_errors": True,
                "format": "json",
                "notify": [],
            },
        },
        {
            "name": "Social Media YouTube - Posts Collection",
            "endpoint": "https://api.brightdata.com/datasets/v3/trigger",
            "payload": {
                "dataset": "gd_l7q8zkp1l8rwq7r",  # Standard YouTube dataset
                "inputs": [{"url": test_url}],
                "format": "json",
            },
        },
        {
            "name": "Web Scraper API - YouTube Social Media",
            "endpoint": "https://api.brightdata.com/webscraper/api/trigger",
            "payload": {
                "collector": "youtube_posts",
                "inputs": [{"url": test_url}],
                "format": "json",
            },
        },
        {
            "name": "Alternative Web Scraper Endpoint",
            "endpoint": "https://api.brightdata.com/web-scraper/trigger",
            "payload": {"collector": "youtube_posts", "inputs": [{"url": test_url}]},
        },
        {
            "name": "Dataset API v3 - Standard Call",
            "endpoint": "https://api.brightdata.com/datasets/v3/trigger",
            "payload": {
                "dataset": "youtube",
                "inputs": [{"url": test_url}],
                "format": "json",
            },
        },
    ]

    working_apis = []

    for i, test_case in enumerate(api_tests, 1):
        print(f"{i}. Testing: {test_case['name']}")
        print(f"   Endpoint: {test_case['endpoint']}")
        print(f"   Payload: {json.dumps(test_case['payload'], indent=6)}")

        try:
            response = requests.post(
                test_case["endpoint"],
                headers=headers,
                json=test_case["payload"],
                timeout=30,
            )

            print(f"   Status: {response.status_code}")

            if response.status_code == 200:
                print(f"   ✅ SUCCESS!")
                working_apis.append(test_case["name"])

                try:
                    data = response.json()
                    print(
                        f"   Response keys: {list(data.keys()) if isinstance(data, dict) else type(data)}"
                    )

                    # Check for important response fields
                    if isinstance(data, dict):
                        if "snapshot_id" in data:
                            print(f"   📊 Snapshot ID: {data['snapshot_id']}")
                        if "status" in data:
                            print(f"   📊 Status: {data['status']}")
                        if "data" in data:
                            print(
                                f"   📊 Data received: {len(data['data']) if isinstance(data['data'], list) else 'Yes'}"
                            )

                except Exception as e:
                    print(f"   Response parsing error: {e}")
                    print(f"   Raw response: {response.text[:200]}...")

            elif response.status_code == 400:
                try:
                    error = response.json()
                    print(f"   ❌ Bad Request: {error}")

                    # Check for specific error types
                    if "dataset" in str(error).lower():
                        print(f"   💡 Suggestion: Dataset ID might be incorrect")
                    elif "collector" in str(error).lower():
                        print(f"   💡 Suggestion: Collector name might be incorrect")

                except:
                    print(f"   ❌ Bad Request: {response.text[:200]}")

            elif response.status_code == 401:
                print(f"   🔑 Authentication failed")
                break  # No point testing others if auth fails

            elif response.status_code == 403:
                print(f"   🚫 Forbidden - check API permissions")

            elif response.status_code == 404:
                print(f"   ❌ Endpoint not found")

            elif response.status_code == 429:
                print(f"   ⏱️  Rate limited")

            else:
                print(f"   ⚠️  Status {response.status_code}")
                try:
                    error = response.json()
                    print(f"   Response: {error}")
                except:
                    print(f"   Response: {response.text[:150]}")

        except requests.exceptions.Timeout:
            print(f"   ⏱️  Request timeout")
        except requests.exceptions.ConnectionError as e:
            print(f"   🔌 Connection error: {str(e)[:100]}")
        except Exception as e:
            print(f"   ❌ Error: {str(e)[:100]}")

        print()

    print(f"📊 Final Results:")
    if working_apis:
        print(f"   ✅ Working APIs: {working_apis}")
        print(f"   🎉 YouTube API is functional!")
        print(f"   📋 Next steps:")
        print(f"     - Update youtube_metadata.py and youtube_transcript.py")
        print(f"     - Use the working endpoint and payload structure")
        print(f"     - Test with actual video processing")
    else:
        print(f"   ❌ No working APIs found")
        print(f"   💡 Next steps:")
        print(f"     - Check if your API key has Web Scraper permissions")
        print(f"     - Verify YouTube scraper access in your Bright Data account")
        print(f"     - Contact Bright Data support for dataset access")


if __name__ == "__main__":
    test_correct_youtube_api()
