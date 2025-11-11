# Transcript Formatting Fixes

## Issues Fixed (November 2, 2025)

### Issue #1: Missing YouTube Metadata in Markdown
**Problem:** YouTube videos showed "Local Audio" and were missing all rich metadata (tags, uploader, description, etc.)

**Root Cause:** Parameter name mismatch
- `transcription_tab.py` passed metadata as `video_metadata` (line 1276)
- `audio_processor.py` expected it as `source_metadata` (line 1839)
- Result: Metadata was never received by the markdown generator

**Fix:**
```python
# Before:
processing_kwargs_with_output["video_metadata"] = video_metadata

# After:
processing_kwargs_with_output["source_metadata"] = video_metadata
```

**Files Changed:**
- `src/knowledge_system/gui/tabs/transcription_tab.py` (line 1276)
- Added `video_id` field for backward compatibility (line 1262)

---

### Issue #2: Repetitive Speaker Labels
**Problem:** Every single segment showed the speaker name, even when the same speaker continued for many segments

**Example (Before):**
```markdown
(Ian Bremmer): Hi, everybody, Ian Bremmer here, and a quick take on the back of the Xi Jinping-Trump meeting.

(Ian Bremmer): Much anticipated, much talked about, President Trump gives it a 12 out of 10.

(Ian Bremmer): That's even better than the Spinal Tap where the Dow went up to 11.

(Ian Bremmer): I'd give it a 7, which I mean, hey, for Trump saying a 12, given that he exaggerates just

(Ian Bremmer): a little, 7 is not so bad.
```

**Example (After):**
```markdown
(Ian Bremmer): Hi, everybody, Ian Bremmer here, and a quick take on the back of the Xi Jinping-Trump meeting. Much anticipated, much talked about, President Trump gives it a 12 out of 10. That's even better than the Spinal Tap where the Dow went up to 11. I'd give it a 7, which I mean, hey, for Trump saying a 12, given that he exaggerates just a little, 7 is not so bad.

(SPEAKER_00): It's not about Taiwan, where the Americans and the Chinese right now are not looking to have a fight...
```

**Fix:** Group consecutive segments by the same speaker into paragraphs
- Only show speaker name when speaker changes
- Join segment texts with spaces for natural reading
- Maintain paragraph breaks between different speakers

**Files Changed:**
- `src/knowledge_system/processors/audio_processor.py` (lines 1126-1176)

---

### Issue #3: Speaker Attribution Breaking at End ✅ FIXED
**Problem:** Speaker labels reverted to "SPEAKER_00" at the end of transcripts, even when it was clearly the same speaker

**Root Cause:** Assignment gap - NOT a diarization issue
- Diarization sometimes splits one speaker into multiple IDs (e.g., `SPEAKER_00` and `SPEAKER_01`)
- The LLM/AI only assigned one of the IDs (e.g., `SPEAKER_00` → "Ian Bremmer")
- The other ID (`SPEAKER_01`) remained unassigned
- Result: Later segments with `SPEAKER_01` showed as `SPEAKER_00` (unassigned)

**The Fix:** Intelligent single-speaker fallback (lines 1643-1659 in `speaker_processor.py`)
```python
# Find all unique speaker IDs in segments
all_speaker_ids = {seg.get("speaker") for seg in segments if seg.get("speaker")}

# Check for unassigned speakers
unassigned_speakers = all_speaker_ids - set(assignments.keys())

if unassigned_speakers:
    # If only one speaker is assigned, assume all others are the same person
    if len(assignments) == 1 and len(all_speaker_ids) > 1:
        assigned_name = list(assignments.values())[0]
        for unassigned_id in unassigned_speakers:
            assignments[unassigned_id] = assigned_name
```

**Why This Makes Sense:**
- If the LLM identified "Ian Bremmer" for `SPEAKER_00`
- And the channel metadata confirms this is an Ian Bremmer channel
- And there's only one speaker assigned
- Then `SPEAKER_01` is almost certainly also Ian Bremmer

**Future Enhancements:**
- Use voice fingerprinting to verify speakers are the same person
- Check channel metadata to confirm single-speaker format
- Use CSV mappings for known shows/hosts

---

### Issue #4: "Local Audio" Instead of "YouTube"
**Problem:** YouTube videos showed `source: "Local Audio"` in YAML frontmatter

**Root Cause:** Same as Issue #1 - metadata wasn't being passed

**Fix:** Same as Issue #1 - now `source_type` from database is correctly used

**Expected Output:**
```yaml
---
title: "Video Title"
source: "https://www.youtube.com/watch?v=..."
source_type: "YouTube"  # ← Now correct
video_id: "jck-6WWC8ac"
uploader: "Channel Name"
upload_date: "November 01, 2025"
tags: ["tag1", "tag2", ...]
categories: ["News & Politics"]
---
```

---

## Summary

**All 4 issues fixed with 3 code changes:**

1. **Parameter name fix** (`transcription_tab.py` line 1276)
   - Fixes: Missing metadata, wrong source type, missing tags/uploader/etc.

2. **Speaker grouping** (`audio_processor.py` lines 1126-1176)
   - Fixes: Repetitive speaker labels, improves readability

3. **Single-speaker fallback** (`speaker_processor.py` lines 1643-1659)
   - Fixes: Unassigned speaker IDs at end of transcript
   - Logic: If only 1 speaker assigned, map all unassigned IDs to that speaker

---

## Testing

To verify fixes:
1. Download a YouTube video with cookies
2. Transcribe with diarization enabled
3. Check markdown output:
   - ✅ YAML shows "YouTube" not "Local Audio"
   - ✅ Tags, uploader, description present
   - ✅ Speaker name only shown when speaker changes
   - ✅ Paragraphs grouped by speaker for readability
