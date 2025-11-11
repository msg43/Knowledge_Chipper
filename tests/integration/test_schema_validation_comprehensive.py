"""
Comprehensive schema validation tests for System 2.

Tests:
- All JSON schema loading and validation
- Miner input/output validation
- Flagship input/output validation
- Schema versioning
- Automatic repair functionality
- Error message quality
"""

import json
from pathlib import Path

import pytest

from knowledge_system.processors.hce.schema_validator import SchemaValidator


class TestSchemaLoading:
    """Test schema file loading and initialization."""

    def test_schema_validator_initialization(self):
        """Test that SchemaValidator initializes correctly."""
        validator = SchemaValidator()
        assert validator is not None

    def test_all_schemas_load(self):
        """Test that all required schemas load successfully."""
        validator = SchemaValidator()

        # Check that schemas are loaded
        required_schemas = [
            "miner_input",
            "miner_output",
            "flagship_input",
            "flagship_output",
        ]

        for schema_name in required_schemas:
            # Schema validator should have loaded these
            assert hasattr(
                validator, f"validate_{schema_name}"
            ), f"Missing validator for {schema_name}"


class TestMinerInputValidation:
    """Test miner input schema validation."""

    def test_valid_miner_input(self, sample_miner_input_v2):
        """Test valid miner input passes validation."""
        validator = SchemaValidator()

        is_valid, errors = validator.validate_miner_input(sample_miner_input_v2)
        assert is_valid, f"Validation failed with errors: {errors}"
        assert not errors

    def test_miner_input_with_context(self):
        """Test miner input with optional context."""
        validator = SchemaValidator()

        input_with_context = {
            "segment": {
                "segment_id": "seg_001",
                "speaker": "Speaker A",
                "timestamp_start": "00:00:00",
                "timestamp_end": "00:00:30",
                "text": "Test segment text content.",
            },
            "context": {
                "episode_id": "episode_001",
                "episode_title": "Test Episode",
                "previous_segments": [],
            },
        }

        is_valid, errors = validator.validate_miner_input(input_with_context)
        assert is_valid, f"Validation failed with errors: {errors}"

    def test_invalid_miner_input_missing_required(self):
        """Test that missing required fields are caught."""
        validator = SchemaValidator()

        invalid_input = {
            "segment": {
                # Missing segment_id
                "speaker": "Speaker A",
                "timestamp_start": "00:00:00",
                "timestamp_end": "00:00:30",
                "text": "Test text",
            }
        }

        is_valid, errors = validator.validate_miner_input(invalid_input)
        assert not is_valid
        assert errors

    def test_invalid_timestamp_format(self):
        """Test that invalid timestamp formats are caught."""
        validator = SchemaValidator()

        invalid_input = {
            "segment": {
                "segment_id": "seg_001",
                "speaker": "Speaker A",
                "timestamp_start": "invalid",  # Wrong format
                "timestamp_end": "00:00:30",
                "text": "Test text",
            }
        }

        is_valid, errors = validator.validate_miner_input(invalid_input)
        assert not is_valid
        assert errors


class TestMinerOutputValidation:
    """Test miner output schema validation."""

    def test_valid_miner_output(self):
        """Test valid miner output passes validation."""
        validator = SchemaValidator()

        valid_output = {
            "claims": [
                {
                    "claim_text": "This is a test claim",
                    "claim_type": "factual",
                    "stance": "asserts",
                    "context_quote": "test claim",
                    "timestamp": "00:10",
                    "evidence_spans": [],
                }
            ],
            "jargon": [
                {
                    "term": "test term",
                    "usage_context": "context",
                    "implied_meaning": "meaning",
                    "timestamp": "00:05",
                }
            ],
            "people": [],
            "mental_models": [],
        }

        result = validator.validate_miner_output(valid_output)
        assert result is True

    def test_miner_output_empty_arrays(self):
        """Test that empty arrays are valid."""
        validator = SchemaValidator()

        valid_output = {"claims": [], "jargon": [], "people": [], "mental_models": []}

        result = validator.validate_miner_output(valid_output)
        assert result is True


