#!/usr/bin/env python3
"""
Test the new YouTube metadata extraction priority system.
"""

import os
import sys
from unittest.mock import MagicMock, patch


def test_priority_system():
    """Test that the priority system works correctly."""

    print("🧪 Testing YouTube Metadata Priority System")
    print("=" * 50)

    # Test 1: Check that unified method calls correct priorities
    print("1. Testing priority logic...")
    try:
        from src.knowledge_system.processors.youtube_metadata import (
            YouTubeMetadataProcessor,
        )

        processor = YouTubeMetadataProcessor()

        # Mock the extraction methods to track what gets called
        processor._extract_metadata_packetstream = MagicMock(return_value=None)
        processor._extract_metadata_direct_ytdlp = MagicMock(return_value=None)
        processor._extract_metadata_bright_data = MagicMock(return_value=None)

        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

        # Test with single URL (≤2 videos) - should try PacketStream, then direct yt-dlp
        print("   📍 Testing single URL (≤2 videos)...")
        result = processor._extract_metadata_unified(test_url, total_urls=1)

        # Verify PacketStream was called first
        processor._extract_metadata_packetstream.assert_called_once_with(test_url)
        print("   ✅ PacketStream tried first")

        # Verify direct yt-dlp was called as fallback (for ≤2 videos)
        processor._extract_metadata_direct_ytdlp.assert_called_once_with(test_url)
        print("   ✅ Direct yt-dlp tried as fallback (≤2 videos)")

        # Verify Bright Data was NOT called (disabled)
        processor._extract_metadata_bright_data.assert_not_called()
        print("   ✅ Bright Data NOT called (disabled)")

        # Reset mocks
        processor._extract_metadata_packetstream.reset_mock()
        processor._extract_metadata_direct_ytdlp.reset_mock()
        processor._extract_metadata_bright_data.reset_mock()

        # Test with 3 URLs (>2 videos) - should try PacketStream only, skip direct yt-dlp
        print("   📍 Testing batch of 3 URLs (>2 videos)...")
        result = processor._extract_metadata_unified(test_url, total_urls=3)

        # Verify PacketStream was called first
        processor._extract_metadata_packetstream.assert_called_once_with(test_url)
        print("   ✅ PacketStream tried first")

        # Verify direct yt-dlp was NOT called (>2 videos, bot detection risk)
        processor._extract_metadata_direct_ytdlp.assert_not_called()
        print("   ✅ Direct yt-dlp skipped (>2 videos, bot detection risk)")

        # Verify Bright Data was NOT called (disabled)
        processor._extract_metadata_bright_data.assert_not_called()
        print("   ✅ Bright Data NOT called (disabled)")

    except Exception as e:
        print(f"   ❌ Priority logic error: {e}")
        return False

    # Test 2: Check extraction method implementations exist
    print("2. Testing extraction method implementations...")
    try:
        # Check PacketStream method exists
        assert hasattr(processor, "_extract_metadata_packetstream")
        print("   ✅ PacketStream extraction method exists")

        # Check direct yt-dlp method exists
        assert hasattr(processor, "_extract_metadata_direct_ytdlp")
        print("   ✅ Direct yt-dlp extraction method exists")

        # Check conversion helper exists
        assert hasattr(processor, "_convert_ytdlp_to_metadata")
        print("   ✅ yt-dlp conversion helper exists")

        # Check duration parser exists
        assert hasattr(processor, "_parse_duration_string")
        print("   ✅ Duration parsing helper exists")

    except Exception as e:
        print(f"   ❌ Method implementation error: {e}")
        return False

    # Test 3: Test duration parsing utility
    print("3. Testing duration parsing...")
    try:
        # Test various duration formats
        assert processor._parse_duration_string("120") == 120
        assert processor._parse_duration_string("2:30") == 150  # 2 min 30 sec
        assert processor._parse_duration_string("1:02:30") == 3750  # 1 hr 2 min 30 sec
        assert processor._parse_duration_string(None) == None
        assert processor._parse_duration_string("") == None
        print("   ✅ Duration parsing works correctly")

    except Exception as e:
        print(f"   ❌ Duration parsing error: {e}")
        return False

    # Test 4: Check that Bright Data code is conserved but disabled
    print("4. Testing Bright Data conservation...")
    try:
        # Bright Data method should still exist (conserved)
        assert hasattr(processor, "_extract_metadata_bright_data")
        print("   ✅ Bright Data method conserved")

        # But the unified method should not call it (disabled)
        with patch.object(processor, "_extract_metadata_bright_data") as mock_bd:
            processor._extract_metadata_unified(test_url, total_urls=1)
            mock_bd.assert_not_called()
            print("   ✅ Bright Data method not invoked (disabled)")

    except Exception as e:
        print(f"   ❌ Bright Data conservation error: {e}")
        return False

    print("\n🎉 All priority system tests passed!")
    print("\n📋 Priority System Summary:")
    print("   🥇 PRIMARY: PacketStream proxy with yt-dlp")
    print("   🥈 FALLBACK: Direct yt-dlp (only for ≤2 videos)")
    print("   🚫 DISABLED: Bright Data (code conserved but not invoked)")
    print("\n🔧 Behavior:")
    print("   • 1-2 videos: PacketStream → Direct yt-dlp → Fail")
    print(
        "   • 3+ videos: PacketStream → Fail (no direct yt-dlp to avoid bot detection)"
    )
    print("   • Bright Data: Available in code but never called")

    return True


if __name__ == "__main__":
    try:
        success = test_priority_system()
        if not success:
            exit(1)
    except Exception as e:
        print(f"❌ Priority system test failed: {e}")
        exit(1)
