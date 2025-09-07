#!/usr/bin/env python3
"""
Test YouTube Posts API with the correct dataset ID.
"""

import json
import time

import requests


def test_youtube_dataset():
    """Test the YouTube Posts API with the correct dataset ID."""

    api_key = "ed14d427de1f0186066bbbc3d948808642f1a43c57c79d6259a2438f54e8de51"
    dataset_id = "gd_lk538t2k2p1k3oos71"
    test_url = "https://www.youtube.com/watch?v=ksHkSuNTIKo"

    print("🎬 Testing YouTube Posts API with Correct Dataset ID")
    print("=" * 60)
    print(f"Dataset ID: {dataset_id}")
    print(f"Test video: {test_url}")
    print()

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Trigger URL
    trigger_url = f"https://api.brightdata.com/datasets/v3/trigger?dataset_id={dataset_id}&format=json"

    # Request payload
    payload = [{"url": test_url}]

    print(f"🚀 Step 1: Triggering Data Collection")
    print(f"   URL: {trigger_url}")
    print(f"   Payload: {json.dumps(payload)}")

    try:
        # 1. Trigger the collection
        response = requests.post(trigger_url, headers=headers, json=payload, timeout=30)

        print(f"   Status: {response.status_code}")

        # Check for policy errors
        policy_code = response.headers.get("x-brd-err-code")
        policy_msg = response.headers.get("x-brd-err-msg")

        if policy_code:
            print(f"   🚫 POLICY ERROR:")
            print(f"      Code: {policy_code}")
            print(f"      Message: {policy_msg}")
            if "policy_20050" in str(policy_code):
                print(
                    f"   💡 Solution: Complete KYC verification in Bright Data dashboard"
                )
            return

        elif response.status_code == 200:
            print(f"   ✅ SUCCESS! Collection triggered!")

            try:
                data = response.json()
                print(
                    f"   Response keys: {list(data.keys()) if isinstance(data, dict) else type(data)}"
                )

                if isinstance(data, dict) and "snapshot_id" in data:
                    snapshot_id = data["snapshot_id"]
                    print(f"   📊 Snapshot ID: {snapshot_id}")

                    # 2. Poll for the data
                    print(f"\n📥 Step 2: Fetching Video Data")
                    data_url = f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}/data?format=json"
                    print(f"   Data URL: {data_url}")

                    max_attempts = 10
                    for attempt in range(max_attempts):
                        print(f"\n   📥 Attempt {attempt + 1}/{max_attempts}...")

                        try:
                            data_response = requests.get(
                                data_url, headers=headers, timeout=20
                            )
                            print(f"      Status: {data_response.status_code}")

                            if data_response.status_code == 200:
                                if data_response.text.strip():
                                    print(f"   ✅ VIDEO DATA RECEIVED!")

                                    try:
                                        video_data = data_response.json()
                                        print(f"      Data type: {type(video_data)}")

                                        if (
                                            isinstance(video_data, list)
                                            and len(video_data) > 0
                                        ):
                                            video_item = video_data[0]
                                            if isinstance(video_item, dict):
                                                print(
                                                    f"      📊 Video metadata fields ({len(video_item)} total):"
                                                )

                                                # Show all available fields
                                                for field in sorted(video_item.keys()):
                                                    value = video_item[field]
                                                    if (
                                                        isinstance(value, str)
                                                        and len(value) > 50
                                                    ):
                                                        preview = value[:50] + "..."
                                                    else:
                                                        preview = str(value)
                                                    print(
                                                        f"         {field}: {preview}"
                                                    )

                                                print(
                                                    f"\n      🎯 Key YouTube Fields Found:"
                                                )
                                                # Check for our required fields
                                                key_mappings = {
                                                    "video_id": video_item.get(
                                                        "video_id"
                                                    ),
                                                    "title": video_item.get("title"),
                                                    "url": video_item.get("url"),
                                                    "description": video_item.get(
                                                        "description"
                                                    ),
                                                    "youtuber (uploader)": video_item.get(
                                                        "youtuber"
                                                    ),
                                                    "youtuber_id": video_item.get(
                                                        "youtuber_id"
                                                    ),
                                                    "date_posted": video_item.get(
                                                        "date_posted"
                                                    ),
                                                    "video_length": video_item.get(
                                                        "video_length"
                                                    ),
                                                    "views": video_item.get("views"),
                                                    "likes": video_item.get("likes"),
                                                    "num_comments": video_item.get(
                                                        "num_comments"
                                                    ),
                                                    "preview_image": video_item.get(
                                                        "preview_image"
                                                    ),
                                                    "transcript": video_item.get(
                                                        "transcript"
                                                    ),
                                                    "formatted_transcript": video_item.get(
                                                        "formatted_transcript"
                                                    ),
                                                    "related_videos": video_item.get(
                                                        "related_videos"
                                                    ),
                                                    "subscribers": video_item.get(
                                                        "subscribers"
                                                    ),
                                                    "verified": video_item.get(
                                                        "verified"
                                                    ),
                                                    "avatar_img_channel": video_item.get(
                                                        "avatar_img_channel"
                                                    ),
                                                    "channel_url": video_item.get(
                                                        "channel_url"
                                                    ),
                                                }

                                                found_fields = []
                                                missing_fields = []

                                                for (
                                                    field_name,
                                                    value,
                                                ) in key_mappings.items():
                                                    if value is not None:
                                                        found_fields.append(field_name)
                                                        if (
                                                            isinstance(value, str)
                                                            and len(value) > 30
                                                        ):
                                                            print(
                                                                f"         ✅ {field_name}: {str(value)[:30]}..."
                                                            )
                                                        else:
                                                            print(
                                                                f"         ✅ {field_name}: {value}"
                                                            )
                                                    else:
                                                        missing_fields.append(
                                                            field_name
                                                        )

                                                print(f"\n      📊 Summary:")
                                                print(
                                                    f"         ✅ Found: {len(found_fields)}/{len(key_mappings)} required fields"
                                                )
                                                if missing_fields:
                                                    print(
                                                        f"         ❌ Missing: {missing_fields}"
                                                    )

                                                print(
                                                    f"\n   🎉 SUCCESS! YouTube Posts API is working with rich metadata!"
                                                )

                                        elif isinstance(video_data, dict):
                                            print(
                                                f"      Single video object: {list(video_data.keys())}"
                                            )
                                        else:
                                            print(
                                                f"      Unexpected data format: {type(video_data)}"
                                            )

                                    except json.JSONDecodeError as e:
                                        print(f"      ❌ JSON parsing error: {e}")
                                        print(
                                            f"      Raw response (first 500 chars): {data_response.text[:500]}"
                                        )

                                    break  # Success, exit polling loop

                                else:
                                    print(f"      ⏳ No data yet (empty response)")

                            elif data_response.status_code == 202:
                                print(f"      ⏳ Still processing...")

                            elif data_response.status_code == 404:
                                print(f"      ❌ Snapshot not found - may have expired")
                                break

                            else:
                                print(
                                    f"      ❌ Data fetch error: {data_response.status_code}"
                                )
                                try:
                                    error = data_response.json()
                                    print(f"      Error: {error}")
                                except:
                                    print(f"      Response: {data_response.text[:100]}")
                                break

                        except Exception as e:
                            print(f"      ❌ Data fetch exception: {str(e)[:100]}")
                            break

                        if attempt < max_attempts - 1:
                            wait_time = min(
                                5, 2**attempt
                            )  # Exponential backoff, max 5 seconds
                            print(
                                f"      ⏱️  Waiting {wait_time} seconds before retry..."
                            )
                            time.sleep(wait_time)

                    else:
                        print(
                            f"\n   ⏱️  Timeout: Data not ready after {max_attempts} attempts"
                        )
                        print(
                            f"   💡 The collection may still be processing - try fetching data later"
                        )

                else:
                    print(f"   ⚠️  Unexpected trigger response: {data}")

            except Exception as e:
                print(f"   ❌ Response parsing error: {e}")
                print(f"   Raw response: {response.text[:300]}")

        elif response.status_code == 400:
            try:
                error = response.json()
                print(f"   ❌ Bad Request: {error}")
            except:
                print(f"   ❌ Bad Request: {response.text[:200]}")

        elif response.status_code == 401:
            print(f"   🔑 Authentication failed - check API key")

        elif response.status_code == 403:
            print(f"   🚫 Forbidden - check account permissions")

        elif response.status_code == 404:
            print(f"   ❌ Dataset not found - check dataset ID")

        else:
            print(f"   ⚠️  Status {response.status_code}")
            try:
                error = response.json()
                print(f"   Response: {error}")
            except:
                print(f"   Response: {response.text[:150]}")

    except Exception as e:
        print(f"   ❌ Request error: {str(e)}")


if __name__ == "__main__":
    test_youtube_dataset()
