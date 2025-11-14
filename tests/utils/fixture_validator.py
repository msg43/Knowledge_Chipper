"""
Fixture validation utilities for schema-driven testing.

Ensures test fixtures stay in sync with JSON schemas.
"""
from functools import wraps
from typing import Any, Callable

from knowledge_system.processors.hce.schema_validator import SchemaValidator


class FixtureValidationError(Exception):
    """Raised when a fixture fails schema validation."""
    pass


class SchemaFixtureValidator:
    """Validates test fixtures against JSON schemas."""

    def __init__(self):
        self.validator = SchemaValidator()

    def validate_fixture(self, schema_name: str):
        """
        Decorator to validate fixtures against a schema.

        Usage:
            @pytest.fixture
            @validator.validate_fixture("miner_output.v1")
            def sample_miner_output():
                return {...}
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                data = func(*args, **kwargs)
                is_valid, errors = self.validator.validate(data, schema_name)
                if not is_valid:
                    error_msg = "\n".join(errors)
                    raise FixtureValidationError(
                        f"Fixture '{func.__name__}' invalid for schema '{schema_name}':\n{error_msg}"
                    )
                return data
            return wrapper
        return decorator

    def assert_valid(self, data: Any, schema_name: str, context: str = ""):
        """
        Assert that data is valid against a schema.

        Usage in tests:
            validator.assert_valid(output, "miner_output.v1", "test_mining")
        """
        is_valid, errors = self.validator.validate(data, schema_name)
        if not is_valid:
            error_msg = "\n".join(errors)
            ctx = f" ({context})" if context else ""
            raise AssertionError(
                f"Data invalid for schema '{schema_name}'{ctx}:\n{error_msg}"
            )


# Global validator instance for import
fixture_validator = SchemaFixtureValidator()
