"""
Unit tests for multi-profile scoring system.
"""

import pytest
from knowledge_system.scoring.multi_profile_scorer import (
    calculate_composite_importance,
    get_importance_max,
    get_importance_percentile,
    get_importance_top_k,
    get_tier,
    score_all_profiles,
    score_for_profile,
    validate_dimensions,
)
from knowledge_system.scoring.profiles import STANDARD_PROFILES


class TestDimensionValidation:
    """Test dimension validation."""

    def test_valid_6_dimensions(self):
        """Test that all 6 required dimensions are validated."""
        dimensions = {
            "epistemic_value": 9,
            "actionability": 6,
            "novelty": 8,
            "verifiability": 8,
            "understandability": 7,
            "temporal_stability": 8,
            "scope": 6,
        }
        is_valid, errors = validate_dimensions(dimensions)
        assert is_valid
        assert len(errors) == 0

    def test_missing_dimension(self):
        """Test that missing dimensions are caught."""
        dimensions = {
            "epistemic_value": 9,
            "actionability": 6,
            "novelty": 8,
            "verifiability": 8,
            "understandability": 7,
            # Missing temporal_stability and scope
        }
        is_valid, errors = validate_dimensions(dimensions)
        assert not is_valid
        assert len(errors) == 2
        assert any("temporal_stability" in err for err in errors)
        assert any("scope" in err for err in errors)

    def test_out_of_range_dimension(self):
        """Test that out-of-range scores are caught."""
        dimensions = {
            "epistemic_value": 11,  # Out of range
            "actionability": 6,
            "novelty": 8,
            "verifiability": 8,
            "understandability": 7,
            "temporal_stability": 8,
            "scope": 6,
        }
        is_valid, errors = validate_dimensions(dimensions)
        assert not is_valid
        assert any("out of range" in err for err in errors)

    def test_negative_dimension(self):
        """Test that negative scores are caught."""
        dimensions = {
            "epistemic_value": -1,  # Negative
            "actionability": 6,
            "novelty": 8,
            "verifiability": 8,
            "understandability": 7,
            "temporal_stability": 8,
            "scope": 6,
        }
        is_valid, errors = validate_dimensions(dimensions)
        assert not is_valid
        assert any("out of range" in err for err in errors)


class TestProfileWeights:
    """Test that profile weights are valid."""

    def test_all_profiles_sum_to_one(self):
        """Test that all profile weights sum to 1.0."""
        for profile_name, profile in STANDARD_PROFILES.items():
            total = sum(profile.weights.values())
            assert abs(total - 1.0) < 0.01, f"{profile_name} weights sum to {total}, not 1.0"

    def test_all_profiles_have_6_dimensions(self):
        """Test that all profiles include all 6 dimensions (or omit with 0 weight)."""
        required_dimensions = {
            "epistemic_value",
            "actionability",
            "novelty",
            "verifiability",
            "understandability",
            "temporal_stability",
            "scope",
        }
        
        for profile_name, profile in STANDARD_PROFILES.items():
            # Profile may omit dimensions (treated as 0 weight)
            # But all mentioned dimensions should be from the required set
            for dim in profile.weights.keys():
                assert dim in required_dimensions, f"{profile_name} has invalid dimension: {dim}"


class TestProfileScoring:
    """Test profile scoring arithmetic."""

    def test_score_for_profile_scientist(self):
        """Test scoring for scientist profile."""
        dimensions = {
            "epistemic_value": 9,
            "actionability": 6,
            "novelty": 8,
            "verifiability": 8,
            "understandability": 7,
            "temporal_stability": 8,
            "scope": 6,
        }
        
        scientist_profile = STANDARD_PROFILES["scientist"]
        score = score_for_profile(dimensions, scientist_profile)
        
        # Manual calculation based on scientist weights:
        # epistemic_value: 0.45, verifiability: 0.28, novelty: 0.13,
        # temporal_stability: 0.08, scope: 0.04, actionability: 0.02
        expected = (9 * 0.45) + (8 * 0.28) + (8 * 0.13) + (8 * 0.08) + (6 * 0.04) + (6 * 0.02)
        expected = round(expected, 2)
        
        assert abs(score - expected) < 0.1, f"Expected {expected}, got {score}"

    def test_score_all_profiles(self):
        """Test scoring across all profiles."""
        dimensions = {
            "epistemic_value": 9,
            "actionability": 6,
            "novelty": 8,
            "verifiability": 8,
            "understandability": 7,
            "temporal_stability": 8,
            "scope": 6,
        }
        
        scores = score_all_profiles(dimensions)
        
        # Should have 12 profiles
        assert len(scores) == 12
        
        # All scores should be in valid range
        for profile_name, score in scores.items():
            assert 0 <= score <= 10, f"{profile_name} score {score} out of range"


class TestMaxScoring:
    """Test max-scoring aggregation."""

    def test_max_scoring_rescues_niche_claims(self):
        """Test that max-scoring promotes niche-but-valuable claims."""
        # High epistemic value, low actionability (niche scientific insight)
        niche_claim = {
            "epistemic_value": 9,
            "actionability": 3,
            "novelty": 8,
            "verifiability": 8,
            "understandability": 6,
            "temporal_stability": 8,
            "scope": 5,
        }
        
        importance, best_profile, all_scores = get_importance_max(niche_claim)
        
        # Should score high for scientist (weights epistemic_value heavily)
        assert importance >= 7.5, f"Expected high importance, got {importance}"
        assert best_profile == "scientist", f"Expected scientist, got {best_profile}"
        assert all_scores["scientist"] >= 7.5

    def test_trivial_claims_still_rejected(self):
        """Test that trivial claims score low for ALL profiles."""
        trivial_claim = {
            "epistemic_value": 2,
            "actionability": 1,
            "novelty": 1,
            "verifiability": 10,
            "understandability": 10,
            "temporal_stability": 4,
            "scope": 2,
        }
        
        importance, best_profile, all_scores = get_importance_max(trivial_claim)
        
        # Even max score should be < 7.0 (C-tier or below)
        # Note: With 6 dimensions, high understandability/actionability can push trivial claims to ~6.5
        assert importance < 7.0, f"Trivial claim scored too high: {importance}"
        
        # All profiles should score < 7.0
        for profile_name, score in all_scores.items():
            assert score < 7.0, f"{profile_name} scored trivial claim too high: {score}"


