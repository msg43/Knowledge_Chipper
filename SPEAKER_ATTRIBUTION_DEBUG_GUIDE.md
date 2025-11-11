# Speaker Attribution Debug Guide - November 10, 2025

## Issue Summary

User reports that speaker attribution is showing generic labels (SPEAKER_01) instead of real names, despite:
1. Gwen/Qwen model being installed and enabled by default
2. channel_hosts.csv containing 262 podcast mappings
3. Multi-layered speaker attribution system in place

## Root Cause Analysis

### The System Architecture (Working as Designed)

The speaker attribution system has multiple layers:

1. **Diarization** → Identifies speakers as SPEAKER_00, SPEAKER_01, etc.
2. **CSV Mapping** → Loads known hosts from `config/channel_hosts.csv` (262 podcasts)
3. **LLM Analysis** → Uses Qwen to analyze metadata + speech samples + CSV context
4. **Application** → Replaces generic labels with real names

### The Critical Failure Point

**Location**: `src/knowledge_system/utils/llm_speaker_suggester.py` lines 148-151

```python
if not self.llm_client:
    logger.info("No LLM configured - using pattern-based fallback")
    return self._simple_fallback(speaker_segments)
```

When `self.llm_client` is `None`, the system falls back to simple pattern matching, which:
- Cannot use the CSV mappings effectively
- Cannot analyze conversational context
- Returns generic names or fails to identify speakers

### Why is `self.llm_client` None?

The initialization chain is:

```
LLMSpeakerSuggester.__init__()
  → _initialize_llm()
    → _try_configured_llm()  # Checks user settings
    → _try_mvp_llm()         # Checks for Qwen/Gwen
      → MVPLLMSetup.is_mvp_ready()
        → ollama_manager.is_service_running()
        → ollama_manager.get_available_models()
        → Check if model name matches MVP_MODEL_ALTERNATIVES
```

**The Problem**: Model name mismatch between what Ollama returns and what the code expects.

## Model Name Mismatch Investigation

### What the Code Expects

From `src/knowledge_system/utils/mvp_llm_setup.py` lines 22-27:

```python
MVP_MODEL_ALTERNATIVES = [
    "qwen2.5:7b-instruct",      # Expected format
    "qwen2.5:3b-instruct",
    "llama3.2:3b-instruct",
    "phi3:3.8b-mini-instruct",
]
```

### What Ollama Might Return

Ollama's API (`/api/tags`) returns model names in various formats:
- `qwen2.5:7b-instruct` (exact match - GOOD)
- `qwen2.5:7b` (missing `-instruct` suffix)
- `qwen2.5:latest` (version tag instead of size)
- `qwen2.5` (no version at all)

### The Matching Logic

From `src/knowledge_system/utils/mvp_llm_setup.py` lines 37-48:

```python
def is_mvp_ready(self) -> bool:
    if not self.ollama_manager.is_service_running():
        return False
    
    installed_models = self.ollama_manager.get_available_models()
    model_names = [model.name for model in installed_models]
    
    # EXACT STRING MATCH ONLY
    return any(model in model_names for model in MVP_MODEL_ALTERNATIVES)
```

**Problem**: Uses exact string matching (`model in model_names`), so:
- ✅ `"qwen2.5:7b-instruct"` matches `"qwen2.5:7b-instruct"` 
- ❌ `"qwen2.5:7b"` does NOT match `"qwen2.5:7b-instruct"`
- ❌ `"qwen2.5:latest"` does NOT match `"qwen2.5:7b-instruct"`

## CSV Mapping Status

### CSV File is Loaded Correctly

From `src/knowledge_system/processors/speaker_processor.py` lines 1182-1203:

