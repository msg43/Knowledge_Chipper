"""
Unit tests for Question Mapper system.

Tests the three-stage pipeline:
1. QuestionDiscovery - Extract questions from claims
2. QuestionMerger - Deduplicate against existing questions
3. ClaimAssignment - Map claims to questions
"""

import json
import pytest
from unittest.mock import MagicMock, Mock

from src.knowledge_system.processors.question_mapper import (
    QuestionDiscovery,
    QuestionMerger,
    ClaimAssignment,
    QuestionMapperOrchestrator,
)
from src.knowledge_system.processors.question_mapper.models import (
    DiscoveredQuestion,
    MergeRecommendation,
    ClaimQuestionMapping,
    QuestionType,
    MergeAction,
    RelationType,
)


class TestQuestionDiscovery:
    """Tests for QuestionDiscovery processor."""

    @pytest.fixture
    def mock_llm(self):
        """Mock LLM adapter."""
        llm = MagicMock()
        llm.generate = MagicMock()
        return llm

    @pytest.fixture
    def discovery(self, mock_llm):
        """QuestionDiscovery instance with mocked LLM."""
        return QuestionDiscovery(mock_llm)

    @pytest.fixture
    def sample_claims(self):
        """Sample claims for testing."""
        return [
            {
                "claim_id": "claim_1",
                "claim_text": "Carbon taxes reduce emissions by 15-20%.",
            },
            {
                "claim_id": "claim_2",
                "claim_text": "Sweden implemented a carbon tax in 1991.",
            },
            {
                "claim_id": "claim_3",
                "claim_text": "Carbon taxes have minimal impact according to some studies.",
            },
        ]

    def test_discover_questions_success(self, discovery, mock_llm, sample_claims):
        """Test successful question discovery."""
        # Mock LLM response
        mock_response = json.dumps(
            [
                {
                    "question_text": "How effective are carbon taxes at reducing emissions?",
                    "question_type": "factual",
                    "domain": "climate policy",
                    "claim_ids": ["claim_1", "claim_3"],
                    "confidence": 0.9,
                    "rationale": "Claims present conflicting evidence on effectiveness.",
                }
            ]
        )
        mock_llm.generate.return_value = mock_response

        # Run discovery
        questions = discovery.discover_questions(sample_claims)

        # Assertions
        assert len(questions) == 1
        assert questions[0].question_text == "How effective are carbon taxes at reducing emissions?"
        assert questions[0].question_type == QuestionType.FACTUAL
        assert questions[0].domain == "climate policy"
        assert questions[0].confidence == 0.9
        assert "claim_1" in questions[0].claim_ids

        # Verify LLM was called
        mock_llm.generate.assert_called_once()

    def test_discover_questions_empty_claims(self, discovery):
        """Test error handling for empty claims."""
        with pytest.raises(ValueError, match="empty claims list"):
            discovery.discover_questions([])

    def test_discover_questions_invalid_claims(self, discovery):
        """Test error handling for malformed claims."""
        bad_claims = [{"claim_id": "c1"}]  # Missing claim_text
        with pytest.raises(ValueError, match="missing required fields"):
            discovery.discover_questions(bad_claims)

    def test_discover_questions_filters_low_confidence(
        self, discovery, mock_llm, sample_claims
    ):
        """Test that low-confidence questions are filtered."""
        mock_response = json.dumps(
            [
                {
                    "question_text": "Good question",
                    "question_type": "factual",
                    "domain": "test",
                    "claim_ids": ["claim_1"],
                    "confidence": 0.8,
                    "rationale": "High confidence",
                },
                {
                    "question_text": "Bad question",
                    "question_type": "factual",
                    "domain": "test",
                    "claim_ids": ["claim_2"],
                    "confidence": 0.3,
                    "rationale": "Low confidence",
                },
            ]
        )
        mock_llm.generate.return_value = mock_response

        questions = discovery.discover_questions(sample_claims, min_confidence=0.6)

        assert len(questions) == 1
        assert questions[0].question_text == "Good question"

    def test_discover_questions_batched(self, discovery, mock_llm):
        """Test batched processing for large claim sets."""
        # Create 100 claims
        claims = [
            {"claim_id": f"c_{i}", "claim_text": f"Claim {i}"} for i in range(100)
        ]

        mock_llm.generate.return_value = json.dumps([])

        discovery.discover_questions_batched(claims, batch_size=50)

        # Should make 2 LLM calls
        assert mock_llm.generate.call_count == 2


