#!/usr/bin/env python3
"""
Diagnostic script to check why YouTube metadata isn't appearing in transcripts.

Usage:
    python scripts/diagnose_metadata_issue.py VIDEO_ID_OR_URL

Example:
    python scripts/diagnose_metadata_issue.py dQw4w9WgXcQ
    python scripts/diagnose_metadata_issue.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from knowledge_system.database.service import DatabaseService
from knowledge_system.utils.video_id_extractor import VideoIDExtractor


def diagnose(video_id_or_url: str):
    """Diagnose metadata issue for a video."""

    print("=" * 80)
    print("YouTube Metadata Diagnostic Tool")
    print("=" * 80)
    print()

    # Extract video_id if URL provided
    if "youtube.com" in video_id_or_url or "youtu.be" in video_id_or_url:
        print(f"🔍 Extracting video_id from URL: {video_id_or_url}")
        try:
            video_id = VideoIDExtractor.extract_video_id(video_id_or_url)
            print(f"✅ Extracted video_id: {video_id}")
        except Exception as e:
            print(f"❌ Failed to extract video_id: {e}")
            return
    else:
        video_id = video_id_or_url
        print(f"🔍 Using video_id: {video_id}")

    print()
    print("-" * 80)
    print("Step 1: Checking database for video record...")
    print("-" * 80)

    # Query database
    db = DatabaseService()
    video = db.get_video(video_id)

    if not video:
        print(f"❌ NO VIDEO FOUND IN DATABASE for video_id: {video_id}")
        print()
        print("This is the problem! The video needs to be downloaded first.")
        print()
        print("Solutions:")
        print("  1. Download the video through the YouTube tab first")
        print(
            "  2. Or paste the YouTube URL in the Transcription tab (it will download automatically)"
        )
        print()
        print(
            "The video must be downloaded through the app to save metadata to database."
        )
        return

    print(f"✅ Found video in database: {video.title}")
    print()

    print("-" * 80)
    print("Step 2: Checking metadata fields...")
    print("-" * 80)
    print()

    # Check each metadata field
    checks = {
        "Title": video.title,
        "Description": video.description,
        "Thumbnail Path": video.thumbnail_local_path,
        "Uploader": video.uploader,
        "Upload Date": video.upload_date,
        "Duration": video.duration_seconds,
        "View Count": video.view_count,
    }

    all_good = True
    for field_name, field_value in checks.items():
        if field_value:
            if field_name == "Description":
                preview = (
                    str(field_value)[:80] + "..."
                    if len(str(field_value)) > 80
                    else str(field_value)
                )
                print(f"✅ {field_name}: {preview}")
            else:
                print(f"✅ {field_name}: {field_value}")
        else:
            print(f"❌ {field_name}: MISSING (None/empty)")
            all_good = False

    print()

    # Check tags
    tags = []
    if video.platform_tags:
        tags = [
            tag_assoc.tag.tag_name for tag_assoc in video.platform_tags if tag_assoc.tag
        ]

    if tags:
        print(f"✅ Tags: {len(tags)} tags found")
        print(f"   First 5: {tags[:5]}")
    else:
        print(f"❌ Tags: MISSING (no tags in database)")
        all_good = False

    print()

    # Check categories
    categories = []
    if video.platform_categories:
        categories = [
            cat_assoc.category.category_name
            for cat_assoc in video.platform_categories
            if cat_assoc.category
        ]

    if categories:
        print(f"✅ Categories: {categories}")
    else:
        print(f"⚠️  Categories: None (this is optional)")

    print()

    # Check thumbnail file
    if video.thumbnail_local_path:
        thumb_path = Path(video.thumbnail_local_path)
        if thumb_path.exists():
            print(f"✅ Thumbnail file exists: {thumb_path}")
        else:
            print(
                f"⚠️  Thumbnail path in database but file doesn't exist: {thumb_path}"
            )
            print(f"   The markdown will include the path, but image won't display")

    print()
    print("=" * 80)

    if all_good and tags:
        print("✅ ALL METADATA PRESENT - Transcription should include everything!")
        print()
        print("If your transcript .md file is still missing metadata:")
        print("  1. Check the logs for the messages I added:")
        print("     - '✅ Extracted video_id from...'")
        print("     - '🔍 Querying database for video_id...'")
        print("     - '✅ Retrieved YouTube metadata...'")
        print("     - '✅ Embedded thumbnail in markdown'")
        print("     - '✅ Added description to markdown'")
        print("     - '✅ Added N tags to YAML frontmatter'")
        print()
        print("  2. Make sure the filename contains the video_id:")
        print(f"     - Should be like: 'Title_{video_id}.webm'")
        print(f"     - Or: 'Title [{video_id}].webm'")
    else:
        print("❌ METADATA INCOMPLETE - This is why it's not appearing!")
        print()
        print("The video was downloaded but metadata wasn't saved properly.")
        print()
        print("Solutions:")
        print("  1. Delete the video from database and re-download")
        print("  2. Or manually update the database fields")
        print("  3. Check if yt-dlp is up to date (might be YouTube API changes)")

    print("=" * 80)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/diagnose_metadata_issue.py VIDEO_ID_OR_URL")
        print()
        print("Examples:")
        print("  python scripts/diagnose_metadata_issue.py dQw4w9WgXcQ")
        print(
            '  python scripts/diagnose_metadata_issue.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ"'
        )
        sys.exit(1)

    diagnose(sys.argv[1])
