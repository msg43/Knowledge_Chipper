# Transcription to Summarization Tab Fix

## Issue
When transcription succeeded and the completion popup offered the option to summarize the transcript, clicking "Summarize" would switch to the summarization tab but show "No transcript files found to load".

## Root Cause
The `successful_files` list in `EnhancedTranscriptionWorker` was storing only the **filename** (not full path) of transcribed files:

```python
self.successful_files.append({
    "file": file_name,  # Just the filename, not full path!
    "text_length": text_length,
    "saved_to": Path(saved_file).name if saved_file else None,
})
```

When `_switch_to_summarization_with_files()` tried to load these files into the summarization tab, it only had filenames and attempted to reconstruct the full paths by guessing, which often failed.

## Solution
### 1. Store Full Path in successful_files
Added `saved_file_path` field to store the complete path of saved transcript files:

```python
self.successful_files.append({
    "file": file_name,
    "text_length": text_length,
    "saved_to": Path(saved_file).name if saved_file else None,
    "saved_file_path": saved_file,  # Store full path for summarization tab
})
```

### 2. Update File Loading Logic
Modified `_switch_to_summarization_with_files()` to prioritize the full path:

```python
for file_info in successful_files:
    # First try to get the full saved file path (new field)
    saved_file_path = file_info.get("saved_file_path")
    if saved_file_path and Path(saved_file_path).exists():
        file_paths.append(str(saved_file_path))
        continue
    
    # Fallback: Try to reconstruct path from filename and output directory
    file_path = file_info.get("file")
    if file_path and output_dir:
        # ... existing reconstruction logic
```

## Files Changed
- `src/knowledge_system/gui/tabs/transcription_tab.py`
  - Line ~912: Added `saved_file_path` to successful_files dict
  - Line 2484-2533: Updated `_switch_to_summarization_with_files()` to use full path

## Testing
To test this fix:
1. Transcribe a file using the Transcription tab
2. Wait for the completion summary dialog to appear
3. Click the "Continue to Summarization" or "Summarize" button
4. Verify that the summarization tab now shows the transcript files in its file list

## Backward Compatibility
The fallback logic ensures that if `saved_file_path` is not present (old data), the system will still attempt to reconstruct the path using the original logic.

