# ADR-003: JSON Schema Validation with Automatic Repair

## Status
Accepted

## Context
LLM outputs can be inconsistent:
- Missing required fields
- Wrong data types
- Structural variations
- Model-specific formatting quirks

Strict validation would reject many otherwise usable responses, while no validation risks data corruption.

## Decision
Implement two-tier validation:
1. **Strict validation** to detect issues
2. **Automatic repair** for common problems
3. **Fail with clear errors** only for unfixable issues
4. **Version schemas** for future evolution

## Repair Strategy

### Repairable Issues
- Missing array fields → Initialize as empty arrays
- Wrong types for arrays → Convert to empty arrays
- Missing summary assessment → Create minimal valid structure
- null values in required fields → Use type-appropriate defaults

### Non-Repairable Issues
- Completely invalid structure
- Missing critical nested data
- Incompatible schema versions

## Consequences

### Positive
- **Higher success rate** for LLM outputs
- **Graceful degradation** instead of hard failures
- **Clear error messages** when repair impossible
- **Forward compatibility** via versioning

### Negative
- **Hidden data loss** if repair is too aggressive
- **Complexity** in repair logic
- **Testing burden** for edge cases

### Neutral
- Repair actions are logged for debugging
- Original data preserved in LLM response table

## Implementation

```python
def repair_and_validate_miner_output(data):
    # Try validation first
    is_valid, errors = validate_miner_output(data)
    if is_valid:
        return data, True, []
    
    # Attempt repairs
    repaired = data.copy()
    for field in ["claims", "jargon", "people", "mental_models"]:
        if field not in repaired:
            repaired[field] = []
        elif not isinstance(repaired[field], list):
            repaired[field] = []
    
    # Validate repaired data
    is_valid, errors = validate_miner_output(repaired)
    if is_valid:
        logger.info("Successfully repaired miner output")
        return repaired, True, []
    
    # Fail if still invalid
    raise KnowledgeSystemError(
        f"Schema validation failed: {errors}",
        error_code=ErrorCode.VALIDATION_SCHEMA_ERROR_HIGH
    )
```

## Versioning Strategy

Schemas follow semantic versioning:
- `/schemas/miner_output.v1.json` - Current version
- `/schemas/miner_output.v2.json` - Future version
- Code can handle multiple versions for migration
