"""
YouTube utility functions for URL validation and processing

YouTube utility functions for URL validation and processing.
Consolidates common YouTube operations used across processors.
SIMPLE VERSION - No password prompts!
"""

import random
import re
import time
from pathlib import Path
from typing import Any

from ..logger import get_logger

logger = get_logger(__name__)

# YouTube URL patterns (consolidated from multiple processors)
YOUTUBE_URL_PATTERNS = [
    r"https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+",
    r"https?://(?:www\.)?youtube\.com/playlist\?list=[\w-]+",
    r"https?://(?:www\.)?youtu\.be/[\w-]+",
]

# Global cache for the successfully authenticated cookie jar
_cookie_jar_cache = None
_cookie_jar_timestamp = 0.0
_cookie_jar_ttl = 7200  # Cache cookies for 2 hours to avoid repeated keychain access


def is_youtube_url(text: str) -> bool:
    """
    Check if text contains a YouTube URL
    Check if text contains a YouTube URL.

    Args:
        text: Text to check for YouTube URLs

    Returns:
        True if text contains a YouTube URL, False otherwise
    """
    return any(re.search(pattern, text) for pattern in YOUTUBE_URL_PATTERNS)
    return any(re.search(pattern, text) for pattern in YOUTUBE_URL_PATTERNS)


