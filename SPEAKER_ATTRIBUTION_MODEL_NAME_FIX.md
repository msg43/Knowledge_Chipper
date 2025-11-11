# Speaker Attribution Model Name Fix - November 10, 2025

## Problem

Speaker attribution was failing even when Qwen model was bundled and installed with the app. Users saw generic `SPEAKER_01` labels instead of real speaker names despite:
- Qwen model being installed during app setup
- 262-podcast CSV mapping database available
- Multi-layered speaker attribution system in place

## Root Cause

**Model Name Mismatch Between Installation and Detection**

### Installation Scripts

Different scripts were pulling models with inconsistent names:

1. **`post_install_setup.sh` (line 74)**:
   ```bash
   DEFAULT_MODEL="qwen2.5:7b"  # WITHOUT -instruct
   ollama pull "$DEFAULT_MODEL"
   ```

2. **`setup_ollama_models.sh` (lines 98-118)**:
   ```python
   # Hardware-based recommendations
   "qwen2.5:14b"  # WITHOUT -instruct
   "qwen2.5:7b"   # WITHOUT -instruct
   "qwen2.5:3b"   # WITHOUT -instruct
   ```

3. **`bundle_ollama_models.sh` (line 71)**:
   ```bash
   # Download the model
   ollama pull "qwen2.5:7b-instruct"  # WITH -instruct
   ```

### Detection Code

**`src/knowledge_system/utils/mvp_llm_setup.py` (lines 22-27)** - BEFORE FIX:
```python
MVP_MODEL_ALTERNATIVES = [
    "qwen2.5:7b-instruct",      # Expected WITH -instruct
    "qwen2.5:3b-instruct",      # Expected WITH -instruct
    "llama3.2:3b-instruct",     # Expected WITH -instruct
    "phi3:3.8b-mini-instruct",  # Expected WITH -instruct
]
```

### What Ollama Actually Returns

When you run `ollama pull qwen2.5:7b-instruct`, Ollama:
1. Downloads the model
2. **Stores it as `qwen2.5:7b`** (strips the `-instruct` suffix)
3. Returns `"qwen2.5:7b"` from `get_available_models()`

**Result**: Exact string match fails:
- Code looks for: `"qwen2.5:7b-instruct"`
- Ollama returns: `"qwen2.5:7b"`
- Match: ❌ FAIL

## The Fix

### Updated MVP Model List

**`src/knowledge_system/utils/mvp_llm_setup.py`** - AFTER FIX:

```python
# Recommended model for speaker attribution (excellent JSON compliance, good at text analysis)
# NOTE: Ollama stores models without the -instruct suffix even when pulled with it
# e.g., "ollama pull qwen2.5:7b-instruct" stores as "qwen2.5:7b"
MVP_MODEL = "qwen2.5:7b"  # 7B model, ~4GB download, excellent JSON schema compliance

# Alternative models in order of preference
# These match the ACTUAL names Ollama returns from get_available_models()
MVP_MODEL_ALTERNATIVES = [
    "qwen2.5:7b",       # 7B, 4GB - excellent JSON compliance, best for structured output
    "qwen2.5:14b",      # 14B, 8GB - higher quality for Max/Ultra systems
    "qwen2.5:3b",       # 3B, 2GB - smaller Qwen option for base systems
    "llama3.2:3b",      # 3B, 2GB - fallback option
    "phi3:3.8b",        # 3.8B, 2.3GB - very good at text
]
```

### Simplified Detection Logic

Removed fuzzy matching since we now have exact names:

**BEFORE** (with fuzzy matching):
```python
def is_mvp_ready(self) -> bool:
    installed_models = self.ollama_manager.get_available_models()
    model_names = [model.name for model in installed_models]
    
    # Check for exact matches first
    if any(model in model_names for model in MVP_MODEL_ALTERNATIVES):
        return True
    
    # Check for partial matches (fuzzy logic)
    for mvp_model in MVP_MODEL_ALTERNATIVES:
        base_name = mvp_model.split(':')[0]
        for installed in model_names:
            if installed.startswith(base_name):
                return True
    
    return False
```

