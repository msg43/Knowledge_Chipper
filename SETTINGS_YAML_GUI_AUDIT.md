# SETTINGS.YAML → GUI TABS COMPREHENSIVE AUDIT

## Methodology
Systematic audit of every setting in `settings.yaml` to verify if it's:
1. ✅ Wired to GUI tab
2. ⚠️ Partially wired (some fields missing)
3. ❌ Not wired to GUI
4. ℹ️ Backend-only (no GUI needed)

---

## AUDIT RESULTS

### 1. `app:` Settings
```yaml
app:
  name: "Knowledge System"
  version: "0.1.1"
  debug: false
```

**Status:** ℹ️ **Backend-only** (No GUI needed)  
**Reason:** Application metadata, not user-configurable  
**Tab:** N/A

---

### 2. `paths:` Settings
```yaml
paths:
  data_dir: "~/Documents/KnowledgeSystem"
  output_dir: "~/Documents/KnowledgeSystem/output"
  cache_dir: "~/Documents/KnowledgeSystem/cache"
  logs_dir: "./logs"
```

**Status:** ⚠️ **Partially wired**
- `output_dir` → Used in tabs as per-tab output directory selection ✅
- `data_dir`, `cache_dir`, `logs_dir` → Backend-only (no GUI controls) ℹ️

**Tabs:** Transcription, Summarization, Process (all have output directory pickers)  
**Issue:** Each tab lets user pick output_dir but doesn't show/respect `settings.yaml` paths as defaults  
**Fix Needed:** `get_output_directory()` should fall back to `settings.paths.output_dir`

---

### 3. `performance:` Settings
```yaml
performance:
  profile: "auto"
  enable_hardware_detection: true
  override_whisper_model: null
  override_device: null
  override_batch_size: null
  override_max_concurrent: null
  optimize_for_use_case: "general"
  force_mps: false
  force_coreml: false
```

**Status:** ℹ️ **Backend-only** (advanced users only)  
**Reason:** Auto-detected based on hardware, rarely needs GUI override  
**Tab:** Could add "Advanced Performance" tab in future  
**Current:** Settings respected by backend, no GUI controls needed

---

### 4. `thread_management:` Settings
```yaml
thread_management:
  omp_num_threads: 8
  max_concurrent_files: 4
  per_process_thread_limit: 4
  enable_parallel_processing: true
  sequential_processing: false
  tokenizers_parallelism: false
  pytorch_enable_mps_fallback: true
```

**Status:** ⚠️ **Partially wired**
- Most settings → Backend-only (auto-calculated from hardware) ℹ️
- `max_concurrent_files` → Could be exposed in Batch Processing tab ❌

**Tabs:** None currently expose these  
**Tab Expected:** Batch Processing Tab (has parallel workers spinboxes)  
**Issue:** Batch Processing uses hardcoded spinbox defaults (4, 8, 6) instead of `settings.yaml`

**Fix Needed:**
```python
# In batch_processing_tab.py _create_left_panel():
self.max_downloads_spin.setValue(
    self.settings.thread_management.max_concurrent_files or 4
)
```

---

### 5. `transcription:` Settings
```yaml
transcription:
  whisper_model: "base"
  use_gpu: true
  diarization: false
  min_words: 50
  use_whisper_cpp: false
```

**Status:** ✅ **WIRED (via GUISettingsManager fix)**

**Tab:** Transcription Tab  
**Implementation:**
```python
# In settings_manager.py get_combo_selection():
if tab_name == "Transcription":
    if combo_name == "model":
        return self.system_settings.transcription.whisper_model  # ✅
    elif combo_name == "device":
        return "auto" if self.system_settings.transcription.use_gpu else "cpu"  # ✅
```

**Remaining Fields:**
- `diarization` → Checkbox (session state only, could default to settings.yaml) ⚠️
- `min_words` → Not exposed in GUI ❌
- `use_whisper_cpp` → Not exposed in GUI ❌

---

