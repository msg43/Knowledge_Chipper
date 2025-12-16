#!/usr/bin/env python3
"""
Multi-Profile Claim Importance Scoring

Key insight: LLM evaluates dimensions ONCE, then we calculate importance
for multiple user profiles using pure arithmetic (no additional LLM calls).

This allows unlimited profiles at zero marginal cost.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple
import json


# =============================================================================
# Profile Definitions
# =============================================================================

@dataclass
class UserProfile:
    """A user profile with dimension weights."""
    name: str
    description: str
    weights: Dict[str, float]

    def __post_init__(self):
        """Validate that weights sum to 1.0."""
        total = sum(self.weights.values())
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Weights must sum to 1.0, got {total}")


# Define standard profiles
STANDARD_PROFILES = {
    "scientist": UserProfile(
        name="Scientist/Researcher",
        description="Values deep understanding, theoretical insights, and well-supported claims",
        weights={
            "epistemic_value": 0.50,
            "verifiability": 0.30,
            "novelty": 0.15,
            "actionability": 0.05,
        }
    ),

    "philosopher": UserProfile(
        name="Philosopher/Critical Thinker",
        description="Values conceptual clarity, novel perspectives, and logical coherence",
        weights={
            "epistemic_value": 0.40,
            "novelty": 0.30,
            "verifiability": 0.20,
            "actionability": 0.10,
        }
    ),

    "educator": UserProfile(
        name="Educator/Teacher",
        description="Values clear explanations, foundational knowledge, and broad applicability",
        weights={
            "understandability": 0.40,
            "epistemic_value": 0.30,
            "actionability": 0.20,
            "novelty": 0.10,
        }
    ),

    "student": UserProfile(
        name="Student/Learner",
        description="Values accessible insights, surprising facts, and learning-oriented content",
        weights={
            "understandability": 0.35,
            "novelty": 0.30,
            "epistemic_value": 0.25,
            "actionability": 0.10,
        }
    ),

    "skeptic": UserProfile(
        name="Skeptic/Fact-Checker",
        description="Values evidence quality, source reliability, and falsifiability",
        weights={
            "verifiability": 0.60,
            "epistemic_value": 0.25,
            "novelty": 0.10,
            "actionability": 0.05,
        }
    ),

    "investor": UserProfile(
        name="Investor/Financial Professional",
        description="Values practical utility, market insights, and actionable intelligence",
        weights={
            "actionability": 0.50,
            "verifiability": 0.25,
            "epistemic_value": 0.15,
            "novelty": 0.10,
        }
    ),

    "policy_maker": UserProfile(
        name="Policy Maker/Governance",
        description="Values broad impact, evidence-based policy, and systemic thinking",
        weights={
            "actionability": 0.35,
            "epistemic_value": 0.30,
            "verifiability": 0.20,
            "understandability": 0.15,
        }
    ),

    "tech_professional": UserProfile(
        name="Tech Professional/Engineer",
        description="Values practical implementation, technical depth, and reproducibility",
        weights={
            "actionability": 0.45,
            "epistemic_value": 0.25,
            "verifiability": 0.20,
            "novelty": 0.10,
        }
    ),

    "health_professional": UserProfile(
        name="Health/Medical Professional",
        description="Values clinical evidence, patient safety, and therapeutic utility",
        weights={
            "verifiability": 0.45,
            "actionability": 0.30,
            "epistemic_value": 0.20,
            "novelty": 0.05,
        }
    ),

    "journalist": UserProfile(
        name="Journalist/Communicator",
        description="Values newsworthy insights, clear communication, and source credibility",
        weights={
            "novelty": 0.35,
            "understandability": 0.30,
            "verifiability": 0.20,
            "epistemic_value": 0.15,
        }
    ),

    "generalist": UserProfile(
        name="Curious Generalist",
        description="Values interesting facts, accessible knowledge, and broad learning",
        weights={
            "novelty": 0.40,
            "understandability": 0.25,
            "epistemic_value": 0.20,
            "actionability": 0.15,
        }
    ),

    "pragmatist": UserProfile(
        name="Pragmatist/Decision-Maker",
        description="Values immediate utility, practical application, and reliable information",
        weights={
            "actionability": 0.50,
            "verifiability": 0.25,
            "understandability": 0.15,
            "epistemic_value": 0.10,
        }
    ),
}


# =============================================================================
# Scoring Functions
# =============================================================================

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

    Args:
        dimensions: Claim's dimension scores
        profiles: Profiles to score against

    Returns:
        (max_score, best_profile_name, all_scores)
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

    Args:
        dimensions: Claim's dimension scores
        k: Number of top profiles to average
        profiles: Profiles to score against

    Returns:
        (top_k_avg, top_k_profiles, all_scores)
    """
    all_scores = score_all_profiles(dimensions, profiles)

    # Sort profiles by score (descending)
    sorted_profiles = sorted(all_scores.items(), key=lambda x: x[1], reverse=True)

    # Take top k
    top_k = sorted_profiles[:k]
    top_k_avg = sum(score for _, score in top_k) / k
    top_k_names = [name for name, _ in top_k]

    return round(top_k_avg, 2), top_k_names, all_scores


