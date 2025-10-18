# GUI Model URI Format Fix

## Problem Statement

The GUI was experiencing **consistent failures during transcription and symbolization** despite comprehensive tests passing successfully. This created a critical disconnect between test validation and real-world GUI usage.

## Root Cause Analysis

### The Bug

The GUI and the HCE pipeline were using **incompatible model URI formats**:

**GUI Construction (BROKEN):**
```python
# src/knowledge_system/gui/tabs/summarization_tab.py:2988 (before fix)
def _get_model_override(self, provider_combo, model_combo):
    return f"{provider}/{model}"  # ❌ Used slash separator
```

**HCE Parser Expectation:**
```python
# src/knowledge_system/processors/hce/model_uri_parser.py:50
if ":" in model_uri:
    parts = model_uri.split(":", 1)  # ✅ Expects colon separator
```

### The Impact

When a user selected **OpenAI** + **gpt-4o-mini** in the GUI:

1. GUI created: `"openai/gpt-4o-mini"` ❌
2. Parser saw NO colon (`:`) in the string
3. Parser treated the **entire string** as a model name
4. Parser defaulted to `provider="ollama"` (line 62 in model_uri_parser.py)
5. System attempted: `ollama.generate("openai/gpt-4o-mini")` 
6. **FAILURE**: Ollama has no model called "openai/gpt-4o-mini"

### Why Tests Passed But GUI Failed

**Tests used correct format directly:**
```python
# Tests always used proper format
miner_model="openai:gpt-4o-mini-2024-07-18"  # ✅ Colon separator
flagship_judge_model="openai:gpt-4o"         # ✅ Colon separator
```

**GUI went through broken helper method:**
```python
# GUI called the broken _get_model_override() method
gui_settings["miner_model_override"] = self._get_model_override(
    self.miner_provider, self.miner_model  # ❌ Returned "openai/gpt-4o-mini"
)
```

## The Fix

Changed the model URI construction to use the correct format:

```python
def _get_model_override(
    self, provider_combo: QComboBox, model_combo: QComboBox
) -> str | None:
    """Get model override string from provider and model combos.
    
    Returns a model URI in the format expected by parse_model_uri():
    - "provider:model" for standard providers (openai, anthropic, etc.)
    - "local://model" for local Ollama models
    """
    provider = provider_combo.currentText().strip()
    model = model_combo.currentText().strip()

    if not provider or not model:
        return None

    # Map "local" provider to the local:// protocol format
    if provider.lower() == "local":
        return f"local://{model}"  # ✅ "local://qwen2.5:7b-instruct"
    
    # Use colon separator for all other providers (NOT slash)
    return f"{provider}:{model}"  # ✅ "openai:gpt-4o-mini"
```

## Examples

### Before Fix (BROKEN)
- **OpenAI** + **gpt-4o-mini** → `"openai/gpt-4o-mini"` → Parsed as `ollama` provider with model `"openai/gpt-4o-mini"` → **FAIL**
- **Anthropic** + **claude-3-5-sonnet** → `"anthropic/claude-3-5-sonnet"` → Parsed as `ollama` provider → **FAIL**
- **Local** + **qwen2.5:7b** → `"local/qwen2.5:7b"` → Parsed as `ollama` provider → **FAIL** (confusing because it's already Ollama!)

### After Fix (CORRECT)
- **OpenAI** + **gpt-4o-mini** → `"openai:gpt-4o-mini"` → Parsed as `openai` provider with model `"gpt-4o-mini"` → ✅
- **Anthropic** + **claude-3-5-sonnet** → `"anthropic:claude-3-5-sonnet"` → Parsed as `anthropic` provider → ✅
- **Local** + **qwen2.5:7b** → `"local://qwen2.5:7b"` → Parsed as `ollama` provider with model `"qwen2.5:7b"` → ✅

## Files Changed

- `src/knowledge_system/gui/tabs/summarization_tab.py` - Fixed `_get_model_override()` method (lines 2978-2998)

## Verification

To verify this fix works:

1. Open GUI
2. Go to Summarization tab
3. Select **OpenAI** provider + **gpt-4o-mini** model for Unified Miner
4. Process a markdown file
5. Check logs - should see successful OpenAI API calls, NOT Ollama errors

## Related Components

The following components correctly parse the fixed format:

- `src/knowledge_system/processors/hce/model_uri_parser.py` - Parses `provider:model` format
- `src/knowledge_system/processors/hce/unified_pipeline.py` - Uses parsed model URIs
- `src/knowledge_system/core/system2_orchestrator.py` - Passes model URIs to mining jobs
- `src/knowledge_system/processors/summarizer_unified.py` - Applies model overrides from GUI

## Prevention

This type of bug occurred because:

1. **No integration test** covering GUI → HCE model configuration flow
2. **Silent failures** - Parser defaulted to Ollama instead of raising an error
3. **Format not documented** in the GUI code

### Recommendations

1. Add integration test that simulates GUI model selection and verifies correct provider is called
2. Consider making `parse_model_uri()` raise an error for ambiguous formats instead of defaulting
3. Add format validation in GUI when user selects provider/model
4. Document expected format in GUI tooltips/help text

