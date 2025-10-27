# Active TODOs - Knowledge Chipper

**Last Updated:** October 27, 2025

This document catalogs all active TODO items found in the codebase, organized by priority and category.

---

## 🔴 HIGH PRIORITY

### HCE Summarization System Upgrades
**Location:** `data/TODO_HCE_Summarization_Upgrades.md`

**Status:** ✅ **ACTIVE** - Major feature enhancement plan with 10 workstreams

**Overview:** Comprehensive upgrade to the HCE (Hierarchical Claim Extraction) summarization system to add flexibility, cost control, and user configurability.

**Key Features to Implement:**

1. **Skim Optionality** - Make high-level skim step toggleable
   - CLI flags: `--use-skim/--no-skim`
   - GUI checkbox in Summarization tab
   - Allow disabling to reduce LLM calls for faster processing

2. **Dual-Judge Routing** - Split claims between lightweight and flagship models
   - Route high-value claims to expensive flagship models
   - Use lightweight models for routine claims
   - Configurable uncertainty thresholds

3. **Per-Stage Model Configuration** - Granular model selection
   - Separate model choices for: miner, judge, embedder, reranker, NLI
   - Both CLI and GUI configuration
   - Enable mixing providers (e.g., local miner + cloud judge)

4. **Profiles** - Pre-configured quality presets
   - **Fast:** No skim, no routing, lightweight only
   - **Balanced:** Skim enabled, moderate routing (default)
   - **Quality:** Full pipeline, aggressive routing to flagship models

5. **Prompt-Driven Summary Mode** - Template-based alternative
   - Allow bypassing HCE formatting for custom templates
   - Use selected prompt template as authoritative structure
   - Optional metadata-only HCE extraction

6. **Session Reporting** - Enhanced analytics
   - Track routing decisions (which claims → flagship vs local)
   - Per-stage token counts, costs, and timing
   - Reproducibility: log all effective config settings

7. **Budget Guardrails** - Cost controls
   - Per-file and per-session token limits
   - Soft caps with warnings when exceeded
   - Prune/defer flagship calls beyond budget

8. **Skim Improvements** - Selectable skim model
   - CLI: `--skim-model`
   - GUI: Advanced dropdown
   - Use milestones to guide miner window selection

9. **Documentation** - User-facing guides
   - README updates with examples
   - Workflow tutorials for common scenarios

10. **Testing** - Comprehensive test coverage
    - Routing correctness, dual-judge dispatch
    - Profile expansion, budget enforcement
    - Golden report tests for analytics

**Files Affected:**
- `src/knowledge_system/processors/summarizer.py`
- `src/knowledge_system/processors/hce/config_flex.py`
- `src/knowledge_system/processors/hce/router.py`
- `src/knowledge_system/processors/hce/judge.py`
- `src/knowledge_system/processors/hce/skim.py`
- `src/knowledge_system/commands/summarize.py`
- `src/knowledge_system/commands/process.py`
- `src/knowledge_system/gui/tabs/summarization_tab.py`

---

## 🟡 MEDIUM PRIORITY

### MOC Generation Integration
**Location:** `src/knowledge_system/gui/tabs/process_tab.py:184,232`

**Status:** ⚠️ **PARTIALLY COMPLETE** - MOC processor exists, needs System2 integration

**Description:** The MOC (Maps of Content) processor and database models are fully implemented (`src/knowledge_system/processors/moc.py`), but it needs to be integrated into the Process Tab workflow through System2Orchestrator as a job type.

**Current State:**
- ✅ MOC processor implemented
- ✅ Database models exist
- ✅ File generation service supports MOC
- ❌ Not integrated into Process Tab automated workflow
- ❌ No System2 job type for MOC generation

**What's Needed:**
1. Add `moc` job type to System2Orchestrator
2. Wire Process Tab checkbox to create MOC jobs
3. Handle MOC generation after summarization completes
4. Update UI to show MOC generation progress

**Workaround:** MOC generation currently works through direct processor usage, just not through the automated Process Tab pipeline.

---

### Proxy Provider Implementations
**Location:** `src/knowledge_system/utils/proxy/`

