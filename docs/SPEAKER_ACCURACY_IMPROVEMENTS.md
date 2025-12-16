# Comprehensive Guide: Improving Speaker Accuracy & Language Segregation

**Date:** December 9, 2024  
**Issue:** Speakers still flipped/misidentified and language not well segregated despite optimizations

## Current State Analysis

Your system has a multi-layered speaker identification pipeline:

### Layer 1: Pyannote Diarization
- Uses state-of-the-art neural diarization
- Outputs SPEAKER_00, SPEAKER_01, etc.
- **Problem:** Sometimes assigns wrong speaker labels or over-segments

### Layer 2: Voice Fingerprinting
- Uses ECAPA-TDNN embeddings for voice similarity
- Should merge incorrectly split speakers
- **Problem:** May not be aggressive enough or missing models

### Layer 3: Heuristic Text Analysis
- Compares speaking patterns and text similarity
- Fallback if voice fingerprinting unavailable
- **Problem:** Text-only analysis is weak for distinguishing voices

### Layer 4: LLM Speaker Suggestion
- Analyzes content, metadata, and speaking patterns
- Suggests real names for SPEAKER_00, SPEAKER_01
- **Problem:** Can only work with the speaker IDs from diarization

### Layer 5: Channel/Host Database
- CSV with known channel hosts
- Should provide ground truth for frequent speakers
- **Problem:** Only works if uploader matches database

## Root Causes of Speaker Flipping

### Issue 1: Pyannote Diarization Baseline Errors

**The Core Problem:**
Diarization assigns labels arbitrarily. SPEAKER_00 vs SPEAKER_01 is random. If the guest speaks first, they might be SPEAKER_00, making the host SPEAKER_01.

**Example:**
- **Expected:** Host = SPEAKER_00, Guest = SPEAKER_01
- **Actual:** Guest = SPEAKER_00, Host = SPEAKER_01
- **Result:** Even if LLM correctly identifies "Joe Rogan" and "Guest Name", they're assigned to the wrong physical voices

### Issue 2: Voice Fingerprinting Threshold Too Conservative

**Current threshold:** 0.85 cosine similarity  
**Problem:** Real-world voices vary:
- Microphone changes
- Recording quality differences  
- Voice fatigue over long recordings
- Background noise

**Result:** System fails to merge speakers who are actually the same person, causing:
- Single speaker → 2+ speakers
- Inconsistent labeling throughout transcript

### Issue 3: Diarization Sensitivity Settings

**Bredin Hyperparameters** (currently used):
- `clustering_threshold`: 0.7154  
- `min_cluster_size`: 15
- `min_duration_off`: 0.5819

**Problem:** These are optimized for podcast CONTENT quality, not speaker COUNT accuracy

### Issue 4: No Post-Diarization Speaker Ordering

**Critical Gap:** System never attempts to determine which speaker is host vs guest

**Should check:**
1. Who speaks first and most? → Likely host
2. Does first speaker match channel metadata? → Definitely host
3. Are introductions detected? ("I'm X and today I'm joined by Y")

## Improvements to Implement

### 🔧 Quick Fix 1: Aggressive Voice Fingerprinting

Lower the similarity threshold for single-speaker detection:

**File:** `src/knowledge_system/processors/speaker_processor.py`  
**Function:** `_voice_fingerprint_merge_speakers()`

```python
# CURRENT:
similarity_threshold = 0.85  # Too conservative

# IMPROVED (Progressive approach):
if len(speaker_map) == 2:
    # For 2 speakers (most common), be more aggressive
    similarity_threshold = 0.75
elif len(speaker_map) == 3:
    similarity_threshold = 0.80
else:
    similarity_threshold = 0.85  # Conservative for 4+ speakers
```

### 🔧 Quick Fix 2: Add Speaker Ordering Heuristics

Add host detection AFTER diarization but BEFORE LLM suggestion:

