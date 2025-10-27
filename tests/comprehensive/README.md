# Comprehensive Real Testing Suite

This directory contains the consolidated, non-overlapping test suite for real GUI + real data testing.

## Overview

This replaces **15+ redundant test files** with **3 focused test files** that provide complete coverage of all real functionality:

### Test Files

1. **`test_real_gui_complete.py`** - Real GUI workflows with actual data sources
2. **`test_real_integration_complete.py`** - Real file processing and System2 orchestration  
3. **`test_real_system2_complete.py`** - Real System2 job tracking and database operations

### What This Replaces

**GUI Tests (5 files → 1 file):**
- `tests/gui_comprehensive/test_transcribe_inputs.py`
- `tests/gui_comprehensive/test_summarize_inputs.py`
- `tests/gui_comprehensive/test_workflows_real.py`
- `tests/gui_comprehensive/test_all_workflows_automated.py`
- `tests/gui_comprehensive/test_smoke_automated.py`

**Integration Tests (3 files → 1 file):**
- `tests/integration/test_unified_real_content.py`
- `tests/system2/test_mining_full.py`
- `tests/system2/test_unified_hce_operations.py`

**System2 Tests (4 files → 1 file):**
- `tests/system2/test_orchestrator.py`
- `tests/system2/test_orchestrator_integration.py`
- `tests/system2/test_llm_adapter_real.py`
- `tests/integration/test_system2_orchestrator.py`

**Root Tests (2 files → 0 files):**
- `test_comprehensive.py`
- `test_unified_pipeline.py`

## Coverage

### Real GUI Testing (`test_real_gui_complete.py`)
- **Transcription**: YouTube URL, playlist, RSS feed, local audio/video, batch processing
- **Summarization**: MD, PDF, TXT, DOCX, HTML, JSON, RTF formats
- **Workflows**: Complete transcribe → summarize pipeline
- **Tab Navigation**: All 7 tabs load and switch correctly
- **Error Handling**: Invalid inputs, cancellation, edge cases
- **Real Processing**: Actual Ollama integration, real file processing
- **Database Validation**: SQLite persistence verification
- **Output Validation**: Markdown file generation with YAML frontmatter

### Real Integration Testing (`test_real_integration_complete.py`)
- **File Processing**: Ken Rogoff RTF, Bannon MD, Wolf RTF
- **System2 Mining**: Real Ollama integration with sample transcripts
- **Checkpoint/Resume**: Job interruption and recovery
- **Database Storage**: HCE tables (claims, evidence_spans, people, concepts)
- **Context Quotes**: Population verification
- **Performance Metrics**: Timing and parallel processing
- **Database Validation**: Evidence spans, claim tiers, relations, categories

### Real System2 Testing (`test_real_system2_complete.py`)
- **Job Creation**: Real database operations
- **Job Execution**: Complete processing workflows
- **Status Tracking**: Real-time status updates
- **LLM Tracking**: Request/response logging
- **Error Handling**: Real error scenarios
- **Database Operations**: CRUD operations, foreign keys, WAL mode
- **Singleton Behavior**: Orchestrator instance management

## Usage

### Run All Tests
```bash
python -m pytest tests/comprehensive/ -v
```

### Run Specific Test Suites
```bash
# GUI tests only
python -m pytest tests/comprehensive/test_real_gui_complete.py -v

# Integration tests only  
python -m pytest tests/comprehensive/test_real_integration_complete.py -v

# System2 tests only
python -m pytest tests/comprehensive/test_real_system2_complete.py -v
```

### Run Specific Test Classes
```bash
# Transcription tests only
python -m pytest tests/comprehensive/test_real_gui_complete.py::TestRealGUITranscription -v

# Mining tests only
python -m pytest tests/comprehensive/test_real_integration_complete.py::TestRealSystem2Mining -v

# Job creation tests only
python -m pytest tests/comprehensive/test_real_system2_complete.py::TestRealJobCreation -v
```

## Requirements

### For GUI Tests
- Ollama running with `qwen2.5:7b-instruct` model
- Real test files available:
  - `fixtures/sample_files/test_speech.mp3`
  - `fixtures/sample_files/short_video.webm`
  - `fixtures/sample_files/sample_transcript.md`
  - `KenRogoff_Transcript.rtf`
  - `KenRogoff_Transcript.pdf`
  - `KenRogoff_Transcript.docx`

### For Integration Tests
- Ollama running with `qwen2.5:7b-instruct` model
- Real content files:
  - `KenRogoff_Transcript.rtf`
  - `Steve Bannon Silicon Valley Is Turning Us Into 'Digital Serfs'.md`
  - `Maxine_Wolf_Deposition_Text.rtf`

### For System2 Tests
- Database service available
- System2 models initialized

## Benefits

### Reduced Redundancy
- **Before**: 15+ test files with overlapping functionality
- **After**: 3 focused test files with clear separation of concerns
- **Reduction**: ~80% fewer test files

### Improved Maintainability
- Single source of truth for each test type
- Shared utilities in `utils.py`
- Consistent patterns across all tests

### Better Organization
- Clear separation: GUI, Integration, System2
- Logical grouping of related functionality
- Easy to find and modify specific tests

### Comprehensive Coverage
- All real functionality tested
- No gaps in coverage
- Real data sources and real outputs

## Test Structure

```
tests/comprehensive/
├── __init__.py                    # Main test runner
├── test_real_gui_complete.py      # GUI workflows
├── test_real_integration_complete.py  # File processing
├── test_real_system2_complete.py  # System2 orchestration
├── utils.py                       # Shared utilities
└── README.md                      # This file
```

## Migration Guide

### From Old Tests
1. **GUI tests**: Use `test_real_gui_complete.py` instead of multiple GUI test files
2. **Integration tests**: Use `test_real_integration_complete.py` instead of scattered integration tests
3. **System2 tests**: Use `test_real_system2_complete.py` instead of multiple System2 test files

### Test Discovery
The `__init__.py` file imports all test classes for easy discovery:
```python
from .test_real_gui_complete import *
from .test_real_integration_complete import *
from .test_real_system2_complete import *
```

### Shared Utilities
Common functionality is in `utils.py`:
- `create_sandbox()` - Test environment setup
- `switch_to_tab()` - GUI tab navigation
- `wait_for_completion()` - Processing completion
- `DBValidator` - Database validation
- `check_ollama_running()` - Ollama status check

## Future Enhancements

### Potential Additions
- **Performance benchmarks**: Timing comparisons
- **Stress testing**: Large file processing
- **Concurrency testing**: Multiple simultaneous operations
- **Error recovery**: Network failures, timeouts
- **Configuration testing**: Different model combinations

### Maintenance
- **Regular updates**: Keep test data current
- **Performance monitoring**: Track test execution times
- **Coverage analysis**: Ensure no functionality gaps
- **Documentation**: Keep README updated
