# Multi-Base SQLAlchemy Architecture: Analysis and Migration Plan

## Executive Summary

The Knowledge Chipper system currently uses **three separate SQLAlchemy declarative bases**:
1. `MainBase` - Core media sources and transcripts (`models.py`)
2. `HCEBase` - HCE (Hybrid Claim Extraction) models (`hce_models.py`)
3. `System2Base` - System 2 job tracking and LLM requests (`system2_models.py`)

This architecture causes **cross-base foreign key resolution failures** in SQLAlchemy, particularly when:
- Creating new records that reference entities in different bases
- Using in-memory databases for testing
- Flushing sessions with mixed-base entities

**Recommendation**: Merge all models into a single `Base` to eliminate these issues.

---

## What We Learned

### 1. The Problem Manifestation

**Symptom**:
```python
sqlalchemy.exc.NoReferencedTableError: Foreign key associated with column 
'episodes.video_id' could not find table 'media_sources' with which to 
generate a foreign key to target column 'media_id'
```

**When It Occurs**:
- When `Episode` (HCEBase) tries to reference `MediaSource` (MainBase)
- During SQLAlchemy's table sorting phase before flushing
- In both test and production scenarios

### 2. Why Multiple Bases Cause Problems

SQLAlchemy's declarative base creates a **metadata registry** for tables. Each `Base` has its own:
- Table metadata collection
- Mapper registry
- Dependency graph for foreign keys

**The Issue**:
```python
# In hce_models.py
Base = declarative_base()  # Creates HCEBase metadata

class Episode(Base):
    video_id = Column(String, ForeignKey('media_sources.media_id'))
    # ↑ References a table NOT in this Base's metadata!
```

When SQLAlchemy tries to:
1. Sort tables by foreign key dependencies
2. Generate CREATE TABLE statements
3. Flush pending changes

It **only looks within the current Base's metadata**, so it can't find `media_sources`.

### 3. Why It Sometimes "Works"

The code appears to work in some scenarios because:

**Scenario A: Tables Already Exist**
- If tables were created by migrations or previous runs
- SQLAlchemy doesn't need to create them, just reference them
- Foreign key constraints are enforced by the database, not SQLAlchemy

**Scenario B: Separate Transactions**
- If MediaSource and Episode are created in different sessions
- Each session only deals with one Base at a time
- No cross-base dependency resolution needed

**Scenario C: No Flush Triggered**
- If queries don't trigger autoflush
- If commit happens without mixed-base pending changes

### 4. Current Architecture

```
src/knowledge_system/database/
├── models.py (MainBase)
│   ├── MediaSource
│   ├── Transcript
│   ├── Summary
│   ├── GeneratedFile
│   ├── BrightDataSession
│   ├── ProcessingJob
│   ├── ChannelHostMapping
│   └── Speaker* models (5 tables)
│
├── hce_models.py (HCEBase)
│   ├── Episode ──FK──> MediaSource (MainBase) ❌
│   ├── Claim
│   ├── EvidenceSpan
│   ├── Jargon
│   ├── Person
│   ├── Concept
│   ├── ClaimTierValidation
│   ├── QualityMetric
│   ├── QualityRating
│   └── MocExtraction
│
└── system2_models.py (System2Base)
    ├── Job
    ├── JobRun ──FK──> Job (same base) ✅
    ├── LLMRequest ──FK──> JobRun (same base) ✅
    └── LLMResponse ──FK──> LLMRequest (same base) ✅
```

**Key Observation**: Only HCEBase has cross-base foreign keys. System2Base is self-contained.

---

## Migration Plan: Merge to Single Base

### Phase 1: Preparation (1-2 hours)

#### 1.1 Audit All Foreign Keys

Document every foreign key relationship:

```bash
# Find all ForeignKey definitions
grep -r "ForeignKey" src/knowledge_system/database/*.py
```

**Expected Cross-Base FKs**:
- `Episode.video_id` → `MediaSource.media_id` (HCE → Main)
- Possibly others in HCE models

#### 1.2 Backup Current State

```bash
# Backup database
cp ~/Library/Application\ Support/KnowledgeChipper/knowledge_system.db \
   ~/Library/Application\ Support/KnowledgeChipper/knowledge_system.db.backup

# Backup code
git checkout -b feature/single-base-migration
git add -A
git commit -m "Pre-migration: Multiple declarative bases"
```