class TestTemporalStability:
    """Test temporal stability dimension effects."""

    def test_ephemeral_claims_score_lower(self):
        """Test that ephemeral claims score lower than timeless ones."""
        # Ephemeral claim (current event)
        ephemeral = {
            "epistemic_value": 5,
            "actionability": 5,
            "novelty": 5,
            "verifiability": 8,
            "understandability": 8,
            "temporal_stability": 2,  # Ephemeral
            "scope": 5,
        }
        
        # Timeless claim (fundamental principle)
        timeless = {
            "epistemic_value": 5,
            "actionability": 5,
            "novelty": 5,
            "verifiability": 8,
            "understandability": 8,
            "temporal_stability": 10,  # Timeless
            "scope": 5,
        }
        
        ephemeral_score, _, _ = get_importance_max(ephemeral)
        timeless_score, _, _ = get_importance_max(timeless)
        
        # Timeless should score higher (temporal_stability weighted in some profiles)
        assert timeless_score > ephemeral_score, \
            f"Timeless ({timeless_score}) should score higher than ephemeral ({ephemeral_score})"


class TestTierAssignment:
    """Test tier assignment from importance scores."""

    def test_tier_boundaries(self):
        """Test tier assignment at boundaries."""
        assert get_tier(10.0) == "A"
        assert get_tier(8.0) == "A"
        assert get_tier(7.9) == "B"
        assert get_tier(6.5) == "B"
        assert get_tier(6.4) == "C"
        assert get_tier(5.0) == "C"
        assert get_tier(4.9) == "D"
        assert get_tier(0.0) == "D"

    def test_tier_from_dimensions(self):
        """Test full pipeline: dimensions → importance → tier."""
        # A-tier claim
        a_tier_dims = {
            "epistemic_value": 9,
            "actionability": 8,
            "novelty": 8,
            "verifiability": 9,
            "understandability": 8,
            "temporal_stability": 9,
            "scope": 8,
        }
        
        importance, _, _ = get_importance_max(a_tier_dims)
        tier = get_tier(importance)
        assert tier == "A", f"Expected A-tier, got {tier} (importance: {importance})"
        
        # D-tier claim
        d_tier_dims = {
            "epistemic_value": 2,
            "actionability": 2,
            "novelty": 2,
            "verifiability": 5,
            "understandability": 8,
            "temporal_stability": 3,
            "scope": 2,
        }
        
        importance, _, _ = get_importance_max(d_tier_dims)
        tier = get_tier(importance)
        assert tier in ["C", "D"], f"Expected C or D-tier, got {tier} (importance: {importance})"


class TestCompositeImportance:
    """Test composite importance calculation."""

    def test_calculate_composite_importance_max(self):
        """Test composite importance with max-scoring."""
        dimensions = {
            "epistemic_value": 9,
            "actionability": 6,
            "novelty": 8,
            "verifiability": 8,
            "understandability": 7,
            "temporal_stability": 8,
            "scope": 6,
        }
        
        importance, metadata, all_scores = calculate_composite_importance(
            dimensions, method="max"
        )
        
        assert isinstance(importance, float)
        assert 0 <= importance <= 10
        assert isinstance(metadata, str)  # best_profile name
        assert len(all_scores) == 12

    def test_calculate_composite_importance_top_k(self):
        """Test composite importance with top-k averaging."""
        dimensions = {
            "epistemic_value": 9,
            "actionability": 6,
            "novelty": 8,
            "verifiability": 8,
            "understandability": 7,
            "temporal_stability": 8,
            "scope": 6,
        }
        
        importance, metadata, all_scores = calculate_composite_importance(
            dimensions, method="top_k", k=3
        )
        
        assert isinstance(importance, float)
        assert 0 <= importance <= 10
        assert isinstance(metadata, str)  # comma-separated profile names
        assert len(all_scores) == 12

    def test_invalid_dimensions_raises_error(self):
        """Test that invalid dimensions raise an error."""
        invalid_dimensions = {
            "epistemic_value": 11,  # Out of range
            "actionability": 6,
        }
        
        with pytest.raises(ValueError, match="Invalid dimensions"):
            calculate_composite_importance(invalid_dimensions, method="max")


class TestTopKScoring:
    """Test top-k averaging aggregation."""

    def test_top_k_more_selective_than_max(self):
        """Test that top-k is more selective than max-scoring."""
        # Claim that's great for one profile, mediocre for others
        dimensions = {
            "epistemic_value": 10,  # Great for scientist
            "actionability": 3,     # Poor for investor
            "novelty": 5,
            "verifiability": 8,
            "understandability": 5,
            "temporal_stability": 8,
            "scope": 4,
        }
        
        max_score, _, _ = get_importance_max(dimensions)
        top_k_score, _, _ = get_importance_top_k(dimensions, k=3)
        
        # Top-k should be lower (averages top 3, not just max)
        assert top_k_score <= max_score, \
            f"Top-k ({top_k_score}) should be ≤ max ({max_score})"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

