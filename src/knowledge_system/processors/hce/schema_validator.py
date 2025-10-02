"""
JSON Schema validation for unified HCE pipeline outputs.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import jsonschema
    from jsonschema import validate

    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False


class SchemaValidator:
    """Validates JSON outputs against schemas."""

    def __init__(self):
        self.schemas = {}
        self._load_schemas()

    def _load_schemas(self):
        """Load all JSON schemas from the schemas directory."""
        schema_dir = Path(__file__).parent / "schemas"

        if not schema_dir.exists():
            return

        for schema_file in schema_dir.glob("*.json"):
            try:
                schema_name = schema_file.stem
                with open(schema_file) as f:
                    self.schemas[schema_name] = json.load(f)
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
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

        if schema_name not in self.schemas:
            return False, [f"Schema '{schema_name}' not found"]

        try:
            validate(instance=data, schema=self.schemas[schema_name])
            return True, []
        except jsonschema.ValidationError as e:
            return False, [str(e)]
        except Exception as e:
            return False, [f"Validation error: {e}"]

    def validate_miner_output(self, data: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate unified miner output."""
        return self.validate(data, "miner_output")

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