```python
def _get_known_hosts_from_channel(self, metadata):
    # ... extract channel_id and channel_name from metadata ...
    
    # Load channel mappings from CSV
    csv_path = Path(__file__).parent.parent.parent.parent / "config" / "channel_hosts.csv"
    
    if not csv_path.exists():
        logger.debug("channel_hosts.csv not found")
        return None
    
    # Build lookup dictionary
    channel_hosts = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Store by both channel_id and podcast_name
            channel_hosts[row['channel_id']] = row['host_name']
            channel_hosts[row['podcast_name']] = row['host_name']
```

**Status**: ✅ CSV loading works correctly

### CSV is Passed to LLM

From `src/knowledge_system/processors/speaker_processor.py` lines 1035-1058:

```python
# Get known host names from channel (if available)
known_hosts = self._get_known_hosts_from_channel(metadata)

if known_hosts:
    logger.info(f"📺 Channel has known hosts: {known_hosts}")

# Call LLM with known host names as context
llm_suggestions = suggest_speaker_names_with_llm(
    speaker_segments_for_llm, metadata, known_hosts  # ← CSV data passed here
)
```

**Status**: ✅ CSV data is passed to LLM as context

### But LLM Never Receives It

If `self.llm_client` is `None`, the system never reaches the LLM call:

```python
# llm_speaker_suggester.py line 148-151
if not self.llm_client:
    logger.info("No LLM configured - using pattern-based fallback")
    return self._simple_fallback(speaker_segments)  # ← CSV context lost!
```

**Status**: ❌ CSV context is lost when LLM is unavailable

## Diagnostic Steps

### 1. Check Ollama Service Status

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Expected output: JSON with list of models
```

### 2. Check Installed Model Names

```bash
# List installed models
ollama list

# Look for output like:
# qwen2.5:7b-instruct    4.7GB    2 weeks ago
# qwen2.5:7b             4.7GB    2 weeks ago
```

### 3. Check Application Logs

Look for these log messages during transcription:

**Good Signs**:
```
Using MVP LLM: qwen2.5:7b-instruct
📺 Channel has 1 known hosts: ['Peter Zeihan']
→ LLM will match speakers to these names based on transcript content
LLM suggested names for 2 speakers
  SPEAKER_00 -> 'Peter Zeihan' (confidence: 0.95)
  SPEAKER_01 -> 'Ian Bremmer' (confidence: 0.85)
```

**Bad Signs**:
```
No LLM available - speaker suggestions will use smart fallback
No LLM configured - using pattern-based fallback
⚠️ No automatic speaker assignments could be generated
```

### 4. Check Model Name Format

Add temporary logging to see exact model names:

```python
# In src/knowledge_system/utils/mvp_llm_setup.py, line 45
installed_models = self.ollama_manager.get_available_models()
model_names = [model.name for model in installed_models]

# ADD THIS:
logger.info(f"🔍 DEBUG: Installed model names: {model_names}")
logger.info(f"🔍 DEBUG: Looking for: {MVP_MODEL_ALTERNATIVES}")

return any(model in model_names for model in MVP_MODEL_ALTERNATIVES)
```

## Solutions

### Solution 1: Fix Model Name Matching (Recommended)

Make the matching more flexible to handle different Ollama naming conventions:

```python
# In src/knowledge_system/utils/mvp_llm_setup.py

def is_mvp_ready(self) -> bool:
    """Check if MVP LLM is ready to use."""
    try:
        if not self.ollama_manager.is_service_running():
            return False
        
        installed_models = self.ollama_manager.get_available_models()
        model_names = [model.name for model in installed_models]
        
        # Check for exact matches first
        if any(model in model_names for model in MVP_MODEL_ALTERNATIVES):
            return True
        
        # Check for partial matches (e.g., "qwen2.5:7b" matches "qwen2.5:7b-instruct")
        for mvp_model in MVP_MODEL_ALTERNATIVES:
            base_name = mvp_model.split(':')[0]  # "qwen2.5"
            for installed in model_names:
                if installed.startswith(base_name):
                    logger.info(f"✅ Found compatible model: {installed} (looking for {mvp_model})")
                    return True
        
        return False
    
    except Exception as e:
        logger.debug(f"Error checking MVP LLM status: {e}")
        return False

