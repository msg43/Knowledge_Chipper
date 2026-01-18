# Codebase Cleanup Analysis Report

**Date**: January 17, 2026  
**Branch**: cleanup-2026-01-17

---

## Vulture Analysis (Python Dead Code Detection)

**Command**: `vulture src/knowledge_system --min-confidence 80`

### Findings (25 issues found)

#### Unused Variables (9 issues)
1. `src/knowledge_system/core/segment_processor.py:61` - unused variable 'source_format' (100%)
2. `src/knowledge_system/database/models.py:43` - unused variable 'dialect' (100%)
3. `src/knowledge_system/database/models.py:49` - unused variable 'dialect' (100%)
4. `src/knowledge_system/database/models.py:2391` - unused variable 'connection_record' (100%)
5. `src/knowledge_system/database/service.py:2033` - unused variable 'hce_outputs' (100%)
6. `src/knowledge_system/errors.py:448` - unused variable 'include_context' (100%)
7. `src/knowledge_system/services/podcast_episode_searcher.py:98` - unused variable 'youtube_video_id' (100%)
8. `src/knowledge_system/services/wikidata_categorizer.py:582` - unused variable 'llm_reasoning' (100%)
9. `src/knowledge_system/services/wikidata_categorizer.py:583` - unused variable 'content_snippet' (100%)
10. `src/knowledge_system/utils/speaker_intelligence.py:522` - unused variable 'meeting_time' (100%)
11. `src/knowledge_system/utils/speaker_intelligence.py:536` - unused variable 'email_context' (100%)

#### Unused Imports (9 issues)
1. `src/knowledge_system/database/claim_store.py:14` - unused import 'ClaimExport' (90%)
2. `src/knowledge_system/database/claim_store.py:14` - unused import 'ClaimTag' (90%)
3. `src/knowledge_system/database/download_podcast_categories.py:17` - unused import 'Set' (90%)
4. `src/knowledge_system/database/download_podcast_categories.py:18` - unused import 'urlencode' (90%)
5. `src/knowledge_system/database/models.py:13` - unused import 'JSON' (90%)
6. `src/knowledge_system/database/service.py:21` - unused import 'QualityMetrics' (90%)
7. `src/knowledge_system/processors/audio_processor.py:19` - unused import 'AsyncTranscriptionManager' (90%)
8. `src/knowledge_system/services/playwright_youtube_scraper.py:10` - unused import 'Browser' (90%)
9. `src/knowledge_system/services/playwright_youtube_scraper.py:10` - unused import 'BrowserContext' (90%)
10. `src/knowledge_system/services/youtube_data_api.py:12` - unused import 'urlencode' (90%)

#### Code Quality Issues (4 issues)
1. `src/knowledge_system/processors/audio_processor.py:1886` - redundant if-condition (100%)
2. `src/knowledge_system/utils/cache_management.py:271` - unreachable code after 'return' (100%)
3. `src/knowledge_system/utils/youtube_utils.py:44` - unreachable code after 'return' (100%)
4. `src/knowledge_system/utils/youtube_utils.py:390` - unreachable code after 'return' (100%)

### Action Items
- Clean up unused imports (low priority - doesn't affect functionality)
- Remove unused variables (low priority)
- Fix unreachable code (medium priority - indicates logic errors)
- Review redundant if-condition (low priority)

---

## depcheck Analysis (npm Unused Dependencies)

**Command**: `depcheck --ignores="@types/*,eslint-*,prettier,husky,vitest,jsdom,@vitejs/*,@testing-library/*,tw-animate-css,ts-node,drizzle-kit,supabase"`

### Unused Dependencies (4 packages)
1. `@supabase/auth-helpers-nextjs` - Old Supabase auth helper (replaced by @supabase/ssr)
2. `pgvector` - PostgreSQL vector extension (may be used indirectly)
3. `react-force-graph-2d` - 2D graph visualization (check if used)
4. `react-resizable-panels` - Resizable panel component (check if used)

### Unused devDependencies (1 package)
1. `@tailwindcss/postcss` - Tailwind PostCSS plugin (check if needed for Tailwind v4)

### Missing Dependencies (2 packages)
1. `@playwright/test` - Used in playwright.config.ts (should be in devDependencies)
2. `@axe-core/playwright` - Used in tests/a11y/components.spec.ts (should be in devDependencies)

### Action Items
- **Remove**: `@supabase/auth-helpers-nextjs` (confirmed replaced)
- **Verify then remove**: `react-force-graph-2d`, `react-resizable-panels` (check usage)
- **Keep**: `pgvector` (likely used by Supabase queries)
- **Add to devDependencies**: `@playwright/test`, `@axe-core/playwright`
- **Verify**: `@tailwindcss/postcss` (Tailwind v4 may not need it)

---

## Summary

### Knowledge_Chipper
- **25 issues** found by vulture
- Most are low-priority cleanup (unused imports/variables)
- **4 code quality issues** need attention (unreachable code)

### GetReceipts
- **4 unused dependencies** to review
- **1 unused devDependency** to verify
- **2 missing dependencies** to add

### Next Steps
1. Delete `_deprecated/` folder (122 files)
2. Remove deprecated Python code (HCE, voice, diarization)
3. Clean up unused imports/variables from vulture report
4. Remove confirmed unused npm packages
5. Add missing devDependencies
