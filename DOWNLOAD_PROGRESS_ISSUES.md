# YouTube Download Progress Issues

## Problems Identified

### Issue 1: Download Progress Not Shown in Progress Bar
**Problem:** During YouTube download, the progress bar stays in "indeterminate/rolling" mode instead of showing actual download progress.

**Why this happens:**
1. `YouTubeDownloadProcessor` (youtube_download.py:511) calls `progress_callback()` with **only a message string**:
   ```python
   progress_callback(progress_msg)  # Just a string, no percentage!
   ```

2. The message contains the percentage (e.g., "Downloading: file.mp4 | 10.5/50.2 MB (21%)"), but it's **embedded in text**, not as a separate parameter

3. The GUI's `_transcription_progress_callback()` receives this string and emits it (line 114-115):
   ```python
   self.transcription_step_updated.emit(
       step_description_or_dict, progress_percent  # progress_percent = 0 (default)!
   )
   ```

4. The progress bar's `update_current_file_progress()` is called with **0%**, so it doesn't update

**Result:** Progress bar shows indeterminate "rolling" animation during downloads instead of actual percentage

---

### Issue 2: Progress Jumps to 90% Before Transcription
**Problem:** After download completes, the progress bar jumps from 0% (or rolling) to 90% immediately, before any transcription or conversion work begins.

**Why this happens:**
Look at line 217 in transcription_tab.py:
```python
self.transcription_step_updated.emit(
    f"📥 [{idx}/{total}] Downloading{attempt_msg}...",
    int(20 + (idx / total) * 70),  # <-- This calculation!
)
```

**The Math:**
- For a **single URL** (idx=1, total=1):
  ```python
  progress = 20 + (1/1) * 70 = 20 + 70 = 90%
  ```

- This **90%** is reported at the **START** of download, not at completion!

Then at line 233-235, when download completes:
```python
self.transcription_step_updated.emit(
    f"✅ [{idx}/{total}] Downloaded successfully",
    int(20 + (idx / total) * 70),  # Still 90%!
)
```

**Timeline:**
```
0%    → Start
90%   → "Downloading..." (before download even starts!) 
90%   → (download happens, bar doesn't move)
90%   → "Downloaded successfully"
90%   → (conversion happens)
90%   → (transcription starts)
100%  → Done
```

---

## Root Causes

### Issue 1: Download Progress Callback Format
The `YouTubeDownloadProcessor` sends progress as:
```python
progress_callback("📥 Downloading: file.mp4 | 10.5/50.2 MB (21%)")
```

But the GUI expects:
```python
progress_callback("📥 Downloading...", 21)  # message + percentage
```

### Issue 2: Pre-allocated Progress Ranges
The code pre-allocates progress ranges:
- **0-20%**: Reserved for URL expansion/preparation
- **20-90%**: Reserved for downloads (allocated evenly across URLs)
- **90-100%**: Reserved for transcription

But it **reports the END of the range at the START of the phase**, causing premature jumps.

---

## Solutions

### Solution 1: Pass Download Progress Percentage

**File:** `src/knowledge_system/processors/youtube_download.py` (line 511)

**Change from:**
```python
progress_callback(progress_msg)
```

**Change to:**
```python
# Extract percentage and pass it separately
if self.progress_callback:
    self.progress_callback(progress_msg, int(percent))
```

This allows the GUI to update the progress bar with actual download percentages.

### Solution 2: Fix Progress Range Calculation

**File:** `src/knowledge_system/gui/tabs/transcription_tab.py`

**Current problem (line 215-218):**
```python
self.transcription_step_updated.emit(
    f"📥 [{idx}/{total}] Downloading{attempt_msg}...",
    int(20 + (idx / total) * 70),  # Reports END of range at START!
)
```

**Better approach:**
```python
# Report START of this file's download range
download_start = 20 + ((idx - 1) / total) * 70  # Previous files complete
self.transcription_step_updated.emit(
    f"📥 [{idx}/{total}] Downloading{attempt_msg}...",
    int(download_start),  # Start at beginning of this file's range
)
```

