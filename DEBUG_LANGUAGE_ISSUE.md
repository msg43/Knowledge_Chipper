# Language Selection Debug Analysis

## The Problem
Transcriptions are happening in French despite user expecting English or auto-detection.

## Investigation Summary

### 1. Language Selection Flow
1. **GUI Selection**: User selects language in `TranscriptionTab.language_combo`
2. **Settings Extraction**: `_get_transcription_settings()` extracts language:
   - Returns `None` if "auto" selected
   - Returns language code (e.g., "fr", "en") if specific language selected
3. **Worker Processing**: Language passed in `processing_kwargs`
4. **Audio Processor**: Receives language in kwargs
5. **Optimization Step**: `optimize_transcription_for_apple_silicon()` modifies kwargs
6. **Whisper.cpp**: Receives `--language` parameter if not "auto"

### 2. Potential Root Causes

#### A. Saved Settings Issue
- GUI persists combo box selections via `SessionManager`
- If user previously selected "fr" (French), it's saved and restored on next launch
- Check: `saved_language = self.gui_settings.get_combo_selection(self.tab_name, "language", "auto")`

#### B. Auto-Detection Failure
- If language="auto" (or None), Whisper auto-detects language
- Whisper might be incorrectly detecting French for English audio
- This can happen with:
  - Poor audio quality
  - Background noise
  - Accented English
  - Short audio clips

#### C. Settings Not Being Passed
- Language might be getting lost in the kwargs chain
- Optimization step might be overwriting it

### 3. Debug Steps

To debug this issue:

1. **Check Current GUI Setting**:
   - Open the app
   - Look at Language dropdown in Transcription tab
   - Is it showing "fr" or "auto"?

2. **Force English**:
   - Explicitly select "en" in the Language dropdown
   - Save settings
   - Try transcription again

3. **Add Debug Logging**:
   ```python
   # In transcription_tab.py, after line 676:
   logger.info(f"🔍 DEBUG: Language setting = {processing_kwargs.get('language', 'NOT SET')}")
   
   # In audio_processor.py, after line 1278:
   logger.info(f"🔍 DEBUG: Language after optimization = {optimized_kwargs.get('language', 'NOT SET')}")
   
   # In whisper_cpp_transcribe.py, after line 787:
   logger.info(f"🔍 DEBUG: Language passed to whisper = {language}")
   ```

### 4. Likely Solution

The most probable cause is that the GUI is loading a previously saved "fr" selection. The fix would be:

1. **Clear Saved Settings**:
   - Delete any session files
   - Or manually set language to "en" or "auto" in the GUI

2. **Check Default**:
   - Line 2719 in transcription_tab.py loads saved language with default "auto"
   - But if "fr" was previously saved, it will load that

3. **Verify Auto-Detection**:
   - If using "auto", Whisper might be misdetecting language
   - Force "en" for English transcriptions

### 5. Recommended Fix

Add explicit language logging and ensure the GUI defaults to "auto" or "en" rather than loading a potentially incorrect saved value:

```python
# In _load_settings(), after loading saved language:
if saved_language not in ["auto", "en"]:
    logger.warning(f"Unusual saved language '{saved_language}', defaulting to 'auto'")
    saved_language = "auto"
```

This would prevent accidentally transcribing in the wrong language due to old saved settings.
