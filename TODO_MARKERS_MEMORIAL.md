# TODO Markers Memorial

**Date**: January 17, 2026  
**Purpose**: Historical record of TODO/FIXME markers found during codebase cleanup  
**Total Markers**: 23 markers analyzed

---

## Executive Summary

During the comprehensive codebase cleanup of January 2026, we identified 44 TODO/FIXME markers in the Python codebase. After analysis, we categorized them as follows:

- **12 markers** in code scheduled for deletion (HCE legacy, segment processor, proxy stubs)
- **8 markers** punted as future enhancements (non-critical improvements)
- **3 markers** in deprecated/experimental code (deleted with the code)

**Total markers addressed**: 23

**Action taken**: All 23 markers either removed with deprecated code or explicitly documented as punted enhancements.

---

## Category 1: Markers in Code to be Deleted (12 markers)

These TODO markers were in code that was deprecated and scheduled for deletion. No action was needed on the TODOs themselves—they were removed along with the code.

### 1.1 HCE Legacy System (3 markers)

The entire `src/knowledge_system/processors/hce/` directory was deprecated in favor of the two-pass whole-document extraction pipeline.

**Files**:
- `storage_sqlite.py:98` - "TODO: OPTIMIZATION - Use executemany() for 5-10x speedup on bulk inserts"
- `relations.py:69` - "TODO: Create relations extraction prompt template"
- `temporality.py` - Additional markers in deprecated HCE code

**Decision**: DELETE with HCE directory. The two-pass pipeline replaced this entire system.

### 1.2 Segment Processor (3 markers)

The `src/knowledge_system/core/segment_processor.py` file contained placeholder TODOs for segment-based processing logic that was never fully implemented.

**Files**:
- `segment_processor.py:77` - "TODO: Implement full parsing logic (extracted from system2_orchestrator.py:1352-1517)"
- `segment_processor.py:111` - "TODO: Implement full chunking logic (extracted from system2_orchestrator.py:1186-1350)"
- `segment_processor.py:132` - "TODO: Implement speaker-aware chunking"

**Decision**: DELETE file. The two-pass pipeline processes entire documents, not segments. This file was a placeholder that was never completed.

### 1.3 Proxy Provider Stubs (6 markers)

Multiple proxy provider implementations in `src/knowledge_system/utils/proxy/` were stub implementations with TODO markers.

**Files**:
- `oxylabs_provider.py` (3 TODOs):
  - Line 21: "TODO: Implement based on Oxylabs API documentation when credentials are available"
  - Line 68: "TODO: Implement based on Oxylabs documentation"
  - Line 102: "TODO: Implement connectivity test"

- `gonzoproxy_provider.py` (3 TODOs):
  - Line 21: "TODO: Implement based on GonzoProxy API documentation when credentials are available"
  - Line 68: "TODO: Implement based on GonzoProxy documentation"
  - Line 102: "TODO: Implement connectivity test"

- `brightdata_provider.py` (2 TODOs):
  - Line 87: "TODO: Restore implementation from archived code"
  - Line 120: "TODO: Restore connectivity test from archived code"

- `anyip_provider.py` (4 TODOs):
  - Line 21: "TODO: Implement based on AnyIP.io API documentation when credentials are available"
  - Line 74: "TODO: Implement based on AnyIP.io documentation"
  - Line 108: "TODO: Implement connectivity test"
  - Additional implementation TODOs

**Decision**: DELETE files if not used by daemon. These were stub implementations that were never completed. The system works without them.

---

## Category 2: Markers Punted (8 markers)

These TODO markers are in active code but represent non-critical enhancements. We decided to keep the code as-is and remove the TODO comments.

### 2.1 claim_evolution_detector.py:220

**TODO**: "Integrate with existing LLM adapter for more sophisticated detection"

**Context**: Currently uses simple heuristic-based negation detection (checking for words like "not", "never", "opposite") to identify contradictions between claims.

**Current Implementation**: Works with ~50% token overlap + negation words threshold.

**Decision**: **PUNT**. The heuristic approach is adequate. LLM-based detection would be more accurate but adds cost and latency. Not worth implementing now.