#### 1.3 Create Test Suite

Create a comprehensive test to verify nothing breaks:

```python
# tests/test_single_base_migration.py
def test_all_models_accessible():
    """Verify all models work after migration."""
    from src.knowledge_system.database.models import Base
    
    # Should be able to access all models
    assert 'media_sources' in Base.metadata.tables
    assert 'episodes' in Base.metadata.tables
    assert 'claims' in Base.metadata.tables
    assert 'job' in Base.metadata.tables
    # ... etc
```

### Phase 2: Code Migration (2-3 hours)

#### 2.1 Choose the Primary Base

**Recommendation**: Use `MainBase` from `models.py` as the single base because:
- It's the oldest and most established
- Most imports already reference it
- Fewer files need updating

#### 2.2 Migration Steps

**Step 1: Move HCE Models to models.py**

```python
# In src/knowledge_system/database/models.py

# Remove this from hce_models.py:
# Base = declarative_base()

# Add to models.py (after existing models):

# ============================================================================
# HCE (Hybrid Claim Extraction) Models
# ============================================================================

class Episode(Base):  # Use existing Base, not new one
    """Episode extracted from a media source during HCE processing."""
    
    __tablename__ = "episodes"
    __table_args__ = {"extend_existing": True}
    
    episode_id = Column(String, primary_key=True)
    video_id = Column(String, ForeignKey("media_sources.media_id"), nullable=False)
    # ... rest of model
    
    # Relationship now works because both tables in same Base!
    media_source = relationship("MediaSource", back_populates="episodes")

class Claim(Base):
    # ... move from hce_models.py

class EvidenceSpan(Base):
    # ... move from hce_models.py

# ... move all other HCE models
```

**Step 2: Move System2 Models to models.py**

```python
# In src/knowledge_system/database/models.py

# ============================================================================
# System 2 Job Tracking Models
# ============================================================================

class Job(Base):  # Use existing Base
    """System 2 job definition."""
    __tablename__ = "job"
    # ... rest of model

class JobRun(Base):
    # ... move from system2_models.py

class LLMRequest(Base):
    # ... move from system2_models.py

class LLMResponse(Base):
    # ... move from system2_models.py
```

**Step 3: Update hce_models.py to be a Re-export Module**

```python
# src/knowledge_system/database/hce_models.py
"""
HCE models - Re-exports from unified models.py for backward compatibility.

This module maintains the old import paths while using the unified Base.
"""

from .models import (
    Base,  # Now the unified base
    Episode,
    Claim,
    EvidenceSpan,
    Jargon,
    Person,
    Concept,
    ClaimTierValidation,
    QualityMetric,
    QualityRating,
    MocExtraction,
)

__all__ = [
    "Base",
    "Episode",
    "Claim",
    "EvidenceSpan",
    "Jargon",
    "Person",
    "Concept",
    "ClaimTierValidation",
    "QualityMetric",
    "QualityRating",
    "MocExtraction",
]
```

**Step 4: Update system2_models.py Similarly**

```python
# src/knowledge_system/database/system2_models.py
"""
System 2 models - Re-exports from unified models.py for backward compatibility.
"""

from .models import (
    Base,
    Job,
    JobRun,
    LLMRequest,
    LLMResponse,
)

__all__ = ["Base", "Job", "JobRun", "LLMRequest", "LLMResponse"]
```

#### 2.3 Update Relationships

Add bidirectional relationships where appropriate:

```python
# In models.py

class MediaSource(Base):
    # ... existing fields
    
    # Add relationship to episodes
    episodes = relationship("Episode", back_populates="media_source")

class Episode(Base):
    # ... existing fields
    
    # Add relationship to media source
    media_source = relationship("MediaSource", back_populates="episodes")
```

### Phase 3: Update Imports (1-2 hours)

#### 3.1 Find All Import Statements

```bash
# Find all imports of the old bases
grep -r "from.*hce_models import" src/
grep -r "from.*system2_models import" src/
grep -r "from.*models import" src/
```

#### 3.2 Update Import Patterns

**Most imports won't need changes** because we're keeping the re-export modules!

Only update imports that specifically import `Base`:

```python
# OLD (if importing Base from multiple places)
from src.knowledge_system.database.models import Base as MainBase
from src.knowledge_system.database.hce_models import Base as HCEBase

# NEW (single Base)
from src.knowledge_system.database.models import Base
```

