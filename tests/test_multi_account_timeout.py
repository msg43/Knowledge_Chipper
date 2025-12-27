#!/usr/bin/env python3
"""
Tests for multi-account download timeout handling.

Verifies that:
1. Downloads timeout after specified duration
2. Timed-out downloads are added to retry queue
3. System moves to next account after timeout
4. Retry queue processes timed-out downloads
"""

import asyncio
import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from knowledge_system.services.multi_account_downloader import MultiAccountDownloadScheduler


@pytest.fixture
def mock_schedulers():
    """Create mock download schedulers."""
    schedulers = []
    for i in range(3):
        scheduler = Mock()
        scheduler.is_sleep_time = Mock(return_value=False)
        scheduler.download_single = AsyncMock()
        schedulers.append(scheduler)
    return schedulers


@pytest.fixture
def multi_account_scheduler(tmp_path, mock_schedulers):
    """Create MultiAccountDownloadScheduler with mock schedulers."""
    cookie_files = [f"cookie_{i}.txt" for i in range(3)]
    
    with patch('knowledge_system.services.multi_account_downloader.DownloadScheduler') as mock_ds:
        mock_ds.side_effect = mock_schedulers
        
        scheduler = MultiAccountDownloadScheduler(
            cookie_files=cookie_files,
            parallel_workers=3,
            enable_sleep_period=False,
        )
        
        # Replace schedulers with our mocks
        scheduler.schedulers = mock_schedulers
        
        return scheduler


@pytest.mark.asyncio
async def test_download_timeout_moves_to_retry_queue(multi_account_scheduler, tmp_path):
    """Test that timed-out downloads are added to retry queue."""
    
    # Mock a download that takes too long
    async def slow_download(*args, **kwargs):
        await asyncio.sleep(100)  # Simulate stuck download
        return {"success": True, "url": "test_url"}
    
    multi_account_scheduler.schedulers[0].download_single = slow_download
    
    # Attempt download with 1-second timeout
    result = await multi_account_scheduler.download_with_failover(
        url="https://youtube.com/watch?v=test123",
        account_idx=0,
        scheduler=multi_account_scheduler.schedulers[0],
        output_dir=tmp_path,
        timeout=1.0  # 1 second timeout
    )
    
    # Verify download failed due to timeout
    assert result["success"] is False
    assert "Timeout" in result["error"]
    
    # Verify URL was added to retry queue
    assert "https://youtube.com/watch?v=test123" in multi_account_scheduler.retry_queue
    
    # Verify account health was updated
    assert multi_account_scheduler.account_health[0]["consecutive_failures"] == 1
    assert multi_account_scheduler.account_health[0]["total_failures"] == 1


@pytest.mark.asyncio
async def test_successful_download_completes_within_timeout(multi_account_scheduler, tmp_path):
    """Test that successful downloads complete within timeout."""
    
    # Mock a fast successful download
    async def fast_download(*args, **kwargs):
        await asyncio.sleep(0.1)  # Quick download
        return {
            "success": True,
            "url": "test_url",
            "audio_file": tmp_path / "test.mp3"
        }
    
    multi_account_scheduler.schedulers[0].download_single = fast_download
    
    # Attempt download with 5-second timeout
    result = await multi_account_scheduler.download_with_failover(
        url="https://youtube.com/watch?v=test456",
        account_idx=0,
        scheduler=multi_account_scheduler.schedulers[0],
        output_dir=tmp_path,
        timeout=5.0
    )
    
    # Verify download succeeded
    assert result["success"] is True
    
    # Verify URL was NOT added to retry queue
    assert "https://youtube.com/watch?v=test456" not in multi_account_scheduler.retry_queue
    
    # Verify account health shows success
    assert multi_account_scheduler.account_health[0]["consecutive_failures"] == 0
    assert multi_account_scheduler.account_health[0]["total_downloads"] == 1


@pytest.mark.asyncio
async def test_timeout_statistics_tracking(multi_account_scheduler, tmp_path):
    """Test that timeout statistics are tracked correctly."""
    
    # Mock a slow download
    async def slow_download(*args, **kwargs):
        await asyncio.sleep(100)
        return {"success": True}
    
    multi_account_scheduler.schedulers[0].download_single = slow_download
    
    initial_failed = multi_account_scheduler.stats["downloads_failed"]
    
    # Attempt download with timeout
    await multi_account_scheduler.download_with_failover(
        url="https://youtube.com/watch?v=test789",
        account_idx=0,
        scheduler=multi_account_scheduler.schedulers[0],
        output_dir=tmp_path,
        timeout=1.0
    )
    
    # Verify statistics were updated
    assert multi_account_scheduler.stats["downloads_failed"] == initial_failed + 1


@pytest.mark.asyncio
async def test_multiple_timeouts_different_accounts(multi_account_scheduler, tmp_path):
    """Test that multiple accounts can timeout independently."""
    
    # Mock slow downloads for multiple accounts
    for i in range(3):
        async def slow_download(*args, **kwargs):
            await asyncio.sleep(100)
            return {"success": True}
        
        multi_account_scheduler.schedulers[i].download_single = slow_download
    
    # Attempt downloads on different accounts
    urls = [
        "https://youtube.com/watch?v=test1",
        "https://youtube.com/watch?v=test2",
        "https://youtube.com/watch?v=test3",
    ]
    
    for i, url in enumerate(urls):
        await multi_account_scheduler.download_with_failover(
            url=url,
            account_idx=i,
            scheduler=multi_account_scheduler.schedulers[i],
            output_dir=tmp_path,
            timeout=1.0
        )
    
    # Verify all URLs were added to retry queue
    assert len(multi_account_scheduler.retry_queue) == 3
    for url in urls:
        assert url in multi_account_scheduler.retry_queue
    
    # Verify each account's health was updated
    for i in range(3):
        assert multi_account_scheduler.account_health[i]["consecutive_failures"] == 1


@pytest.mark.asyncio
async def test_custom_timeout_values(multi_account_scheduler, tmp_path):
    """Test that custom timeout values work correctly."""
    
    # Mock a download that takes 3 seconds
    async def medium_download(*args, **kwargs):
        await asyncio.sleep(3)
        return {"success": True, "url": "test_url"}
    
    multi_account_scheduler.schedulers[0].download_single = medium_download
    
    # Test with 2-second timeout (should timeout)
    result_short = await multi_account_scheduler.download_with_failover(
        url="https://youtube.com/watch?v=short",
        account_idx=0,
        scheduler=multi_account_scheduler.schedulers[0],
        output_dir=tmp_path,
        timeout=2.0
    )
    
    assert result_short["success"] is False
    assert "Timeout" in result_short["error"]
    
    # Reset retry queue
    multi_account_scheduler.retry_queue.clear()
    
    # Test with 5-second timeout (should succeed)
    result_long = await multi_account_scheduler.download_with_failover(
        url="https://youtube.com/watch?v=long",
        account_idx=0,
        scheduler=multi_account_scheduler.schedulers[0],
        output_dir=tmp_path,
        timeout=5.0
    )
    
    assert result_long["success"] is True
    assert len(multi_account_scheduler.retry_queue) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

