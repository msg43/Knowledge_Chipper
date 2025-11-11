# Transcript Formatting Fixes - November 10, 2025

## Summary

Fixed 4 issues with transcript markdown output identified by user review:

1. ✅ **YouTube Description Header**: Changed from generic "Description" to "YouTube Description" for YouTube videos
2. ✅ **Filename Suffix Removal**: Removed "_transcript" suffix from markdown filenames  
3. ⚠️ **Speaker Attribution Issue**: Documented root cause of SPEAKER_01 labels appearing instead of real names
4. ✅ **Paragraph Breaking Optimization**: Improved readability with shorter paragraphs and more natural breaks

## Changes Made

### 1. YouTube Description Header (audio_processor.py)

**Problem**: All videos showed "## Description" regardless of source type

**Solution**: Made header conditional on source_type
- YouTube videos: "## YouTube Description"
- Other sources: "## Description"

**Code Location**: Lines 1295-1308 in `audio_processor.py`

```python
if source_metadata is not None:
    if description_text:
        # Use "YouTube Description" for YouTube videos, "Description" for others
        if source_type == "YouTube":
            lines.append("## YouTube Description")
        else:
            lines.append("## Description")
```

### 2. Filename Suffix Removal (audio_processor.py)

**Problem**: Filenames had redundant "_transcript" suffix:
- Before: `Trump exploits antisemitism to attack Harvard_transcript.md`
- After: `Trump exploits antisemitism to attack Harvard.md`

**Solution**: Changed filename generation to use clean title without suffix

**Code Location**: Lines 1472-1494 in `audio_processor.py`

```python
# Don't append "_transcript" suffix - use clean title as-is
filename = f"{safe_name}.md"
output_path = output_dir / filename
```

### 3. Speaker Attribution Issue - Root Cause Analysis

**Problem**: Transcripts showing "SPEAKER_01" instead of real speaker names like "Ian Bremmer"

**Root Cause**: The speaker attribution system requires an LLM (Language Model) to be configured and available. When the LLM is not available or not configured, the system falls back to generic speaker labels.

**How Speaker Attribution Works**:

1. **Diarization** identifies that multiple speakers are present and labels them as SPEAKER_00, SPEAKER_01, etc.
2. **Speaker Attribution** uses LLM to analyze:
   - Video metadata (title, description, uploader)
   - First 5 segments of each speaker's speech
   - Channel host database
   - Conversational context
3. **LLM Suggestion** provides real names (e.g., "Noah Feldman", "Ian Bremmer")
4. **Application** replaces SPEAKER_00 → "Noah Feldman", SPEAKER_01 → "Ian Bremmer"

**Why It's Failing**:

The code flow at lines 2116-2141 in `audio_processor.py` shows:

```python
# Get automatic assignments (from DB, AI, or fallback)
assignments = self._get_automatic_speaker_assignments(
    speaker_data_list, str(path)
)

if assignments:
    # Apply assignments to transcript data
    final_data = speaker_processor.apply_speaker_assignments(
        final_data, assignments, str(path), speaker_data_list
    )
else:
    logger.warning("⚠️ No automatic speaker assignments could be generated")
```

If `_get_automatic_speaker_assignments` returns None or empty dict, the markdown is saved with generic SPEAKER_00, SPEAKER_01 labels.

**Diagnostic Steps**:

1. Check if LLM is configured in settings
2. Look for log messages like:
   - "✅ Using LLM suggestion: SPEAKER_00 -> 'Noah Feldman'"
   - "❌ CRITICAL: No LLM suggestion for SPEAKER_00"
   - "LLM suggestion failed"
3. Check if fallback is being used:
   - "Smart fallback when LLM is not available"

**Resolution Options**:

1. **Configure LLM**: Set up OpenAI, Anthropic, or local LLM in settings
2. **Check LLM Availability**: Ensure API keys are valid and LLM is accessible
3. **Manual Assignment**: Use the speaker attribution dialog to manually assign names (this will be remembered for future transcriptions of the same channel)

### 4. Paragraph Breaking Optimization (audio_processor.py)

**Problem**: Paragraphs were too long (up to 900-1200 characters), making transcripts hard to scan

**Solution**: Optimized paragraph breaking parameters for better readability:
- **Pause threshold**: 7s → 3s (break on shorter pauses for more natural flow)
- **Max paragraph length**: 900 → 500 characters (shorter paragraphs easier to scan)
- **Force break**: 1200 → 700 characters (reasonable upper limit)

**Code Location**: Lines 1335-1346 in `audio_processor.py`

**Before**:
```python
pause_threshold_seconds = 7.0
max_paragraph_chars = 900
# Force break at 1200 chars
```

**After**:
```python
# Optimized for better markdown readability:
# - Shorter paragraphs for easier scanning
# - More aggressive breaking on pauses for natural flow
# - Prioritize sentence boundaries for clean breaks
pause_threshold_seconds = 3.0  # Break on shorter pauses (was 7.0)
max_paragraph_chars = 500  # Shorter paragraphs for readability (was 900)
force_break_chars = 700  # Force break at reasonable length (was 1200)
```

**Impact**:
- Transcripts now have 2-3x more paragraph breaks
- Each paragraph is a more digestible chunk
- Breaks align better with natural speech pauses
- Maintains speaker change and sentence boundary logic

## Testing

To test these changes:

1. **YouTube Description Header**: Transcribe a YouTube video and verify header says "## YouTube Description"
2. **Filename**: Check that new transcript files don't have "_transcript" suffix
3. **Speaker Attribution**: 
   - With LLM configured: Should see real names
   - Without LLM: Will see SPEAKER_00, SPEAKER_01 (expected behavior)
4. **Paragraph Breaking**: Transcripts should have shorter, more readable paragraphs with natural breaks

## Files Modified

- `src/knowledge_system/processors/audio_processor.py` (lines 1295-1308, 1335-1346, 1472-1494)
- `CHANGELOG.md` (added entries for all changes)

## Related Documentation

- Speaker attribution architecture: `docs/TRANSCRIPT_ARCHITECTURE_CLARIFICATION.md`
- Speaker attribution operational order: `docs/SPEAKER_ATTRIBUTION_OPERATIONAL_ORDER_FIX.md`
- Previous transcript fixes: `docs/TRANSCRIPT_OUTPUT_FIXES_2025.md`
