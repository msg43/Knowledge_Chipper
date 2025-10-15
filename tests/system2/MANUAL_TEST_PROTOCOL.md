# System 2 Manual Testing Protocol

This document provides step-by-step instructions for manually verifying the System 2 implementation.

## Prerequisites

Before starting the tests, ensure:

1. **Ollama is running** with the required model
   ```bash
   # Check if Ollama is running
   curl http://localhost:11434/api/tags
   
   # Pull the model if needed
   ollama pull qwen2.5:7b-instruct
   ```

2. **Database is initialized**
   - The knowledge_system.db file exists with System 2 tables

3. **Test transcript available**
   - Create or use an existing transcript file for testing

## Test Suite

### Test 1: Verify Ollama Integration

**Objective:** Confirm the LLM adapter can communicate with Ollama.

**Steps:**
1. Run the manual test script:
   ```bash
   python scripts/test_ollama_integration.py
   ```

**Expected Results:**
- ✓ Ollama is running
- ✓ qwen2.5:7b-instruct model is available
- ✓ All 5 tests pass:
  - Simple completion
  - JSON generation
  - Retry logic
  - Hardware tier detection
  - Concurrent requests

**Pass Criteria:** All tests show ✓ marks

---

### Test 2: Database Tracking Verification

**Objective:** Verify LLM requests and responses are tracked in the database.

**Steps:**
1. Run the LLM adapter tests:
   ```bash
   pytest tests/system2/test_llm_adapter_real.py::TestLLMAdapterReal::test_request_tracking -v -s
   ```

2. Inspect the database:
   ```bash
   sqlite3 knowledge_system.db
   ```

3. Query for tracked requests:
   ```sql
   SELECT COUNT(*) FROM llm_request;
   SELECT COUNT(*) FROM llm_response;
   SELECT * FROM llm_request LIMIT 5;
   SELECT * FROM llm_response LIMIT 5;
   ```

**Expected Results:**
- At least 1 request in `llm_request` table
- At least 1 response in `llm_response` table
- Requests have: provider, model, temperature, request_json
- Responses have: completion_tokens, latency_ms, response_json

**Pass Criteria:** Requests and responses are properly linked by request_id

---

### Test 3: Mining End-to-End

**Objective:** Test the complete mining workflow from transcript to database.

**Steps:**
1. Create a test transcript file (`test_transcript.md`):
   ```markdown
   # Test Transcript
   
   AI has transformed many industries.
   
   Machine learning requires large datasets.
   
   Geoffrey Hinton is a pioneer in deep learning.
   
   Neural networks are inspired by biological systems.
   ```

2. Run the mining test:
   ```bash
   pytest tests/system2/test_mining_full.py::TestMiningWithOllama::test_mine_simple_transcript -v -s
   ```

3. Verify in database:
   ```sql
   SELECT * FROM episodes WHERE episode_id = 'episode_test_mine';
   SELECT COUNT(*) FROM claims WHERE episode_id = 'episode_test_mine';
   SELECT COUNT(*) FROM jargon WHERE episode_id = 'episode_test_mine';
   SELECT COUNT(*) FROM people WHERE episode_id = 'episode_test_mine';
   SELECT COUNT(*) FROM concepts WHERE episode_id = 'episode_test_mine';
   ```

**Expected Results:**
- Episode is created in database
- Mining extracts claims, jargon, people, concepts (counts may vary)
- Job completes with status 'succeeded'

**Pass Criteria:** At least one episode record exists with some extracted entities

---

### Test 4: Checkpoint and Resume

**Objective:** Verify the system can save checkpoints and resume interrupted jobs.

**Steps:**
1. Create a longer transcript (20+ lines)

2. Start a mining job that will save checkpoints:
   ```bash
   pytest tests/system2/test_mining_full.py::TestMiningWithOllama::test_checkpoint_save_and_resume -v -s
   ```

3. Check database for checkpoint data:
   ```sql
   SELECT checkpoint_json FROM job_run WHERE checkpoint_json IS NOT NULL;
   ```

