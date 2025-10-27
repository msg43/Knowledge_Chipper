# Database Access Patterns

**Date:** October 26, 2025  
**Applies to:** Knowledge Chipper / Knowledge System

---

## Overview

The Knowledge System uses **three different database access patterns**, each optimized for specific use cases. This document explains when to use each pattern and why.

---

## The Three Patterns

### 1. 🎯 **ORM (SQLAlchemy Models)**

**Use for:**
- Single-record CRUD operations
- Simple queries with relationships
- Type-safe operations
- When maintainability > raw performance

**Examples:**
```python
# Creating a video record
video = Video(
    video_id="abc123",
    title="My Video",
    url="https://youtube.com/watch?v=abc123"
)
db_service.session.add(video)
db_service.session.commit()

# Querying with relationships
video = db_service.session.query(Video)\
    .filter(Video.video_id == "abc123")\
    .first()
transcripts = video.transcripts  # Automatic relationship loading
```

**Benefits:**
- ✅ Type-safe (IDE autocomplete, type checking)
- ✅ Automatic relationship handling
- ✅ Easy to maintain and understand
- ✅ Built-in validation

**Overhead:**
- ⚠️ ~10-20% slower than raw SQL
- ⚠️ Memory overhead for Python objects
- ⚠️ Not ideal for bulk operations (100+ records)

**When to use:**
```python
# ✅ Good - single record
db_service.create_video(video_data)

# ✅ Good - simple query
videos = db_service.get_videos_by_status("pending")

# ❌ Bad - bulk insert (use bulk_insert_json instead)
for claim in 500_claims:
    session.add(claim)  # Slow!
```

---

### 2. ⚡ **Direct SQL (cursor.execute)**

**Use for:**
- Bulk writes (100+ records)
- Complex joins and analytics queries
- Performance-critical paths
- When you need full SQL control

**Examples:**
```python
# Bulk insert with ON CONFLICT handling
conn = db_service.engine.raw_connection()
cur = conn.cursor()
cur.execute("BEGIN")

for claim in claims:
    cur.execute("""
        INSERT INTO hce_claims(episode_id, claim_id, canonical, tier)
        VALUES(?, ?, ?, ?)
        ON CONFLICT(episode_id, claim_id) DO UPDATE SET
            canonical = excluded.canonical,
            tier = excluded.tier
    """, (claim.episode_id, claim.claim_id, claim.canonical, claim.tier))

cur.execute("COMMIT")
```

**Benefits:**
- ✅ Maximum performance (~80% faster than ORM for bulk)
- ✅ Full control over SQL (CTEs, window functions, etc.)
- ✅ Fine-grained conflict resolution
- ✅ Direct FTS index manipulation

**Trade-offs:**
- ⚠️ Manual type handling (no validation)
- ⚠️ More verbose code
- ⚠️ No automatic relationship loading
- ⚠️ SQL injection risk if not parameterized

**When to use:**
```python
# ✅ Good - bulk write (HCEStore pattern)
for claim in 500_claims:
    cur.execute("INSERT INTO hce_claims(...) VALUES(...)", data)

# ✅ Good - complex analytics
cur.execute("""
    SELECT episode_id, COUNT(*) as claim_count,
           AVG(importance) as avg_importance
    FROM hce_claims
    WHERE tier = 'A'
    GROUP BY episode_id
    HAVING claim_count > 10
""")

# ❌ Bad - simple single-record insert (use ORM)
cur.execute("INSERT INTO videos(...) VALUES(...)", data)  # Overkill!
```

---

### 3. 🚀 **bulk_insert_json()**

**Use for:**
- High-volume inserts (100+ records)
- Batch data imports
- When you want speed + parameter safety

**Examples:**
```python
# Bulk insert with conflict resolution
claims_data = [
    {"episode_id": "ep1", "claim_id": "c1", "canonical": "...", "tier": "A"},
    {"episode_id": "ep1", "claim_id": "c2", "canonical": "...", "tier": "B"},
    # ... 500 more claims
]

count = db_service.bulk_insert_json(
    table_name="hce_claims",
    records=claims_data,
    conflict_resolution="REPLACE"  # or "IGNORE" or "FAIL"
)
print(f"Inserted {count} claims")
```

**Benefits:**
- ✅ Fast (~80% faster than ORM, nearly as fast as raw SQL)
- ✅ Parameter-safe (prevents SQL injection)
- ✅ Simple API (just pass list of dicts)
- ✅ Flexible conflict handling

**Limitations:**
- ⚠️ All records must have same schema (keys)
- ⚠️ No relationship handling
- ⚠️ No validation (manual type checking needed)

**When to use:**
```python
# ✅ Good - bulk import from API
api_results = fetch_youtube_metadata(video_ids)  # 200 videos
db_service.bulk_insert_json("videos", api_results)

# ✅ Good - batch processing results
processed_claims = [process(claim) for claim in raw_claims]
db_service.bulk_insert_json("hce_claims", processed_claims)

# ❌ Bad - single record (use ORM)
db_service.bulk_insert_json("videos", [single_video])  # Overkill!

# ❌ Bad - need relationships (use ORM)
# bulk_insert_json doesn't handle foreign keys automatically
```

---

## Decision Tree

