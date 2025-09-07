#!/usr/bin/env python3
"""
Test the synchronous Web Scraper API for fresh YouTube metadata.
"""

import json
import time

import requests


def test_synchronous_scraper():
    """Test the synchronous /scrape endpoint for immediate YouTube data."""

    api_key = "ed14d427de1f0186066bbbc3d948808642f1a43c57c79d6259a2438f54e8de51"
    dataset_id = "gd_lk538t2k2p1k3oos71"
    test_url = "https://www.youtube.com/watch?v=ksHkSuNTIKo"

    print("🚀 Testing Synchronous Web Scraper API for Fresh YouTube Metadata")
    print("=" * 70)
    print(f"Dataset ID: {dataset_id}")
    print(f"Test video: {test_url}")
    print()

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Synchronous scrape endpoint
    scrape_url = f"https://api.brightdata.com/datasets/v3/scrape?dataset_id={dataset_id}&format=json"

    # Payload for synchronous request
    payload = {"input": [{"url": test_url}]}

    print(f"🎯 Testing Synchronous Scrape (Immediate Results)")
    print(f"   URL: {scrape_url}")
    print(f"   Payload: {json.dumps(payload, indent=6)}")

    try:
        # Make synchronous request with longer timeout for processing
        print(f"   🔄 Making synchronous request (may take 30-60 seconds)...")
        response = requests.post(
            scrape_url,
            headers=headers,
            json=payload,
            timeout=90,  # Allow up to 90 seconds for synchronous processing
        )

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
            print(f"   ✅ SUCCESS! Synchronous response received!")

            try:
                video_data = response.json()
                print(f"   Response type: {type(video_data)}")

                if isinstance(video_data, list) and len(video_data) > 0:
                    video_item = video_data[0]
                    if isinstance(video_item, dict):
                        print(f"\n   🎉 FRESH YOUTUBE METADATA RECEIVED!")
                        print(f"   📊 Video fields ({len(video_item)} total):")

                        # Show all available fields
                        for field in sorted(video_item.keys()):
                            value = video_item[field]
                            if isinstance(value, str) and len(value) > 60:
                                preview = value[:60] + "..."
                            else:
                                preview = str(value)
                            print(f"      {field}: {preview}")

                        print(f"\n   🎯 Key YouTube Metadata Mapping:")
                        # Map to our required fields
                        metadata_mapping = {
                            "video_id": video_item.get("video_id"),
                            "title": video_item.get("title"),
                            "url": video_item.get("url"),
                            "description": video_item.get("description"),
                            "uploader (youtuber)": video_item.get("youtuber"),
                            "uploader_id (youtuber_id)": video_item.get("youtuber_id"),
                            "upload_date (date_posted)": video_item.get("date_posted"),
                            "duration (video_length)": video_item.get("video_length"),
                            "view_count (views)": video_item.get("views"),
                            "like_count (likes)": video_item.get("likes"),
                            "comment_count (num_comments)": video_item.get(
                                "num_comments"
                            ),
                            "thumbnail_url (preview_image)": video_item.get(
                                "preview_image"
                            ),
                            "transcript": "YES"
                            if video_item.get("transcript")
                            else "NO",
                            "formatted_transcript": "YES"
                            if video_item.get("formatted_transcript")
                            else "NO",
                            "related_videos": f"{len(video_item.get('related_videos', []))} items"
                            if video_item.get("related_videos")
                            else "NO",
                            "channel_stats (subscribers)": video_item.get(
                                "subscribers"
                            ),
                            "verified": video_item.get("verified"),
                            "channel_url": video_item.get("channel_url"),
                            "avatar_img_channel": video_item.get("avatar_img_channel"),
                        }

                        found_count = 0
                        for field_name, value in metadata_mapping.items():
                            if value is not None and value != "NO":
                                found_count += 1
                                if isinstance(value, str) and len(value) > 50:
                                    display_value = value[:50] + "..."
                                else:
                                    display_value = value
                                print(f"      ✅ {field_name}: {display_value}")
                            else:
                                print(f"      ❌ {field_name}: Not available")

                        print(f"\n   📊 Results Summary:")
                        print(
                            f"      ✅ Metadata fields found: {found_count}/{len(metadata_mapping)}"
                        )
                        print(f"      🎬 Video processed successfully!")
                        print(f"      ⚡ Synchronous response - immediate results!")

                        return True  # Success!

                elif isinstance(video_data, dict):
                    print(f"   📊 Single video object: {list(video_data.keys())}")
                    # Handle single object response
                    if "data" in video_data:
                        print(
                            f"   📊 Contains data field with: {type(video_data['data'])}"
                        )
                else:
                    print(f"   ⚠️  Unexpected response format: {type(video_data)}")
                    print(f"   Raw response preview: {str(video_data)[:200]}...")

            except json.JSONDecodeError as e:
                print(f"   ❌ JSON parsing error: {e}")
                print(f"   Raw response (first 500 chars): {response.text[:500]}")

        elif response.status_code == 202:
            print(f"   ⏳ Async processing initiated (too complex for sync)")

            try:
                data = response.json()
                if "snapshot_id" in data:
                    snapshot_id = data["snapshot_id"]
                    print(f"   📊 Snapshot ID: {snapshot_id}")
                    print(f"   💡 Fall back to async polling...")

                    # Quick async polling attempt
                    status_url = (
                        f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}"
                    )
                    print(f"   🔄 Polling for results...")

                    for attempt in range(6):  # 1 minute of polling
                        time.sleep(10)
                        print(f"      Attempt {attempt + 1}/6...")

                        try:
                            status_response = requests.get(
                                status_url, headers=headers, timeout=15
                            )
                            if status_response.status_code == 200:
                                print(f"      ✅ Async data ready!")
                                # Could parse the async result here
                                break
                            else:
                                print(f"      ⏳ Status: {status_response.status_code}")
                        except:
                            print(f"      ❌ Polling error")

            except:
                print(f"   Response: {response.text[:200]}")

        elif response.status_code == 400:
            try:
                error = response.json()
                print(f"   ❌ Bad Request: {error}")
            except:
                print(f"   ❌ Bad Request: {response.text[:200]}")

        elif response.status_code == 401:
            print(f"   🔑 Authentication failed")

        elif response.status_code == 403:
            print(f"   🚫 Forbidden - check account permissions")

        elif response.status_code == 404:
            print(f"   ❌ Endpoint not found - check dataset ID or URL structure")

        else:
            print(f"   ⚠️  Status {response.status_code}")
            try:
                error = response.json()
                print(f"   Response: {error}")
            except:
                print(f"   Response: {response.text[:150]}")

    except requests.exceptions.Timeout:
        print(f"   ⏱️  Request timeout (>90s) - video processing taking too long")
        print(f"   💡 Consider using async /trigger endpoint for complex videos")

    except Exception as e:
        print(f"   ❌ Request error: {str(e)}")

    return False


if __name__ == "__main__":
    success = test_synchronous_scraper()

    if success:
        print(f"\n🎊 BREAKTHROUGH: Synchronous YouTube API Working!")
        print(
            f"📋 Ready to implement in your youtube_metadata.py and youtube_transcript.py"
        )
        print(f"⚡ This gives you immediate fresh metadata for any YouTube video!")
    else:
        print(f"\n💡 Next steps:")
        print(f"   - Check if synchronous endpoint needs different parameters")
        print(f"   - Fall back to async /trigger if sync times out")
        print(f"   - Consider yt-dlp enhanced solution as alternative")