### Phase 4: Update Database Service (30 minutes)

#### 4.1 Simplify Table Creation

```python
# In src/knowledge_system/database/service.py

class DatabaseService:
    def __init__(self, db_url: str | None = None):
        # ... existing init code
        
        # OLD: Create tables from multiple bases
        # from .models import Base as MainBase
        # from .hce_models import Base as HCEBase
        # from .system2_models import Base as System2Base
        # MainBase.metadata.create_all(self.engine)
        # HCEBase.metadata.create_all(self.engine)
        # System2Base.metadata.create_all(self.engine)
        
        # NEW: Single base
        from .models import Base
        Base.metadata.create_all(self.engine)
```

### Phase 5: Update Tests (1-2 hours)

#### 5.1 Update Test Fixtures

```python
# In test fixtures (conftest.py or individual test files)

@pytest.fixture
def test_db_service():
    """Create test database with all tables."""
    db_service = DatabaseService("sqlite:///:memory:")
    
    # OLD: Multiple bases
    # from src.knowledge_system.database.models import Base as MainBase
    # from src.knowledge_system.database.hce_models import Base as HCEBase
    # from src.knowledge_system.database.system2_models import Base as System2Base
    # MainBase.metadata.create_all(db_service.engine)
    # HCEBase.metadata.create_all(db_service.engine)
    # System2Base.metadata.create_all(db_service.engine)
    
    # NEW: Single base
    from src.knowledge_system.database.models import Base
    Base.metadata.create_all(db_service.engine)
    
    yield db_service
```

#### 5.2 Remove Cross-Base Workarounds

Remove the code we added to `hce_operations.py` that creates MediaSource:

```python
# REMOVE THIS (no longer needed):
# Ensure media source exists (required for foreign key)
from .models import MediaSource
media_source = session.query(MediaSource).filter_by(media_id=video_id).first()
if not media_source:
    media_source = MediaSource(...)
    session.add(media_source)
    session.flush()
```

The foreign key will now resolve correctly because both tables are in the same Base!

### Phase 6: Testing (2-3 hours)

#### 6.1 Run All Tests

```bash
# Unit tests
pytest tests/system2/test_hce_operations.py -v

# Integration tests
pytest tests/system2/test_llm_adapter_real.py -v -m integration

# Full suite
python tests/run_all_tests.py all --verbose
```

#### 6.2 Test Database Operations

```bash
# Test creating episodes with foreign keys
python -c "
from src.knowledge_system.database import DatabaseService
from src.knowledge_system.database.hce_operations import store_mining_results
from src.knowledge_system.processors.hce.unified_miner import UnifiedMinerOutput

db = DatabaseService('sqlite:///test_single_base.db')

output = UnifiedMinerOutput({
    'claims': [{'claim_id': 'test1', 'claim_text': 'Test', 'claim_type': 'factual'}],
    'jargon': [], 'people': [], 'mental_models': []
})

store_mining_results(db, 'episode_test', [output])
print('✅ Single base works!')
"
```

#### 6.3 Test GUI

```bash
# Launch GUI and verify all functionality
python -m knowledge_system.gui
```

Test:
- Creating new episodes
- Viewing HCE data
- Running System 2 jobs
- All database operations

### Phase 7: Migration Script (Optional, 1 hour)

If you have existing data, create a migration script:

```python
# scripts/migrate_to_single_base.py
"""
Migration script for moving to single Base.

Note: This is mostly a no-op because table schemas don't change,
only the Python code organization changes.
"""

from src.knowledge_system.database import DatabaseService
from src.knowledge_system.database.models import Base

def migrate():
    """Verify all tables exist and are accessible."""
    db = DatabaseService()
    
    # Verify all tables
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    
    expected_tables = [
        'media_sources', 'transcripts', 'summaries',
        'episodes', 'claims', 'jargon', 'people', 'concepts',
        'job', 'job_run', 'llm_request', 'llm_response',
    ]
    
    missing = [t for t in expected_tables if t not in tables]
    if missing:
        print(f"❌ Missing tables: {missing}")
        print("Creating missing tables...")
        Base.metadata.create_all(db.engine)
    else:
        print("✅ All tables present")
    
    print(f"Total tables: {len(tables)}")
    print("Migration complete!")

if __name__ == "__main__":
    migrate()
```

---

## Benefits of Single Base

