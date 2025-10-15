# System 2 - Next Steps Guide

## Immediate Actions (Before Testing)

### 1. Ensure Ollama is Running

```bash
# Check if Ollama is running
ps aux | grep ollama

# If not running, start it
ollama serve &

# Verify it's accessible
curl http://localhost:11434/api/tags
```

### 2. Pull Required Model

```bash
# Pull the model if not already present
ollama pull qwen2.5:7b-instruct

# Verify
ollama list | grep qwen2.5
```

---

## Quick Verification (5 minutes)

### Step 1: Run Manual Test Script

This will verify Ollama integration is working:

```bash
python3 scripts/test_ollama_integration.py
```

**Expected Output:**
```
====================================================
Ollama Integration Test Suite
====================================================

[Pre-check] Verifying Ollama is running...
✓ Ollama is running
  Available models: qwen2.5:7b-instruct, ...

[Test 1] Simple completion...
✓ Response: Hello! ...
  Tokens: 120

[Test 2] JSON generation...
✓ JSON Response: {"status": "ok"}
  Parsed successfully: ['status']

...

✓ All tests passed!
```

If this passes, System 2 is ready to use! ✅

---

### Step 2: Run Unit Tests (No Ollama Required)

```bash
pytest tests/system2/test_hce_operations.py -v
```

**Expected:** All 16 tests pass

---

### Step 3: Run One Integration Test

```bash
pytest tests/system2/test_llm_adapter_real.py::TestLLMAdapterReal::test_basic_completion -v -s
```

**Expected:** Test passes with real Ollama response

---

## Full Test Suite (30-60 minutes)

### Run All Tests

```bash
# Run all System 2 tests
pytest tests/system2/ -v

# Or with detailed output
pytest tests/system2/ -v -s
```

### Expected Results:
- Unit tests: ~16 pass quickly (< 1 minute)
- Integration tests: ~33 pass (may take 10-30 minutes due to LLM calls)
- **Total: ~49 tests should pass**

---

## Testing with GUI (10 minutes)

### Step 1: Prepare Test File

Create `test_transcript.md`:
```markdown
# Test Transcript

AI is transforming healthcare through predictive analytics.

Machine learning models require extensive training data.

Geoffrey Hinton pioneered deep learning research.

Neural networks are computational models inspired by the brain.
```

### Step 2: Launch GUI

```bash
python3 -m knowledge_system.gui.main_window_pyqt6
```

### Step 3: Process File

1. Go to **Summarization** tab
2. Click **"Add Files"** → select `test_transcript.md`
3. Settings:
   - Provider: **ollama**
   - Model: **qwen2.5:7b-instruct**
4. Click **"Start Processing"**

### Step 4: Verify Results

**Expected:**
- Progress bar updates
- Status shows "Processing..." then "Complete"
- HCE analytics panel shows:
  - Claims extracted: X
  - People extracted: X
  - Concepts extracted: X

### Step 5: Check Database

```bash
sqlite3 knowledge_system.db

SELECT * FROM job ORDER BY created_at DESC LIMIT 1;
SELECT * FROM llm_request ORDER BY created_at DESC LIMIT 5;
SELECT * FROM claims ORDER BY created_at DESC LIMIT 5;
```

**Expected:**
- Job record exists with type 'mine'
- LLM requests are tracked
- Claims are stored in database

---

## Troubleshooting

### Issue: "Ollama connection failed"

**Check:**
```bash
curl http://localhost:11434/api/tags
```

**Fix:**
```bash
ollama serve &
sleep 2
ollama pull qwen2.5:7b-instruct
```

---

### Issue: "Model not found"

**Fix:**
```bash
ollama pull qwen2.5:7b-instruct
```

---

### Issue: Tests are slow

**Normal:** Integration tests with real LLM are slow (2-5 seconds per segment)

**Speed up:**
```bash
# Run only fast unit tests
pytest tests/system2/test_hce_operations.py -v
```

---

### Issue: Import errors

**Fix:**
```bash
# Ensure you're in project root
cd /Users/matthewgreer/Projects/Knowledge_Chipper

# Install in development mode if needed
pip install -e .
```

---

## Understanding the Results

### What Success Looks Like

After processing a transcript through System 2, you should see:

**In Database:**
- `job` table: Record with job_type='mine'
- `job_run` table: Record with status='succeeded'
- `llm_request` table: Multiple requests (one per segment)
- `llm_response` table: Corresponding responses
- `episodes` table: Episode record
- `claims` table: Extracted claims
- `jargon` table: Extracted terminology
- `people` table: Extracted people mentions
- `concepts` table: Extracted mental models