```
┌─────────────────────────────────┐
│ How many records?               │
└────────┬────────────────────────┘
         │
    ┌────┴────┐
    │ 1-10?   │
    └────┬────┘
         │
         ├─ Yes ──→ Use ORM
         │
         └─ No ───→ 100+?
                    │
                    ├─ Yes ──→ Need complex SQL logic?
                    │          │
                    │          ├─ Yes → Direct SQL (cursor.execute)
                    │          └─ No ─→ bulk_insert_json()
                    │
                    └─ No (10-100) ──→ Use ORM with batching
                                       (flush every 50 records)
```

---

## Real-World Examples

### ✅ HCEStore - Direct SQL (Correct Choice)

**Why:**
- Writes 500-1000 records per job
- Needs complex ON CONFLICT logic
- Updates FTS indexes
- Performance-critical path

**Pattern:**
```python
def upsert_pipeline_outputs(self, outputs):
    conn = self.db_service.engine.raw_connection()
    cur = conn.cursor()
    cur.execute("BEGIN")
    
    # Bulk insert claims with conflict handling
    for claim in outputs.claims:  # 100-200 claims
        cur.execute("""
            INSERT INTO hce_claims(...) VALUES(...)
            ON CONFLICT(...) DO UPDATE SET ...
        """, claim_data)
    
    # Update FTS indexes
    cur.execute("INSERT INTO hce_claims_fts SELECT ...")
    
    cur.execute("COMMIT")
```

**Performance:** ~500-1000 records/second

---

### ✅ DatabaseService - ORM (Correct Choice)

**Why:**
- Mostly single-record operations
- Simple queries
- Needs type safety
- Relationships matter

**Pattern:**
```python
def create_video(self, video_data):
    video = Video(**video_data)
    self.session.add(video)
    self.session.commit()
    return video

def get_video_by_id(self, video_id):
    return self.session.query(Video)\
        .filter(Video.video_id == video_id)\
        .first()
```

**Performance:** Acceptable for single records

---

### ✅ bulk_insert_json() - Available for Future Use

**When to use:**
- Batch YouTube metadata import
- Bulk claim validation results
- Large CSV/JSON imports

**Pattern:**
```python
# Import 500 video metadata records
metadata_records = [
    {"video_id": "v1", "title": "...", "duration": 3600},
    {"video_id": "v2", "title": "...", "duration": 1800},
    # ... 498 more
]

db_service.bulk_insert_json(
    "videos",
    metadata_records,
    conflict_resolution="REPLACE"
)
```

---

## Performance Comparison

| Pattern | Single Record | 100 Records | 1000 Records | Type Safety | SQL Control |
|---------|--------------|-------------|--------------|-------------|-------------|
| **ORM** | ~1ms | ~150ms | ~1500ms | ✅ Yes | ⚠️ Limited |
| **bulk_insert_json** | ~2ms | ~20ms | ~120ms | ❌ No | ⚠️ Basic |
| **Direct SQL** | ~0.5ms | ~15ms | ~100ms | ❌ No | ✅ Full |

**Benchmark conditions:** SQLite on SSD, simple inserts, no indexes

---

## Best Practices

### 1. Default to ORM
```python
# ✅ Start with ORM for new features
video = Video(video_id=vid, title=title)
session.add(video)
```

### 2. Measure Before Optimizing
```python
# ✅ Profile first, then optimize
import time
start = time.time()
# ... your code ...
print(f"Took {time.time() - start:.2f}s")

# Only switch to direct SQL if ORM is measurably slow
```

### 3. Batch ORM Operations
```python
# ✅ Flush in batches if using ORM for moderate bulk (10-100 records)
for i, claim in enumerate(claims):
    session.add(claim)
    if i % 50 == 0:
        session.flush()
session.commit()
```

### 4. Document Your Choice
```python
# ✅ Explain why you chose a pattern
def upsert_hce_data(self, outputs):
    """
    Uses direct SQL for performance.
    HCE jobs write 500+ records and need ~2s total time.
    ORM would take ~10s for same operation.
    """
    conn = self.engine.raw_connection()
    # ...
```

---

## Common Mistakes

### ❌ Using ORM for Bulk Inserts
```python
# BAD - Takes 10+ seconds for 500 records
for claim in 500_claims:
    session.add(Claim(**claim))
session.commit()

# GOOD - Takes ~0.5 seconds
db_service.bulk_insert_json("hce_claims", claims_data)
```

### ❌ Using Direct SQL for Single Records
```python
# BAD - Verbose, no type safety
cur.execute("INSERT INTO videos(video_id, title) VALUES(?, ?)", (vid, title))

# GOOD - Clean, type-safe
video = Video(video_id=vid, title=title)
session.add(video)
```

### ❌ Forgetting to Parameterize
```python
# DANGER - SQL injection risk!
cur.execute(f"INSERT INTO videos VALUES('{user_input}')")

# SAFE - Parameterized query
cur.execute("INSERT INTO videos VALUES(?)", (user_input,))
```

---

## Summary

**Use the right tool for the job:**

| Situation | Pattern | Why |
|-----------|---------|-----|
| Single record CRUD | ORM | Type-safe, easy |
| Simple queries | ORM | Relationship handling |
| Bulk writes (100+) | Direct SQL or bulk_insert_json | Performance |
| Complex analytics | Direct SQL | Full SQL control |
| Batch imports | bulk_insert_json | Speed + safety |

**When in doubt:**
1. Start with ORM
2. Measure performance
3. Optimize if needed (usually you won't need to)

---

**See Also:**
- `src/knowledge_system/database/service.py` - DatabaseService implementation
- `src/knowledge_system/database/hce_store.py` - Direct SQL example
- SQLAlchemy docs: https://docs.sqlalchemy.org/