def extract_urls(input_data: Any) -> list[str]:
    """
    Extract YouTube URLs from input data

    Extract YouTube URLs from input data.
    Handles both direct URLs and files containing URLs.

    Args:
        input_data: Input data (URL string or file path)

    Returns:
        List of YouTube URLs found

    Raises:
        FileNotFoundError: If input appears to be a file path but file doesn't exist
        IOError: If file cannot be read
    """
    # Handle different input types
    if isinstance(input_data, list):
        # If input is already a list, assume it's a list of URLs and return it
        urls = []
        for item in input_data:
            item_str = str(item)
            if is_youtube_url(item_str):
                urls.append(item_str)
        return urls

    input_str = str(input_data)
    urls = []

    # If it's already a URL
    if is_youtube_url(input_str):
        urls.append(input_str)
        return urls

    # If it's a file path
    file_path = Path(input_str)
    if file_path.exists():
        try:
            with open(file_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and is_youtube_url(line):
                        urls.append(line)
        except (OSError, UnicodeDecodeError) as e:
            logger.error(f"Error reading file {input_str}: {e}")
            raise OSError(f"Cannot read file: {e}")
    elif file_path.suffix and not file_path.exists():
        # If it looks like a file path but doesn't exist, raise error
        raise FileNotFoundError(f"File does not exist: {input_str}")

    return urls


def get_manual_cookie_file() -> Path | None:
    """
    Check for manual cookie file in common locations
    Check for manual cookie file in common locations.

    Returns:
        Path to cookie file if found, None otherwise
    """
    possible_paths = [
        Path.home() / ".config" / "knowledge_system" / "cookies.txt",
        Path.home() / ".knowledge_system" / "cookies.txt",
        Path.cwd() / "cookies.txt",
        Path.cwd() / "config" / "cookies.txt",
    ]

    for path in possible_paths:
        if path.exists():
            logger.info(f"Found manual cookie file: {path}")
            return path

    return None


def _show_cookie_help_dialog(error_message: str | None = None):
    """
    Shows a helpful dialog box when cookies are stale or authentication fails.

    Guarantees NSWindow/QMessageBox creation happens on the Qt main thread.
    """
    try:
        # Try to import GUI components
        from PyQt6.QtCore import QThread, QTimer
        from PyQt6.QtWidgets import QApplication, QMessageBox

        # Get the current application instance
        app = QApplication.instance()
        if not app:
            logger.warning("No QApplication instance found, cannot show dialog")
            return

        def _show_dialog() -> None:
            try:
                parent = app.activeWindow()
                msg_box = QMessageBox(parent)
                msg_box.setWindowTitle("YouTube Authentication Issue")
                msg_box.setIcon(QMessageBox.Icon.Warning)

                if (
                    error_message
                    and "sign in to confirm you're not a bot" in error_message.lower()
                ):
                    title = "YouTube Requires Fresh Authentication"
                    message = """
It looks like your YouTube cookies have expired or are no longer valid.

To fix this, please:

1. Open Chrome or Firefox and go to YouTube.com
2. Make sure you're logged into your Google account
3. Install a cookie exporter extension:
   • Chrome: "Get cookies.txt" extension
   • Firefox: "cookies.txt" extension
4. Click the extension icon and export cookies
5. Save the file as 'cookies.txt' in your config folder

This will allow the app to access YouTube without being blocked.

Would you like to see detailed instructions?
                    """
                else:
                    title = "YouTube Authentication Failed"
                    message = """
The app couldn't authenticate with YouTube using your current settings.

This usually means:
• Your browser cookies have expired
• YouTube is blocking automated access
• You need to provide fresh authentication

The easiest solution is to create a manual cookies.txt file.

Would you like to see detailed instructions?
                    """

                msg_box.setText(title)
                msg_box.setInformativeText(message)
                msg_box.setStandardButtons(
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)

                # Show the dialog on the main thread
                result = msg_box.exec()

                if result == QMessageBox.StandardButton.Yes:
                    # Show detailed instructions
                    detailed_msg = QMessageBox(parent)
                    detailed_msg.setWindowTitle("Detailed Cookie Instructions")
                    detailed_msg.setIcon(QMessageBox.Icon.Information)
                    detailed_msg.setText("How to Create a cookies.txt File")
                    detailed_msg.setInformativeText(create_cookie_instructions())
                    detailed_msg.setStandardButtons(QMessageBox.StandardButton.Ok)
                    detailed_msg.exec()
            except Exception as dialog_err:
                logger.error(f"Failed while showing cookie help dialog: {dialog_err}")

        # Marshal to main thread if needed
        if QThread.currentThread() != app.thread():
            QTimer.singleShot(0, _show_dialog)
            return

        _show_dialog()

    except ImportError:
        logger.warning("PyQt6 not available, cannot show dialog")
    except Exception as e:
        logger.error(f"Failed to prepare cookie help dialog: {e}")


def get_single_working_strategy() -> dict[str, Any]:
    """
    Gets a single, persistently cached, working authentication strategy
    Gets a single, persistently cached, working authentication strategy.

    This function tries strategies in order of effectiveness and caches the first
    successful one to avoid repeated password prompts and network requests.

    Order of strategies:
    1. Re-use a recently cached, working cookie jar.
    2. Use a manual `cookies.txt` file if it exists.
    3. Attempt to load cookies from browsers, stopping at the first success.
    4. Fallback to simple, unauthenticated headers.

    Returns:
        A dictionary of yt-dlp options for authentication.
    """
    global _cookie_jar_cache, _cookie_jar_timestamp
    global _cookie_jar_cache, _cookie_jar_timestamp

    # Strategy 1: Re-use a recently cached, working cookie jar
    now = time.time()
    if _cookie_jar_cache and (now - _cookie_jar_timestamp < _cookie_jar_ttl):
        logger.info("Re-using cached authentication strategy.")
        return {"cookiejar": _cookie_jar_cache}

    # Strategy 2: Use a manual `cookies.txt` file
    manual_cookie_file = get_manual_cookie_file()
    if manual_cookie_file:
        logger.info(f"Using manual cookie file: {manual_cookie_file}")
        return {"cookiefile": str(manual_cookie_file)}

    # Strategy 3: Attempt to load cookies from browsers, stopping at the first success
    try:
        pass

        from yt_dlp.cookies import load_cookies

        browsers_to_try = [
            ("chrome", None),
            ("safari", None),
            ("firefox", None),
            ("brave", None),
            ("edge", None),
            ("opera", None),
        ]

        for browser_name, profile in browsers_to_try:
            logger.info(f"Attempting to load cookies from {browser_name}...")
            try:
                # This is the point where macOS may ask for a password.
                cookie_jar = load_cookies(None, (browser_name, profile), None)
                if cookie_jar and len(list(cookie_jar)) > 0:
                    logger.info(
                        f"Loaded {len(list(cookie_jar))} cookies from {browser_name}."
                    )
                    # Cache the cookie jar for future use
                    _cookie_jar_cache = cookie_jar
                    _cookie_jar_timestamp = now
                    return {"cookiejar": cookie_jar}
            except Exception as e:
                # This is expected if a browser isn't installed.
                logger.debug(f"Could not load cookies from {browser_name}: {e}")
                continue  # Try the next browser
    except ImportError:
        logger.warning(
            "yt_dlp cookie importer not available. Cannot load browser cookies."
        )
    except Exception as e:
        logger.error(f"An unexpected error occurred during browser cookie loading: {e}")

    # Strategy 4: Fallback to simple, unauthenticated headers
    logger.info("Using fallback authentication strategy (no cookies).")
    return {
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "sleep_interval_requests": 1,
        "sleep_interval": 3,
        "max_sleep_interval": 10,
        "http_headers": {
            "Accept-Language": "en-US,en;q=0.9",
        },
    }


def create_cookie_instructions() -> str:
    """
    Create instructions for manually creating a cookie file
    Create instructions for manually creating a cookie file.

    Returns:
        String with detailed instructions
    """
    return """
To fix YouTube authentication issues, you can create a manual cookie file:

1. Install a browser extension like "Get cookies.txt" or "cookies.txt"
2. Visit YouTube in your browser and make sure you're logged in
3. Use the extension to export cookies for youtube.com
4. Save the cookie file as one of these paths:
   - ~/.config/knowledge_system/cookies.txt
   - ~/.knowledge_system/cookies.txt
   - ./cookies.txt (in your project directory)
   - ./config/cookies.txt

The cookie file should be in Netscape/Mozilla format (cookies.txt format).

Alternatively, you can try:
- Visiting YouTube videos in your browser first
- Using a different network connection
- Waiting a few minutes between attempts
"""


def extract_video_id(url: str) -> str:
    """
    Extract video ID from YouTube URL
    Extract video ID from YouTube URL.

    Args:
        url: YouTube URL

    Returns:
        Video ID string
    """
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]+)",
        r"youtube\.com/playlist\?list=([a-zA-Z0-9_-]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    # Fallback: use a hash of the URL
    import hashlib

    return hashlib.md5(url.encode(), usedforsecurity=False).hexdigest()[:8]


