# Vestigial Prompt Picker Removed

**Date:** November 4, 2025  
**File Modified:** `src/knowledge_system/gui/tabs/summarization_tab.py`

## Summary

Removed the non-functional "Prompt File" picker from the Summarization tab. This UI control appeared to allow users to select custom prompts, but the selected value was never actually used by the processing pipeline.

## Background

The Knowledge Chipper system uses a **claim-centric HCE (Human-Compatible Extraction) pipeline** with prompts that are:

1. **Automatically selected based on Content Type:**
   - `unified_miner_transcript_own.txt` → "Transcript (Own)"
   - `unified_miner_transcript_third_party.txt` → "Transcript (Third-party)"
   - `unified_miner_document.txt` → "Document (PDF/eBook)" and "Document (White Paper)"

2. **Hardcoded in the pipeline:**
   - Selection happens in `system2_orchestrator.py` (lines 1114-1121)
   - The `UnifiedMiner` class chooses the appropriate prompt based on content_type
   - No mechanism exists to override this via GUI settings

3. **Part of a multi-stage process:**
   - `unified_miner.txt` (or variants) → Extract claims, jargon, people, mental models
   - `flagship_evaluator.txt` → Evaluate and rank extracted entities
   - `short_summary.txt` → Pre-mining context summary
   - `long_summary.txt` → Post-evaluation comprehensive summary

## What Was Removed

### UI Elements (lines 805-833)
```python
# REMOVED:
- prompt_label = QLabel("Prompt File:")
- self.template_path_edit = QLineEdit(default_template_path)
- browse_template_btn = QPushButton("Browse")
- All associated tooltips and layout code
```

### Methods
```python
# REMOVED:
- def _select_template(self): # Line 2277-2286
- def _on_analysis_type_changed(self, analysis_type: str): # Lines 3403-3435
```

### Data Flow
```python
# REMOVED from gui_settings dictionaries:
- "template_path": self.template_path_edit.text()  # Lines 1277, 1315

# REMOVED from widget lists:
- self.template_path_edit  # Lines 2892, 2914

# REMOVED from settings persistence:
- Loading: Lines 2997-3007
- Saving: Lines 3183-3187
```

## Evidence It Was Vestigial

### 1. Never Passed to Orchestrator
```python
# Line 234-245: Job creation in summarization worker
job_id = orchestrator.create_job(
    "mine",
    source_id,
    config={
        "source": "manual_summarization",
        "file_path": str(file_path),
        "gui_settings": self.gui_settings,
        "content_type": content_type,  # ← This selects the prompt
        "miner_model": f"...",
        # NO template_path parameter!
    },
)
```

### 2. Hardcoded in System2Orchestrator
```python
# Lines 1114-1121 in system2_orchestrator.py
prompt_path = (
    Path(__file__).parent.parent
    / "processors"
    / "hce"
    / "prompts"
    / "unified_miner.txt"  # ← Hardcoded!
)
miner = UnifiedMiner(llm, prompt_path)
```

### 3. Content Type Selection
```python
# Lines 64-71 in unified_miner.py
if content_type:
    content_type_files = {
        "transcript_own": "unified_miner_transcript_own.txt",
        "transcript_third_party": "unified_miner_transcript_third_party.txt",
        "document_pdf": "unified_miner_document.txt",
        "document_whitepaper": "unified_miner_document.txt",
    }
    prompt_file = content_type_files.get(content_type)
    # ← Content type is the selector, not custom path
```

## User Impact

### Before
- ❌ Confusing UI control that didn't work
- ❌ Users might think they can customize prompts via GUI
- ❌ Settings saved but never used (wasted storage/confusion)
- ❌ No error messages when custom prompt ignored

### After
- ✅ Cleaner, more honest UI
- ✅ Clear that Content Type controls prompt selection
- ✅ No vestigial settings persistence
- ✅ No functionality lost (feature never worked)

## How to Customize Prompts (Advanced Users)

If users need to customize prompts, they should:

1. **Edit the prompt files directly:**
   - Located in: `src/knowledge_system/processors/hce/prompts/`
   - Files: `unified_miner_transcript_own.txt`, etc.

2. **Use the Prompts Tab:**
   - Available in the GUI for viewing/editing HCE prompts
   - Shows all active prompts in the pipeline
   - Direct editing of system prompts

3. **Understand the multi-stage architecture:**
   - Cannot substitute a single "summary prompt"
   - System uses 4 prompts in sequence (miner → evaluator → short/long summary)
   - Each stage has specific input/output requirements

## Related Files

- `src/knowledge_system/gui/tabs/prompts_tab.py` - GUI for editing HCE prompts
- `src/knowledge_system/processors/hce/unified_miner.py` - Prompt selection logic
- `src/knowledge_system/processors/hce/unified_pipeline.py` - Full pipeline orchestration
- `src/knowledge_system/core/system2_orchestrator.py` - Job execution

## Testing

No testing required - this removal has zero functional impact since the feature never worked. The Content Type dropdown continues to work as before.

## Conclusion

This cleanup removes technical debt and user confusion. The **Content Type** dropdown is the correct and functional way to select between prompt variants. Custom prompts should be managed through direct file editing or the Prompts tab, not through a non-functional GUI picker in the Summarization tab.