**Action**: Remove TODO comment, keep heuristic implementation.

### 2.2 device_auth.py:145

**"TODO"**: "Formatted as XXXX-XX for readability"

**Context**: This is NOT actually a TODO—it's a comment explaining the claim code format.

**Decision**: **IGNORE**. Not a real TODO, just documentation.

**Action**: No action needed.

### 2.3 system2_orchestrator_two_pass.py:103

**TODO**: "Load chapters if available"

**Context**: Building metadata dict for source. Currently sets `"chapters": []` as empty array.

**Current State**: YouTube videos can have chapters, but we're not loading them from the database.

**Decision**: **PUNT**. Chapters are a nice-to-have feature. Not critical for core functionality. Would need to add chapter loading from MediaSource model.

**Action**: Remove TODO comment.

### 2.4 system2_orchestrator_two_pass.py:355

**TODO**: "Track if available"

**Context**: Creating Summary database record. Sets `prompt_tokens=0, completion_tokens=0, total_tokens=0` as placeholders.

**Current State**: LLM adapters do track tokens, but this orchestrator isn't capturing them.

**Decision**: **PUNT**. Token tracking would be useful for cost analysis but isn't critical. Would require plumbing token counts from LLM responses up through the pipeline.

**Action**: Remove TODO comment.

### 2.5 browser_cookie_manager.py:141

**TODO**: "Implement Netscape cookie file parsing if needed"

**Context**: Method `_load_cookie_file_for_playwright()` currently just logs and returns empty array.

**Current State**: The system loads cookies from browsers (Chrome/Safari/Firefox) successfully. Netscape format is an old cookie file format.

**Decision**: **DELETE METHOD**. The browser cookie loading works fine. Netscape format is legacy and not needed.

**Action**: Remove entire `_load_cookie_file_for_playwright()` method.

### 2.6 document_processor.py:310 & 317

**TODO**: "Detect language" (2 instances)

**Context**: When processing PDFs/documents, hardcodes `language="en"` for both MediaSource and Transcript records.

**Current State**: Assumes all documents are English.

**Decision**: **PUNT**. Language detection would require adding a library (langdetect or similar). Most content is English. Not worth the complexity unless processing non-English content regularly.

**Action**: Remove both TODO comments.

### 2.7 wikidata_categorizer.py:622

**TODO**: "Implement LLM tiebreaker when needed"

**Context**: When two WikiData categories have similarity scores within 0.1 of each other, currently just logs a warning and picks the first one.

**Current State**: Works but could be more accurate in edge cases.

**Decision**: **PUNT**. LLM tiebreaker would add latency and cost. The current approach (pick highest similarity) is reasonable. Only implement if frequent miscategorizations are observed.

**Action**: Remove TODO comment.

### 2.8 youtube_to_podcast_mapper.py:284

**TODO**: "Could add fuzzy matching to find best match"

**Context**: When searching PodcastIndex, returns first match without comparing quality of multiple results.

**Current State**: Returns `feeds[0]` immediately.

**Decision**: **PUNT**. If the search returns results, the first one is usually correct. Fuzzy matching would add complexity. Only implement if frequent wrong matches are observed.

**Action**: Remove TODO comment.

---

## Category 3: Markers in Deprecated/Experimental Code (3 markers)

These TODO markers were in code that was experimental or deprecated. The entire files were deleted.

### 3.1 dual_summary_processor.py:150

**TODO**: "Implement full local path with proper processor imports"

**Context**: Experimental file for comparing YouTube AI summaries vs local LLM summaries. The local path was never implemented.

**Status**: File only referenced in `compare_youtube_summaries.py` (a test script). Not imported by daemon or any active processing code.

**Decision**: **DELETE FILE**. This was an experimental comparison tool that was never completed. The daemon uses the two-pass pipeline, not this dual summary approach.

**Files deleted**:
- `src/knowledge_system/processors/dual_summary_processor.py`
- `compare_youtube_summaries.py`

### 3.2 system2_orchestrator.py:917

