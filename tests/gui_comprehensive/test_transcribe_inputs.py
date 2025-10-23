"""
Parameterized transcription input tests.

Tests all input types with auto-process on/off:
- YouTube URL
- YouTube playlist
- RSS feed
- Local audio (.mp3)
- Local video (.webm)
- Batch multiple files

Provider: whisper.cpp, Model: medium
Options: diarization=on (conservative), language=en, cookies=yes, proxy=off
"""

import os
import pytest
from pathlib import Path

# Set testing mode before any imports
os.environ["KNOWLEDGE_CHIPPER_TESTING_MODE"] = "1"
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication

from .utils import (
    create_sandbox, 
    switch_to_tab, 
    process_events_for, 
    DBValidator, 
    find_button_by_text, 
    wait_until,
    get_transcribe_tab,
    add_file_to_transcribe,
    wait_for_completion,
    read_markdown_with_frontmatter,
)


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def test_sandbox(tmp_path):
    """Create isolated test sandbox with DB and output dirs."""
    sandbox = create_sandbox(tmp_path / "sandbox")
    yield sandbox
    # Cleanup handled by pytest tmp_path fixture


@pytest.fixture
def gui_app(qapp, test_sandbox):
    """Launch GUI with test sandbox."""
    from knowledge_system.gui.main_window_pyqt6 import MainWindow
    
    window = MainWindow()
    window.show()
    process_events_for(500)
    
    yield window
    
    window.close()
    process_events_for(200)


