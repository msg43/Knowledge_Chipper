#!/usr/bin/env python3
"""
Test the DCA endpoint with different collector IDs.
"""

import json

import requests


def test_dca_collectors():
    """Test the DCA endpoint with various collector IDs."""

    api_key = "ed14d427de1f0186066bbbc3d948808642f1a43c57c79d6259a2438f54e8de51"
    endpoint = "https://api.brightdata.com/dca/trigger"
    test_url = "https://www.youtube.com/watch?v=ksHkSuNTIKo"

    print("🧪 Testing DCA Endpoint with Different Collector IDs")
    print("=" * 60)
    print(f"Endpoint: {endpoint}")
    print(f"Test URL: {test_url}")
    print()

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Different collector IDs to try
    collector_variations = [
        # Simple formats
        "youtube",
        "youtube_posts",
        "youtube_scraper",
        "youtube_api",
        "youtube_dataset",
        "youtube_videos",
        "youtube_metadata",
        # Alternative naming
        "social_media_youtube",
        "web_scraper_youtube",
        "video_scraper",
        "yt_scraper",
        # Possible dataset names
        "gd_ld5m4gk19e",  # Example dataset ID format
        "gd_l36m9k18xo",  # Another example
        # Generic scrapers
        "web_scraper",
        "social_media",
        "video_platform",
    ]

    successful_collectors = []

    for i, collector in enumerate(collector_variations, 1):
        print(f"{i:2d}. Testing collector: '{collector}'")

        payload = {"collector": collector, "url": test_url}

        try:
            response = requests.post(
                endpoint, headers=headers, json=payload, timeout=15
            )

            if response.status_code == 200:
                print(f"    ✅ SUCCESS! Collector '{collector}' works")
                successful_collectors.append(collector)
                try:
                    data = response.json()
                    print(
                        f"    Response keys: {list(data.keys()) if isinstance(data, dict) else 'Non-dict response'}"
                    )
                except:
                    print(f"    Response: {response.text[:100]}...")

            elif response.status_code == 400:
                try:
                    error = response.json()
                    if "collector" in str(error).lower():
                        print(f"    ❌ Bad collector ID: {error}")
                    else:
                        print(f"    ⚠️  Bad request (different issue): {error}")
                except:
                    print(f"    ❌ Bad request: {response.text[:100]}")

            elif response.status_code == 401:
                print(f"    🔑 Auth error (collector might be restricted)")

            elif response.status_code == 403:
                print(f"    🚫 Forbidden (collector exists but not accessible)")

            elif response.status_code == 404:
                print(f"    ❌ Not found")

            else:
                print(f"    ⚠️  Status {response.status_code}: {response.text[:100]}")

        except requests.exceptions.Timeout:
            print(f"    ⏱️  Timeout")
        except Exception as e:
            print(f"    ❌ Error: {str(e)[:50]}")

    print(f"\n📊 Results:")
    if successful_collectors:
        print(f"   ✅ Working collector IDs: {successful_collectors}")
        print(f"   🎉 YouTube API scraper is working with DCA endpoint!")
    else:
        print(f"   ❌ No working collector IDs found")
        print(f"   💡 Next steps:")
        print(f"     - Check your Bright Data dashboard for available collectors")
        print(f"     - You may need to create a YouTube collector first")
        print(f"     - Contact Bright Data support for collector setup")


if __name__ == "__main__":
    test_dca_collectors()
