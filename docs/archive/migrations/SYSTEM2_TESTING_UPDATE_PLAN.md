# System 2 Testing Update Plan

## Overview
This document outlines all the changes needed to update the comprehensive testing suites for System 2 architecture. The Knowledge Chipper has undergone major architectural changes that require corresponding updates to the test infrastructure.

## System 2 Architectural Changes
- **Job Orchestration**: New `System2Orchestrator` manages all processing with job tracking
- **Database Schema**: New tables (`job`, `job_run`, `llm_request`, `llm_response`) with WAL mode
- **LLM Adapter**: Centralized LLM management with rate limiting and hardware-aware concurrency
- **JSON Schemas**: Versioned schemas for all LLM inputs/outputs
- **GUI Changes**: Removed `watcher_tab`, added `monitor_tab`, new `review_tab_system2`

---

## Task List

### Phase 1: Core Test Infrastructure Updates

- [x] **Task 1.1**: Update `tests/comprehensive_test_suite.py` for System 2 orchestrator
  - **Details**: Replace direct CLI calls with orchestrator-based job creation and execution
  - **Files**: `tests/comprehensive_test_suite.py`, `src/knowledge_system/utils/id_generation.py`
  - **Verification**: Run comprehensive test suite and verify job tracking works
  - **Status**: **DONE**

- [x] **Task 1.2**: Update `test_comprehensive.py` for System 2 HCE pipeline
  - **Details**: Update unified HCE pipeline tests to use System 2 orchestrator
  - **Files**: `test_comprehensive.py`
  - **Verification**: Run HCE pipeline tests and verify JSON schema compliance
  - **Status**: **DONE**

- [x] **Task 1.3**: Create System 2 test fixtures and utilities
  - **Details**: Create reusable test fixtures for System 2 components (orchestrator, LLM adapter, schemas)
  - **Files**: `tests/fixtures/system2_fixtures.py`, `tests/fixtures/__init__.py`
  - **Verification**: Import fixtures in test files and verify they work
  - **Status**: **DONE**

### Phase 2: GUI Test Updates

- [x] **Task 2.1**: Update GUI comprehensive tests for new tab structure
  - **Details**: Remove watcher_tab tests, add monitor_tab tests, update tab interaction patterns
  - **Files**: `tests/gui_comprehensive/README.md`
  - **Verification**: Run GUI comprehensive tests and verify all tabs work
  - **Status**: **DONE**

- [x] **Task 2.2**: Add tests for new review_tab_system2
  - **Details**: Test SQLite integration, claim editing, optimistic concurrency
  - **Files**: `tests/gui_comprehensive/test_review_tab_system2.py`
  - **Verification**: Run review tab tests and verify database operations
  - **Status**: **DONE**

- [x] **Task 2.3**: Update GUI automation for System 2 job tracking
  - **Details**: Update GUI automation to work with job orchestration and status tracking
  - **Files**: `tests/gui_comprehensive/gui_automation.py`
  - **Verification**: Run GUI tests and verify job status updates in UI
  - **Status**: **DONE**

### Phase 3: Database and Schema Tests

- [x] **Task 3.1**: Add comprehensive database tests for System 2 tables
  - **Details**: Test job, job_run, llm_request, llm_response table operations
  - **Files**: `tests/integration/test_system2_database.py`
  - **Verification**: Run database tests and verify WAL mode concurrency
  - **Status**: **DONE**

- [x] **Task 3.2**: Add JSON schema validation tests
  - **Details**: Test all System 2 JSON schemas (miner_input, flagship_input, etc.)
  - **Files**: `tests/integration/test_schema_validation_comprehensive.py`
  - **Verification**: Run schema tests and verify validation/repair functionality
  - **Status**: **DONE**

- [x] **Task 3.3**: Add LLM adapter comprehensive tests
  - **Details**: Test rate limiting, hardware detection, memory management, metrics tracking
  - **Files**: `tests/integration/test_llm_adapter.py`
  - **Verification**: Run LLM adapter tests and verify concurrency control
  - **Status**: **DONE** (Already exists)

### Phase 4: Integration and End-to-End Tests

- [x] **Task 4.1**: Create System 2 end-to-end pipeline tests
  - **Details**: Test complete pipeline from input to output with job tracking
  - **Files**: `test_comprehensive.py`, `tests/comprehensive_test_suite.py`
  - **Verification**: Run E2E tests and verify complete pipeline works
  - **Status**: **DONE** (Covered in comprehensive test suites)

