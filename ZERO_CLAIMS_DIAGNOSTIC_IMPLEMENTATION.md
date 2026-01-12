# Zero Claims Diagnostic Implementation

**Created:** January 12, 2026  
**Status:** Complete - Ready for Testing

## Problem

Extractions were completing with status "success" but returning 0 claims, 0 jargon, 0 people, 0 concepts. No error was reported, making it impossible to diagnose the issue.

## Solution

Implemented comprehensive diagnostic logging and hard validation to:
1. Identify the root cause through systematic logging
2. Prevent false success reporting
3. Fail jobs properly when no data is extracted

## Root Cause Possibilities (Ordered by Probability)

1. **LLM API key invalid/missing** - Most common
2. **LLM returning error/refusal instead of JSON** - Second most common
3. **Prompt template malformed/empty** - Variables not substituted
4. **JSON parsing failing silently** - Response valid but structure mismatch
5. **Response structure mismatch** - LLM using different field names
6. **Transcript empty or malformed** - No content to extract from

## Implementation Details

### Phase 1: API Key & LLM Response Validation

**File:** `daemon/services/simple_llm_wrapper.py`

Added after LLM call (line 92):
```python
# Log response details for diagnostics
content = result.get('content', '')
logger.info(f"LLM call successful: {len(content)} chars")
logger.info(f"Response preview (first 500 chars): {content[:500]}")

# Check if response looks like JSON
if content.strip().startswith('{') or '```json' in content:
    logger.info("Response appears to be JSON format")
else:
    logger.warning(f"Response does NOT appear to be JSON! Starts with: {content[:100]}")
```

**What This Catches:**
- API key not working (empty response)
- LLM returning error message instead of JSON
- LLM returning refusal or content policy violation

### Phase 2: Prompt Template Validation

**File:** `src/knowledge_system/processors/two_pass/extraction_pass.py`

Added before LLM call (line 135):
```python
# Validate prompt was properly built
logger.info(f"Prompt built: {len(prompt):,} chars")
logger.info(f"   - Contains transcript: {'{transcript}' not in prompt}")
logger.info(f"   - Contains metadata: title={metadata.get('title', 'N/A')[:50]}")

if len(prompt) < 1000:
    logger.warning(f"Prompt suspiciously short ({len(prompt)} chars)! May be malformed.")

if '{transcript}' in prompt:
    logger.error("CRITICAL: Prompt contains unreplaced {transcript} placeholder!")
    logger.error(f"   Prompt preview: {prompt[:1000]}")
    raise ValueError("Prompt template variables not substituted")
```

**What This Catches:**
- Template file missing or corrupted
- Variables not being substituted
- Empty transcript passed to prompt builder
- Prompt template malformed

### Phase 3: Transcript Validation

**File:** `daemon/services/processing_service.py`

Added before pipeline execution (line 571):
```python
# Validate transcript before processing
if not transcript or len(transcript.strip()) == 0:
    raise Exception("Cannot extract claims: Transcript is empty")

logger.info(f"Transcript ready: {len(transcript):,} chars")
```

**What This Catches:**
- Empty transcript from YouTube service
- Transcript not loaded from database
- File read failure

### Phase 4: Hard Validation (Zero Claims = Job Failure)

**File:** `daemon/services/processing_service.py`

Added after extraction (line 607):
```python
# VALIDATION: Fail job if no data extracted
total_entities = result.total_claims
if hasattr(result, 'extraction'):
    total_entities += len(getattr(result.extraction, 'jargon', []))
    total_entities += len(getattr(result.extraction, 'people', []))
    total_entities += len(getattr(result.extraction, 'mental_models', []))

if total_entities == 0:
    error_details = {
        "transcript_length": len(transcript),
        "metadata_keys": list(metadata.keys()),
        "provider": provider,
        "model": model,
        "result_type": str(type(result)),
        "has_extraction_attr": hasattr(result, 'extraction'),
    }
    error_msg = (
        f"EXTRACTION FAILED: Zero entities extracted from {len(transcript):,} char transcript.\n"
        f"Details: {json.dumps(error_details, indent=2)}\n\n"
        f"Possible causes:\n"
        f"  1. API key invalid/missing for {provider}\n"
        f"  2. LLM returned error instead of JSON\n"
        f"  3. Prompt malformed (check logs for unreplaced variables)\n"
        f"  4. JSON parsing failed\n"
        f"  5. Response structure mismatch\n\n"
        f"Check logs above for:\n"
        f"  - API key status (ANTHROPIC_API_KEY, OPENAI_API_KEY, etc.)\n"
        f"  - LLM response preview\n"
        f"  - Prompt length and content\n"
        f"  - JSON parsing warnings"
    )
    logger.error(error_msg)
    raise Exception(error_msg)
```

**What This Prevents:**
- Job marked as "complete" when no data extracted
- Upload attempting with empty data
- False success reporting to user
- Silent failures

## Diagnostic Logging Flow

When an extraction runs, logs will now show:

```
1. API Key Status Check:
   API keys in environment:
     - OPENAI_API_KEY: Set/Not set
     - ANTHROPIC_API_KEY: Set/Not set
     - GOOGLE_API_KEY: Set/Not set

