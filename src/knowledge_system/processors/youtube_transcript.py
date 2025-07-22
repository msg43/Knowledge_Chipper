"""
YouTube Transcript Processor

Extracts transcripts from YouTube videos using Webshare rotating residential proxies.
Simplified version that only uses the proxy-based YouTube Transcript API.
"""

import json
import re
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from datetime import datetime

try:
    from youtube_transcript_api._api import YouTubeTranscriptApi
except ImportError:
    YouTubeTranscriptApi = None

from pydantic import BaseModel, Field

from ..errors import YouTubeAPIError
from ..logger import get_logger
from ..utils.youtube_utils import is_youtube_url, extract_urls
from ..utils.cancellation import CancellationToken, CancellationError
from .base import BaseProcessor, ProcessorResult
from ..utils.text_utils import strip_bracketed_content

logger = get_logger(__name__)


class YouTubeTranscript(BaseModel):
    """YouTube transcript model."""

    video_id: str = Field(..., description="YouTube video ID")
    title: str = Field(..., description="Video title")
    url: str = Field(..., description="Full YouTube URL")
    language: str = Field(..., description="Transcript language code")
    is_manual: bool = Field(
        ..., description="Whether this is a manual transcript (not auto-generated)"
    )
    transcript_text: str = Field(..., description="Full transcript text")
    transcript_data: List[Dict[str, Any]] = Field(
        default_factory=list, description="Raw transcript data with timestamps"
    )
    duration: Optional[int] = Field(
        default=None, description="Video duration in seconds"
    )
    uploader: str = Field(default="", description="Channel name")
    upload_date: Optional[str] = Field(
        default=None, description="Upload date (YYYYMMDD)"
    )
    description: str = Field(default="", description="Video description")
    view_count: Optional[int] = Field(
        default=None, description="Video view count"
    )
    tags: List[str] = Field(
        default_factory=list, description="Video tags"
    )
    thumbnail_url: Optional[str] = Field(
        default=None, description="Thumbnail URL from YouTube API"
    )
    fetched_at: datetime = Field(
        default_factory=datetime.now, description="When transcript was fetched"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = self.model_dump()
        # Convert datetime to ISO string for JSON serialization
        if "fetched_at" in data and isinstance(data["fetched_at"], datetime):
            data["fetched_at"] = data["fetched_at"].isoformat()
        return data

    def to_markdown(self, include_timestamps: bool = True,
                    include_analysis: bool = True, vault_path: Optional[Path] = None, 
                    output_dir: Optional[Path] = None, strip_interjections: bool = False,
                    interjections_file: Optional[Path] = None) -> str:
        """Convert transcript to markdown format with enhanced Obsidian sections."""
        lines = []

        # Add YAML frontmatter with title and metadata
        # Escape quotes in title for YAML safety
        safe_title = self.title.replace('"', '\\"')
        lines.append("---")
        lines.append(f'title: "{safe_title}"')
        lines.append(f'source: "{self.url}"')
        lines.append(f'video_id: "{self.video_id}"')
        lines.append(f'language: "{self.language}"')
        lines.append(f'type: "{"Manual" if self.is_manual else "Auto-generated"}"')
        
        # Only include metadata if available (keeping it simple)
        if self.uploader:
            lines.append(f'uploader: "{self.uploader}"')
        
        if self.upload_date:
            try:
                date_obj = datetime.strptime(self.upload_date, "%Y%m%d")
                lines.append(f'upload_date: "{date_obj.strftime("%B %d, %Y")}"')
            except ValueError:
                lines.append(f'upload_date: "{self.upload_date}"')
        
        if self.duration:
            minutes = self.duration // 60
            seconds = self.duration % 60
            lines.append(f'duration: "{minutes}:{seconds:02d}"')
        
        # Add view count if available
        if self.view_count:
            lines.append(f'view_count: {self.view_count}')
        
        # Add tags if available (limit to first 10 to keep YAML manageable)
        if self.tags:
            tags_subset = self.tags[:10]
            # Format tags as a YAML array, escaping quotes in tag names
            safe_tags = [tag.replace('"', '\\"') for tag in tags_subset]
            tags_yaml = '[' + ', '.join(f'"{tag}"' for tag in safe_tags) + ']'
            lines.append(f'tags: {tags_yaml}')
            if len(self.tags) > 10:
                lines.append(f'# ... and {len(self.tags) - 10} more tags')
        
        # Add transcript processing metadata
        lines.append(f'model: "YouTube Transcript"')
        lines.append(f'device: "Web API"')
        
        # Add extraction timestamp
        lines.append(f'fetched: "{self.fetched_at.strftime("%Y-%m-%d %H:%M:%S")}"')
        
        lines.append("---")
        lines.append("")

        # Create sanitized title for thumbnail reference
        safe_title_for_filename = re.sub(r"[^\w\s-]", "", self.title).strip()
        safe_title_for_filename = re.sub(r"[-\s]+", "-", safe_title_for_filename)
        
        # Add thumbnail reference for YouTube videos using sanitized title
        if safe_title_for_filename:
            lines.append(f"![Video Thumbnail](Thumbnails/{safe_title_for_filename}-Thumbnail.jpg)")
        else:
            lines.append(f"![Video Thumbnail](Thumbnails/{self.video_id}-Thumbnail.jpg)")
        lines.append("")

        # Add Full Transcript section
        lines.append("## Full Transcript")
        lines.append("")

        # Format transcript with timestamps if available
        if self.transcript_data and include_timestamps:
            for segment in self.transcript_data:
                start_time = segment.get("start", 0)
                text = segment.get("text", "").strip()
                if text:
                    # Remove bracketed content like [music], [applause], etc.
                    text = strip_bracketed_content(text)
                    # Only add the segment if there's still text after bracket removal
                    if text.strip():
                        minutes = int(start_time // 60)
                        seconds = int(start_time % 60)
                        timestamp = f"{minutes:02d}:{seconds:02d}"
                        lines.append(f"**{timestamp}** {text}")
                        lines.append("")
        else:
            # Plain text transcript - also remove bracketed content
            transcript_text = strip_bracketed_content(self.transcript_text)
            lines.append(transcript_text)

        return "\n".join(lines)

    def to_srt(self, strip_interjections: bool = False, interjections_file: Optional[Path] = None) -> str:
        """Convert transcript to SRT format."""
        if not self.transcript_data:
            return ""

        srt_lines = []
        for i, segment in enumerate(self.transcript_data, 1):
            start_time = segment.get("start", 0)
            duration = segment.get("duration", 2.0)  # Default 2 second duration
            end_time = start_time + duration
            text = segment.get("text", "").strip()

            if text:
                # Remove bracketed content like [music], [applause], etc.
                text = strip_bracketed_content(text)
                # Only add the segment if there's still text after bracket removal
                if text.strip():
                    # Format timestamps for SRT
                    start_srt = self._format_srt_timestamp(start_time)
                    end_srt = self._format_srt_timestamp(end_time)
                    
                    srt_lines.append(str(i))
                    srt_lines.append(f"{start_srt} --> {end_srt}")
                    srt_lines.append(text)
                    srt_lines.append("")

        return "\n".join(srt_lines)

    def _format_srt_timestamp(self, seconds: float) -> str:
        """Format seconds to SRT timestamp format (HH:MM:SS,mmm)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"


class YouTubeTranscriptProcessor(BaseProcessor):
    """
    Processor for extracting YouTube transcripts using Webshare rotating proxies.
    
    Simplified processor that only uses the proxy-based YouTube Transcript API.
    No fallback methods - requires working Webshare credentials.
    """

    def __init__(
        self,
        preferred_language: str = "en",
        prefer_manual: bool = True,
        fallback_to_auto: bool = True,
        **kwargs
    ):
        """Initialize the YouTube transcript processor."""
        super().__init__("youtube_transcript")
        self.preferred_language = preferred_language
        self.prefer_manual = prefer_manual
        self.fallback_to_auto = fallback_to_auto

        if YouTubeTranscriptApi is None:
            raise ImportError(
                "youtube-transcript-api is required for transcript extraction. "
                "Install it with: pip install youtube-transcript-api"
            )

    @property
    def supported_formats(self) -> List[str]:
        """Return list of supported input formats."""
        return ["youtube_url"]

    def validate_input(self, input_data: Any) -> bool:
        """Validate that input contains YouTube URLs."""
        if isinstance(input_data, str):
            return is_youtube_url(input_data)
        elif isinstance(input_data, list):
            return any(is_youtube_url(str(item)) for item in input_data)
        return False

    def _extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL."""
        if 'youtu.be/' in url:
            return url.split('youtu.be/')[1].split('?')[0]
        elif 'watch?v=' in url:
            return url.split('watch?v=')[1].split('&')[0]
        else:
            logger.error(f"Could not extract video ID from URL: {url}")
            return None
            


    def _validate_webshare_config(self) -> List[str]:
        """Validate WebShare proxy configuration."""
        from ..config import get_settings
        
        settings = get_settings()
        issues = []
        
        if not settings.api_keys.webshare_username:
            issues.append("WebShare Username not configured")
        if not settings.api_keys.webshare_password:
            issues.append("WebShare Password not configured")
            
        return issues

    def _fetch_video_transcript(self, url: str, cancellation_token: Optional[CancellationToken] = None) -> Optional[YouTubeTranscript]:
        """Fetch transcript for a single video using proxy-based YouTube Transcript API."""
        
        logger.info(f"Fetching transcript for: {url}")
        
        if YouTubeTranscriptApi is None:
            logger.error("youtube-transcript-api is not available")
            return None
        
        try:
            # Check for cancellation at the start
            if cancellation_token and cancellation_token.is_cancelled():
                raise CancellationError("Transcript fetch cancelled")
                
            from ..config import get_settings
            
            # Get Webshare credentials from settings
            settings = get_settings()
            username = settings.api_keys.webshare_username
            password = settings.api_keys.webshare_password
            
            if not username or not password:
                logger.error("Webshare credentials not found. Please configure WebShare Username and Password in Settings.")
                return None
            
            # Extract video ID from URL
            video_id = self._extract_video_id(url)
            if not video_id:
                return None
            
            # Configure YouTube Transcript API with WebShare proxy
            logger.info("Using Webshare rotating proxy for transcript extraction")
            
            # Set up proxy configuration for youtube-transcript-api
            proxies = {
                'http': f"http://{username}:{password}@p.webshare.io:80/",
                'https': f"http://{username}:{password}@p.webshare.io:80/"
            }
            
            # Fetch real metadata using the YouTube metadata processor
            real_metadata = None
            try:
                from .youtube_metadata import YouTubeMetadataProcessor
                metadata_processor = YouTubeMetadataProcessor()
                metadata_result = metadata_processor.process(url)
                if metadata_result.success and metadata_result.data and metadata_result.data.get('metadata'):
                    real_metadata = metadata_result.data['metadata'][0]
                    logger.info(f"Successfully fetched metadata: {real_metadata.get('title', 'Unknown')}")
            except Exception as e:
                logger.warning(f"Could not fetch metadata for {video_id}: {e}")
            
            # Try transcript extraction with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Check for cancellation before each attempt
                    if cancellation_token and cancellation_token.is_cancelled():
                        raise CancellationError("Transcript fetch cancelled during retry")
                        
                    # Add configurable delay to avoid rate limiting
                    delay_config = settings.youtube_processing
                    
                    # Check if we should skip delays when using proxies
                    has_proxy = (settings.api_keys.webshare_username and 
                                settings.api_keys.webshare_password)
                    
                    if delay_config.disable_delays_with_proxy and has_proxy:
                        logger.debug("Skipping transcript delay - using rotating proxies")
                    else:
                        delay = random.uniform(
                            delay_config.transcript_delay_min, 
                            delay_config.transcript_delay_max
                        )
                        logger.info(f"Applying transcript delay: {delay:.1f}s")
                        
                        # Check cancellation during delay
                        if cancellation_token:
                            elapsed = 0
                            check_interval = 0.1
                            while elapsed < delay:
                                if cancellation_token.is_cancelled():
                                    raise CancellationError("Transcript fetch cancelled during delay")
                                time.sleep(min(check_interval, delay - elapsed))
                                elapsed += check_interval
                        else:
                            time.sleep(delay)
                    
                    # Get list of available transcripts with proxy
                    transcript_list = YouTubeTranscriptApi.list_transcripts(video_id, proxies=proxies)
                    
                    # Check for cancellation after transcript list fetch
                    if cancellation_token and cancellation_token.is_cancelled():
                        raise CancellationError("Transcript fetch cancelled after getting transcript list")
                    
                    # Try to find preferred transcript
                    transcript = None
                    is_manual = False
                    
                    # First try manual transcripts
                    if self.prefer_manual:
                        try:
                            # Try preferred language first
                            transcript = transcript_list.find_manually_created_transcript([self.preferred_language])
                            is_manual = True
                            logger.info(f"Found manual transcript in {self.preferred_language}")
                        except:
                            try:
                                # Try English as fallback
                                transcript = transcript_list.find_manually_created_transcript(['en'])
                                is_manual = True
                                logger.info("Found manual transcript in English")
                            except:
                                # Try any manual transcript
                                try:
                                    for t in transcript_list:
                                        # Use getattr to safely check for attribute
                                        if getattr(t, 'is_manually_created', False):
                                            transcript = t
                                            is_manual = True
                                            logger.info(f"Found manual transcript in {getattr(t, 'language_code', 'unknown')}")
                                            break
                                except:
                                    pass
                    
                    # Then try automatic captions if no manual found and allowed
                    if not transcript and self.fallback_to_auto:
                        try:
                            # Try preferred language first
                            transcript = transcript_list.find_generated_transcript([self.preferred_language])
                            is_manual = False
                            logger.info(f"Found automatic transcript in {self.preferred_language}")
                        except:
                            try:
                                # Try English as fallback
                                transcript = transcript_list.find_generated_transcript(['en'])
                                is_manual = False
                                logger.info("Found automatic transcript in English")
                            except:
                                # Try any automatic transcript
                                try:
                                    for t in transcript_list:
                                        # Use getattr to safely check for attribute
                                        if not getattr(t, 'is_manually_created', True):
                                            transcript = t
                                            is_manual = False
                                            logger.info(f"Found automatic transcript in {getattr(t, 'language_code', 'unknown')}")
                                            break
                                except:
                                    pass
                    
                    if not transcript:
                        logger.warning(f"No suitable transcript found for video {video_id}")
                        return None
                    
                    # Check for cancellation before fetching transcript content
                    if cancellation_token and cancellation_token.is_cancelled():
                        raise CancellationError("Transcript fetch cancelled before content download")
                    
                    # Fetch the transcript content
                    transcript_data = transcript.fetch()
                    
                    if not transcript_data:
                        logger.warning(f"Empty transcript data for video {video_id}")
                        return None
                    
                    # Convert to our format - handle different transcript data formats safely
                    transcript_text_parts = []
                    formatted_transcript_data = []
                    
                    for i, entry in enumerate(transcript_data):
                        # Handle both dict and object formats
                        if isinstance(entry, dict):
                            # Dict format
                            text = entry.get('text', '')
                            start = entry.get('start', 0)
                            duration = entry.get('duration', 0)
                        elif hasattr(entry, 'text'):
                            # Object format
                            text = getattr(entry, 'text', '')
                            start = getattr(entry, 'start', 0)
                            duration = getattr(entry, 'duration', 0)
                        else:
                            # String format or unknown - skip
                            continue
                            
                        if text:
                            transcript_text_parts.append(text)
                            formatted_transcript_data.append({
                                'start': start,
                                'end': start + duration,
                                'text': text,
                                'duration': duration
                            })
                    
                    transcript_text = " ".join(transcript_text_parts)
                    
                    # Use real metadata if available, otherwise create fallback
                    if real_metadata:
                        title = real_metadata.get('title', f'YouTube Video {video_id}')
                        uploader = real_metadata.get('uploader', '')
                        duration = real_metadata.get('duration')
                        upload_date = real_metadata.get('upload_date')
                        description = real_metadata.get('description', '')
                        view_count = real_metadata.get('view_count')
                        tags = real_metadata.get('tags', [])
                        thumbnail_url = real_metadata.get('thumbnail_url')
                    else:
                        title = f'YouTube Video {video_id}'
                        uploader = ''
                        duration = None
                        upload_date = None
                        description = ''
                        view_count = None
                        tags = []
                        thumbnail_url = None
                    
                    # Create transcript object
                    result = YouTubeTranscript(
                        video_id=video_id,
                        title=title,
                        url=url,
                        language=getattr(transcript, 'language_code', 'unknown'),
                        is_manual=is_manual,
                        transcript_text=transcript_text,
                        transcript_data=formatted_transcript_data,
                        duration=duration,
                        uploader=uploader,
                        upload_date=upload_date,
                        description=description,
                        view_count=view_count,
                        tags=tags,
                        thumbnail_url=thumbnail_url,
                        fetched_at=datetime.now()
                    )
                    
                    logger.info(f"Successfully extracted transcript for {video_id}")
                    return result
                        
                except CancellationError:
                    # Re-raise cancellation errors
                    raise
                except Exception as e:
                    error_msg = str(e)
                    logger.info(f"Attempt {attempt + 1} failed: {error_msg}")
                    
                    # Check for specific proxy authentication errors
                    if "407 Proxy Authentication Required" in error_msg or "ProxyError" in error_msg:
                        logger.error(f"Proxy authentication failed for video {video_id}. Please check your WebShare credentials.")
                        break
                    elif "402 Payment Required" in error_msg:
                        logger.error(f"💰 WebShare account requires payment for video {video_id}. Please add funds to your WebShare account at https://panel.webshare.io/")
                        break
                    elif "Tunnel connection failed" in error_msg:
                        logger.error(f"Proxy connection failed for video {video_id}. WebShare proxy may be unavailable.")
                        break
                    
                    if attempt < max_retries - 1:
                        wait_time = random.uniform(2, 5)
                        logger.info(f"Waiting {wait_time:.1f}s before retry...")
                        
                        # Check cancellation during wait
                        if cancellation_token:
                            elapsed = 0
                            check_interval = 0.1
                            while elapsed < wait_time:
                                if cancellation_token.is_cancelled():
                                    raise CancellationError("Transcript fetch cancelled during retry wait")
                                time.sleep(min(check_interval, wait_time - elapsed))
                                elapsed += check_interval
                        else:
                            time.sleep(wait_time)
                    else:
                        logger.error(f"All attempts failed for video {video_id}")
                        
        except CancellationError:
            logger.info(f"Transcript fetch cancelled for {url}")
            raise
        except Exception as proxy_error:
            logger.error(f"Webshare proxy transcript extraction failed: {proxy_error}")
            
        return None

    def process(
        self,
        input_data: Any,
        output_dir: Optional[Union[str, Path]] = None,
        output_format: Optional[str] = None,
        vault_path: Optional[Union[str, Path]] = None,
        include_timestamps: bool = True,
        include_analysis: bool = True,
        strip_interjections: bool = False,
        interjections_file: Optional[Union[str, Path]] = None,
        cancellation_token: Optional[CancellationToken] = None,
        **kwargs,
    ) -> ProcessorResult:
        """Process YouTube URLs to extract transcripts."""
        try:
            # Check for cancellation at the start
            if cancellation_token and cancellation_token.is_cancelled():
                return ProcessorResult(
                    success=False, 
                    errors=["Processing cancelled before start"],
                    metadata={"processor": self.name, "cancelled": True}
                )
                
            output_format = output_format or "md"
            urls = extract_urls(input_data)

            if not urls:
                return ProcessorResult(
                    success=False, errors=["No valid YouTube URLs found in input"]
                )
            
            # Expand any playlist URLs into individual video URLs
            from ..utils.youtube_utils import expand_playlist_urls
            urls = expand_playlist_urls(urls)
            if not urls:
                return ProcessorResult(
                    success=False, errors=["No valid video URLs found after playlist expansion"]
                )
            
            # Validate WebShare configuration before processing
            config_issues = self._validate_webshare_config()
            if config_issues:
                logger.warning("WebShare configuration issues detected")
                for issue in config_issues:
                    logger.warning(issue)
                return ProcessorResult(
                    success=False, 
                    errors=[f"WebShare configuration issue: {'; '.join(config_issues)}"]
                )

            output_dir = Path(output_dir).expanduser() if output_dir else Path.cwd()
            output_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"YouTube transcript extraction starting. Output directory: {output_dir}")
            logger.info(f"Output directory exists: {output_dir.exists()}")
            logger.info(f"Output directory is writable: {output_dir.is_dir() and output_dir.stat().st_mode}")

            transcripts = []
            errors = []

            for url in urls:
                try:
                    # Check for cancellation before each URL
                    if cancellation_token and cancellation_token.is_cancelled():
                        logger.info("Processing cancelled by user")
                        break
                        
                    transcript = self._fetch_video_transcript(url, cancellation_token)
                    if transcript:
                        transcripts.append(transcript)
                    else:
                        logger.warning(f"No transcript returned for {url}")
                        errors.append(f"No transcript available for {url}")
                except CancellationError:
                    logger.info("Transcript extraction cancelled by user")
                    break
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Error processing {url}: {error_msg}")
                    
                    # Categorize the error for better user feedback
                    if "407 Proxy Authentication Required" in error_msg or "Proxy authentication failed" in error_msg:
                        errors.append(f"🔐 Proxy authentication failed for {url}: Please check your WebShare Username and Password in Settings")
                    elif "402 Payment Required" in error_msg:
                        errors.append(f"💰 WebShare account payment required for {url}: Your WebShare proxy account is out of funds. Please add payment at https://panel.webshare.io/ to continue using YouTube extraction")
                    elif "Proxy connection failed" in error_msg or "Tunnel connection failed" in error_msg:
                        errors.append(f"🌐 Proxy connection failed for {url}: WebShare proxy may be unavailable or blocked")
                    elif "Sign in to confirm you're not a bot" in error_msg:
                        errors.append(f"🔐 Authentication required for {url}: YouTube is requiring sign-in verification")
                    elif "live stream recording is not available" in error_msg:
                        errors.append(f"❌ Video unavailable: {url} appears to be a live stream recording that is no longer available")
                    elif "Video unavailable" in error_msg or "This video is not available" in error_msg:
                        errors.append(f"❌ Video unavailable: {url} - video may be private, deleted, or region-restricted")
                    else:
                        errors.append(f"❌ Error processing {url}: {error_msg}")

            # Save transcripts to files
            logger.info(f"Saving {len(transcripts)} transcripts to files")
            if not transcripts:
                logger.warning("No transcripts available for file writing!")
            
            # Create Thumbnails subdirectory
            thumbnails_dir = output_dir / "Thumbnails"
            thumbnails_dir.mkdir(exist_ok=True)
            logger.info(f"Created thumbnails directory: {thumbnails_dir}")
            
            saved_files = []
            for transcript in transcripts:
                try:
                    # Check for cancellation before file writing
                    if cancellation_token and cancellation_token.is_cancelled():
                        logger.info("File writing cancelled by user")
                        break
                        
                    # Create sanitized filename from title
                    safe_title = re.sub(r"[^\w\s-]", "", transcript.title).strip()
                    safe_title = re.sub(r"[-\s]+", "-", safe_title)
                    
                    # Use sanitized title for filename, fallback to video ID if empty or placeholder
                    if (safe_title and len(safe_title) > 0 and 
                        not safe_title.startswith("YouTube-Video") and 
                        not transcript.title.startswith("YouTube Video ")):
                        filename = f"{safe_title}.{output_format}"
                        thumbnail_filename = f"{safe_title}-Thumbnail.jpg"
                    else:
                        filename = f"{transcript.video_id}_transcript.{output_format}"
                        thumbnail_filename = f"{transcript.video_id}-Thumbnail.jpg"

                    filepath = output_dir / filename
                    thumbnail_path = thumbnails_dir / thumbnail_filename
                    
                    logger.info(f"Creating transcript file: {filepath}")
                    logger.info(f"File path exists before writing: {filepath.parent.exists()}")

                    # Write transcript in requested format
                    vault_path_obj = Path(vault_path) if vault_path else None
                    interjections_file_obj = Path(interjections_file) if interjections_file else None
                    
                    if output_format == "md":
                        content = transcript.to_markdown(
                            include_timestamps=include_timestamps,
                            include_analysis=include_analysis,
                            vault_path=vault_path_obj,
                            output_dir=output_dir,
                            strip_interjections=strip_interjections,
                            interjections_file=interjections_file_obj
                        )
                    elif output_format == "srt":
                        content = transcript.to_srt(
                            strip_interjections=strip_interjections,
                            interjections_file=interjections_file_obj
                        )
                    else:
                        content = transcript.transcript_text

                    # Write file with detailed error handling
                    try:
                        with open(filepath, "w", encoding="utf-8") as f:
                            f.write(content)
                        logger.info(f"Successfully wrote {len(content)} characters to {filepath}")
                        
                        # Verify file was written correctly
                        if filepath.exists():
                            file_size = filepath.stat().st_size
                            logger.info(f"File verification successful: {filepath} ({file_size} bytes)")
                            saved_files.append(str(filepath))
                        else:
                            logger.error(f"File was not created: {filepath}")
                            errors.append(f"Failed to create file: {filepath}")
                            
                    except Exception as write_error:
                        logger.error(f"Failed to write file {filepath}: {write_error}")
                        errors.append(f"Failed to write file {filepath}: {write_error}")
                        continue
                    
                    # Download thumbnail
                    try:
                        logger.info(f"Downloading thumbnail for {transcript.video_id}")
                        from ..utils.youtube_utils import download_thumbnail
                        
                        thumbnail_result = download_thumbnail(transcript.url, thumbnails_dir, use_cookies=False)
                        if thumbnail_result:
                            # Rename the downloaded thumbnail to our desired name
                            downloaded_path = Path(thumbnail_result)
                            if downloaded_path.exists() and downloaded_path != thumbnail_path:
                                downloaded_path.rename(thumbnail_path)
                                logger.info(f"Thumbnail saved as: {thumbnail_path}")
                            elif downloaded_path == thumbnail_path:
                                logger.info(f"Thumbnail saved as: {thumbnail_path}")
                        else:
                            logger.warning(f"Failed to download thumbnail for {transcript.video_id}")
                    except Exception as e:
                        logger.warning(f"Thumbnail download failed for {transcript.video_id}: {e}")

                except Exception as e:
                    error_msg = f"Failed to save transcript for {transcript.video_id}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)

            # Return results
            success = len(transcripts) > 0
            logger.info(f"Transcript processing completed. Success: {success}, Files saved: {len(saved_files)}")
            
            return ProcessorResult(
                success=success,
                data={
                    "transcripts": [t.to_dict() for t in transcripts],
                    "saved_files": saved_files,
                    "output_format": output_format,
                    "output_directory": str(output_dir),
                },
                errors=errors if errors else None,
                metadata={
                    "processor": self.name,
                    "urls_processed": len(urls),
                    "transcripts_extracted": len(transcripts),
                    "files_saved": len(saved_files),
                    "prefer_manual": self.prefer_manual,
                    "fallback_to_auto": self.fallback_to_auto,
                    "cancelled": cancellation_token.is_cancelled if cancellation_token else False,
                },
            )
            
        except CancellationError:
            logger.info("YouTube transcript processing cancelled")
            return ProcessorResult(
                success=False,
                errors=["Processing cancelled by user"],
                metadata={
                    "processor": self.name,
                    "cancelled": True,
                }
            )
        except Exception as e:
            logger.error(f"Unexpected error in YouTube transcript processing: {e}")
            return ProcessorResult(
                success=False,
                errors=[f"Unexpected error: {e}"],
                metadata={
                    "processor": self.name,
                    "error": str(e),
                }
            )


def extract_youtube_transcript(
    url: str,
    preferred_language: str = "en",
    prefer_manual: bool = True,
    fallback_to_auto: bool = True,
) -> Optional[YouTubeTranscript]:
    """
    Standalone function to extract a single YouTube transcript.

    Args:
        url: YouTube video URL
        preferred_language: Preferred transcript language
        prefer_manual: Whether to prefer manual transcripts over automatic
        fallback_to_auto: Whether to fall back to automatic captions

    Returns:
        YouTubeTranscript object or None if extraction failed
    """
    processor = YouTubeTranscriptProcessor(
        preferred_language=preferred_language,
        prefer_manual=prefer_manual,
        fallback_to_auto=fallback_to_auto,
    )
    
    result = processor.process(url)
    
    if result.success and result.data and result.data.get("transcripts"):
        # Return the first transcript
        transcript_dict = result.data["transcripts"][0]
        return YouTubeTranscript(**transcript_dict)
    
    return None
