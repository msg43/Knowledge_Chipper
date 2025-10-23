# Logging Verbosity Reduction

## Overview
Reduced console log verbosity to focus on actionable information: segment mining progress, warnings, errors, and critical debugging information.

## Changes Made

### 1. Removed SimpleProgressBar Debug Prints
**File:** `src/knowledge_system/gui/components/simple_progress_bar.py`

Removed verbose print statements that cluttered the console:
- `🔍 [SimpleProgressBar] Started: total=X, mode=...`
- `🔍 [SimpleProgressBar] Updated: X/Y = Z%...`
- `🔍 [SimpleProgressBar] Current file progress: X% → Total: Y%`
- `🔍 [SimpleProgressBar] Phase: Processing - X%`
- `🔍 [SimpleProgressBar] Finished: completed=X, failed=Y`
- `🔍 [SimpleProgressBar] Reset`
- `🔍 [SimpleProgressBar] Total set: X, switching to determinate mode`

**Rationale:** Progress is already displayed in the GUI progress bars. Console prints are redundant.

### 2. Converted INFO Logs to DEBUG Level

#### LLM Request Logging
**File:** `src/knowledge_system/core/llm_adapter.py`
- Changed `logger.info("LLM request starting...")` → `logger.debug(...)`
- Changed `logger.info("Estimated cost: $...")` → `logger.debug(...)`

**Rationale:** LLM request tracking is useful for debugging but too verbose during normal operation.

#### Resource Monitoring
**File:** `src/knowledge_system/core/dynamic_parallelization.py`
- Changed `logger.info("Resource status - CPU: X%, RAM: Y%...")` → `logger.debug(...)`

**Rationale:** Resource stats logged every minute are noisy. High resource usage warnings remain at WARNING level.

#### Job Run Status
**File:** `src/knowledge_system/core/system2_orchestrator.py`
- Changed `logger.info("Updated job run X status to Y")` → `logger.debug(...)`

**Rationale:** Status updates happen frequently and clutter the log. Checkpoints saved messages also at DEBUG level.

#### Schema Enforcement Messages
**Files:** 
- `src/knowledge_system/processors/hce/unified_miner.py`
- `src/knowledge_system/processors/hce/flagship_evaluator.py`
- `src/knowledge_system/utils/llm_providers.py`

- Changed `logger.info("🔒 Using structured outputs...")` → `logger.debug(...)`

**Rationale:** Schema enforcement is an implementation detail, not user-facing information.

## What Remains Visible at INFO Level

### Segment Mining Progress
The most important progress indicator remains visible in the GUI:
- **Display:** "⚙️ Unified Mining: segment X/Y" in the progress bar
- **Source:** `system2_orchestrator.py` line 453 progress callback
- **GUI:** `summarization_tab.py` line 166

### Important Logs
- **Warnings:** All warnings remain at WARNING level
- **Errors:** All errors remain at ERROR level  
- **Critical Operations:**
  - "Unified mining extracted: X claims, Y jargon terms..."
  - "✅ Diarization completed for 'file': X segments found"
  - "Parallel processing completed: X/Y successful"
  - High resource usage warnings (CPU/RAM > 90%)

## How to Enable Verbose Logging

If you need to see the DEBUG-level logs for troubleshooting:

### Option 1: Environment Variable
```bash
export LOG_LEVEL=DEBUG
python -m knowledge_system.cli ...
```

### Option 2: Settings File
Edit `config/settings.yaml`:
```yaml
monitoring:
  log_level: DEBUG
```

### Option 3: CLI Argument
```bash
python -m knowledge_system.cli --log-level DEBUG ...
```

## Log Output Comparison

### Before (INFO Level - Verbose)
```
2025-10-21 19:07:11.183 | INFO | Updated job run X status to running
2025-10-21 19:07:11.183 | INFO | LLM request starting (1/2 active)
2025-10-21 19:07:12.024 | INFO | Estimated cost: $0.1506
2025-10-21 19:07:12.025 | INFO | 🔒 Using structured outputs with schema enforcement for miner
🔍 [SimpleProgressBar] Phase: Processing - 20%
🔍 [SimpleProgressBar] Current file progress: 20% → Total: 20%
2025-10-21 19:07:12.298 | INFO | Resource status - CPU: 14.6%, RAM: 59.4% (52.0GB available)
```

### After (INFO Level - Clean)
```
2025-10-21 19:07:15.820 | INFO | Parallel processing completed: 23/23 successful
2025-10-21 19:07:16.045 | INFO | Unified mining extracted: 45 claims, 12 jargon terms, 8 people, 5 mental models
```

**Segment progress still visible in GUI:**
```
Progress Bar: [████████████░░░░░░░░] 60%
Status: ⚙️ Unified Mining: segment 14/23
```

## Benefits

1. **Cleaner Console Output:** Only actionable information displayed
2. **Easier Debugging:** Warnings and errors stand out
3. **Better UX:** Users see mining progress without noise
4. **Flexible:** DEBUG logs still available when needed
5. **Performance:** Slightly reduced I/O from fewer log writes

## Notes

- All functionality remains unchanged
- GUI progress displays are unaffected
- Segment mining progress is still clearly visible
- Errors, warnings, and important events remain prominent