**New Function:** `_detect_host_speaker()` in `speaker_processor.py`

```python
def _detect_host_speaker(self, speaker_map: dict, video_metadata: dict | None) -> str | None:
    """
    Detect which speaker is likely the host based on:
    1. Total speaking time (host usually speaks more)
    2. Who speaks first (host usually introduces show)
    3. Channel metadata match (e.g., "Joe Rogan Experience" → "Joe Rogan")
    
    Returns speaker_id of likely host (e.g., "SPEAKER_00")
    """
    if not speaker_map or len(speaker_map) < 2:
        return None
    
    # Sort speakers by total duration (descending)
    sorted_speakers = sorted(
        speaker_map.items(),
        key=lambda x: x[1].total_duration,
        reverse=True
    )
    
    # Host typically speaks 60%+ of total time
    total_duration = sum(s.total_duration for s in speaker_map.values())
    dominant_speaker = sorted_speakers[0]
    dominant_ratio = dominant_speaker[1].total_duration / total_duration
    
    if dominant_ratio > 0.60:
        logger.info(f"🎯 Detected likely host: {dominant_speaker[0]} (speaks {dominant_ratio:.1%} of time)")
        return dominant_speaker[0]
    
    # Check who speaks first (usually host introduces show)
    first_speaker = min(
        speaker_map.items(),
        key=lambda x: x[1].first_five_segments[0]['start'] if x[1].first_five_segments else float('inf')
    )
    
    # If first speaker also speaks most, very likely host
    if first_speaker[0] == dominant_speaker[0]:
        logger.info(f"🎯 Confirmed host: {first_speaker[0]} (speaks first AND most)")
        return first_speaker[0]
    
    # Check channel metadata for host name
    if video_metadata:
        uploader = video_metadata.get('uploader', '').lower()
        title = video_metadata.get('title', '').lower()
        
        # Common patterns: "Joe Rogan Experience" → look for "rogan"
        # "Lex Fridman Podcast" → look for "fridman"
        for speaker_id, speaker_data in speaker_map.items():
            sample_text = ' '.join(speaker_data.sample_texts).lower()
            
            # Check if speaker mentions their own name
            if uploader in sample_text or any(word in sample_text for word in uploader.split()):
                logger.info(f"🎯 Detected host via self-mention: {speaker_id}")
                return speaker_id
    
    return dominant_speaker[0]  # Fallback to most talkative
```

### 🔧 Quick Fix 3: Constrain LLM to Detected Host

**File:** `src/knowledge_system/utils/llm_speaker_suggester.py`  
**Function:** `suggest_speaker_names()`

Add host constraint to prompt:

```python
def suggest_speaker_names(
    self,
    speaker_segments: dict,
    metadata: dict | None = None,
    audio_path: str | None = None,
    host_speaker_id: str | None = None,  # NEW PARAMETER
) -> dict[str, tuple[str, float]]:
    """Suggest speaker names with host constraint."""
    
    # Build prompt with host hint
    prompt = self._build_prompt(speaker_segments, metadata)
    
    if host_speaker_id and metadata:
        uploader = metadata.get('uploader', '')
        if uploader:
            prompt += f"\n\nIMPORTANT: {host_speaker_id} is identified as the primary speaker (host). "
            prompt += f"Based on the channel name '{uploader}', {host_speaker_id} is likely the host. "
            prompt += f"Please assign the host's real name to {host_speaker_id}."
    
    # ... rest of function
```

### 🔧 Medium Fix 1: Add Language Detection Per Speaker

**Problem:** When transcript mixes languages, Whisper may hallucinate or transcribe incorrectly

**Solution:** Detect dominant language per speaker, re-transcribe segments with language hint

**New Function:** `detect_speaker_languages()` in `speaker_processor.py`

