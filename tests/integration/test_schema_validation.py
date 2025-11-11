"""
Integration tests for System 2 schema validation.

Tests JSON schema validation and repair functionality.
"""

import json
from pathlib import Path

import pytest

from knowledge_system.processors.hce.schema_validator import (
    SchemaValidator,
    get_validator,
    repair_and_validate_flagship_output,
    repair_and_validate_miner_output,
)


class TestSchemaLoading:
    """Test schema loading and initialization."""

    def test_load_schemas_from_root(self, monkeypatch):
        """Test loading schemas from root schemas directory."""
        # Create mock schema directory
        mock_root = Path("/mock/root")
        schema_dir = mock_root / "schemas"

        def mock_exists(self):
            return str(self) == str(schema_dir)

        def mock_glob(self, pattern):
            if str(self) == str(schema_dir) and pattern == "*.json":
                return [
                    Path(schema_dir / "miner_input.v1.json"),
                    Path(schema_dir / "miner_output.v1.json"),
                ]
            return []

        monkeypatch.setattr(Path, "exists", mock_exists)
        monkeypatch.setattr(Path, "glob", mock_glob)

        # Mock file reading
        def mock_open(path, *args, **kwargs):
            if "miner_input" in str(path):
                content = '{"type": "object", "properties": {}}'
            else:
                content = '{"type": "object", "properties": {}}'

            from io import StringIO

            return StringIO(content)

        monkeypatch.setattr("builtins.open", mock_open)

        validator = SchemaValidator()

        # Should have loaded versioned and base names
        assert "miner_input.v1" in validator.schemas
        assert "miner_input" in validator.schemas
        assert "miner_output.v1" in validator.schemas
        assert "miner_output" in validator.schemas


class TestMinerValidation:
    """Test miner schema validation."""

    @pytest.fixture
    def validator(self):
        """Create validator with actual schemas loaded from files."""
        # Use the real validator which loads schemas from the schemas directory
        return get_validator()

    def test_validate_miner_input_valid(self, validator, sample_miner_input_v2):
        """Test validating valid miner input."""
        is_valid, errors = validator.validate(sample_miner_input_v2, "miner_input")
        assert is_valid, f"Validation failed with errors: {errors}"
        assert not errors

    def test_validate_miner_input_invalid(self, validator):
        """Test validating invalid miner input."""
        invalid_input = {"wrong_field": "value"}
        is_valid, errors = validator.validate(invalid_input, "miner_input")
        assert not is_valid
        assert errors

    def test_validate_miner_output_valid(self, validator, sample_miner_output_v2):
        """Test validating valid miner output."""
        is_valid, errors = validator.validate(sample_miner_output_v2, "miner_output")
        assert is_valid, f"Validation failed with errors: {errors}"
        assert not errors

    def test_validate_miner_output_invalid(self, validator):
        """Test validating invalid miner output."""
        # Missing required fields
        invalid_output = {"claims": []}
        is_valid, errors = validator.validate(invalid_output, "miner_output")
        assert not is_valid
        assert any(
            "jargon" in str(e) or "people" in str(e) or "mental_models" in str(e)
            for e in errors
        )


class TestFlagshipValidation:
    """Test flagship schema validation."""

    @pytest.fixture
    def validator(self):
        """Create validator with actual schemas loaded from files."""
        return get_validator()

    def test_validate_flagship_input_valid(self, validator, sample_flagship_input_v2):
        """Test validating valid flagship input."""
        is_valid, errors = validator.validate(
            sample_flagship_input_v2, "flagship_input"
        )
        assert is_valid, f"Validation failed with errors: {errors}"
        assert not errors

    def test_validate_flagship_output_valid(self, validator, sample_flagship_output_v2):
        """Test validating valid flagship output."""
        is_valid, errors = validator.validate(
            sample_flagship_output_v2, "flagship_output"
        )
        assert is_valid, f"Validation failed with errors: {errors}"
        assert not errors


class TestSchemaRepairOld:
    """Test schema repair functionality (old tests - keeping for reference)."""

    @pytest.fixture
    def validator(self):
        """Create validator with test schemas."""
        validator = SchemaValidator()
        # Add test schemas
        validator.schemas["flagship_input"] = {
            "type": "object",
            "required": ["content_summary", "claims_to_evaluate"],
            "properties": {
                "content_summary": {"type": "string"},
                "claims_to_evaluate": {"type": "array"},
            },
        }
        validator.schemas["flagship_output"] = {
            "type": "object",
            "required": ["evaluated_claims", "summary_assessment"],
            "properties": {
                "evaluated_claims": {"type": "array"},
                "summary_assessment": {"type": "object"},
            },
        }
        return validator


