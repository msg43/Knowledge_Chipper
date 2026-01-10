"""
YouTube Transcript Service for Daemon

Uses the proven approach from scrape_youtube_complete.py:
- YouTube Transcript API for transcripts (fast, reliable)
- yt-dlp only for metadata (no download needed)
- Returns data in format compatible with daemon processing pipeline
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional
from youtube_transcript_api import YouTubeTranscriptApi
import yt_dlp

logger = logging.getLogger(__name__)


class YouTubeTranscriptService:
    """
    Lightweight YouTube transcript service.
    Gets transcript and metadata without downloading video.
    """
    
    def __init__(self):
        self.transcript_api = YouTubeTranscriptApi()
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL."""
        if 'v=' in url:
            return url.split('v=')[1].split('&')[0]
        elif 'youtu.be/' in url:
            return url.split('youtu.be/')[1].split('?')[0]
        return None
    
    def get_metadata(self, url: str) -> Dict[str, Any]:
        """
        Get video metadata using yt-dlp (metadata only, no download).
        This is fast and doesn't trigger YouTube's anti-bot measures.
        """
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'skip_download': True,  # Don't download, just get info
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                video_id = info.get('id', self.extract_video_id(url))
                
                # Format upload date
                upload_date = info.get('upload_date', '')
                if upload_date and len(upload_date) == 8:
                    from datetime import datetime
                    try:
                        dt = datetime.strptime(upload_date, '%Y%m%d')
                        upload_date = dt.strftime('%Y-%m-%dT00:00:00')
                    except:
                        pass
                
                return {
                    'success': True,
                    'video_id': video_id,
                    'title': info.get('title', 'Unknown'),
                    'uploader': info.get('uploader', 'Unknown'),
                    'uploader_id': info.get('uploader_id', ''),
                    'upload_date': upload_date,
                    'duration_seconds': info.get('duration', 0),
                    'view_count': info.get('view_count', 0),
                    'description': info.get('description', ''),
                    'thumbnail_url': info.get('thumbnail', ''),
                    'url': url,
                }
        except Exception as e:
            logger.error(f"Error getting metadata: {e}")
            video_id = self.extract_video_id(url)
            return {
                'success': False,
                'video_id': video_id,
                'url': url,
                'title': 'Unknown',
                'error': str(e)
            }
    
    def get_transcript(self, video_id: str) -> Dict[str, Any]:
        """
        Get transcript using YouTube Transcript API.
        This is the most reliable method and doesn't require downloading.
        """
        try:
            # Fetch transcript
            transcript_data = self.transcript_api.fetch(video_id)
            
            # Format transcript with timestamps
            formatted_lines = []
            for entry in transcript_data:
                # Entry is a FetchedTranscriptSnippet object with attributes, not a dict
                timestamp = entry.start if hasattr(entry, 'start') else 0
                text = entry.text if hasattr(entry, 'text') else ''
                
                # Format timestamp as [MM:SS]
                minutes = int(timestamp // 60)
                seconds = int(timestamp % 60)
                time_str = f"[{minutes:02d}:{seconds:02d}]"
                
                formatted_lines.append(f"{time_str} {text}")
            
            transcript_text = '\n'.join(formatted_lines)
            
            return {
                'success': True,
                'transcript': transcript_text,
                'entry_count': len(transcript_data),
            }
            
        except Exception as e:
            logger.error(f"Error getting transcript for {video_id}: {e}")
            return {
                'success': False,
                'transcript': None,
                'error': str(e)
            }
    
    def get_complete_data(self, url: str) -> Dict[str, Any]:
        """
        Get both metadata and transcript.
        This is the main method the daemon should use.
        
        Returns:
            {
                'success': bool,
                'video_id': str,
                'title': str,
                'transcript': str,
                'metadata': dict,
                'error': str (if failed)
            }
        """
        # Step 1: Get metadata
        logger.info(f"Getting metadata for: {url}")
        metadata_result = self.get_metadata(url)
        
        if not metadata_result.get('success'):
            return {
                'success': False,
                'error': f"Failed to get metadata: {metadata_result.get('error')}"
            }
        
        video_id = metadata_result['video_id']
        
        # Step 2: Get transcript
        logger.info(f"Getting transcript for video ID: {video_id}")
        transcript_result = self.get_transcript(video_id)
        
        if not transcript_result.get('success'):
            return {
                'success': False,
                'video_id': video_id,
                'metadata': metadata_result,
                'error': f"Failed to get transcript: {transcript_result.get('error')}"
            }
        
        # Success!
        return {
            'success': True,
            'video_id': video_id,
            'title': metadata_result['title'],
            'transcript': transcript_result['transcript'],
            'metadata': metadata_result,
            'transcript_entry_count': transcript_result['entry_count'],
        }