**Status:** 🔵 **BLOCKED** - Waiting for credentials and API documentation

**Description:** Four proxy providers have stub implementations waiting for account credentials and API documentation.

#### 1. Oxylabs Provider
**File:** `oxylabs_provider.py:68,102`

**What's Needed:**
- Oxylabs account credentials
- API documentation for proxy configuration
- Implementation of `get_proxy_config()` method
- Implementation of `test_connectivity()` method

#### 2. GonzoProxy Provider
**File:** `gonzoproxy_provider.py:68,102`

**What's Needed:**
- GonzoProxy account credentials
- API documentation
- Same method implementations as above

#### 3. AnyIP.io Provider
**File:** `anyip_provider.py:74,108,118`

**What's Needed:**
- AnyIP.io account credentials
- API documentation
- Determination of required credential fields
- Same method implementations as above

#### 4. BrightData Provider
**File:** `brightdata_provider.py:87,120`

**Status:** ⚠️ **SPECIAL** - Implementation exists in archived code

**What's Needed:**
- Restore implementation from archived code
- Restore connectivity test from archived code
- Test with current BrightData API

**Note:** BrightData is the recommended provider (over deprecated WebShare). Priority should be higher if YouTube processing at scale is needed.

---

### Document Language Detection
**Location:** `src/knowledge_system/processors/document_processor.py:297`

**Status:** ✅ **ACTIVE** - Enhancement opportunity

**Description:** Currently hardcoded to English (`"en"`). Should detect document language automatically.

**What's Needed:**
1. Add language detection library (e.g., `langdetect`, `lingua-py`)
2. Detect language from document text sample
3. Pass detected language to downstream processors
4. Fall back to English if detection fails

**Impact:** Would enable proper processing of non-English documents.

---

### HCE Prompt Templates
**Location:** `src/knowledge_system/processors/hce/`

**Status:** ✅ **ACTIVE** - Two templates needed

#### Temporality Analysis
**File:** `temporality.py:116`

**Description:** Feature is disabled pending prompt template creation. Would analyze temporal aspects of claims (when did events occur, timelines, etc.).

**What's Needed:**
- Create `config/prompts/temporality.txt` template
- Define what temporal information to extract
- Re-enable the feature in the pipeline

#### Relations Extraction  
**File:** `relations.py:69`

**Description:** Feature is disabled pending prompt template creation. Would extract relationships between entities, concepts, and claims.

**What's Needed:**
- Create `config/prompts/relations.txt` template  
- Define relationship types to extract
- Re-enable the feature in the pipeline

**Note:** Both features have implementation code ready; they just need prompt templates to function.

---

## 🟢 LOW PRIORITY

### Code Cleanup Tasks

#### 1. Remove Obsolete Settings Method
**Location:** `src/knowledge_system/gui/tabs/api_keys_tab.py:2034`

**Status:** ✅ **ACTIVE** - Safe to remove

**Description:** The `_apply_recommended_settings()` method starting at line 1982 is obsolete. Hardware optimization is now handled during installation via `scripts/generate_machine_config.py`.

**Action:** Delete the obsolete method and its references.

---

#### 2. Error Taxonomy Migration
**Location:** `src/knowledge_system/errors.py:30`

**Status:** ✅ **ACTIVE** - Technical debt

**Description:** Legacy error codes need migration to new taxonomy. Currently marked for backwards compatibility:
- `PROCESSING_FAILED`
- `INVALID_INPUT`
- `LLM_API_ERROR`
- `LLM_PARSE_ERROR`
- `DATABASE_ERROR`
- `FILE_NOT_FOUND`
- `TRANSCRIPTION_ERROR`
- `CONFIGURATION_ERROR`

**What's Needed:**
1. Map each legacy code to new severity-based taxonomy
2. Update all usages in codebase
3. Deprecate old codes (keep for 1-2 releases)
4. Remove legacy codes after deprecation period

---

#### 3. WebShare to BrightData Migration
**Location:** `scripts/cleanup_webshare_legacy.py:36`

**Status:** ⚠️ **LEGACY** - Consider deprecation