Then update progress during download:
```python
# In download callback:
file_download_range = 70 / total  # Each file gets equal portion of 20-90%
current_file_progress = download_start + (download_percent / 100 * file_download_range)
self.transcription_step_updated.emit(
    f"📥 [{idx}/{total}] Downloading: {download_percent:.1f}%...",
    int(current_file_progress),
)
```

---

## Visual: Current vs Fixed Behavior

### Current Behavior (Single File)
```
Phase              Progress Bar    Reality
─────────────────  ──────────────  ─────────────────────
Start              0%              ✓ Correct
"Downloading..."   90%!            ✗ Wrong - just started!
(downloading...)   ⚙️ rolling      ✗ Should show 0→100%
"Downloaded"       90%             ✗ Still 90%
(converting...)    90%             ✗ No feedback
"Transcribing..."  90%→95%→100%    ✗ Too fast at end
```

### Fixed Behavior (Single File)
```
Phase              Progress Bar    Reality
─────────────────  ──────────────  ─────────────────────
Start              0%              ✓ Correct
"Downloading..."   0%              ✓ Starting download
(downloading...)   5→20→50→75→90%  ✓ Real download progress!
"Downloaded"       90%             ✓ Download complete
(converting...)    90→92%          ✓ Shows conversion
"Transcribing..."  92→95→98→100%   ✓ Shows transcription
```

### Fixed Behavior (5 Files)
```
Phase                      Progress Bar    Reality
─────────────────────────  ──────────────  ─────────────────────
Start                      0%              ✓
Downloading file 1         20→30%          ✓ 20-34% range
Downloading file 2         34→48%          ✓ 34-48% range  
Downloading file 3         48→62%          ✓ 48-62% range
Downloading file 4         62→76%          ✓ 62-76% range
Downloading file 5         76→90%          ✓ 76-90% range
Transcribing all 5 files   90→100%         ✓ Remaining 10%
```

---

## Implementation Plan

### Step 1: Fix YouTube Download Progress Callback
Update `youtube_download.py` to pass percentage:
```python
# Line 511 area
if total_bytes > 0:
    percent = (downloaded_bytes / total_bytes) * 100
    # ... build progress_msg ...
    
    if self.progress_callback:
        # Pass both message and percentage
        self.progress_callback(progress_msg, int(percent))
```

### Step 2: Update Transcription Worker Download Progress Handling
In `transcription_tab.py`, update the download function to:
1. Calculate the correct starting progress for each file
2. Map download progress (0-100%) to the file's allocated range (e.g., 20-34% for file 1 of 5)
3. Update progress bar continuously during download

### Step 3: Connect Download Progress to Progress Bar
Modify `_transcription_progress_callback()` to handle download progress:
```python
def _transcription_progress_callback(self, step_description_or_dict: Any, progress_percent: int = 0):
    # ... existing code ...
    
    # Update progress bar for ALL progress updates, not just transcription
    if progress_percent > 0:
        # This will now work for downloads, transcription, diarization, etc.
        self.transcription_step_updated.emit(step_description_or_dict, progress_percent)
```

---

## Benefits of Fixing

✅ **Download progress visible** - Users see actual download percentages (0-100%) for each file
✅ **No premature jumps** - Progress bar doesn't jump to 90% at download start  
✅ **Smooth progress** - Continuous updates throughout entire pipeline
✅ **Accurate feedback** - Users know exactly what's happening and how far along
✅ **Better time estimates** - Users can predict completion time from progress rate

---

## Testing Checklist

- [ ] Single YouTube URL download shows 0→90% during download
- [ ] Single URL shows 90→100% during transcription
- [ ] Multiple URLs show smooth progress across all downloads
- [ ] Progress never jumps backwards
- [ ] Progress never jumps forward prematurely
- [ ] Local file transcription still works correctly (no regression)