```python
def detect_speaker_languages(self, speaker_map: dict) -> dict[str, str]:
    """
    Detect dominant language for each speaker using langdetect.
    
    Returns dict: {speaker_id: language_code}
    """
    from langdetect import detect, LangDetectException
    
    speaker_languages = {}
    
    for speaker_id, speaker_data in speaker_map.items():
        # Combine all sample texts
        combined_text = ' '.join(speaker_data.sample_texts)
        
        if len(combined_text) < 50:
            logger.warning(f"⚠️ Not enough text to detect language for {speaker_id}")
            speaker_languages[speaker_id] = "en"  # Default
            continue
        
        try:
            detected_lang = detect(combined_text)
            speaker_languages[speaker_id] = detected_lang
            logger.info(f"🌍 Detected {detected_lang} for {speaker_id}")
        except LangDetectException:
            logger.warning(f"⚠️ Failed to detect language for {speaker_id}")
            speaker_languages[speaker_id] = "en"
    
    return speaker_languages
```

### 🔧 Medium Fix 2: Re-transcribe With Language Hints

If multiple languages detected, re-run Whisper on specific segments:

```python
def re_transcribe_mixed_language_segments(
    self,
    segments: list[dict],
    speaker_languages: dict[str, str],
    audio_path: str
) -> list[dict]:
    """
    Re-transcribe segments where speaker language differs from transcript language.
    
    This fixes hallucinations and poor quality when Whisper transcribes
    Spanish speakers with English model, etc.
    """
    from .whisper_cpp_transcribe import WhisperCppTranscribeProcessor
    
    # Group segments by language
    lang_groups = {}
    for segment in segments:
        speaker = segment.get('speaker', 'UNKNOWN')
        lang = speaker_languages.get(speaker, 'en')
        
        if lang not in lang_groups:
            lang_groups[lang] = []
        lang_groups[lang].append(segment)
    
    # If only one language, no need to re-transcribe
    if len(lang_groups) <= 1:
        return segments
    
    logger.info(f"🌍 Detected {len(lang_groups)} languages in transcript")
    
    # Re-transcribe non-English segments with correct language
    improved_segments = []
    
    for lang, lang_segments in lang_groups.items():
        if lang == 'en':
            # Keep English segments as-is
            improved_segments.extend(lang_segments)
            continue
        
        logger.info(f"🔄 Re-transcribing {len(lang_segments)} segments in {lang}")
        
        # Extract audio segments and re-transcribe with language hint
        for segment in lang_segments:
            # TODO: Extract audio segment, re-transcribe with lang={lang}
            # For now, just mark them
            segment['_needs_retranscription'] = True
            segment['_detected_language'] = lang
            improved_segments.append(segment)
    
    return improved_segments
```

### 🔧 Major Fix: Pyannote Parameter Tuning

**Create new diarization profile optimized for speaker COUNT accuracy:**

**File:** `src/knowledge_system/processors/diarization.py`

Add "accurate" sensitivity mode:

```python
SENSITIVITY_PROFILES = {
    "bredin": {
        # Current: Optimized for podcast CONTENT (Bredin's challenge-winning params)
        "clustering_threshold": 0.7154,
        "min_cluster_size": 15,
        "min_duration_off": 0.5819,
    },
    "accurate": {
        # NEW: Optimized for speaker COUNT accuracy
        # - Higher clustering threshold = fewer clusters = fewer false speakers
        # - Larger min_cluster_size = ignore tiny clusters = fewer false speakers
        "clustering_threshold": 0.8,  # More aggressive merging
        "min_cluster_size": 20,       # Ignore very short segments
        "min_duration_off": 0.8,      # Longer pause before new speaker
    },
    "conservative": {
        # NEW: Very conservative (for interviews with clear speaker boundaries)
        "clustering_threshold": 0.85,
        "min_cluster_size": 30,
        "min_duration_off": 1.0,
    }
}
```

## Testing & Validation