2. Transcript Validation:
   Transcript ready: 15,234 chars

3. Provider Selection:
   Starting two-pass extraction for dQw4w9WgXcQ
   Provider: anthropic, Model: claude-sonnet-4-20250514

4. Prompt Building:
   Prompt built: 18,456 chars
     - Contains transcript: True
     - Contains metadata: title=Peter Attia on Longevity

5. LLM Call:
   Calling LLM: provider=anthropic, model=claude-sonnet-4-20250514
   LLM call successful: 12,345 chars
   Response preview (first 500 chars): {"claims": [{"claim_text": "..."...
   Response appears to be JSON format

6. JSON Parsing:
   Parsed extraction data:
     - Claims: 15
     - Jargon: 5
     - People: 3
     - Mental Models: 2

7. Result Validation:
   Two-pass result type: <class 'TwoPassResult'>
   Total claims: 15
   Extraction claims: 15

8. Final Status:
   Extracted 15 claims, 5 jargon, 3 people
```

If any step fails, the specific failure point will be clear in the logs.

## What Changed

### Files Modified

1. **`daemon/services/simple_llm_wrapper.py`** (+7 lines)
   - Added response preview logging (first 500 chars)
   - Added JSON format detection warning
   - Logs if response doesn't look like JSON

2. **`src/knowledge_system/processors/two_pass/extraction_pass.py`** (+13 lines)
   - Added prompt length validation
   - Added transcript placeholder detection
   - Added metadata presence logging
   - Warns if prompt < 1000 chars

3. **`daemon/services/processing_service.py`** (+36 lines)
   - Added transcript empty check before pipeline
   - Added comprehensive validation after extraction
   - Added detailed error message with 6 possible causes
   - Updated job status message to show all entity counts
   - Prevents completion if total_entities == 0

4. **`CHANGELOG.md`** - Documented comprehensive diagnostics

5. **`ZERO_CLAIMS_DIAGNOSTIC_IMPLEMENTATION.md`** (NEW) - This documentation

## Testing Instructions

### Step 1: Restart Daemon

```bash
# Kill old daemon
ps aux | grep "python.*daemon.main" | grep -v grep | awk '{print $2}' | xargs kill

# Start new daemon with diagnostic code
cd /Users/matthewgreer/Projects/Knowledge_Chipper
python3 -m daemon.main
```

### Step 2: Run Test Extraction

Via web UI or API:
```bash
curl -X POST http://localhost:8765/process \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://youtube.com/watch?v=SHORT_VIDEO_ID",
    "extract_claims": true,
    "llm_provider": "anthropic",
    "llm_model": "claude-sonnet-4-20250514"
  }'
```

### Step 3: Analyze Logs

Check for the diagnostic sequence:
1. API key status
2. Transcript length
3. Prompt length
4. LLM response preview
5. JSON format check
6. Parsed entity counts
7. Validation pass/fail

### Step 4: Identify Root Cause

Based on logs:

**If "API key: Not set":**
- Problem: API key not configured
- Solution: Set API key in web UI settings

**If "Response does NOT appear to be JSON":**
- Problem: LLM returning error or refusal
- Solution: Check API key validity, check model name, review response preview

**If "Prompt contains unreplaced {transcript}":**
- Problem: Template variable substitution failed
- Solution: Check metadata being passed to _build_prompt

**If "Parsed extraction data: Claims: 0":**
- Problem: JSON valid but empty arrays
- Solution: Check LLM response for actual content, may be model issue

**If "EXTRACTION FAILED: Zero entities":**
- Problem: Validation triggered
- Solution: Review all diagnostic logs above to identify which check failed

## Expected Outcomes

### Successful Extraction

```
Job Status: complete
Message: "Extracted 15 claims, 5 jargon, 3 people"
Episode Page: Created in output/summaries/
Upload: Succeeded with 23 total records
```

### Failed Extraction (Zero Claims)

```
Job Status: failed
Message: "EXTRACTION FAILED: Zero entities extracted..."
Error Details: Full diagnostic info with 6 possible causes
Episode Page: Not created
Upload: Not attempted
```

## Next Steps

1. Restart daemon with diagnostic code
2. Run extraction on a test video
3. Review logs to identify which of the 6 causes is the issue
4. Fix the root cause
5. Re-test to confirm
6. Release as v1.1.19

## Related Issues

- PyQt6 import issue (fixed in device_auth.py)
- Debug timestamp messages (fixed in processing_service.py)
- Episode page generation (now conditional on successful extraction)

## Rollback

If diagnostics cause issues, remove:
- Response preview logging in simple_llm_wrapper.py
- Prompt validation in extraction_pass.py  
- Hard validation in processing_service.py

All changes are additive and safe to remove.

---

**Status:** Ready for testing  
**Next:** Restart daemon and run extraction to see diagnostic logs
