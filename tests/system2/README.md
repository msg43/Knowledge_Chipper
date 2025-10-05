# System 2 Test Suite

This directory contains the test suite for the System 2 implementation of Knowledge Chipper.

## Overview

The test suite covers:
- **Orchestrator Integration**: Job creation, execution, state transitions
- **Schema Validation**: JSON schema validation and automatic repair
- **LLM Adapter**: Concurrency control, rate limiting, memory management
- **Database Operations**: Job tracking, checkpoint/resume functionality

## Running Tests

### Run all System 2 tests:
```bash
python tests/system2/run_tests.py
```

### Run specific test modules:
```bash
# Test orchestrator only
pytest tests/system2/test_orchestrator.py -v

# Test schema validation only
pytest tests/system2/test_schema_validation.py -v

# Test LLM adapter only
pytest tests/system2/test_llm_adapter.py -v
```

### Run with coverage:
```bash
pytest tests/system2/ --cov=src.knowledge_system --cov-report=html
```

## Test Structure

### `fixtures.py`
Contains reusable test fixtures and sample data:
- Database fixtures (test DB, sample jobs, runs, etc.)
- Sample transcript and extraction data
- Mock LLM adapter for testing without API calls
- Schema snapshot data for validation testing

### `test_orchestrator.py`
Integration tests for the System2Orchestrator:
- Job lifecycle management
- State transitions
- Error handling and recovery
- Checkpoint/resume functionality
- Auto-process chaining

### `test_schema_validation.py`
Tests for JSON schema validation:
- Schema loading and initialization
- Valid/invalid data detection
- Automatic repair functionality
- Error message quality
- Version handling

### `test_llm_adapter.py`
Tests for the LLM adapter and concurrency control:
- Hardware tier detection
- Rate limiting with exponential backoff
- Memory monitoring and throttling
- Batch processing
- Metrics tracking

## Test Data

The test suite uses realistic sample data that follows the actual schemas:
- Miner input/output schemas
- Flagship input/output schemas
- Job and run state transitions
- LLM request/response tracking

## Continuous Integration

These tests should be run as part of the CI pipeline to ensure:
1. No regression in System 2 functionality
2. Schema compatibility is maintained
3. Performance characteristics are preserved
4. Error handling works correctly

## Adding New Tests

When adding new System 2 features:
1. Add fixtures to `fixtures.py` if needed
2. Create test cases in the appropriate test file
3. Ensure tests cover both success and failure paths
4. Include integration tests for end-to-end workflows
5. Update this README if adding new test modules