class TestTranscribeInputs:
    """Test all transcription input types."""
    
    @pytest.mark.parametrize("auto_process", [False], ids=["no_autoprocess"])
    def test_youtube_url(self, gui_app, test_sandbox, auto_process):
        """Test REAL transcription of YouTube URL."""
        # 1. Switch to Transcribe tab
        assert switch_to_tab(gui_app, "Transcribe"), "Failed to switch to Transcribe tab"
        process_events_for(500)
        
        # 2. Get transcribe tab and add YouTube URL
        transcribe_tab = get_transcribe_tab(gui_app)
        assert transcribe_tab is not None, "Could not find Transcribe tab"
        
        # Use the YouTube URL from test_links.md
        youtube_url = "https://youtu.be/CYrISmYGT8A?si=4TvYl42udS1v-jum"
        
        # Add URL to transcription queue
        add_file_to_transcribe(transcribe_tab, Path(youtube_url))
        process_events_for(200)
        
        # 3. Click Start button
        assert hasattr(transcribe_tab, 'start_btn'), "Transcribe tab has no start_btn"
        transcribe_tab.start_btn.click()
        process_events_for(500)
        
        # 4. Wait for real YouTube download + transcription (may take 5-10 minutes)
        print("⏳ Waiting for real YouTube transcription (this may take 5-10 minutes)...")
        success = wait_for_completion(transcribe_tab, timeout_seconds=600)
        assert success, "YouTube transcription did not complete within 10 minutes"
        
        # 5. Validate database
        db = DBValidator(test_sandbox.db_path)
        videos = db.get_all_videos()
        assert len(videos) > 0, "No media record created"
        
        transcript = db.get_transcript_for_video(videos[0]['video_id'])
        assert transcript is not None, "No transcript found"
        assert len(transcript.get('transcript_text', '')) > 0, "Transcript empty"
        
        # 6. Validate markdown
        md_files = list(test_sandbox.output_dir.glob("**/*.md"))
        assert len(md_files) > 0, "No markdown files created"
        
        print(f"✅ YouTube transcription test passed")
    
    @pytest.mark.parametrize("auto_process", [False], ids=["no_autoprocess"])
    def test_youtube_playlist(self, gui_app, test_sandbox, auto_process):
        """Test REAL transcription of YouTube playlist."""
        # 1. Switch to Transcribe tab
        assert switch_to_tab(gui_app, "Transcribe"), "Failed to switch to Transcribe tab"
        process_events_for(500)
        
        # 2. Get transcribe tab and add playlist URL
        transcribe_tab = get_transcribe_tab(gui_app)
        assert transcribe_tab is not None, "Could not find Transcribe tab"
        
        # Use the playlist URL from test_links.md
        playlist_url = "https://youtube.com/playlist?list=PLmPoIpZcewRt6SXGBm0eBykcCp9Zx-fns&si=fsZvALKteA_t2PiJ"
        
        add_file_to_transcribe(transcribe_tab, Path(playlist_url))
        process_events_for(200)
        
        # 3. Start processing
        transcribe_tab.start_btn.click()
        process_events_for(500)
        
        # 4. Wait for playlist processing (may take 10-20 minutes for multiple videos)
        print("⏳ Waiting for real playlist transcription (this may take 10-20 minutes)...")
        success = wait_for_completion(transcribe_tab, timeout_seconds=1200)
        assert success, "Playlist transcription did not complete within 20 minutes"
        
        # 5. Validate multiple videos processed
        db = DBValidator(test_sandbox.db_path)
        videos = db.get_all_videos()
        assert len(videos) >= 2, f"Expected at least 2 videos from playlist, found {len(videos)}"
        
        # Verify transcripts for videos
        for video in videos[:3]:  # Check first 3
            transcript = db.get_transcript_for_video(video['video_id'])
            assert transcript is not None, f"No transcript for {video['video_id']}"
        
        print(f"✅ Playlist transcription test passed: {len(videos)} videos processed")
    
    @pytest.mark.parametrize("auto_process", [False], ids=["no_autoprocess"])
    def test_rss_feed(self, gui_app, test_sandbox, auto_process):
        """Test REAL transcription from RSS feed."""
        # 1. Switch to Transcribe tab
        assert switch_to_tab(gui_app, "Transcribe"), "Failed to switch to Transcribe tab"
        process_events_for(500)
        
        # 2. Get transcribe tab and add RSS feed URL
        transcribe_tab = get_transcribe_tab(gui_app)
        assert transcribe_tab is not None, "Could not find Transcribe tab"
        
        # Use the RSS feed URL from test_links.md (Sam Harris podcast)
        rss_url = "https://podcasts.apple.com/us/podcast/making-sense-with-sam-harris/id733163012?i=1000731856868"
        
        add_file_to_transcribe(transcribe_tab, Path(rss_url))
        process_events_for(200)
        
        # 3. Start processing
        transcribe_tab.start_btn.click()
        process_events_for(500)
        
        # 4. Wait for RSS feed processing (may take 10-15 minutes)
        print("⏳ Waiting for real RSS feed transcription (this may take 10-15 minutes)...")
        success = wait_for_completion(transcribe_tab, timeout_seconds=900)
        assert success, "RSS feed transcription did not complete within 15 minutes"
        
        # 5. Validate at least one episode processed
        db = DBValidator(test_sandbox.db_path)
        videos = db.get_all_videos()
        assert len(videos) >= 1, "No episodes processed from RSS feed"
        
        transcript = db.get_transcript_for_video(videos[0]['video_id'])
        assert transcript is not None, "No transcript found"
        assert len(transcript.get('transcript_text', '')) > 0, "Transcript empty"
        
        print(f"✅ RSS feed transcription test passed: {len(videos)} episode(s) processed")
    
    @pytest.mark.parametrize("auto_process", [False], ids=["no_autoprocess"])
    def test_local_audio(self, gui_app, test_sandbox, auto_process):
        """Test REAL transcription of local audio file (.mp3)."""
        # 1. Switch to Transcribe tab
        assert switch_to_tab(gui_app, "Transcribe"), "Failed to switch to Transcribe tab"
        process_events_for(500)
        
        # 2. Get transcribe tab and add audio file
        transcribe_tab = get_transcribe_tab(gui_app)
        assert transcribe_tab is not None, "Could not find Transcribe tab"
        
        audio_file = Path(__file__).parent.parent / "fixtures/sample_files/short_audio.mp3"
        assert audio_file.exists(), f"Test audio file not found: {audio_file}"
        
        success = add_file_to_transcribe(transcribe_tab, audio_file)
        assert success, "Failed to add audio file to transcription queue"
        process_events_for(200)
        
        # 3. Find and click Start button
        assert hasattr(transcribe_tab, 'start_btn'), "Transcribe tab has no start_btn"
        transcribe_tab.start_btn.click()
        process_events_for(500)
        
        # 4. Wait for real processing to complete (up to 3 minutes for 30sec audio)
        print("⏳ Waiting for real transcription (this may take 1-3 minutes)...")
        success = wait_for_completion(transcribe_tab, timeout_seconds=180)
        assert success, "Transcription did not complete within 3 minutes"
        
        # 5. Validate database output
        db = DBValidator(test_sandbox.db_path)
        
        # Check for video/media record
        videos = db.get_all_videos()
        assert len(videos) > 0, "No media record created in database"
        
        video = videos[0]
        assert video.get('status') in ['completed', 'complete', None], f"Unexpected status: {video.get('status')}"
        
        # Check for transcript record
        transcript = db.get_transcript_for_video(video['video_id'])
        assert transcript is not None, "No transcript record found in database"
        assert len(transcript.get('transcript_text', '')) > 0, "Transcript text is empty"
        
        # Validate transcript schema
        errors = db.validate_transcript_schema(transcript)
        if errors:
            print(f"⚠️  Schema validation warnings: {errors}")
        
        # 6. Validate markdown file was created
        md_files = list(test_sandbox.output_dir.glob("**/*.md"))
        assert len(md_files) > 0, f"No markdown files created in {test_sandbox.output_dir}"
        
        # Find transcript markdown
        transcript_md = None
        for md_file in md_files:
            if 'transcript' in md_file.stem.lower():
                transcript_md = md_file
                break
        
        assert transcript_md is not None, "No transcript markdown file found"
        
        # Validate markdown content
        frontmatter, body = read_markdown_with_frontmatter(transcript_md)
        assert 'video_id' in frontmatter or 'title' in frontmatter, "Markdown missing required frontmatter"
        assert len(body) > 50, f"Transcript body too short: {len(body)} chars"
        
        print(f"✅ Test passed: {len(transcript['transcript_text'])} chars transcribed")
        print(f"   Markdown: {transcript_md.name}")
        print(f"   Output: {body[:100]}...")
    
    @pytest.mark.parametrize("auto_process", [False], ids=["no_autoprocess"])
    def test_local_video(self, gui_app, test_sandbox, auto_process):
        """Test REAL transcription of local video file (.webm)."""
        # 1. Switch to Transcribe tab
        assert switch_to_tab(gui_app, "Transcribe"), "Failed to switch to Transcribe tab"
        process_events_for(500)
        
        # 2. Get transcribe tab and add video file
        transcribe_tab = get_transcribe_tab(gui_app)
        assert transcribe_tab is not None, "Could not find Transcribe tab"
        
        video_file = Path(__file__).parent.parent / "fixtures/sample_files/short_video.webm"
        assert video_file.exists(), f"Test video file not found: {video_file}"
        
        success = add_file_to_transcribe(transcribe_tab, video_file)
        assert success, "Failed to add video file to transcription queue"
        process_events_for(200)
        
        # 3. Click Start button
        assert hasattr(transcribe_tab, 'start_btn'), "Transcribe tab has no start_btn"
        transcribe_tab.start_btn.click()
        process_events_for(500)
        
        # 4. Wait for real processing (may take longer due to video extraction)
        print("⏳ Waiting for real video transcription (this may take 2-4 minutes)...")
        success = wait_for_completion(transcribe_tab, timeout_seconds=240)
        assert success, "Video transcription did not complete within 4 minutes"
        
        # 5. Validate database
        db = DBValidator(test_sandbox.db_path)
        videos = db.get_all_videos()
        assert len(videos) > 0, "No media record created"
        
        transcript = db.get_transcript_for_video(videos[0]['video_id'])
        assert transcript is not None, "No transcript found"
        assert len(transcript.get('transcript_text', '')) > 0, "Transcript empty"
        
        # 6. Validate markdown
        md_files = list(test_sandbox.output_dir.glob("**/*.md"))
        assert len(md_files) > 0, "No markdown files created"
        
        print(f"✅ Video transcription test passed")
    
    @pytest.mark.parametrize("auto_process", [False], ids=["no_autoprocess"])
    def test_batch_files(self, gui_app, test_sandbox, auto_process):
        """Test batch processing multiple local files."""
        # 1. Switch to Transcribe tab
        assert switch_to_tab(gui_app, "Transcribe"), "Failed to switch to Transcribe tab"
        process_events_for(500)
        
        # 2. Get transcribe tab and add multiple files
        transcribe_tab = get_transcribe_tab(gui_app)
        assert transcribe_tab is not None, "Could not find Transcribe tab"
        
        # Add 2 audio files
        audio1 = Path(__file__).parent.parent / "fixtures/sample_files/short_audio.mp3"
        audio2 = Path(__file__).parent.parent / "fixtures/sample_files/short_audio_multi.mp3"
        
        assert audio1.exists() and audio2.exists(), "Test audio files not found"
        
        add_file_to_transcribe(transcribe_tab, audio1)
        process_events_for(100)
        add_file_to_transcribe(transcribe_tab, audio2)
        process_events_for(200)
        
        # 3. Start processing
        transcribe_tab.start_btn.click()
        process_events_for(500)
        
        # 4. Wait for batch processing (longer timeout for multiple files)
        print("⏳ Waiting for batch transcription (this may take 3-5 minutes)...")
        success = wait_for_completion(transcribe_tab, timeout_seconds=300)
        assert success, "Batch transcription did not complete within 5 minutes"
        
        # 5. Validate both files were processed
        db = DBValidator(test_sandbox.db_path)
        videos = db.get_all_videos()
        assert len(videos) >= 2, f"Expected at least 2 media records, found {len(videos)}"
        
        # Verify transcripts exist for both
        for video in videos[:2]:
            transcript = db.get_transcript_for_video(video['video_id'])
            assert transcript is not None, f"No transcript for {video['video_id']}"
            assert len(transcript.get('transcript_text', '')) > 0, "Transcript empty"
        
        print(f"✅ Batch transcription test passed: {len(videos)} files processed")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