**Expected Results:**
- Checkpoints are saved every 5 segments
- Checkpoint JSON contains `last_segment` and `partial_results`
- Job can load checkpoint and resume

**Pass Criteria:** Checkpoint data is persisted and retrievable

---

### Test 5: GUI Integration

**Objective:** Verify the GUI can process files through System 2.

**Steps:**
1. Launch the GUI:
   ```bash
   python -m knowledge_system.gui.main_window_pyqt6
   ```

2. Navigate to the Summarization tab

3. Add the test transcript file

4. Configure settings:
   - Provider: ollama
   - Model: qwen2.5:7b-instruct

5. Click "Start Processing"

**Expected Results:**
- File appears in the queue
- Progress bar updates during processing
- Status shows "Processing" then "Complete"
- HCE analytics are displayed (claims, people, concepts counts)
- No error messages appear

**Pass Criteria:** File processes successfully and shows extracted entity counts

---

### Test 6: Job and JobRun Tables

**Objective:** Verify job orchestration is properly tracked.

**Steps:**
1. After running Test 3 or Test 5, inspect the database:
   ```sql
   SELECT * FROM job ORDER BY created_at DESC LIMIT 5;
   SELECT * FROM job_run ORDER BY created_at DESC LIMIT 5;
   ```

2. Verify relationships:
   ```sql
   SELECT 
       j.job_id,
       j.job_type,
       jr.status,
       jr.metrics_json
   FROM job j
   JOIN job_run jr ON j.job_id = jr.job_id
   ORDER BY j.created_at DESC
   LIMIT 5;
   ```

**Expected Results:**
- Job records have: job_id, job_type, input_id, config_json
- JobRun records have: run_id, status, started_at, completed_at
- Status transitions: queued → running → succeeded
- Metrics JSON contains progress information

**Pass Criteria:** Jobs and runs are properly linked and tracked

---

### Test 7: Error Handling

**Objective:** Verify system handles errors gracefully.

**Steps:**
1. Test with invalid file path:
   ```python
   from src.knowledge_system.core.system2_orchestrator import System2Orchestrator
   from src.knowledge_system.database import DatabaseService
   import asyncio
   
   async def test_error():
       orch = System2Orchestrator(DatabaseService())
       job_id = orch.create_job("mine", "test_ep", {"file_path": "/nonexistent.md"})
       try:
           result = await orch.process_job(job_id)
           print(f"Result: {result}")
       except Exception as e:
           print(f"✓ Error caught: {e}")
   
   asyncio.run(test_error())
   ```

2. Check database for error record:
   ```sql
   SELECT error_code, error_message FROM job_run WHERE status = 'failed' ORDER BY created_at DESC LIMIT 1;
   ```

**Expected Results:**
- Exception is raised
- JobRun status is set to 'failed'
- error_code and error_message are populated
- System doesn't crash

**Pass Criteria:** Errors are caught, logged, and recorded in database

---

### Test 8: Full Pipeline

**Objective:** Test complete transcribe → mine → flagship pipeline.

**Steps:**
1. Create a pipeline test:
   ```python
   from src.knowledge_system.core.system2_orchestrator import System2Orchestrator
   from src.knowledge_system.database import DatabaseService
   import asyncio
   
   async def test_pipeline():
       orch = System2Orchestrator(DatabaseService())
       job_id = orch.create_job(
           "pipeline",
           "test_video",
           {
               "file_path": "test_transcript.md",
               "stages": ["transcribe", "mine", "flagship"],
               "miner_model": "ollama:qwen2.5:7b-instruct"
           }
       )
       result = await orch.process_job(job_id)
       print(f"Pipeline result: {result}")
       return result
   
   result = asyncio.run(test_pipeline())
   ```

2. Verify all stages completed:
   ```sql
   SELECT * FROM job WHERE job_type IN ('transcribe', 'mine', 'flagship') ORDER BY created_at DESC LIMIT 3;
   ```

**Expected Results:**
- All three stages complete successfully
- Each stage creates its own job record
- Pipeline result shows all stages in completed_stages list
- Final status is 'succeeded'

**Pass Criteria:** All stages complete and data is available in database

---

### Test 9: Performance Check

