#!/usr/bin/env python3
"""
Scrape complete YouTube video data: metadata, transcript, and AI summary.
Outputs in Knowledge_Chipper markdown format.
"""
import sys
import asyncio
import json
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from knowledge_system.services.playwright_youtube_scraper import PlaywrightYouTubeScraper
from knowledge_system.logger import get_logger

logger = get_logger(__name__)


async def scrape_complete_video_data(url: str) -> dict:
    """
    Scrape complete video data including metadata, transcript, and AI summary.
    """
    from playwright.async_api import async_playwright
    from knowledge_system.services.browser_cookie_manager import BrowserCookieManager
    
    cookie_manager = BrowserCookieManager()
    result = {
        'metadata': {},
        'transcript': '',
        'ai_summary': '',
        'success': False,
        'errors': []
    }
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            
            # Load cookies
            cookies = cookie_manager.get_youtube_cookies_for_playwright()
            if cookies:
                await context.add_cookies(cookies)
                print(f"✅ Loaded {len(cookies)} authentication cookies")
            
            page = await context.new_page()
            
            try:
                # Navigate to video
                print(f"📺 Navigating to video...")
                await page.goto(url, wait_until='networkidle', timeout=15000)
                await page.wait_for_timeout(3000)  # Extra wait for dynamic content
                
                # Extract metadata from page
                print(f"📋 Extracting metadata...")
                metadata = await extract_metadata(page, url)
                result['metadata'] = metadata
                
                # Get transcript
                print(f"📝 Getting transcript...")
                transcript = await extract_transcript(page)
                result['transcript'] = transcript
                
                # Get AI summary
                print(f"🤖 Getting YouTube AI summary...")
                ai_summary = await extract_ai_summary(page)
                result['ai_summary'] = ai_summary
                
                result['success'] = True
                
            finally:
                await browser.close()
                
    except Exception as e:
        logger.error(f"Failed to scrape video: {e}", exc_info=True)
        result['errors'].append(str(e))
    
    return result


async def extract_metadata(page, url: str) -> dict:
    """Extract video metadata from the page."""
    metadata = {'url': url}
    
    try:
        # Title
        title_element = await page.query_selector('h1.ytd-watch-metadata yt-formatted-string')
        if title_element:
            metadata['title'] = await title_element.inner_text()
        
        # Channel name
        channel_element = await page.query_selector('ytd-channel-name a')
        if channel_element:
            metadata['uploader'] = await channel_element.inner_text()
        
        # Video ID
        video_id = url.split('v=')[1].split('&')[0] if 'v=' in url else 'unknown'
        metadata['video_id'] = video_id
        
        # Description (expand it first)
        try:
            more_button = await page.query_selector('tp-yt-paper-button#expand')
            if more_button:
                await more_button.click()
                await page.wait_for_timeout(500)
        except:
            pass
        
        desc_element = await page.query_selector('ytd-text-inline-expander#description-inline-expander')
        if desc_element:
            metadata['description'] = await desc_element.inner_text()
        
        # Views, date, etc. from metadata
        info_element = await page.query_selector('#info-container #info')
        if info_element:
            info_text = await info_element.inner_text()
            metadata['info'] = info_text
        
        return metadata
        
    except Exception as e:
        logger.error(f"Error extracting metadata: {e}")
        return metadata


