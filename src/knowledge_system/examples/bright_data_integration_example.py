"""
Example integration of Bright Data adapters with existing processors.

Demonstrates how to use Bright Data JSON responses with existing YouTubeMetadata
and YouTubeTranscript models for seamless compatibility.
"""

from typing import Any

from ..database import DatabaseService
from ..logger import get_logger
from ..processors.youtube_metadata import YouTubeMetadata
from ..processors.youtube_transcript import YouTubeTranscript
from ..utils.bright_data_adapters import (
    BrightDataAdapter,
    adapt_bright_data_metadata,
    adapt_bright_data_transcript,
)

logger = get_logger(__name__)


def process_bright_data_youtube_response(
    bright_data_response: dict[str, Any],
    video_url: str,
    include_transcript: bool = True,
) -> dict[str, Any]:
    """
    Complete example of processing Bright Data YouTube API response.

    Shows how to:
    1. Validate Bright Data response
    2. Adapt to existing models
    3. Store in database
    4. Generate output files

    Args:
        bright_data_response: Raw JSON from Bright Data YouTube API Scraper
        video_url: Original YouTube URL
        include_transcript: Whether to process transcript data

    Returns:
        Processing results with adapted models and database IDs
    """
    results = {
        "success": False,
        "video_metadata": None,
        "transcript": None,
        "database_records": {},
        "errors": [],
    }

    try:
        # Step 1: Validate Bright Data response
        if not BrightDataAdapter.validate_bright_data_response(bright_data_response):
            results["errors"].append("Invalid Bright Data response format")
            return results

        logger.info(f"Processing Bright Data response for: {video_url}")

        # Step 2: Adapt metadata to existing YouTubeMetadata model
        try:
            metadata = adapt_bright_data_metadata(bright_data_response, video_url)
            results["video_metadata"] = metadata
            logger.info(f"Successfully adapted metadata for video {metadata.video_id}")

            # Step 3: Store metadata in database
            db_service = DatabaseService()
            video_record = db_service.create_video(
                video_id=metadata.video_id,
                title=metadata.title,
                url=metadata.url,
                uploader=metadata.uploader,
                duration_seconds=metadata.duration,
                upload_date=metadata.upload_date,
                description=metadata.description,
                status="completed",
                extraction_method=metadata.extraction_method,
                thumbnail_url=metadata.thumbnail_url,
                tags_json=metadata.tags,
                categories_json=metadata.categories,
                # New enhanced fields
                related_videos_json=metadata.related_videos,
                channel_stats_json=metadata.channel_stats,
                video_chapters_json=metadata.video_chapters,
            )

            if video_record:
                results["database_records"]["video"] = video_record.video_id
                logger.info(
                    f"Stored video metadata in database: {video_record.video_id}"
                )

        except Exception as e:
            error_msg = f"Failed to adapt/store metadata: {e}"
            results["errors"].append(error_msg)
            logger.error(error_msg)

        # Step 4: Process transcript if available and requested
        if include_transcript:
            try:
                transcript = adapt_bright_data_transcript(
                    bright_data_response, video_url
                )
                results["transcript"] = transcript
                logger.info(
                    f"Successfully adapted transcript for video {transcript.video_id}"
                )

                # Store transcript in database
                if (
                    transcript.transcript_text
                ):  # Only store if we have actual transcript text
                    transcript_record = db_service.create_transcript(
                        video_id=transcript.video_id,
                        language=transcript.language,
                        transcript_text=transcript.transcript_text,
                        transcript_segments_json=transcript.transcript_data,
                        transcript_type="bright_data_api",
                        is_manual=transcript.is_manual,
                    )

                    if transcript_record:
                        results["database_records"][
                            "transcript"
                        ] = transcript_record.transcript_id
                        logger.info(
                            f"Stored transcript in database: {transcript_record.transcript_id}"
                        )

            except Exception as e:
                error_msg = f"Failed to adapt/store transcript: {e}"
                results["errors"].append(error_msg)
                logger.error(error_msg)

        # Step 5: Mark as successful if we got at least metadata
        results["success"] = results["video_metadata"] is not None

        if results["success"]:
            logger.info(f"Successfully processed Bright Data response for {video_url}")
        else:
            logger.error(f"Failed to process Bright Data response for {video_url}")

        return results

    except Exception as e:
        error_msg = f"Critical error processing Bright Data response: {e}"
        results["errors"].append(error_msg)
        logger.error(error_msg)
        return results