**In GUI:**
- File status: "Complete"
- Analytics show non-zero counts
- No error messages

**In Logs:**
- `logs/knowledge_system.log` shows:
  - "Created job..."
  - "Processing mining for..."
  - "Stored mining results for..."
  - "Updated job run status to succeeded"

---

## Performance Expectations

### Processing Times

**Per segment:**
- LLM call: 1-3 seconds
- Parsing: < 10ms
- Database write: < 100ms
- **Total: ~1-3 seconds per segment**

**10-line transcript:**
- Segments: ~7 (after filtering headers)
- Total time: ~7-21 seconds
- Plus overhead: ~5 seconds
- **Expected: 12-26 seconds total**

**100-line transcript:**
- Segments: ~70
- Total time: ~2-5 minutes
- **Expected: 3-6 minutes total**

### Resource Usage

- **CPU:** Moderate (Ollama runs LLM locally)
- **Memory:** ~2-4 GB (for qwen2.5:7b model)
- **Disk:** Minimal (database writes are small)
- **Network:** None (all local)

---

## What to Do If Something Fails

### 1. Check Prerequisites

```bash
# Ollama running?
ps aux | grep ollama

# Model available?
ollama list | grep qwen2.5

# Database exists?
ls -lh knowledge_system.db
```

### 2. Run Diagnostic Test

```bash
python3 scripts/test_ollama_integration.py
```

If this fails, fix Ollama before proceeding.

### 3. Check Logs

```bash
tail -f logs/knowledge_system.log
```

Look for error messages or stack traces.

### 4. Inspect Database

```bash
sqlite3 knowledge_system.db

-- Check for failed jobs
SELECT * FROM job_run WHERE status = 'failed' ORDER BY created_at DESC LIMIT 5;

-- Check error messages
SELECT error_code, error_message FROM job_run WHERE error_message IS NOT NULL LIMIT 5;
```

### 5. Follow Manual Test Protocol

See `tests/system2/MANUAL_TEST_PROTOCOL.md` for step-by-step verification.

---

## Integration with Existing System

System 2 is **backwards compatible**. The GUI currently uses System 2 for job orchestration, but the underlying HCE pipeline works the same way.

**You can:**
- ✅ Process files through GUI (uses System2Orchestrator)
- ✅ Use CLI commands (can be updated to use System2Orchestrator)
- ✅ Access data in database (same HCE tables)
- ✅ Export to Obsidian (same workflow)

**System 2 adds:**
- Job tracking
- Checkpoint/resume capability
- LLM request/response logging
- Better error handling

---

## Documentation

### For Users
- This file (SYSTEM2_NEXT_STEPS.md)
- `SYSTEM2_IMPLEMENTATION_SUMMARY.md` - What was built
- `tests/system2/MANUAL_TEST_PROTOCOL.md` - Detailed testing

### For Developers
- `SYSTEM2_IMPLEMENTATION_GUIDE.md` - Architecture overview
- `tests/system2/README.md` - How to run tests
- Code comments in modified files

---

## Success Checklist

Before considering System 2 "done", verify:

- [ ] `python3 scripts/test_ollama_integration.py` passes
- [ ] `pytest tests/system2/test_hce_operations.py -v` passes (all 16 tests)
- [ ] `pytest tests/system2/test_llm_adapter_real.py -v` passes (at least connectivity test)
- [ ] GUI can process a test file successfully
- [ ] Database has `job`, `job_run`, `llm_request`, `llm_response` tables populated
- [ ] Claims appear in `claims` table after processing

**If all checkboxes are checked, System 2 is fully operational!** ✅

---

## Getting Help

1. **Check logs:** `logs/knowledge_system.log`
2. **Run diagnostics:** `python3 scripts/test_ollama_integration.py`
3. **Follow manual protocol:** `tests/system2/MANUAL_TEST_PROTOCOL.md`
4. **Review implementation:** `SYSTEM2_IMPLEMENTATION_SUMMARY.md`

---

## What's Next (Optional)

System 2 is complete for MVP use. Future enhancements could include:

1. **Full Flagship Evaluation** - Implement claim scoring logic
2. **Real Transcription** - Add whisper.cpp integration
3. **Additional LLM Providers** - OpenAI, Anthropic, Google
4. **Upload Functionality** - Cloud storage integration
5. **Performance Optimization** - Batch processing, parallelization

But for now, **System 2 is ready to use with Ollama!** 🎉