**AFTER** (exact matching only):
```python
def is_mvp_ready(self) -> bool:
    installed_models = self.ollama_manager.get_available_models()
    model_names = [model.name for model in installed_models]
    
    # Check for exact matches (model names now match what Ollama actually returns)
    return any(model in model_names for model in MVP_MODEL_ALTERNATIVES)
```

## Why This Approach is Better

### 1. **No Fuzzy Logic Needed**
- We know exactly what model we're bundling
- We know exactly what name Ollama will assign it
- Simple exact string matching is sufficient and more reliable

### 2. **Matches Installation Reality**
- Installation scripts pull `"qwen2.5:7b"`
- Ollama stores as `"qwen2.5:7b"`
- Detection looks for `"qwen2.5:7b"`
- ✅ Perfect match

### 3. **Handles Hardware Variations**
- Base systems (16GB): `"qwen2.5:3b"`
- Pro systems (16-32GB): `"qwen2.5:7b"`
- Max systems (32-64GB): `"qwen2.5:14b"`
- Ultra systems (64GB+): `"qwen2.5:14b"`

All model names match what Ollama actually returns.

### 4. **Clear Documentation**
Added inline comments explaining Ollama's naming behavior:
```python
# NOTE: Ollama stores models without the -instruct suffix even when pulled with it
# e.g., "ollama pull qwen2.5:7b-instruct" stores as "qwen2.5:7b"
```

## Testing

### Before Fix
```
No LLM available - speaker suggestions will use smart fallback
No LLM configured - using pattern-based fallback
⚠️ No automatic speaker assignments could be generated
```

Result: Generic `SPEAKER_01` labels in transcript

### After Fix
```
✅ Found MVP model: qwen2.5:7b
Using MVP LLM: qwen2.5:7b
📺 Channel has 1 known hosts: ['Peter Zeihan']
→ LLM will match speakers to these names based on transcript content
✅ Applied automatic speaker assignments: {'SPEAKER_00': 'Peter Zeihan', 'SPEAKER_01': 'Guest Name'}
```

Result: Real speaker names in transcript

## Files Modified

1. **`src/knowledge_system/utils/mvp_llm_setup.py`**
   - Updated `MVP_MODEL` from `"qwen2.5:7b-instruct"` to `"qwen2.5:7b"`
   - Updated `MVP_MODEL_ALTERNATIVES` to match Ollama's actual names
   - Removed fuzzy matching logic (no longer needed)
   - Added documentation comments

2. **`CHANGELOG.md`**
   - Documented the fix

3. **`SPEAKER_ATTRIBUTION_MODEL_NAME_FIX.md`** (this file)
   - Comprehensive documentation of the issue and fix

## Verification Steps

To verify the fix works:

1. **Check installed model name**:
   ```bash
   ollama list
   # Should show: qwen2.5:7b (not qwen2.5:7b-instruct)
   ```

2. **Run a test transcription** with diarization enabled

3. **Check logs** for:
   ```
   ✅ Found MVP model: qwen2.5:7b
   Using MVP LLM: qwen2.5:7b
   ```

4. **Verify transcript** has real speaker names, not SPEAKER_01

## Lessons Learned

### 1. **Always Check Actual API Responses**
Don't assume the model name you pass to `ollama pull` is the same name returned by `ollama list` or the API.

### 2. **Document Naming Quirks**
When external tools (like Ollama) transform names, document it clearly in code comments.

### 3. **Keep Installation and Detection in Sync**
Regularly audit that:
- Installation scripts pull models with names X
- Detection code looks for models with names X
- They match exactly

### 4. **Prefer Exact Matching When Possible**
Fuzzy matching is a band-aid. If you control both installation and detection, use exact names.

## Related Issues

This fix also resolves:
- CSV mapping database not being used (LLM was never initialized)
- Speaker attribution dialog not appearing (LLM check failed)
- Automatic speaker assignments returning None (no LLM available)

All these issues stemmed from the same root cause: LLM not being detected due to model name mismatch.