class TestQuestionMerger:
    """Tests for QuestionMerger processor."""

    @pytest.fixture
    def mock_llm(self):
        """Mock LLM adapter."""
        llm = MagicMock()
        llm.generate = MagicMock()
        return llm

    @pytest.fixture
    def merger(self, mock_llm):
        """QuestionMerger instance with mocked LLM."""
        return QuestionMerger(mock_llm)

    @pytest.fixture
    def new_questions(self):
        """Sample new questions."""
        return [
            {
                "question_text": "What causes inflation?",
                "question_type": "causal",
                "domain": "economics",
            }
        ]

    @pytest.fixture
    def existing_questions(self):
        """Sample existing questions."""
        return [
            {
                "question_id": "q_existing_1",
                "question_text": "What causes inflation in modern economies?",
                "question_type": "causal",
                "domain": "economics",
            }
        ]

    def test_analyze_merges_duplicate(
        self, merger, mock_llm, new_questions, existing_questions
    ):
        """Test merge recommendation for duplicate question."""
        mock_response = json.dumps(
            [
                {
                    "new_question_text": "What causes inflation?",
                    "action": "merge_into_existing",
                    "target_question_id": "q_existing_1",
                    "target_question_text": "What causes inflation in modern economies?",
                    "confidence": 0.95,
                    "rationale": "Same question, existing is more specific.",
                }
            ]
        )
        mock_llm.generate.return_value = mock_response

        recommendations = merger.analyze_merges(new_questions, existing_questions)

        assert len(recommendations) == 1
        assert recommendations[0].action == MergeAction.MERGE_INTO_EXISTING
        assert recommendations[0].target_question_id == "q_existing_1"
        assert recommendations[0].confidence == 0.95

    def test_analyze_merges_keep_distinct(self, merger, mock_llm, new_questions):
        """Test recommendation to keep question distinct."""
        # No existing questions
        recommendations = merger.analyze_merges(new_questions, [])

        assert len(recommendations) == 1
        assert recommendations[0].action == MergeAction.KEEP_DISTINCT
        assert recommendations[0].target_question_id is None

    def test_analyze_merges_domain_filtering(
        self, merger, mock_llm, new_questions, existing_questions
    ):
        """Test that domain filtering works."""
        # Add unrelated question in different domain
        existing_questions.append(
            {
                "question_id": "q_unrelated",
                "question_text": "What is quantum entanglement?",
                "question_type": "factual",
                "domain": "physics",
            }
        )

        mock_llm.generate.return_value = json.dumps([])

        merger.analyze_merges(new_questions, existing_questions)

        # Check that LLM was called with filtered questions
        call_args = mock_llm.generate.call_args
        prompt = call_args.kwargs["prompt"]

        # Should only include economics questions, not physics
        assert "inflation" in prompt.lower()
        assert "quantum" not in prompt.lower()


