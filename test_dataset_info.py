#!/usr/bin/env python3
"""
Test to get information about the dataset and available endpoints.
"""

import json

import requests


def test_dataset_info():
    """Test to understand what this dataset actually is."""

    api_key = "ed14d427de1f0186066bbbc3d948808642f1a43c57c79d6259a2438f54e8de51"
    dataset_id = "gd_lk538t2k2p1k3oos71"

    print("🔍 Diagnosing Dataset and API Structure")
    print("=" * 50)
    print(f"Dataset ID: {dataset_id}")
    print()

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Test different diagnostic endpoints
    diagnostic_tests = [
        {
            "name": "Get Dataset Info",
            "method": "GET",
            "url": f"https://api.brightdata.com/datasets/v3/{dataset_id}",
            "payload": None,
        },
        {
            "name": "List Available Datasets",
            "method": "GET",
            "url": "https://api.brightdata.com/datasets/v3",
            "payload": None,
        },
        {
            "name": "Get Account Info",
            "method": "GET",
            "url": "https://api.brightdata.com/user",
            "payload": None,
        },
        {
            "name": "Check Dataset Status",
            "method": "GET",
            "url": f"https://api.brightdata.com/datasets/v3/{dataset_id}/status",
            "payload": None,
        },
        {
            "name": "Test Invalid Dataset",
            "method": "POST",
            "url": f"https://api.brightdata.com/datasets/v3/trigger?dataset_id=invalid_test&format=json",
            "payload": [{"url": "https://www.youtube.com/watch?v=test"}],
        },
        {
            "name": "Test Without Dataset ID",
            "method": "POST",
            "url": "https://api.brightdata.com/datasets/v3/trigger?format=json",
            "payload": [{"url": "https://www.youtube.com/watch?v=test"}],
        },
    ]

    working_endpoints = []

    for i, test in enumerate(diagnostic_tests, 1):
        print(f"{i}. Testing: {test['name']}")
        print(f"   {test['method']} {test['url']}")

        try:
            if test["method"] == "GET":
                response = requests.get(test["url"], headers=headers, timeout=10)
            else:
                response = requests.post(
                    test["url"], headers=headers, json=test["payload"], timeout=10
                )

            print(f"   Status: {response.status_code}")

            if response.status_code == 200:
                print(f"   ✅ SUCCESS!")
                working_endpoints.append(test["name"])

                try:
                    data = response.json()
                    print(f"   Response type: {type(data)}")

                    if isinstance(data, dict):
                        print(f"   Keys: {list(data.keys())}")

                        # Look for dataset information
                        if "datasets" in data:
                            datasets = data["datasets"]
                            print(f"   📊 Found {len(datasets)} datasets")
                            if isinstance(datasets, list) and len(datasets) > 0:
                                print(
                                    f"   Sample dataset: {datasets[0] if datasets else 'None'}"
                                )

                        elif "name" in data or "type" in data:
                            print(f"   📊 Dataset info: {data}")

                    elif isinstance(data, list):
                        print(f"   List with {len(data)} items")
                        if len(data) > 0:
                            print(f"   Sample: {data[0]}")

                except Exception as e:
                    print(f"   Raw response: {response.text[:200]}...")

            elif response.status_code == 401:
                print(f"   🔑 Auth failed")

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

        except Exception as e:
            print(f"   ❌ Error: {str(e)[:100]}")

        print()

    print(f"📊 Diagnostic Results:")
    if working_endpoints:
        print(f"   ✅ Working endpoints: {working_endpoints}")
    else:
        print(f"   ❌ No endpoints returned useful information")

    print(f"\n💡 Next Steps:")
    print(f"   1. Check your Bright Data dashboard for the correct dataset ID")
    print(f"   2. Verify YouTube Posts API is enabled on your account")
    print(f"   3. Try a known working dataset ID from documentation")
    print(f"   4. Contact Bright Data support with your account details")


if __name__ == "__main__":
    test_dataset_info()
