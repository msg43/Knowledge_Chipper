#!/usr/bin/env python3
"""
Test YouTube Posts API with correct structure for metadata extraction.
"""

import json
import time

import requests


def test_youtube_posts_api():
    """Test the YouTube Posts API - Collect by URL endpoint."""

    api_key = "ed14d427de1f0186066bbbc3d948808642f1a43c57c79d6259a2438f54e8de51"
    test_url = "https://www.youtube.com/watch?v=ksHkSuNTIKo"

    print("🎬 Testing YouTube Posts API - Collect by URL")
    print("=" * 60)
    print(f"Target: Extract video metadata from {test_url}")
    print(f"Expected fields: video_id, title, url, description, youtuber, youtuber_id,")
    print(f"                date_posted, video_length, views, preview_image, etc.")
    print()

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Different endpoint patterns for YouTube Posts API
    endpoint_variations = [
        {
            "name": "Standard Web Scraper API",
            "endpoint": "https://api.brightdata.com/dca/trigger",
            "payload": {
                "collector": "youtube_posts",
                "inputs": [{"url": test_url}],
                "format": "json",
            },
        },
        {
            "name": "Posts API with Dataset ID",
            "endpoint": "https://api.brightdata.com/dca/trigger",
            "payload": {
                "dataset_id": "youtube_posts",
                "inputs": [{"url": test_url}],
                "format": "json",
            },
        },
        {
            "name": "Social Media YouTube Collector",
            "endpoint": "https://api.brightdata.com/dca/trigger",
            "payload": {
                "collector": "social_media_youtube",
                "inputs": [{"url": test_url}],
                "format": "json",
            },
        },
        {
            "name": "Generic YouTube Collector",
            "endpoint": "https://api.brightdata.com/dca/trigger",
            "payload": {"collector": "youtube", "inputs": [{"url": test_url}]},
        },
        {
            "name": "Direct URL with Fields Specification",
            "endpoint": "https://api.brightdata.com/dca/trigger",
            "payload": {
                "collector": "youtube_posts",
                "inputs": [{"url": test_url}],
                "fields": [
                    "video_id",
                    "title",
                    "url",
                    "description",
                    "youtuber",
                    "youtuber_id",
                    "date_posted",
                    "video_length",
                    "views",
                    "likes",
                    "num_comments",
                    "preview_image",
                    "transcript",
                    "formatted_transcript",
                    "related_videos",
                    "subscribers",
                    "verified",
                    "avatar_img_channel",
                ],
            },
        },
        {
            "name": "Alternative DCA Format",
            "endpoint": "https://api.brightdata.com/dca/trigger",
            "payload": {"url": test_url, "collector": "youtube_posts"},
        },
    ]

    successful_tests = []

    for i, test_case in enumerate(endpoint_variations, 1):
        print(f"{i}. Testing: {test_case['name']}")
        print(f"   Endpoint: {test_case['endpoint']}")
        print(f"   Payload keys: {list(test_case['payload'].keys())}")

        try:
            response = requests.post(
                test_case["endpoint"],
                headers=headers,
                json=test_case["payload"],
                timeout=30,
            )

            print(f"   Status: {response.status_code}")

            if response.status_code == 200:
                print(f"   ✅ SUCCESS! YouTube Posts API is working!")
                successful_tests.append(test_case["name"])

                try:
                    data = response.json()
                    print(f"   Response type: {type(data)}")

                    if isinstance(data, dict):
                        print(f"   Response keys: {list(data.keys())}")

                        # Check for expected YouTube metadata fields
                        if "data" in data:
                            print(f"   ✅ Data field present")
                            if isinstance(data["data"], list) and len(data["data"]) > 0:
                                video_data = data["data"][0]
                                print(
                                    f"   Video data keys: {list(video_data.keys()) if isinstance(video_data, dict) else 'Not a dict'}"
                                )

                                # Check for key YouTube fields
                                youtube_fields = [
                                    "title",
                                    "video_id",
                                    "youtuber",
                                    "views",
                                    "preview_image",
                                ]
                                found_fields = [
                                    field
                                    for field in youtube_fields
                                    if field in video_data
                                ]
                                print(f"   ✅ Found YouTube fields: {found_fields}")

                        if "snapshot_id" in data:
                            print(f"   📊 Snapshot ID: {data['snapshot_id']}")
                        if "status" in data:
                            print(f"   📊 Status: {data['status']}")

                except Exception as e:
                    print(f"   ⚠️  Response parsing error: {e}")
                    print(
                        f"   Raw response (first 300 chars): {response.text[:300]}..."
                    )

            elif response.status_code == 400:
                try:
                    error = response.json()
                    print(f"   ❌ Bad Request: {error}")

                    # Analyze the error for insights
                    error_str = str(error).lower()
                    if "collector" in error_str:
                        print(f"   💡 Collector issue - check collector name/ID")
                    elif "dataset" in error_str:
                        print(f"   💡 Dataset issue - check dataset configuration")
                    elif "permission" in error_str:
                        print(f"   💡 Permission issue - check account access")

                except:
                    print(f"   ❌ Bad Request: {response.text[:200]}")

            elif response.status_code == 401:
                print(f"   🔑 Authentication failed - check API key")

            elif response.status_code == 403:
                print(f"   🚫 Forbidden - check account permissions for YouTube API")

            elif response.status_code == 404:
                print(f"   ❌ Endpoint not found")

            elif response.status_code == 429:
                print(f"   ⏱️  Rate limited - too many requests")

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

    print(f"📊 YouTube Posts API Test Results:")
    if successful_tests:
        print(f"   ✅ Working configurations: {successful_tests}")
        print(f"   🎉 YouTube metadata extraction is functional!")
        print(f"   📋 Next steps:")
        print(f"     - Update youtube_metadata.py with working configuration")
        print(f"     - Map response fields to YouTubeMetadata model")
        print(f"     - Test with actual video processing workflow")
        print(f"     - Verify all required fields are captured")
    else:
        print(f"   ❌ No working configurations found")
        print(f"   🔍 This indicates:")
        print(f"     - YouTube Posts API may not be enabled on your account")
        print(f"     - Collector needs to be created in Bright Data dashboard")
        print(f"     - Account may need upgrade for Web Scraper API access")
        print(f"   📞 Recommended: Contact Bright Data support for YouTube API access")


if __name__ == "__main__":
    test_youtube_posts_api()
