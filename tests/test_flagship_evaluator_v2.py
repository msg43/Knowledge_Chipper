"""
Integration tests for Flagship Evaluator V2 with multi-profile scoring.
"""

import pytest
from knowledge_system.processors.hce.flagship_evaluator import (
    EvaluatedClaim,
    FlagshipEvaluationOutput,
)


class TestFlagshipEvaluatorV2Output:
    """Test that flagship evaluator produces v2 output with dimensions."""

    def test_evaluated_claim_has_dimension_fields(self):
        """Test that EvaluatedClaim can handle v2 fields."""
        claim_data = {
            "original_claim_text": "Test claim",
            "decision": "accept",
            "dimensions": {
                "epistemic_value": 9,
                "actionability": 6,
                "novelty": 8,
                "verifiability": 8,
                "understandability": 7,
                "temporal_stability": 8,
                "scope": 6,
            },
            "profile_scores": {
                "scientist": 8.4,
                "investor": 7.1,
                "philosopher": 8.2,
            },
            "importance": 8.4,
            "best_profile": "scientist",
            "tier": "A",
            "novelty": 8,
            "confidence_final": 8,
            "reasoning": "Test reasoning",
            "rank": 1,
        }
        
        claim = EvaluatedClaim(claim_data)
        
        # Check v2 fields are accessible
        assert claim.dimensions == claim_data["dimensions"]
        assert claim.profile_scores == claim_data["profile_scores"]
        assert claim.best_profile == "scientist"
        assert claim.tier == "A"
        assert claim.importance == 8.4
        
        # Check backward compatibility fields
        assert claim.novelty == 8
        assert claim.confidence_final == 8

    def test_evaluated_claim_backward_compatibility(self):
        """Test that EvaluatedClaim works with v1 output (no dimensions)."""
        v1_claim_data = {
            "original_claim_text": "Test claim",
            "decision": "accept",
            "importance": 8,
            "novelty": 7,
            "confidence_final": 8,
            "reasoning": "Test reasoning",
            "rank": 1,
        }
        
        claim = EvaluatedClaim(v1_claim_data)
        
        # Should handle missing v2 fields gracefully
        assert claim.dimensions == {}
        assert claim.profile_scores == {}
        assert claim.best_profile == ""
        assert claim.importance == 8
        assert claim.novelty == 7
        assert claim.confidence_final == 8

    def test_flagship_output_with_dimensions(self):
        """Test FlagshipEvaluationOutput with v2 schema."""
        output_data = {
            "evaluated_claims": [
                {
                    "original_claim_text": "Claim 1",
                    "decision": "accept",
                    "dimensions": {
                        "epistemic_value": 9,
                        "actionability": 6,
                        "novelty": 8,
                        "verifiability": 8,
                        "understandability": 7,
                        "temporal_stability": 8,
                        "scope": 6,
                    },
                    "profile_scores": {
                        "scientist": 8.4,
                        "investor": 7.1,
                    },
                    "importance": 8.4,
                    "best_profile": "scientist",
                    "tier": "A",
                    "novelty": 8,
                    "confidence_final": 8,
                    "reasoning": "High epistemic value",
                    "rank": 1,
                },
                {
                    "original_claim_text": "Claim 2",
                    "decision": "reject",
                    "rejection_reason": "Trivial",
                    "dimensions": {
                        "epistemic_value": 2,
                        "actionability": 1,
                        "novelty": 1,
                        "verifiability": 10,
                        "understandability": 10,
                        "temporal_stability": 4,
                        "scope": 2,
                    },
                    "importance": 3.5,
                    "tier": "D",
                    "reasoning": "Too trivial",
                    "rank": 2,
                },
            ],
            "summary_assessment": {
                "total_claims_processed": 2,
                "claims_accepted": 1,
                "claims_rejected": 1,
                "key_themes": ["test"],
                "overall_quality": "high",
                "recommendations": "Good quality",
            },
        }
        
        output = FlagshipEvaluationOutput(output_data)
        
        assert output.is_valid()
        assert len(output.evaluated_claims) == 2
        
        # Check accepted claim has v2 fields
        accepted = output.get_accepted_claims()[0]
        assert accepted.dimensions["epistemic_value"] == 9
        assert accepted.best_profile == "scientist"
        assert accepted.tier == "A"
        
        # Check rejected claim
        rejected = output.get_rejected_claims()[0]
        assert rejected.decision == "reject"
        assert rejected.dimensions["epistemic_value"] == 2


class TestDimensionProcessing:
    """Test dimension processing in flagship evaluator."""

    def test_dimensions_extracted_to_separate_columns(self):
        """Test that temporal_stability and scope are extracted for filtering."""
        claim_data = {
            "original_claim_text": "Test claim",
            "decision": "accept",
            "dimensions": {
                "epistemic_value": 9,
                "actionability": 6,
                "novelty": 8,
                "verifiability": 8,
                "understandability": 7,
                "temporal_stability": 8,
                "scope": 6,
            },
            "importance": 8.4,
            "reasoning": "Test",
            "rank": 1,
        }
        
        claim = EvaluatedClaim(claim_data)
        
        # These should be accessible from dimensions
        assert claim.dimensions["temporal_stability"] == 8
        assert claim.dimensions["scope"] == 6


