#!/usr/bin/env python3
"""
Debug script to diagnose YouTube transcript availability issues.
"""

import sys
from pathlib import Path

# Add the project source to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from knowledge_system.config import get_settings
from knowledge_system.logger import get_logger

logger = get_logger(__name__)


def debug_transcript_availability(video_url: str):
    """Debug transcript availability for a YouTube video."""

    print("=" * 60)
    print("YOUTUBE TRANSCRIPT DEBUGGING")
    print("=" * 60)

    # Extract video ID
    if "youtu.be/" in video_url:
        video_id = video_url.split("youtu.be/")[1].split("?")[0].split("&")[0]
    elif "watch?v=" in video_url:
        video_id = video_url.split("watch?v=")[1].split("&")[0]
    else:
        print(f"❌ Could not extract video ID from URL: {video_url}")
        return

    print(f"🔍 Video ID: {video_id}")
    print(f"🔗 URL: {video_url}")
    print()

    # Check WebShare credentials
    print("📋 CHECKING WEBSHARE CONFIGURATION")
    print("-" * 40)
    settings = get_settings()
    username = settings.api_keys.webshare_username
    password = settings.api_keys.webshare_password

    if not username:
        print("❌ WebShare username not configured")
    else:
        print(
            f"✅ WebShare username: {username[:4]}...{username[-4:] if len(username) > 8 else username}"
        )

    if not password:
        print("❌ WebShare password not configured")
    else:
        print(f"✅ WebShare password: {'*' * len(password)}")

    print()

    if not username or not password:
        print("⚠️  WebShare credentials missing - transcript extraction will fail")
        print("   Please configure WebShare Username and Password in Settings")
        return

    # Try to import and use the YouTube transcript API
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api.proxies import WebshareProxyConfig

        print("✅ YouTube Transcript API imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import YouTube Transcript API: {e}")
        return

    print()
    print("🔍 CHECKING TRANSCRIPT AVAILABILITY")
    print("-" * 40)

    # Set up WebShare proxy configuration
    proxy_config = WebshareProxyConfig(
        proxy_username=username, proxy_password=password, retries_when_blocked=3
    )

    try:
        # Create API instance with proxy
        api = YouTubeTranscriptApi(proxy_config=proxy_config)

        # Get available transcripts
        transcript_list = api.list(video_id)

        print("✅ Successfully connected to YouTube transcript API")
        print()

        # List all available transcripts
        available_transcripts = []
        for transcript in transcript_list:
            lang_code = getattr(transcript, "language_code", "unknown")
            is_manual = getattr(transcript, "is_manually_created", None)
            transcript_type = (
                "Manual"
                if is_manual
                else "Auto-generated"
                if is_manual is not None
                else "Unknown"
            )

            available_transcripts.append(
                {
                    "language_code": lang_code,
                    "is_manual": is_manual,
                    "type": transcript_type,
                }
            )

            print(f"📝 Found transcript: {lang_code} ({transcript_type})")

        if not available_transcripts:
            print("❌ No transcripts found for this video")
            print(
                "   This means YouTube does not provide any transcripts (manual or auto-generated)"
            )
            print(
                "   Even if you see subtitles in the web interface, they may not be available via API"
            )
        else:
            print()
            print("🧪 TESTING TRANSCRIPT RETRIEVAL")
            print("-" * 40)

            # Try to fetch the first available transcript
            for transcript in transcript_list:
                try:
                    lang_code = getattr(transcript, "language_code", "unknown")
                    print(f"Attempting to fetch {lang_code} transcript...")

                    transcript_data = transcript.fetch()
                    if transcript_data:
                        print(
                            f"✅ Successfully fetched {lang_code} transcript ({len(transcript_data)} segments)"
                        )

                        # Show first few segments
                        print("📄 First 3 transcript segments:")
                        for i, segment in enumerate(transcript_data[:3]):
                            # Handle both dict and object formats
                            if hasattr(segment, "text"):
                                text = segment.text
                                start = getattr(segment, "start", 0)
                            elif hasattr(segment, "get"):
                                text = segment.get("text", "No text")
                                start = segment.get("start", 0)
                            else:
                                text = str(segment)
                                start = 0
                            print(f"   {i+1}. [{start:.1f}s] {text}")
                        break
                    else:
                        print(f"❌ Empty transcript data for {lang_code}")
                except Exception as e:
                    print(f"❌ Failed to fetch {lang_code} transcript: {e}")
            else:
                print("❌ Could not fetch any transcripts")

    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error accessing transcript API: {error_msg}")

        # Categorize common errors
        if "407 Proxy Authentication Required" in error_msg:
            print("🔐 PROXY AUTHENTICATION FAILED")
            print("   Your WebShare credentials may be incorrect")
            print("   Please verify your WebShare Username and Password")
        elif "402 Payment Required" in error_msg:
            print("💰 WEBSHARE PAYMENT REQUIRED")
            print("   Your WebShare account is out of funds")
            print("   Please add payment at https://panel.webshare.io/")
        elif (
            "NoTranscriptFound" in error_msg or "Transcript not available" in error_msg
        ):
            print("📝 NO TRANSCRIPT AVAILABLE")
            print("   YouTube does not provide transcripts for this video")
            print(
                "   This can happen even if subtitles are visible in the web interface"
            )
        elif "Private video" in error_msg or "Video unavailable" in error_msg:
            print("🔒 VIDEO ACCESS RESTRICTED")
            print("   The video may be private, deleted, or region-restricted")
        else:
            print("🌐 NETWORK/CONNECTION ISSUE")
            print("   There may be a connectivity or proxy issue")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_transcript.py <youtube_url>")
        print(
            "Example: python debug_transcript.py https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        )
        sys.exit(1)

    video_url = sys.argv[1]
    debug_transcript_availability(video_url)
