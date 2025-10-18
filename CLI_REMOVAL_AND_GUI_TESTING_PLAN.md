# Plan: Remove CLI and Test GUI Code

## Executive Summary

This plan outlines how to:
1. Remove all CLI-specific code
2. Create comprehensive tests for the GUI code (which uses `System2Orchestrator`)
3. Ensure the system only has **one code path** for each operation

**✅ SAFETY VERIFIED:** See `GUI_FUNCTIONALITY_PRESERVATION_AUDIT.md` for complete analysis proving no GUI features will be lost.

---

## Prerequisites

**IMPORTANT:** Before removing any code, complete the audit:

✅ **Audit Complete:** `GUI_FUNCTIONALITY_PRESERVATION_AUDIT.md`
- All GUI features catalogued
- All processors audited
- Dependencies verified
- Migration path identified

**Critical Finding:** Monitor tab needs update before deletion (uses `SummarizerProcessor`)

---

## Phase 1: Identify What to Remove

### CLI Command Files to Delete

```
src/knowledge_system/commands/
├── __init__.py          # DELETE - CLI command registry
├── common.py            # DELETE - CLI context/utilities
├── database.py          # KEEP (move to utils) - useful for DB management
├── moc.py               # DELETE - CLI MOC generation
├── process.py           # DELETE - CLI batch processing
├── summarize.py         # DELETE - CLI summarization
├── transcribe.py        # DELETE - CLI transcription
├── upload.py            # DELETE - CLI upload to STP
└── voice_test.py        # DELETE - CLI voice testing
```

### CLI Entry Points to Remove

```
src/knowledge_system/
├── cli.py               # DELETE - Main CLI entry point
├── __main__.py          # MODIFY - Remove CLI, keep GUI launch
└── pyproject.toml       # MODIFY - Remove CLI console scripts
```

### Processors to Remove or Modify

These are CLI-only wrappers that System2Orchestrator doesn't use:

```
src/knowledge_system/processors/
├── summarizer.py         # DELETE - CLI-specific wrapper
├── summarizer_legacy.py  # DELETE - Old implementation
├── audio_processor.py    # KEEP - Used by GUI transcription tab
└── ...
```

### Keep These (Used by GUI)

```
src/knowledge_system/
├── core/
│   ├── system2_orchestrator.py     # KEEP - GUI uses this
│   ├── llm_adapter.py               # KEEP - GUI needs this
│   └── ...
├── processors/
│   ├── hce/
│   │   └── unified_pipeline.py     # KEEP - Core HCE logic
│   ├── youtube_download.py          # KEEP - GUI YouTube tab
│   ├── diarization.py               # KEEP - GUI transcription
│   └── whisper_cpp_transcribe.py   # KEEP - GUI transcription
├── gui/                             # KEEP - The whole GUI
└── database/                        # KEEP - Database layer
```

---

## Phase 2: Files to Delete

### Step 1: Delete CLI Commands
```bash
# Delete CLI command modules
rm -rf src/knowledge_system/commands/

# Delete main CLI entry point
rm src/knowledge_system/cli.py
```

### Step 2: Delete CLI-Specific Processors
```bash
# Delete CLI wrapper processors
rm src/knowledge_system/processors/summarizer.py
rm src/knowledge_system/processors/summarizer_legacy.py
rm src/knowledge_system/processors/summarizer_unified.py
```

### Step 3: Delete CLI Tests
```bash
# Find and delete CLI-specific tests
rm -rf tests/test_cli*.py
rm -rf tests/commands/
```

### Step 4: Clean Up Entry Points
```python
# Modify pyproject.toml - Remove this section:
[project.scripts]
knowledge-system = "knowledge_system.cli:main"  # DELETE THIS

# Keep or add:
[project.gui-scripts]
knowledge-chipper = "knowledge_system.gui.__main__:main"
```

### Step 5: Update __main__.py
```python
# src/knowledge_system/__main__.py
# OLD:
if __name__ == "__main__":
    from .cli import main  # CLI entry
    main()

# NEW:
if __name__ == "__main__":
    from .gui.__main__ import main  # GUI only
    main()
```

---

