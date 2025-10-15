# HCE (Hybrid Claim Extractor) Troubleshooting Guide

## Problem Summary

The HCE system is successfully processing segments and running parallel workers, but extracted claims are not appearing in the final summary output files. The system shows "Extracted 0 claims using HCE analysis" despite all infrastructure components working correctly.

## Current Status: ✅ Infrastructure Fixed, ❓ Claims Not Appearing

### ✅ Successfully Fixed Issues:
1. **Missing OllamaManager.generate() method** - Added to `src/knowledge_system/utils/ollama_manager.py`
2. **Missing DatabaseService.get_latest_summary() method** - Added to `src/knowledge_system/database/service.py`
3. **Transcript parsing issues** - Fixed segment extraction in `src/knowledge_system/processors/summarizer.py`
4. **Minimal HCE prompt** - Replaced with robust prompt in `src/knowledge_system/processors/hce/prompts/miner.txt`
5. **Parallel processing timeout** - Fixed 1-second timeout issue in `src/knowledge_system/processors/hce/parallel_processor.py`

### ❓ Current Issue: Claims Not Appearing in Output

**Symptoms:**
- HCE pipeline runs without "futures unfinished" errors
- Parallel processing completes successfully (8 workers, 38 segments)
- Summary files show "Extracted 0 claims using HCE analysis"
- Process completes with "✓ Summarized" message

## Debugging Steps Taken

### 1. Infrastructure Verification
**Command:** `knowledge-system process "output/What's happening with GOLD right now will make you crazy.md" --summarize --no-transcribe --output output/ --no-moc`

**Results:**
- ✅ Transcript parsing: "Parsing transcript with 39 speaker segments" → "Created 38 segments for HCE processing"
- ✅ Parallel processing: "Using parallel processing for 38 segments" with 8 workers
- ✅ No timeout errors: Process completes without "8 futures unfinished" error
- ❌ Claims extraction: Still shows 0 claims in final output

### 2. Component Testing
**Individual components verified working:**
- ✅ OllamaManager.generate() method exists and functional
- ✅ DatabaseService.get_latest_summary() method exists and functional
- ✅ HCE prompt is comprehensive and robust
- ✅ Parallel processing timeout increased to 60 seconds

## Possible Root Causes

### 1. **Claims Processing Pipeline Issue**
**Location:** `src/knowledge_system/processors/hce/`
**Symptoms:** Claims extracted but not saved/formatted correctly
**Check:**
- Claims extraction working but results not propagated to summary
- Database saving issues
- Result formatting problems

### 2. **Ollama Service Issues**
**Location:** `src/knowledge_system/utils/ollama_manager.py`
**Symptoms:** API calls failing silently
**Check:**
- Ollama service running: `ollama list`
- Model availability: Check if required models are installed
- API response validation: Claims might be extracted but malformed JSON

### 3. **Result Integration Issues**
**Location:** `src/knowledge_system/processors/summarizer.py`
**Symptoms:** Claims extracted but not integrated into final summary
**Check:**
- HCE results not being merged into summary content
- File writing issues
- Template rendering problems

### 4. **Database Transaction Issues**
**Location:** `src/knowledge_system/database/service.py`
**Symptoms:** Claims extracted but not persisted
**Check:**
- Database write failures
- Transaction rollbacks
- Schema issues

## Diagnostic Commands

### Check Ollama Service
```bash
# Verify Ollama is running
ollama list

# Test Ollama API directly
curl -X POST http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen2.5:7b", "prompt": "Test prompt", "stream": false}'
```

### Check Database State
```bash
# Check if claims are being written to database
sqlite3 "$(find ~ -name "knowledge_system.db" 2>/dev/null | head -1)" \
  "SELECT COUNT(*) FROM summaries WHERE video_id LIKE '%gold%';"
```

### Check Log Files
```bash
# Look for detailed HCE processing logs
grep -r "HCE\|claim\|miner" logs/ 2>/dev/null | tail -20
```

### Manual HCE Component Test
```python
# Test individual HCE components
cd /Users/matthewgreer/Projects/Knowledge_Chipper
source venv/bin/activate
python -c "
from knowledge_system.processors.hce.miner import ClaimMiner
from knowledge_system.processors.hce.data_models import Segment

# Test claim extraction on a sample segment
miner = ClaimMiner()
test_segment = Segment(
    episode_id='test',
    segment_id='test_001',
    speaker='Test Speaker',
    t0='000000',
    t1='000030',
    text='Gold prices are rising due to dollar weakness and inflation concerns.'
)

result = miner.extract_claims([test_segment])
print(f'Extracted {len(result)} claims')
for claim in result:
    print(f'- {claim.claim_text}')
"
```

## Key Files to Investigate

### 1. **Main Processing Pipeline**
- `src/knowledge_system/processors/summarizer.py` (lines 700-900)
  - Look for HCE result integration
  - Check `process()` method claim handling
  - Verify summary formatting includes claims

### 2. **HCE Parallel Processing**
- `src/knowledge_system/processors/hce/parallel_processor.py` (lines 100-200)
  - Check if results are properly collected from futures
  - Verify result aggregation logic
  - Look for silent failures in result processing

### 3. **Claim Extraction**
- `src/knowledge_system/processors/hce/miner.py`
  - Verify `extract_claims()` method returns valid results
  - Check JSON parsing of LLM responses
  - Look for error handling that might suppress results

### 4. **Database Integration**
- `src/knowledge_system/database/service.py`
  - Check `save_summary()` method includes HCE data
  - Verify database schema supports claims
  - Look for transaction issues

### 5. **Output Formatting**
- `src/knowledge_system/processors/summarizer.py` (summary formatting section)
  - Check if claims are included in markdown output
  - Verify template rendering includes HCE sections
  - Look for conditional logic that might skip claims

## Next Debugging Steps

### 1. **Add Detailed Logging**
Add debug prints to track claim flow:
```python
# In summarizer.py, after HCE processing
logger.info(f"HCE processing returned {len(hce_results)} results")
for i, result in enumerate(hce_results):
    logger.info(f"HCE result {i}: {len(result.claims) if hasattr(result, 'claims') else 'No claims attr'} claims")
```

### 2. **Test Individual Components**
Run the manual HCE component test above to isolate where the failure occurs.

### 3. **Check Process Flow**
Add breakpoints or logging at each step:
1. Segment creation → HCE input
2. HCE processing → Raw results
3. Result aggregation → Formatted claims
4. Database saving → Persistence
5. Summary generation → Final output

### 4. **Verify Model Availability**
Ensure the required Ollama model is installed and functional:
```bash
ollama pull qwen2.5:7b  # or whatever model is configured
```

## Expected Behavior

When working correctly, the logs should show:
1. "Parsing transcript with X speaker segments"
2. "Created Y segments for HCE processing"
3. "Using parallel processing for Y segments"
4. "Parallel processing completed: Y/Y successful"
5. **Missing:** "Extracted N claims using HCE analysis" (where N > 0)

## Resolution Strategy

1. **Immediate:** Run manual component test to isolate failure point
2. **Short-term:** Add detailed logging to track claim flow through pipeline
3. **Medium-term:** Verify all integration points between components
4. **Long-term:** Add comprehensive error handling and validation

---

**Last Updated:** September 30, 2025  
**Status:** Infrastructure fixed, investigating claims integration  
**Priority:** High - Core functionality not working despite successful processing