async def extract_transcript(page) -> str:
    """Extract transcript using YouTube's transcript API."""
    try:
        # Get video ID from current URL
        url = page.url
        video_id = url.split('v=')[1].split('&')[0] if 'v=' in url else None
        
        if video_id:
            # Use the correct API - create instance and fetch
            from youtube_transcript_api import YouTubeTranscriptApi
            
            api = YouTubeTranscriptApi()
            transcript_data = api.fetch(video_id)
            
            # Format transcript with timestamps
            formatted_transcript = ""
            for entry in transcript_data:
                # Extract data from the transcript snippet object
                start_time = entry.start if hasattr(entry, 'start') else entry['start']
                text = entry.text if hasattr(entry, 'text') else entry['text']
                
                minutes = int(start_time // 60)
                seconds = int(start_time % 60)
                timestamp = f"{minutes:02d}:{seconds:02d}"
                formatted_transcript += f"**{timestamp}** {text}\n\n"
            
            return formatted_transcript
        
    except Exception as e:
        logger.error(f"Error extracting transcript: {e}")
    
    return "Transcript not available"


async def extract_ai_summary(page) -> str:
    """Extract YouTube AI summary by clicking Ask button."""
    try:
        # Find and click Ask button
        ask_selectors = [
            "button[aria-label*='Ask']",
            "button:has-text('Ask')",
            "ytd-button-renderer:has-text('Ask')",
        ]
        
        ask_button = None
        for selector in ask_selectors:
            try:
                btn = await page.query_selector(selector)
                if btn and await btn.is_visible():
                    ask_button = btn
                    print(f"  Found Ask button")
                    break
            except:
                continue
        
        if not ask_button:
            return "YouTube AI summary not available (Ask button not found - may require YouTube Premium)"
        
        # Click Ask
        await ask_button.click()
        await page.wait_for_timeout(2000)
        
        # Find and click Summarize
        summarize_selectors = [
            "button:has-text('Summarize')",
            "ytd-menu-item:has-text('Summarize')",
            "tp-yt-paper-item:has-text('Summarize')",
        ]
        
        summarize_button = None
        for selector in summarize_selectors:
            try:
                btn = await page.query_selector(selector)
                if btn and await btn.is_visible():
                    summarize_button = btn
                    print(f"  Found Summarize button")
                    break
            except:
                continue
        
        if not summarize_button:
            return "YouTube AI summary not available (Summarize option not found)"
        
        # Click Summarize
        await summarize_button.click()
        print(f"  Waiting for YouTube to generate summary (10-20 seconds for long videos)...")
        
        # Wait longer for initial generation - long videos take more time
        await page.wait_for_timeout(12000)  # Initial 12 second wait
        
        # Poll for summary content with much longer timeout
        max_wait = 60  # Increased to 60 seconds for long videos
        start = asyncio.get_event_loop().time()
        last_length = 0
        stable_count = 0
        last_text = ""
        
        while (asyncio.get_event_loop().time() - start) < max_wait:
            # Try to get the entire engagement panel content
            selectors = [
                'ytd-engagement-panel-section-list-renderer [id="content"]',
                'ytd-engagement-panel-section-list-renderer',
                '[role="article"]',
                '.response-content',
            ]
            
            for selector in selectors:
                try:
                    panel = await page.query_selector(selector)
                    if panel:
                        # Get all text from the panel
                        full_text = await panel.inner_text()
                        
                        # Filter out UI noise
                        lines = full_text.split('\n')
                        filtered_lines = []
                        
                        skip_phrases = [
                            'Hello!',
                            'Curious about',
                            'Not sure what to ask',
                            'Choose something:',
                            'Follow along using the transcript',
                            'Show transcript',
                        ]
                        
                        for line in lines:
                            line = line.strip()
                            # Skip empty lines and UI elements
                            if not line or any(phrase in line for phrase in skip_phrases):
                                continue
                            # Skip very short lines that are likely UI elements
                            if len(line) < 15:
                                continue
                            filtered_lines.append(line)
                        
                        if filtered_lines:
                            clean_text = '\n\n'.join(filtered_lines)
                            current_length = len(clean_text)
                            
                            # Check if summary has stopped growing
                            if current_length == last_length and clean_text == last_text:
                                stable_count += 1
                                # Need 5 stable checks for long summaries
                                if stable_count >= 5 and current_length > 300:
                                    print(f"  ✅ Summary complete ({current_length} chars)")
                                    return clean_text
                            else:
                                if current_length > last_length:
                                    print(f"  📝 Summary growing... ({current_length} chars)")
                                stable_count = 0
                                last_length = current_length
                                last_text = clean_text
                            
                            break  # Found content, no need to try other selectors
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue
            
            await page.wait_for_timeout(2000)  # Check every 2 seconds
        
        # Return what we have even if timeout
        if last_length > 100:
            print(f"  ⚠️  Timeout but got summary ({last_length} chars)")
            return last_text
        
        return "YouTube AI summary generation timed out"
        
    except Exception as e:
        logger.error(f"Error extracting AI summary: {e}")
        return f"Error getting AI summary: {str(e)}"


def format_markdown_output(data: dict) -> str:
    """Format scraped data into Knowledge_Chipper markdown format."""
    metadata = data['metadata']
    base_url = metadata.get('url', '').split('&')[0].split('#')[0]  # Clean URL
    
    # Format duration if available
    duration_str = "Unknown"
    
    # Format date
    generated_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Build YAML frontmatter
    frontmatter_lines = [
        f'title: "{metadata.get("title", "Unknown Title")}"',
        f'video_id: "{metadata.get("video_id", "unknown")}"',
        f'uploader: "{metadata.get("uploader", "Unknown")}"',
        f'url: "{metadata.get("url", "")}"',
        f'generated: "{generated_date}"',
    ]
    
    frontmatter = '\n'.join(frontmatter_lines)
    
    # Helper function to convert timestamps to YouTube links
    def hyperlink_timestamps(text: str, base_url: str) -> str:
        """Convert timestamps like (0:55) or 00:00 to clickable YouTube links."""
        import re
        
        # Pattern 1a: Timestamp RANGES in parentheses like (1:16-1:28) or (32:15-32:37)
        def replace_paren_range(match):
            start_ts = match.group(1)
            end_ts = match.group(2)
            start_sec = parse_timestamp_to_seconds(start_ts)
            end_sec = parse_timestamp_to_seconds(end_ts)
            # Link to start time
            return f"([{start_ts}]({base_url}&t={start_sec}s)-[{end_ts}]({base_url}&t={end_sec}s))"
        
        text = re.sub(r'\((\d{1,2}:\d{2})-(\d{1,2}:\d{2})\)', replace_paren_range, text)
        
        # Pattern 1b: Single timestamps in parentheses like (0:55) or (27:02)
        def replace_paren_timestamp(match):
            timestamp = match.group(1)
            seconds = parse_timestamp_to_seconds(timestamp)
            return f"[{timestamp}]({base_url}&t={seconds}s)"
        
        text = re.sub(r'\((\d{1,2}:\d{2})\)', replace_paren_timestamp, text)
        
        # Pattern 1c: Timestamps in square brackets like [7:12] or [0:55]
        # But NOT if they're already hyperlinked (would have "](" after them)
        def replace_bracket_timestamp(match):
            # Check if this is already a hyperlink by looking ahead
            full_match = match.group(0)
            timestamp = match.group(1)
            # If followed by ](, it's already a link, skip it
            return full_match  # Will be handled by negative lookahead in regex
        
        # Use negative lookahead to avoid matching already-hyperlinked timestamps
        text = re.sub(
            r'\[(\d{1,2}:\d{2})\](?!\()',
            lambda m: f"[{m.group(1)}]({base_url}&t={parse_timestamp_to_seconds(m.group(1))}s)",
            text
        )
        
        # Pattern 2: Bold timestamps like **00:06**
        text = re.sub(
            r'\*\*(\d{1,2}:\d{2})\*\*',
            lambda m: f"**[{m.group(1)}]({base_url}&t={parse_timestamp_to_seconds(m.group(1))}s)**",
            text
        )
        
        # Pattern 3: Timestamps with // separator like "00:00 //"
        text = re.sub(
            r'(\d{2}:\d{2}) //',
            lambda m: f"[{m.group(1)}]({base_url}&t={parse_timestamp_to_seconds(m.group(1))}s) //",
            text
        )
        
        # Pattern 4: Standalone timestamps at start of line (chapters)
        # This is tricky - we need to avoid false positives
        # Only match if it's at the start of a line followed by newline or end
        # Use word boundaries and context to avoid matching time-like numbers in text
        lines = text.split('\n')
        processed_lines = []
        
        for line in lines:
            stripped = line.strip()
            # Check if line is JUST a timestamp (chapter marker)
            # Match: "0:00" or "2:24" or "50:08" at start of line
            if re.match(r'^(\d{1,2}:\d{2})$', stripped):
                timestamp = stripped
                seconds = parse_timestamp_to_seconds(timestamp)
                processed_lines.append(f"[{timestamp}]({base_url}&t={seconds}s)")
            else:
                processed_lines.append(line)
        
        return '\n'.join(processed_lines)
    
    def parse_timestamp_to_seconds(timestamp: str) -> int:
        """Convert timestamp string like '1:23' or '01:23:45' to seconds."""
        parts = timestamp.split(':')
        if len(parts) == 2:
            # MM:SS format
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            # HH:MM:SS format
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        return 0
    
    # Hyperlink all timestamps
    description = hyperlink_timestamps(metadata.get('description', 'No description available'), base_url)
    ai_summary = hyperlink_timestamps(data.get('ai_summary', 'AI summary not available'), base_url)
    transcript = hyperlink_timestamps(data.get('transcript', 'Transcript not available'), base_url)
    
    # Build markdown content
    markdown = f"""---
{frontmatter}
---

# {metadata.get('title', 'Unknown Title')}

## Video Metadata

- **Title**: {metadata.get('title', 'Unknown')}
- **Channel**: {metadata.get('uploader', 'Unknown')}
- **Video ID**: {metadata.get('video_id', 'unknown')}
- **URL**: [{metadata.get('url', '')}]({metadata.get('url', '')})
- **Generated**: {generated_date}

## Description

{description}

## YouTube AI Summary

{ai_summary}

## Full Transcript

> **Note**: This transcript was extracted from YouTube's automatic captions. Click any timestamp to jump to that point in the video.

{transcript}

---
*Generated by Knowledge_Chipper YouTube Scraper on {generated_date}*
"""
    
    return markdown


def main():
    if len(sys.argv) < 2:
        print("Usage: python scrape_youtube_complete.py <youtube_url> [output_file]")
        print("\nExample:")
        print("  python scrape_youtube_complete.py 'https://www.youtube.com/watch?v=AmIiqY2VJkQ'")
        sys.exit(1)
    
    url = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    print(f"\n{'='*70}")
    print(f"YouTube Complete Video Scraper")
    print(f"{'='*70}\n")
    print(f"URL: {url}\n")
    
    # Scrape data
    data = asyncio.run(scrape_complete_video_data(url))
    
    if not data['success']:
        print(f"\n❌ Failed to scrape video")
        for error in data['errors']:
            print(f"   {error}")
        sys.exit(1)
    
    # Format as markdown
    markdown = format_markdown_output(data)
    
    # Save to file
    if output_file:
        output_path = Path(output_file)
    else:
        video_id = data['metadata'].get('video_id', 'unknown')
        output_path = Path(f"output/{video_id}_complete.md")
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding='utf-8')
    
    print(f"\n{'='*70}")
    print(f"✅ Complete video data scraped successfully!")
    print(f"{'='*70}\n")
    print(f"📄 Saved to: {output_path}")
    print(f"📝 Transcript: {len(data['transcript'])} characters")
    print(f"🤖 AI Summary: {len(data['ai_summary'])} characters")
    print(f"\n{'='*70}\n")
    
    # Also print the markdown to console
    print(markdown)


if __name__ == "__main__":
    main()