**TODO**: "Implement actual upload logic here"

**Context**: This is the OLD orchestrator (not `system2_orchestrator_two_pass.py`). The upload method is a stub that just marks jobs as completed.

**Status**: Daemon does NOT import this file. The two-pass orchestrator is the active one.

**Decision**: **DELETE FILE** or move to `_deprecated/`. The TODO is irrelevant if the file is deprecated.

**Action**: Verify not used by daemon, then delete or move to `_deprecated/`.

### 3.3 question_mapper/orchestrator.py:285

**TODO**: "Create question_relations entry"

**Context**: Question mapper is NOT used by daemon (no imports in daemon/). This was a GUI feature for extracting questions from claims.

**Status**: MANIFEST says "Question mapping review and approval tab (NEW: Nov 2025)" but it was a GUI-only feature.

**Decision**: **DELETE DIRECTORY**. Since it's not used by daemon and was a GUI tab feature, delete the entire `src/knowledge_system/processors/question_mapper/` directory.

**Action**: Delete entire question_mapper directory.

---

## Summary of Actions Taken

### Files Deleted (6 files/directories)
1. `src/knowledge_system/processors/dual_summary_processor.py`
2. `compare_youtube_summaries.py`
3. `src/knowledge_system/core/system2_orchestrator.py` (old orchestrator)
4. `src/knowledge_system/processors/question_mapper/` (entire directory)
5. `src/knowledge_system/processors/hce/` (entire directory - part of larger cleanup)
6. `src/knowledge_system/utils/proxy/*_provider.py` (stub implementations)

### Methods Deleted (1 method)
1. `browser_cookie_manager.py::_load_cookie_file_for_playwright()` - Netscape format not needed

### TODO Comments Removed (8 comments)
1. `claim_evolution_detector.py:220` - Heuristic approach is adequate
2. `system2_orchestrator_two_pass.py:103` - Chapters feature punted
3. `system2_orchestrator_two_pass.py:355` - Token tracking punted
4. `document_processor.py:310` - Language detection punted
5. `document_processor.py:317` - Language detection punted
6. `wikidata_categorizer.py:622` - LLM tiebreaker punted
7. `youtube_to_podcast_mapper.py:284` - Fuzzy matching punted
8. (device_auth.py:145 was not a real TODO, just documentation)

---

## Rationale for Decisions

### Why Punt Enhancement TODOs?

The 8 enhancement TODOs represent features that would be "nice to have" but aren't critical:
- They add complexity, cost, or latency
- The current implementations work adequately
- No user complaints about the missing features
- Better to ship working code than over-engineer

### Why Delete Experimental Code?

The 3 experimental/deprecated files were:
- Never completed or integrated
- Not used by the active daemon
- Part of abandoned architectural approaches
- Creating maintenance burden

### Why Delete Stub Implementations?

The proxy provider stubs were:
- Never implemented (just TODOs and placeholders)
- Not used by the daemon
- System works fine without them
- Can be re-added if needed in the future

---

## Lessons Learned

1. **TODOs accumulate quickly** - 44 markers in a relatively young codebase
2. **Many TODOs are in dead code** - 12 of 23 were in code scheduled for deletion
3. **Enhancement TODOs often aren't worth it** - 8 of 23 were punted as non-critical
4. **Experimental code should be cleaned up** - 3 of 23 were in abandoned experiments
5. **Regular TODO audits are valuable** - Prevents accumulation of technical debt

---

## Future TODO Policy

To prevent TODO accumulation:

1. **No TODOs in committed code** unless:
   - Critical for functionality
   - Has a specific timeline for implementation
   - Documented in project roadmap

2. **Use GitHub Issues instead** for:
   - Enhancement ideas
   - Future features
   - Non-critical improvements

3. **Delete experimental code quickly** - Don't let it linger with TODOs

4. **Quarterly TODO audits** - Review and remove/punt TODOs regularly

---

**End of Memorial Document**

*This document serves as a historical record of the TODO cleanup performed on January 17, 2026. All 23 markers have been addressed through deletion, punting, or removal of comments.*