**Description:** Script exists to deprecate WebShare and migrate users to BrightData. However, BrightData provider itself needs restoration (see proxy providers above).

**Recommendation:** Complete BrightData provider implementation first, then run this cleanup script.

---

### Database Service Enhancements

#### 1. Speaker Voice Methods
**Location:** Multiple files

**Status:** 🔵 **BLOCKED** - Requires audio feature extraction

**Files:**
- `database/speaker_models.py:293`
- `database/speaker_models_old.py:535`  
- `database/speaker_models_new.py:293`
- `voice/voice_fingerprinting.py:558`
- `voice/speaker_verification_service.py:212`
- `processors/speaker_processor.py:550`

**Description:** Several voice/speaker features need actual audio feature matching implementation:
- `find_matching_voices()` - Currently returns all voices instead of matching by features
- `get_all_voices()` - Needs implementation in database service
- `get_all_speakers()` - Needs implementation in database service
- Audio segment extraction - Currently skipped

**What's Needed:**
1. Implement proper audio feature vector comparison
2. Add similarity threshold matching
3. Implement missing database service methods
4. Add actual audio segment extraction

**Impact:** Would enable true voice fingerprinting and speaker identification.

---

## ⚪ DEFERRED / UNCERTAIN

### System2 Upload Job Type
**Location:** `src/knowledge_system/core/system2_orchestrator.py:903`

**Status:** ❓ **QUESTIONABLE** - May be obsolete

**Description:** TODO says to implement upload logic in System2Orchestrator. However, upload functionality is fully implemented elsewhere:
- ✅ `gui/tabs/cloud_uploads_tab.py` - OAuth-based upload GUI
- ✅ `knowledge_chipper_oauth/getreceipts_uploader.py` - Full upload implementation  
- ✅ `services/supabase_storage.py` - Storage service
- ✅ `services/claims_upload_service.py` - Claims upload service

**Question:** Is System2 job-based upload still needed?

**Recommendation:** 
- If CLI-based upload is desired, implement this
- If GUI upload is sufficient, mark TODO as obsolete
- Current upload functionality works fine through GUI

---

### Transcription Dependency Check
**Location:** `src/knowledge_system/gui/tabs/transcription_tab.py:3544`

**Status:** ⚠️ **WORKAROUND** - Temporary fix in place

**Description:** Diarization dependencies may be installed but check fails in GUI context. Currently using a workaround to skip installation dialog.

**What's Needed:**
1. Investigate why GUI context fails dependency check
2. Fix the underlying detection issue
3. Remove temporary workaround

**Impact:** Currently functional with workaround, but should be fixed properly.

---

## 📊 Summary Statistics

**Total Active TODOs:** 35+

**By Priority:**
- 🔴 High: 10 (HCE Summarization features)
- 🟡 Medium: 11 (MOC integration, proxies, templates, language detection)
- 🟢 Low: 10 (cleanup, database enhancements)
- ⚪ Deferred: 4+ (upload job type, transcription check)

**By Category:**
- **Feature Enhancements:** 15
- **Infrastructure:** 6 (proxies, database)
- **Code Cleanup:** 5
- **Documentation:** 2
- **Testing:** 2
- **Bug Fixes:** 2

**By Status:**
- ✅ Active & Ready: 20
- ⚠️ Partially Complete: 5
- 🔵 Blocked (needs external resources): 7
- ❓ Questionable/May be obsolete: 3

---

## 🎯 Recommended Next Steps

1. **Immediate:** Review HCE Summarization Upgrades plan and prioritize which features to implement first
2. **Short-term:** Complete BrightData proxy provider (high value for YouTube processing)
3. **Medium-term:** Create HCE prompt templates for temporality and relations
4. **Long-term:** Clean up technical debt (error taxonomy, obsolete methods)

---

## 📝 Notes

- Many TODOs represent **future enhancements** rather than broken functionality
- Core system is **fully functional** - these are optimization and expansion opportunities
- Proxy provider TODOs are **blocked** on external account setup
- Some TODOs may be **obsolete** due to alternative implementations (e.g., upload functionality)

---

*This file should be reviewed quarterly and updated as TODOs are completed or new ones are identified.*

