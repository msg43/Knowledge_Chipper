# Fix: JSONEncodedType Double-Deserialization Bug

## Problem

The error occurred when generating summary markdown files:

```
Failed to generate summary markdown for Steve Bannon_ Silicon Valley Is Turning Us Into 'Digital Serfs'_vvj_J2tB2Ag: the JSON object must be str, bytes or bytearray, not dict
```

## Root Cause

SQLAlchemy's `JSONEncodedType` custom type automatically handles JSON serialization/deserialization:
- When **writing** to database: Python dict → JSON string (via `process_bind_param`)
- When **reading** from database: JSON string → Python dict (via `process_result_value`)

The bug was that multiple parts of the codebase were calling `json.loads()` on fields that were already deserialized to Python dicts by SQLAlchemy.

## Fields Affected

All fields using `JSONEncodedType` in `models.py`:
- `summary_metadata_json` (Summary model)
- `hce_data_json` (Summary model)
- `categories_json` (MediaSource model)
- `tags_json` (MediaSource model)
- `related_videos_json` (MediaSource model)
- `channel_stats_json` (MediaSource model)
- `speaker_assignments` (Transcript model)
- `input_urls_json` (Job model)
- `config_json` (Job model)
- And others...

## Files Fixed

### 1. `/src/knowledge_system/services/file_generation.py`

**Line 341** (generate_summary_markdown):
```python
# BEFORE:
hce_data = json.loads(summary.hce_data_json) if summary.hce_data_json else None

# AFTER:
# Note: hce_data_json is a JSONEncodedType field, already deserialized to dict
hce_data = summary.hce_data_json if summary.hce_data_json else None
```

**Line 1164** (generate_claims_report):
```python
# BEFORE:
hce_data = json.loads(summary.hce_data_json)

# AFTER:
# Note: hce_data_json is a JSONEncodedType field, already deserialized to dict
hce_data = summary.hce_data_json
```

**Line 1298** (generate_contradiction_report):
```python
# BEFORE:
hce_data = json.loads(summary.hce_data_json)

# AFTER:
# Note: hce_data_json is a JSONEncodedType field, already deserialized to dict
hce_data = summary.hce_data_json
```

**Line 1389** (generate_evidence_mapping):
```python
# BEFORE:
hce_data = json.loads(summary.hce_data_json)

# AFTER:
# Note: hce_data_json is a JSONEncodedType field, already deserialized to dict
hce_data = summary.hce_data_json
```

### 2. `/src/knowledge_system/gui/tabs/claim_search_tab.py`

**Line 70** (load_claims):
```python
# BEFORE:
hce_data = json.loads(summary.hce_data_json)

# AFTER:
# Note: hce_data_json is a JSONEncodedType field, already deserialized to dict
hce_data = summary.hce_data_json
```

**Line 542** (load_relations):
```python
# BEFORE:
hce_data = json.loads(summary.hce_data_json)

# AFTER:
# Note: hce_data_json is a JSONEncodedType field, already deserialized to dict
hce_data = summary.hce_data_json
```

### 3. `/scripts/validate_hce_migration.py`

**Line 122**:
```python
# BEFORE:
hce_data = json.loads(summary.hce_data_json)

# AFTER:
# Note: hce_data_json is a JSONEncodedType field, already deserialized to dict
hce_data = summary.hce_data_json
```

## Other Fields Not Affected

Note that `processing_metadata_json` in the `SpeakerAssignment` model uses plain `Text` type (not `JSONEncodedType`), so the property methods that manually call `json.loads()` and `json.dumps()` are correct and were not changed.

## Testing

The fix resolves the runtime error. The summary markdown generation should now work correctly for HCE-processed videos.

## Prevention

When working with database models:
1. Check if a field uses `JSONEncodedType` - if so, it's already a Python object
2. Only use `json.loads()` on fields with plain `Text` type that store JSON strings
3. Add comments to clarify when a field is already deserialized

