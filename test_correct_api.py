#!/usr/bin/env python3
"""
Test to find the correct API structure for this account.
"""

import json

import requests


def test_correct_api():
    """Test different API base paths to find what works."""

    api_key = "ed14d427de1f0186066bbbc3d948808642f1a43c57c79d6259a2438f54e8de51"
    test_url = "https://www.youtube.com/watch?v=ksHkSuNTIKo"

    print("🔎 Finding Correct API Structure for Your Account")
    print("=" * 60)

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Test different API structures
    api_tests = [
        {
            "name": "Web Scraper API - Trigger",
            "url": "https://api.brightdata.com/webscraper/trigger",
            "payload": {"url": test_url},
        },
        {
            "name": "DCA API - Original",
            "url": "https://api.brightdata.com/dca/trigger",
            "payload": {"url": test_url},
        },
        {
            "name": "Datasets v1",
            "url": "https://api.brightdata.com/datasets/v1/trigger",
            "payload": {"url": test_url},
        },
        {
            "name": "Datasets v2",
            "url": "https://api.brightdata.com/datasets/v2/trigger",
            "payload": {"url": test_url},
        },
        {
            "name": "Simple Scraper API",
            "url": "https://api.brightdata.com/scraper/trigger",
            "payload": {"url": test_url},
        },
        {
            "name": "Zone-based API",
            "url": "https://api.brightdata.com/zone/scrape",
            "payload": {"url": test_url},
        },
        {
            "name": "Account Status Check",
            "url": "https://api.brightdata.com/account/status",
            "payload": None,
            "method": "GET",
        },
        {
            "name": "Basic Zones List",
            "url": "https://api.brightdata.com/zone",
            "payload": None,
            "method": "GET",
        },
    ]

    working_apis = []

    for i, test in enumerate(api_tests, 1):
        print(f"{i}. Testing: {test['name']}")
        print(f"   URL: {test['url']}")

        try:
            method = test.get("method", "POST")

            if method == "GET":
                response = requests.get(test["url"], headers=headers, timeout=15)
            else:
                response = requests.post(
                    test["url"], headers=headers, json=test["payload"], timeout=15
                )

            print(f"   Status: {response.status_code}")

            if response.status_code == 200:
                print(f"   ✅ SUCCESS! Found working API")
                working_apis.append(test["name"])
                try:
                    data = response.json()
                    print(
                        f"   Response: {type(data)} with keys {list(data.keys()) if isinstance(data, dict) else len(data) if isinstance(data, list) else 'unknown'}"
                    )
                except:
                    print(f"   Response: {response.text[:150]}...")

            elif response.status_code == 400:
                print(f"   📝 BAD REQUEST (endpoint exists)")
                working_apis.append(f"{test['name']} (needs correct params)")
                try:
                    error = response.json()
                    print(f"   Error: {error}")
                except:
                    print(f"   Error: {response.text[:100]}")

            elif response.status_code == 401:
                print(f"   🔑 Auth failed")

            elif response.status_code == 403:
                print(f"   🚫 Forbidden (endpoint exists)")
                working_apis.append(f"{test['name']} (access denied)")

            elif response.status_code == 404:
                print(f"   ❌ Not found")

            else:
                print(f"   ⚠️  Status {response.status_code}")
                working_apis.append(f"{test['name']} (status {response.status_code})")
                print(f"   Response: {response.text[:100]}")

        except requests.exceptions.Timeout:
            print(f"   ⏱️  Timeout")

        except Exception as e:
            print(f"   ❌ Error: {str(e)[:80]}")

        print()

    print(f"📊 API Discovery Results:")
    if working_apis:
        print(f"   ✅ Found working/existing APIs:")
        for api in working_apis:
            print(f"     - {api}")
        print(f"\n   💡 This shows which APIs your account has access to!")
    else:
        print(f"   ❌ No APIs responded positively")
        print(f"   🔍 This suggests a fundamental account or API key issue")

    print(f"\n🎯 Conclusion:")
    print(f"   - Any non-404 response means that API exists for your account")
    print(f"   - We can then figure out the correct payload format")
    print(f"   - 400/403 errors are actually good news (endpoint exists)")


if __name__ == "__main__":
    test_correct_api()
