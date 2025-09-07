#!/usr/bin/env python3
"""
Test the correct Bright Data Datasets API structure for YouTube Posts.
"""

import json
import os
import time

import requests


def test_datasets_api():
    """Test the Datasets v3 API with different YouTube dataset IDs."""

    api_key = "ed14d427de1f0186066bbbc3d948808642f1a43c57c79d6259a2438f54e8de51"
    test_url = "https://www.youtube.com/watch?v=ksHkSuNTIKo"

    print("🎬 Testing Datasets v3 API for YouTube Posts")
    print("=" * 60)
    print(f"Based on: https://api.brightdata.com/datasets/v3/trigger")
    print(f"Test video: {test_url}")
    print()

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Common YouTube dataset IDs to try
    dataset_ids_to_try = [
        "gd_l7q8zkp1l8rwq7r",  # Common YouTube Posts dataset
        "gd_l36m9k18xo",  # Alternative format
        "gd_ld5m4gk19e",  # Another format
        "youtube_posts",  # Simple name
        "youtube",  # Generic
        "social_media_youtube",  # Descriptive name
    ]

    successful_triggers = []

    for i, dataset_id in enumerate(dataset_ids_to_try, 1):
        print(f"{i}. Testing Dataset ID: '{dataset_id}'")

        # Construct the trigger URL
        trigger_url = f"https://api.brightdata.com/datasets/v3/trigger?dataset_id={dataset_id}&format=json"

        # Request payload
        payload = [{"url": test_url}]

        print(f"   URL: {trigger_url}")
        print(f"   Payload: {json.dumps(payload)}")

        try:
            response = requests.post(
                trigger_url, headers=headers, json=payload, timeout=30
            )

            print(f"   Status: {response.status_code}")

            # Check for policy errors in headers
            policy_code = response.headers.get("x-brd-err-code")
            policy_msg = response.headers.get("x-brd-err-msg")

            if policy_code:
                print(f"   🚫 POLICY ERROR: {policy_code} - {policy_msg}")
                if "policy_20050" in str(policy_code):
                    print(f"   💡 This means: Complete KYC to enable YouTube routes")
                successful_triggers.append(f"{dataset_id} (needs KYC)")

            elif response.status_code == 200:
                print(f"   ✅ SUCCESS! Trigger accepted!")

                try:
                    data = response.json()
                    print(
                        f"   Response keys: {list(data.keys()) if isinstance(data, dict) else type(data)}"
                    )

                    if isinstance(data, dict) and "snapshot_id" in data:
                        snapshot_id = data["snapshot_id"]
                        print(f"   📊 Snapshot ID: {snapshot_id}")
                        successful_triggers.append(f"{dataset_id} -> {snapshot_id}")

                        # Try to fetch the data
                        print(f"   🔄 Attempting to fetch data...")
                        data_url = f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}/data?format=json"

                        # Poll for data (simple attempt)
                        for attempt in range(5):
                            print(f"   📥 Fetch attempt {attempt + 1}/5...")

                            try:
                                data_response = requests.get(
                                    data_url, headers=headers, timeout=15
                                )
                                print(f"      Data status: {data_response.status_code}")

                                if data_response.status_code == 200:
                                    if data_response.text.strip():
                                        print(f"   ✅ DATA RECEIVED!")
                                        try:
                                            video_data = data_response.json()
                                            print(
                                                f"      Data type: {type(video_data)}"
                                            )
                                            if (
                                                isinstance(video_data, list)
                                                and len(video_data) > 0
                                            ):
                                                video_item = video_data[0]
                                                if isinstance(video_item, dict):
                                                    print(
                                                        f"      Video fields: {list(video_item.keys())}"
                                                    )

                                                    # Check for key YouTube metadata
                                                    key_fields = [
                                                        "title",
                                                        "video_id",
                                                        "url",
                                                        "description",
                                                        "youtuber",
                                                        "views",
                                                        "preview_image",
                                                        "likes",
                                                    ]
                                                    found_fields = [
                                                        f
                                                        for f in key_fields
                                                        if f in video_item
                                                    ]
                                                    if found_fields:
                                                        print(
                                                            f"      ✅ YouTube metadata: {found_fields}"
                                                        )
                                        except:
                                            print(
                                                f"      Raw data preview: {data_response.text[:200]}..."
                                            )
                                        break
                                    else:
                                        print(f"      ⏳ No data yet (empty response)")

                                elif data_response.status_code == 202:
                                    print(f"      ⏳ Still processing...")

                                else:
                                    print(
                                        f"      ❌ Data fetch error: {data_response.status_code}"
                                    )
                                    break

                            except Exception as e:
                                print(f"      ❌ Data fetch exception: {str(e)[:50]}")
                                break

                            time.sleep(3)  # Wait before next attempt

                    else:
                        print(f"   ⚠️  Unexpected response format: {data}")

                except Exception as e:
                    print(f"   ⚠️  Response parsing error: {e}")
                    print(f"   Raw response: {response.text[:200]}...")

            elif response.status_code == 400:
                try:
                    error = response.json()
                    print(f"   ❌ Bad Request: {error}")

                    # Check for specific error types
                    error_str = str(error).lower()
                    if "dataset" in error_str:
                        print(f"   💡 Dataset ID '{dataset_id}' may not exist")
                    elif "permission" in error_str:
                        print(f"   💡 Permission issue with dataset")

                except:
                    print(f"   ❌ Bad Request: {response.text[:150]}")

            elif response.status_code == 401:
                print(f"   🔑 Authentication failed")
                break  # No point testing others

            elif response.status_code == 403:
                print(f"   🚫 Forbidden")
                successful_triggers.append(f"{dataset_id} (forbidden)")

            elif response.status_code == 404:
                print(f"   ❌ Dataset not found")

            else:
                print(f"   ⚠️  Status {response.status_code}")
                try:
                    error = response.json()
                    print(f"   Response: {error}")
                except:
                    print(f"   Response: {response.text[:100]}")

        except requests.exceptions.Timeout:
            print(f"   ⏱️  Request timeout")
        except Exception as e:
            print(f"   ❌ Error: {str(e)[:100]}")

        print()

    print(f"📊 Datasets v3 API Test Results:")
    if successful_triggers:
        print(f"   ✅ Working configurations:")
        for trigger in successful_triggers:
            print(f"     - {trigger}")
        print(f"\n   🎉 YouTube Datasets API is functional!")
        print(f"   📋 Next steps:")
        print(f"     - Use the working dataset_id in your code")
        print(f"     - Implement polling mechanism for data retrieval")
        print(f"     - Map response fields to YouTubeMetadata model")
    else:
        print(f"   ❌ No working dataset configurations found")
        print(f"   💡 This could mean:")
        print(f"     - Need to find correct dataset_id from Bright Data dashboard")
        print(f"     - Account may need specific YouTube API access")
        print(f"     - Dataset IDs are account-specific")


if __name__ == "__main__":
    test_datasets_api()