def get_available_mvp_model(self) -> str | None:
    """Get the best available MVP model."""
    try:
        installed_models = self.ollama_manager.get_available_models()
        model_names = [model.name for model in installed_models]
        
        # Return first exact match
        for model in MVP_MODEL_ALTERNATIVES:
            if model in model_names:
                return model
        
        # Return first partial match
        for mvp_model in MVP_MODEL_ALTERNATIVES:
            base_name = mvp_model.split(':')[0]
            for installed in model_names:
                if installed.startswith(base_name):
                    logger.info(f"✅ Using compatible model: {installed} (requested {mvp_model})")
                    return installed
        
        return None
    
    except Exception:
        return None
```

### Solution 2: Verify Model Installation

Ensure the model is installed with the correct name:

```bash
# Pull the exact model name the code expects
ollama pull qwen2.5:7b-instruct

# Verify it's installed
ollama list | grep qwen2.5
```

### Solution 3: Add Better Error Logging

Add diagnostic logging to understand what's happening:

```python
# In src/knowledge_system/processors/audio_processor.py, line 2116-2141

# Get automatic assignments (from DB, AI, or fallback)
logger.info("🔍 Attempting to get automatic speaker assignments...")
assignments = self._get_automatic_speaker_assignments(
    speaker_data_list, str(path)
)

if assignments:
    logger.info(f"✅ Got {len(assignments)} automatic assignments: {assignments}")
    # Apply assignments...
else:
    logger.error("❌ CRITICAL: No automatic speaker assignments could be generated")
    logger.error(f"   Speaker data list: {len(speaker_data_list)} speakers")
    logger.error(f"   Recording path: {path}")
    
    # Check if LLM was available
    from ..utils.mvp_llm_setup import get_mvp_llm_setup
    mvp_setup = get_mvp_llm_setup()
    logger.error(f"   MVP LLM ready: {mvp_setup.is_mvp_ready()}")
    logger.error(f"   Available MVP model: {mvp_setup.get_available_mvp_model()}")
```

## Testing Plan

1. **Add debug logging** to see exact model names
2. **Run a test transcription** with diarization enabled
3. **Check logs** for:
   - "Using MVP LLM: ..." message
   - "📺 Channel has X known hosts: ..." message
   - "LLM suggested names for X speakers" message
4. **If LLM not found**, check model name format and apply Solution 1

## Expected Behavior After Fix

When working correctly, logs should show:

```
🔍 Retrieving metadata from all sources for audio_test_abc123
   Primary: YouTube - Trump exploits antisemitism to attack Harvard...
✅ Found 2 speakers for assignment
✅ MVP LLM is ready - will use AI speaker suggestions
🤖 Using AI-powered speaker suggestions
📺 Channel has 1 known hosts: ['Noah Feldman']
   → LLM will match speakers to these names based on transcript content
Using MVP LLM: qwen2.5:7b-instruct
LLM suggested names for 2 speakers
  SPEAKER_00 -> 'Noah Feldman' (confidence: 0.95)
  SPEAKER_01 -> 'Ian Bremmer' (confidence: 0.85)
✅ Applied automatic speaker assignments: {'SPEAKER_00': 'Noah Feldman', 'SPEAKER_01': 'Ian Bremmer'}
```

## Files to Check

1. `src/knowledge_system/utils/mvp_llm_setup.py` - Model name matching logic
2. `src/knowledge_system/utils/llm_speaker_suggester.py` - LLM initialization
3. `src/knowledge_system/processors/audio_processor.py` - Speaker assignment invocation
4. `config/channel_hosts.csv` - CSV mappings (should be working)
5. Application logs during transcription

## Next Steps

1. Add debug logging to see exact model names returned by Ollama
2. Implement flexible model name matching (Solution 1)
3. Test with a known podcast (e.g., Peter Zeihan, Joe Rogan)
4. Verify CSV mappings are being used
5. Update documentation with findings
