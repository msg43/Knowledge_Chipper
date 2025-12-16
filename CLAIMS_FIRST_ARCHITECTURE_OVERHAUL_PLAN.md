# Claims-First Architecture Overhaul Plan

**Date:** December 15, 2025
**Status:** Proposed (Not Yet Implemented)
**Scope:** Complete redesign of Knowledge Chipper's claim extraction pipeline

---

## Executive Summary

This document proposes a fundamental architectural shift from a **speaker-first** processing model to a **claims-first** processing model. The current system spends 80% of its effort on speaker diarization and attribution (6 fragile layers of acoustic analysis, voice fingerprinting, and LLM matching) before extracting the claims users actually care about. The proposed system inverts this: extract high-value claims first, then attribute speakers only to claims that matter.

### Current Problems

1. **Fragile speaker diarization pipeline**: 6-stage system with cascading failures (pyannote → voice fingerprinting → speaker merging → CSV lookup → LLM attribution → user confirmation)
2. **Unreliable speaker attribution**: Despite extensive work, speaker labels remain inconsistent (SPEAKER_01 appears instead of real names, over-segmentation issues persist)
3. **Wrong optimization target**: 100% effort on speaker labels for entire transcript, when users only need speakers for ~10-20 high-value claims
4. **Massive complexity**: ~3,800 lines of code, 8 major dependencies, 5GB of models, multiple points of failure
5. **User needs mismatch**: Users browse claims/jargon/people/concepts on website—they never see or need fully diarized transcripts

### Proposed Solution

**Claims-first pipeline:**
1. Transcribe audio → Extract all claims → Filter to high-value claims → Attribute speakers to those claims only
2. Eliminate: pyannote diarization, voice fingerprinting (wav2vec2, ECAPA-TDNN), 6-layer speaker merging
3. Simplify: ~1,350 lines of code (64% reduction), 2 major dependencies (75% reduction)
4. Same or better quality: LLMs can identify speakers from claim context more reliably than acoustic models can segment speakers across entire transcripts

---

## Table of Contents

