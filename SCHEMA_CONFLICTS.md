# Schema Conflicts and Redundancies Analysis

## Summary

After migrating `MediaSource` from `models.py` to `claim_models.py`, several other major conflicts remain:

## 1. Duplicate Table Definitions

### Episodes Table
- **`models.py`**: `Episode` with `video_id` FK to `media_sources.media_id`
- **`claim_models.py`**: `Episode` with `source_id` FK to `media_sources.source_id`
- **Conflict**: Same table name `episodes` but different schemas
- **Impact**: Foreign key mismatches, query failures

### Claims Table
- **`models.py`**: `Claim` with composite PK (`episode_id`, `claim_id`)
- **`claim_models.py`**: `Claim` with single PK `claim_id` (global unique)
- **Conflict**: Same table name `claims` but different primary key structures
- **Impact**: Schema mismatch errors, data integrity issues

### People Table
- **`models.py`**: `Person` with composite PK (`episode_id`, `person_id`)
- **`claim_models.py`**: `Person` with single PK `person_id` (global unique)
- **Conflict**: Same table name `people` but different schemas
- **Impact**: Foreign key errors, query failures

### Concepts Table
- **`models.py`**: `Concept` with composite PK (`episode_id`, `concept_id`)
- **`claim_models.py`**: `Concept` with single PK `concept_id` (global unique)
- **Conflict**: Same table name `concepts` but different schemas
- **Impact**: Foreign key errors, query failures

### Jargon Table
- **`models.py`**: `Jargon` with composite PK (`episode_id`, `term_id`)
- **`claim_models.py`**: `JargonTerm` with single PK `jargon_id` (global unique)
- **Conflict**: Different table names (`jargon` vs `jargon_terms`) but overlapping purpose
- **Impact**: Code confusion, migration issues

## 2. Separate Base Classes

- **`models.py`**: Uses `Base = declarative_base()`
- **`claim_models.py`**: Uses `Base = declarative_base()`
- **Problem**: Two separate ORM hierarchies cannot share foreign keys properly
- **Impact**: Foreign key relationships broken between models from different bases

## 3. Confusing Import Paths

- **`hce_models.py`**: Imports from `models.py` (old schema), not `claim_models.py`
- **Problem**: Code importing from `hce_models` gets old schema models
- **Impact**: Schema mismatches, wrong foreign keys

## 4. Extend Existing Workaround

- Many models in `models.py` have `__table_args__ = {"extend_existing": True}`
- **Problem**: This suggests trying to extend tables that might be defined elsewhere
- **Impact**: Hides schema conflicts, makes debugging harder

## 5. Current Usage Patterns

From code analysis:
- `claim_store.py` uses `claim_models.*` ✅
- `service.py` uses `claim_models.Episode` ✅
- `review_tab_system2.py` uses `claim_models.*` ✅
- `hce_models.py` imports from `models.py` ❌ (wrong!)
- `__init__.py` exports from `hce_models` which uses `models.py` ❌ (wrong!)

## Recommendations

1. **Migrate all HCE models to claim_models**:
   - Update `hce_models.py` to import from `claim_models.py` instead of `models.py`
   - Or deprecate `hce_models.py` entirely

2. **Use single Base class**:
   - Have `claim_models.py` import `Base` from `models.py` (or vice versa)
   - Ensures proper foreign key relationships

3. **Remove `extend_existing` workarounds**:
   - Once unified, these shouldn't be necessary

4. **Update all imports**:
   - Change imports from `hce_models` or `models.*` to `claim_models.*` for HCE-related models
   - Keep `models.py` only for non-HCE models (Transcript, Summary, etc.)

5. **Consider deprecation path**:
   - Mark old `models.py` HCE models as deprecated
   - Add migration path documentation
