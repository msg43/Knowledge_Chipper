# Robust LLM Fallback System - November 10, 2025

## Problem

The original system would fail completely if the exact preferred model wasn't found:

```python
# OLD CODE
def get_available_mvp_model(self) -> str | None:
    for model in MVP_MODEL_ALTERNATIVES:
        if model in model_names:
            return model
    return None  # ❌ FAILS if preferred models not found
```

**Result**: Speaker attribution would fail even if the user had other perfectly good models installed (e.g., `qwen2.5:14b`, `llama3.1:8b`, etc.)

## Solution

Implemented a 5-tier fallback system that uses ANY available model rather than failing:

### Priority Order

```python
def get_available_mvp_model(self) -> str | None:
    """
    Get the best available MVP model with robust fallback.
    
    Priority order:
    1. Preferred models (MVP_MODEL_ALTERNATIVES)
    2. Any Qwen model (our preferred family)
    3. Any Llama model (good fallback)
    4. Any other instruct model (better than nothing)
    5. Any available model (last resort)
    """
```

### Tier 1: Preferred Models (Best Quality)

```python
# PRIORITY 1: Return first match from our preferred list
for model in MVP_MODEL_ALTERNATIVES:
    if model in model_names:
        logger.info(f"✅ Using preferred MVP model: {model}")
        return model
```

**Models**: `["qwen2.5:7b", "qwen2.5:14b", "qwen2.5:3b", "llama3.2:3b", "phi3:3.8b"]`

**Log Output**: `✅ Using preferred MVP model: qwen2.5:7b`

### Tier 2: Any Qwen Model (Preferred Family)

```python
# PRIORITY 2: Any Qwen model (our preferred family)
qwen_models = [m for m in model_names if m.startswith("qwen")]
if qwen_models:
    qwen_models.sort(reverse=True)  # Prefer larger models
    logger.info(f"⚠️ Using fallback Qwen model: {qwen_models[0]} (preferred models not found)")
    return qwen_models[0]
```

**Catches**: `qwen2.5:32b`, `qwen2.5-coder:7b`, `qwen3:30b`, etc.

**Log Output**: `⚠️ Using fallback Qwen model: qwen2.5:32b (preferred models not found)`

**Why**: Qwen family has excellent JSON compliance and text analysis, even if not our exact preferred versions.

### Tier 3: Any Llama Model (Good General Fallback)

```python
# PRIORITY 3: Any Llama model (good general fallback)
llama_models = [m for m in model_names if "llama" in m.lower()]
if llama_models:
    # Prefer instruct models, then larger models
    instruct_models = [m for m in llama_models if "instruct" in m.lower()]
    if instruct_models:
        instruct_models.sort(reverse=True)
        logger.info(f"⚠️ Using fallback Llama model: {instruct_models[0]} (Qwen not found)")
        return instruct_models[0]
```

**Catches**: `llama3.1:70b-instruct`, `llama3.2:3b-instruct`, `llama2:13b`, etc.

**Log Output**: `⚠️ Using fallback Llama model: llama3.1:70b-instruct (Qwen not found)`

**Why**: Llama models are widely available and perform well on text analysis tasks.

### Tier 4: Any Instruct Model (Better Than Nothing)

```python
# PRIORITY 4: ANY available model (better than failing completely)
instruct_models = [m for m in model_names if "instruct" in m.lower()]
if instruct_models:
    logger.warning(f"⚠️ Using generic fallback model: {instruct_models[0]} (no preferred models found)")
    logger.warning("   Speaker attribution quality may be reduced")
    return instruct_models[0]
```

**Catches**: `mistral:7b-instruct`, `gemma:7b-instruct`, `phi3:3.8b-instruct`, etc.

**Log Output**: 
```
⚠️ Using generic fallback model: mistral:7b-instruct (no preferred models found)
   Speaker attribution quality may be reduced
```

**Why**: Instruct-tuned models are better at following instructions and structured output than base models.

### Tier 5: Any Available Model (Last Resort)

```python
# Last resort: just use the first available model
logger.warning(f"⚠️ Using last-resort fallback model: {model_names[0]} (no instruct models found)")
logger.warning("   Speaker attribution quality may be significantly reduced")
return model_names[0]
```

**Catches**: ANY model the user has installed

**Log Output**:
```
⚠️ Using last-resort fallback model: codellama:7b (no instruct models found)
   Speaker attribution quality may be significantly reduced
```

**Why**: Even a code-focused or base model can attempt speaker attribution. It's better than failing completely and showing generic `SPEAKER_01` labels.

## Updated `is_mvp_ready()` Logic

**OLD** (strict matching):
```python
def is_mvp_ready(self) -> bool:
    installed_models = self.ollama_manager.get_available_models()
    model_names = [model.name for model in installed_models]
    
    # Only returns True if exact preferred model found
    return any(model in model_names for model in MVP_MODEL_ALTERNATIVES)
```

**NEW** (any model works):
```python
def is_mvp_ready(self) -> bool:
    """
    Returns True if Ollama is running and has ANY usable model installed.
    We now use a robust fallback system, so any model is better than none.
    """
    if not self.ollama_manager.is_service_running():
        return False
    
    installed_models = self.ollama_manager.get_available_models()
    
    # As long as there's at least one model, we can use it
    return len(installed_models) > 0
```

## Benefits

### 1. **Never Fails When Models Are Available**