## Phase 3: Create GUI Tests for System2Orchestrator

### Current GUI Test Status

**What Exists:**
- `tests/gui_comprehensive/` - Framework for GUI interaction testing
- Tests GUI buttons, file loading, tab switching
- Does NOT test the actual processing logic

**What's Missing:**
- Tests for `System2Orchestrator.process_job()`
- Tests for async/threading behavior
- Tests for LLM adapter with async clients
- Tests for event loop management
- Integration tests that validate full pipeline

### Tests to Create

#### 3.1: System2Orchestrator Tests

```python
# tests/system2/test_orchestrator.py
import pytest
import asyncio
from pathlib import Path
from knowledge_system.core.system2_orchestrator import System2Orchestrator
from knowledge_system.database import DatabaseService

class TestSystem2Orchestrator:
    """Test the System2Orchestrator used by GUI."""
    
    @pytest.fixture
    async def orchestrator(self):
        """Create orchestrator with test database."""
        db = DatabaseService(":memory:")  # In-memory test DB
        return System2Orchestrator(db_service=db)
    
    @pytest.mark.asyncio
    async def test_create_and_process_mine_job(self, orchestrator, tmp_path):
        """Test creating and processing a mining job (summarization)."""
        # Create test transcript
        test_file = tmp_path / "test_transcript.md"
        test_file.write_text("This is a test transcript with some content.")
        
        # Create job
        job_id = orchestrator.create_job(
            job_type="mine",
            input_id="test_episode",
            config={
                "source": "test",
                "file_path": str(test_file),
                "miner_model": "openai:gpt-4o-mini",
            }
        )
        
        # Process job
        result = await orchestrator.process_job(job_id)
        
        # Validate
        assert result["status"] == "succeeded"
        assert "result" in result
        assert result["result"].get("claims_extracted", 0) > 0
    
    @pytest.mark.asyncio
    async def test_multiple_concurrent_jobs(self, orchestrator, tmp_path):
        """Test processing multiple jobs concurrently."""
        files = []
        job_ids = []
        
        # Create test files
        for i in range(5):
            test_file = tmp_path / f"test_{i}.md"
            test_file.write_text(f"Test content {i}")
            files.append(test_file)
            
            # Create jobs
            job_id = orchestrator.create_job(
                job_type="mine",
                input_id=f"episode_{i}",
                config={
                    "source": "test",
                    "file_path": str(test_file),
                    "miner_model": "openai:gpt-4o-mini",
                }
            )
            job_ids.append(job_id)
        
        # Process all jobs concurrently
        results = await asyncio.gather(*[
            orchestrator.process_job(job_id) for job_id in job_ids
        ])
        
        # Validate all succeeded
        for result in results:
            assert result["status"] == "succeeded"
    
    @pytest.mark.asyncio
    async def test_event_loop_cleanup(self, orchestrator, tmp_path):
        """Test that async clients are properly cleaned up."""
        test_file = tmp_path / "test.md"
        test_file.write_text("Test content")
        
        job_id = orchestrator.create_job(
            job_type="mine",
            input_id="cleanup_test",
            config={
                "source": "test",
                "file_path": str(test_file),
                "miner_model": "openai:gpt-4o-mini",
            }
        )
        
        # Process job - should not raise event loop errors
        result = await orchestrator.process_job(job_id)
        
        assert result["status"] == "succeeded"
        # If we get here without RuntimeError, cleanup worked
```

#### 3.2: LLM Adapter Tests

```python
# tests/core/test_llm_adapter_async.py
import pytest
import asyncio
from knowledge_system.core.llm_adapter import LLMAdapter
from knowledge_system.database import DatabaseService

class TestLLMAdapterAsync:
    """Test async LLM adapter behavior."""
    
    @pytest.mark.asyncio
    async def test_openai_async_client_cleanup(self):
        """Test that AsyncOpenAI client is properly cleaned up."""
        db = DatabaseService(":memory:")
        adapter = LLMAdapter(db_service=db)
        
        # Make a call
        result = await adapter.complete(
            provider="openai",
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Test"}]
        )
        
        assert result["content"]
        # Event loop should still be running - no cleanup errors
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test multiple concurrent LLM requests."""
        db = DatabaseService(":memory:")
        adapter = LLMAdapter(db_service=db)
        
        # Make 5 concurrent requests
        tasks = [
            adapter.complete(
                provider="openai",
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": f"Test {i}"}]
            )
            for i in range(5)
        ]
        
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 5
        for result in results:
            assert result["content"]
```