### 6. `llm:` Settings
```yaml
llm:
  provider: "local"
  model: "gpt-4o-mini-2024-07-18"
  local_model: "qwen2.5:7b-instruct"
  max_tokens: 15000
  temperature: 0.1
```

**Status:** ✅ **WIRED (via GUISettingsManager fix)**

**Tabs:** Summarization Tab, HCE Advanced Settings  
**Implementation:**
```python
# In settings_manager.py get_combo_selection():
if combo_name == "provider":
    return self.system_settings.llm.provider  # ✅
elif combo_name == "model":
    return self.system_settings.llm.local_model  # ✅
elif combo_name.endswith("_provider"):  # All HCE stages
    return self.system_settings.llm.provider  # ✅
```

**Remaining Fields:**
- `max_tokens` → Could be spinbox in Summarization tab ⚠️
- `temperature` → Could be slider in Summarization tab ⚠️

---

### 7. `local_config:` Settings
```yaml
local_config:
  base_url: "http://localhost:11434"
  model: "qwen2.5:7b-instruct"
  max_tokens: 15000
  temperature: 0.1
  timeout: 600
  backend: "ollama"
  num_predict: 2000
  num_ctx: 8192
  use_stream: true
```

**Status:** ℹ️ **Backend-only** (advanced Ollama configuration)  
**Reason:** Most users don't need to change these  
**Tab:** Could add "Local LLM Settings" tab for power users  
**Current:** Backend respects these automatically

---

### 8. `api_keys:` Settings
```yaml
api_keys:
  openai_api_key: "${OPENAI_API_KEY}"
  anthropic_api_key: "${ANTHROPIC_API_KEY}"
  youtube_api_key: "${YOUTUBE_API_KEY}"
  huggingface_token: "${HUGGINGFACE_HUB_TOKEN}"
```

**Status:** ✅ **WIRED**

**Tab:** API Keys Tab  
**Implementation:** Loads from credential files, saves to environment  
**Note:** Does NOT load defaults from `settings.yaml` (security by design)  
**Behavior:** Correct - API keys should not have defaults in settings.yaml

---

### 9. `processing:` Settings
```yaml
processing:
  batch_size: 10
  concurrent_jobs: 2
  retry_attempts: 3
  timeout_seconds: 300
```

**Status:** ⚠️ **Partially wired**
- `batch_size` → Used by backend, not exposed in GUI ℹ️
- `concurrent_jobs` → Could default Batch Processing spinboxes ❌
- `retry_attempts` → Backend-only ℹ️
- `timeout_seconds` → Backend-only ℹ️

**Tab Expected:** Batch Processing Tab  
**Current:** Uses hardcoded spinbox values instead of `settings.yaml`

---

### 10. `youtube_processing:` Settings
```yaml
youtube_processing:
  proxy_strict_mode: true
  disable_delays_with_proxy: false
  use_proxy_delays: true
  metadata_delay_min: 0.5
  metadata_delay_max: 2.0
  transcript_delay_min: 1.0
  transcript_delay_max: 3.0
  api_batch_delay_min: 1.0
  api_batch_delay_max: 3.0
```

**Status:** ⚠️ **Partially wired**
- `proxy_strict_mode` → Used by backend ✅
- Delay settings → Used by backend when downloading YouTube content ✅
- **NO GUI CONTROLS** for any of these settings ❌

**Tab Expected:** Transcription Tab (YouTube section) or dedicated YouTube Settings tab  
**Issue:** Users must manually edit `settings.yaml` to change YouTube behavior  
**Fix Needed:** Add YouTube settings section to Transcription tab or Settings tab

---

### 11. `speaker_identification:` Settings
```yaml
speaker_identification:
  diarization_sensitivity: "conservative"
  min_speaker_duration: 1.0
  speaker_separation_threshold: 0.75
```

**Status:** ✅ **WIRED**

**Tab:** Speaker Attribution Tab  
**Note:** This is a dedicated tab for speaker settings  
**Behavior:** Correct - users can configure diarization sensitivity

