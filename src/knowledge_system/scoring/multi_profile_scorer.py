"""
Multi-Profile Scoring Functions

Key innovation: LLM evaluates dimensions ONCE, then pure arithmetic
calculates importance scores for unlimited profiles at zero marginal cost.
"""

from typing import Dict, List, Tuple
from .profiles import UserProfile, STANDARD_PROFILES


def score_for_profile(
    dimensions: Dict[str, float],
    profile: UserProfile
) -> float:
    """
    Calculate importance score for a specific profile.

    This is pure arithmetic - no LLM calls!

    Args:
        dimensions: Claim's dimension scores (from LLM)
        profile: User profile with dimension weights

    Returns:
        Importance score (0-10 scale)

    Example:
        >>> dimensions = {"epistemic_value": 9, "actionability": 6, ...}
        >>> profile = STANDARD_PROFILES["scientist"]
        >>> score_for_profile(dimensions, profile)
        8.4  # 9×0.50 + 8×0.30 + 8×0.15 + 6×0.05 = 8.4
    """
    score = 0.0
    for dimension, weight in profile.weights.items():
        dimension_score = dimensions.get(dimension, 0.0)
        score += weight * dimension_score

    return round(score, 2)


def score_all_profiles(
    dimensions: Dict[str, float],
    profiles: Dict[str, UserProfile] = None
) -> Dict[str, float]:
    """
    Score claim across all profiles.

    Args:
        dimensions: Claim's dimension scores
        profiles: Profiles to score against (default: STANDARD_PROFILES)

    Returns:
        Dictionary mapping profile_name -> score

    Example:
        >>> dimensions = {"epistemic_value": 9, ...}
        >>> scores = score_all_profiles(dimensions)
        >>> scores
        {"scientist": 8.4, "investor": 7.1, "philosopher": 8.2, ...}
    """
    if profiles is None:
        profiles = STANDARD_PROFILES

    scores = {}
    for profile_name, profile in profiles.items():
        scores[profile_name] = score_for_profile(dimensions, profile)

    return scores


def get_importance_max(
    dimensions: Dict[str, float],
    profiles: Dict[str, UserProfile] = None
) -> Tuple[float, str, Dict[str, float]]:
    """
    Get importance using max-scoring approach.

    Returns the HIGHEST score across all profiles.
    Rationale: "Is this A-tier for ANYONE?"

    Args:
        dimensions: Claim's dimension scores
        profiles: Profiles to score against

    Returns:
        (max_score, best_profile_name, all_scores)

    Example:
        >>> dimensions = {"epistemic_value": 9, "actionability": 6, ...}
        >>> importance, best_profile, all_scores = get_importance_max(dimensions)
        >>> importance
        8.4
        >>> best_profile
        "scientist"
    """
    all_scores = score_all_profiles(dimensions, profiles)

    best_profile = max(all_scores.items(), key=lambda x: x[1])
    max_score = best_profile[1]
    best_profile_name = best_profile[0]

    return max_score, best_profile_name, all_scores


def get_importance_top_k(
    dimensions: Dict[str, float],
    k: int = 2,
    profiles: Dict[str, UserProfile] = None
) -> Tuple[float, List[str], Dict[str, float]]:
    """
    Get importance using top-k averaging approach.

    Returns average of top k profile scores.
    More selective than pure max-scoring.
    Rationale: "Is this A-tier for at least K profiles?"

    Args:
        dimensions: Claim's dimension scores
        k: Number of top profiles to average
        profiles: Profiles to score against

    Returns:
        (top_k_avg, top_k_profiles, all_scores)

    Example:
        >>> dimensions = {"epistemic_value": 9, ...}
        >>> importance, top_profiles, all_scores = get_importance_top_k(dimensions, k=2)
        >>> importance
        8.3  # avg(8.4, 8.2) = 8.3
        >>> top_profiles
        ["scientist", "philosopher"]
    """
    all_scores = score_all_profiles(dimensions, profiles)

    # Sort profiles by score (descending)
    sorted_profiles = sorted(all_scores.items(), key=lambda x: x[1], reverse=True)

    # Take top k
    top_k = sorted_profiles[:k]
    top_k_avg = sum(score for _, score in top_k) / k
    top_k_names = [name for name, _ in top_k]

    return round(top_k_avg, 2), top_k_names, all_scores


