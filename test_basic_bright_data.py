#!/usr/bin/env python3
"""
Test basic Bright Data API connectivity with simpler endpoints.
"""

import json

import requests


def test_basic_bright_data():
    """Test basic Bright Data API endpoints."""

    api_key = "ed14d427de1f0186066bbbc3d948808642f1a43c57c79d6259a2438f54e8de51"

    print("🧪 Testing Basic Bright Data API Connectivity")
    print("=" * 60)

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Test basic API endpoints to see what's available
    basic_tests = [
        {
            "name": "Account Status Check",
            "method": "GET",
            "endpoint": "https://api.brightdata.com/user",
            "payload": None,
        },
        {
            "name": "Zone List",
            "method": "GET",
            "endpoint": "https://api.brightdata.com/zone",
            "payload": None,
        },
        {
            "name": "Dataset List",
            "method": "GET",
            "endpoint": "https://api.brightdata.com/datasets",
            "payload": None,
        },
        {
            "name": "Web Scraper Collections",
            "method": "GET",
            "endpoint": "https://api.brightdata.com/collections",
            "payload": None,
        },
        {
            "name": "Simple DCA Test",
            "method": "POST",
            "endpoint": "https://api.brightdata.com/dca/trigger",
            "payload": {"url": "https://www.youtube.com/watch?v=ksHkSuNTIKo"},
        },
        {
            "name": "Scraper API Test",
            "method": "POST",
            "endpoint": "https://api.brightdata.com/scrape",
            "payload": {"url": "https://www.youtube.com/watch?v=ksHkSuNTIKo"},
        },
    ]

    available_endpoints = []

    for i, test in enumerate(basic_tests, 1):
        print(f"\n{i}. Testing: {test['name']}")
        print(f"   {test['method']} {test['endpoint']}")

        try:
            if test["method"] == "GET":
                response = requests.get(test["endpoint"], headers=headers, timeout=15)
            else:
                response = requests.post(
                    test["endpoint"], headers=headers, json=test["payload"], timeout=15
                )

            print(f"   Status: {response.status_code}")

            if response.status_code == 200:
                print(f"   ✅ SUCCESS!")
                available_endpoints.append(test["endpoint"])

                try:
                    data = response.json()
                    if isinstance(data, dict):
                        print(f"   Response keys: {list(data.keys())}")
                        # Show some useful info
                        if "zones" in data:
                            print(f"   Zones available: {len(data['zones'])}")
                        if "datasets" in data:
                            print(f"   Datasets available: {len(data['datasets'])}")
                        if "collections" in data:
                            print(
                                f"   Collections available: {len(data['collections'])}"
                            )
                    elif isinstance(data, list):
                        print(f"   Response: List with {len(data)} items")
                    else:
                        print(f"   Response type: {type(data)}")

                except Exception as e:
                    print(f"   Response parsing error: {e}")
                    print(f"   Raw response: {response.text[:200]}...")

            elif response.status_code == 401:
                print(f"   🔑 Authentication failed")

            elif response.status_code == 403:
                print(f"   🚫 Forbidden")

            elif response.status_code == 404:
                print(f"   ❌ Not found")

            elif response.status_code == 400:
                try:
                    error = response.json()
                    print(f"   ❌ Bad request: {error}")
                except:
                    print(f"   ❌ Bad request: {response.text[:100]}")

            else:
                print(f"   ⚠️  Status {response.status_code}")
                print(f"   Response: {response.text[:100]}")

        except requests.exceptions.Timeout:
            print(f"   ⏱️  Timeout")
        except requests.exceptions.ConnectionError as e:
            print(f"   🔌 Connection error")
        except Exception as e:
            print(f"   ❌ Error: {str(e)[:100]}")

    print(f"\n📊 Summary:")
    if available_endpoints:
        print(f"   ✅ Working endpoints found: {len(available_endpoints)}")
        for endpoint in available_endpoints:
            print(f"     - {endpoint}")
        print(f"\n   💡 This confirms your API key is working!")
        print(f"   🎯 The issue is likely with the specific YouTube API structure.")
    else:
        print(f"   ❌ No working endpoints found")
        print(f"   🔍 This suggests a fundamental API access issue")


if __name__ == "__main__":
    test_basic_bright_data()