---

### 12. `moc:` Settings
```yaml
moc:
  default_theme: "topical"
  default_depth: 2
  extract_people: true
  extract_tags: true
  extract_mental_models: true
  extract_jargon: true
  extract_beliefs: true
  min_people_mentions: 2
  min_tag_occurrences: 3
  min_belief_confidence: 0.7
```

**Status:** ❌ **NOT WIRED**

**Tab Expected:** Process Tab (MOC generation)  
**Current:** Process Tab has checkboxes for MOC generation but doesn't expose extraction settings  
**Issue:** All these settings are backend-only, no GUI controls  
**Fix Needed:** Add MOC configuration section to Process Tab or create dedicated MOC Settings tab

---

### 13. `monitoring:` Settings
```yaml
monitoring:
  log_level: "INFO"
  log_file_max_size: 10
  log_file_backup_count: 5
  enable_performance_tracking: true
  track_processing_times: true
  track_resource_usage: true
```

**Status:** ⚠️ **Partially wired**
- `log_level` → Monitor Tab shows logs but doesn't let user change level ❌
- Other settings → Backend-only ℹ️

**Tab:** Monitor Tab  
**Issue:** Monitor Tab displays logs but no dropdown to change log level  
**Fix Needed:** Add log level dropdown to Monitor Tab

---

### 14. `gui_features:` Settings
```yaml
gui_features:
  show_process_management_tab: false
  show_file_watcher_tab: true
  enable_advanced_features: false
```

**Status:** ✅ **WIRED**

**Tab:** N/A (controls which tabs are visible)  
**Implementation:** Main window reads these to show/hide tabs  
**Behavior:** Correct

---

### 15. `cloud:` Settings
```yaml
cloud:
  supabase_url: null
  supabase_key: null
  supabase_bucket: null
```

**Status:** ✅ **WIRED**

**Tab:** Cloud Uploads Tab  
**Implementation:** Tab loads Supabase credentials from settings  
**Behavior:** Correct

---

### 16. `summarization:` Settings
```yaml
summarization:
  provider: "openai"
  model: "gpt-4"
  max_tokens: 10000
  temperature: 0.1
```

**Status:** ⚠️ **Partially wired**
- `provider`, `model` → ✅ WIRED via GUISettingsManager
- `max_tokens`, `temperature` → ❌ NOT exposed in Summarization Tab GUI

**Tab:** Summarization Tab  
**Issue:** Advanced LLM parameters not configurable in GUI  
**Fix Needed:** Add "Advanced" section with max_tokens and temperature controls

---

### 17. `getreceipts:` Settings
```yaml
getreceipts:
  enabled: false
  base_url: "https://getreceipts-web.vercel.app"
  timeout_seconds: 30
  max_retries: 3
  retry_delay: 1.0
  min_confidence: 0.6
  max_claims_per_export: 20
  include_all_tiers: true
  include_tier_c: true
  include_evidence_timestamps: true
  auto_export_after_processing: false
  export_only_on_success: true
```

**Status:** ❌ **NOT WIRED**

**Tab Expected:** Review Tab or dedicated GetReceipts Settings tab  
**Current:** GetReceipts integration exists in backend but no GUI controls  
**Issue:** Users cannot configure GetReceipts export settings via GUI  
**Fix Needed:** Add GetReceipts section to Review Tab

---

## SUMMARY STATISTICS

| Status | Count | Percentage |
|--------|-------|-----------|
| ✅ Fully Wired | 5 sections | 29% |
| ⚠️ Partially Wired | 7 sections | 41% |
| ❌ Not Wired | 2 sections | 12% |
| ℹ️ Backend-only (No GUI needed) | 3 sections | 18% |

---

## PRIORITY FIXES

### 🔴 HIGH PRIORITY (User-facing, commonly changed)

1. **Transcription Tab → Diarization Checkbox**
   - Should default to `settings.yaml → transcription.diarization`
   - Currently: Session state only, no fallback

