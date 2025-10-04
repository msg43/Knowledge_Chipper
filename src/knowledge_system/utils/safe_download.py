"""Safe download utilities with proper error handling and recovery."""
import os
import signal
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Optional

import requests

from ..logger import get_logger

logger = get_logger(__name__)


class SafeDownloader:
    """Thread-safe downloader with timeout and signal handling."""

    def __init__(self, timeout: int = 300):  # 5 minute default timeout
        self.timeout = timeout
        self._stop_event = threading.Event()

    def download_file(
        self,
        url: str,
        dest_path: Path,
        progress_callback: Callable | None = None,
        chunk_size: int = 1024 * 1024,  # 1MB chunks for large files
    ) -> bool:
        """
        Download a file safely with proper error handling.

        Returns:
            True if successful, False otherwise
        """
        temp_path = dest_path.with_suffix(".tmp")

        try:
            # Start download with timeout
            logger.info(f"Starting download: {url} -> {dest_path}")

            session = requests.Session()
            session.headers.update(
                {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                }
            )

            # Get file with streaming
            response = session.get(
                url,
                stream=True,
                timeout=(10, 30),  # (connect timeout, read timeout)
                allow_redirects=True,
            )
            response.raise_for_status()

            # Get total size
            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0
            start_time = time.time()

            # Download in chunks
            with open(temp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if self._stop_event.is_set():
                        logger.warning("Download cancelled by user")
                        return False

                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        # Check timeout
                        if time.time() - start_time > self.timeout:
                            raise TimeoutError(
                                f"Download exceeded {self.timeout}s timeout"
                            )

                        # Progress callback
                        if progress_callback and total_size > 0:
                            percent = (downloaded / total_size) * 100
                            elapsed = time.time() - start_time
                            speed_mbps = (
                                (downloaded / (1024 * 1024)) / elapsed
                                if elapsed > 0
                                else 0
                            )

                            progress_callback(
                                {
                                    "status": "downloading",
                                    "percent": percent,
                                    "downloaded_mb": downloaded / (1024 * 1024),
                                    "total_mb": total_size / (1024 * 1024),
                                    "speed_mbps": speed_mbps,
                                    "message": f"Downloading: {percent:.1f}% ({speed_mbps:.1f} MB/s)",
                                }
                            )

            # Verify download
            if total_size > 0 and downloaded != total_size:
                raise Exception(f"Incomplete download: {downloaded}/{total_size} bytes")

            # Move to final location
            temp_path.rename(dest_path)
            logger.info(f"Download completed: {dest_path}")
            return True

        except requests.exceptions.Timeout:
            logger.error("Download timed out")
            if progress_callback:
                progress_callback(
                    {
                        "status": "error",
                        "message": "Download timed out - check your connection",
                    }
                )
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error: {e}")
            if progress_callback:
                progress_callback(
                    {"status": "error", "message": "Connection failed - check internet"}
                )
        except Exception as e:
            logger.error(f"Download error: {e}")
            if progress_callback:
                progress_callback(
                    {"status": "error", "message": f"Download failed: {str(e)}"}
                )
        finally:
            # Cleanup temp file
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except:
                    pass

        return False

    def cancel(self):
        """Cancel ongoing download."""
        self._stop_event.set()


def download_with_retry(
    url: str,
    dest_path: Path,
    max_retries: int = 3,
    progress_callback: Callable | None = None,
) -> bool:
    """
    Download with automatic retry on failure.

    Returns:
        True if successful, False otherwise
    """
    for attempt in range(max_retries):
        if attempt > 0:
            logger.info(f"Retry attempt {attempt + 1}/{max_retries}")
            time.sleep(2**attempt)  # Exponential backoff

        downloader = SafeDownloader()
        if downloader.download_file(url, dest_path, progress_callback):
            return True

    return False
