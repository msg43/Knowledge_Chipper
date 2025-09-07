#!/usr/bin/env python3
"""
Test YouTube Social Media API with correct endpoints (no collectors needed).
"""

import json

import requests


def test_social_media_api():
    """Test the YouTube Social Media API endpoints."""

    api_key = "ed14d427de1f0186066bbbc3d948808642f1a43c57c79d6259a2438f54e8de51"
    test_url = "https://www.youtube.com/watch?v=ksHkSuNTIKo"

    print("🎬 Testing YouTube Social Media API (No Collectors Required)")
    print("=" * 70)
    print(
        f"Based on: https://docs.brightdata.com/api-reference/web-scraper-api/social-media-apis/youtube"
    )
    print(f"Test video: {test_url}")
    print()

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Test different Social Media API endpoints
    api_tests = [
        {
            "name": "Health Check - Discover by Search",
            "endpoint": "https://api.brightdata.com/v1/social-media/youtube/discover/search",
            "payload": {
                "keyword_search": "python tutorial",
                "type": "video",
                "duration": "short",
            },
        },
        {
            "name": "Posts API - Collect by URL (Direct Video)",
            "endpoint": "https://api.brightdata.com/v1/social-media/youtube/posts/collect",
            "payload": {"url": test_url},
        },
        {
            "name": "Posts API - Alternative Endpoint",
            "endpoint": "https://api.brightdata.com/v1/social-media/youtube/posts",
            "payload": {"url": test_url},
        },
        {
            "name": "Discover by Keywords (General)",
            "endpoint": "https://api.brightdata.com/v1/social-media/youtube/discover/keywords",
            "payload": {"keyword": "programming"},
        },
    ]

    working_endpoints = []
    policy_errors = []

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

            # Check for policy errors in headers
            policy_code = response.headers.get("x-brd-err-code")
            policy_msg = response.headers.get("x-brd-err-msg")

            if policy_code or policy_msg:
                print(f"   🚫 POLICY ERROR:")
                print(f"      Code: {policy_code}")
                print(f"      Message: {policy_msg}")
                if "policy_20050" in str(policy_code):
                    print(f"   💡 This means: Complete KYC to enable YouTube routes")
                policy_errors.append(f"{test_case['name']}: {policy_code}")

            elif response.status_code == 200:
                print(f"   ✅ SUCCESS! Social Media API is working!")
                working_endpoints.append(test_case["name"])

                try:
                    data = response.json()
                    print(f"   Response type: {type(data)}")

                    if isinstance(data, dict):
                        print(f"   Response keys: {list(data.keys())}")

                        # Check for video data structure
                        if (
                            "data" in data
                            and isinstance(data["data"], list)
                            and len(data["data"]) > 0
                        ):
                            video_data = data["data"][0]
                            if isinstance(video_data, dict):
                                print(
                                    f"   📊 Video data fields: {list(video_data.keys())}"
                                )

                                # Check for key YouTube metadata fields
                                key_fields = [
                                    "title",
                                    "video_id",
                                    "url",
                                    "description",
                                    "youtuber",
                                    "views",
                                    "preview_image",
                                    "date_posted",
                                ]
                                found_fields = [
                                    f for f in key_fields if f in video_data
                                ]
                                if found_fields:
                                    print(f"   ✅ Found metadata: {found_fields}")

                        elif "results" in data:
                            print(
                                f"   📊 Results count: {len(data['results']) if isinstance(data['results'], list) else 'N/A'}"
                            )

                except Exception as e:
                    print(f"   ⚠️  Response parsing error: {e}")
                    print(
                        f"   Raw response (first 300 chars): {response.text[:300]}..."
                    )

            elif response.status_code == 400:
                try:
                    error = response.json()
                    print(f"   ❌ Bad Request: {error}")
                except:
                    print(f"   ❌ Bad Request: {response.text[:200]}")

            elif response.status_code == 401:
                print(f"   🔑 Authentication failed - check API key")

            elif response.status_code == 403:
                print(f"   🚫 Forbidden - check headers for policy info")
                try:
                    error = response.json()
                    print(f"   Error details: {error}")
                except:
                    print(f"   Response: {response.text[:200]}")

            elif response.status_code == 404:
                print(f"   ❌ Endpoint not found - may need different URL structure")

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

    print(f"📊 Social Media API Test Results:")
    if working_endpoints:
        print(f"   ✅ Working endpoints: {working_endpoints}")
        print(f"   🎉 YouTube Social Media API is functional!")
        print(f"   📋 Next steps:")
        print(f"     - Update youtube_metadata.py with working endpoint")
        print(f"     - Map Social Media API response to YouTubeMetadata model")
        print(f"     - Test video processing with Rich Meta data")

    elif policy_errors:
        print(f"   🚫 Policy restrictions found: {policy_errors}")
        print(f"   💡 Solution: Complete KYC verification in Bright Data dashboard")
        print(f"   📋 Steps:")
        print(f"     1. Log into https://brightdata.com/cp")
        print(f"     2. Complete KYC verification process")
        print(f"     3. Request 'Full access' for YouTube routes")
        print(f"     4. Retry API calls after approval")

    else:
        print(f"   ❌ No working endpoints found")
        print(f"   🔍 Check:")
        print(f"     - API key validity")
        print(f"     - Account status and billing")
        print(f"     - Bright Data service status")


if __name__ == "__main__":
    test_social_media_api()
