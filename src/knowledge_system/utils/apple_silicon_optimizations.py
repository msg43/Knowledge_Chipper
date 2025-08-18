"""
Apple Silicon optimization utilities for Knowledge Chipper.

This module provides optimized configurations for transcription and diarization
on Apple Silicon hardware, taking advantage of unified memory architecture
and Neural Engine capabilities.
"""

import platform
from pathlib import Path
from typing import Any, Dict, Tuple

import psutil

from knowledge_system.logger import get_logger

logger = get_logger(__name__)


def is_apple_silicon() -> bool:
    """Check if running on Apple Silicon (M1/M2/M3 series)."""
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def get_system_memory_gb() -> float:
    """Get total system memory in GB."""
    return psutil.virtual_memory().total / (1024**3)


def get_cpu_count() -> int:
    """Get the number of CPU cores."""
    return psutil.cpu_count(logical=False) or 4


def get_apple_silicon_whisper_config(
    model_size: str = "base", file_duration_minutes: float = 60.0
) -> dict[str, Any]:
    """
    Get optimized whisper.cpp configuration for Apple Silicon.

    Args:
        model_size: Whisper model size (tiny, base, small, medium, large)
        file_duration_minutes: Estimated duration of audio file in minutes

    Returns:
        Dictionary with optimized parameters for whisper.cpp
    """
    if not is_apple_silicon():
        return {}

    memory_gb = get_system_memory_gb()
    cpu_cores = get_cpu_count()

    # Base configuration optimized for Apple Silicon
    config = {
        "use_coreml": True,  # Always use Core ML on Apple Silicon
    }

    # Optimize thread count based on available cores
    # Apple Silicon benefits from higher thread counts due to unified memory
    if cpu_cores >= 10:  # M3 Pro/Ultra
        config["omp_threads"] = min(8, cpu_cores // 2)
    elif cpu_cores >= 8:  # M2 Pro/M3
        config["omp_threads"] = 6
    else:  # M1/M2 base
        config["omp_threads"] = 4

    # Optimize batch size based on model and memory
    model_memory_requirements = {
        "tiny": 0.2,  # ~200MB
        "base": 0.4,  # ~400MB
        "small": 1.0,  # ~1GB
        "medium": 2.5,  # ~2.5GB
        "large": 4.0,  # ~4GB
    }

    model_memory = model_memory_requirements.get(model_size, 1.0)

    # Calculate batch size based on available memory and file duration
    # Longer files need smaller batch sizes to avoid memory pressure
    # Note: whisper.cpp beam size is limited to max 8, so cap batch sizes accordingly
    if memory_gb >= 32:  # High-end systems (M3 Ultra, etc.)
        if file_duration_minutes <= 30:
            config[
                "batch_size"
            ] = 8  # Reduced from 32 to stay within whisper.cpp limits
        elif file_duration_minutes <= 60:
            config[
                "batch_size"
            ] = 8  # Reduced from 24 to stay within whisper.cpp limits
        else:
            config[
                "batch_size"
            ] = 8  # Reduced from 16 to stay within whisper.cpp limits
    elif memory_gb >= 16:  # Mid-range systems (M2 Pro, M3)
        if file_duration_minutes <= 30:
            config[
                "batch_size"
            ] = 8  # Reduced from 24 to stay within whisper.cpp limits
        elif file_duration_minutes <= 60:
            config[
                "batch_size"
            ] = 8  # Reduced from 16 to stay within whisper.cpp limits
        else:
            config[
                "batch_size"
            ] = 8  # Reduced from 12 to stay within whisper.cpp limits
    else:  # Base systems (M1, M2 base)
        if file_duration_minutes <= 30:
            config[
                "batch_size"
            ] = 8  # Reduced from 16 to stay within whisper.cpp limits
        elif file_duration_minutes <= 60:
            config[
                "batch_size"
            ] = 8  # Reduced from 12 to stay within whisper.cpp limits
        else:
            config["batch_size"] = 8  # Already compliant

    # Adjust for model size (larger models need smaller batches)
    if model_size in ["medium", "large"]:
        config["batch_size"] = max(8, config["batch_size"] // 2)

    logger.info(
        f"Apple Silicon optimization: {cpu_cores} cores, {memory_gb:.1f}GB RAM, "
        f"threads={config['omp_threads']}, batch_size={config['batch_size']}"
    )

    return config


def get_apple_silicon_diarization_config(
    file_duration_minutes: float = 60.0,
) -> dict[str, Any]:
    """
    Get optimized diarization configuration for Apple Silicon.

    Args:
        file_duration_minutes: Estimated duration of audio file in minutes

    Returns:
        Dictionary with optimized parameters for pyannote.audio
    """
    if not is_apple_silicon():
        return {}

    memory_gb = get_system_memory_gb()

    config = {
        "device": "mps",  # Use Metal Performance Shaders on Apple Silicon
    }

    # Optimize chunking for long files on Apple Silicon
    # Unified memory allows larger chunks, but we need to be careful with very long files
    if memory_gb >= 32:  # High-end systems
        if file_duration_minutes <= 60:
            config["chunk_length"] = 30.0  # 30-second chunks
        else:
            config["chunk_length"] = 20.0  # Smaller chunks for very long files
    elif memory_gb >= 16:  # Mid-range systems
        if file_duration_minutes <= 60:
            config["chunk_length"] = 20.0
        else:
            config["chunk_length"] = 15.0
    else:  # Base systems
        config["chunk_length"] = 15.0  # Conservative chunking

    logger.info(
        f"Apple Silicon diarization optimization: {memory_gb:.1f}GB RAM, "
        f"chunk_length={config['chunk_length']}s"
    )

    return config


def optimize_transcription_for_apple_silicon(
    model_size: str,
    audio_duration_seconds: float = 3600.0,
    enable_diarization: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Get comprehensive optimization settings for Apple Silicon transcription.

    Args:
        model_size: Whisper model size
        audio_duration_seconds: Duration of audio in seconds
        enable_diarization: Whether diarization is enabled

    Returns:
        Tuple of (whisper_config, diarization_config)
    """
    duration_minutes = audio_duration_seconds / 60.0

    whisper_config = get_apple_silicon_whisper_config(model_size, duration_minutes)
    diarization_config = (
        get_apple_silicon_diarization_config(duration_minutes)
        if enable_diarization
        else {}
    )

    # Cross-optimize: if both transcription and diarization are running,
    # reduce memory pressure by being more conservative
    if enable_diarization and whisper_config and diarization_config:
        memory_gb = get_system_memory_gb()

        # Reduce batch sizes when both are running to prevent memory pressure
        if memory_gb < 16:
            whisper_config["batch_size"] = max(
                8, whisper_config.get("batch_size", 16) // 2
            )
            diarization_config["chunk_length"] = min(
                10.0, diarization_config.get("chunk_length", 15.0)
            )

        logger.info(
            "Applied cross-optimization for concurrent transcription and diarization"
        )

    return whisper_config, diarization_config


def get_memory_pressure_threshold() -> float:
    """
    Get memory pressure threshold percentage for Apple Silicon.

    Returns:
        Memory usage percentage at which to start applying memory pressure mitigations
    """
    memory_gb = get_system_memory_gb()

    # Higher-memory systems can use more before applying pressure mitigations
    if memory_gb >= 32:
        return 0.8  # 80% usage threshold
    elif memory_gb >= 16:
        return 0.75  # 75% usage threshold
    else:
        return 0.7  # 70% usage threshold for base systems


def check_memory_pressure() -> tuple[bool, float]:
    """
    Check if system is under memory pressure.

    Returns:
        Tuple of (is_under_pressure, current_usage_percentage)
    """
    memory = psutil.virtual_memory()
    usage_percent = memory.percent / 100.0
    threshold = get_memory_pressure_threshold()

    return usage_percent > threshold, usage_percent


def apply_memory_pressure_mitigations() -> dict[str, Any]:
    """
    Get reduced settings to apply when under memory pressure.

    Returns:
        Dictionary with conservative settings
    """
    logger.warning("System under memory pressure, applying conservative settings")

    return {
        "whisper": {
            "batch_size": 8,
            "omp_threads": 2,
        },
        "diarization": {
            "chunk_length": 10.0,
        },
    }


# Example usage and testing functions
def test_apple_silicon_optimizations():
    """Test function to verify optimizations work correctly."""
    if not is_apple_silicon():
        print("❌ Not running on Apple Silicon")
        return

    print("🍎 Apple Silicon Optimizations Test")
    print("=" * 40)

    memory_gb = get_system_memory_gb()
    cpu_cores = get_cpu_count()

    print(f"System: {memory_gb:.1f}GB RAM, {cpu_cores} CPU cores")

    # Test different scenarios
    test_cases = [
        ("base", 30.0, False),  # 30-minute file, no diarization
        ("medium", 60.0, True),  # 1-hour file with diarization
        ("large", 120.0, True),  # 2-hour file with diarization
    ]

    for model, duration, diarization in test_cases:
        print(f"\nTest: {model} model, {duration}min file, diarization={diarization}")
        whisper_cfg, diar_cfg = optimize_transcription_for_apple_silicon(
            model, duration * 60, diarization
        )
        print(f"  Whisper: {whisper_cfg}")
        if diar_cfg:
            print(f"  Diarization: {diar_cfg}")

    # Test memory pressure
    under_pressure, usage = check_memory_pressure()
    print(f"\nMemory: {usage:.1%} used, under pressure: {under_pressure}")


if __name__ == "__main__":
    test_apple_silicon_optimizations()
