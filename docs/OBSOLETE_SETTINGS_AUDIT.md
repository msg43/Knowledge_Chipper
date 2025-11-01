# Obsolete Settings Audit

**Date:** October 31, 2025  
**Purpose:** Identify GUI settings that have no backend implementation (technical debt)

---

## Findings

### ❌ OBSOLETE: Tier Thresholds (Summarization Tab)

**GUI Widgets:**
- `tier_a_threshold_spin` - Line 930-944
- `tier_b_threshold_spin` - Line 946-960

**Current Values:**
- Tier A: 85%
- Tier B: 65%

**Status:** **COMPLETELY UNUSED**

**Evidence:**
1. ✅ Defined in `config.py` lines 586-591
2. ✅ Displayed in GUI (summarization_tab.py)
3. ✅ Saved to session state
4. ❌ **NEVER used in HCE processing**

**How Tiers Are Actually Assigned:**
- Tiers (A, B, C) are assigned **BY THE LLM** in the flagship evaluator
- See `schemas/flagship_output.v1.json` line 59-63: `tier` is an enum field in the LLM output
- The LLM decides tier based on its own judgment, not numeric thresholds
- No code in `src/knowledge_system/processors/hce/` references `tier_a_threshold` or `tier_b_threshold`

**Recommendation:** **DELETE ENTIRELY**
- Remove from GUI (summarization_tab.py)
- Remove from config.py
- Remove from settings.yaml
- Update documentation to clarify tiers are LLM-assigned

---

### ❌ OBSOLETE: Token Budgets (Summarization Tab)

**GUI Widgets:**
- `flagship_file_tokens_spin` - Line 1236-1239
- `flagship_session_tokens_spin` - Line 1250-1253

**Current Values:**
- File tokens: 0 (Unlimited)
- Session tokens: 0 (Unlimited)

**Status:** **COMPLETELY UNUSED**

**Evidence:**
1. ✅ Displayed in GUI (collapsed by default)
2. ✅ Saved to session state
3. ❌ **NEVER used anywhere** - grep found ZERO references in processing code
4. ❌ Not in config.py
5. ❌ Not in settings.yaml
6. ❌ Not passed to any LLM adapter or orchestrator

**Recommendation:** **DELETE ENTIRELY**
- These appear to be placeholder UI for a feature that was never implemented
- No backend support exists
- Confusing to users (looks like it should work but doesn't)

---

### ✅ USED: Claim Tier Filter (Summarization Tab)

**GUI Widget:**
- `claim_tier_combo` - Line 909

**Status:** **USED - UI filter only**

**Evidence:**
- Used in `_load_database_episodes()` to filter which claims to display
- This is a UI filter, not a processing configuration
- Should still follow settings hierarchy for user convenience

**Recommendation:** **KEEP - Fix to use settings hierarchy**

---

### ✅ USED: Max Claims (Summarization Tab)

**GUI Widget:**
- `max_claims_spin` - Line 925

**Status:** **USED**

**Evidence:**
- Used in database queries to limit results
- Valid UI configuration

**Recommendation:** **KEEP - Fix to use settings hierarchy**

---

## Summary

**DELETE (Technical Debt):**
1. Tier A Threshold spinbox
2. Tier B Threshold spinbox  
3. Flagship File Tokens spinbox
4. Flagship Session Tokens spinbox
5. Budgets & Limits group box (entire section)

**KEEP & FIX (Real Settings):**
1. Provider combo
2. Model combo
3. Claim tier filter combo (UI state)
4. Max claims spinbox (UI limit)
5. Template path
6. Advanced model provider/model combos

---

## Implementation

### Step 1: Remove Obsolete Code

**File:** `src/knowledge_system/gui/tabs/summarization_tab.py`

Remove lines ~930-960 (tier threshold spinboxes)
Remove lines ~1225-1265 (budgets group)
Remove from `_load_settings()` lines ~3095-3105
Remove from `_save_settings()` lines ~3297-3311

**File:** `src/knowledge_system/config.py`

Remove lines 586-591 (tier threshold fields from HCEConfig)

**File:** `config/settings.example.yaml`

No changes needed (tier thresholds not documented there)

### Step 2: Update Documentation

Add note to HCE documentation:
> **Note:** Claim tiers (A, B, C) are assigned by the LLM flagship evaluator based on its judgment of importance, novelty, and confidence. There are no numeric thresholds - the LLM decides tier assignment holistically.

---

## Estimated Effort

- Remove obsolete code: 15 minutes
- Test GUI still works: 5 minutes
- Update documentation: 5 minutes

**Total: ~25 minutes**

---

## Benefits

1. **Reduced Confusion** - Users won't see settings that don't work
2. **Cleaner UI** - Less clutter in summarization tab
3. **Honest Interface** - GUI accurately reflects what the system does
4. **Less Maintenance** - Fewer settings to manage and test
5. **Technical Debt Paid** - Remove dead code

---

## Related

- `docs/SETTINGS_HIERARCHY_AUDIT.md` - Full settings audit
- `schemas/flagship_output.v1.json` - Shows tier is LLM-assigned
- `src/knowledge_system/processors/hce/flagship_evaluator.py` - Tier assignment logic

