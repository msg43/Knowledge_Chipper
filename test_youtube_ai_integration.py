#!/usr/bin/env python3
"""
Test YouTube AI Summary Integration with Existing Pipeline
Tests the full workflow: download → scrape AI summary → save to DB → generate markdown
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from knowledge_system.processors.youtube_download_with_ai_summary import YouTubeDownloadWithAISummary
from knowledge_system.processors.audio_processor import AudioProcessor
from knowledge_system.database.service import DatabaseService
from knowledge_system.logger import get_logger

logger = get_logger(__name__)


def test_full_pipeline(url: str):
    """Test the full YouTube → AI Summary → DB → Markdown pipeline."""
    
    print(f"\n{'='*70}")
    print(f"Testing YouTube AI Summary Integration")
    print(f"{'='*70}\n")
    print(f"URL: {url}\n")
    
    db_service = DatabaseService()
    
    # Step 1: Download with AI summary scraping
    print("Step 1: Download video + scrape AI summary")
    print("-" * 70)
    
    downloader = YouTubeDownloadWithAISummary(
        enable_ai_summary=True,
        download_thumbnails=True
    )
    
    def progress(msg):
        print(f"  {msg}")
    
    download_result = downloader.process(
        input_data=url,
        progress_callback=progress,
        db_service=db_service
    )
    
    if not download_result.success:
        print(f"\n❌ Download failed: {download_result.errors}")
        return False
    
    source_id = download_result.data.get('source_id')
    audio_file = download_result.data.get('downloaded_files', [None])[0]
    
    print(f"\n✅ Download complete")
    print(f"   Source ID: {source_id}")
    print(f"   Audio file: {audio_file}")
    
    # Check if AI summary was saved
    video = db_service.get_source(source_id)
    if video and video.youtube_ai_summary:
        print(f"   ✅ YouTube AI Summary: {len(video.youtube_ai_summary)} chars")
    else:
        print(f"   ⚠️  No YouTube AI Summary")
    
    # Step 2: Transcribe (if audio was downloaded)
    if audio_file:
        print(f"\nStep 2: Transcribe audio")
        print("-" * 70)
        
        transcriber = AudioProcessor()
        
        # Build source_metadata including AI summary
        source_metadata = {
            'source_id': source_id,
            'title': video.title,
            'url': video.url,
            'uploader': video.uploader,
            'description': video.description,
            'youtube_ai_summary': video.youtube_ai_summary,
            'source_type': 'YouTube',
            'tags': [],  # Would need to query tags relationship
        }
        
        transcribe_result = transcriber.process(
            input_data=audio_file,
            progress_callback=progress,
            source_metadata=source_metadata,
            db_service=db_service
        )
        
        if transcribe_result.success:
            print(f"\n✅ Transcription complete")
            
            # Check for generated markdown
            if transcribe_result.output_files:
                markdown_file = transcribe_result.output_files[0]
                print(f"   📄 Markdown: {markdown_file}")
                
                # Verify markdown contains AI summary
                if Path(markdown_file).exists():
                    content = Path(markdown_file).read_text()
                    if '## YouTube AI Summary' in content:
                        print(f"   ✅ Markdown includes YouTube AI Summary section")
                    else:
                        print(f"   ⚠️  Markdown missing YouTube AI Summary section")
                    
                    if '&t=' in content:
                        timestamp_count = content.count('&t=')
                        print(f"   ✅ Markdown has {timestamp_count} hyperlinked timestamps")
                    else:
                        print(f"   ⚠️  Markdown missing hyperlinked timestamps")
                        
                return True
        else:
            print(f"\n❌ Transcription failed: {transcribe_result.errors}")
            return False
    
    return True


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_youtube_ai_integration.py <youtube_url>")
        print("\nExample:")
        print("  python test_youtube_ai_integration.py 'https://www.youtube.com/watch?v=AmIiqY2VJkQ'")
        sys.exit(1)
    
    url = sys.argv[1]
    success = test_full_pipeline(url)
    
    if success:
        print(f"\n{'='*70}")
        print(f"✅ Integration test PASSED")
        print(f"{'='*70}\n")
    else:
        print(f"\n{'='*70}")
        print(f"❌ Integration test FAILED")
        print(f"{'='*70}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()

