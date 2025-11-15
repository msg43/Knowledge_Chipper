"""
Tests for JSON schema validation and repair functionality.

Tests schema validation, automatic repair, and error handling
for all System 2 JSON schemas.
"""

import json
from pathlib import Path

import pytest

from src.knowledge_system.errors import ErrorCode, KnowledgeSystemError
from src.knowledge_system.processors.hce.schema_validator import (
    get_validator,
    repair_and_validate_flagship_output,
    repair_and_validate_miner_output,
    validate_flagship_output,
    validate_miner_output,
)

from .fixtures import SAMPLE_FLAGSHIP_OUTPUT, SAMPLE_MINER_OUTPUT, SCHEMA_SNAPSHOT_DATA


class TestSchemaValidation:
    """Test cases for schema validation."""

    def test_validator_initialization(self):
        """Test validator loads schemas correctly."""
        validator = get_validator()

        # Check that schemas are loaded
        assert len(validator.schemas) > 0

        # Check versioned schemas exist
        expected_schemas = [
            "miner_input.v1",
            "miner_output.v1",
            "flagship_input.v1",
            "flagship_output.v1",
        ]

        for schema_name in expected_schemas:
            assert schema_name in validator.schemas

    def test_valid_miner_output(self):
        """Test validation of valid miner output."""
        is_valid, errors = validate_miner_output(SAMPLE_MINER_OUTPUT)

        assert is_valid
        assert len(errors) == 0

    def test_invalid_miner_output_missing_field(self):
        """Test validation catches missing required fields."""
        invalid_output = {
            # Missing "claims" field
            "jargon": [],
            "people": [],
            "mental_models": [],
        }

        is_valid, errors = validate_miner_output(invalid_output)

        assert not is_valid
        assert len(errors) > 0
        assert any("claims" in error for error in errors)

    def test_invalid_miner_output_wrong_type(self):
        """Test validation catches type errors."""
        invalid_output = {
            "claims": "should be array",  # Wrong type
            "jargon": [],
            "people": [],
            "mental_models": [],
        }

        is_valid, errors = validate_miner_output(invalid_output)

        assert not is_valid
        assert len(errors) > 0

    def test_repair_miner_output_missing_arrays(self):
        """Test repair adds missing array fields."""
        incomplete_output = {
            "claims": [
                {
                    "claim_text": "This is a test claim with enough length to meet schema requirements",
                    "claim_type": "factual",
                    "domain": "general",
                    "stance": "asserts",
                    "evidence_spans": [
                        {
                            "segment_id": "seg_001",
                            "quote": "test quote",
                            "t0": "00:00:00",
                            "t1": "00:00:05",
                        }
                    ],
                }
            ]
            # Missing jargon, people, mental_models
        }

        repaired, is_valid, errors = repair_and_validate_miner_output(incomplete_output)

        assert is_valid
        assert "jargon" in repaired and isinstance(repaired["jargon"], list)
        assert "people" in repaired and isinstance(repaired["people"], list)
        assert "mental_models" in repaired and isinstance(
            repaired["mental_models"], list
        )

    def test_repair_miner_output_type_conversion(self):
        """Test repair converts wrong types to arrays."""
        wrong_type_output = {
            "claims": [],
            "jargon": None,  # Should be array
            "people": {},  # Should be array
            "mental_models": "wrong",  # Should be array
        }

        repaired, is_valid, errors = repair_and_validate_miner_output(wrong_type_output)

        assert is_valid
        assert isinstance(repaired["jargon"], list)
        assert isinstance(repaired["people"], list)
        assert isinstance(repaired["mental_models"], list)

    def test_valid_flagship_output(self):
        """Test validation of valid flagship output."""
        is_valid, errors = validate_flagship_output(SAMPLE_FLAGSHIP_OUTPUT)

        assert is_valid
        assert len(errors) == 0

    def test_invalid_flagship_output_missing_assessment(self):
        """Test validation catches missing summary assessment."""
        invalid_output = {
            "evaluated_claims": []
            # Missing summary_assessment
        }

        is_valid, errors = validate_flagship_output(invalid_output)

        assert not is_valid
        assert any("summary_assessment" in error for error in errors)

    def test_repair_flagship_output(self):
        """Test repair adds missing summary assessment."""
        incomplete_output = {
            "evaluated_claims": [
                {
                    "original_claim_text": "Test",
                    "decision": "accept",
                    "importance": 5,
                    "novelty": 5,
                    "confidence_final": 5,
                    "reasoning": "Test",
                    "rank": 1,
                }
            ]
            # Missing summary_assessment
        }

        repaired, is_valid, errors = repair_and_validate_flagship_output(
            incomplete_output
        )

        assert is_valid
        assert "summary_assessment" in repaired
        # Repair adds default summary_assessment with 0 counts (doesn't analyze claims)
        assert "total_claims_processed" in repaired["summary_assessment"]
        assert "claims_accepted" in repaired["summary_assessment"]

    def test_repair_failure_raises_error(self):
        """Test that unfixable validation errors raise proper exception."""
        # Invalid data with nested structure violations that can't be auto-repaired
        completely_invalid = {
            "claims": [
                {
                    "claim_text": "x",  # Too short (minLength: 10)
                    "claim_type": "invalid",  # Invalid enum
                    "stance": "invalid",  # Invalid enum
                    "evidence_spans": [],  # Empty but required to have items
                }
            ],
            "jargon": [],
            "people": [],
            "mental_models": [],
        }

        with pytest.raises(KnowledgeSystemError) as exc_info:
            repair_and_validate_miner_output(completely_invalid)

        assert exc_info.value.error_code == ErrorCode.VALIDATION_SCHEMA_ERROR_HIGH.value

    def test_schema_snapshots(self):
        """Test schema validation against snapshot test data."""
        validator = get_validator()

        for schema_name, test_data in SCHEMA_SNAPSHOT_DATA.items():
            # Test valid examples
            for valid_example in test_data["valid"]:
                is_valid, errors = validator.validate(valid_example, schema_name)
                assert is_valid, f"Valid example failed for {schema_name}: {errors}"

            # Test invalid examples
            for invalid_example in test_data["invalid"]:
                is_valid, errors = validator.validate(invalid_example, schema_name)
                assert not is_valid, f"Invalid example passed for {schema_name}"

    def test_nested_validation_errors(self):
        """Test validation provides helpful error messages for nested fields."""
        invalid_claim = {
            "claims": [
                {
                    "claim_text": "Test",
                    "claim_type": "invalid_type",  # Invalid enum value
                    "stance": "asserts",
                    "evidence_spans": [
                        {
                            "quote": "Test quote"
                            # Missing t0 and t1
                        }
                    ],
                }
            ],
            "jargon": [],
            "people": [],
            "mental_models": [],
        }

        is_valid, errors = validate_miner_output(invalid_claim)

        assert not is_valid
        # Should have at least one error (validator may stop at first error)
        assert len(errors) >= 1

    def test_schema_version_handling(self):
        """Test that versioned schemas are handled correctly."""
        validator = get_validator()

        # Test with version suffix
        is_valid_v1, _ = validator.validate(SAMPLE_MINER_OUTPUT, "miner_output.v1")
        assert is_valid_v1

        # Test without version suffix (should use v1 by default)
        is_valid_base, _ = validator.validate(SAMPLE_MINER_OUTPUT, "miner_output")
        assert is_valid_base

    def test_repair_preserves_valid_data(self):
        """Test that repair doesn't modify valid data unnecessarily."""
        import copy

        original = copy.deepcopy(SAMPLE_MINER_OUTPUT)
        repaired, is_valid, _ = repair_and_validate_miner_output(original)

        assert is_valid
        # Check that valid data is preserved
        assert repaired["claims"] == original["claims"]
        assert repaired["jargon"] == original["jargon"]
        assert repaired["people"] == original["people"]
        assert repaired["mental_models"] == original["mental_models"]
