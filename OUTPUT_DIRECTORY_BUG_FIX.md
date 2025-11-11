# Output Directory Bug Fix

## Issue Description

The Summarize tab was displaying the user-selected output directory in the UI (e.g., `/Users/matthewgreer/Projects/SAMPLE OUTPUTS/SUMMARY`), but summary files were being saved to the default `output/summaries/` directory instead.

### Root Cause

The problem was in how the `output_dir` setting was passed from the GUI to the System2 Orchestrator:

1. **Summarization Tab** (`summarization_tab.py`):
   - The tab correctly collected `output_dir` from the UI field (`self.output_edit.text()`)
   - It placed this value inside the `gui_settings` dict
   - The config passed to the orchestrator had `gui_settings` as a nested object

2. **System2 Orchestrator Mining** (`system2_orchestrator_mining.py`):
   - The orchestrator looked for `output_dir` at the **top level** of the config dict: `config.get("output_dir")`
   - Since `output_dir` was nested inside `gui_settings`, it returned `None`
   - The `FileGenerationService` then fell back to its default `Path("output")` directory

### Example of the Bug

**User's UI showed:**
```
Output Directory: /Users/matthewgreer/Projects/SAMPLE OUTPUTS/SUMMARY
```

**Actual file saved to:**
```
/Users/matthewgreer/Projects/Knowledge_Chipper/output/summaries/audio_Markets Drop After Fed Rate Cut ｜｜ Peter Zeihan [hyIgB-xFQzQ]_383f376f_summary.md
```

## Fix Applied

### Files Modified

1. **`src/knowledge_system/gui/tabs/summarization_tab.py`** (2 locations)
   - Line ~248: Database source processing
   - Line ~269: File source processing
   
   **Change:** Extract `output_dir` from `gui_settings` and add it to the top level of the config dict:
   ```python
   config={
       "source": "manual_summarization",
       "file_path": str(file_path),
       "gui_settings": self.gui_settings,
       "content_type": content_type,
       "miner_model": f"{self.gui_settings.get('provider', 'openai')}:{self.gui_settings.get('model', 'gpt-4o-mini-2024-07-18')}",
       "output_dir": self.gui_settings.get('output_dir'),  # ← ADDED THIS LINE
   }
   ```

2. **`src/knowledge_system/gui/tabs/monitor_tab.py`** (1 location)
   - Line ~507: Auto-processing mining job
   
   **Change:** Add `output_dir` to config using the default summaries path from settings:
   ```python
   config={
       "source": "monitor_tab_auto",
       "file_path": str(file_path),
       "miner_model": f"{self.settings.llm.provider}:gpt-4o-mini-2024-07-18",
       "output_dir": str(self.settings.paths.summaries),  # ← ADDED THIS LINE
   }
   ```

### Other Tabs Checked

- **Process Tab** (`process_tab.py`): ✅ Already correctly passes `output_dir` at top level (lines 196, 239)
- **Transcription Tab** (`transcription_tab.py`): ✅ Creates pipeline jobs, not mining jobs - different code path

## Verification

The fix ensures that:
1. When users select an output directory in the Summarize tab, files are saved to that directory
2. The Monitor tab uses the system default summaries path from settings
3. The Process tab continues to work correctly (already had the fix)

## Technical Details

### Config Structure Before Fix
```python
config = {
    "source": "manual_summarization",
    "file_path": "/path/to/file.md",
    "gui_settings": {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "output_dir": "/Users/matthewgreer/Projects/SAMPLE OUTPUTS/SUMMARY",  # ← Nested here
        # ... other settings
    }
}
```

### Config Structure After Fix
```python
config = {
    "source": "manual_summarization",
    "file_path": "/path/to/file.md",
    "output_dir": "/Users/matthewgreer/Projects/SAMPLE OUTPUTS/SUMMARY",  # ← Now at top level
    "gui_settings": {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "output_dir": "/Users/matthewgreer/Projects/SAMPLE OUTPUTS/SUMMARY",  # ← Also kept in gui_settings for compatibility
        # ... other settings
    }
}
```

### How FileGenerationService Uses output_dir

From `src/knowledge_system/core/system2_orchestrator_mining.py` (lines 388-407):
```python
# 10. Generate summary markdown file
summary_file_path = None
try:
    from ..services.file_generation import FileGenerationService

    output_dir = config.get("output_dir")  # ← Looks at top level
    if output_dir:
        file_gen = FileGenerationService(output_dir=Path(output_dir))
    else:
        file_gen = FileGenerationService()  # ← Falls back to default "output"

    summary_file_path = file_gen.generate_summary_markdown_from_pipeline(
        source_id, pipeline_outputs
    )
```

## Date
November 8, 2025
