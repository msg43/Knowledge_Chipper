#!/usr/bin/env python3
"""
Test script to verify the Summarize tab database refresh fix.

This script:
1. Checks if there are transcripts in the database
2. Verifies the query used by the Summarize tab works correctly
3. Checks for orphaned transcripts (transcripts without MediaSource records)
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from knowledge_system.database import DatabaseService
from knowledge_system.database.models import MediaSource, Transcript


def test_database_query():
    """Test the database query used by the Summarize tab."""
    print("=" * 80)
    print("Testing Summarize Tab Database Query")
    print("=" * 80)

    db = DatabaseService()

    with db.get_session() as session:
        # Count total transcripts
        total_transcripts = session.query(Transcript).count()
        print(f"\n✓ Total transcripts in database: {total_transcripts}")

        if total_transcripts == 0:
            print("\n⚠️  No transcripts found in database.")
            print("   Please transcribe a YouTube URL first to test this fix.")
            return

        # Query for media sources with transcripts (same query as Summarize tab)
        query = (
            session.query(MediaSource)
            .join(
                Transcript,
                MediaSource.source_id == Transcript.source_id,
                isouter=True,
            )
            .filter(Transcript.transcript_id.isnot(None))
        )

        videos = query.all()
        print(f"✓ Found {len(videos)} MediaSource records with transcripts")

        # Check for orphaned transcripts
        if total_transcripts > len(videos):
            orphaned_transcripts = (
                session.query(Transcript)
                .outerjoin(MediaSource, Transcript.source_id == MediaSource.source_id)
                .filter(MediaSource.source_id.is_(None))
                .all()
            )

            if orphaned_transcripts:
                print(f"\n⚠️  Found {len(orphaned_transcripts)} orphaned transcripts!")
                print("   (Transcripts without corresponding MediaSource records)")
                print(
                    f"   Source IDs: {[t.source_id for t in orphaned_transcripts[:5]]}"
                )

                # Show details of first orphaned transcript
                if orphaned_transcripts:
                    first = orphaned_transcripts[0]
                    print(f"\n   Example orphaned transcript:")
                    print(f"   - Transcript ID: {first.transcript_id}")
                    print(f"   - Source ID: {first.source_id}")
                    print(f"   - Language: {first.language}")
                    print(f"   - Created: {first.created_at}")
                    print(
                        f"   - Text length: {len(first.transcript_text) if first.transcript_text else 0} chars"
                    )
            else:
                print(
                    f"\n✓ All {total_transcripts} transcripts have corresponding MediaSource records"
                )
        else:
            print(
                f"\n✓ All {total_transcripts} transcripts have corresponding MediaSource records"
            )

        # Show sample of videos with transcripts
        if videos:
            print(f"\n✓ Sample of transcribed videos:")
            for i, video in enumerate(videos[:5], 1):
                print(f"\n   {i}. {video.title or video.source_id}")
                print(f"      Source ID: {video.source_id}")
                print(
                    f"      Duration: {video.duration_seconds}s"
                    if video.duration_seconds
                    else "      Duration: unknown"
                )
                print(f"      Created: {video.created_at}")

                # Get transcript info
                transcript = (
                    session.query(Transcript)
                    .filter(Transcript.source_id == video.source_id)
                    .first()
                )
                if transcript:
                    text_length = (
                        len(transcript.transcript_text)
                        if transcript.transcript_text
                        else 0
                    )
                    print(
                        f"      Transcript: {text_length:,} chars, {transcript.segment_count} segments"
                    )

            if len(videos) > 5:
                print(f"\n   ... and {len(videos) - 5} more")

    print("\n" + "=" * 80)
    print("Test Complete!")
    print("=" * 80)
    print("\nThe Summarize tab should now automatically refresh when you:")
    print("1. Switch to the Summarize tab after transcribing a video")
    print("2. Switch to the 'Summarize from Database' view")
    print("\nIf you still don't see new transcripts, check the logs for:")
    print("- 'Total transcripts in database: N'")
    print("- 'Found N MediaSource records with transcripts'")
    print("- Any warnings about orphaned transcripts")
    print()


if __name__ == "__main__":
    try:
        test_database_query()
    except Exception as e:
        print(f"\n❌ Error running test: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
