#!/usr/bin/env python3
"""
Audio Staging Location Examples

Clear examples of how to specify where audio files should be staged
to avoid local disk storage issues.
"""

import asyncio
from pathlib import Path

from .connected_processing_coordinator import (
    AudioPreservationConfig,
    ConnectedProcessingCoordinator,
    process_with_audio_preservation,
)


async def example_external_drive():
    """Example: Stage audio files on external drive"""

    # Specify external drive location
    staging_location = Path("/Volumes/MyExternalDrive/podcast_audio")

    audio_config = AudioPreservationConfig(
        preserve_audio=True,
        staging_location=staging_location,  # External drive
        max_disk_usage_gb=500.0,  # 500GB limit
        cleanup_after_days=60,  # Keep for 2 months
        compression_enabled=True,  # Optimize only if beneficial
    )

    urls = ["https://www.youtube.com/watch?v=example1"]

    result = await process_with_audio_preservation(urls=urls, audio_config=audio_config)

    print(f"Audio files staged in: {result['audio_preservation']['staging_location']}")


async def example_network_drive():
    """Example: Stage audio files on network drive"""

    # Specify network drive location (e.g., NAS, shared folder)
    staging_location = Path("/mnt/nas/podcast_processing/audio_cache")

    audio_config = AudioPreservationConfig(
        preserve_audio=True,
        staging_location=staging_location,  # Network drive
        max_disk_usage_gb=1000.0,  # 1TB limit
        cleanup_after_days=90,  # Keep for 3 months
        compression_enabled=False,  # Don't optimize on network storage
    )

    # Process with network staging
    urls = ["https://www.youtube.com/watch?v=example1"]

    result = await process_with_audio_preservation(urls=urls, audio_config=audio_config)


async def example_cloud_storage_mount():
    """Example: Stage audio files on cloud storage mount (e.g., rclone)"""

    # Specify cloud storage mount location
    staging_location = Path("/mnt/google_drive/podcast_audio")

    audio_config = AudioPreservationConfig(
        preserve_audio=True,
        staging_location=staging_location,  # Cloud storage mount
        max_disk_usage_gb=2000.0,  # 2TB limit
        cleanup_after_days=180,  # Keep for 6 months
        compression_enabled=True,  # Compress for cloud storage efficiency
    )

    urls = ["https://www.youtube.com/watch?v=example1"]

    result = await process_with_audio_preservation(urls=urls, audio_config=audio_config)


async def example_multiple_locations():
    """Example: Check multiple potential staging locations"""

    # List of potential staging locations to try
    potential_locations = [
        Path("/Volumes/ExternalDrive/podcast_audio"),  # External drive
        Path("/mnt/nas/podcast_audio"),  # NAS
        Path.home() / "podcast_audio",  # Home directory (fallback)
    ]

    # Find the best location with most free space
    best_location = None
    max_free_space = 0

    for location in potential_locations:
        try:
            if location.parent.exists():
                import shutil

                free_space = shutil.disk_usage(location.parent).free
                if free_space > max_free_space:
                    max_free_space = free_space
                    best_location = location
                print(
                    f"Location: {location} - Free space: {free_space/(1024**3):.1f}GB"
                )
        except (OSError, PermissionError):
            print(f"Location: {location} - Not accessible")
            continue

    if best_location:
        print(f"Selected staging location: {best_location}")

        audio_config = AudioPreservationConfig(
            preserve_audio=True,
            staging_location=best_location,
            max_disk_usage_gb=max_free_space
            / (1024**3)
            * 0.8,  # Use 80% of available space
            cleanup_after_days=30,
            compression_enabled=True,
        )

        # Process with selected location
        urls = ["https://www.youtube.com/watch?v=example1"]

        result = await process_with_audio_preservation(
            urls=urls, audio_config=audio_config
        )
    else:
        print("No suitable staging location found!")


async def example_dynamic_location_selection():
    """Example: Let the system automatically choose the best location"""

    # Don't specify staging_location - let system choose automatically
    audio_config = AudioPreservationConfig(
        preserve_audio=True,
        # staging_location=None,  # System will choose automatically
        max_disk_usage_gb=100.0,  # 100GB limit
        cleanup_after_days=30,
        compression_enabled=True,
    )

    # Create coordinator to see what location was chosen
    coordinator = ConnectedProcessingCoordinator(audio_config=audio_config)

    # Check what location was automatically selected
    storage_info = coordinator.get_audio_storage_info()
    print(
        f"Automatically selected staging location: {storage_info['staging_location']}"
    )
    print(f"Available free space: {storage_info['free_space_gb']:.1f}GB")

    # Process with automatically selected location
    urls = ["https://www.youtube.com/watch?v=example1"]

    result = await coordinator.process_with_audio_preservation(urls)

    print(f"Audio files staged in: {result['audio_preservation']['staging_location']}")


async def example_check_staging_location():
    """Example: Check current staging location and usage"""

    coordinator = ConnectedProcessingCoordinator()

    # Get current storage information
    storage_info = coordinator.get_audio_storage_info()

    print("Current Audio Storage Information:")
    print(f"  Staging Location: {storage_info['staging_location']}")
    print(f"  Total Audio Size: {storage_info['total_audio_size_gb']:.2f} GB")
    print(f"  Free Space: {storage_info['free_space_gb']:.2f} GB")
    print(f"  Max Allowed: {storage_info['max_allowed_gb']:.2f} GB")
    print(f"  Usage: {storage_info['usage_percentage']:.1f}%")
    print(f"  Preserved Files: {storage_info['preserved_files']}")
    print(
        f"  Compression: {'Enabled' if storage_info['compression_enabled'] else 'Disabled'}"
    )

    # Check if cleanup is needed
    if storage_info["usage_percentage"] > 80:
        print("⚠️  High disk usage detected!")
        print("Consider running cleanup or increasing max_disk_usage_gb")

        # Optionally run cleanup
        coordinator.cleanup_old_audio(days=14)

        # Check again
        storage_info = coordinator.get_audio_storage_info()
        print(f"After cleanup: {storage_info['total_audio_size_gb']:.2f} GB")


if __name__ == "__main__":
    # Run examples
    print("=== External Drive Example ===")
    asyncio.run(example_external_drive())

    print("\n=== Network Drive Example ===")
    asyncio.run(example_network_drive())

    print("\n=== Cloud Storage Example ===")
    asyncio.run(example_cloud_storage_mount())

    print("\n=== Multiple Locations Example ===")
    asyncio.run(example_multiple_locations())

    print("\n=== Auto-Selection Example ===")
    asyncio.run(example_dynamic_location_selection())

    print("\n=== Check Current Staging ===")
    asyncio.run(example_check_staging_location())