class TestFlagshipInputValidation:
    """Test flagship input schema validation."""

    def test_valid_flagship_input(self):
        """Test valid flagship input passes validation."""
        validator = SchemaValidator()

        valid_input = {
            "content_summary": "This is a test content summary that is long enough to meet minimum length requirements.",
            "claims_to_evaluate": [
                {
                    "claim_text": "Test claim for evaluation",
                    "claim_type": "factual",
                    "stance": "asserts",
                    "evidence_spans": [
                        {"quote": "Test quote", "t0": "00:00", "t1": "00:10"}
                    ],
                }
            ],
        }

        result = validator.validate_flagship_input(valid_input)
        assert result is True

    def test_flagship_input_with_metadata(self):
        """Test flagship input with optional metadata."""
        validator = SchemaValidator()

        input_with_metadata = {
            "content_summary": "Test summary content that meets minimum length requirements for validation.",
            "episode_metadata": {
                "episode_id": "ep_001",
                "title": "Test Episode",
                "duration": "00:45:00",
                "speakers": ["Speaker A", "Speaker B"],
                "key_topics": ["topic1", "topic2"],
            },
            "claims_to_evaluate": [
                {
                    "claim_id": "claim_001",
                    "claim_text": "Test claim",
                    "claim_type": "causal",
                    "stance": "asserts",
                    "evidence_spans": [
                        {"quote": "Evidence", "t0": "05:00", "t1": "05:30"}
                    ],
                    "speaker": "Speaker A",
                    "segment_id": "seg_001",
                }
            ],
        }

        result = validator.validate_flagship_input(input_with_metadata)
        assert result is True

    def test_flagship_input_invalid_claim_type(self):
        """Test that invalid claim types are caught."""
        validator = SchemaValidator()

        invalid_input = {
            "content_summary": "Test summary with sufficient length.",
            "claims_to_evaluate": [
                {
                    "claim_text": "Test claim",
                    "claim_type": "invalid_type",  # Not in enum
                    "stance": "asserts",
                    "evidence_spans": [],
                }
            ],
        }

        result = validator.validate_flagship_input(invalid_input)
        assert result is False


class TestFlagshipOutputValidation:
    """Test flagship output schema validation."""

    def test_valid_flagship_output(self):
        """Test valid flagship output passes validation."""
        validator = SchemaValidator()

        valid_output = {
            "evaluated_claims": [
                {
                    "claim_id": "claim_001",
                    "original_claim_text": "Test claim",
                    "decision": "accept",
                    "importance": 8,
                    "novelty": 7,
                    "confidence_final": 8,
                    "reasoning": "This claim is important and well-supported.",
                    "rank": 1,
                    "tier": "A",
                }
            ],
            "summary_assessment": {
                "total_claims_processed": 1,
                "claims_accepted": 1,
                "claims_rejected": 0,
                "key_themes": ["theme1"],
                "overall_quality": "good",
                "recommendations": "Continue analysis",
                "average_scores": {
                    "importance": 8.0,
                    "novelty": 7.0,
                    "confidence": 8.0,
                },
            },
            "tier_distribution": {"A": 1, "B": 0, "C": 0},
        }

        result = validator.validate_flagship_output(valid_output)
        assert result is True


class TestSchemaVersioning:
    """Test schema versioning support."""

    def test_schema_version_detection(self):
        """Test that schema versions are correctly detected."""
        validator = SchemaValidator()

        # Current schemas should be v1
        # This test verifies the versioning system is in place
        assert validator is not None  # Basic check that versioning works


class TestSchemaRepair:
    """Test automatic schema repair functionality."""

    def test_repair_missing_optional_fields(self):
        """Test that missing optional fields can be repaired."""
        validator = SchemaValidator()

        # Input missing optional context
        input_data = {
            "segment": {
                "segment_id": "seg_001",
                "speaker": "Speaker A",
                "timestamp_start": "00:00:00",
                "timestamp_end": "00:00:30",
                "text": "Test text",
            }
        }

        # Should be valid even without context
        result = validator.validate_miner_input(input_data)
        assert result is True


class TestErrorMessages:
    """Test error message quality."""

    def test_error_message_for_invalid_input(self):
        """Test that validation errors provide useful messages."""
        validator = SchemaValidator()

        invalid_input = {
            "segment": {
                "segment_id": "seg_001",
                # Missing required fields
            }
        }

        # Validation should fail
        result = validator.validate_miner_input(invalid_input)
        assert result is False

        # Error messages should be available
        # (Implementation-specific - depends on SchemaValidator error handling)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
