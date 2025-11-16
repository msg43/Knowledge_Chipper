"""
Granular Testing Mode Control

Replaces the all-or-nothing TESTING_MODE=1 with fine-grained control over what gets bypassed in tests.

Instead of:
    TESTING_MODE=1  # Bypasses everything

Use:
    SKIP_PREFLIGHT=1       # Skip only preflight checks
    SKIP_TRANSCRIPTION=1   # Skip only Whisper transcription
    SKIP_LLM=1            # Skip only LLM calls
    FAST_MODE=1           # Use tiny models instead of production models

This allows tests to be more selective about what they bypass, enabling better production testing.
"""

import os
from typing import Dict, Any


def is_testing_mode() -> bool:
    """
    Check if ANY testing mode is enabled.

    Returns True if any of the testing flags are set.
    Used for backward compatibility.
    """
    return (
        os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE") == "1" or
        skip_preflight() or
        skip_transcription() or
        skip_llm() or
        is_fast_mode()
    )


def skip_preflight() -> bool:
    """
    Skip preflight checks (FFmpeg, yt-dlp validation).

    Use when:
    - Testing non-download/transcode features
    - CI environment without FFmpeg installed
    - Running unit tests that don't need these dependencies

    Don't use when:
    - Testing actual download or transcription workflows
    - Running integration tests
    - Testing app startup sequence
    """
    return os.environ.get("SKIP_PREFLIGHT") == "1"


def skip_transcription() -> bool:
    """
    Skip actual Whisper transcription (use mock or empty result).

    Use when:
    - Testing non-transcription features
    - Testing data flow without slow Whisper processing
    - Running quick unit tests

    Don't use when:
    - Testing AudioProcessor
    - Testing full pipeline workflows
    - Verifying actual transcription output
    """
    return os.environ.get("SKIP_TRANSCRIPTION") == "1"


def skip_llm() -> bool:
    """
    Skip actual LLM calls (Ollama, OpenAI, etc.).

    Use when:
    - Testing without Ollama running
    - Testing non-LLM features
    - Running quick tests

    Don't use when:
    - Testing claim extraction
    - Testing System2 orchestrator
    - Verifying LLM integration
    """
    return os.environ.get("SKIP_LLM") == "1"


def is_fast_mode() -> bool:
    """
    Use tiny/small models instead of production models.

    When enabled:
    - Whisper uses 'tiny' model instead of 'base'/'small'
    - Ollama uses smaller models if available
    - Reduces test runtime significantly

    Use when:
    - Running integration tests quickly
    - Testing workflow without caring about quality

    Don't use when:
    - Testing actual output quality
    - Benchmarking performance
    """
    return os.environ.get("FAST_MODE") == "1"


def is_production_mode() -> bool:
    """
    Check if tests are running in full production mode (no bypasses).

    Returns True only if NONE of the testing flags are set.
    This means real preflight, real transcription, real LLM, production models.
    """
    return not is_testing_mode()


def get_whisper_model() -> str:
    """
    Get appropriate Whisper model based on testing mode.

    Returns:
        'tiny' in FAST_MODE
        'base' in production mode
    """
    if is_fast_mode():
        return 'tiny'
    return 'base'


def get_testing_config() -> Dict[str, Any]:
    """
    Get current testing configuration.

    Returns dict with all testing flags and their values.
    Useful for debugging and logging.
    """
    return {
        'testing_mode': is_testing_mode(),
        'production_mode': is_production_mode(),
        'skip_preflight': skip_preflight(),
        'skip_transcription': skip_transcription(),
        'skip_llm': skip_llm(),
        'fast_mode': is_fast_mode(),
        'whisper_model': get_whisper_model(),
    }


def ensure_production_mode():
    """
    Remove all testing mode environment variables.

    Call this at the start of production tests to ensure they run in true production mode.
    """
    testing_vars = [
        'KNOWLEDGE_CHIPPER_TESTING_MODE',
        'SKIP_PREFLIGHT',
        'SKIP_TRANSCRIPTION',
        'SKIP_LLM',
        'FAST_MODE',
    ]

    for var in testing_vars:
        os.environ.pop(var, None)


# Backward compatibility
def should_skip_preflight() -> bool:
    """Legacy alias for skip_preflight()."""
    return skip_preflight() or os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE") == "1"


def should_skip_heavy_processing() -> bool:
    """
    Check if heavy processing (transcription, LLM) should be skipped.

    Returns True if either skip_transcription or skip_llm is enabled.
    """
    return skip_transcription() or skip_llm() or os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE") == "1"