def is_playlist_url(url: str) -> bool:
    """
    Check if URL is a YouTube playlist
    Check if URL is a YouTube playlist.

    Args:
        url: URL to check

    Returns:
        True if URL is a playlist, False otherwise
    """
    return "playlist?list=" in url or ("list=" in url and "watch?v=" not in url)
    return "playlist?list=" in url or ("list=" in url and "watch?v=" not in url)


def expand_playlist_urls(urls: list[str]) -> list[str]:
    """
    Expand any playlist URLs in the list to individual video URLs
    Expand any playlist URLs in the list to individual video URLs.

    Args:
        urls: List of YouTube URLs that may contain playlists

    Returns:
        List of individual video URLs with playlists expanded
    """
    result = expand_playlist_urls_with_metadata(urls)

    result = expand_playlist_urls_with_metadata(urls)
    return result["expanded_urls"]


def expand_playlist_urls_with_metadata(urls: list[str]) -> dict[str, Any]:
    """
    Expand any playlist URLs in the list to individual video URLs with playlist metadata
    Expand any playlist URLs in the list to individual video URLs with playlist metadata.

    Args:
        urls: List of YouTube URLs that may contain playlists

    Returns:
        Dictionary containing:
        - 'expanded_urls': List of individual video URLs with playlists expanded
        - 'playlist_info': List of playlist metadata for tracking progress
    """
    try:
        import yt_dlp

        from ..config import get_settings
        from ..utils.packetstream_proxy import PacketStreamProxyManager

        settings = get_settings()

        # Check if PacketStream credentials are available
        use_proxy = False
        proxy_manager = None
        proxy_url = None

        try:
            proxy_manager = PacketStreamProxyManager()
            if proxy_manager.username and proxy_manager.auth_key:
                use_proxy = True
                logger.info(
                    "Using PacketStream residential proxies for playlist expansion"
                )
            else:
                logger.info(
                    "PacketStream proxy credentials not configured; using direct method"
                )
        except Exception as e:
            logger.info(f"PacketStream proxy not available (using direct method): {e}")
            use_proxy = False

        expanded_urls = []
        playlist_info = []

        for url in urls:
            if is_playlist_url(url):
                logger.info(f"Expanding playlist: {url}")

                # Get proxy URL if using PacketStream
                current_proxy_url = None
                if use_proxy and proxy_manager:
                    try:
                        current_proxy_url = proxy_manager.get_proxy_url()
                        if current_proxy_url:
                            logger.debug(
                                f"Using PacketStream proxy for playlist expansion"
                            )
                    except Exception as e:
                        logger.warning(f"Failed to get PacketStream proxy URL: {e}")

                ydl_opts = {
                    "quiet": True,
                    "no_warnings": True,
                    "extract_flat": True,  # Only extract URLs, don't download
                    "proxy": current_proxy_url,
                    "socket_timeout": 30,
                    "retries": 3,
                }

                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=False)

                        if info and "entries" in info:
                            playlist_title = info.get("title", "Unknown Playlist")
                            playlist_count = len(info["entries"])
                            playlist_start_index = len(expanded_urls)

                            for entry in info["entries"]:
                                if entry and "id" in entry:
                                    video_url = (
                                        f"https://www.youtube.com/watch?v={entry['id']}"
                                    )
                                    expanded_urls.append(video_url)

                            # Store playlist metadata for progress tracking
                            playlist_info.append(
                                {
                                    "original_url": url,
                                    "title": playlist_title,
                                    "total_videos": playlist_count,
                                    "start_index": playlist_start_index,
                                    "end_index": len(expanded_urls) - 1,
                                    "video_urls": expanded_urls[playlist_start_index:],
                                }
                            )

                            logger.info(
                                f"Expanded playlist '{playlist_title}' to {playlist_count} videos"
                            )

                            # Playlist expansion successful

                        else:
                            logger.warning(f"No entries found in playlist: {url}")

                except Exception as e:
                    logger.error(f"Failed to expand playlist {url}: {e}")
                    expanded_urls.append(url)  # Keep original if expansion fails

                finally:
                    # No cleanup needed for PacketStream (handled automatically)
                    pass
            else:
                expanded_urls.append(url)

        return {"expanded_urls": expanded_urls, "playlist_info": playlist_info}

    except ImportError:
        logger.warning("yt-dlp not available for playlist expansion")
        return {"expanded_urls": urls, "playlist_info": []}
    except Exception as e:
        logger.error(f"Error during playlist expansion: {e}")
        return {"expanded_urls": urls, "playlist_info": []}


