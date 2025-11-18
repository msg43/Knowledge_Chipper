"""
Pydantic models for Question Mapper data structures.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class QuestionType(str, Enum):
    """Types of questions."""

    FACTUAL = "factual"  # "What is X?"
    CAUSAL = "causal"  # "Why does X happen?"
    NORMATIVE = "normative"  # "Should we do X?"
    COMPARATIVE = "comparative"  # "What's better: X or Y?"
    PROCEDURAL = "procedural"  # "How do you do X?"
    FORECASTING = "forecasting"  # "Will X happen?"


class MergeAction(str, Enum):
    """Actions for question merging."""

    MERGE_INTO_EXISTING = "merge_into_existing"  # New is duplicate/subset
    MERGE_EXISTING_INTO_NEW = "merge_existing_into_new"  # Existing is subset
    LINK_AS_RELATED = "link_as_related"  # Keep both, link as related
    KEEP_DISTINCT = "keep_distinct"  # No relationship


class RelationType(str, Enum):
    """How a claim relates to a question."""

    ANSWERS = "answers"  # Direct answer
    PARTIAL_ANSWER = "partial_answer"  # Addresses part of question
    SUPPORTS_ANSWER = "supports_answer"  # Evidence for an answer
    CONTRADICTS = "contradicts"  # Conflicts with proposed answer
    PREREQUISITE = "prerequisite"  # Background knowledge needed
    FOLLOW_UP = "follow_up"  # Raises related question
    CONTEXT = "context"  # Provides framing/background


class DiscoveredQuestion(BaseModel):
    """A question discovered from claims."""

    question_text: str
    question_type: QuestionType
    domain: Optional[str] = None
    claim_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v):
        """Ensure confidence is between 0 and 1."""
        if not 0 <= v <= 1:
            raise ValueError("Confidence must be between 0 and 1")
        return v


class MergeRecommendation(BaseModel):
    """Recommendation for merging a new question with existing ones."""

    new_question_text: str
    action: MergeAction
    target_question_id: Optional[str] = None  # For merge actions
    target_question_text: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str


class ClaimQuestionMapping(BaseModel):
    """Mapping between a claim and a question."""

    claim_id: str
    question_id: str
    relation_type: RelationType
    relevance_score: float = Field(ge=0.0, le=1.0)
    rationale: str


class QuestionMapperResult(BaseModel):
    """Complete result from question mapping process."""

    discovered_questions: list[DiscoveredQuestion] = Field(default_factory=list)
    merge_recommendations: list[MergeRecommendation] = Field(default_factory=list)
    claim_mappings: list[ClaimQuestionMapping] = Field(default_factory=list)
    processing_time_seconds: float = 0.0
    llm_calls_made: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
