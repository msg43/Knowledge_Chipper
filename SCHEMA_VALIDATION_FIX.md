# Schema Validation Error Fix

**Date**: 2025-11-08  
**Issue**: LLM-generated JSON failing schema validation due to enum mismatches

## Problem

The unified miner was generating valid, semantically correct values that were being rejected by the JSON schema validator:

1. **`context_type` enum mismatch**: Schema defined `["exact", "sentence", "paragraph"]` but database expected `["exact", "extended", "segment"]`
2. **`domain` enum too restrictive**: Only 7 domains allowed, causing LLM to generate values like:
   - `"politics"` → rejected
   - `"AI"` → rejected  
   - `"cybersecurity and internet policy"` → rejected

### Example Errors

```
'politics' is not one of ['economics', 'technology', 'medical', 'legal', 'scientific', 'business', 'other']
'extended' is not one of ['exact', 'sentence', 'paragraph']
'cybersecurity and internet policy' is not one of ['economics', 'technology', 'medical', 'legal', 'scientific', 'business', 'other']
'AI' is not one of ['economics', 'technology', 'medical', 'legal', 'scientific', 'business', 'other']
```

## Root Cause

The JSON schema file (`schemas/miner_output.v1.json`) had two issues:

1. **Wrong enum values**: The `context_type` enum didn't match the database schema constraints
2. **Insufficient domain coverage**: Only 7 domains defined when content spans many more fields

## Solution

### 1. Fixed `context_type` Enum

**File**: `schemas/miner_output.v1.json` (line 68)

**Before**:
```json
"context_type": {
  "type": "string",
  "enum": ["exact", "sentence", "paragraph"],
  "description": "Type of context provided",
  "default": "exact"
}
```

**After**:
```json
"context_type": {
  "type": "string",
  "enum": ["exact", "extended", "segment"],
  "description": "Type of context provided",
  "default": "exact"
}
```

This now matches the database schema constraints defined in:
- `src/knowledge_system/database/models.py` (line 852)
- `src/knowledge_system/database/migrations/claim_centric_schema.sql` (line 197)
- `src/knowledge_system/processors/hce/sqlite_schema.sql` (line 82)

### 2. Removed Domain Enum Constraint

**File**: `schemas/miner_output.v1.json` (line 93-96)

**Before**:
```json
"domain": {
  "type": "string",
  "enum": ["economics", "technology", "medical", "legal", "scientific", "business", "other"],
  "description": "Domain or field this jargon belongs to"
}
```

**After**:
```json
"domain": {
  "type": "string",
  "description": "Domain or field this jargon belongs to (e.g., 'constitutional law', 'quantum mechanics', 'behavioral economics')"
}
```

**Rationale**: The enum constraint was artificially limiting the LLM's ability to accurately describe domains. Jargon terms should be categorized by their actual field (e.g., "quantum mechanics", "constitutional law", "behavioral economics") rather than forced into predefined buckets. This allows natural, accurate domain classification that reflects the content.

### 3. Simplified Schema Validator

**File**: `src/knowledge_system/processors/hce/schema_validator.py` (lines 362-364)

Removed complex domain mapping logic. Now simply ensures the field exists:

```python
# Ensure domain exists (no validation - free-form string)
if "domain" not in term:
    term["domain"] = "general"
```

The validator no longer attempts to normalize or map domain values - it accepts whatever the LLM determines is the most accurate domain description.

## Testing

Created and ran comprehensive tests to verify the fix:

```bash
✓ Context type repair: 'sentence' → 'exact'
✓ Domain values now accepted as-is: 'AI', 'politics', 'cybersecurity and internet policy'
✓ Context type preservation: 'extended' → 'extended' (preserved)
```

## Impact

### Before
- LLM-generated valid semantic values were rejected
- Fallback to unstructured JSON parsing
- Loss of schema validation benefits
- Frequent validation errors in logs

### After
- Schema accepts any domain value the LLM provides
- No artificial constraints on domain categorization
- LLM can accurately describe specialized fields (e.g., "quantum mechanics", "constitutional law")
- Reduced reliance on fallback mechanisms
- Cleaner logs with fewer validation warnings

## Files Modified

1. `schemas/miner_output.v1.json` - Fixed `context_type` enum, removed `domain` enum constraint
2. `src/knowledge_system/processors/hce/schema_validator.py` - Simplified domain validation (free-form string)
3. `CHANGELOG.md` - Documented the fix

## Related Documentation

- Database schema: `src/knowledge_system/database/models.py`
- SQL migrations: `src/knowledge_system/database/migrations/claim_centric_schema.sql`
- HCE schema: `src/knowledge_system/processors/hce/sqlite_schema.sql`
- Schema audit: `docs/UNIFIED_MINER_AUDIT.md`
