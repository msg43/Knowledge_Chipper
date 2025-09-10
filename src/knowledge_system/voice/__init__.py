"""
Voice Processing Module

Advanced voice fingerprinting and speaker verification system for 97% accuracy.
"""

from .speaker_verification_service import (
    SpeakerVerificationService,
    create_speaker_verification_service,
)
from .voice_fingerprinting import (
    AdvancedVoiceEncoder,
    VoiceFeatureExtractor,
    VoiceFingerprintProcessor,
    create_voice_fingerprint_processor,
    load_audio_for_voice_processing,
)

__all__ = [
    "VoiceFeatureExtractor",
    "AdvancedVoiceEncoder",
    "VoiceFingerprintProcessor",
    "SpeakerVerificationService",
    "create_voice_fingerprint_processor",
    "create_speaker_verification_service",
    "load_audio_for_voice_processing",
]
