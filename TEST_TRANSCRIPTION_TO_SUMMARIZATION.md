# Test: Transcription to Summarization Tab Flow

## Purpose
Verify that clicking "Summarize" in the transcription completion dialog properly loads transcript files into the summarization tab.

## Test Steps

### Setup
1. Launch the Knowledge Chipper GUI
2. Navigate to the "Local Transcription" tab
3. Ensure you have a test audio/video file ready (or use a short YouTube video)

### Test Case 1: Local File Transcription
1. Add a test audio/video file to transcribe
2. Set output directory to a known location
3. Select a transcription model (e.g., "tiny" for faster testing)
4. Click "Start Transcription"
5. Wait for transcription to complete

### Expected Results After Transcription
1. A completion summary dialog should appear showing:
   - Number of successful files
   - Character count
   - List of transcribed files
   - "Continue to Summarization" or similar button

2. When you click the "Continue to Summarization" button:
   - ✅ The summarization tab should activate
   - ✅ The file list in the summarization tab should show the transcript file(s)
   - ✅ Full paths should be displayed (not just filenames)
   - ✅ No "No transcript files found to load" warning should appear

### Test Case 2: YouTube Transcription
1. Navigate to the "YouTube" tab
2. Enter a short YouTube URL (5-10 minutes for faster testing)
3. Set output directory to a known location
4. Click "Extract Transcript"
5. Wait for extraction to complete

### Expected Results
Similar to Test Case 1, but note:
- YouTube tab uses a different completion dialog (CloudTranscriptionSummary)
- This dialog may not have direct "Summarize" button integration yet
- Manual navigation to summarization tab should still work

## Verification

### Before the Fix
- Clicking "Summarize" would switch tabs but show "⚠️ No transcript files found to load"
- User would have to manually browse for the transcript files

### After the Fix
- Clicking "Summarize" should automatically load the transcript files
- Files should appear in the summarization tab's file list with full paths
- User can immediately start summarization without manual file selection

## Debug Information

If the issue persists, check:

1. **Console output** for any error messages about file paths
2. **Verify transcript files exist** in the output directory
3. **Check file naming** - transcripts should end with `_transcript.md` by default
4. **Inspect successful_files data**:
   ```python
   # In transcription_tab.py, around line 2471
   print(f"DEBUG: successful_files = {successful_files}")
   # Should show dicts with 'saved_file_path' key
   ```

## Related Files
- `src/knowledge_system/gui/tabs/transcription_tab.py`
- `src/knowledge_system/gui/components/completion_summary.py`
- `src/knowledge_system/gui/tabs/summarization_tab.py`

## Fix Summary
Added `saved_file_path` field to the successful_files data structure to store the full path of saved transcript files, allowing the summarization tab to directly load them without path guessing.