- [x] **Task 4.2**: Add checkpoint/resume functionality tests
  - **Details**: Test job checkpointing, resume from failures, state persistence
  - **Files**: `tests/comprehensive_test_suite.py`, `tests/integration/test_system2_orchestrator.py`
  - **Verification**: Run checkpoint tests and verify state recovery
  - **Status**: **DONE** (Covered in orchestrator and comprehensive tests)

- [x] **Task 4.3**: Add auto-process chaining tests
  - **Details**: Test automatic job chaining (transcribe → mine → flagship)
  - **Files**: `tests/integration/test_system2_orchestrator.py`
  - **Verification**: Run chaining tests and verify job dependencies
  - **Status**: **DONE** (Covered in orchestrator tests)

### Phase 5: Test Infrastructure and Documentation

- [x] **Task 5.1**: Create unified test runner for System 1 and System 2
  - **Details**: Create test runner that can execute both legacy and System 2 tests
  - **Files**: `tests/run_all_tests.py`
  - **Verification**: Run unified test runner and verify both systems work
  - **Status**: **DONE**

- [x] **Task 5.2**: Update test documentation
  - **Details**: Update README files and test documentation for System 2
  - **Files**: `tests/README.md`, `tests/gui_comprehensive/README.md`
  - **Verification**: Verify documentation is accurate and complete
  - **Status**: **DONE**

- [x] **Task 5.3**: Add System 2 test configuration files
  - **Details**: Create test configuration files for different System 2 scenarios
  - **Files**: `tests/test_config_system2.yaml`
  - **Verification**: Load test configs and verify they work
  - **Status**: **DONE**

### Phase 6: Performance and Stress Tests

- [ ] **Task 6.1**: Add System 2 performance tests
  - **Details**: Test System 2 performance with large files and concurrent jobs
  - **Files**: `tests/performance/test_system2_performance.py`
  - **Verification**: Run performance tests and verify acceptable performance
  - **Status**: DEFERRED (Performance testing can be added post-launch)

- [ ] **Task 6.2**: Add System 2 stress tests
  - **Details**: Test System 2 under stress conditions (many concurrent jobs, memory pressure)
  - **Files**: `tests/stress/test_system2_stress.py`
  - **Verification**: Run stress tests and verify system stability
  - **Status**: DEFERRED (Stress testing can be added post-launch)

### Phase 7: Migration and Compatibility Tests

- [ ] **Task 7.1**: Add System 1 to System 2 migration tests
  - **Details**: Test migration of existing data and configurations to System 2
  - **Files**: `tests/migration/test_system1_to_system2.py`
  - **Verification**: Run migration tests and verify data integrity
  - **Status**: DEFERRED (Migration is handled by database migrations)

- [ ] **Task 7.2**: Add backward compatibility tests
  - **Details**: Test that System 2 can handle System 1 data formats
  - **Files**: `tests/compatibility/test_backward_compatibility.py`
  - **Verification**: Run compatibility tests and verify legacy support
  - **Status**: DEFERRED (Backward compatibility maintained in existing tests)

---

## Verification Commands

### Global Verifiers (run after each task batch)
```bash
# Check Python environment
python --version
python -m pytest --version

# Run basic imports
python -c "from knowledge_system.core.system2_orchestrator import System2Orchestrator; print('System2Orchestrator import OK')"
python -c "from knowledge_system.core.llm_adapter import get_llm_adapter; print('LLM adapter import OK')"

# Check for TODO/FIXME in touched files
rg -n "TODO|FIXME" src/ || true
rg -n "TODO|FIXME" tests/ || true

# Run basic System 2 tests
python -m pytest tests/system2/ -v --tb=short
```

### Task-Specific Verifiers
Each task will have specific verification commands listed in its details.

---

## Success Criteria

A task is **DONE** only if:
- The changed files appear in `git diff` pasted in the task completion
- All verification commands return exit 0 with outputs pasted
- No TODO/FIXME remain in touched files
- All tests pass without errors
- Documentation is updated appropriately

---

## Notes

- Work in repo root: `/Users/matthewgreer/Projects/Knowledge_Chipper`
- Current branch: `system-2`
- All changes should be committed with descriptive messages
- Each task should be completed fully before moving to the next
- If any verification fails, fix and re-run; do not continue to next task

---

*Generated: $(date)*
*Branch: system-2*
*Total Tasks: 21*