#### 3.3: GUI Integration Tests

```python
# tests/gui_comprehensive/test_system2_integration.py
import pytest
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from knowledge_system.gui.main_window import MainWindow

class TestGUISystem2Integration:
    """Test GUI integration with System2Orchestrator."""
    
    @pytest.fixture
    def app(self):
        """Create QApplication."""
        return QApplication([])
    
    @pytest.fixture
    def main_window(self, app):
        """Create main window."""
        return MainWindow()
    
    def test_summarization_tab_uses_system2(self, main_window, tmp_path):
        """Test that summarization tab uses System2Orchestrator."""
        # Get summarization tab
        summarization_tab = self._find_tab(main_window, "Summarize")
        
        # Load test file
        test_file = tmp_path / "test.md"
        test_file.write_text("Test content for summarization")
        
        # Add file to tab
        summarization_tab.file_list.addItem(str(test_file))
        
        # Configure settings
        summarization_tab.provider_combo.setCurrentText("openai")
        summarization_tab.model_combo.setCurrentText("gpt-4o-mini")
        
        # Start processing
        summarization_tab._start_processing()
        
        # Wait for completion
        self._wait_for_processing(summarization_tab, timeout=60)
        
        # Verify job was created in database
        # Verify no event loop errors
        # Verify output was generated
    
    def test_transcription_to_summarization_flow(self, main_window, tmp_path):
        """Test complete flow: transcribe → dialog → summarization."""
        # Test the fix we just implemented
        # Transcribe file → completion dialog → click summarize → verify files load
```

---

## Phase 4: Test Configuration

### pytest.ini Updates
```ini
# pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto  # Enable async tests
markers =
    gui: GUI tests (require display)
    async: Async tests
    integration: Integration tests
    unit: Unit tests
    slow: Tests that take > 10 seconds

# GUI tests need QT_QPA_PLATFORM
env =
    QT_QPA_PLATFORM=offscreen
```

### Test Organization
```
tests/
├── unit/                      # Fast unit tests
│   ├── test_database.py
│   ├── test_models.py
│   └── ...
├── core/                      # Core system tests
│   ├── test_llm_adapter_async.py
│   ├── test_system2_orchestrator.py
│   └── ...
├── gui_comprehensive/         # GUI interaction tests
│   ├── test_system2_integration.py
│   ├── test_tabs.py
│   └── ...
└── integration/               # Full integration tests
    ├── test_end_to_end.py
    └── ...
```

---

## Phase 5: Execution Plan

### Step-by-Step Removal

**CRITICAL:** Follow this exact order to prevent breaking the GUI

```bash
# 0. Read the audit first!
cat GUI_FUNCTIONALITY_PRESERVATION_AUDIT.md

# 1. Create a feature branch
git checkout -b remove-cli-add-gui-tests

# 2. Write the new GUI/System2 tests FIRST
# (implement tests from Phase 3)
pytest tests/core/test_system2_orchestrator.py
pytest tests/core/test_llm_adapter_async.py

# 3. BEFORE removing CLI: Update Monitor tab
# Edit src/knowledge_system/gui/tabs/monitor_tab.py
# Change: from ...processors.summarizer import SummarizerProcessor
# To: from ...core.system2_orchestrator import System2Orchestrator
# Update the auto-summarization logic accordingly

# 4. Test Monitor tab works with System2Orchestrator
python -m knowledge_system.gui
# Manually test Monitor tab auto-summarization

# 5. NOW safe to remove CLI code
rm -rf src/knowledge_system/commands/
rm src/knowledge_system/cli.py
rm src/knowledge_system/processors/summarizer*.py
rm src/knowledge_system/processors/moc.py  # If not used elsewhere

# 6. Update processor __init__.py
# Remove SummarizerProcessor and MOCProcessor exports

# 7. Update entry points in pyproject.toml
# Remove: knowledge-system = "knowledge_system.cli:main"
# Keep: knowledge-chipper = "knowledge_system.gui.__main__:main"

# 8. Update src/knowledge_system/__main__.py
# Change to use GUI main() instead of CLI main()

# 9. Run all tests
pytest tests/

# 10. Manual GUI testing - test EVERY tab
python -m knowledge_system.gui
# 1. Introduction - loads?
# 2. Transcribe - can transcribe?
# 3. Prompts - can view/edit?
# 4. Summarize - can summarize?
# 5. Review - can view claims?
# 6. Monitor - auto-process works?
# 7. Settings - can configure?

# 11. Commit and test
git add .
git commit -m "Remove CLI, add comprehensive GUI/System2 tests

- Updated Monitor tab to use System2Orchestrator
- Removed all CLI command modules
- Removed CLI-specific processors (SummarizerProcessor, MOCProcessor)
- Added comprehensive System2/GUI tests
- Updated entry points to GUI-only
- Verified all GUI functionality preserved (see GUI_FUNCTIONALITY_PRESERVATION_AUDIT.md)"
```

