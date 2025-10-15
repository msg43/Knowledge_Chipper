#!/usr/bin/env python3
"""
Usage Example: Connected Processing with Audio Preservation

This example shows how to use the connected processing coordinator
with intelligent audio preservation and staging.
"""

import asyncio
from pathlib import Path
from typing import Any

from .connected_processing_coordinator import (
    AudioPreservationConfig,
    ConnectedProcessingCoordinator,
    process_with_audio_preservation,
)


async def example_basic_usage():
    """Basic usage example with audio preservation"""

    # Example URLs
    urls = [
        "https://www.youtube.com/watch?v=example1",
        "https://www.youtube.com/watch?v=example2",
        # ... 5000 more URLs
    ]

    # Configure audio preservation
    audio_config = AudioPreservationConfig(
        preserve_audio=True,  # Keep audio files
        staging_location=Path.home() / "podcast_audio_cache",  # Custom location
        max_disk_usage_gb=200.0,  # Max 200GB for audio files
        cleanup_after_days=30,  # Auto-cleanup after 30 days
        compression_enabled=True,  # Compress to save space
    )

    # Progress callback
    def progress_callback(
        stage: str, completed: int, total: int, stats: dict[str, Any]
    ):
        print(f"{stage}: {completed}/{total} ({stats})")

    # Process with audio preservation
    result = await process_with_audio_preservation(
        urls=urls,
        audio_config=audio_config,
        progress_callback=progress_callback,
        resume_from_existing=True,  # Resume from existing audio files
    )

    print(f"Processing completed: {result['success']}")
    print(f"Audio preservation: {result['audio_preservation']}")


async def example_resume_without_redownload():
    """Example of resuming processing without re-downloading audio"""

    # Same URLs as before
    urls = [
        "https://www.youtube.com/watch?v=example1",
        "https://www.youtube.com/watch?v=example2",
        # ... 5000 more URLs
    ]

    # Create coordinator
    coordinator = ConnectedProcessingCoordinator()

    # First run: Download all audio files
    print("First run: Downloading audio files...")
    result1 = await coordinator.process_with_audio_preservation(
        urls, resume_from_existing=False  # Start fresh
    )

    print(f"Downloaded {result1['audio_preservation']['preserved_files']} audio files")

    # Second run: Resume processing without re-downloading
    print("Second run: Resuming from existing audio files...")
    result2 = await coordinator.process_with_audio_preservation(
        urls, resume_from_existing=True  # Resume from existing audio
    )

    print(f"Resumed processing: {result2['stats']['completed_jobs']} jobs completed")
    print(
        f"No re-downloads needed: {result2['audio_preservation']['preserved_files']} files preserved"
    )


async def example_disk_space_management():
    """Example of intelligent disk space management"""

    coordinator = ConnectedProcessingCoordinator()

    # Check current storage usage
    storage_info = coordinator.get_audio_storage_info()
    print(f"Current audio storage:")
    print(f"  Location: {storage_info['staging_location']}")
    print(f"  Total size: {storage_info['total_audio_size_gb']:.2f} GB")
    print(f"  Free space: {storage_info['free_space_gb']:.2f} GB")
    print(f"  Usage: {storage_info['usage_percentage']:.1f}% of allowed")

    # Cleanup old files if needed
    if storage_info["usage_percentage"] > 80:
        print("High disk usage detected, cleaning up old files...")
        coordinator.cleanup_old_audio(days=14)  # Clean files older than 14 days

        # Check again
        storage_info = coordinator.get_audio_storage_info()
        print(f"After cleanup: {storage_info['total_audio_size_gb']:.2f} GB")


async def example_custom_staging_location():
    """Example of using custom staging location"""

    # Configure custom staging location (e.g., external drive)
    audio_config = AudioPreservationConfig(
        preserve_audio=True,
        staging_location=Path("/Volumes/ExternalDrive/podcast_audio"),  # External drive
        max_disk_usage_gb=500.0,  # 500GB limit
        compression_enabled=True,
    )

    coordinator = ConnectedProcessingCoordinator(audio_config=audio_config)

    # Process with custom staging
    urls = ["https://www.youtube.com/watch?v=example1"]

    result = await coordinator.process_with_audio_preservation(urls)

    print(f"Audio files stored in: {result['audio_preservation']['staging_location']}")


if __name__ == "__main__":
    # Run examples
    asyncio.run(example_basic_usage())
    asyncio.run(example_resume_without_redownload())
    asyncio.run(example_disk_space_management())
    asyncio.run(example_custom_staging_location())
