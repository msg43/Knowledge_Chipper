# System 2 JSON Schemas

This directory contains JSON schemas for validating LLM inputs and outputs in the System 2 architecture.

## Schema Files

### Mining Pipeline
- `miner_input.v1.json` - Input format for the Unified Miner that extracts claims, jargon, people, and mental models
- `miner_output.v1.json` - Output format from the Unified Miner

### Evaluation Pipeline  
- `flagship_input.v1.json` - Input format for the Flagship Evaluator that ranks and scores claims
- `flagship_output.v1.json` - Output format from the Flagship Evaluator

## Versioning

Schemas use semantic versioning (v1, v2, etc.) to support evolution while maintaining backwards compatibility.

## Schema Validation

The schemas are used by:
1. `src/knowledge_system/processors/hce/schema_validator.py` - Runtime validation with repair
2. LLM adapters for structured output generation (when supported)
3. Test fixtures for ensuring data consistency

## Key Features

### Miner Schemas
- Extracts claims with types (factual, causal, normative, forecast, definition)
- Captures speaker stance (asserts, questions, opposes, neutral)
- Includes evidence spans with timestamps
- Extracts jargon, people mentions, and mental models

### Flagship Schemas
- Evaluates claims for intellectual significance
- Scores on importance (0-10), novelty (0-10), confidence (0-10)
- Supports accept/reject/merge/split decisions
- Assigns quality tiers (A, B, C) based on scores
- Provides summary assessment of extraction quality

## Usage Example

```python
from knowledge_system.processors.hce.schema_validator import SchemaValidator

validator = SchemaValidator()

# Validate miner output
is_valid, errors = validator.validate_miner_output(miner_result)
if not is_valid:
    repaired = validator.repair_miner_output(miner_result)

# Validate flagship output  
is_valid, errors = validator.validate_flagship_output(evaluator_result)
```

## Schema Evolution

When updating schemas:
1. Create a new version (e.g., `miner_input.v2.json`)
2. Update the validator to support both versions
3. Add migration logic if needed
4. Update this README with changes
