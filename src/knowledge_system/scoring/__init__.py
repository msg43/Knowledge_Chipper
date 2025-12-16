"""
Multi-Profile Claim Scoring System

This module provides multi-profile importance scoring for claims.
Key innovation: LLM evaluates dimensions ONCE, then arithmetic calculates
scores for unlimited profiles at zero marginal cost.
"""

from .profiles import UserProfile, STANDARD_PROFILES
from .multi_profile_scorer import (
    score_for_profile,
    score_all_profiles,
    get_importance_max,
    get_importance_top_k,
    get_tier,
)

__all__ = [
    "UserProfile",
    "STANDARD_PROFILES",
    "score_for_profile",
    "score_all_profiles",
    "get_importance_max",
    "get_importance_top_k",
    "get_tier",
]
