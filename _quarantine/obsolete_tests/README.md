# Obsolete Test Files - Quarantined for Deletion

This directory contains test files that have been replaced by the new comprehensive test suite in `tests/comprehensive/`.

## Files Quarantined (16 files):

### GUI Comprehensive Tests (Replaced by `test_real_gui_complete.py`)
- `test_transcribe_inputs.py` - Transcription input tests
- `test_summarize_inputs.py` - Summarization input tests  
- `test_workflows_real.py` - Real workflow tests
- `test_all_workflows_automated.py` - Automated workflow tests
- `test_smoke_automated.py` - Smoke tests
- `test_transcribe_workflows.py` - Transcription workflow tests

### Integration Tests (Replaced by `test_real_integration_complete.py`)
- `test_unified_real_content.py` - Unified real content tests
- `test_system2_orchestrator.py` - System2 orchestrator integration tests

### System2 Tests (Replaced by `test_real_system2_complete.py`)
- `test_mining_full.py` - Full mining tests
- `test_unified_hce_operations.py` - Unified HCE operations tests
- `test_orchestrator.py` - Orchestrator tests
- `test_orchestrator_integration.py` - Orchestrator integration tests
- `test_llm_adapter_real.py` - LLM adapter real tests

### Root Level Tests (Replaced by comprehensive suite)
- `test_comprehensive.py` - Comprehensive tests
- `test_unified_pipeline.py` - Unified pipeline tests
- `test_stub_complete.py` - Stub tests

## Replacement Test Suite

All functionality from these files has been consolidated into:

1. **`tests/comprehensive/test_real_gui_complete.py`** - GUI tests with real data
2. **`tests/comprehensive/test_real_integration_complete.py`** - Integration tests with real data  
3. **`tests/comprehensive/test_real_system2_complete.py`** - System2 tests with real data

## Safe to Delete

These files can be safely deleted after confirming the new comprehensive test suite works correctly.

Quarantined on: October 24, 2024
Reason: Consolidated into non-overlapping comprehensive test suite
