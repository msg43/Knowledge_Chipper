"""
Warning suppression utilities for Knowledge_Chipper.

This module provides centralized warning management for common deprecation warnings
from ML/audio libraries used in the system.
"""

import warnings


def suppress_ml_library_warnings() -> None:
    """
    Suppress common deprecation warnings from ML/audio libraries.

    This function suppresses warnings from:
    - TorchAudio backend deprecations (transitioning to TorchCodec)
    - PyAnnote Audio internal warnings about std() degrees of freedom
    - Other PyTorch/audio processing library deprecations

    These warnings are informational only and don't affect functionality.
    They come from library-internal code that users cannot fix directly.
    """
    # TorchAudio backend deprecation warnings
    warnings.filterwarnings(
        "ignore", category=UserWarning, module="torchaudio._backend.utils"
    )
    warnings.filterwarnings(
        "ignore", category=UserWarning, module="torchaudio._backend.soundfile_backend"
    )

    # PyAnnote Audio internal warnings
    warnings.filterwarnings(
        "ignore", category=UserWarning, module="pyannote.audio.models.blocks.pooling"
    )
    warnings.filterwarnings(
        "ignore", category=UserWarning, module="pyannote.audio.core.io"
    )

    # PyAnnote Database SyntaxWarnings (invalid escape sequences in their code)
    warnings.filterwarnings(
        "ignore", category=SyntaxWarning, module="pyannote.database.util"
    )
    warnings.filterwarnings(
        "ignore", category=SyntaxWarning, module="pyannote.database.loader"
    )

    # Message-based filters for specific warning content
    warnings.filterwarnings(
        "ignore", message=".*load_with_torchcodec.*", category=UserWarning
    )
    warnings.filterwarnings(
        "ignore", message=".*torchaudio.*torchcodec.*", category=UserWarning
    )
    warnings.filterwarnings(
        "ignore", message=".*std\\(\\): degrees of freedom.*", category=UserWarning
    )
    warnings.filterwarnings(
        "ignore", message=".*AudioMetaData has been deprecated.*", category=UserWarning
    )
    warnings.filterwarnings(
        "ignore", message=".*info has been deprecated.*", category=UserWarning
    )

    # Additional PyTorch warnings that may appear
    warnings.filterwarnings(
        "ignore", message=".*backend is deprecated.*", category=UserWarning
    )
    warnings.filterwarnings(
        "ignore", message=".*correction should be strictly less.*", category=UserWarning
    )


def restore_ml_library_warnings() -> None:
    """
    Restore ML library warnings by resetting the warnings filter for affected modules.

    This function can be used to re-enable warnings for debugging purposes.
    """
    # Reset warnings filters for the modules we suppressed
    modules_to_reset = [
        "torchaudio._backend.utils",
        "torchaudio._backend.soundfile_backend",
        "pyannote.audio.models.blocks.pooling",
        "pyannote.audio.core.io",
    ]

    # Remove existing filters for these modules
    for entry in warnings.filters[:]:
        if hasattr(entry, "module") and entry.module in modules_to_reset:
            warnings.filters.remove(entry)


# Auto-apply suppressions when this module is imported
suppress_ml_library_warnings()
