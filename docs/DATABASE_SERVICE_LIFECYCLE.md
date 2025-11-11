# DatabaseService Lifecycle Management

**Best Practices for Creating and Reusing Database Connections**

## Overview

The `DatabaseService` class manages SQLite database connections. Following proper lifecycle patterns prevents:
- Connection leaks
- Locking issues (especially on Windows)
- Connection pool exhaustion
- Transaction boundary violations

---

## ✅ Best Practice: Reuse DatabaseService Instances

### Pattern 1: Pass from Top-Level Coordinator

**Recommended for:** GUI applications, batch processing, orchestrators

```python
# In main coordinator (GUI, CLI main, orchestrator)
from knowledge_system.database.service import DatabaseService

class MainCoordinator:
    def __init__(self):
        # Create ONE instance for the entire session
        self.db_service = DatabaseService()
    
    def process_files(self, files):
        # Pass to workers
        for file in files:
            processor = AudioProcessor(
                model="base",
                db_service=self.db_service  # ✅ Reuse
            )
            result = processor.process(file)
```

**Benefits:**
- Single connection pool per application
- Proper transaction boundaries
- No connection leaks
- Better performance (connection reuse)

---

### Pattern 2: Create at Module Entry Point

**Recommended for:** CLI scripts, standalone processors

```python
# In CLI entry point or standalone script
from knowledge_system.database.service import DatabaseService
from knowledge_system.processors.audio_processor import AudioProcessor

def main():
    # Create once at entry point
    db_service = DatabaseService()
    
    # Pass to all processors
    audio_processor = AudioProcessor(
        model="medium",
        db_service=db_service  # ✅ Reuse
    )
    
    # Process files
    for file in files:
        result = audio_processor.process(
            file,
            db_service=db_service  # ✅ Pass to process()
        )
```

---

### Pattern 3: Thread-Safe Worker Pattern

**Recommended for:** Multi-threaded batch processing

```python
from concurrent.futures import ThreadPoolExecutor
from knowledge_system.database.service import DatabaseService

class BatchProcessor:
    def __init__(self):
        # Shared db_service is thread-safe (uses session-per-request)
        self.db_service = DatabaseService()
    
    def process_batch(self, files):
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for file in files:
                # Each thread gets the SAME db_service instance
                # SQLAlchemy sessions are thread-local
                future = executor.submit(
                    self._process_file, 
                    file, 
                    self.db_service  # ✅ Thread-safe
                )
                futures.append(future)
            
            # Collect results
            return [f.result() for f in futures]
    
    def _process_file(self, file, db_service):
        processor = AudioProcessor(db_service=db_service)
        return processor.process(file)
```

**Key Point:** SQLAlchemy's `get_session()` context manager creates thread-local sessions, so sharing one `DatabaseService` instance across threads is safe.

---

## ❌ Anti-Pattern: Creating Multiple Instances

### What NOT to Do

```python
# ❌ BAD: Creates new connection in processor
class AudioProcessor:
    def process(self, file, db_service=None):
        if not db_service:
            # ❌ Creates NEW DatabaseService instance
            db_service = DatabaseService()
        
        # Use db_service...
```

**Problems:**
1. **Connection Pool Exhaustion:** Each instance creates its own connection pool
2. **Locking on Windows:** Multiple connections to same SQLite DB can cause locks
3. **Transaction Isolation:** Different instances can't participate in same transaction
4. **Performance:** Connection creation overhead repeated unnecessarily

---

## 🔧 Fixed Pattern in Knowledge Chipper

As of the latest fixes, `AudioProcessor` now **requires** `db_service` parameter:

```python
# ✅ FIXED: No fallback creation
class AudioProcessor:
    def process(self, file, **kwargs):
        db_service = kwargs.get("db_service")
        if not db_service:
            logger.error("db_service not provided - cannot save to database")
            enhanced_metadata["database_save_failed"] = True
            # Fail gracefully but don't create fallback
        
        if db_service:
            # Use provided db_service...
```

This ensures callers explicitly manage the lifecycle.

---

## 📋 Checklist for Adding New Processors

When creating a new processor that needs database access:

- [ ] Add `db_service` parameter to `__init__()` or `process()`
- [ ] Don't create `DatabaseService()` as fallback
- [ ] Document that `db_service` is required
- [ ] Pass `db_service` from coordinator/main entry point
- [ ] Use `with db_service.get_session() as session:` for queries
- [ ] Don't hold sessions across async operations

---

## 🧪 Testing Pattern

For unit tests, create ONE DatabaseService for the entire test suite:

```python
import pytest
from knowledge_system.database.service import DatabaseService

@pytest.fixture(scope="session")
def db_service():
    """Shared database service for all tests."""
    return DatabaseService()

def test_audio_processing(db_service):
    processor = AudioProcessor(
        model="base",
        db_service=db_service  # ✅ Reuse fixture
    )
    # Test...
```

---

## 🔍 How to Audit Your Code

Search for anti-patterns:

```bash
# Find places creating DatabaseService without passing it
grep -r "DatabaseService()" src/

# Find processors that might create fallback instances
grep -A 5 "if not db_service" src/
```

Review each occurrence:
- **Top-level coordinators:** OK to create
- **Processors/utilities:** Should receive via parameter
- **Fallback creation:** Remove or require parameter

---

## 📚 Related Documentation

- SQLAlchemy Session Management: https://docs.sqlalchemy.org/en/14/orm/session_basics.html
- SQLite Locking: https://www.sqlite.org/lockingv3.html
- Context Managers: https://docs.python.org/3/reference/compound_stmts.html#the-with-statement

---

## Summary

**Golden Rule:** Create `DatabaseService` once at application entry point, pass to all processors.

| Location | Pattern | Action |
|----------|---------|--------|
| Main/GUI/Orchestrator | Create | `db_service = DatabaseService()` |
| Processor | Receive | `def __init__(self, db_service=None)` |
| Worker Function | Receive | `def process(self, db_service)` |
| Utility | Receive | Pass from caller |

This ensures:
- ✅ Single connection pool
- ✅ Proper transaction boundaries  
- ✅ No locking issues
- ✅ Better performance
- ✅ Easier testing
