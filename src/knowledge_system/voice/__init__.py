"""
Voice Processing Module

REMOVED in v4.0.0: Voice fingerprinting and speaker verification have been removed
in favor of claims-first architecture. Speaker attribution is now handled by 
LazySpeakerAttributor using LLM-based context analysis rather than acoustic fingerprinting.

For speaker attribution, use:
    from knowledge_system.processors.claims_first import LazySpeakerAttributor
"""

# REMOVED in v4.0.0: All voice processing modules deleted
# - voice_fingerprinting.py
# - speaker_verification_service.py
# - accuracy_testing.py

__all__ = []
