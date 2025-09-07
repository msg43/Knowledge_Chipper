#!/usr/bin/env python3
"""
Test various Social Media API endpoint patterns to find the correct structure.
"""

import json

import requests


def test_api_variations():
    """Test different API endpoint patterns for Social Media APIs."""

    api_key = "ed14d427de1f0186066bbbc3d948808642f1a43c57c79d6259a2438f54e8de51"
    test_url = "https://www.youtube.com/watch?v=ksHkSuNTIKo"

    print("🔍 Testing Various Social Media API Endpoint Patterns")
    print("=" * 70)

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Different endpoint pattern possibilities
    endpoint_patterns = [
        # Social Media API patterns
        {
            "name": "Social Media v1 - Search",
            "endpoint": "https://api.brightdata.com/v1/social-media/youtube/search",
            "payload": {"query": "python tutorial", "type": "video"},
        },
        {
            "name": "Social Media v1 - Posts (no discover)",
            "endpoint": "https://api.brightdata.com/v1/social-media/youtube/posts",
            "payload": {"url": test_url},
        },
        {
            "name": "Social Media API - Direct",
            "endpoint": "https://api.brightdata.com/social-media/youtube/posts",
            "payload": {"url": test_url},
        },
        {
            "name": "Datasets API - Social Media",
            "endpoint": "https://api.brightdata.com/datasets/social-media/youtube",
            "payload": {"inputs": [{"url": test_url}]},
        },
        {
            "name": "Web Scraper - Social Media",
            "endpoint": "https://api.brightdata.com/webscraper/social-media/youtube",
            "payload": {"url": test_url},
        },
        {
            "name": "API v2 - YouTube",
            "endpoint": "https://api.brightdata.com/v2/youtube/posts",
            "payload": {"url": test_url},
        },
        {
            "name": "Simple API - YouTube Direct",
            "endpoint": "https://api.brightdata.com/youtube/video",
            "payload": {"url": test_url},
        },
        {
            "name": "Scraping API - YouTube",
            "endpoint": "https://api.brightdata.com/scraping/youtube",
            "payload": {"url": test_url},
        },
    ]

    working_endpoints = []

    for i, test_case in enumerate(endpoint_patterns, 1):
        print(f"{i:2d}. Testing: {test_case['name']}")
        print(f"     Endpoint: {test_case['endpoint']}")

        try:
            response = requests.post(
                test_case["endpoint"],
                headers=headers,
                json=test_case["payload"],
                timeout=15,
            )

            print(f"     Status: {response.status_code}")

            # Check headers for policy errors
            policy_code = response.headers.get("x-brd-err-code")
            policy_msg = response.headers.get("x-brd-err-msg")

            if policy_code:
                print(f"     🚫 Policy: {policy_code} - {policy_msg}")
                working_endpoints.append(f"{test_case['name']} (needs KYC)")

            elif response.status_code == 200:
                print(f"     ✅ SUCCESS!")
                working_endpoints.append(test_case["name"])

                try:
                    data = response.json()
                    print(
                        f"     Response keys: {list(data.keys()) if isinstance(data, dict) else type(data)}"
                    )
                except:
                    print(f"     Response: {response.text[:100]}...")

            elif response.status_code == 400:
                try:
                    error = response.json()
                    print(f"     ❌ Bad Request: {error}")
                    if "collector" not in str(error).lower():
                        working_endpoints.append(f"{test_case['name']} (param issue)")
                except:
                    print(f"     ❌ Bad Request: {response.text[:100]}")

            elif response.status_code == 401:
                print(f"     🔑 Auth failed")

            elif response.status_code == 403:
                print(f"     🚫 Forbidden")
                working_endpoints.append(f"{test_case['name']} (access issue)")

            elif response.status_code == 404:
                print(f"     ❌ Not found")

            elif response.status_code == 422:
                print(f"     📝 Validation error")
                working_endpoints.append(f"{test_case['name']} (validation)")
                try:
                    error = response.json()
                    print(f"     Details: {error}")
                except:
                    pass

            else:
                print(f"     ⚠️  Status {response.status_code}")
                working_endpoints.append(
                    f"{test_case['name']} (status {response.status_code})"
                )

        except Exception as e:
            print(f"     ❌ Error: {str(e)[:50]}")

    print(f"\n📊 Results Summary:")
    if working_endpoints:
        print(f"   ✅ Potentially working endpoints:")
        for endpoint in working_endpoints:
            print(f"     - {endpoint}")
        print(f"\n   💡 Any non-404 response indicates the endpoint exists!")
    else:
        print(f"   ❌ All endpoints returned 404")
        print(f"   💡 This suggests the Social Media API structure is different")
        print(f"   📞 Recommendation: Contact Bright Data for current API documentation")


if __name__ == "__main__":
    test_api_variations()