**Objective:** Verify performance meets acceptable thresholds.

**Steps:**
1. Process a medium-sized transcript (100 lines)

2. Record metrics:
   - Total time to complete
   - Time per segment
   - Memory usage during processing

3. Check database metrics:
   ```sql
   SELECT 
       metrics_json,
       (julianday(completed_at) - julianday(started_at)) * 86400 as duration_seconds
   FROM job_run
   WHERE status = 'succeeded'
   ORDER BY created_at DESC
   LIMIT 1;
   ```

**Expected Results:**
- Processing completes in reasonable time (< 5 seconds per segment)
- Memory usage stays below 70% threshold
- No memory leaks (memory returns to baseline after processing)

**Pass Criteria:** Performance is acceptable for user experience

---

### Test 10: Concurrent Jobs

**Objective:** Verify multiple jobs can run concurrently with proper resource management.

**Steps:**
1. Start 3 jobs simultaneously:
   ```python
   import asyncio
   from src.knowledge_system.core.system2_orchestrator import System2Orchestrator
   from src.knowledge_system.database import DatabaseService
   
   async def test_concurrent():
       orch = System2Orchestrator(DatabaseService())
       
       # Create 3 jobs
       job_ids = []
       for i in range(3):
           job_id = orch.create_job(
               "mine",
               f"episode_concurrent_{i}",
               {"file_path": "test_transcript.md", "miner_model": "ollama:qwen2.5:7b-instruct"}
           )
           job_ids.append(job_id)
       
       # Process concurrently
       results = await asyncio.gather(*[orch.process_job(jid) for jid in job_ids])
       print(f"All jobs completed: {len(results)}")
       return results
   
   results = asyncio.run(test_concurrent())
   ```

2. Verify all completed:
   ```sql
   SELECT COUNT(*) FROM job WHERE job_type = 'mine' AND input_id LIKE 'episode_concurrent_%';
   ```

**Expected Results:**
- All 3 jobs complete successfully
- Jobs respect concurrency limits (based on hardware tier)
- No deadlocks or race conditions
- Database consistency maintained

**Pass Criteria:** All jobs complete without errors

---

## Troubleshooting

### Issue: Ollama not responding

**Solution:**
```bash
# Check if Ollama is running
ps aux | grep ollama

# Restart Ollama
pkill ollama
ollama serve &

# Verify
curl http://localhost:11434/api/tags
```

### Issue: Database locked errors

**Solution:**
```bash
# Close all connections to the database
pkill -f knowledge_system

# Restart the application
```

### Issue: LLM responses are invalid JSON

**Solution:**
- This can happen with JSON mode
- Check the LLM prompt includes clear JSON instructions
- Verify the model supports structured output
- Review error logs for parse errors

### Issue: Slow performance

**Solution:**
- Check system resources (CPU, memory, disk)
- Verify Ollama is using GPU acceleration if available
- Reduce batch sizes or concurrency limits
- Consider using a smaller/faster model for testing

---

## Success Criteria Summary

All tests pass when:

- [ ] Ollama integration works (Test 1)
- [ ] Database tracking is functional (Test 2)
- [ ] Mining extracts entities (Test 3)
- [ ] Checkpoints save and resume (Test 4)
- [ ] GUI processes files successfully (Test 5)
- [ ] Job orchestration is tracked (Test 6)
- [ ] Errors are handled gracefully (Test 7)
- [ ] Full pipeline completes (Test 8)
- [ ] Performance is acceptable (Test 9)
- [ ] Concurrent jobs work (Test 10)

---

## Notes

- Run tests in the order listed for best results
- Each test can be run independently
- Keep test transcripts short (< 100 lines) for faster iteration
- Review logs in `logs/knowledge_system.log` for debugging
- Database can be reset by deleting `knowledge_system.db` (backup first!)

---

## Reporting Issues

If any test fails:

1. Note which test failed
2. Capture error messages from console and logs
3. Check database state with provided SQL queries
4. Review the rollback plan in the implementation guide
5. Report with:
   - Test number and name
   - Error message
   - Database query results
   - Log excerpts