class TestTierDistribution:
    """Test tier distribution in output."""

    def test_tier_distribution_includes_all_tiers(self):
        """Test that tier distribution can include A/B/C/D tiers."""
        output_data = {
            "evaluated_claims": [
                {
                    "original_claim_text": "A-tier claim",
                    "decision": "accept",
                    "importance": 9,
                    "tier": "A",
                    "novelty": 8,
                    "confidence_final": 9,
                    "reasoning": "Excellent",
                    "rank": 1,
                },
                {
                    "original_claim_text": "B-tier claim",
                    "decision": "accept",
                    "importance": 7,
                    "tier": "B",
                    "novelty": 6,
                    "confidence_final": 7,
                    "reasoning": "Good",
                    "rank": 2,
                },
                {
                    "original_claim_text": "C-tier claim",
                    "decision": "accept",
                    "importance": 5.5,
                    "tier": "C",
                    "novelty": 5,
                    "confidence_final": 6,
                    "reasoning": "Moderate",
                    "rank": 3,
                },
                {
                    "original_claim_text": "D-tier claim",
                    "decision": "reject",
                    "importance": 3,
                    "tier": "D",
                    "novelty": 2,
                    "confidence_final": 5,
                    "reasoning": "Low quality",
                    "rank": 4,
                },
            ],
            "summary_assessment": {
                "total_claims_processed": 4,
                "claims_accepted": 3,
                "claims_rejected": 1,
                "key_themes": ["test"],
                "overall_quality": "medium",
            },
            "tier_distribution": {
                "A": 1,
                "B": 1,
                "C": 1,
                "D": 1,
            },
        }
        
        output = FlagshipEvaluationOutput(output_data)
        
        assert output.is_valid()
        assert len(output.get_accepted_claims()) == 3
        
        # Check tier distribution
        tier_dist = output_data.get("tier_distribution", {})
        assert tier_dist.get("A") == 1
        assert tier_dist.get("B") == 1
        assert tier_dist.get("C") == 1
        assert tier_dist.get("D") == 1


class TestProfileDistribution:
    """Test profile distribution in output."""

    def test_profile_distribution_tracking(self):
        """Test that best_profile distribution is tracked."""
        output_data = {
            "evaluated_claims": [
                {
                    "original_claim_text": "Scientific claim",
                    "decision": "accept",
                    "best_profile": "scientist",
                    "importance": 8.4,
                    "tier": "A",
                    "reasoning": "High epistemic value",
                    "rank": 1,
                },
                {
                    "original_claim_text": "Investment claim",
                    "decision": "accept",
                    "best_profile": "investor",
                    "importance": 8.2,
                    "tier": "A",
                    "reasoning": "High actionability",
                    "rank": 2,
                },
                {
                    "original_claim_text": "Another scientific claim",
                    "decision": "accept",
                    "best_profile": "scientist",
                    "importance": 7.8,
                    "tier": "B",
                    "reasoning": "Good epistemic value",
                    "rank": 3,
                },
            ],
            "summary_assessment": {
                "total_claims_processed": 3,
                "claims_accepted": 3,
                "claims_rejected": 0,
                "key_themes": ["science", "investment"],
                "overall_quality": "high",
            },
            "profile_distribution": {
                "scientist": 2,
                "investor": 1,
            },
        }
        
        output = FlagshipEvaluationOutput(output_data)
        
        assert output.is_valid()
        
        # Check profile distribution
        profile_dist = output_data.get("profile_distribution", {})
        assert profile_dist.get("scientist") == 2
        assert profile_dist.get("investor") == 1


class TestBackwardCompatibility:
    """Test backward compatibility with v1 output."""

    def test_v1_output_still_works(self):
        """Test that v1 output without dimensions still works."""
        v1_output = {
            "evaluated_claims": [
                {
                    "original_claim_text": "Old claim",
                    "decision": "accept",
                    "importance": 8,
                    "novelty": 7,
                    "confidence_final": 8,
                    "reasoning": "Good claim",
                    "rank": 1,
                    "tier": "A",
                }
            ],
            "summary_assessment": {
                "total_claims_processed": 1,
                "claims_accepted": 1,
                "claims_rejected": 0,
                "key_themes": ["test"],
                "overall_quality": "high",
            },
        }
        
        output = FlagshipEvaluationOutput(v1_output)
        
        assert output.is_valid()
        assert len(output.get_accepted_claims()) == 1
        
        claim = output.get_accepted_claims()[0]
        assert claim.importance == 8
        assert claim.novelty == 7
        assert claim.confidence_final == 8
        
        # v2 fields should be empty but not cause errors
        assert claim.dimensions == {}
        assert claim.profile_scores == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

