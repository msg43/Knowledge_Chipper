# System 2 Tests

This directory contains tests for the System 2 architecture implementation.

## Test Structure

### Unit Tests (Fast, No External Dependencies)
- `test_unified_hce_operations.py` - Unified HCE storage via System2Orchestrator
- Tests run with in-memory database
- No external LLM required

### Integration Tests (Require Ollama)
- `test_llm_adapter_real.py` - Real Ollama API calls
- `test_mining_full.py` - Complete mining workflow
- `test_orchestrator_integration.py` - Full orchestrator tests

### Manual Tests
- `MANUAL_TEST_PROTOCOL.md` - Step-by-step verification guide
- Use for comprehensive system validation

## Prerequisites

### For Integration Tests

1. **Install Ollama**
   ```bash
   # macOS
   brew install ollama
   
   # Or download from https://ollama.ai
   ```

2. **Start Ollama**
   ```bash
   ollama serve
   ```

3. **Pull Required Model**
   ```bash
   ollama pull qwen2.5:7b-instruct
   ```

4. **Verify Ollama is Running**
   ```bash
   curl http://localhost:11434/api/tags
   ```

## Running Tests

### Run All Unit Tests
```bash
pytest tests/system2/test_unified_hce_operations.py -v
```

### Run Integration Tests (Requires Ollama)
```bash
# Run all integration tests
pytest tests/system2/ -v -m integration

# Run specific test file
pytest tests/system2/test_llm_adapter_real.py -v -s

# Run specific test
pytest tests/system2/test_mining_full.py::TestMiningWithOllama::test_mine_simple_transcript -v -s
```

### Run Manual Test Script
```bash
python scripts/test_ollama_integration.py
```

## Test Markers

Tests use pytest markers:
- `@pytest.mark.integration` - Requires Ollama running
- `@pytest.mark.asyncio` - Async test
- `@pytest.mark.e2e` - End-to-end test

## Test Options

### Verbose Output
```bash
pytest tests/system2/ -v -s
```

### Show Print Statements
```bash
pytest tests/system2/ -s
```

### Stop on First Failure
```bash
pytest tests/system2/ -x
```

### Run Only Fast Tests (Skip Integration)
```bash
pytest tests/system2/ -v -m "not integration"
```

## Troubleshooting

### Ollama Not Running
```
Error: Ollama connection failed
```

**Solution:**
```bash
# Check if Ollama is running
ps aux | grep ollama

# Start Ollama
ollama serve &

# Verify
curl http://localhost:11434/api/tags
```

### Model Not Found
```
Error: qwen2.5:7b-instruct model not found
```

**Solution:**
```bash
ollama pull qwen2.5:7b-instruct
```

### Database Locked
```
Error: database is locked
```

**Solution:**
```bash
# Close all connections
pkill -f knowledge_system

# Or delete test database (for tests only)
rm -f test_knowledge.db
```

### Tests Running Slowly
Integration tests with real LLM calls can take time:
- Each segment mining: ~1-3 seconds
- Multiple segments: multiply accordingly
- Use `-v -s` flags to see progress

## Test Coverage

Run with coverage:
```bash
pytest tests/system2/ --cov=src/knowledge_system/core --cov=src/knowledge_system/database/hce_operations --cov-report=html
```

View coverage report:
```bash
open htmlcov/index.html
```

## Continuous Integration

For CI/CD pipelines:

1. **Without Ollama (Unit Tests Only)**
   ```bash
   pytest tests/system2/test_hce_operations.py -v
   ```

2. **With Ollama (Full Suite)**
   ```bash
   # Ensure Ollama is running in CI
   ollama serve &
   sleep 5
   ollama pull qwen2.5:7b-instruct
   
   # Run all tests
   pytest tests/system2/ -v
   ```

## Test Data

Test files use:
- In-memory SQLite databases (auto-cleanup)
- Temporary files for transcripts (auto-cleanup with pytest fixtures)
- Sample test data in `tests/fixtures/`

## Writing New Tests

### Template for Integration Test

```python
import pytest
from src.knowledge_system.core.system2_orchestrator import System2Orchestrator
from src.knowledge_system.database import DatabaseService

@pytest.fixture
def test_db_service():
    """Create test database."""
    return DatabaseService(":memory:")

@pytest.mark.integration
@pytest.mark.asyncio
async def test_my_feature(test_db_service):
    """Test my feature."""
    orchestrator = System2Orchestrator(test_db_service)
    
    # Your test code here
    result = await orchestrator.process_job(job_id)
    
    assert result["status"] == "succeeded"
```

## Best Practices

1. **Use Fixtures** - Reuse database and file fixtures
2. **Mark Integration Tests** - Use `@pytest.mark.integration`
3. **Clean Up** - Fixtures handle cleanup automatically
4. **Assertions** - Be specific about expected outcomes
5. **Logging** - Use `-s` flag to see detailed output during development

## Support

For issues or questions:
1. Check `MANUAL_TEST_PROTOCOL.md` for detailed verification steps
2. Review test output with `-v -s` flags
3. Check `logs/knowledge_system.log` for system logs
4. Inspect database with SQLite browser

## Related Documentation

- `MANUAL_TEST_PROTOCOL.md` - Manual testing procedures
- `../../SYSTEM2_IMPLEMENTATION_GUIDE.md` - Architecture overview
- `../../docs/guides/` - System guides and documentation
