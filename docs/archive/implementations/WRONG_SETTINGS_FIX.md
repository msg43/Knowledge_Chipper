# WRONG SETTINGS - ROOT CAUSES & FIXES

## ❌ ISSUE 1: Wrong Summarization Provider/Model

### What You're Seeing
```
DEBUG: Starting summarization with provider='openai', model='gpt-4o-mini-2024-07-18'
WRONG ❌
```

### Root Cause
GUI session state (`state/application_state.json`) is overriding `config/settings.yaml`.

**Session State (Lines 22-23):**
```json
"last_llm_provider": "openai",
"last_llm_model": "gpt-4o-mini-2024-07-18",
```

**Settings YAML:**
```yaml
llm:
  provider: "local"
  local_model: "qwen2.5:7b-instruct"
```

### Why This Happens
`SummarizationTab._load_settings()` (line 2652-2668) loads from `gui_settings` which reads from session state, **not** from `settings.yaml`.

```python
# Load provider selection
saved_provider = self.gui_settings.get_combo_selection(
    self.tab_name, "provider", "local"  # ← Default is ignored if session state exists
)
```

### Fix Option 1: Update Session State (Quick)
```bash
cd /Users/matthewgreer/Projects/Knowledge_Chipper

# Backup current state
cp state/application_state.json state/application_state.json.backup

# Update to local provider
python3 << 'EOF'
import json

with open("state/application_state.json", "r") as f:
    state = json.load(f)

state["preferences"]["last_llm_provider"] = "local"
state["preferences"]["last_llm_model"] = "qwen2.5:7b-instruct"

with open("state/application_state.json", "w") as f:
    json.dump(state, f, indent=2)

print("✅ Session state updated to use local provider")
EOF
```

### Fix Option 2: Clear Session State (Nuclear)
```bash
rm state/application_state.json
# Will be recreated on next launch with defaults
```

### Fix Option 3: Set in GUI
1. Open Summarization tab
2. Change Provider dropdown to "local"
3. Change Model dropdown to "qwen2.5:7b-instruct"
4. Run a job (this saves the selection to session state)

---

## ❌ ISSUE 2: Wrong Hardware Tier Detection

### What You're Seeing
```
LLM Adapter initialized for consumer tier (max 2 concurrent cloud / 3 local requests)
WRONG ❌
```

**Expected:**
```
LLM Adapter initialized for enterprise tier (max 8 concurrent cloud / 8 local requests)
✅
```

### Root Cause
`LLMAdapter._determine_hardware_tier()` was checking for `chip_variant` field that doesn't exist.

**Old Code (BROKEN):**
```python
if "apple" in specs.get("chip_type", "").lower():
    if "ultra" in specs.get("chip_variant", "").lower():  # ❌ chip_variant doesn't exist!
        return "enterprise"
```

**What system_profiler Actually Returns:**
```json
{
  "chip_type": "Apple M2 Ultra"  // ← Full name is HERE
}
```

### ✅ FIX APPLIED
Updated `src/knowledge_system/core/llm_adapter.py` line 183-209:

```python
def _determine_hardware_tier(self, specs: dict[str, Any]) -> str:
    """Determine hardware tier from specs."""
    # Check for Apple Silicon
    chip_type = specs.get("chip_type", "").lower()
    if "apple" in chip_type or "m1" in chip_type or "m2" in chip_type or "m3" in chip_type:
        # Check chip_type directly (contains full name like "apple m2 ultra")
        if "ultra" in chip_type:
            return "enterprise"  # ✅ Will now match "apple m2 ultra"
        elif "pro" in chip_type or "max" in chip_type:
            return "prosumer"
        else:
            return "consumer"
    # ... x86 detection code ...
```

**Result:** M2 Ultra now correctly detected as **enterprise tier** → 8 concurrent local requests

---

## ❌ ISSUE 3: Worker Pool Numbers Look Wrong?

### What You're Seeing
```
Initialized worker pools: [('download', 12), ('miner', 16), ('flagship_evaluator', 2), ('transcription', 4), ('voice_fingerprinting', 8)]
```

### Are These Actually Wrong?

**Let's analyze:**

These are **MAX workers** calculated by `DynamicParallelizationManager`:

1. **Download (12):** I/O bound, can handle many concurrent HTTP requests ✅
2. **Miner (16):** `base_max_workers * 2` where base = 8 (from 24 cores - 6 reserve = 18 → min(8, 18)) ✅
3. **Flagship Evaluator (2):** Limited to `min(2, base_max_workers)` for long-context evaluation ✅
4. **Transcription (4):** `base_max_workers // 2` = 8 // 2 = 4 ✅
5. **Voice Fingerprinting (8):** CPU-intensive, good parallelization = base_max_workers ✅

### Why base_max_workers = 8?

From `dynamic_parallelization.py` line 254-259:
```python
available_cores = (
    self.resource_limits.max_cpu_cores - self.resource_limits.os_reserve_cores
)
base_max_workers = min(8, available_cores)  # ← Conservative start
```

- M2 Ultra: 24 cores
- OS reserve (enterprise): 6 cores
- Available: 18 cores
- base_max_workers: `min(8, 18)` = **8** ✅

**This is CORRECT and intentional** - starts conservative and scales up dynamically based on actual performance.

### Expected After Hardware Tier Fix

With enterprise tier detection working:
- OS reserve cores: 6 (was probably 3-4 before)
- Available cores: 18 (same)
- Miner memory allocation: More aggressive (32GB FP16 model support)
- LLM concurrency: 8 local (was 3) ← **This is the main win**

---

## 🎯 SUMMARY: What to Fix

### Must Fix
1. **Update session state** to use `provider: local` (see Fix Option 1 above)

### Already Fixed
2. ✅ Hardware tier detection now works correctly
3. ✅ Worker pools are calculated correctly (not actually wrong)

### Expected Results After Fixes
```
DEBUG: Starting summarization with provider='local', model='qwen2.5:7b-instruct'
✅ CORRECT

LLM Adapter initialized for enterprise tier (max 8 concurrent cloud / 8 local requests)
✅ CORRECT

Initialized worker pools: [('download', 12), ('miner', 16), ('flagship_evaluator', 2), ('transcription', 4), ('voice_fingerprinting', 8)]
✅ CORRECT (these numbers are intentionally conservative)
```

---

## 🚀 Quick Fix Command

Run this to fix the session state issue:

```bash
cd /Users/matthewgreer/Projects/Knowledge_Chipper && python3 << 'EOF'
import json

with open("state/application_state.json", "r") as f:
    state = json.load(f)

state["preferences"]["last_llm_provider"] = "local"
state["preferences"]["last_llm_model"] = "qwen2.5:7b-instruct"

with open("state/application_state.json", "w") as f:
    json.dump(state, f, indent=2)

print("✅ Fixed: Session state now uses local provider")
print("   Restart GUI to see changes")
EOF
```
