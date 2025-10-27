# Deprecated Code

This directory contains code deprecated during the storage unification (v2.0.0-unified).

## Files

### database/hce_operations.py
**Deprecated:** 2025-10-23  
**Replaced by:** `storage_sqlite.upsert_pipeline_outputs()` and `system2_orchestrator_mining.py`  
**Reason:** Dual storage paths consolidated into unified pipeline

**What it did:**
- Stored mining results using SQLAlchemy ORM
- Sequential segment-by-segment processing
- Simple data structures without evidence spans or relations

**Why it was replaced:**
- Performance: Sequential processing was 3-8x slower than parallel
- Data quality: Lacked evidence spans, claim relations, and structured categories
- Maintainability: Dual storage paths (main DB + HCE DB) were confusing
- Architecture: UnifiedHCEPipeline provides better separation of concerns

### database/hce_models.py  
**Status:** Re-exported from models.py for backward compatibility  
**Not deprecated yet:** Still used by some legacy code paths

## Rollback

If you need to rollback to the old system:

```bash
# Restore deprecated code
git mv _deprecated/database/hce_operations.py src/knowledge_system/database/

# Restore old System2Orchestrator._process_mine()
git show backup/before-unification:src/knowledge_system/core/system2_orchestrator.py > temp_orchestrator.py
# Then manually copy the _process_mine method back

# Restore database
cp knowledge_system.db.pre_unification.TIMESTAMP knowledge_system.db
```

## Migration Path

Old code that imports `hce_operations`:
```python
from ..database.hce_operations import store_mining_results
```

Should be updated to:
```python
from ..processors.hce.storage_sqlite import upsert_pipeline_outputs, open_db
from pathlib import Path

# Old way
store_mining_results(db_service, episode_id, miner_outputs)

# New way
unified_db = Path.home() / "Library" / "Application Support" / "SkipThePodcast" / "unified_hce.db"
conn = open_db(unified_db)
upsert_pipeline_outputs(conn, pipeline_outputs, episode_title="...", video_id="...")
conn.commit()
conn.close()
```

## Timeline

- **2025-10-23**: Storage unification implemented
- **2025-11-23** (planned): Remove deprecated code after 30-day grace period
- **2025-12-23** (planned): Delete _deprecated directory entirely

## Questions?

See:
- `UNIFICATION_MASTER_PLAN.md` - Full implementation plan
- `docs/ARCHITECTURE_UNIFIED.md` - New architecture documentation
- `docs/guides/USER_GUIDE_UNIFIED.md` - User guide for new system