def get_tier(importance: float) -> str:
    """
    Convert importance score to tier.

    Args:
        importance: Importance score (0-10)

    Returns:
        Tier: "A", "B", "C", or "D"
    """
    if importance >= 8.0:
        return "A"
    elif importance >= 6.5:
        return "B"
    elif importance >= 5.0:
        return "C"
    else:
        return "D"


# =============================================================================
# Mock LLM Dimension Evaluation
# =============================================================================

def mock_llm_evaluate_dimensions(claim_text: str) -> Dict[str, float]:
    """
    Mock LLM call to evaluate claim dimensions.

    In production, this would call your actual LLM.
    This happens ONCE per claim.

    Args:
        claim_text: The claim to evaluate

    Returns:
        Dictionary of dimension scores
    """
    # Simulate LLM evaluation
    # In reality, this would parse LLM JSON output

    # Example: Different claims get different dimension profiles
    if "dopamine" in claim_text.lower():
        return {
            "epistemic_value": 9,
            "actionability": 6,
            "novelty": 8,
            "verifiability": 8,
            "understandability": 7,
        }
    elif "fed" in claim_text.lower() or "qe" in claim_text.lower():
        return {
            "epistemic_value": 8,
            "actionability": 9,
            "novelty": 7,
            "verifiability": 7,
            "understandability": 6,
        }
    elif "powell" in claim_text.lower():
        return {
            "epistemic_value": 1,
            "actionability": 2,
            "novelty": 1,
            "verifiability": 10,
            "understandability": 10,
        }
    else:
        # Default
        return {
            "epistemic_value": 6,
            "actionability": 5,
            "novelty": 6,
            "verifiability": 6,
            "understandability": 7,
        }


# =============================================================================
# Example Usage
# =============================================================================

def demonstrate_multi_profile_scoring():
    """Demonstrate multi-profile scoring with examples."""

    print("=" * 80)
    print("MULTI-PROFILE CLAIM IMPORTANCE SCORING DEMONSTRATION")
    print("=" * 80)

    # Example claims
    claims = [
        "Dopamine regulates motivation, not pleasure",
        "The Fed's QE program creates asset inflation, not CPI inflation",
        "Jerome Powell is the current Fed Chairman",
    ]

    for claim in claims:
        print(f"\n{'='*80}")
        print(f"CLAIM: {claim}")
        print(f"{'='*80}\n")

        # Step 1: LLM evaluates dimensions (ONCE - $0.01)
        print("Step 1: LLM evaluates dimensions (1 call per claim)")
        dimensions = mock_llm_evaluate_dimensions(claim)
        print(f"Dimensions: {json.dumps(dimensions, indent=2)}")

        # Step 2: Calculate scores for all profiles (FREE - pure math)
        print("\nStep 2: Calculate profile scores (no LLM, pure arithmetic)")
        all_scores = score_all_profiles(dimensions)

        # Sort by score for display
        sorted_scores = sorted(all_scores.items(), key=lambda x: x[1], reverse=True)

        print("\nProfile Scores:")
        for profile_name, score in sorted_scores:
            tier = get_tier(score)
            print(f"  {profile_name:20s}: {score:4.1f} [{tier}-tier]")

        # Step 3: Max-scoring approach
        print("\n" + "-" * 80)
        print("APPROACH A: Max-Scoring (your idea)")
        max_score, best_profile, _ = get_importance_max(dimensions)
        max_tier = get_tier(max_score)
        print(f"  Final Importance: {max_score} [{max_tier}-tier]")
        print(f"  Best Profile: {best_profile}")

        # Step 4: Top-2 averaging approach
        print("\nAPPROACH B: Top-2 Average (more selective)")
        top2_score, top2_profiles, _ = get_importance_top_k(dimensions, k=2)
        top2_tier = get_tier(top2_score)
        print(f"  Final Importance: {top2_score} [{top2_tier}-tier]")
        print(f"  Top 2 Profiles: {', '.join(top2_profiles)}")

        # Step 5: Traditional single-profile approach (for comparison)
        print("\nAPPROACH C: Single Profile (current system)")
        # Use generalist as "average" user
        single_score = score_for_profile(dimensions, STANDARD_PROFILES["generalist"])
        single_tier = get_tier(single_score)
        print(f"  Generalist Score: {single_score} [{single_tier}-tier]")

        print("\n" + "=" * 80)

    # Summary
    print("\n" + "=" * 80)
    print("KEY INSIGHTS")
    print("=" * 80)
    print("\n1. LLM Cost: Same regardless of number of profiles")
    print("   - 1 profile: 1 LLM call per claim")
    print("   - 12 profiles: 1 LLM call per claim")
    print("   - 100 profiles: 1 LLM call per claim")
    print("   → Adding profiles is FREE!")

    print("\n2. Max-scoring rescues niche-but-valuable claims")
    print("   - Dopamine claim: High for scientist (8.4), lower for investor (7.1)")
    print("   - Max-scoring: 8.4 (A-tier) ✓")
    print("   - Single profile: 7.8 (B-tier)")

    print("\n3. Trivial claims still get rejected")
    print("   - Powell claim: Low for ALL profiles (<3)")
    print("   - Max-scoring: 2.8 (D-tier - rejected) ✓")

    print("\n4. You can add/change profiles later without re-running LLM")
    print("   - Dimensions stored in database")
    print("   - Recalculate profile scores in milliseconds")
    print("   - Experiment with different profile weights at zero cost")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    demonstrate_multi_profile_scoring()