### 1. **Eliminates Cross-Base FK Issues** ✅
- No more `NoReferencedTableError`
- Foreign keys resolve correctly
- Table sorting works properly

### 2. **Simpler Code** ✅
```python
# Before: Multiple imports
from .models import Base as MainBase
from .hce_models import Base as HCEBase
from .system2_models import Base as System2Base

# After: Single import
from .models import Base
```

### 3. **Better Testing** ✅
- In-memory databases work correctly
- No special test setup needed
- Faster test execution

### 4. **Easier Maintenance** ✅
- One place to look for all models
- Clear dependency graph
- Simpler migrations

### 5. **Better Relationships** ✅
```python
# Can now do:
episode.media_source  # Direct relationship
media_source.episodes  # Reverse relationship
```

---

## Risks and Mitigation

### Risk 1: Breaking Existing Imports

**Mitigation**: Keep re-export modules (`hce_models.py`, `system2_models.py`)
- Old imports continue to work
- Gradual migration possible
- No immediate breaking changes

### Risk 2: Database Migration Issues

**Mitigation**: No schema changes needed!
- Tables remain the same
- Only Python code changes
- Existing data unaffected

### Risk 3: Merge Conflicts

**Mitigation**: 
- Do migration in dedicated branch
- Coordinate with team
- Merge during quiet period

### Risk 4: Hidden Dependencies

**Mitigation**:
- Comprehensive test suite
- Grep for all imports
- Test in staging first

---

## Timeline Estimate

| Phase | Time | Difficulty |
|-------|------|------------|
| 1. Preparation | 1-2 hours | Easy |
| 2. Code Migration | 2-3 hours | Medium |
| 3. Update Imports | 1-2 hours | Easy |
| 4. Update Database Service | 30 min | Easy |
| 5. Update Tests | 1-2 hours | Medium |
| 6. Testing | 2-3 hours | Medium |
| 7. Migration Script | 1 hour | Easy |
| **Total** | **9-14 hours** | **Medium** |

**Recommendation**: Allocate 2 full days for the migration including testing and fixes.

---

## Alternative: Keep Multiple Bases

If merging is not feasible, alternatives include:

### Option A: Remove Foreign Key Constraint

```python
class Episode(Base):
    # Remove FK constraint, just store the ID
    video_id = Column(String, nullable=False)  # No ForeignKey()
    
    # Handle referential integrity in application code
    @property
    def media_source(self):
        from .models import MediaSource
        return session.query(MediaSource).filter_by(media_id=self.video_id).first()
```

**Pros**: No SQLAlchemy issues
**Cons**: Lose database-level referential integrity

### Option B: Use Different ORM

Switch to an ORM that handles cross-module relationships better (e.g., Django ORM, Pony ORM).

**Pros**: Might handle cross-base FKs better
**Cons**: Major refactor, learning curve

### Option C: Accept Current Limitations

Keep multiple bases and work around issues:
- Use persistent test databases
- Ensure MediaSource exists before creating Episode
- Document the limitation

**Pros**: No code changes needed
**Cons**: Ongoing maintenance burden

---

## Recommendation

**Merge to single Base** is the best solution because:

1. ✅ **Solves the root cause** (not a workaround)
2. ✅ **Reasonable effort** (9-14 hours)
3. ✅ **No data migration** (only code changes)
4. ✅ **Backward compatible** (via re-exports)
5. ✅ **Long-term benefits** (simpler, more maintainable)

The migration is straightforward and the benefits far outweigh the effort.

---

## Next Steps

1. **Review this plan** with the team
2. **Schedule the migration** (allocate 2 days)
3. **Create feature branch** (`feature/single-base-migration`)
4. **Follow phases 1-7** systematically
5. **Test thoroughly** before merging
6. **Update documentation** after migration

---

## Questions to Consider

Before starting:

1. **Are there any external tools** that depend on the current structure?
2. **Are there any migrations** that need to be updated?
3. **Is there a staging environment** to test first?
4. **Who needs to review** the changes?
5. **What's the rollback plan** if issues arise?

---

## Conclusion

The multi-base architecture was likely created for modularity, but it introduces SQLAlchemy limitations that outweigh the benefits. Merging to a single Base is:

- **Technically sound** ✅
- **Low risk** ✅  
- **High reward** ✅
- **Recommended** ✅

The migration can be done incrementally and safely with proper testing.