def download_thumbnail_direct(
    url: str, output_dir: Path, thumbnail_url: str | None = None
) -> str | None:
    """
    Download thumbnail for YouTube video using direct URL access (no cookies needed)
    Download thumbnail for YouTube video using direct URL access (no cookies needed).

    Args:
        url: YouTube video URL
        output_dir: Directory to save thumbnail (should be the exact directory to save to)
        thumbnail_url: Optional specific thumbnail URL from YouTube API

    Returns:
        Path to downloaded thumbnail file, or None if failed
    """
    try:
        import time

        import requests

        video_id = extract_video_id(url)

        # BUGFIX: Save directly to provided output_dir, don't create additional "Thumbnails" subdirectory
        # The caller is responsible for ensuring they pass the correct directory
        output_dir.mkdir(parents=True, exist_ok=True)

        logger.debug(f"Downloading thumbnail directly for: {url} to {output_dir}")

        # Use API-provided thumbnail URL if available, otherwise try different quality levels
        thumbnail_configs = []
        if thumbnail_url and isinstance(thumbnail_url, str):
            thumbnail_configs.append(("api", thumbnail_url))
            logger.debug(f"Using API-provided thumbnail URL: {thumbnail_url}")
        else:
            logger.debug("No API thumbnail URL provided, trying direct image URLs")

        # Fallback to direct image URLs
        thumbnail_configs.extend(
            [
                ("maxres", f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"),
                ("hq", f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"),
                ("mq", f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"),
                ("default", f"https://img.youtube.com/vi/{video_id}/default.jpg"),
                # Alternative formats
                ("sd", f"https://img.youtube.com/vi/{video_id}/sddefault.jpg"),
                ("thumb1", f"https://img.youtube.com/vi/{video_id}/1.jpg"),
                ("thumb2", f"https://img.youtube.com/vi/{video_id}/2.jpg"),
                ("thumb3", f"https://img.youtube.com/vi/{video_id}/3.jpg"),
            ]
        )

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        for quality, thumbnail_image_url in thumbnail_configs:
            try:
                # Add a small delay to avoid rate limiting
                time.sleep(0.1)

                response = requests.get(
                    thumbnail_image_url, headers=headers, timeout=10
                )
                if response.status_code == 200:
                    # Check if it's a valid image (not a placeholder)
                    content_length = len(response.content)
                    if (
                        content_length > 1000
                    ):  # Valid thumbnails are typically larger than 1KB
                        thumbnail_path = output_dir / f"{video_id}_thumbnail.jpg"
                        with open(thumbnail_path, "wb") as f:
                            f.write(response.content)
                        logger.info(
                            f"Successfully downloaded {quality} thumbnail ({content_length} bytes): {thumbnail_path}"
                        )
                        return str(thumbnail_path)
                    else:
                        logger.debug(
                            f"{quality} thumbnail too small ({content_length} bytes), trying next quality"
                        )
                        continue
                else:
                    logger.debug(
                        f"{quality} thumbnail not available (status {response.status_code})"
                    )
                    continue
            except requests.exceptions.RequestException as e:
                logger.debug(f"Failed to download {quality} thumbnail: {e}")
                continue
            except Exception as e:
                logger.debug(f"Unexpected error downloading {quality} thumbnail: {e}")
                continue

        logger.warning(f"No thumbnail available for video: {video_id}")
        return None

    except Exception as e:
        logger.warning(f"Failed to download thumbnail for {url}: {e}")
        return None


def download_thumbnail(
    url: str,
    output_dir: Path,
    use_cookies: bool = False,
    thumbnail_url: str | None = None,
) -> str | None:
    """
    Download thumbnail for YouTube video using direct URL access (no bot detection risk)
    Download thumbnail for YouTube video using direct URL access (no bot detection risk).

    Args:
        url: YouTube video URL
        output_dir: Directory to save thumbnail
        use_cookies: Ignored - kept for backward compatibility
        thumbnail_url: Optional specific thumbnail URL from YouTube API

    Returns:
        Path to downloaded thumbnail file, or None if failed
    """
    # Always use direct download method - no yt-dlp fallback to avoid bot detection

    # Always use direct download method - no yt-dlp fallback to avoid bot detection
    return download_thumbnail_direct(url, output_dir, thumbnail_url)


def get_no_cookie_strategy() -> dict[str, Any]:
    """
    Gets authentication strategy that never uses cookies
    Gets authentication strategy that never uses cookies.

    Returns:
        A dictionary of yt-dlp options for cookie-free authentication.
    """
    logger.info("Using no-cookie authentication strategy.")

    logger.info("Using no-cookie authentication strategy.")
    return {
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "sleep_interval_requests": 1,
        "sleep_interval": 3,
        "max_sleep_interval": 10,
        "http_headers": {
            "Accept-Language": "en-US,en;q=0.9",
        },
    }


def download_thumbnails_batch(
    urls: list[str], output_dir: Path, timeout: int = 30, use_cookies: bool = False
) -> list[str | None]:
    """
    Download thumbnails for multiple YouTube videos with rate limiting
    Download thumbnails for multiple YouTube videos with rate limiting.

    Args:
        urls: List of YouTube video URLs
        output_dir: Directory to save thumbnails
        timeout: Request timeout in seconds
        use_cookies: Whether to use cookies for authentication (default: False)

    Returns:
        List of thumbnail paths (None for failed downloads)
    """
    thumbnail_paths = []
    thumbnail_paths = []

    for i, url in enumerate(urls):
        if i > 0:
            # Add a randomized delay between requests to avoid rate limiting
            delay = random.uniform(2, 5)
            logger.debug(f"Waiting for {delay:.2f} seconds before next download.")
            time.sleep(delay)

        thumbnail_path = download_thumbnail(url, output_dir, use_cookies=use_cookies)
        thumbnail_paths.append(thumbnail_path)

    return thumbnail_paths


def clear_authentication_cache():
    """Clear the authentication cache to force re-authentication."""
    global _cookie_jar_cache, _cookie_jar_timestamp

    _cookie_jar_cache = None
    _cookie_jar_timestamp = 0.0

    logger.info("Authentication cache cleared")


def get_authentication_status() -> dict[str, Any]:
    """
    Get current authentication status and diagnostics
    Get current authentication status and diagnostics.

    Returns:
        Dictionary with authentication status information
    """
    now = time.time()
    now = time.time()

    status = {
        "is_authenticated": _cookie_jar_cache is not None,
        "cache_age_seconds": (
            (now - _cookie_jar_timestamp) if _cookie_jar_cache else None
        ),
        "manual_cookie_file_found": (
            str(get_manual_cookie_file()) if get_manual_cookie_file() else "No"
        ),
    }

    return status


def initiate_browser_authentication() -> bool:
    """
    Initiate a browser-based authentication flow for YouTube

    Initiate a browser-based authentication flow for YouTube.
    This opens the user's browser to authenticate with YouTube without storing passwords.

    Returns:
        True if authentication was initiated successfully, False otherwise
    """
    try:
        import platform
        import subprocess
        import webbrowser

        # Open YouTube in the default browser
        youtube_url = "https://www.youtube.com"

        logger.info("Opening YouTube in your browser for authentication...")
        logger.info("Please:")
        logger.info("1. Sign in to your Google account")
        logger.info("2. Visit a few YouTube videos to establish session")
        logger.info("3. Return to the app and try processing again")

        # Open browser
        webbrowser.open(youtube_url)

        # Also show instructions in a more prominent way
        if platform.system() == "Darwin":  # macOS
            try:
                subprocess.run(
                    [
                        "osascript",
                        "-e",
                        'display dialog "YouTube authentication required!\n\nPlease:\n1. Sign in to YouTube in your browser\n2. Visit a few videos\n3. Return here and try again" with title "YouTube Authentication" buttons {"OK"} default button "OK"',
                    ],
                    check=False,
                )
            except Exception as e:
                logger.debug(
                    f"AppleScript network optimization failed: {e}"
                )  # Fallback if AppleScript fails

        return True

    except Exception as e:
        logger.error(f"Failed to initiate browser authentication: {e}")
        return False


def get_authentication_help() -> str:
    """
    Get comprehensive help for YouTube authentication issues
    Get comprehensive help for YouTube authentication issues.

    Returns:
        String with detailed authentication help
    """
    return """
YouTube Authentication Help

The app needs to authenticate with YouTube to access video transcripts. Here are the secure ways to do this:

Browser-based authentication (recommended):
1. Click "Open Browser for Authentication" in the Utilities tab
2. Sign in to your Google account in the browser
3. Visit a few YouTube videos to establish your session
4. Return to the app and try processing again

Manual cookie export:
1. Install a browser extension:
   • Chrome: "Get cookies.txt" extension
   • Firefox: "cookies.txt" extension
2. Visit YouTube and make sure you're logged in
3. Use the extension to export cookies for youtube.com
4. Save as 'cookies.txt' in your config folder

Security notes:
• Your app NEVER stores passwords
• Only session cookies are used (like your browser)
• Cookies expire automatically
• You can revoke access anytime in your Google account

Troubleshooting:
• Try different browsers (Chrome, Safari, Firefox)
• Wait a few minutes between attempts
• Check if videos are age-restricted or private
• Use a different network connection if needed
"""