def get_importance_percentile(
    dimensions: Dict[str, float],
    percentile: float = 100.0,
    profiles: Dict[str, UserProfile] = None
) -> Tuple[float, Dict[str, float]]:
    """
    Get importance using percentile-based approach.

    Allows tuning from max (p=100) to median (p=50) to min (p=0).

    Args:
        dimensions: Claim's dimension scores
        percentile: Percentile to use (0-100, where 100 = max, 50 = median)
        profiles: Profiles to score against

    Returns:
        (percentile_score, all_scores)

    Example:
        >>> dimensions = {"epistemic_value": 9, ...}
        >>> importance, all_scores = get_importance_percentile(dimensions, percentile=90)
        >>> importance
        8.2  # 90th percentile score
    """
    all_scores = score_all_profiles(dimensions, profiles)

    # Sort scores
    sorted_scores = sorted(all_scores.values(), reverse=True)

    # Calculate index for percentile
    if percentile >= 100.0:
        index = 0  # max
    elif percentile <= 0.0:
        index = len(sorted_scores) - 1  # min
    else:
        # Linear interpolation
        index = int((100.0 - percentile) / 100.0 * (len(sorted_scores) - 1))

    percentile_score = sorted_scores[index]

    return round(percentile_score, 2), all_scores


def get_tier(importance: float) -> str:
    """
    Convert importance score to tier.

    Args:
        importance: Importance score (0-10)

    Returns:
        Tier: "A", "B", "C", or "D"

    Example:
        >>> get_tier(8.4)
        "A"
        >>> get_tier(6.8)
        "B"
        >>> get_tier(5.2)
        "C"
        >>> get_tier(3.5)
        "D"
    """
    if importance >= 8.0:
        return "A"
    elif importance >= 6.5:
        return "B"
    elif importance >= 5.0:
        return "C"
    else:
        return "D"


def validate_dimensions(dimensions: Dict[str, float]) -> Tuple[bool, List[str]]:
    """
    Validate that dimensions dict has required fields and valid ranges.

    Args:
        dimensions: Dimension scores dict

    Returns:
        (is_valid, list_of_errors)

    Example:
        >>> validate_dimensions({"epistemic_value": 9, ...})
        (True, [])
        >>> validate_dimensions({"epistemic_value": 11})
        (False, ["epistemic_value score 11.0 out of range [0, 10]", ...])
    """
    required_dimensions = [
        "epistemic_value",
        "actionability",
        "novelty",
        "verifiability",
        "understandability"
    ]

    errors = []

    # Check required dimensions exist
    for dim in required_dimensions:
        if dim not in dimensions:
            errors.append(f"Missing required dimension: {dim}")

    # Check ranges
    for dim, score in dimensions.items():
        if not isinstance(score, (int, float)):
            errors.append(f"{dim} score must be numeric, got {type(score)}")
        elif not (0 <= score <= 10):
            errors.append(f"{dim} score {score} out of range [0, 10]")

    is_valid = len(errors) == 0
    return is_valid, errors


def calculate_composite_importance(
    dimensions: Dict[str, float],
    method: str = "max",
    k: int = 2,
    percentile: float = 100.0,
    profiles: Dict[str, UserProfile] = None
) -> Tuple[float, str, Dict[str, float]]:
    """
    Calculate composite importance score using specified method.

    Unified interface for all scoring methods.

    Args:
        dimensions: Claim's dimension scores
        method: Scoring method ("max", "top_k", "percentile")
        k: Number of profiles for top_k method
        percentile: Percentile for percentile method
        profiles: Profiles to score against

    Returns:
        (importance, metadata, all_scores)
        where metadata varies by method:
        - max: best_profile_name
        - top_k: comma-separated top k profile names
        - percentile: f"p{percentile}"

    Example:
        >>> importance, metadata, scores = calculate_composite_importance(
        ...     dimensions, method="max"
        ... )
        >>> importance
        8.4
        >>> metadata
        "scientist"
    """
    # Validate dimensions
    is_valid, errors = validate_dimensions(dimensions)
    if not is_valid:
        raise ValueError(f"Invalid dimensions: {'; '.join(errors)}")

    if method == "max":
        importance, best_profile, all_scores = get_importance_max(dimensions, profiles)
        metadata = best_profile

    elif method == "top_k":
        importance, top_profiles, all_scores = get_importance_top_k(dimensions, k, profiles)
        metadata = ", ".join(top_profiles)

    elif method == "percentile":
        importance, all_scores = get_importance_percentile(dimensions, percentile, profiles)
        metadata = f"p{percentile}"

    else:
        raise ValueError(f"Unknown scoring method: {method}. Use 'max', 'top_k', or 'percentile'")

    return importance, metadata, all_scores