class TestSchemaRepair:
    """Test schema repair functionality."""

    @pytest.fixture
    def validator(self):
        """Create validator with repair logic."""
        validator = SchemaValidator()
        validator.schemas["miner_output"] = {
            "type": "object",
            "required": ["claims", "jargon", "people", "mental_models"],
            "properties": {
                "claims": {"type": "array", "items": {"type": "object"}},
                "jargon": {"type": "array", "items": {"type": "object"}},
                "people": {"type": "array", "items": {"type": "object"}},
                "mental_models": {"type": "array", "items": {"type": "object"}},
            },
        }
        return validator

    def test_repair_missing_fields(self, validator):
        """Test repairing missing required fields."""
        broken_output = {"claims": [{"text": "test claim"}]}

        repaired, is_valid, errors = validator.repair_and_validate(
            broken_output, "miner_output"
        )

        assert is_valid
        assert "jargon" in repaired
        assert "people" in repaired
        assert "mental_models" in repaired
        assert isinstance(repaired["jargon"], list)

    def test_repair_wrong_types(self, validator):
        """Test repairing wrong field types."""
        broken_output = {
            "claims": "not a list",  # Should be array
            "jargon": None,  # Should be array
            "people": {},  # Should be array
            "mental_models": 123,  # Should be array
        }

        repaired, is_valid, errors = validator.repair_and_validate(
            broken_output, "miner_output"
        )

        assert is_valid
        assert isinstance(repaired["claims"], list)
        assert isinstance(repaired["jargon"], list)
        assert isinstance(repaired["people"], list)
        assert isinstance(repaired["mental_models"], list)

    def test_repair_preserves_valid_data(self, validator, sample_miner_output):
        """Test that repair preserves valid data."""
        # Remove one field
        broken = sample_miner_output.copy()
        del broken["mental_models"]

        repaired, is_valid, errors = validator.repair_and_validate(
            broken, "miner_output"
        )

        assert is_valid
        # Original data preserved
        assert repaired["claims"] == sample_miner_output["claims"]
        assert repaired["jargon"] == sample_miner_output["jargon"]
        assert repaired["people"] == sample_miner_output["people"]
        # Missing field added
        assert "mental_models" in repaired


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_repair_and_validate_miner(self):
        """Test convenience function for miner output."""
        broken_output = {"claims": []}

        with pytest.MonkeyPatch.context() as m:
            # Mock validator
            mock_validator = SchemaValidator()
            mock_validator.schemas["miner_output"] = {
                "type": "object",
                "required": ["claims", "jargon", "people", "mental_models"],
            }
            m.setattr(
                "knowledge_system.processors.hce.schema_validator._validator",
                mock_validator,
            )

            repaired, is_valid, errors = repair_and_validate_miner_output(broken_output)

            assert "jargon" in repaired
            assert "people" in repaired
            assert "mental_models" in repaired

    def test_repair_and_validate_flagship(self):
        """Test convenience function for flagship output."""
        broken_output = {"evaluated_claims": []}

        with pytest.MonkeyPatch.context() as m:
            # Mock validator
            mock_validator = SchemaValidator()
            mock_validator.schemas["flagship_output"] = {
                "type": "object",
                "required": ["evaluated_claims", "summary_assessment"],
            }
            m.setattr(
                "knowledge_system.processors.hce.schema_validator._validator",
                mock_validator,
            )

            repaired, is_valid, errors = repair_and_validate_flagship_output(
                broken_output
            )

            assert "summary_assessment" in repaired


class TestSchemaEvolution:
    """Test handling of schema versions."""

    def test_version_compatibility(self):
        """Test that versioned and base schemas work together."""
        validator = SchemaValidator()

        # Add v1 schema
        validator.schemas["test_schema.v1"] = {
            "type": "object",
            "properties": {"version": {"const": 1}},
        }
        validator.schemas["test_schema"] = validator.schemas["test_schema.v1"]

        # Validate against base name
        is_valid, _ = validator.validate({"version": 1}, "test_schema")
        assert is_valid

        # Validate against versioned name
        is_valid, _ = validator.validate({"version": 1}, "test_schema.v1")
        assert is_valid


# Import fixtures
from tests.fixtures.system2_fixtures import (
    sample_flagship_input,
    sample_flagship_output,
    sample_miner_input,
    sample_miner_output,
)