2. **Batch Processing Tab → Concurrent Jobs**
   - Should default spinboxes to `settings.yaml → processing.concurrent_jobs`
   - Currently: Hardcoded values (4, 8, 6)

3. **Output Directory Defaults**
   - All tabs should fall back to `settings.yaml → paths.output_dir`
   - Currently: Session state → empty string (requires manual selection)

### 🟡 MEDIUM PRIORITY (Power users)

4. **Summarization Tab → max_tokens & temperature**
   - Add Advanced section with these controls
   - Currently: No GUI controls, must edit settings.yaml

5. **Monitor Tab → Log Level Dropdown**
   - Allow changing log level without restarting
   - Currently: Display only, no controls

6. **YouTube Processing Settings**
   - Add section to Transcription Tab or Settings Tab
   - Currently: Must edit settings.yaml manually

### 🟢 LOW PRIORITY (Advanced/rarely changed)

7. **MOC Settings Tab**
   - Dedicated tab for MOC extraction configuration
   - Currently: All backend-only

8. **GetReceipts Settings**
   - Add to Review Tab or create dedicated tab
   - Currently: All backend-only

9. **Transcription → min_words & use_whisper_cpp**
   - Add to Advanced section
   - Currently: Backend-only

---

## RECOMMENDED FIXES

### Fix 1: Enhance `get_checkbox_state()` in settings_manager.py

```python
def get_checkbox_state(
    self, tab_name: str, checkbox_name: str, default: bool = False
) -> bool:
    """Get the saved state of a checkbox."""
    # Check session state first
    saved_value = self.session_manager.get_tab_setting(tab_name, checkbox_name, None)
    if saved_value is not None:
        return saved_value
    
    # Fall back to settings.yaml
    if self.system_settings is not None:
        if tab_name == "Transcription" and checkbox_name == "diarization":
            return self.system_settings.transcription.diarization
    
    return default
```

### Fix 2: Enhance `get_output_directory()` in settings_manager.py

```python
def get_output_directory(self, tab_name: str, default: str | None = None) -> str:
    """Get the saved output directory for a tab."""
    # Try tab-specific directory first
    saved_dir = self.session_manager.get_tab_setting(
        tab_name, "output_directory", None
    )
    # ... existing fallback logic ...
    
    # Fall back to settings.yaml paths
    if not saved_dir and self.system_settings is not None:
        saved_dir = str(self.system_settings.paths.output_dir)
    
    return saved_dir or default or ""
```

### Fix 3: Enhance `get_spinbox_value()` in settings_manager.py

```python
def get_spinbox_value(
    self, tab_name: str, spinbox_name: str, default: int = 0
) -> int:
    """Get the saved value of a spinbox."""
    saved_value = self.session_manager.get_tab_setting(tab_name, spinbox_name, None)
    if saved_value is not None:
        return saved_value
    
    # Fall back to settings.yaml
    if self.system_settings is not None:
        if spinbox_name == "max_concurrent_files":
            return self.system_settings.thread_management.max_concurrent_files
        elif spinbox_name == "concurrent_jobs":
            return self.system_settings.processing.concurrent_jobs
    
    return default
```

---

## CONCLUSION

**Current State:** ~70% of user-facing settings are wired, but many use hardcoded defaults instead of respecting `settings.yaml`.

**Root Issue:** `GUISettingsManager` only recently got `settings.yaml` integration (for provider/model). Other methods (`get_checkbox_state`, `get_output_directory`, `get_spinbox_value`) still don't fall back to `settings.yaml`.

**Solution:** Apply the same pattern-based fallback approach to all `GUISettingsManager` getter methods.

**Impact:** After full implementation, users will be able to:
1. Set system-wide defaults in `settings.yaml`
2. Override per-session in GUI (preserves "last used" behavior)
3. Clear session state to reset to `settings.yaml` defaults

**Files to Modify:** 
- `src/knowledge_system/gui/core/settings_manager.py` (enhance all getter methods)
- Optionally: Add GUI controls for currently backend-only settings

