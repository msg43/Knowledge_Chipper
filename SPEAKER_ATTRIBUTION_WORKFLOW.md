# Speaker Attribution Workflow (No Popups)

## Overview
As of this update, all speaker assignment popup dialogs have been removed from the batch processing workflow. Speaker attribution is now handled exclusively through the **Speaker Attribution Tab**.

## How It Works

### 1. During Video Processing
- Videos are processed with diarization enabled (if configured)
- The system identifies different speakers in the audio (SPEAKER_00, SPEAKER_01, etc.)
- LLM suggestions for speaker names are generated and saved to the database
- **No popup dialogs appear** - processing continues uninterrupted
- All files are written to SQLite database immediately

### 2. Post-Processing Speaker Assignment
After videos are processed, users manage speaker assignments through the **Speaker Attribution Tab**:

1. **Automatic Queue Building**
   - The tab automatically finds all transcripts with unconfirmed speaker assignments
   - These are loaded into a queue for review

2. **Review Interface**
   - Users see the transcript with speaker segments highlighted
   - LLM suggestions are pre-filled but can be modified
   - Users can:
     - Accept the AI suggestions
     - Modify speaker names
     - Navigate through the queue with Previous/Next buttons
     - Save assignments for future use

3. **Benefits**
   - **Non-blocking**: Video processing runs at full speed without interruptions
   - **Batch review**: Review all speaker assignments at your convenience
   - **Persistent**: All data is saved to SQLite, survives crashes/restarts
   - **Flexible**: Can review assignments hours, days, or weeks later

## Configuration

### Enable/Disable Diarization
Diarization can be toggled in the YouTube tab settings. When disabled:
- No speaker identification occurs
- Transcripts contain continuous text without speaker labels
- No entries appear in the Speaker Attribution queue

### Parallel Processing
With popup dialogs removed, true parallel processing is now possible:
- Multiple videos process simultaneously (when batch criteria are met)
- Within each video: transcription and diarization run in parallel
- No UI blocking ensures maximum throughput

## Database Storage
All speaker-related data is stored in the SQLite database:
- Initial diarization results
- LLM suggestions
- User confirmations
- Speaker voice characteristics for future matching

## Migration from Popup Workflow
If you were used to the popup workflow:
1. Process your videos as normal
2. When ready to assign speakers, go to the Speaker Attribution tab
3. The queue will show all pending assignments
4. Review and confirm at your own pace

The removal of popups ensures a smoother, faster, and more reliable processing experience.