---

## Phase 6: Benefits of This Approach

### Before (Current State)
```
┌─────────────────┐    ┌─────────────────┐
│   CLI Path      │    │   GUI Path      │
│  (tested)       │    │  (untested)     │
├─────────────────┤    ├─────────────────┤
│ Summarizer      │    │ System2Orch     │
│ Processor       │    │ + async         │
│ (sync)          │    │ + threading     │
└─────────────────┘    └─────────────────┘
     ✅ Works             ❌ Issues
```

### After (Proposed State)
```
┌──────────────────────────┐
│      GUI Only            │
│    (fully tested)        │
├──────────────────────────┤
│  System2Orchestrator     │
│  + LLMAdapter            │
│  + UnifiedPipeline       │
│  + Database tracking     │
└──────────────────────────┘
        ✅ Tested
        ✅ One code path
        ✅ Feature complete
```

### Advantages
1. ✅ **One code path** - No divergence
2. ✅ **Tested architecture** - Tests match reality
3. ✅ **Less code** - Fewer files to maintain
4. ✅ **Clearer focus** - GUI-first application
5. ✅ **Better features** - System2 gives you job tracking, resume, etc.

### Trade-offs
1. ❌ No CLI for automation (but GUI has all features)
2. ❌ Need to write comprehensive async tests
3. ❌ Slightly higher learning curve (System2 vs simple processors)

---

## Estimated Effort

| Phase | Effort | Priority |
|-------|--------|----------|
| Write System2 tests | 2-3 days | HIGH |
| Write LLM adapter tests | 1 day | HIGH |
| Write GUI integration tests | 2-3 days | MEDIUM |
| Delete CLI code | 1 hour | LOW |
| Update documentation | 1 day | MEDIUM |
| Manual testing | 1 day | HIGH |

**Total: ~1-2 weeks**

---

## Alternative: Keep Minimal CLI

If you want to keep *some* CLI for scripting/automation:

```python
# Minimal CLI that uses same System2 path as GUI
@click.command()
@click.argument("file_path")
def summarize_headless(file_path):
    """Headless summarization using System2 (same as GUI)."""
    orchestrator = System2Orchestrator()
    job_id = orchestrator.create_job("mine", Path(file_path).stem, {...})
    result = asyncio.run(orchestrator.process_job(job_id))
    print(result)
```

This way:
- ✅ CLI uses **exact same code** as GUI
- ✅ Both paths are tested
- ✅ No divergence
- ✅ Automation still possible

---

## Recommendation

**Recommended approach:**

1. **Write comprehensive System2/GUI tests first** (Phases 3-4)
2. **Delete ALL CLI code** (Phase 1-2)
3. **Optionally: Add minimal headless CLI** that uses System2

This gives you:
- One tested, proven code path
- No CLI/GUI divergence
- Full GUI feature set with job tracking
- Optional automation via minimal CLI wrapper

The current setup is maintaining two completely different implementations. Better to have one excellent, tested implementation than two half-tested ones.