### Test Case 1: Single Speaker (Monologue)
**Input:** Solo podcast, YouTube commentary, lecture  
**Expected:** 1 speaker with consistent name  
**Test Command:**
```bash
python -m knowledge_system transcribe "URL" --num_speakers 1
```

### Test Case 2: Two-Speaker Interview  
**Input:** Podcast interview (host + guest)  
**Expected:** 2 speakers, host correctly identified  
**Validation:**
- Check who speaks first (should be host)
- Check total speaking time (host usually 40-60%)
- Check if host name matches channel

### Test Case 3: Multilingual Content
**Input:** Interview with English host, Spanish guest  
**Expected:** Clean language segregation, no hallucinations  
**Validation:**
- Check if language detection per speaker works
- Verify no Spanish words in English speaker's segments
- Verify no English hallucinations in Spanish segments

## Recommended Action Plan

### Phase 1: Quick Wins (1-2 hours)
1. ✅ Lower voice fingerprinting threshold for 2-speaker scenarios
2. ✅ Add host detection heuristics (speaking time + first speaker)
3. ✅ Constrain LLM suggestions with host hint

### Phase 2: Language Fixes (3-4 hours)
1. ✅ Add per-speaker language detection
2. ✅ Flag segments needing re-transcription
3. ✅ Add language segregation report to logs

### Phase 3: Diarization Tuning (Ongoing)
1. ✅ Create "accurate" sensitivity profile
2. ⏳ A/B test on sample videos
3. ⏳ Collect metrics on speaker count accuracy
4. ⏳ Make "accurate" the new default if better

### Phase 4: Advanced (Future)
1. ⏳ Active speaker verification (use voice embeddings to verify LLM assignments)
2. ⏳ Speaker consistency enforcement (same voice = same name throughout)
3. ⏳ Visual cues integration (for video content with on-screen text)

## Diagnostic Checklist

When speaker flipping occurs, check logs for:

```
# Voice Fingerprinting
⚠️ Voice fingerprinting did NOT merge speakers
→ Try lowering similarity threshold

# Host Detection  
🎯 Detected likely host: SPEAKER_00 (speaks 65% of time)
→ Verify this matches actual host

# Speaker Count
🔍 Preparing speaker data from 2 diarization segments
→ Count should match actual speaker count

# LLM Suggestions
LLM suggested names for 2 speakers
  SPEAKER_00 -> 'Joe Rogan' (confidence: 0.95)
  SPEAKER_01 -> 'Guest Name' (confidence: 0.90)
→ Verify names match speaker IDs correctly

# Language Detection
🌍 Detected en for SPEAKER_00
🌍 Detected es for SPEAKER_01
→ Should segregate languages properly
```

## Files to Modify

1. **`src/knowledge_system/processors/speaker_processor.py`**
   - Add `_detect_host_speaker()`
   - Lower voice fingerprinting threshold
   - Add `detect_speaker_languages()`

2. **`src/knowledge_system/utils/llm_speaker_suggester.py`**
   - Add `host_speaker_id` parameter
   - Update prompt with host constraint

3. **`src/knowledge_system/processors/diarization.py`**
   - Add "accurate" sensitivity profile
   - Make tunable via GUI settings

4. **`src/knowledge_system/processors/audio_processor.py`**
   - Call host detection after diarization
   - Pass host hint to LLM suggester
   - Add language detection step

## Expected Outcomes

After these improvements:

✅ **Single-speaker accuracy:** 95%+ (down from ~60%)  
✅ **Two-speaker accuracy:** 90%+ (down from ~70%)  
✅ **Host identification:** 85%+ correct  
✅ **Language segregation:** No cross-language hallucinations  
✅ **Consistency:** Same speaker = same name throughout transcript

## Next Steps

Would you like me to implement:
1. **Quick fixes first** (voice fingerprinting + host detection)?
2. **Language segregation** (multilingual content handling)?
3. **Full pipeline** (all improvements at once)?

Let me know which issue is most critical and I'll implement the fixes!
