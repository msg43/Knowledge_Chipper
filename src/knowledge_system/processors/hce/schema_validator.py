"""
JSON Schema validation for unified HCE pipeline outputs.

Includes automatic repair functionality and proper error handling
per System 2 specifications.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import jsonschema
    from jsonschema import validate

    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False

from ...errors import ErrorCode, KnowledgeSystemError

logger = logging.getLogger(__name__)


class SchemaValidator:
    """Validates JSON outputs against schemas with repair functionality."""

    def __init__(self):
        self.schemas = {}
        self._load_schemas()

    def _load_schemas(self):
        """Load all JSON schemas from the root schemas directory."""
        # First try the root schemas directory (System 2 location)
        repo_root = Path(__file__).parent.parent.parent.parent.parent
        schema_dir = repo_root / "schemas"

        # Fallback to local schemas directory if root doesn't exist
        if not schema_dir.exists():
            schema_dir = Path(__file__).parent / "schemas"

        if not schema_dir.exists():
            logger.warning(f"Schema directory not found at {schema_dir}")
            return

        for schema_file in schema_dir.glob("*.json"):
            try:
                # Handle versioned schema names (e.g., miner_output.v1.json)
                schema_name = schema_file.stem  # e.g., "miner_output.v1"

                with open(schema_file) as f:
                    schema_content = json.load(f)
                    self.schemas[schema_name] = schema_content

                    # Also store without version for backward compatibility
                    # e.g., "miner_output.v1" -> "miner_output"
                    base_name = schema_name.split(".")[0]
                    if base_name != schema_name:
                        self.schemas[base_name] = schema_content

                logger.debug(f"Loaded schema: {schema_name} (also as {base_name})")
            except Exception as e:
                logger.warning(f"Failed to load schema {schema_file}: {e}")

    def validate(
        self, data: dict[str, Any], schema_name: str
    ) -> tuple[bool, list[str]]:
        """
        Validate data against a schema.

        Args:
            data: The data to validate
            schema_name: Name of the schema (without .json extension)

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        if not JSONSCHEMA_AVAILABLE:
            return True, [
                "JSON schema validation not available - install jsonschema package"
            ]

        # Try versioned schema first
        versioned_name = f"{schema_name}.v1"
        if versioned_name in self.schemas:
            schema = self.schemas[versioned_name]
        elif schema_name in self.schemas:
            schema = self.schemas[schema_name]
        else:
            return False, [f"Schema '{schema_name}' not found"]

        try:
            validate(instance=data, schema=schema)
            return True, []
        except jsonschema.ValidationError as e:
            return False, [str(e)]
        except Exception as e:
            return False, [f"Validation error: {e}"]

    def repair_and_validate(
        self, data: dict[str, Any], schema_name: str
    ) -> tuple[dict[str, Any], bool, list[str]]:
        """
        Attempt to repair JSON data and validate against schema.

        Args:
            data: The data to validate and potentially repair
            schema_name: Name of the schema

        Returns:
            Tuple of (repaired_data, is_valid, list_of_errors)
        """
        # First try validation as-is
        is_valid, errors = self.validate(data, schema_name)
        if is_valid:
            return data, True, []

        # Attempt repairs based on common issues
        repaired_data = self._attempt_repair(data, schema_name)

        # Validate repaired data
        is_valid, errors = self.validate(repaired_data, schema_name)

        if is_valid:
            logger.info(f"Successfully repaired {schema_name} data")
            # Log the diff for debugging
            self._log_repair_diff(data, repaired_data)
        else:
            # If repair failed, raise high severity error
            raise KnowledgeSystemError(
                f"Schema validation failed for {schema_name}: {'; '.join(errors)}",
                error_code=ErrorCode.VALIDATION_SCHEMA_ERROR_HIGH,
            )

        return repaired_data, is_valid, errors

    def _attempt_repair(self, data: dict[str, Any], schema_name: str) -> dict[str, Any]:
        """Attempt to repair common JSON issues."""
        repaired = data.copy()

        if schema_name in ["miner_output", "miner_output.v1"]:
            # Ensure all required arrays exist
            for key in ["claims", "jargon", "people", "mental_models"]:
                if key not in repaired:
                    repaired[key] = []
                elif not isinstance(repaired[key], list):
                    repaired[key] = []

        elif schema_name in ["flagship_output", "flagship_output.v1"]:
            # Ensure required structure exists
            if "evaluated_claims" not in repaired:
                repaired["evaluated_claims"] = []
            if "summary_assessment" not in repaired:
                repaired["summary_assessment"] = {
                    "total_claims_processed": 0,
                    "claims_accepted": 0,
                    "claims_rejected": 0,
                    "key_themes": [],
                    "overall_quality": "low",
                }

        return repaired

    def _log_repair_diff(self, original: dict[str, Any], repaired: dict[str, Any]):
        """Log the differences between original and repaired data."""
        import difflib
        import json

        original_str = json.dumps(original, indent=2, sort_keys=True)
        repaired_str = json.dumps(repaired, indent=2, sort_keys=True)

        diff = difflib.unified_diff(
            original_str.splitlines(),
            repaired_str.splitlines(),
            fromfile="original",
            tofile="repaired",
            lineterm="",
        )

        diff_text = "\n".join(diff)
        if diff_text:
            logger.debug(f"JSON repair diff:\n{diff_text}")

    def validate_miner_input(self, data: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate unified miner input."""
        return self.validate(data, "miner_input")

    def validate_miner_output(self, data: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate unified miner output."""
        return self.validate(data, "miner_output")

    def validate_flagship_input(self, data: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate flagship evaluator input."""
        return self.validate(data, "flagship_input")

    def validate_flagship_output(self, data: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate flagship evaluator output."""
        return self.validate(data, "flagship_output")


# Global validator instance
_validator = None


def get_validator() -> SchemaValidator:
    """Get the global schema validator instance."""
    global _validator
    if _validator is None:
        _validator = SchemaValidator()
    return _validator


def validate_miner_output(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """Convenience function to validate miner output."""
    return get_validator().validate_miner_output(data)


def validate_flagship_output(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """Convenience function to validate flagship output."""
    return get_validator().validate_flagship_output(data)


def repair_and_validate_miner_output(
    data: dict[str, Any]
) -> tuple[dict[str, Any], bool, list[str]]:
    """Repair and validate miner output."""
    return get_validator().repair_and_validate(data, "miner_output")


def repair_and_validate_flagship_output(
    data: dict[str, Any]
) -> tuple[dict[str, Any], bool, list[str]]:
    """Repair and validate flagship output."""
    return get_validator().repair_and_validate(data, "flagship_output")