def compare_yt_dlp_vs_bright_data_output():
    """
    Example comparison between yt-dlp output and Bright Data API response.

    Shows how both sources can be adapted to the same YouTubeMetadata model
    for consistent processing.
    """
    # Example yt-dlp output (current format)
    yt_dlp_output = {
        "id": "dQw4w9WgXcQ",
        "title": "Rick Astley - Never Gonna Give You Up (Official Video)",
        "uploader": "Rick Astley",
        "upload_date": "20091025",
        "duration": 212,
        "view_count": 1234567890,
        "like_count": 9876543,
        "description": "The official video for Rick Astley's hit song",
        "tags": ["rick astley", "never gonna give you up", "80s"],
        "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
    }

    # Example Bright Data API response (new format)
    bright_data_output = {
        "id": "dQw4w9WgXcQ",
        "title": "Rick Astley - Never Gonna Give You Up (Official Video)",
        "videoDetails": {
            "lengthSeconds": "212",
            "viewCount": "1234567890",
            "author": "Rick Astley",
            "channelId": "UCuAXFkgsw1L7xaCfnd5JJOw",
        },
        "statistics": {"viewCount": "1234567890", "likeCount": "9876543"},
        "snippet": {
            "publishedAt": "2009-10-25T00:00:00Z",
            "channelTitle": "Rick Astley",
            "tags": ["rick astley", "never gonna give you up", "80s"],
            "description": "The official video for Rick Astley's hit song",
            "thumbnails": {
                "high": {"url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg"}
            },
        },
    }

    url = "https://youtube.com/watch?v=dQw4w9WgXcQ"

    # Adapt yt-dlp output (existing logic)
    yt_dlp_metadata = YouTubeMetadata(
        video_id=yt_dlp_output["id"],
        title=yt_dlp_output["title"],
        url=url,
        uploader=yt_dlp_output["uploader"],
        upload_date=yt_dlp_output["upload_date"],
        duration=yt_dlp_output["duration"],
        view_count=yt_dlp_output["view_count"],
        like_count=yt_dlp_output["like_count"],
        description=yt_dlp_output["description"],
        tags=yt_dlp_output["tags"],
        thumbnail_url=yt_dlp_output["thumbnail"],
        extraction_method="yt-dlp",
    )

    # Adapt Bright Data output (new logic)
    bright_data_metadata = adapt_bright_data_metadata(bright_data_output, url)

    # Compare results - should be nearly identical
    print("=== yt-dlp Metadata ===")
    print(f"Video ID: {yt_dlp_metadata.video_id}")
    print(f"Title: {yt_dlp_metadata.title}")
    print(f"Duration: {yt_dlp_metadata.duration}")
    print(f"Views: {yt_dlp_metadata.view_count}")
    print(f"Extraction: {yt_dlp_metadata.extraction_method}")

    print("\n=== Bright Data Metadata ===")
    print(f"Video ID: {bright_data_metadata.video_id}")
    print(f"Title: {bright_data_metadata.title}")
    print(f"Duration: {bright_data_metadata.duration}")
    print(f"Views: {bright_data_metadata.view_count}")
    print(f"Extraction: {bright_data_metadata.extraction_method}")

    # Both should be compatible with existing database/processing logic
    assert yt_dlp_metadata.video_id == bright_data_metadata.video_id
    assert yt_dlp_metadata.title == bright_data_metadata.title
    assert yt_dlp_metadata.duration == bright_data_metadata.duration
    assert yt_dlp_metadata.view_count == bright_data_metadata.view_count

    print("\n✅ Both formats successfully adapted to identical YouTubeMetadata models!")
    return yt_dlp_metadata, bright_data_metadata


def demonstrate_error_handling():
    """
    Demonstrate robust error handling with malformed Bright Data responses.
    """
    # Test various malformed responses
    test_cases = [
        ({}, "Empty response"),
        ({"title": None}, "Null title"),
        ({"corrupted": "data"}, "Irrelevant data"),
        ({"videoDetails": {"invalid": True}}, "Malformed structure"),
    ]

    url = "https://youtube.com/watch?v=test123"

    for response, description in test_cases:
        try:
            print(f"\n--- Testing: {description} ---")

            # Should not raise exceptions
            metadata = adapt_bright_data_metadata(response, url)
            transcript = adapt_bright_data_transcript(response, url)

            print(f"✅ Metadata adapted: {metadata.video_id} - {metadata.title}")
            print(f"✅ Transcript adapted: {transcript.video_id} - {transcript.title}")

            # Verify they're valid model instances
            assert isinstance(metadata, YouTubeMetadata)
            assert isinstance(transcript, YouTubeTranscript)

        except Exception as e:
            print(f"❌ Unexpected error with {description}: {e}")
            raise

    print("\n✅ All error cases handled gracefully!")


if __name__ == "__main__":
    """Run example demonstrations."""
    print("🔄 Bright Data Integration Examples")
    print("=" * 50)

    # Example 1: Format comparison
    print("\n1. Comparing yt-dlp vs Bright Data formats...")
    compare_yt_dlp_vs_bright_data_output()

    # Example 2: Error handling
    print("\n2. Testing error handling...")
    demonstrate_error_handling()

    # Example 3: Full processing workflow
    print("\n3. Full processing workflow example...")
    sample_response = {
        "id": "example123",
        "title": "Example Video",
        "videoDetails": {"lengthSeconds": "300", "author": "Example Channel"},
        "transcript": [
            {"start": 0, "text": "Hello world"},
            {"start": 5, "text": "This is an example"},
        ],
    }

    results = process_bright_data_youtube_response(
        sample_response, "https://youtube.com/watch?v=example123"
    )

    if results["success"]:
        print("✅ Full workflow completed successfully")
        print(f"   Video: {results['video_metadata'].title}")
        print(
            f"   Transcript length: {len(results['transcript'].transcript_text)} chars"
        )
    else:
        print(f"❌ Workflow failed: {results['errors']}")

    print("\n🎉 All examples completed!")
