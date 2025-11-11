# Schema Repair: Missing Claim Domain Fix

**Date**: 2025-11-08  
**Issue**: Schema validation failures when LLMs omit required `domain` field from claims

## Problem

The warning message indicated that structured JSON generation was failing and falling back to non-structured mode:

```
WARNING | Structured JSON generation failed, falling back: Schema validation failed for miner_output: 
'domain' is a required property
```

The claim in question was missing the `domain` field:
```json
{
  "claim_text": "the fed is in a bit of a box...",
  "claim_type": "causal",
  "stance": "asserts",
  "evidence_spans": [...]
  // Missing: "domain" field
}
```

## Root Cause

The `domain` field was recently added as a required field for claims in the schema (`schemas/miner_output.v1.json` line 13), and all miner prompts were updated to instruct LLMs to include it. However, the schema repair logic in `schema_validator.py` was not updated to handle cases where LLMs fail to include the domain field.

The repair logic already handled missing domains for **jargon terms** (line 362-364):
```python
# Ensure domain exists (no validation - free-form string)
if "domain" not in term:
    term["domain"] = "general"
```

But it did **not** handle missing domains for **claims**.

## Solution

Added the same repair logic for claims in `src/knowledge_system/processors/hce/schema_validator.py` (after line 274):

```python
# Ensure domain exists (required field)
if "domain" not in claim:
    claim["domain"] = "general"
```

This ensures that when an LLM fails to include the domain field, the repair logic automatically adds a sensible default value of `"general"`, allowing validation to pass and preventing fallback to non-structured JSON generation.

## Testing

Verified the fix with a test case matching the error scenario:

```python
test_data = {
    'claims': [
        {
            'claim_text': 'the fed is in a bit of a box',
            'claim_type': 'causal',
            'stance': 'asserts',
            'evidence_spans': [...]
            # Missing domain field
        }
    ],
    'jargon': [],
    'people': [],
    'mental_models': []
}

repaired, is_valid, errors = repair_and_validate_miner_output(test_data)
# Result: ✓ Validation passed, domain = "general" added
```

## Impact

### Before
- LLMs occasionally omitted the `domain` field from claims
- Schema validation failed with `VALIDATION_SCHEMA_ERROR_HIGH`
- System fell back to non-structured JSON generation
- Warning messages logged but processing continued with repaired data

### After
- Missing `domain` fields are automatically repaired to `"general"`
- Schema validation passes consistently
- Structured JSON generation succeeds
- No fallback needed, cleaner logs

## Design Consistency

This fix maintains consistency with the existing repair logic:
- **Jargon terms**: Missing domain → `"general"`
- **Claims**: Missing domain → `"general"` (now fixed)
- Both use the same default value and repair strategy

## Related Documentation

- `CLAIM_DOMAIN_IMPLEMENTATION.md` - Original domain field implementation
- `schemas/miner_output.v1.json` - Schema requiring domain field
- `src/knowledge_system/processors/hce/prompts/unified_miner.txt` - Prompt instructing LLMs to include domain