class TestClaimAssignment:
    """Tests for ClaimAssignment processor."""

    @pytest.fixture
    def mock_llm(self):
        """Mock LLM adapter."""
        llm = MagicMock()
        llm.generate = MagicMock()
        return llm

    @pytest.fixture
    def assignment(self, mock_llm):
        """ClaimAssignment instance with mocked LLM."""
        return ClaimAssignment(mock_llm)

    @pytest.fixture
    def sample_claims(self):
        """Sample claims for testing."""
        return [
            {
                "claim_id": "claim_1",
                "claim_text": "Carbon taxes reduce emissions by 15-20%.",
            }
        ]

    @pytest.fixture
    def sample_questions(self):
        """Sample questions for testing."""
        return [
            {
                "question_id": "q_1",
                "question_text": "How effective are carbon taxes?",
            }
        ]

    def test_assign_claims_success(
        self, assignment, mock_llm, sample_claims, sample_questions
    ):
        """Test successful claim assignment."""
        mock_response = json.dumps(
            [
                {
                    "claim_id": "claim_1",
                    "question_id": "q_1",
                    "relation_type": "answers",
                    "relevance_score": 0.95,
                    "rationale": "Directly answers effectiveness question with data.",
                }
            ]
        )
        mock_llm.generate.return_value = mock_response

        mappings = assignment.assign_claims(sample_claims, sample_questions)

        assert len(mappings) == 1
        assert mappings[0].claim_id == "claim_1"
        assert mappings[0].question_id == "q_1"
        assert mappings[0].relation_type == RelationType.ANSWERS
        assert mappings[0].relevance_score == 0.95

    def test_assign_claims_filters_low_relevance(
        self, assignment, mock_llm, sample_claims, sample_questions
    ):
        """Test filtering of low-relevance assignments."""
        mock_response = json.dumps(
            [
                {
                    "claim_id": "claim_1",
                    "question_id": "q_1",
                    "relation_type": "context",
                    "relevance_score": 0.3,
                    "rationale": "Weak connection.",
                }
            ]
        )
        mock_llm.generate.return_value = mock_response

        mappings = assignment.assign_claims(
            sample_claims, sample_questions, min_relevance=0.5
        )

        assert len(mappings) == 0

    def test_assign_claims_empty_questions(self, assignment, sample_claims):
        """Test assignment with no questions."""
        mappings = assignment.assign_claims(sample_claims, [])
        assert len(mappings) == 0

    def test_assign_claims_batched(self, assignment, mock_llm, sample_questions):
        """Test batched assignment for many claims."""
        claims = [{"claim_id": f"c_{i}", "claim_text": f"Text {i}"} for i in range(60)]

        mock_llm.generate.return_value = json.dumps([])

        assignment.assign_claims_batched(
            claims, sample_questions, claims_per_batch=30
        )

        # Should make 2 LLM calls
        assert mock_llm.generate.call_count == 2


class TestQuestionMapperOrchestrator:
    """Tests for QuestionMapperOrchestrator."""

    @pytest.fixture
    def mock_llm(self):
        """Mock LLM adapter."""
        return MagicMock()

    @pytest.fixture
    def mock_db(self):
        """Mock database service."""
        db = MagicMock()
        db.get_questions_by_domain.return_value = []
        db.create_question.return_value = "q_new_123"
        db.assign_claim_to_question.return_value = True
        return db

    @pytest.fixture
    def orchestrator(self, mock_llm, mock_db):
        """QuestionMapperOrchestrator instance."""
        return QuestionMapperOrchestrator(mock_llm, mock_db)

    @pytest.fixture
    def sample_claims(self):
        """Sample claims."""
        return [
            {"claim_id": "c1", "claim_text": "Test claim 1"},
            {"claim_id": "c2", "claim_text": "Test claim 2"},
        ]

    def test_process_claims_full_pipeline(
        self, orchestrator, mock_llm, mock_db, sample_claims
    ):
        """Test complete pipeline execution."""
        # Track which call we're on
        call_count = [0]

        def mock_generate(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # Discovery response
                return json.dumps(
                    [
                        {
                            "question_text": "What is X?",
                            "question_type": "factual",
                            "domain": "test",
                            "claim_ids": ["c1", "c2"],
                            "confidence": 0.8,
                            "rationale": "Test question",
                        }
                    ]
                )
            elif call_count[0] == 2:
                # Assignment response (merger is skipped when no existing questions)
                return json.dumps(
                    [
                        {
                            "claim_id": "c1",
                            "question_id": "q_new_123",
                            "relation_type": "answers",
                            "relevance_score": 0.85,
                            "rationale": "Directly answers",
                        }
                    ]
                )
            else:
                return json.dumps([])

        mock_llm.generate.side_effect = mock_generate

        result = orchestrator.process_claims(sample_claims, auto_approve=True)

        # Verify results
        assert len(result.discovered_questions) == 1
        assert len(result.merge_recommendations) == 1  # Auto-generated KEEP_DISTINCT
        assert len(result.claim_mappings) == 1
        assert result.llm_calls_made >= 2  # At least discovery + assignment

        # Verify database calls
        mock_db.create_question.assert_called_once()
        mock_db.assign_claim_to_question.assert_called_once()

    def test_process_claims_no_discoveries(self, orchestrator, mock_llm, sample_claims):
        """Test pipeline when no questions discovered."""
        mock_llm.generate.return_value = json.dumps([])

        result = orchestrator.process_claims(sample_claims)

        assert len(result.discovered_questions) == 0
        assert len(result.merge_recommendations) == 0
        assert len(result.claim_mappings) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
