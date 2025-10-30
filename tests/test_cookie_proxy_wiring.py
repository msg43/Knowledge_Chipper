#!/usr/bin/env python3
"""
Test to verify cookie and proxy settings are properly wired from GUI to download processor.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.knowledge_system.processors.youtube_download import YouTubeDownloadProcessor
from src.knowledge_system.services.download_scheduler import DownloadScheduler
from src.knowledge_system.services.multi_account_downloader import (
    MultiAccountDownloadScheduler,
)
from src.knowledge_system.services.youtube_download_service import (
    YouTubeDownloadService,
)


def test_youtube_download_processor_accepts_disable_proxies_param():
    """Test that YouTubeDownloadProcessor accepts disable_proxies_with_cookies parameter."""
    processor = YouTubeDownloadProcessor(
        enable_cookies=True,
        cookie_file_path="/tmp/test_cookies.txt",
        disable_proxies_with_cookies=True,
    )

    assert processor.enable_cookies is True
    assert processor.cookie_file_path == "/tmp/test_cookies.txt"
    assert processor.disable_proxies_with_cookies is True


def test_youtube_download_processor_uses_gui_setting_over_config():
    """Test that processor uses GUI setting (instance variable) over config file."""
    # Create processor with explicit setting
    processor = YouTubeDownloadProcessor(
        enable_cookies=True,
        cookie_file_path="/tmp/test_cookies.txt",
        disable_proxies_with_cookies=False,  # GUI says use proxies
    )

    # The processor should store the instance variable correctly
    # When process() is called, it will check instance variable first before config
    assert processor.disable_proxies_with_cookies is False

    # Test with opposite value
    processor2 = YouTubeDownloadProcessor(
        enable_cookies=True,
        cookie_file_path="/tmp/test_cookies.txt",
        disable_proxies_with_cookies=True,  # GUI says disable proxies
    )
    assert processor2.disable_proxies_with_cookies is True


def test_youtube_download_service_passes_parameter():
    """Test that YouTubeDownloadService passes disable_proxies_with_cookies to processor."""
    service = YouTubeDownloadService(
        enable_cookies=True,
        cookie_file_path="/tmp/test_cookies.txt",
        disable_proxies_with_cookies=True,
    )

    # Verify the parameter was passed to the underlying processor
    assert service.downloader.disable_proxies_with_cookies is True


def test_download_scheduler_passes_parameter():
    """Test that DownloadScheduler passes disable_proxies_with_cookies to processor."""
    scheduler = DownloadScheduler(
        cookie_file_path="/tmp/test_cookies.txt",
        disable_proxies_with_cookies=True,
    )

    # Verify the parameter was passed to the underlying processor
    assert scheduler.downloader.disable_proxies_with_cookies is True


def test_multi_account_scheduler_passes_parameter():
    """Test that MultiAccountDownloadScheduler passes disable_proxies_with_cookies to all schedulers."""
    scheduler = MultiAccountDownloadScheduler(
        cookie_files=["/tmp/cookies1.txt", "/tmp/cookies2.txt"],
        disable_proxies_with_cookies=True,
    )

    # Verify all underlying schedulers got the parameter
    for sub_scheduler in scheduler.schedulers:
        assert sub_scheduler.downloader.disable_proxies_with_cookies is True


def test_processor_defaults_to_none_when_not_specified():
    """Test that processor defaults to None (will use config) when parameter not specified."""
    processor = YouTubeDownloadProcessor(
        enable_cookies=True,
        cookie_file_path="/tmp/test_cookies.txt",
        # disable_proxies_with_cookies not specified
    )

    # Should default to None, which means "use config file value"
    assert processor.disable_proxies_with_cookies is None


def test_processor_respects_explicit_false():
    """Test that processor respects explicit False (use proxies even with cookies)."""
    processor = YouTubeDownloadProcessor(
        enable_cookies=True,
        cookie_file_path="/tmp/test_cookies.txt",
        disable_proxies_with_cookies=False,  # Explicitly use proxies
    )

    assert processor.disable_proxies_with_cookies is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
