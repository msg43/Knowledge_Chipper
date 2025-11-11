# Schema V2 Migration - Full Alignment

## Problem

Schema validation was failing for mental models with the error:

```
WARNING | Structured JSON generation failed, falling back: Schema validation failed for miner_output: 
'description' is a required property

Failed validating 'required' in schema['properties']['mental_models']['items']:
    {'type': 'object',
     'required': ['name', 'description'],
     ...
```

The LLM was correctly generating mental models with a `definition` field, but the v1 schema was expecting `description`.

## Root Cause

There was an inconsistency between schema versions and prompt examples:

1. **`miner_output.v1.json`** (line 102): Required field was `description`
2. **`miner_output.v2.json`** (line 216): Required field was `definition`
3. **Prompt specification** (unified_miner.txt line 114): Instructed LLMs to use `definition`
4. **Prompt examples** (unified_miner.txt lines 313, 326, 339): Showed `description`

The LLM followed the field specification (`definition`) but the validator was using v1 schema which expected `description`, causing validation failures.

## Solution

### 1. Full V2 Migration

**Completely replaced `schemas/miner_output.v1.json` with v2 structure** to eliminate all transformation needs:

**Before (v1 - flat structure):**
```json
"mental_models": {
  "required": ["name", "description"],
  "properties": {
    "name": "...",
    "description": "...",  // ❌ Wrong field name
    "context_quote": "...",  // ❌ Flat structure
    "timestamp": "..."       // ❌ Single timestamp
  }
}
```

**After (v1 = v2 - nested structure):**
```json
"mental_models": {
  "required": ["name", "definition", "evidence_spans"],
  "properties": {
    "name": "...",
    "definition": "...",     // ✅ Correct field name
    "aliases": [],           // ✅ Added
    "evidence_spans": [{     // ✅ Nested evidence
      "segment_id": "...",
      "quote": "...",
      "t0": "...",
      "t1": "...",
      "context_text": "...",
      "context_type": "exact|extended|segment"
    }]
  }
}
```

**This applies to ALL entity types:**
- **Claims**: Now require `evidence_spans` (not flat `timestamp`/`evidence_quote`)
- **Jargon**: Now require `evidence_spans` (not flat `context_quote`/`timestamp`)
- **People**: Now require `mentions` array (not flat `context_quote`/`timestamp`)
- **Mental Models**: Now require `evidence_spans` + `definition` (not `description`)

### 2. Updated Prompts

Updated all prompt examples to use `definition` consistently:

- `src/knowledge_system/processors/hce/prompts/unified_miner.txt`
- `src/knowledge_system/processors/hce/prompts/unified_miner_moderate.txt`
- `src/knowledge_system/processors/hce/prompts/unified_miner_liberal.txt`
- `src/knowledge_system/processors/hce/prompts/unified_miner_conservative.txt`

Changed all mental model examples from:
```json
{"name": "Circle of Competence", "description": "..."}
```

To:
```json
{"name": "Circle of Competence", "definition": "..."}
```

### 3. Existing Repair Logic

The repair logic in `schema_validator.py` (lines 417-421) already handles backward compatibility:

```python
# Ensure definition exists (rename from description if needed)
if "definition" not in model and "description" in model:
    model["definition"] = model.pop("description")
elif "definition" not in model:
    model["definition"] = ""
```

This automatically converts old data with `description` to the new `definition` field.

## Impact

- **✅ No transformation needed**: v1 = v2, so LLM output validates directly without repair
- **✅ Prompt alignment**: Prompts already instructed v2 format, now schema matches
- **✅ Forward compatibility**: All new extractions use full evidence structure
- **✅ Backward compatibility**: Repair logic still converts old flat data to nested structure
- **✅ Consistency**: All schemas, prompts, and code now aligned on v2 format
- **✅ No data loss**: Existing data in database is unaffected

## Files Changed

1. `schemas/miner_output.v1.json` - **Completely replaced with v2 structure** (contains nested evidence_spans, definition field)
2. `schemas/miner_output.v2.json` - **DELETED** (was redundant duplicate of v1)
3. `src/knowledge_system/utils/pydantic_models.py` - Pydantic MentalModel class updated to use `definition`
4. `knowledge_chipper_oauth/getreceipts_uploader.py` - Updated to try `definition` first, fall back to `description` for backward compatibility
5. `src/knowledge_system/processors/hce/prompts/unified_miner.txt` - Prompt examples
6. `src/knowledge_system/processors/hce/prompts/unified_miner_moderate.txt` - Prompt examples
7. `src/knowledge_system/processors/hce/prompts/unified_miner_liberal.txt` - Prompt examples
8. `src/knowledge_system/processors/hce/prompts/unified_miner_conservative.txt` - Prompt examples

## Note on File Naming

The file is named `miner_output.v1.json` but contains the v2 structure. This is because:
- The validator is hardcoded to look for `.v1` files first (line 101 in `schema_validator.py`)
- Other schemas also use `.v1` naming (`flagship_output.v1.json`, etc.)
- To maintain consistency, we kept the `.v1` filename but updated its contents to v2 structure
- The separate `.v2.json` file was deleted as it was a redundant copy

Think of it as: **"v1 file, v2 content"**

## Testing

The fix should eliminate ALL schema validation warnings. The LLM generates v2 format (as instructed by prompts), which now validates directly against v1 schema without any transformation.

## Why This Matters

**Before:** Prompts told LLM to generate v2, but validator expected v1, causing:
- Validation failures
- Unnecessary repair transformations
- Inconsistent data structures

**After:** v1 = v2, so:
- LLM output validates immediately
- No transformation overhead
- Clean, consistent data pipeline
- Future-proof (no migration needed)
