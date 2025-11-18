"""
Question Mapper - Organize claims by the questions they answer.

This module implements a three-stage pipeline for question discovery and assignment:
1. Discovery: Extract questions from claims (unbiased approach)
2. Merging: Analyze new vs existing questions for deduplication
3. Assignment: Map claims to questions with relation types

The goal is to create a sense-making layer that groups claims by inquiry,
enabling users to navigate knowledge through questions rather than just categories or tags.
"""

from .assignment import ClaimAssignment
from .discovery import QuestionDiscovery
from .hce_integration import (
    post_hce_hook,
    process_all_unmapped_sources,
    process_source_questions,
)
from .merger import QuestionMerger
from .models import (
    ClaimQuestionMapping,
    DiscoveredQuestion,
    MergeRecommendation,
    QuestionMapperResult,
)
from .orchestrator import QuestionMapperOrchestrator

__all__ = [
    "QuestionDiscovery",
    "QuestionMerger",
    "ClaimAssignment",
    "QuestionMapperOrchestrator",
    "DiscoveredQuestion",
    "MergeRecommendation",
    "ClaimQuestionMapping",
    "QuestionMapperResult",
    # Integration functions
    "process_source_questions",
    "process_all_unmapped_sources",
    "post_hce_hook",
]