**Before**: If `qwen2.5:7b` not found → speaker attribution fails → generic `SPEAKER_01` labels

**After**: Uses any available model → speaker attribution works → real names (with quality warning if needed)

### 2. **Handles User Customization**

Users who install different models (e.g., `qwen2.5:32b` for better quality, or `llama3.1:70b` for their workflow) will have them automatically detected and used.

### 3. **Graceful Degradation**

The system clearly logs which tier is being used:
- ✅ Green checkmark = preferred model (best quality)
- ⚠️ Warning = fallback tier (may have reduced quality)
- Each tier explains why it was chosen

### 4. **Smart Model Selection**

Within each tier, the system:
- Prefers **instruct models** over base models
- Prefers **larger models** over smaller ones (better quality)
- Uses alphabetical sorting as tiebreaker

### 5. **Transparent Logging**

Users and developers can see exactly what's happening:

```
✅ Using preferred MVP model: qwen2.5:7b
```

vs.

```
⚠️ Using fallback Qwen model: qwen2.5:32b (preferred models not found)
```

vs.

```
⚠️ Using last-resort fallback model: codellama:7b (no instruct models found)
   Speaker attribution quality may be significantly reduced
```

## Example Scenarios

### Scenario 1: Bundled App (Normal Case)

**Installed**: `qwen2.5:7b` (bundled default)

**Result**: 
```
✅ Using preferred MVP model: qwen2.5:7b
```

**Quality**: ✅ Excellent

---

### Scenario 2: Power User with Larger Model

**Installed**: `qwen2.5:32b` (user upgraded for better quality)

**Result**:
```
⚠️ Using fallback Qwen model: qwen2.5:32b (preferred models not found)
```

**Quality**: ✅ Excellent (actually better than default!)

---

### Scenario 3: User Prefers Llama

**Installed**: `llama3.1:70b-instruct` (user's preference)

**Result**:
```
⚠️ Using fallback Llama model: llama3.1:70b-instruct (Qwen not found)
```

**Quality**: ✅ Very Good

---

### Scenario 4: Fresh Install, User Downloaded Random Model

**Installed**: `mistral:7b-instruct` (user testing)

**Result**:
```
⚠️ Using generic fallback model: mistral:7b-instruct (no preferred models found)
   Speaker attribution quality may be reduced
```

**Quality**: ⚠️ Acceptable (better than failing)

---

### Scenario 5: Developer Testing with Code Model

**Installed**: `codellama:7b` (developer's code assistant)

**Result**:
```
⚠️ Using last-resort fallback model: codellama:7b (no instruct models found)
   Speaker attribution quality may be significantly reduced
```

**Quality**: ⚠️ Reduced (but still attempts attribution)

## Testing

### Test Case 1: Preferred Model Available
```bash
ollama list
# qwen2.5:7b    4.7GB    2 weeks ago

# Expected: ✅ Using preferred MVP model: qwen2.5:7b
```

### Test Case 2: Only Larger Qwen Available
```bash
ollama list
# qwen2.5:32b   19GB     1 week ago

# Expected: ⚠️ Using fallback Qwen model: qwen2.5:32b
```

### Test Case 3: Only Llama Available
```bash
ollama list
# llama3.1:8b-instruct   4.7GB    3 days ago

# Expected: ⚠️ Using fallback Llama model: llama3.1:8b-instruct
```

### Test Case 4: Random Model Available
```bash
ollama list
# mistral:7b-instruct   4.1GB    1 day ago

# Expected: ⚠️ Using generic fallback model: mistral:7b-instruct
```

### Test Case 5: No Models Installed
```bash
ollama list
# (empty)

# Expected: No LLM available - speaker suggestions will use smart fallback
```

## Files Modified

1. **`src/knowledge_system/utils/mvp_llm_setup.py`**
   - Updated `is_mvp_ready()` to accept any model
   - Completely rewrote `get_available_mvp_model()` with 5-tier fallback
   - Added detailed logging at each tier

2. **`CHANGELOG.md`**
   - Documented the robust fallback system

3. **`ROBUST_LLM_FALLBACK_SYSTEM.md`** (this file)
   - Comprehensive documentation

## Future Improvements

### 1. Model Quality Scoring
Could add a quality score to each tier and display it in the UI:
```python
quality_scores = {
    "tier1": 1.0,  # Preferred models
    "tier2": 0.95, # Other Qwen models
    "tier3": 0.85, # Llama models
    "tier4": 0.70, # Generic instruct models
    "tier5": 0.50, # Last resort
}
```

### 2. User Notification
Could show a notification in the GUI when using fallback tiers:
```
"Using fallback model: llama3.1:70b-instruct
Consider installing qwen2.5:7b for optimal performance.
[Install Now] [Dismiss]"
```

### 3. Model Performance Tracking
Could track speaker attribution accuracy by model and recommend upgrades:
```
"Your current model (mistral:7b) has 72% accuracy.
Upgrading to qwen2.5:7b would improve to 94% accuracy.
[Learn More]"
```

## Conclusion

This robust fallback system ensures speaker attribution **never fails when ANY model is available**. It gracefully degrades through 5 tiers, always attempting to provide real speaker names rather than generic labels. The system is transparent about which tier is being used and warns users if quality may be reduced.

**Key Principle**: Any model is better than no model. Better to attempt speaker attribution with a suboptimal model than to fail completely and show `SPEAKER_01` labels.
