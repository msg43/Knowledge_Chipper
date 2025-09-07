#!/usr/bin/env python3
"""
Test to discover the correct Bright Data API endpoints.
"""

import json

import requests


def test_endpoint_discovery():
    """Try to discover the correct Bright Data API endpoints."""

    api_key = "ed14d427de1f0186066bbbc3d948808642f1a43c57c79d6259a2438f54e8de51"

    print("🔍 Discovering Bright Data API Endpoints")
    print("=" * 50)

    # Test different endpoint patterns
    base_urls = [
        "https://api.brightdata.com",
        "https://brightdata.com/api",
        "https://api.luminati.io",
    ]

    endpoint_patterns = [
        "/web-scraper/trigger",
        "/webscraper/trigger",
        "/scraper/trigger",
        "/datasets/trigger",
        "/dca/trigger",
        "/trigger",
        "/collector/trigger",
        "/social-media/youtube",
        "/api/scraper",
        "/api/webscraper",
    ]

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    simple_payload = {
        "collector": "youtube",
        "inputs": [{"url": "https://www.youtube.com/watch?v=ksHkSuNTIKo"}],
    }

    working_endpoints = []

    for base_url in base_urls:
        print(f"\n🌐 Testing base URL: {base_url}")

        for pattern in endpoint_patterns:
            full_url = base_url + pattern
            try:
                print(f"   Testing: {full_url}")
                response = requests.post(
                    full_url, headers=headers, json=simple_payload, timeout=10
                )

                if response.status_code == 200:
                    print(f"   ✅ SUCCESS: {response.status_code}")
                    working_endpoints.append(full_url)
                elif response.status_code == 401:
                    print(f"   🔑 AUTH NEEDED: {response.status_code} (endpoint exists)")
                    working_endpoints.append(f"{full_url} (auth issue)")
                elif response.status_code == 400:
                    print(
                        f"   📝 BAD REQUEST: {response.status_code} (endpoint exists, wrong payload)"
                    )
                    working_endpoints.append(f"{full_url} (payload issue)")
                    try:
                        error = response.json()
                        print(f"      Error: {error}")
                    except:
                        print(f"      Error: {response.text[:100]}")
                elif response.status_code == 404:
                    print(f"   ❌ NOT FOUND: {response.status_code}")
                else:
                    print(
                        f"   ⚠️  STATUS {response.status_code}: {response.text[:100]}"
                    )

            except requests.exceptions.Timeout:
                print(f"   ⏱️  TIMEOUT")
            except requests.exceptions.ConnectionError:
                print(f"   🔌 CONNECTION ERROR")
            except Exception as e:
                print(f"   ❌ ERROR: {str(e)[:50]}")

    print(f"\n📋 Summary:")
    if working_endpoints:
        print("   ✅ Found potentially working endpoints:")
        for endpoint in working_endpoints:
            print(f"     - {endpoint}")
    else:
        print("   ❌ No working endpoints found")
        print("   💡 Suggestions:")
        print("     - API key might not have Web Scraper permissions")
        print("     - YouTube scraper might not be enabled on your account")
        print("     - Try the dataset collection API instead")


if __name__ == "__main__":
    test_endpoint_discovery()
