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
    }
}
