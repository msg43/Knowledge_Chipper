# Transcript Architecture Clarification

## The Problem

I was making redundant "fixes" because I didn't understand the actual architecture:

1. **There IS a single source of truth**: `audio_processor.py` generates markdown files
2. **There IS a powerful speaker attribution system**: `SpeakerProcessor` with LLM + channel_hosts.csv
3. **I added redundant fuzzy matching**: This conflicted with the existing system

## The Actual Architecture

### Markdown Generation Flow

```
Transcription Tab
    ↓
AudioProcessor.process()
    ↓
WhisperCppTranscribeProcessor (transcription)
    ↓
SpeakerDiarizationProcessor (if enabled)
    ↓
SpeakerProcessor.prepare_speaker_data()
    ↓
LLM Speaker Suggestions (uses channel_hosts.csv as context)
    ↓
AudioProcessor._get_automatic_speaker_assignments()
    ↓
SpeakerProcessor.apply_speaker_assignments()
    ↓
AudioProcessor.save_transcript_to_markdown()
    ↓
AudioProcessor._create_markdown()
    ↓
Markdown file with real speaker names
```

### Key Points

1. **Single Source**: `audio_processor.py._create_markdown()` is THE place where markdown is generated

2. **Speaker Attribution**: Handled by `SpeakerProcessor` which:
   - **Receives YouTube metadata** (title, uploader, description) containing correct names
   - Uses LLM to analyze **metadata + transcript** together
   - LLM prompt includes:
     * Title: "Ukraine Strikes Russia's Druzhba Oil Pipeline || **Peter Zeihan**"
     * Uploader: "**Peter Zeihan**"
     * Description: Full text (may contain correct spelling)
     * Transcript: "Peter Zine here..." (may have errors)
     * channel_hosts.csv: Known hosts for context
   - **LLM should prioritize metadata over transcript** for names
   - Stores suggestions in database for learning
   - Allows manual correction via GUI dialog

3. **Database-Centric**: 
   - All metadata saved to database first
   - Markdown generated from database + transcription data
   - Re-runs overwrite existing records

## What Was Fixed (Correctly)

1. ✅ **Title Cleaning**: Remove `[videoID]` from titles (lines 975-976, 1083-1084)
2. ✅ **Filename Generation**: Use clean title without video ID (lines 1184-1195)
3. ✅ **Title Heading**: Add H1 heading below YAML (lines 1080-1086)
4. ✅ **Description Section**: Add YouTube description (lines 1109-1116)
5. ✅ **Thumbnail Embedding**: Include thumbnail path (lines 1088-1105)
6. ✅ **Source Type**: Already correct - maps "youtube" → "YouTube" (lines 959-969)

## What Was Removed (Correctly)

1. ✅ **Fuzzy Matching**: Removed redundant `_correct_speaker_name_fuzzy()` function
   - The existing `SpeakerProcessor` already handles this better with LLM
   - `channel_hosts.csv` is used as context, not for fuzzy matching
   - LLM is smart enough to correct "Peter Zine" → "Peter Zeihan" with proper context

## The Real Issue with "Peter Zine"

The problem isn't the speaker attribution system - the architecture is correct:

1. **YouTube metadata contains correct spelling**: 
   - Title: "Ukraine Strikes Russia's Druzhba Oil Pipeline || **Peter Zeihan**"
   - Uploader: "**Peter Zeihan**"
2. **Whisper transcribed "Zeihan" as "Zine"** (audio transcription error)
3. **LLM receives BOTH metadata and transcript**:
   - Metadata says: "Peter Zeihan" (correct)
   - Transcript says: "Peter Zine" (error)
   - channel_hosts.csv says: "Peter Zeihan" (correct)

### Why LLM Should Get It Right

The LLM prompt (in `llm_speaker_suggester.py` lines 236-257) includes:
- **Title**: Contains "Peter Zeihan" 
- **Uploader/Channel**: "Peter Zeihan"
- **Description**: May contain more references
- **channel_hosts.csv**: "Peter Zeihan" as known host
- **Transcript**: "Peter Zine here..." (the error)

With 3+ sources saying "Zeihan" and only the transcript saying "Zine", the LLM should choose "Zeihan".

### Why It Might Not Work

1. **LLM prompt might not emphasize metadata priority**: The prompt should explicitly tell the LLM to trust metadata over transcript for spelling
2. **Video metadata might not be passed correctly**: Check if `video_metadata` is actually reaching the LLM
3. **LLM might be too literal**: Some LLMs prefer exact transcript matches over metadata inference

## Next Steps

To ensure the LLM uses metadata correctly:

1. **Enhance LLM prompt** (`llm_speaker_suggester.py`):
   - Add explicit instruction: "When the video title or uploader contains a name, use that spelling even if the transcript has variations"
   - Emphasize: "Prioritize metadata (title, uploader, description) over transcript for name spelling"

2. **Verify metadata is passed**: Add logging to confirm:
   - `video_metadata` is passed to `SpeakerProcessor.prepare_speaker_data()`
   - Metadata reaches `suggest_speaker_names_with_llm()`
   - LLM prompt actually includes the metadata

3. **Test with Peter Zeihan video**: Re-transcribe and check logs for:
   - What metadata the LLM receives
   - What the LLM suggests
   - If it correctly chooses "Zeihan" over "Zine"

## Files Modified

- `src/knowledge_system/processors/audio_processor.py`: All markdown generation fixes
- `config/channel_hosts.csv`: Added Peter Zeihan entry
- `knowledge_system.db`: Deleted (was test data)

## Files NOT Modified (And Shouldn't Be)

- `src/knowledge_system/services/file_generation.py`: This is for regenerating files from database, not initial generation
- `src/knowledge_system/processors/speaker_processor.py`: Already has the right logic
- `src/knowledge_system/utils/llm_speaker_suggester.py`: LLM prompts (might need enhancement but not for this issue)

