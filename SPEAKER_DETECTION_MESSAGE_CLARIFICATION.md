# Speaker Detection Message Clarification

## Issue
User reported seeing console message: "diarization complete waiting for transcription" which seemed impossible since transcription needs to happen before diarization.

## Root Cause Analysis
The confusion stemmed from misunderstanding the parallel processing workflow. The system actually runs two **independent** processes simultaneously:

### The Actual Workflow

```
┌─────────────────────────────────────────────┐
│         INPUT: Audio File                   │
└─────────────────┬───────────────────────────┘
                  │
      ┌───────────┴────────────┐
      │                        │
      ▼                        ▼
┌──────────────┐      ┌──────────────────┐
│Transcription │      │Speaker Detection │
│              │      │  (Diarization)   │
│Audio → Text  │      │Audio → Segments  │
│+ Timestamps  │      │+ Speaker IDs     │
│              │      │                  │
│(Neural Engine)│      │     (GPU)        │
└──────┬───────┘      └────────┬─────────┘
       │                       │
       └───────────┬───────────┘
                   ▼
         ┌──────────────────┐
         │Speaker Assignment│
         │  (Sequential)    │
         │                  │
         │ Merges text with │
         │ speaker segments │
         └──────────────────┘
```

### Key Points

1. **Both processes analyze the same audio file independently**:
   - **Transcription**: Converts speech to text with timestamps
   - **Speaker Detection**: Identifies who is speaking at what times

2. **Neither process depends on the other during execution**:
   - They both work directly on the audio file
   - They run simultaneously to save time
   - Either can finish first

3. **Speaker assignment happens AFTER both complete**:
   - This downstream step merges the transcription text with speaker segments
   - This is when you get "Speaker 1 said X" output

## The Fix

Updated terminology and messages to be clearer:

### Before
- "Diarization completed, waiting for transcription..."
- "Running diarization on GPU..."

### After
- "Speaker detection completed, waiting for transcription..."
- "Running speaker detection on GPU..."

### Rationale
- "Speaker detection" is more user-friendly than "diarization"
- Makes it clear that this is detecting WHO speaks WHEN
- Emphasizes that it's independent from transcription (detecting WHAT is said)

## Files Changed

- `src/knowledge_system/utils/async_processing.py`
  - Updated module docstring to explain the workflow
  - Changed "diarization" to "speaker detection" in user-facing messages
  - Updated method docstrings to clarify the parallel processing model
  - Fixed type annotation for proper None handling

## Technical Details

The parallel processing is beneficial because:
- **Transcription** (on Neural Engine): ~10% of real-time
- **Speaker Detection** (on GPU): ~30% of real-time

For a 30-minute file:
- **Sequential**: 3 + 9 = 12 minutes total
- **Parallel**: max(3, 9) × 1.1 = ~10 minutes total
- **Speedup**: ~1.3x faster

This is only used for files > 2 minutes with sufficient CPU cores (4+).

