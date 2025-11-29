"""
JSON Schema validation for unified HCE pipeline outputs.

Includes automatic repair functionality and proper error handling
per System 2 specifications.
"""

import json
import logging
from pathlib import Path
from typing import Any

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

        # Load all schemas first, then prioritize flat schemas
        schema_files = list(schema_dir.glob("*.json"))
        # Sort so _flat schemas are processed LAST (they override non-flat)
        schema_files.sort(key=lambda f: (0 if "_flat" in f.stem else 1, f.stem))

        for schema_file in schema_files:
            try:
                # Handle versioned schema names (e.g., miner_output.v1.json, miner_output_flat.v1.json)
                schema_name = schema_file.stem  # e.g., "miner_output_flat.v1"

                with open(schema_file) as f:
                    schema_content = json.load(f)
                    self.schemas[schema_name] = schema_content

                    # Also store without version for backward compatibility
                    # e.g., "miner_output.v1" -> "miner_output", "miner_output_flat.v1" -> "miner_output_flat"
                    base_name = schema_name.split(".")[0]
                    if base_name != schema_name:
                        self.schemas[base_name] = schema_content

                    # PRIORITY: If this is a _flat schema, use it as the DEFAULT for the base name
                    # e.g., "miner_output_flat.v1" -> also store as "miner_output" (overriding old schema)
                    if "_flat" in base_name:
                        default_name = base_name.replace("_flat", "")
                        self.schemas[default_name] = schema_content
                        logger.info(
                            f"✓ FLAT schema loaded: {schema_name} → default for '{default_name}'"
                        )
                    else:
                        logger.debug(
                            f"Loaded schema: {schema_name} (also as {base_name})"
                        )
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
            logger.debug(f"Successfully repaired {schema_name} data")
            # Log the diff for debugging
            self._log_repair_diff(data, repaired_data)
        else:
            # If repair failed, raise high severity error
            # Ensure all errors are strings before joining
            error_strings = [str(e) for e in errors]
            raise KnowledgeSystemError(
                f"Schema validation failed for {schema_name}: {'; '.join(error_strings)}",
                error_code=ErrorCode.VALIDATION_SCHEMA_ERROR_HIGH,
            )

        return repaired_data, is_valid, errors

    def _attempt_repair(self, data: dict[str, Any], schema_name: str) -> dict[str, Any]:
        """Attempt to repair common JSON issues."""
        repaired = data.copy()

        if schema_name in ["miner_output", "miner_output.v1", "miner_output.v2"]:
            # Ensure all required arrays exist
            for key in ["claims", "jargon", "people", "mental_models"]:
                if key not in repaired:
                    repaired[key] = []
                elif not isinstance(repaired[key], list):
                    repaired[key] = []

            # Repair incomplete items within arrays
            # Claims: ensure evidence_spans exists
            if "claims" in repaired and isinstance(repaired["claims"], list):
                for claim in repaired["claims"]:
                    if isinstance(claim, dict):
                        # V2 SCHEMA: Ensure evidence_spans array exists
                        if "evidence_spans" not in claim:
                            # Try to migrate from v1 flat structure
                            if "timestamp" in claim or "evidence_quote" in claim:
                                claim["evidence_spans"] = [
                                    {
                                        "segment_id": claim.get(
                                            "segment_id", "unknown"
                                        ),
                                        "quote": claim.get("evidence_quote", ""),
                                        "t0": claim.get(
                                            "timestamp",
                                            claim.get("evidence_timestamp", "00:00"),
                                        ),
                                        "t1": claim.get(
                                            "evidence_timestamp",
                                            claim.get("timestamp", "00:00"),
                                        ),
                                        "context_type": "exact",
                                    }
                                ]
                                # Remove old v1 fields
                                claim.pop("timestamp", None)
                                claim.pop("evidence_quote", None)
                                claim.pop("evidence_timestamp", None)
                            else:
                                claim["evidence_spans"] = []

                        # Ensure each evidence span has required fields
                        if isinstance(claim.get("evidence_spans"), list):
                            for evidence in claim["evidence_spans"]:
                                if isinstance(evidence, dict):
                                    if "segment_id" not in evidence:
                                        evidence["segment_id"] = "unknown"
                                    if "context_type" not in evidence:
                                        evidence["context_type"] = "exact"
                                    # Fix invalid context_type values
                                    elif evidence["context_type"] not in [
                                        "exact",
                                        "extended",
                                        "segment",
                                    ]:
                                        # Map common invalid values to valid ones
                                        context_type_map = {
                                            "sentence": "exact",
                                            "paragraph": "extended",
                                            "full": "segment",
                                            "partial": "exact",
                                            "complete": "segment",
                                        }
                                        evidence["context_type"] = context_type_map.get(
                                            evidence["context_type"], "exact"
                                        )

                        # Fix invalid claim types
                        if "claim_type" in claim:
                            valid_types = [
                                "factual",
                                "causal",
                                "normative",
                                "forecast",
                                "definition",
                            ]
                            if claim["claim_type"] not in valid_types:
                                # Map common alternatives
                                type_map = {
                                    "predictive": "forecast",
                                    "evaluative": "normative",
                                    "descriptive": "factual",
                                    "analytical": "causal",
                                    "assertion": "factual",
                                    "assumption": "normative",
                                }
                                claim["claim_type"] = type_map.get(
                                    claim["claim_type"], "factual"
                                )

                        # Fix invalid stance values
                        if "stance" in claim:
                            valid_stances = [
                                "asserts",
                                "questions",
                                "opposes",
                                "neutral",
                            ]
                            if claim["stance"] not in valid_stances:
                                # Map common alternatives
                                stance_map = {
                                    "positive": "asserts",
                                    "negative": "opposes",
                                    "suggests": "asserts",
                                    "supports": "asserts",
                                    "rejects": "opposes",
                                    "denies": "opposes",
                                    "inquires": "questions",
                                    "asks": "questions",
                                    "uncertain": "neutral",
                                    "ambiguous": "neutral",
                                }
                                claim["stance"] = stance_map.get(
                                    claim["stance"], "neutral"
                                )

                        # Ensure domain exists (required field)
                        if "domain" not in claim:
                            claim["domain"] = "general"

            # People: ensure required fields exist (v2 schema)
            if "people" in repaired and isinstance(repaired["people"], list):
                for person in repaired["people"]:
                    if isinstance(person, dict):
                        # V2 SCHEMA: Ensure mentions array exists
                        if "mentions" not in person:
                            # Try to migrate from v1 flat structure
                            if "context_quote" in person or "timestamp" in person:
                                person["mentions"] = [
                                    {
                                        "segment_id": person.get(
                                            "segment_id", "unknown"
                                        ),
                                        "surface_form": person.get("name", ""),
                                        "quote": person.get(
                                            "context_quote", person.get("name", "")
                                        ),
                                        "t0": person.get("timestamp", "00:00"),
                                        "t1": person.get("timestamp", "00:00"),
                                    }
                                ]
                                # Remove old v1 fields
                                person.pop("context_quote", None)
                                person.pop("timestamp", None)
                            else:
                                person["mentions"] = []

                        # Ensure normalized_name exists
                        if "normalized_name" not in person:
                            person["normalized_name"] = person.get("name", "Unknown")

                        # Ensure entity_type exists and is valid
                        if "entity_type" not in person:
                            person["entity_type"] = "person"
                        elif person["entity_type"] not in ["person", "organization"]:
                            # Fix invalid entity_type values (e.g., "event", "concept", etc.)
                            # Map common invalid values to valid ones
                            entity_type_map = {
                                "event": "person",  # Events shouldn't be in people array, but default to person
                                "concept": "person",
                                "place": "organization",  # Places often function like organizations
                                "location": "organization",
                                "thing": "organization",
                                "object": "organization",
                            }
                            original_type = person["entity_type"]
                            person["entity_type"] = entity_type_map.get(
                                person["entity_type"], "person"
                            )
                            logger.debug(
                                f"Repaired invalid entity_type '{original_type}' to '{person['entity_type']}' "
                                f"for person '{person.get('name', 'unknown')}'"
                            )

                        # Ensure confidence exists
                        if "confidence" not in person:
                            person["confidence"] = 0.8

            # Jargon: ensure required fields exist (v2 schema)
            if "jargon" in repaired and isinstance(repaired["jargon"], list):
                for term in repaired["jargon"]:
                    if isinstance(term, dict):
                        # V2 SCHEMA: Ensure evidence_spans array exists
                        if "evidence_spans" not in term:
                            # Try to migrate from v1 flat structure
                            if "context_quote" in term or "timestamp" in term:
                                term["evidence_spans"] = [
                                    {
                                        "segment_id": term.get("segment_id", "unknown"),
                                        "quote": term.get(
                                            "context_quote", term.get("term", "")
                                        ),
                                        "t0": term.get("timestamp", "00:00"),
                                        "t1": term.get("timestamp", "00:00"),
                                        "context_type": "exact",
                                    }
                                ]
                                # Remove old v1 fields
                                term.pop("context_quote", None)
                                term.pop("timestamp", None)
                            else:
                                term["evidence_spans"] = []

                        # Fix invalid context_type in evidence spans
                        if isinstance(term.get("evidence_spans"), list):
                            for evidence in term["evidence_spans"]:
                                if isinstance(evidence, dict):
                                    if "context_type" not in evidence:
                                        evidence["context_type"] = "exact"
                                    elif evidence["context_type"] not in [
                                        "exact",
                                        "extended",
                                        "segment",
                                    ]:
                                        context_type_map = {
                                            "sentence": "exact",
                                            "paragraph": "extended",
                                            "full": "segment",
                                            "partial": "exact",
                                            "complete": "segment",
                                        }
                                        evidence["context_type"] = context_type_map.get(
                                            evidence["context_type"], "exact"
                                        )

                        # Ensure domain exists (no validation - free-form string)
                        if "domain" not in term:
                            term["domain"] = "general"

            # Mental models: ensure required fields exist (v2 schema)
            if "mental_models" in repaired and isinstance(
                repaired["mental_models"], list
            ):
                for model in repaired["mental_models"]:
                    if isinstance(model, dict):
                        # V2 SCHEMA: Ensure evidence_spans array exists
                        if "evidence_spans" not in model:
                            # Try to migrate from v1 flat structure
                            if "context_quote" in model or "timestamp" in model:
                                model["evidence_spans"] = [
                                    {
                                        "segment_id": model.get(
                                            "segment_id", "unknown"
                                        ),
                                        "quote": model.get(
                                            "context_quote", model.get("name", "")
                                        ),
                                        "t0": model.get("timestamp", "00:00"),
                                        "t1": model.get("timestamp", "00:00"),
                                        "context_type": "exact",
                                    }
                                ]
                                # Remove old v1 fields
                                model.pop("context_quote", None)
                                model.pop("timestamp", None)
                            else:
                                model["evidence_spans"] = []

                        # Fix invalid context_type in evidence spans
                        if isinstance(model.get("evidence_spans"), list):
                            for evidence in model["evidence_spans"]:
                                if isinstance(evidence, dict):
                                    if "context_type" not in evidence:
                                        evidence["context_type"] = "exact"
                                    elif evidence["context_type"] not in [
                                        "exact",
                                        "extended",
                                        "segment",
                                    ]:
                                        context_type_map = {
                                            "sentence": "exact",
                                            "paragraph": "extended",
                                            "full": "segment",
                                            "partial": "exact",
                                            "complete": "segment",
                                        }
                                        evidence["context_type"] = context_type_map.get(
                                            evidence["context_type"], "exact"
                                        )

                        # Ensure definition exists (rename from description if needed)
                        if "definition" not in model and "description" in model:
                            model["definition"] = model.pop("description")
                        elif "definition" not in model:
                            model["definition"] = ""

                        # Ensure aliases exists
                        if "aliases" not in model:
                            model["aliases"] = []

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

            # Add placeholder ranks for rejected/merged/split claims
            # Only accepted claims should have meaningful ranks, but we add
            # a sentinel value (999) for rejected claims for backwards compatibility
            if "evaluated_claims" in repaired and isinstance(
                repaired["evaluated_claims"], list
            ):
                for claim in repaired["evaluated_claims"]:
                    if isinstance(claim, dict):
                        decision = claim.get("decision", "reject")
                        # If rank is missing and claim is not accepted, add placeholder
                        if "rank" not in claim:
                            if decision == "accept":
                                # Accepted claims without rank get a default rank
                                claim["rank"] = 999
                            else:
                                # Rejected/merged/split claims get sentinel rank
                                claim["rank"] = 999

            # Repair invalid overall_quality values
            if "summary_assessment" in repaired and isinstance(
                repaired["summary_assessment"], dict
            ):
                quality = repaired["summary_assessment"].get("overall_quality")
                valid_qualities = ["high", "medium", "low"]

                if quality not in valid_qualities:
                    # Map common invalid values to valid ones
                    quality_map: dict[str, str] = {
                        "good": "high",
                        "excellent": "high",
                        "great": "high",
                        "fair": "medium",
                        "average": "medium",
                        "moderate": "medium",
                        "poor": "low",
                        "bad": "low",
                        "weak": "low",
                        "no_claims": "low",
                        "error": "low",
                        "unknown": "medium",
                    }
                    # Ensure quality is a string before using it as a key
                    quality_str = str(quality) if quality is not None else "unknown"
                    repaired["summary_assessment"]["overall_quality"] = quality_map.get(
                        quality_str, "medium"
                    )
                    logger.debug(
                        f"Repaired overall_quality from '{quality}' to '{repaired['summary_assessment']['overall_quality']}'"
                    )

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
    data: dict[str, Any],
) -> tuple[dict[str, Any], bool, list[str]]:
    """Repair and validate miner output."""
    return get_validator().repair_and_validate(data, "miner_output")


def repair_and_validate_flagship_output(
    data: dict[str, Any],
) -> tuple[dict[str, Any], bool, list[str]]:
    """Repair and validate flagship output."""
    return get_validator().repair_and_validate(data, "flagship_output")
