"""
User Profile Definitions for Multi-Profile Claim Scoring

Each profile represents a different type of user with different priorities
when evaluating claim importance.
"""

from dataclasses import dataclass
from typing import Dict


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


# =============================================================================
# Standard User Profiles
# =============================================================================

STANDARD_PROFILES = {
    "scientist": UserProfile(
        name="Scientist/Researcher",
        description="Values deep understanding, theoretical insights, and well-supported claims",
        weights={
            "epistemic_value": 0.45,
            "verifiability": 0.28,
            "novelty": 0.13,
            "temporal_stability": 0.08,  # Scientists value lasting insights
            "scope": 0.04,  # Generalizability matters
            "actionability": 0.02,
        }
    ),

    "philosopher": UserProfile(
        name="Philosopher/Critical Thinker",
        description="Values conceptual clarity, novel perspectives, and logical coherence",
        weights={
            "epistemic_value": 0.37,
            "novelty": 0.27,
            "verifiability": 0.18,
            "scope": 0.10,  # Universal principles highly valued
            "actionability": 0.05,
            "temporal_stability": 0.03,
        }
    ),

    "educator": UserProfile(
        name="Educator/Teacher",
        description="Values clear explanations, foundational knowledge, and broad applicability",
        weights={
            "understandability": 0.37,
            "epistemic_value": 0.27,
            "scope": 0.12,  # Broad applicability important for teaching
            "actionability": 0.15,
            "temporal_stability": 0.06,  # Lasting knowledge for curriculum
            "novelty": 0.03,
        }
    ),

    "student": UserProfile(
        name="Student/Learner",
        description="Values accessible insights, surprising facts, and learning-oriented content",
        weights={
            "understandability": 0.33,
            "novelty": 0.28,
            "epistemic_value": 0.23,
            "actionability": 0.08,
            "scope": 0.05,
            "temporal_stability": 0.03,
        }
    ),

    "skeptic": UserProfile(
        name="Skeptic/Fact-Checker",
        description="Values evidence quality, source reliability, and falsifiability",
        weights={
            "verifiability": 0.58,
            "epistemic_value": 0.23,
            "novelty": 0.08,
            "temporal_stability": 0.06,  # Lasting truth matters
            "actionability": 0.03,
            "scope": 0.02,
        }
    ),

    "investor": UserProfile(
        name="Investor/Financial Professional",
        description="Values practical utility, market insights, and actionable intelligence",
        weights={
            "actionability": 0.48,
            "verifiability": 0.23,
            "epistemic_value": 0.13,
            "novelty": 0.08,
            "temporal_stability": 0.05,  # Some weight on lasting principles
            "scope": 0.03,
        }
    ),

    "policy_maker": UserProfile(
        name="Policy Maker/Governance",
        description="Values broad impact, evidence-based policy, and systemic thinking",
        weights={
            "actionability": 0.32,
            "epistemic_value": 0.27,
            "verifiability": 0.18,
            "scope": 0.12,  # Broad impact crucial
            "understandability": 0.08,
            "temporal_stability": 0.03,
        }
    ),

    "tech_professional": UserProfile(
        name="Tech Professional/Engineer",
        description="Values practical implementation, technical depth, and reproducibility",
        weights={
            "actionability": 0.42,
            "epistemic_value": 0.23,
            "verifiability": 0.18,
            "novelty": 0.08,
            "scope": 0.06,  # Reusable solutions valued
            "temporal_stability": 0.03,
        }
    ),

    "health_professional": UserProfile(
        name="Health/Medical Professional",
        description="Values clinical evidence, patient safety, and therapeutic utility",
        weights={
            "verifiability": 0.42,
            "actionability": 0.28,
            "epistemic_value": 0.18,
            "temporal_stability": 0.07,  # Lasting medical knowledge
            "novelty": 0.03,
            "scope": 0.02,
        }
    ),

    "journalist": UserProfile(
        name="Journalist/Communicator",
        description="Values newsworthy insights, clear communication, and source credibility",
        weights={
            "novelty": 0.33,
            "understandability": 0.28,
            "verifiability": 0.18,
            "epistemic_value": 0.13,
            "scope": 0.05,  # Broad relevance for audience
            "temporal_stability": 0.03,  # Less concerned with longevity
        }
    ),

    "generalist": UserProfile(
        name="Curious Generalist",
        description="Values interesting facts, accessible knowledge, and broad learning",
        weights={
            "novelty": 0.37,
            "understandability": 0.23,
            "epistemic_value": 0.18,
            "actionability": 0.13,
            "scope": 0.06,  # Broad applicability interesting
            "temporal_stability": 0.03,
        }
    ),

    "pragmatist": UserProfile(
        name="Pragmatist/Decision-Maker",
        description="Values immediate utility, practical application, and reliable information",
        weights={
            "actionability": 0.47,
            "verifiability": 0.23,
            "understandability": 0.13,
            "epistemic_value": 0.08,
            "scope": 0.06,  # Broadly applicable solutions
            "temporal_stability": 0.03,
        }
    ),
}


# Dimension definitions for reference
DIMENSION_DEFINITIONS = {
    "epistemic_value": {
        "name": "Epistemic Value",
        "description": "How much does this reduce uncertainty about how the world works?",
        "examples": {
            1: "Trivial observation with no explanatory power",
            5: "Moderate insight that adds some understanding",
            10: "Fundamental insight that transforms understanding"
        }
    },
    "actionability": {
        "name": "Actionability",
        "description": "Can someone make better decisions with this information?",
        "examples": {
            1: "Purely theoretical with no practical application",
            5: "Some practical relevance but limited utility",
            10: "Highly actionable, directly enables better decisions"
        }
    },
    "novelty": {
        "name": "Novelty",
        "description": "Is this surprising or does it challenge common assumptions?",
        "examples": {
            1: "Obvious fact that everyone knows",
            5: "Somewhat novel but not groundbreaking",
            10: "Groundbreaking insight that challenges conventional wisdom"
        }
    },
    "verifiability": {
        "name": "Verifiability",
        "description": "How strong is the evidence and how reliable are the sources?",
        "examples": {
            1: "Pure speculation with no supporting evidence",
            5: "Some evidence but gaps or uncertainties remain",
            10: "Rigorously proven with strong empirical support"
        }
    },
    "understandability": {
        "name": "Understandability",
        "description": "How clear and accessible is this claim?",
        "examples": {
            1: "Opaque, laden with jargon, difficult to parse",
            5: "Reasonably clear but requires some background",
            10: "Crystal clear, accessible to non-experts"
        }
    },
    "temporal_stability": {
        "name": "Temporal Stability",
        "description": "How long will this claim remain true/relevant?",
        "examples": {
            1: "Ephemeral (days/weeks) - current events, short-term predictions",
            5: "Medium-term (years) - contextual facts, evolving situations",
            10: "Timeless (permanent) - mathematical proofs, physical laws, fundamental principles"
        }
    },
    "scope": {
        "name": "Scope",
        "description": "How broadly applicable is this claim?",
        "examples": {
            1: "Highly specific edge case - narrow technical detail",
            5: "Domain-specific - applies to particular field or context",
            10: "Universal principle - applies across all contexts"
        }
    }
}
