#!/usr/bin/env python3
"""
Quick test to verify YouTube scraper API connectivity.
"""

import json
import os

import requests


def test_youtube_scraper_api():
    """Test the YouTube Web Scraper API with the current configuration."""

    # Your API key
    api_key = "ed14d427de1f0186066bbbc3d948808642f1a43c57c79d6259a2438f54e8de51"

    # Test URL
    test_url = "https://www.youtube.com/watch?v=ksHkSuNTIKo"

    print("🧪 Testing YouTube Web Scraper API")
    print("=" * 50)
    print(f"Test URL: {test_url}")
    print(f"API Key: {api_key[:20]}...")
    print()

    # API endpoint
    endpoint = "https://api.brightdata.com/web-scraper/trigger"

    # Headers
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Test different payload configurations
    payloads_to_try = [
        {
            "name": "YouTube Posts API - Primary",
            "payload": {
                "collector": "youtube_posts",
                "inputs": [{"url": test_url}],
                "fields": [
                    "title",
                    "description",
                    "transcript",
                    "formatted_transcript",
                    "youtuber",
                    "youtuber_id",
                    "date_posted",
                    "video_length",
                    "views",
                    "likes",
                    "num_comments",
                    "preview_image",
                    "video_id",
                    "url",
                ],
            },
        },
        {
            "name": "YouTube Posts API - Alternative",
            "payload": {
                "collector": "youtube_posts_api",
                "inputs": [{"url": test_url}],
                "fields": [
                    "title",
                    "description",
                    "transcript",
                    "formatted_transcript",
                    "youtuber",
                    "youtuber_id",
                    "date_posted",
                    "video_length",
                    "views",
                    "likes",
                    "num_comments",
                    "preview_image",
                ],
            },
        },
        {
            "name": "Generic YouTube Collector",
            "payload": {"collector": "youtube", "inputs": [{"url": test_url}]},
        },
        {
            "name": "Social Media YouTube",
            "payload": {
                "collector": "social_media_youtube",
                "inputs": [{"url": test_url}],
            },
        },
        {
            "name": "Web Scraper with YouTube Dataset",
            "payload": {
                "collector": "web_scraper",
                "dataset": "youtube",
                "inputs": [{"url": test_url}],
            },
        },
    ]

    success_count = 0
    for i, test_case in enumerate(payloads_to_try, 1):
        print(f"\n{i}. Testing: {test_case['name']}")
        print("-" * 40)

        try:
            response = requests.post(
                endpoint, headers=headers, json=test_case["payload"], timeout=30
            )

            print(f"   Status Code: {response.status_code}")

            if response.status_code == 200:
                print("   ✅ SUCCESS! API connection working")
                data = response.json()
                print(
                    f"   Response keys: {list(data.keys()) if isinstance(data, dict) else 'Non-dict response'}"
                )
                if isinstance(data, dict) and "data" in data:
                    print(
                        f"   Data keys: {list(data['data'].keys()) if isinstance(data['data'], dict) else 'Non-dict data'}"
                    )
                success_count += 1
                break  # Found working configuration

            elif response.status_code == 401:
                print("   ❌ Authentication failed - check API key")

            elif response.status_code == 400:
                try:
                    error_data = response.json()
                    print(f"   ❌ Bad Request: {error_data}")
                except:
                    print(f"   ❌ Bad Request: {response.text[:200]}")

            elif response.status_code == 403:
                print("   ❌ Access forbidden - check API key permissions")

            elif response.status_code == 404:
                print("   ❌ Endpoint not found")

            elif response.status_code == 429:
                print("   ❌ Rate limited")

            else:
                print(f"   ⚠️  Unexpected status: {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Response: {error_data}")
                except:
                    print(f"   Response: {response.text[:200]}")

        except requests.exceptions.Timeout:
            print("   ❌ Request timeout")
        except requests.exceptions.ConnectionError as e:
            print(f"   ❌ Connection error: {e}")
        except Exception as e:
            print(f"   ❌ Unexpected error: {e}")

    print(f"\n📊 Summary:")
    print(f"   Successful connections: {success_count}/{len(payloads_to_try)}")

    if success_count > 0:
        print("   ✅ YouTube API scraper is working!")
        print("   📋 Next steps:")
        print("     - The API connection is successful")
        print("     - Try running YouTube transcription")
        print("     - Check for Rich Meta data extraction")
    else:
        print("   ❌ No working configurations found")
        print("   📋 Troubleshooting:")
        print("     - Verify API key has Web Scraper permissions")
        print("     - Check if account has YouTube scraper access")
        print("     - Contact Bright Data support if needed")


if __name__ == "__main__":
    test_youtube_scraper_api()