1. [Current System Analysis](#1-current-system-analysis)
2. [Fundamental Paradigm Shift](#2-fundamental-paradigm-shift)
3. [The YouTube Transcript Question](#3-the-youtube-transcript-question)
4. [Proposed Architecture](#4-proposed-architecture)
5. [Implementation Phases](#5-implementation-phases)
6. [Risk Analysis](#6-risk-analysis)
7. [Success Criteria](#7-success-criteria)
8. [Rollback Plan](#8-rollback-plan)
9. [Open Questions](#9-open-questions)

---

## 1. Current System Analysis

### 1.1 Current Pipeline Flow

```
Audio File
  ↓
[1] Whisper Transcription (10-15 min) ✓ Works well
  ↓
[2] Pyannote Diarization (30-60 sec)
    - Output: SPEAKER_00, SPEAKER_01, SPEAKER_02...
    - Problem: Over-segmentation (single speaker split into 2-3 IDs)
  ↓
[3] Voice Fingerprinting - Tier 1 (20-30 sec)
    - Extracts MFCC, spectral, prosodic, wav2vec2, ECAPA features
    - Problem: Deep learning models fail to load, weights don't sum to 1.0
  ↓
[4] Voice Fingerprinting - Tier 2 (fallback)
    - Text-based heuristics when audio fails
    - Problem: Conservative 0.85 threshold misses legitimate merges
  ↓
[5] Heuristic Over-Segmentation Detection (10 sec)
    - Additional pattern-based merging
    - Problem: Another layer trying to fix layer 2's mistakes
  ↓
[6] LLM-Based Speaker Attribution (10 sec + $0.10)
    - CSV channel mapping (262 podcasts)
    - Metadata + transcript analysis
    - Problem: Model name mismatches, "SPEAKER_01" still appears
  ↓
[7] User Confirmation (GUI mode)
    - Manual verification
    - Problem: Shouldn't require user intervention for routine task
  ↓
[8] Claim Extraction ($0.30)
    - Finally extract what users care about
  ↓
Final Output: Claims with fragile speaker labels
```

**Total:** 15+ minutes, $0.40, 6 points of failure

### 1.2 Code Complexity Analysis

| Component | Lines of Code | Dependencies | Failure Modes |
|-----------|---------------|--------------|---------------|
| Whisper transcription | 500 | pywhispercpp | Low (works reliably) |
| Pyannote diarization | 300 | pyannote.audio, torch | Medium (over-segments) |
| Voice fingerprinting | 800 | speechbrain, transformers, wav2vec2, ECAPA-TDNN | High (models don't load) |
| Speaker merging (3 layers) | 600 | N/A | High (threshold tuning) |
| CSV channel mapping | 200 | N/A | Medium (channel not in DB) |
| LLM speaker attribution | 400 | OpenAI/Anthropic/Ollama | Medium (model mismatches) |
| Claim extraction | 1,000 | LLM | Low (works well) |
| **TOTAL** | **~3,800** | **8 major** | **Cascading failures** |

### 1.3 Dependency Burden

**Current required downloads:**
- pyannote.audio models: ~1.5GB
- speechbrain models: ~500MB
- wav2vec2 models: ~1GB
- ECAPA-TDNN models: ~500MB
- Whisper models: 1-3GB (depending on size)
- **Total: ~5GB of models**

**Runtime dependencies:**
- pytorch (heavyweight)
- transformers (heavyweight)
- pyannote.audio (speaker diarization)
- speechbrain (speaker embeddings)
- pywhispercpp (transcription)
- yt-dlp (downloads)
- LLM client (OpenAI/Anthropic/Ollama)

### 1.4 User Need Mismatch

**What the system produces:**
- Fully diarized transcripts with speaker labels on every segment
- Markdown files with SPEAKER_00/SPEAKER_01 or real names
- Database records with speaker assignments

**What users actually use:**
- Browse claims by person on website
- Browse claims by episode
- Search jargon, people, concepts
- **Never view or need fully diarized transcripts**

**Conclusion:** We're solving a problem users don't have, while introducing complexity and fragility.

---

## 2. Fundamental Paradigm Shift

### 2.1 The Core Insight

Current thinking: "To extract claims, we must first know who said what throughout the entire transcript."

New thinking: "Extract valuable claims first, then figure out who said the important ones."

### 2.2 Why This Changes Everything

#### 2.2.1 Selective Attribution is Cheaper

**Current approach:**
- Attribute speakers for 100% of transcript segments
- Typical 2-hour podcast: ~400 segments need speaker labels
- Effort: 400 speaker decisions
- Failure: If any speaker label is wrong, entire transcript is compromised

**Claims-first approach:**
- Extract all claims (50 total)
- Filter to high-value (12 A-tier claims)
- Attribute speakers for 12 claims only
- Effort: 12 speaker decisions
- Failure: If one speaker label is wrong, only that claim is affected

**Ratio:** 33x fewer speaker attribution operations

#### 2.2.2 Better Context for Attribution

**Current approach:**
```
Question: "Who is SPEAKER_01 across this entire 2-hour transcript?"
Context: Entire transcript, disconnected segments
Problem: Generic question, limited context
```

**Claims-first approach:**
```
Question: "Who made THIS specific claim: 'The Fed's balance sheet expansion causes asset inflation'?"
Context:
  - Claim itself (topic = economics → probably economist guest)
  - Surrounding 60 seconds of dialogue
  - First-person language ("In my research...")
  - Metadata (guest is "Jeff Snider, economist")
Problem: Specific question, rich context
```

**Result:** LLM can make higher-confidence attribution with better evidence.

#### 2.2.3 Claims Provide Speaker Signals

Claims naturally contain attribution signals that acoustic models miss:

**First-person claims:**
```
Claim: "My research at Stanford shows dopamine regulates motivation"
Signals:
  - "My research" = first-person ownership
  - "at Stanford" = works at Stanford
  - Metadata: Guest is "Andrew Huberman, Stanford neuroscientist"
Attribution: 95% confidence → Andrew Huberman
```

**Expertise-based claims:**
```
Claim: "The eurodollar market determines global liquidity"
Signals:
  - Topic: complex banking/finance
  - Metadata: Guest is "Jeff Snider, eurodollar expert"
  - Host rarely discusses technical finance
Attribution: 90% confidence → Jeff Snider
```

**Turn-taking patterns:**
```
[15:20] Host: "What about inflation?"
[15:23] Claim: "Asset inflation is distinct from consumer inflation"
[15:45] Host: "That's fascinating. Tell me more."
Signals:
  - Claim is response to host's question
  - Host responds to claim (clear turn-taking)
Attribution: 92% confidence → Guest
```

Acoustic models can't understand any of these signals—they only hear voice frequencies.

### 2.3 Professional Systems Have The Same Problem

Research findings from web search (December 2025):

**Industry-best accuracy:**
- Professional services (AssemblyAI, Otter.ai): 90-95% diarization accuracy
- pyannote.audio on benchmarks: 5-8% DER (error rate)
- **pyannote on real-world podcasts: 15-25% DER**

**Translation:** On a 2-hour podcast with 200 segments:
- Best case: 10 segments have wrong speaker (5% error)
- Typical case: 30-50 segments have wrong speaker (15-25% error)

**How professionals handle this:**
1. Human review (expensive, not scalable)
2. User corrections (Otter.ai model)
3. Living with imperfection (most don't notice)

**Conclusion:** Even with unlimited resources, speaker diarization is an unsolved problem. Professional systems achieve 75-90% accuracy at best.

---

## 3. The YouTube Transcript Question

### 3.1 The Opportunity

YouTube provides auto-generated transcripts for free, instantly. If these are "good enough," we could skip:
- Audio download (30 sec - 2 min)
- Whisper transcription (10-15 min)
- Audio storage and conversion
- Entire audio processing pipeline

**Potential savings:**
- Time: 10-15 minutes → 5 seconds (180x faster)
- Cost: $0.40 → $0.01 (40x cheaper)
- Complexity: Remove audio processing dependencies

### 3.2 The Accuracy Question

**Marketing claims we found:**
- TranscribeTube blog: "YouTube native transcription (66% average)"
- Other sources: "60-70% accuracy"
- Optimal conditions: "Up to 95% accuracy"

**Problems with these claims:**
1. TranscribeTube is a competitor trying to sell their service
2. No methodology provided
3. No citation to actual research
4. Contradictory data (66% vs 95%)

**More reliable sources:**
- Academic studies: 61.92% accuracy in optimal conditions
- Consumer Reports: "auto-captions often fall short" (unquantified)
- Industry standard for accessibility: 99% required, auto-captions don't meet it

**Realistic estimate:**
- Best case (clear audio, single speaker, standard accent): 85-95%
- Average case (typical podcasts): 70-80%
- Worst case (accents, jargon, multiple speakers): 50-65%

### 3.3 What We Actually Need to Know

The critical question isn't "How accurate are YouTube transcripts?" but rather:

**"Does the accuracy difference affect claim extraction quality?"**

Because:
1. LLMs are robust to typos and minor errors
2. Semantic meaning is often preserved even with transcription errors
3. Claims are high-level concepts, not verbatim quotes
4. We're extracting IDEAS, not doing forensic audio analysis

**Example:**
```
Whisper:  "The Fed's balance sheet expansion creates asset inflation"
YouTube:  "The Fed's balance sheet expansion creates asset inflation"
(Same result)

Whisper:  "eurodollar markets affect global liquidity"
YouTube:  "euro dollar markets affect global liquidity"
(Semantic meaning preserved, claim extraction likely identical)

Whisper:  "Stacy Rasgon from Bernstein Research"
YouTube:  "Stacey Raskin from Bernstein Research"
(Name garbled, but LLM might still extract person entity)
```

**The only way to know:** Empirical testing on real podcasts.

### 3.4 What We Lose With YouTube Transcripts

#### 3.4.1 Timestamp Granularity

**YouTube provides:**
```json
[
  {"text": "The Fed's balance sheet expansion creates asset inflation",
   "start": 125.0, "duration": 5.2},
  {"text": "not consumer inflation like most people think",
   "start": 130.2, "duration": 3.8}
]
```
- Segment-level timestamps (5-10 second windows)
- Cannot pinpoint exact word timing

**Whisper provides:**
```json
[
  {"word": "The", "start": 125.3, "end": 125.4},
  {"word": "Fed's", "start": 125.5, "end": 125.7},
  {"word": "balance", "start": 125.8, "end": 126.0},
  ...
]
```
- Word-level timestamps (0.1 second precision)
- Can identify exact moment each word was spoken

**Impact:**
- YouTube: "This claim was made between 125.0s and 130.2s (5.2 second window)"
- Whisper: "This claim starts at 125.5s and ends at 128.7s (exact timing)"

**Does this matter for your use case?**
- Users clicking claim on website need to jump to timestamp
- 5-second window still gets them close enough
- Not critical unless you need exact verbatim quotes for legal purposes

#### 3.4.2 Accuracy Gaps

Areas where YouTube transcripts fail:

**Technical jargon:**
```
Actual:  "quantitative easing affects the eurodollar market"
YouTube: "quantitative easing affects the euro dollar market"
Impact:  Might extract as two separate concepts (euro + dollar) instead of one (eurodollar)
```

**Proper names:**
```
Actual:  "Andrew Huberman"
YouTube: "Andrew Hooberman" or "Andrew Hubermann"
Impact:  Person entity extraction might fail or create duplicate entries
```

**Rapid back-and-forth:**
```
Actual:
  [15:20] Speaker A: "What do you think?"
  [15:22] Speaker B: "I agree completely"
  [15:24] Speaker A: "That makes sense"

YouTube (might merge):
  [15:20] "What do you think? I agree completely. That makes sense."
Impact: Loses speaker turn-taking, harder to attribute
```

**Heavy accents:**
```
Actual:  Clear speech from non-native speaker
YouTube: Garbled or wrong words
Impact:  Claim extraction quality degrades
```

#### 3.4.3 No Control Over Quality

- Can't choose transcription model (stuck with YouTube's system)
- Can't adjust for domain-specific vocabulary
- Quality varies by channel (some have professional captions, most don't)
- No recourse if YouTube transcripts are poor

### 3.5 Proposed Hybrid Strategy

Rather than choosing one or the other, use a **smart hybrid approach:**

```
Step 1: Try YouTube transcript (5 seconds, free)
  ↓
Step 2: Quality assessment (check for garbled words, proper names)
  ↓
Step 3: Decision tree:
  - If quality_score >= 0.7 → Proceed with YouTube transcript
  - If quality_score < 0.7 → Auto-upgrade to Whisper
  ↓
Step 4: Extract claims
  ↓
Step 5: Check extraction confidence
  - If >5 low-confidence claims → Offer Whisper upgrade
  - If user marks "high-value episode" → Re-run with Whisper
```

**Expected distribution:**
- 60-70% of videos: YouTube is fine (40 seconds processing)
- 20-30% of videos: Auto-upgraded to Whisper (poor YouTube quality)
- 10% of videos: User manually requests Whisper (high-value content)

**Average processing time:** ~3-5 minutes instead of 11-15 minutes

### 3.6 Testing Plan for YouTube Transcripts

Before committing to YouTube transcripts, we MUST test empirically:

#### Phase 1: Accuracy Measurement
1. Select 10 representative podcasts you typically process
2. Get both YouTube and Whisper transcripts
3. Calculate Word Error Rate (WER) for each
4. Document which types of errors occur (jargon, names, etc.)

#### Phase 2: Claim Quality Measurement
1. Extract claims from both transcripts using same LLM
2. Compare:
   - Number of claims extracted
   - A-tier claim count
   - Semantic overlap of claims (are they saying the same things?)
3. Calculate "claim extraction quality ratio"

#### Phase 3: Real-World Validation
1. Process 20 videos with YouTube transcripts only
2. Have domain experts review claim quality
3. Identify failure patterns
4. Determine acceptable quality threshold

**Decision criteria:**
- If claim_quality_ratio > 0.85 (85% as good) → YouTube is acceptable
- If claim_quality_ratio < 0.70 (70% as good) → Stick with Whisper
- If 0.70-0.85 → Use hybrid approach

**Note:** Test script has been created (`test_youtube_vs_whisper_quality.py`) but requires HCE integration to run real claim extraction.

---

## 4. Proposed Architecture

### 4.1 New Pipeline Overview

```
Audio/Video Source
  ↓
[Option A: YouTube Transcript] (5 sec, free)
   OR
[Option B: Whisper Transcription] (10 min, compute)
  ↓
[Single LLM Call] Extract ALL entities (30 sec, $0.01-$0.33)
  - Claims
  - Jargon
  - People
  - Concepts
  - Cross-references between entities
  ↓
[Post-Processing] Match evidence quotes → timestamps (5 sec)
  ↓
[Lazy Speaker Attribution] Only for high-value claims (10 sec, $0.05)
  - Filter: importance >= 7 (A/B tier claims)
  - For each claim: targeted LLM call with 60-second context
  ↓
Upload to GetReceipts.org
```

**Total (YouTube path):** ~50 seconds, $0.06-$0.38
**Total (Whisper path):** ~11 minutes, $0.35-$0.63

### 4.2 Component Breakdown

#### 4.2.1 Transcription Layer (Variable)

**Purpose:** Convert audio to text

**Implementation Options:**

**Option A: YouTube Transcript API**
```python
from youtube_transcript_api import YouTubeTranscriptApi

transcript = YouTubeTranscriptApi.get_transcript(video_id)
# Returns: [{"text": "...", "start": 125.0, "duration": 5.2}, ...]
```

Pros:
- Instant (5 seconds)
- Free
- No audio download needed
- No compute required

Cons:
- 70-80% accuracy (estimated)
- Segment-level timestamps only (5-10 sec windows)
- No control over quality
- Only works for YouTube

**Option B: Whisper Transcription**
```python
from knowledge_system.processors.whisper_cpp_transcribe import WhisperCppTranscribeProcessor

transcriber = WhisperCppTranscribeProcessor(model="medium", enable_word_timestamps=True)
result = transcriber.process(audio_path)
# Returns: {"text": "...", "words": [{"word": "The", "start": 125.3, "end": 125.4}, ...]}
```

Pros:
- 95-99% accuracy
- Word-level timestamps (0.1 sec precision)
- Works for any audio source
- Configurable model size

Cons:
- 10-15 minutes processing
- Requires audio download
- Compute intensive
- 1-3GB model storage

**Decision Logic:**
```python
def get_transcript(video_url):
    # Try YouTube first (fast path)
    if is_youtube_url(video_url):
        yt_transcript, quality_score = get_youtube_transcript(video_url)

        if quality_score >= 0.7:
            return yt_transcript, "youtube"

    # Fallback to Whisper (slow but accurate)
    return get_whisper_transcript(video_url), "whisper"
```

#### 4.2.2 Entity Extraction Layer (Single LLM Call)

**Purpose:** Extract all entities in one pass

**Why single call instead of multiple:**
1. **Consistency:** LLM sees all entities together, can cross-reference
2. **Cheaper:** One API call instead of 4 separate calls ($0.30 vs $1.20)
3. **Faster:** Parallel extraction instead of sequential
4. **Better relationships:** Claims can reference "related_jargon" in same response

**Implementation:**

```
Input: Full transcript (30,000-40,000 tokens for 3-hour podcast)

Prompt:
  "Extract the following from this podcast transcript:
   1. CLAIMS: Important, novel, or controversial statements
   2. PEOPLE: Individuals mentioned (with descriptions)
   3. JARGON: Technical terms (with definitions)
   4. CONCEPTS: Mental models, frameworks, theories

   Return JSON with all four entity types, including cross-references."

Output: Single JSON with all entities
{
  "claims": [...],
  "people": [...],
  "jargon": [...],
  "concepts": [...],
  "metadata": {...}
}
```

**LLM Choice:**

For 3-hour podcast (~35,000 tokens input, ~15,000 tokens output):

| Model | Context Window | Input Cost | Output Cost | Total Cost | Notes |
|-------|----------------|------------|-------------|------------|-------|
| Gemini 2.0 Flash | 1M tokens | $0.0026 | $0.0045 | **$0.007** | Cheapest, "lost in middle" solved |
| Claude 3.5 Sonnet | 200K tokens | $0.105 | $0.225 | **$0.33** | Most reliable, moderate cost |
| GPT-4o | 128K tokens | $0.15 | $0.30 | **$0.45** | Expensive, smaller context |

**Recommendation:**
- Default: Gemini 2.0 Flash (1M context, $0.007/podcast)
- Fallback: Claude 3.5 Sonnet if Gemini quality issues

**Chunking Strategy:**

For podcasts >3 hours OR if using model with smaller context:

```
1. Split transcript into semantic chunks (~15,000 tokens each)
   - Chunk at paragraph boundaries (don't split mid-sentence)
   - Use 1,000 token overlap between chunks (catch claims spanning boundaries)

2. Extract from each chunk in parallel
   - 3-hour podcast = 4-6 chunks
   - Process concurrently (all 6 LLM calls at once)

3. Deduplicate across chunks
   - Claims appearing in overlap region → merge
   - Use semantic similarity to detect duplicates

4. Return consolidated results
```

**Cost with chunking:**
- 6 chunks × $0.007 = $0.042 (Gemini)
- 6 chunks × $0.05 = $0.30 (Claude)

#### 4.2.3 Timestamp Matching Layer (Post-Processing)

**Purpose:** Attach timestamps to extracted claims

**Why this is post-processing, not LLM task:**
- LLMs don't see word-level timing data
- LLMs can provide evidence quotes (text)
- Our code matches quotes → timestamps (mechanical)

**Implementation:**

```python
def match_claim_to_timestamps(claim: dict, whisper_words: list) -> dict:
    """
    Match claim's evidence quote to Whisper word timestamps.

    Args:
        claim: {"canonical": "...", "evidence": "The Fed creates inflation..."}
        whisper_words: [{"word": "The", "start": 125.3, "end": 125.4}, ...]

    Returns:
        {"timestamp_start": 125.3, "timestamp_end": 128.7, "confidence": 0.95}
    """
    # Extract words from evidence quote
    evidence_words = claim['evidence'].lower().split()

    # Find matching sequence in whisper words (fuzzy search)
    match_start, match_end = fuzzy_sequence_match(
        evidence_words,
        [w['word'].lower() for w in whisper_words],
        threshold=0.7  # Allow 30% word differences for LLM paraphrasing
    )

    if match_start is None:
        # Fallback: semantic similarity to find approximate location
        return estimate_timestamp_semantic(claim, whisper_words)

    return {
        "timestamp_start": whisper_words[match_start]['start'],
        "timestamp_end": whisper_words[match_end]['end'],
        "confidence": 0.95  # Exact match found
    }
```

**Handling LLM paraphrasing:**

Sometimes LLM rewrites evidence instead of quoting exactly:

```
Transcript:     "The Fed's balance sheet expansion creates asset inflation"
LLM evidence:   "Fed creates asset inflation through balance sheet expansion"
```

**Solution: Fuzzy matching**
```python
def fuzzy_sequence_match(target_words, source_words, threshold=0.7):
    """Find best matching sequence even if words differ."""
    best_match = None
    best_score = 0

    for i in range(len(source_words) - len(target_words)):
        window = source_words[i:i+len(target_words)]

        # Calculate overlap (exact matches + stemmed matches)
        score = word_overlap_score(target_words, window)

        if score > threshold and score > best_score:
            best_match = (i, i + len(target_words))
            best_score = score

    return best_match
```

**YouTube transcript handling:**

With segment-level timestamps (not word-level):

```python
def match_claim_to_youtube_segments(claim: dict, segments: list) -> dict:
    """
    Match claim to YouTube transcript segments.

    Args:
        claim: {"canonical": "...", "evidence": "..."}
        segments: [{"text": "...", "start": 125.0, "duration": 5.2}, ...]

    Returns:
        {"timestamp_start": 125.0, "timestamp_end": 130.2, "confidence": 0.85}
    """
    # Find segment containing evidence quote (text search)
    for segment in segments:
        if claim['evidence'][:50] in segment['text']:
            return {
                "timestamp_start": segment['start'],
                "timestamp_end": segment['start'] + segment['duration'],
                "confidence": 0.85  # Segment-level precision (5-10 sec window)
            }

    # Fallback: semantic search
    return estimate_timestamp_semantic(claim, segments)
```

**Precision comparison:**
- Whisper (word-level): ±0.5 seconds
- YouTube (segment-level): ±5 seconds

**Impact:** User clicking timestamp jumps to approximately correct location (5-second window vs exact moment). Acceptable for podcast navigation.

#### 4.2.4 Lazy Speaker Attribution Layer

**Purpose:** Identify who made high-value claims (not all claims)

**Why "lazy":**
- Only runs for claims where we need speaker info
- Skips C-tier claims entirely (users don't care who said low-value claims)
- Processes claims independently (failure on one doesn't affect others)

**Decision logic:**

```python
for claim in all_claims:
    if claim['importance'] >= 7:  # A-tier (8-10) or B-tier (6-7)
        claim['speaker'] = attribute_speaker(claim, transcript, metadata)
    else:  # C-tier (0-5)
        claim['speaker'] = None  # Don't bother attributing
```

**Typical distribution:**
- 3-hour podcast: 50 total claims
- A-tier (importance 8-10): 12 claims → attribute
- B-tier (importance 6-7): 18 claims → attribute
- C-tier (importance 0-5): 20 claims → skip

**Effort:** 30 speaker attributions instead of 400 segment attributions (13x reduction)

**Implementation:**

```python
def attribute_speaker_to_claim(claim: dict, transcript: str, metadata: dict) -> dict:
    """
    Targeted speaker attribution for a single claim.

    Uses claim content + local context as attribution signals.
    """
    # Extract 60-second context window around claim
    context_start = claim['timestamp_start'] - 30
    context_end = claim['timestamp_end'] + 30
    context_window = extract_context(transcript, context_start, context_end)

    prompt = f"""Identify who made this claim.

CLAIM: "{claim['canonical']}"
TIMESTAMP: {claim['timestamp_start']:.1f}s - {claim['timestamp_end']:.1f}s

CONTEXT (60-second window around claim):
{context_window}

METADATA:
Title: {metadata['title']}
Channel: {metadata['channel_name']}
Participants: {metadata.get('participants', [])}
Description: {metadata['description'][:300]}

ANALYSIS GUIDELINES:
1. Check for first-person language ("I think", "my research", "in my view")
2. Look for turn-taking patterns (question → claim → response)
3. Match topic to participant expertise
4. Check for self-introductions nearby
5. Consider conversational flow

Return JSON:
{{
  "speaker_name": "Jeff Snider",
  "confidence": 0.92,
  "reasoning": [
    "Uses first-person: 'In my view, the eurodollar market...'",
    "Topic is eurodollar markets (matches guest expertise)",
    "Timestamp 15:30 is guest response section (turn-taking pattern)"
  ]
}}

IMPORTANT: If uncertain, return "Unknown" with low confidence rather than guessing.
"""

    response = llm.complete(prompt, temperature=0.1)
    return parse_speaker_attribution(response)
```

**Cost per claim:** ~$0.004 (60-second context = ~200 tokens)

**Total cost for 30 high-value claims:** 30 × $0.004 = $0.12

**Attribution signals the LLM can use:**

1. **First-person language:**
   ```
   Claim: "My research shows dopamine..."
   Signal: "My research" = speaker owns this research
   ```

2. **Expertise matching:**
   ```
   Claim: "The eurodollar market determines global liquidity"
   Metadata: Guest is "Jeff Snider, eurodollar expert"
   Signal: Complex finance topic matches guest expertise
   ```

3. **Turn-taking patterns:**
   ```
   [15:20] Host: "What about inflation?"
   [15:23] Claim: "Asset inflation is distinct from CPI"
   [15:45] Host: "That's fascinating"
   Signal: Claim is sandwiched between host statements = guest response
   ```

4. **Self-introductions:**
   ```
   [00:30] "I'm Andrew Huberman, and today we're discussing..."
   [05:15] Claim: "Dopamine regulates motivation, not pleasure"
   Signal: Same speaker who introduced themselves
   ```

5. **Pronoun consistency:**
   ```
   "In my view, the Fed's actions create distortions. I think this..."
   Signal: "my view" + "I think" = same speaker across sentences
   ```

**Why this works better than acoustic diarization:**

Acoustic models only hear:
- Voice frequency
- Speaking rate
- Pitch patterns

They cannot understand:
- Semantic content
- Expertise domains
- Conversational structure
- Self-reference

LLMs can use ALL of these signals for attribution.

---

## 5. Implementation Phases

### Phase 0: Empirical Testing (2-3 days)

**Purpose:** Validate assumptions before committing to architecture overhaul

**Tasks:**

#### 5.0.1 YouTube Transcript Quality Test
```
1. Install dependency:
   pip install youtube-transcript-api

2. Select 10 representative podcasts:
   - 3 high-quality (clear audio, single speaker)
   - 4 typical quality (interview format, good audio)
   - 3 challenging (multiple speakers, accents, jargon)

3. Run comparison test:
   python test_youtube_vs_whisper_quality.py <url> --output results.json

4. Collect metrics:
   - Word Error Rate (WER)
   - Claim count ratio (YouTube vs Whisper)
   - Claim quality (importance, confidence)
   - Processing time difference
   - Sample claim comparison (are they semantically equivalent?)

5. Decision criteria:
   - If avg WER < 0.25 (75%+ accuracy) → YouTube viable
   - If claim_count_ratio > 0.85 → YouTube extracts 85%+ of claims
   - If claim_quality similar → YouTube acceptable
```

**Deliverable:** Data-driven decision on YouTube transcript viability

**Possible outcomes:**
- ✅ YouTube works: Proceed with hybrid YouTube/Whisper approach
- ❌ YouTube poor: Use Whisper-only, skip YouTube integration
- ⚠️ Mixed results: Use YouTube for simple content, Whisper for complex

#### 5.0.2 HCE Integration into Test Script

Currently `test_youtube_vs_whisper_quality.py` uses mock claim extraction. Must integrate real pipeline:

```python
# Replace mock extraction
def extract_claims_real(transcript_text: str, metadata: dict) -> list[dict]:
    from knowledge_system.processors.hce.unified_miner import UnifiedMiner
    from knowledge_system.processors.hce.flagship_evaluator import FlagshipEvaluator

    # Mine entities
    miner = UnifiedMiner(llm_provider="gemini", model="gemini-2.0-flash")
    mined = miner.mine(transcript_text, metadata)

    # Evaluate claims
    evaluator = FlagshipEvaluator(llm_provider="gemini")
    scored_claims = evaluator.evaluate(mined['claims'])

    return scored_claims
```

**Challenges:**
- UnifiedMiner expects full TranscriptionOutput object, not plain text
- May need to create minimal TranscriptionOutput wrapper
- Settings and config dependencies

**Deliverable:** Test script that extracts real claims for comparison

#### 5.0.3 Analyze Results and Make Go/No-Go Decision

Review test results with decision matrix:

| Metric | Threshold | YouTube Result | Whisper Result | Decision |
|--------|-----------|----------------|----------------|----------|
| Accuracy (WER) | <0.25 | ? | 0.02 (98%) | ? |
| Claims extracted | >40 | ? | 52 | ? |
| A-tier claims | >10 | ? | 14 | ? |
| Claim overlap | >85% | ? | 100% | ? |
| Processing time | <60s | 5s | 900s | YouTube wins |
| Cost | <$0.10 | $0.01 | $0.35 | YouTube wins |

**Decision point:**
- If YouTube meets thresholds → Proceed to Phase 1
- If YouTube fails → Redesign without YouTube, Whisper-only
- If mixed → Use hybrid (quality assessment determines which path)

**Estimated time:** 2-3 days (waiting for Whisper transcription is bottleneck)

---

### Phase 1: Prototype Claims-First Extraction (1 week)

**Purpose:** Build minimal viable claims-first pipeline to validate approach

**Scope:** Single-file prototype, no GUI integration, no database changes

#### 5.1.1 Create Prototype Script

**File:** `prototype_claims_first.py`

**Features:**
1. Accepts video URL
2. Gets transcript (YouTube or Whisper, configurable)
3. Extracts all entities in single LLM call
4. Matches timestamps to claims
5. Attributes speakers to A/B-tier claims only
6. Outputs JSON results

**Not included in prototype:**
- Database integration
- GUI changes
- Batch processing
- Error recovery
- Full production error handling

**Success criteria:**
- Processes a 1-hour podcast end-to-end
- Extracts claims, jargon, people, concepts
- Timestamps are accurate (±5 sec for YouTube, ±1 sec for Whisper)
- Speaker attribution works for high-value claims
- Total processing time <2 minutes (YouTube path) or <12 minutes (Whisper path)

#### 5.1.2 Test on 20 Real Podcasts

**Purpose:** Identify edge cases and failure modes

**Test matrix:**

| Category | Count | Examples |
|----------|-------|----------|
| Single speaker monologue | 4 | Andrew Huberman solo episodes |
| Two-person interview | 8 | Joe Rogan, Lex Fridman |
| Multi-speaker panel | 4 | Roundtable discussions |
| Heavy jargon/technical | 4 | Finance, science podcasts |

**Measure:**
- Claim quality (manual review of samples)
- Speaker attribution accuracy (check 20 random claims)
- Timestamp accuracy (click timestamp, does it jump to right spot?)
- Processing failures (errors, crashes, timeouts)

**Document failure patterns:**
- Which podcasts fail?
- What types of errors occur?
- Are failures recoverable?

#### 5.1.3 Compare to Current System

**Purpose:** Validate that new approach is actually better

**Metrics to compare:**

| Metric | Current System | New Prototype | Change |
|--------|----------------|---------------|--------|
| Processing time | 15 min | ? min | ? |
| Cost per podcast | $0.40 | $? | ? |
| Lines of code | 3,800 | ? | ? |
| Dependencies | 8 major | ? | ? |
| Speaker attribution accuracy | ~75%? | ?% | ? |
| Claim extraction quality | Baseline | Compare | ? |
| Failure rate | ?% | ?% | ? |

**Decision criteria:**
- If new approach is equal or better on all metrics → Proceed to Phase 2
- If new approach is significantly worse on critical metric → Revisit design
- If mixed results → Identify specific improvements needed

**Deliverable:**
- Working prototype script
- Test results from 20 podcasts
- Comparison report with recommendation

**Estimated time:** 1 week

---

### Phase 2: Production Implementation (2-3 weeks)

**Purpose:** Replace current diarization pipeline with claims-first architecture

**Scope:** Full production code, error handling, database integration, no GUI yet

#### 5.2.1 Create New Processing Modules

**New files to create:**

1. **`src/knowledge_system/processors/transcript_fetcher.py`**
   - Unified interface for getting transcripts
   - Supports YouTube API and Whisper
   - Quality assessment logic
   - Auto-upgrade decision logic

2. **`src/knowledge_system/processors/claims_first_pipeline.py`**
   - Main orchestrator for new pipeline
   - Calls unified entity extraction
   - Handles timestamp matching
   - Lazy speaker attribution
   - Error recovery

3. **`src/knowledge_system/processors/timestamp_matcher.py`**
   - Fuzzy quote matching
   - Word-level timestamp assignment
   - Segment-level timestamp handling
   - Confidence scoring

4. **`src/knowledge_system/processors/lazy_speaker_attribution.py`**
   - Selective attribution for high-value claims
   - Context window extraction
   - LLM prompting for attribution
   - Confidence thresholds

**Modified files:**

1. **`src/knowledge_system/processors/audio_processor.py`**
   - Add flag: `use_claims_first_pipeline: bool = False`
   - If True, skip diarization and use new pipeline
   - If False, use existing pipeline (for A/B testing)

2. **`src/knowledge_system/processors/hce/unified_miner.py`**
   - Support plain text input (not just TranscriptionOutput)
   - Handle both word-level and segment-level timestamps
   - Cross-reference entities in single pass

3. **`src/knowledge_system/config.py`**
   - Add config: `transcript_source: "auto" | "youtube" | "whisper"`
   - Add config: `youtube_quality_threshold: float = 0.7`
   - Add config: `lazy_attribution_min_importance: int = 7`

**Deprecated (not deleted, just bypassed):**

Files to mark as deprecated but keep for rollback:

1. `src/knowledge_system/processors/diarization.py`
2. `src/knowledge_system/voice/voice_fingerprinting.py`
3. `src/knowledge_system/processors/speaker_processor.py` (parts of it)
4. `src/knowledge_system/utils/llm_speaker_suggester.py`

Move to: `src/knowledge_system/_deprecated_diarization/`

#### 5.2.2 Database Schema Updates

**New columns needed:**

```sql
-- In claims table
ALTER TABLE claims ADD COLUMN timestamp_precision TEXT DEFAULT 'word';
  -- Values: 'word', 'segment', 'none'

ALTER TABLE claims ADD COLUMN transcript_source TEXT DEFAULT 'whisper';
  -- Values: 'youtube', 'whisper', 'manual'

ALTER TABLE claims ADD COLUMN speaker_attribution_confidence REAL;
  -- 0.0 to 1.0, NULL if not attributed

-- In media_sources table
ALTER TABLE media_sources ADD COLUMN transcript_source TEXT;
  -- Track which method was used for this source

ALTER TABLE media_sources ADD COLUMN transcript_quality_score REAL;
  -- YouTube quality assessment score (if applicable)
```

**Migration script:** `scripts/add_claims_first_columns.py`

#### 5.2.3 Integration with Existing Systems

**HCE Pipeline integration:**

Current flow:
```
AudioProcessor → Transcription + Diarization → HCE Pipeline
```

New flow:
```
ClaimsFirstPipeline → Transcription (no diarization) → HCE Pipeline with lazy attribution
```

**Changes needed:**

1. **UnifiedMiner must accept undiarized transcripts:**
   ```python
   # Current: expects TranscriptionOutput with speaker labels
   # New: accepts plain text OR TranscriptionOutput

   def mine(self, input: str | TranscriptionOutput, metadata: dict):
       if isinstance(input, str):
           # Plain text mode (no speakers yet)
           transcript_text = input
       else:
           # TranscriptionOutput mode (backward compatible)
           transcript_text = input.text
   ```

2. **FlagshipEvaluator must score claims without speakers:**
   ```python
   # Speaker attribution happens AFTER evaluation
   # Evaluator should not require speaker info
   ```

3. **Database storage must handle partial speaker info:**
   ```python
   # Some claims have speakers, some don't (C-tier)
   # This is intentional, not a bug

   if claim.importance >= 7:
       claim.speaker = attribute_speaker(claim)
   else:
       claim.speaker = None  # Explicitly unattributed
   ```

**Queue system integration:**

The Queue tab visualizes pipeline stages. New stages:

| Old Stages | New Stages |
|------------|------------|
| Download | Download (same) |
| Transcribe | Transcribe (same) |
| Diarize | **REMOVED** |
| Voice Fingerprint | **REMOVED** |
| Speaker Attribution | **REMOVED** |
| Extract Claims | Extract All Entities (new: claims + jargon + people + concepts in one call) |
| Evaluate Claims | Evaluate Claims (same) |
| | **NEW: Lazy Speaker Attribution** (runs after evaluation, only for A/B tier) |

**File generation integration:**

Current: Transcript markdown has speaker labels on every segment

New options:
1. **Option A:** Generate transcript without speakers (simpler)
   ```markdown
   ## Transcript

   [00:15] The Federal Reserve's balance sheet expansion...
   [00:45] That's a fascinating point about inflation...
   ```

2. **Option B:** Generate transcript with approximate speakers (if confident)
   ```markdown
   ## Transcript

   **Guest** [00:15]: The Federal Reserve's balance sheet expansion...
   **Host** [00:45]: That's a fascinating point about inflation...
   ```

3. **Option C:** Only show speakers on claim-level (not transcript-level)
   ```markdown
   ## High-Value Claims

   **Andrew Huberman** (confidence: 95%):
   > "Dopamine regulates motivation, not pleasure"
   > Evidence: [Link to timestamp 15:30]
   ```

**Recommendation:** Start with Option A (no speakers in transcript), add Option C (speakers on claims only).

#### 5.2.4 Error Handling and Resilience

**Failure scenarios to handle:**

1. **YouTube transcript unavailable**
   ```python
   try:
       transcript = get_youtube_transcript(video_id)
   except TranscriptsDisabled:
       logger.info("YouTube transcripts disabled, using Whisper")
       transcript = get_whisper_transcript(video_url)
   ```

2. **LLM entity extraction fails**
   ```python
   try:
       entities = unified_miner.mine(transcript)
   except LLMError as e:
       # Retry with different model
       entities = unified_miner.mine(transcript, fallback_model="claude-3.5-sonnet")
   ```

3. **Timestamp matching fails**
   ```python
   timestamp = match_claim_to_timestamps(claim, words)
   if timestamp is None:
       # Fallback: use approximate timing from LLM analysis
       timestamp = estimate_timestamp_from_context(claim, transcript)
   ```

4. **Speaker attribution fails for high-value claim**
   ```python
   try:
       speaker = attribute_speaker(claim, transcript, metadata)
   except Exception as e:
       logger.warning(f"Speaker attribution failed for claim: {e}")
       speaker = {"name": "Unknown", "confidence": 0.0}
   ```

**Graceful degradation:**
- If YouTube transcript fails → Use Whisper
- If word-level timestamps unavailable → Use segment-level
- If speaker attribution fails → Leave as "Unknown" (claim still valuable)
- If entire extraction fails → Save transcript, mark for manual review

#### 5.2.5 A/B Testing Framework

**Purpose:** Run new and old pipelines side-by-side to compare results

**Implementation:**

```python
# In audio_processor.py
class AudioProcessor:
    def __init__(self, use_claims_first: bool = False, ab_test_mode: bool = False):
        self.use_claims_first = use_claims_first
        self.ab_test_mode = ab_test_mode

    def process(self, audio_path):
        if self.ab_test_mode:
            # Run BOTH pipelines, compare results
            old_result = self._process_diarization_first(audio_path)
            new_result = self._process_claims_first(audio_path)

            comparison = compare_results(old_result, new_result)
            log_comparison(comparison)

            return new_result  # Use new by default

        elif self.use_claims_first:
            return self._process_claims_first(audio_path)
        else:
            return self._process_diarization_first(audio_path)
```

**Comparison metrics:**
- Processing time (old vs new)
- Number of claims extracted
- Speaker attribution accuracy (manual review)
- Timestamp accuracy
- Failure rate

**Run A/B test on 100 podcasts:**
- Collect metrics for both pipelines
- Identify any regressions
- Document edge cases where old pipeline performs better

**Decision criteria:**
- If new pipeline is equal or better on 90%+ of podcasts → Deprecate old pipeline
- If new pipeline has significant regressions → Identify and fix before deprecation

**Deliverable:**
- Production-ready claims-first pipeline
- A/B test results from 100 podcasts
- Updated documentation
- Database migrations applied

**Estimated time:** 2-3 weeks

---

### Phase 3: GUI Integration (1 week)

**Purpose:** Expose new pipeline options to users

**Scope:** Update GUI to support transcript source selection and lazy attribution settings

#### 5.3.1 Settings Tab Updates

**New settings to add:**

**Transcription Settings Section:**
```
┌─ Transcript Source ─────────────────────────────────┐
│                                                      │
│ ○ Auto (YouTube first, Whisper if poor quality)     │
│ ○ Always use YouTube transcripts (fastest)          │
│ ○ Always use Whisper (highest quality)              │
│                                                      │
│ YouTube Quality Threshold: [0.7] (0.0-1.0)          │
│   Minimum quality score to use YouTube transcript   │
│                                                      │
└──────────────────────────────────────────────────────┘
```

**Speaker Attribution Settings Section:**
```
┌─ Speaker Attribution ────────────────────────────────┐
│                                                      │
│ [x] Enable lazy speaker attribution                 │
│     Only attribute speakers to high-value claims    │
│                                                      │
│ Minimum Importance for Attribution: [7] (0-10)      │
│   A-tier (8-10) and B-tier (6-7) by default        │
│                                                      │
│ [ ] Attribute speakers to ALL claims                │
│     (slower, not recommended)                        │
│                                                      │
└──────────────────────────────────────────────────────┘
```

#### 5.3.2 Transcription Tab Updates

**Status display enhancements:**

Old display:
```
Processing: video_123.mp4
Stage: Transcribing...
Progress: 45%
```

New display:
```
Processing: video_123.mp4
Transcript Source: YouTube (quality: 0.82)
Stage: Extracting entities...
Progress: 65%

Time saved vs Whisper: 12 min 34 sec
```

**User notifications:**

Show when YouTube transcript is used or upgraded:
```
✓ YouTube transcript quality acceptable (score: 0.82)
  Using fast path (saved 12 minutes)

OR

⚠ YouTube transcript quality poor (score: 0.52)
  Upgrading to Whisper for better accuracy
```

#### 5.3.3 Review Tab Updates

**Claim display with speaker info:**

```
┌─ High-Value Claim (A-tier: 9/10) ───────────────────┐
│                                                      │
│ "The Fed's asset purchases create distortions in    │
│  financial markets without affecting consumer        │
│  inflation as measured by CPI"                       │
│                                                      │
│ Speaker: Jeff Snider (confidence: 92%)               │
│          [Timestamp: 15:30] [Play ▶]                 │
│                                                      │
│ Evidence: "In my view, the Fed's balance sheet..."  │
│                                                      │
│ [Edit Speaker] [Mark Unverified] [Add Note]         │
└──────────────────────────────────────────────────────┘
```

**Filter by speaker attribution:**
```
Filters:
  [x] Show only claims with speakers
  [ ] Show unattributed claims
  [ ] Speaker confidence > 80%
```

#### 5.3.4 Queue Tab Updates

**New pipeline stages:**

Old:
```
video_123.mp4
├─ ✓ Download (2 min)
├─ ✓ Transcribe (12 min)
├─ ✓ Diarize (1 min)
├─ ✓ Voice Fingerprint (30 sec)
├─ → Extract Claims...
└─ ⏳ Evaluate Claims
```

New:
```
video_123.mp4
├─ ✓ Download (2 min)
├─ ✓ Get Transcript [YouTube] (5 sec) ⚡ Fast path
├─ ✓ Extract All Entities (30 sec)
├─ → Evaluate Claims...
└─ ⏳ Lazy Speaker Attribution (12/45 claims)
```

**Show YouTube vs Whisper path:**
- Green lightning bolt (⚡) for YouTube fast path
- Standard icon for Whisper path
- Show time saved when YouTube is used

#### 5.3.5 User Documentation

**In-app help text:**

"**YouTube Transcripts (Beta)**

YouTube provides auto-generated transcripts instantly. In testing, these are 75-85% accurate for typical podcasts—good enough for claim extraction.

**When to use:**
- Default 'Auto' mode tries YouTube first
- Upgrades to Whisper if quality is poor
- You can always force Whisper for critical episodes

**Trade-offs:**
- YouTube: 5 seconds, ±5 sec timestamp precision
- Whisper: 12 minutes, ±1 sec timestamp precision

**Speaker Attribution:**

The new 'lazy attribution' approach only identifies speakers for high-value claims (importance ≥7). This is faster and more reliable than trying to identify speakers for the entire transcript.

**Why?**
- Focuses effort where it matters (A/B tier claims)
- Uses claim content as attribution signal
- More context = better accuracy"

**Deliverable:**
- Updated Settings tab with new options
- Updated status displays showing transcript source
- Updated Review tab with speaker confidence
- Updated Queue tab with new pipeline stages
- In-app documentation

**Estimated time:** 1 week

---

### Phase 4: Testing and Validation (1 week)

**Purpose:** Comprehensive testing before deprecating old pipeline

#### 5.4.1 Automated Testing

**Unit tests:**
- Timestamp matching with fuzzy quotes
- Speaker attribution with various context types
- YouTube quality assessment
- Graceful degradation scenarios

**Integration tests:**
- End-to-end processing with YouTube transcripts
- End-to-end processing with Whisper
- Hybrid path (YouTube → upgrade to Whisper)
- Error recovery scenarios

**Performance tests:**
- 100 podcasts through new pipeline
- Measure: time, cost, accuracy
- Compare to baseline from A/B testing

#### 5.4.2 Manual Validation

**Domain expert review:**
- Select 20 podcasts (diverse topics)
- Expert reviews claims and speaker attributions
- Measures accuracy, identifies errors
- Documents edge cases

**User acceptance testing:**
- 5-10 beta users test new pipeline
- Collect feedback on UX, accuracy, speed
- Identify usability issues

**Regression testing:**
- Compare new pipeline output to old pipeline output
- For 50 previously-processed podcasts
- Ensure no major regressions in claim quality

#### 5.4.3 Performance Benchmarking

**Metrics to collect:**

| Metric | Target | Actual |
|--------|--------|--------|
| Avg processing time (YouTube) | <2 min | ? |
| Avg processing time (Whisper) | <12 min | ? |
| YouTube usage rate | 60-70% | ? |
| Speaker attribution accuracy | >85% | ? |
| Claim extraction quality | ≥ old pipeline | ? |
| Failure rate | <5% | ? |
| User satisfaction | >8/10 | ? |

**Deliverable:**
- Test results showing readiness for production
- Performance benchmarks
- User feedback summary
- List of known issues and workarounds

**Estimated time:** 1 week

---

### Phase 5: Deprecation and Cleanup (1 week)

**Purpose:** Remove old diarization code, finalize new architecture

#### 5.5.1 Make Claims-First Default

**Config changes:**
```python
# In config.py
DEFAULT_USE_CLAIMS_FIRST = True  # Was False during A/B testing
DEFAULT_TRANSCRIPT_SOURCE = "auto"  # YouTube first, Whisper fallback
```

**GUI changes:**
- Remove "Speaker Diarization" tab (or mark as deprecated)
- Remove "Voice Fingerprinting" settings
- Keep old settings visible but disabled with note: "Using new claims-first pipeline"

#### 5.5.2 Code Cleanup

**Move to deprecated:**
```
src/knowledge_system/_deprecated_diarization/
├── diarization.py
├── voice_fingerprinting.py
├── speaker_processor.py (most of it)
├── llm_speaker_suggester.py
└── README.md (explains why deprecated, how to re-enable if needed)
```

**Update imports:**
- Scan codebase for imports of deprecated modules
- Update or comment out
- Add warnings if old code paths are triggered

**Remove dependencies (optional):**
- Can remove pyannote.audio, speechbrain, etc. from requirements
- Or keep them as optional dependencies for 1-2 releases
- Mark as deprecated in requirements.txt

#### 5.5.3 Documentation Updates

**Update docs:**
- ARCHITECTURE_UNIFIED.md
- DATABASE_ARCHITECTURE.md
- PIPELINE_ARCHITECTURE.md
- README.md (installation instructions, feature list)

**Create new docs:**
- CLAIMS_FIRST_ARCHITECTURE.md (this document becomes reference)
- TRANSCRIPT_SOURCE_GUIDE.md (YouTube vs Whisper decision guide)
- LAZY_ATTRIBUTION_EXPLAINED.md (how and why it works)

**Update changelog:**
```markdown
## v2.0.0 - Claims-First Architecture (2025-12-XX)

### Major Changes
- **BREAKING:** Replaced speaker-first pipeline with claims-first architecture
- Reduced processing time by 60-90% (YouTube transcript path)
- Reduced code complexity by 64% (~2,500 lines removed)
- Removed dependencies: pyannote.audio, speechbrain, wav2vec2, ECAPA-TDNN

### New Features
- YouTube transcript support (auto-upgrade to Whisper if poor quality)
- Lazy speaker attribution (only for high-value claims)
- Single-pass entity extraction (claims + jargon + people + concepts)

### Deprecated
- Speaker diarization (pyannote.audio)
- Voice fingerprinting (acoustic similarity)
- Full-transcript speaker attribution

### Migration Guide
Old pipeline still available via config flag for 1 release:
`use_claims_first_pipeline: false`

See CLAIMS_FIRST_MIGRATION_GUIDE.md for details.
```

#### 5.5.4 Release

**Version bump:**
- v1.x.x → v2.0.0 (major version for breaking change)

**Release notes:**
- Highlight speed improvements
- Highlight simplification
- Document breaking changes
- Provide migration guide

**Communication:**
- Announce to users
- Explain benefits
- Address concerns about speaker accuracy
- Provide support channel for issues

**Deliverable:**
- Clean codebase with deprecated code moved
- Updated documentation
- Release v2.0.0
- User communication sent

**Estimated time:** 1 week

---

## 6. Risk Analysis

### 6.1 Technical Risks

#### Risk 6.1.1: YouTube Transcripts Worse Than Expected

**Severity:** HIGH
**Probability:** MEDIUM (30%)

**Description:**
Testing may reveal YouTube transcripts are only 50-60% accurate (worse than estimated 70-80%), making them unsuitable for claim extraction.

**Impact:**
- Cannot use YouTube fast path
- Must use Whisper for all videos
- Processing time remains ~15 minutes (no improvement)
- Still gain from claims-first architecture, but lose speed benefit

**Mitigation:**
1. Phase 0 testing will reveal this before committing to architecture
2. Hybrid approach allows falling back to Whisper
3. Even without YouTube, claims-first is simpler than current system

**Contingency:**
- If YouTube fails testing, proceed with Whisper-only claims-first architecture
- Still achieve complexity reduction and better attribution
- Accept that speed gains won't materialize

#### Risk 6.1.2: LLM Speaker Attribution Less Accurate Than Acoustic

**Severity:** MEDIUM
**Probability:** LOW (15%)

**Description:**
Despite better context, LLM attribution might be worse than current acoustic + LLM hybrid.

**Impact:**
- Speaker labels on claims are wrong more often
- Users lose trust in speaker attribution
- Must revert to acoustic diarization

**Evidence against:**
- Current acoustic system only ~75% accurate (has many errors already)
- LLMs have richer attribution signals (content, expertise, turn-taking)
- Testing on 20 podcasts in Phase 1 will reveal accuracy

**Mitigation:**
1. Measure attribution accuracy in Phase 1 before full implementation
2. Compare to current system in A/B test (Phase 2)
3. Keep confidence scores to flag uncertain attributions
4. Allow users to override/correct speaker labels

**Contingency:**
- If LLM attribution is significantly worse, keep acoustic diarization for speaker segmentation
- Use hybrid: acoustic for segmentation, LLM for naming
- Not as simple, but still better than current 6-layer system

#### Risk 6.1.3: Timestamp Matching Fails for Paraphrased Claims

**Severity:** MEDIUM
**Probability:** MEDIUM (40%)

**Description:**
LLM rewrites claims instead of quoting exactly, making timestamp matching impossible.

**Impact:**
- Claims don't have accurate timestamps
- Users can't jump to claim location in video
- Degrades user experience

**Evidence:**
- LLMs do paraphrase frequently
- Fuzzy matching can handle minor differences
- Worst case: use semantic search to approximate timestamp

**Mitigation:**
1. Instruct LLM to quote verbatim in evidence field
2. Implement fuzzy matching with 70% threshold
3. Fallback to semantic similarity for approximate timestamps
4. Accept ±5-10 second accuracy instead of perfect precision

**Contingency:**
- If timestamp matching fails completely, use semantic search exclusively
- Timestamps will be approximate (±10 seconds)
- Still acceptable for podcast navigation (user can scrub to exact moment)

#### Risk 6.1.4: Single LLM Call Too Expensive

**Severity:** LOW
**Probability:** LOW (10%)

**Description:**
If Gemini 2.0 Flash quality is poor, falling back to Claude 3.5 Sonnet makes cost $0.33/podcast instead of $0.007.

**Impact:**
- Processing 10,000 podcasts = $3,300 instead of $70
- 47x more expensive than expected
- Still cheaper than current $0.40/podcast ($4,000 for 10K)

**Mitigation:**
1. Test Gemini quality in Phase 0
2. If poor, negotiate Claude API credits or use local LLM
3. Optimize prompt to reduce output tokens
4. Chunk longer podcasts to stay under context limits

**Contingency:**
- Use local LLM (Qwen, Llama) for bulk processing
- Reserve cloud LLMs for high-value content
- Accept slower processing for cost savings

#### Risk 6.1.5: Lost-in-Middle Problem Returns

**Severity:** LOW
**Probability:** LOW (10%)

**Description:**
Despite claims that Gemini 2.0 solved "lost in the middle," it might still miss claims from middle of transcript.

**Impact:**
- Fewer claims extracted
- Bias toward beginning/end of podcast
- Incomplete knowledge graph

**Evidence against:**
- Gemini 2.0 Flash specifically addressed this issue
- Our task is extraction (scanning), not retrieval (finding specific fact)
- Even if some degradation, likely still acceptable

**Mitigation:**
1. Test on long podcasts (3+ hours) in Phase 0
2. Compare claim distribution (beginning vs middle vs end)
3. If issue detected, use chunking strategy
4. Process in 30-minute chunks with overlap

**Contingency:**
- Implement chunking for all podcasts >90 minutes
- Deduplicate claims across chunk boundaries
- Slightly slower but ensures no claims missed

### 6.2 Product Risks

#### Risk 6.2.1: Users Expect Full Diarized Transcripts

**Severity:** MEDIUM
**Probability:** LOW (20%)

**Description:**
Some users may rely on fully diarized transcripts for use cases we didn't anticipate.

**Impact:**
- User complaints
- Feature regression perception
- Need to maintain both pipelines

**Evidence against:**
- Your observation: users never view full transcripts on website
- They browse claims/jargon/people/concepts
- Transcripts are intermediate artifacts, not end product

**Mitigation:**
1. Survey users before deprecating old pipeline
2. Keep old pipeline available via config flag for 1-2 releases
3. Document migration path
4. Offer to generate diarized transcripts on demand

**Contingency:**
- Maintain old pipeline as "legacy mode" indefinitely
- Default to new pipeline, opt-in to old
- Most users won't notice change

#### Risk 6.2.2: Speaker Attribution Confidence Too Low

**Severity:** MEDIUM
**Probability:** MEDIUM (30%)

**Description:**
If speaker confidence averages 60-70% instead of 85-95%, users may not trust attributions.

**Impact:**
- Users ignore speaker labels
- Defeats purpose of attribution
- Wastes effort on low-confidence assignments

**Mitigation:**
1. Set confidence threshold (only show if >80%)
2. Mark low-confidence attributions visually in UI
3. Allow users to provide feedback/corrections
4. Use corrections to improve prompts

**Contingency:**
- If confidence consistently low, add human-in-the-loop review
- Batch review interface: user confirms/corrects 20 attributions at once
- System learns from corrections

#### Risk 6.2.3: Claim Quality Degrades With YouTube Transcripts

**Severity:** HIGH
**Probability:** MEDIUM (30%)

**Description:**
Transcription errors in YouTube captions lead to garbled claims that aren't useful.

**Impact:**
- Extracted claims are nonsensical
- Users can't rely on claim accuracy
- Degrades product value

**Evidence:**
- LLMs are somewhat robust to transcription errors
- But if errors are too severe, claim extraction will suffer

**Mitigation:**
1. Phase 0 testing will measure this directly
2. Quality assessment catches poor transcripts
3. Auto-upgrade to Whisper prevents bad extractions
4. Users can manually request Whisper re-processing

**Contingency:**
- If YouTube claim quality is significantly worse, raise quality threshold
- More videos will auto-upgrade to Whisper
- Accept slower processing for better quality

### 6.3 Organizational Risks

#### Risk 6.3.1: Incomplete Testing Before Deprecation

**Severity:** HIGH
**Probability:** MEDIUM (30%)

**Description:**
Rushing to deprecate old pipeline before thoroughly testing new one leads to production issues.

**Impact:**
- Bugs in production
- User complaints
- Emergency rollback needed
- Loss of confidence in system

**Mitigation:**
1. Strict phase gates (don't proceed until tests pass)
2. A/B testing on 100+ podcasts before deprecation
3. Keep old pipeline available as fallback for 2 releases
4. Gradual rollout (10% → 50% → 100% of users)

**Contingency:**
- If major issues discovered after deprecation, rollback immediately
- Re-enable old pipeline via config flag
- Fix issues in new pipeline before re-attempting deprecation

#### Risk 6.3.2: Scope Creep During Implementation

**Severity:** MEDIUM
**Probability:** HIGH (60%)

**Description:**
During implementation, temptation to add "just one more feature" extends timeline indefinitely.

**Impact:**
- Project drags on for months
- Benefits delayed
- Team fatigue

**Mitigation:**
1. Strict scope for each phase
2. "Phase 6: Future Enhancements" document for ideas
3. Weekly progress reviews
4. Ship MVP first, iterate later

**Contingency:**
- If timeline slips >2 weeks, cut scope
- Ship minimal viable version
- Add enhancements in point releases

#### Risk 6.3.3: Dependency Removal Breaks Existing Workflows

**Severity:** MEDIUM
**Probability:** LOW (15%)

**Description:**
Removing pyannote/speechbrain dependencies breaks unrelated workflows we forgot about.

**Impact:**
- Other features stop working
- Emergency dependency re-addition
- Embarrassment

**Evidence against:**
- Dependencies are only used for diarization pipeline
- Codebase search will reveal all usages

**Mitigation:**
1. Grep entire codebase for pyannote/speechbrain imports
2. Test all workflows in Phase 4
3. Keep dependencies as optional for 1 release
4. Document deprecation timeline

**Contingency:**
- If unexpected usage found, keep dependency
- Deprecate in future release after migrating that workflow

---

## 7. Success Criteria

### 7.1 Technical Success Metrics

**Processing Speed:**
- [ ] YouTube path: <2 minutes average (90% faster than current)
- [ ] Whisper path: <12 minutes average (20% faster than current)
- [ ] 60-70% of videos use YouTube fast path

**Accuracy:**
- [ ] Speaker attribution accuracy ≥85% (measured on 100-podcast test set)
- [ ] Claim extraction quality ≥95% of current system (measured by overlap)
- [ ] Timestamp accuracy: ±5 seconds for YouTube, ±1 second for Whisper

**Cost:**
- [ ] Average cost per podcast ≤$0.20 (50% reduction from $0.40)
- [ ] YouTube path: ~$0.07 (83% reduction)
- [ ] Whisper path: ~$0.35 (13% reduction)

**Reliability:**
- [ ] Failure rate <5% (currently ~10-15% due to diarization issues)
- [ ] Graceful degradation: no catastrophic failures
- [ ] Error messages are actionable

**Code Quality:**
- [ ] Total lines of code reduced by 50%+ (~2,000 lines removed)
- [ ] Number of major dependencies reduced from 8 to ≤3
- [ ] Test coverage maintained or improved (≥80%)

### 7.2 Product Success Metrics

**User Experience:**
- [ ] User satisfaction ≥8/10 in survey
- [ ] Processing time reduction noticed and appreciated
- [ ] No major complaints about speaker attribution accuracy
- [ ] Claims on website have reliable speaker labels (≥80% of A-tier claims)

**Feature Parity:**
- [ ] All current claim extraction features work with new pipeline
- [ ] Speaker attribution available for high-value claims
- [ ] Timestamps allow jumping to claim location
- [ ] Export formats maintain quality

**Adoption:**
- [ ] 90%+ of new processing uses claims-first pipeline
- [ ] <10% of users need to use legacy pipeline
- [ ] No rollbacks or emergency reverts needed

### 7.3 Business Success Metrics

**Development Efficiency:**
- [ ] 60% reduction in maintenance burden (fewer dependencies to update)
- [ ] Bug reports related to speaker diarization reduced by 80%
- [ ] Time to add new features reduced (simpler architecture)

**Scalability:**
- [ ] Can process 10,000 podcasts/month sustainably
- [ ] Infrastructure costs reduced by 40% (less compute for Whisper)
- [ ] Pipeline resilient to spikes in usage

**Future-Proofing:**
- [ ] Architecture supports future enhancements (e.g., video content analysis)
- [ ] Easy to swap LLM providers (abstraction layer works)
- [ ] Codebase understandable by new developers

---

## 8. Rollback Plan

### 8.1 Triggers for Rollback

Rollback to old pipeline if ANY of:
1. Speaker attribution accuracy <70% (measured on 100 podcasts)
2. Claim extraction quality <80% of baseline
3. Failure rate >15%
4. User satisfaction <6/10
5. Critical bugs affecting >30% of videos

### 8.2 Rollback Procedure

**Immediate rollback (emergency):**
```python
# In config.py
DEFAULT_USE_CLAIMS_FIRST = False  # Revert to old pipeline
```

**Redeploy:**
- Push config change to production
- Restart services
- Monitor error rates
- Notify users of temporary revert

**Post-rollback:**
1. Analyze root cause of failure
2. Determine if fixable in <1 week
3. If fixable: fix and re-deploy
4. If not fixable: document lessons learned, consider alternative approach

### 8.3 Rollback Readiness

**During Phases 2-4:**
- Keep old pipeline code functional
- Test old pipeline weekly to ensure it still works
- Maintain ability to switch back via config flag

**After Phase 5 (deprecation):**
- Keep old code in `_deprecated_diarization/` for 2 releases
- Document how to re-enable if needed
- After 2 releases (~6 months), if no issues, delete old code

---

## 9. Open Questions

### 9.1 Technical Questions Requiring Research

**Q1: How accurate are YouTube transcripts on our specific podcast genres?**
- **Status:** MUST ANSWER in Phase 0
- **Method:** Test on 10 representative podcasts, measure WER
- **Decision impact:** Determines if YouTube path is viable

**Q2: Can we achieve 85%+ speaker attribution accuracy with LLM-only approach?**
- **Status:** MUST ANSWER in Phase 1
- **Method:** Test on 20 podcasts, compare to current system
- **Decision impact:** Determines if we can fully eliminate acoustic diarization

**Q3: How does claim extraction quality change with YouTube vs Whisper transcripts?**
- **Status:** MUST ANSWER in Phase 0
- **Method:** A/B test claims extracted from both sources
- **Decision impact:** Determines default transcript source

**Q4: What's the optimal confidence threshold for lazy attribution?**
- **Status:** SHOULD ANSWER in Phase 2
- **Method:** Test various thresholds (0.6, 0.7, 0.8, 0.9), measure false positive rate
- **Decision impact:** User experience (show uncertain attributions or hide?)

**Q5: Does Gemini 2.0 Flash have "lost in middle" issues for 3-hour podcasts?**
- **Status:** SHOULD ANSWER in Phase 0
- **Method:** Test on 5 very long podcasts (>3 hours), analyze claim distribution
- **Decision impact:** Need for chunking strategy

### 9.2 Product Questions Requiring User Research

**Q1: Do any users actually need fully diarized transcripts?**
- **Status:** SHOULD ANSWER before Phase 5
- **Method:** User survey, usage analytics
- **Decision impact:** Whether to completely deprecate old pipeline

**Q2: What's the minimum acceptable timestamp precision for users?**
- **Status:** COULD ANSWER in Phase 3
- **Method:** User testing, A/B test ±5 sec vs ±1 sec precision
- **Decision impact:** Whether segment-level timestamps are acceptable

**Q3: How important is speaker attribution to users?**
- **Status:** SHOULD ANSWER before Phase 1
- **Method:** User interviews, feature usage analytics
- **Decision impact:** How much effort to invest in attribution accuracy

**Q4: Would users accept "Unknown" speaker for C-tier claims?**
- **Status:** SHOULD ANSWER in Phase 3
- **Method:** User testing with prototype UI
- **Decision impact:** Lazy attribution cutoff threshold

### 9.3 Business Questions Requiring Analysis

**Q1: What's the ROI of this overhaul?**
- **Development time:** 6-8 weeks
- **Time savings:** 10-13 min/podcast × 1,000 podcasts/month = 167-217 hours/month
- **Cost savings:** $0.20/podcast × 1,000 podcasts/month = $200/month
- **Maintenance savings:** 60% reduction in bug tickets?
- **Status:** Model after Phase 0 testing with actual numbers

**Q2: Should we maintain old pipeline indefinitely for edge cases?**
- **Cost:** Continued maintenance burden
- **Benefit:** Safety net for users with special needs
- **Decision:** Collect data in Phases 2-4 on % of users needing old pipeline

**Q3: What's the competitive advantage of faster processing?**
- **User acquisition:** Does 180x speedup attract new users?
- **Pricing:** Can we charge less due to lower costs?
- **Market positioning:** "Fastest podcast knowledge extraction"?
- **Status:** Marketing analysis needed

### 9.4 Implementation Questions

**Q1: Should we use Gemini, Claude, or GPT for entity extraction?**
- **Current lean:** Gemini 2.0 Flash (1M context, $0.007)
- **Alternative:** Claude 3.5 Sonnet (200K context, $0.33)
- **Test:** Phase 0 quality comparison
- **Decision criteria:** If Gemini quality ≥90% of Claude, use Gemini

**Q2: Should we chunk long podcasts or rely on long context?**
- **Current lean:** Use full context if <3 hours, chunk if >3 hours
- **Alternative:** Always chunk (more reliable, easier to parallelize)
- **Test:** Phase 0 long podcast testing
- **Decision criteria:** If no "lost in middle" detected, use full context

**Q3: Should YouTube transcripts be default or opt-in?**
- **Current lean:** Default "auto" (try YouTube, upgrade if poor)
- **Alternative:** Opt-in only (safer but slower)
- **Test:** Phase 0 quality testing
- **Decision criteria:** If YouTube accuracy >75% on average, make default

**Q4: How to handle claim timestamp precision in UI?**
- **Option A:** Show precision icon (word-level = green, segment = yellow)
- **Option B:** Don't show (users probably don't care)
- **Option C:** Only show if segment-level (caveat)
- **Test:** User testing in Phase 3

**Q5: Should we integrate HCE into single LLM call or keep separate?**
- **Current lean:** Single call for extraction, separate call for evaluation
- **Alternative:** Extract + evaluate in one call (even cheaper)
- **Trade-off:** Single call is cheaper but harder to debug
- **Decision:** Start with separate calls, consider merging in future

---

## 10. Conclusion

### 10.1 Summary of Proposal

This plan proposes replacing Knowledge Chipper's fragile 6-layer speaker diarization pipeline with a simpler **claims-first architecture**:

**Current:** Audio → Transcribe → Diarize → Voice Fingerprint → Speaker Merge → LLM Attribution → Claim Extract
**Proposed:** Audio → Transcribe → Claim Extract → Lazy Speaker Attribution (high-value claims only)

**Expected benefits:**
- 64% code reduction (~2,500 lines removed)
- 75% dependency reduction (8 → 2 major dependencies)
- 60-90% speed increase (YouTube transcript path)
- Better speaker attribution (LLMs have richer signals than acoustic models)
- Simpler mental model (extract what matters first)

**Key insight:** Users don't need fully diarized transcripts. They need high-quality claims with reliable speakers. Current system optimizes for the wrong thing.

### 10.2 Recommended Next Steps

1. **Immediate (this week):**
   - Run Phase 0 testing on 10 podcasts
   - Install `youtube-transcript-api`
   - Integrate HCE into test script
   - Collect empirical data on YouTube transcript quality

2. **If testing is positive (next 2 weeks):**
   - Build Phase 1 prototype
   - Test on 20 real podcasts
   - Present results and make go/no-go decision

3. **If prototype succeeds (following 4-6 weeks):**
   - Implement Phase 2 (production code)
   - Run A/B test on 100 podcasts
   - Integrate Phase 3 (GUI)
   - Execute Phase 4 (testing)

4. **If all validation passes (final 1-2 weeks):**
   - Phase 5 deprecation
   - Release v2.0.0
   - Monitor production usage

**Total timeline:** 8-10 weeks from start to production release

### 10.3 Go/No-Go Decision Points

**After Phase 0 (Week 1):**
- **GO if:** YouTube transcripts ≥75% accurate, claim extraction quality ≥85% of Whisper
- **NO-GO if:** YouTube transcripts <70% accurate or claim quality significantly worse
- **Contingency:** Proceed with Whisper-only claims-first architecture (still worthwhile)

**After Phase 1 (Week 3):**
- **GO if:** LLM speaker attribution ≥80% accurate, prototype works on 18/20 test podcasts
- **NO-GO if:** LLM attribution <70% or prototype fails on >5 podcasts
- **Contingency:** Revert to acoustic diarization, use LLM for naming only

**After Phase 2 (Week 6):**
- **GO if:** A/B test shows new pipeline equal or better on 80%+ of podcasts
- **NO-GO if:** New pipeline worse on >30% of podcasts or critical failures
- **Contingency:** Keep both pipelines, make old pipeline default, iterate on new pipeline

**After Phase 4 (Week 8):**
- **GO if:** All tests pass, user feedback positive, no critical bugs
- **NO-GO if:** Major issues discovered, user satisfaction <7/10
- **Contingency:** Delay deprecation, fix issues, re-test

### 10.4 Success Definition

This overhaul is successful if, 3 months after v2.0.0 release:

1. ✅ 90%+ of podcasts processed with claims-first pipeline
2. ✅ Processing time reduced by 50%+ on average
3. ✅ Speaker attribution accuracy ≥85% (measured)
4. ✅ User satisfaction ≥8/10
5. ✅ <5% bug reports related to new pipeline
6. ✅ No rollbacks needed
7. ✅ Codebase simpler and easier to maintain

If 6/7 criteria met → Success
If 4-5/7 criteria met → Partial success, iterate
If <4/7 criteria met → Failure, consider rollback or major revisions

---

## Appendix A: Comparison Tables

### A.1 Current vs Proposed Pipeline

| Aspect | Current Pipeline | Proposed Pipeline | Change |
|--------|------------------|-------------------|--------|
| **Lines of code** | ~3,800 | ~1,350 | -64% |
| **Major dependencies** | 8 | 2 | -75% |
| **Model downloads** | ~5GB | ~1GB | -80% |
| **Processing time (avg)** | 15 min | 2-12 min | -20% to -87% |
| **Cost per podcast** | $0.40 | $0.07-$0.35 | -13% to -83% |
| **Points of failure** | 6 (cascading) | 2 (isolated) | -67% |
| **Speaker attribution** | Full transcript | High-value claims only | Selective |
| **Complexity** | Very high | Medium | Simplified |
| **Maintainability** | Low | High | Improved |

### A.2 YouTube vs Whisper Transcripts

| Feature | YouTube Transcript | Whisper Transcript |
|---------|-------------------|-------------------|
| **Accuracy** | 70-85% (estimated) | 95-99% |
| **Speed** | 5 seconds | 10-15 minutes |
| **Cost** | Free | Compute cost |
| **Timestamp precision** | Segment (±5 sec) | Word (±0.5 sec) |
| **Availability** | YouTube only | Any audio source |
| **Quality control** | None | Configurable model |
| **Storage** | None | Audio + models |
| **When to use** | Fast path, good enough | High accuracy needed |

### A.3 Attribution Approaches

| Approach | Effort | Accuracy | Signals Used |
|----------|--------|----------|--------------|
| **Acoustic diarization only** | High | 60-70% | Voice frequency, pitch, rate |
| **Acoustic + LLM (current)** | Very high | 70-80% | Voice + metadata + CSV |
| **LLM-only with context** | Medium | 75-85% (est.) | Content, expertise, turn-taking, metadata |
| **Lazy LLM (proposed)** | Low | 80-90% (est.) | All LLM signals + focused context |

**Key insight:** Doing less (selective attribution) yields better results (richer per-claim context).

---

## Appendix B: Example Scenarios

### B.1 Scenario: 2-Hour Joe Rogan Podcast

**Current Pipeline:**
```
1. Download audio: 2 min
2. Whisper transcribe: 12 min
3. Diarization: 45 sec → detects 3 speakers (SPEAKER_00, SPEAKER_01, SPEAKER_02)
4. Voice fingerprint: 30 sec → merges SPEAKER_02 into SPEAKER_00 (over-segmentation)
5. LLM attribution: 15 sec → SPEAKER_00 = "Joe Rogan", SPEAKER_01 = "Guest Name"
6. Extract claims: 40 sec → 52 claims extracted
7. Total: 15 min 45 sec, $0.42
```

**Proposed Pipeline (Whisper path):**
```
1. Download audio: 2 min
2. Whisper transcribe: 12 min (word-level timestamps)
3. Extract all entities: 35 sec → 52 claims, 18 jargon, 8 people, 5 concepts
4. Filter A/B tier: 14 claims (importance ≥7)
5. Lazy attribution: 10 sec → attribute speakers to 14 claims
6. Total: 14 min 45 sec, $0.36
```

**Savings:** 1 minute, $0.06, much simpler code

**Proposed Pipeline (YouTube path - if YouTube transcript available):**
```
1. Get YouTube transcript: 5 sec
2. Quality check: 2 sec → score 0.78 (good enough)
3. Extract all entities: 35 sec → 48 claims (4 fewer due to transcription errors)
4. Filter A/B tier: 13 claims
5. Lazy attribution: 10 sec
6. Total: 52 sec, $0.08
```

**Savings:** 14 minutes 53 seconds (96% faster), $0.34 (81% cheaper)

### B.2 Scenario: Technical Podcast with Heavy Jargon

**Current Pipeline:**
```
YouTube transcript garbles jargon:
  Actual: "The eurodollar market affects liquidity"
  YouTube: "The euro dollar market affects liquidity"

Diarization works but misses some speaker changes.

Result:
  - 38 claims extracted
  - 12 jargon terms (some wrong due to transcription errors)
  - Speaker attribution 70% accurate
```

**Proposed Pipeline (YouTube path with auto-upgrade):**
```
1. Get YouTube transcript: 5 sec
2. Quality check: 2 sec → score 0.62 (poor - heavy jargon garbled)
3. Auto-upgrade decision: "Quality too low, using Whisper"
4. Download audio: 2 min
5. Whisper transcribe: 12 min (gets jargon correct)
6. Extract entities: 35 sec → 42 claims, 18 jargon (accurate)
7. Lazy attribution: 10 sec → 15 A/B claims attributed
8. Total: 14 min 52 sec, $0.36
```

**Result:** System automatically detected poor YouTube quality and upgraded. Same speed as pure Whisper path, but tried fast path first.

### B.3 Scenario: Single-Speaker Monologue

**Current Pipeline:**
```
1. Diarization: Detects 2 speakers (over-segmentation of same person)
2. Voice fingerprint: Fails to merge (similarity 0.68 < 0.7 threshold)
3. LLM attribution: Tries to identify two speakers
   - SPEAKER_00 = "Andrew Huberman" (correct)
   - SPEAKER_01 = "Unknown" (false positive)
4. Result: Some claims wrongly attributed to "Unknown"
```

**Proposed Pipeline:**
```
1. Skip diarization entirely
2. Extract claims: 45 claims
3. Lazy attribution for 16 A/B claims:
   - All claims are monologue (no turn-taking)
   - All use first-person "I", "my research"
   - Metadata: "Andrew Huberman" is host/speaker
   - Result: All 16 claims → "Andrew Huberman" (100% correct)
4. No false positives, no over-segmentation issues
```

**Improvement:** Avoiding acoustic diarization prevents over-segmentation error entirely.

---

## Appendix C: Technical Glossary

**A/B-tier claims:** Claims with importance score ≥6. High-value claims worth investing attribution effort.

**Acoustic diarization:** Using audio signal analysis (frequency, pitch, etc.) to segment speakers.

**Claims-first architecture:** Extract valuable claims before attempting full transcript diarization.

**ECAPA-TDNN:** Deep learning model for speaker embeddings (part of voice fingerprinting).

**Fuzzy matching:** Approximate string matching that allows for minor differences.

**Lazy attribution:** Only computing speaker labels when needed (for high-value claims).

**Lost in the middle:** LLM phenomenon where information in middle of long context is poorly recalled.

**Segment-level timestamps:** Timestamps for phrases/sentences (5-10 second granularity).

**Speaker diarization:** Process of determining "who spoke when" in audio.

**Voice fingerprinting:** Creating acoustic signature of speaker's voice for similarity comparison.

**wav2vec2:** Deep learning model for speech representations (part of voice fingerprinting).

**Word Error Rate (WER):** Percentage of words transcribed incorrectly.

**Word-level timestamps:** Timestamps for individual words (0.1 second granularity).

---

**END OF DOCUMENT**

*Total word count: ~15,000 words*
*Total pages: ~60 pages*
*Reading time: ~60 minutes*
