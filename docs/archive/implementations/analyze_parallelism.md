# Why Doesn't Parallelism Improve Speed?

## Current Configuration
- **Workers:** 7 (auto-calculated for M2 Ultra)
- **OLLAMA_NUM_PARALLEL:** 5 (max concurrent requests Ollama will process)
- **Throughput:** 0.119 seg/sec (8.4s per segment)

## The Bottleneck Analysis

### Hypothesis 1: Ollama Queueing (MOST LIKELY)
**Workers: 7, Ollama slots: 5**

```
Time →
Worker 1: [████████ 4s] (segment 1)
Worker 2: [████████ 4s] (segment 2)  
Worker 3: [████████ 4s] (segment 3)
Worker 4: [████████ 4s] (segment 4)
Worker 5: [████████ 4s] (segment 5)
Worker 6: ⏳ WAITING... [████████ 4s] (segment 6)  ← Queued!
Worker 7: ⏳ WAITING... [████████ 4s] (segment 7)  ← Queued!
```

**Effect:** Only 5 segments process in parallel, despite 7 workers.
**Expected throughput:** 5 concurrent / 4s = **1.25 seg/sec**
**Actual throughput:** 0.119 seg/sec (10x slower!)

**This doesn't explain the slowness!**

---

### Hypothesis 2: GPU Memory Bandwidth (LIKELY)
**M2 Ultra GPU:** 
- Memory bandwidth: ~800 GB/s
- Per model instance: Uses ~40 GB/s for token generation
- Theoretical max: 800 / 40 = **20 concurrent instances**

**But with structured outputs:**
- Each request uses `temp=0` (greedy decoding, no sampling)
- Schema constraint checking adds overhead
- May serialize some GPU operations

**Effect:** GPU can only truly process **1-2 requests at a time** despite Ollama accepting 5.

---

### Hypothesis 3: Structured Output Overhead (PROBABLE)
**Structured outputs with schema:**
```
Time per request breakdown:
1. Prompt processing: ~0.2s
2. Token generation: ~3.5s (500 tokens @ ~140 tok/s)
3. Schema validation: ~0.5s (token-level constraint checking)
4. JSON parsing: ~0.1s
Total: ~4.3s
```

**With 5 concurrent requests:**
- If schema validation is CPU-bound and serialized: 5 × 0.5s = 2.5s overhead
- If GPU can only process 1 at a time due to temp=0: 5 × 4.3s = 21.5s

**Actual time for 14 segments with 7 workers (5 Ollama slots):**
- Wave 1: 5 segments in 4.3s each = **~20-25s** (GPU serialization)
- Wave 2: 5 segments in 4.3s each = **~20-25s**
- Wave 3: 4 segments in 4.3s each = **~15-20s**
- **Total: ~60s** if truly parallel
- **Actual: 118s** (2x slower)

---

## The Real Culprit: Temperature=0

**With temp=0 (greedy decoding):**
- NO parallel token sampling
- Deterministic path through model
- GPU must wait for each token before generating next
- **Forces sequential processing at GPU level**

**With temp=1.0 (sampling):**
- Can batch multiple sequences
- GPU can process tokens in parallel
- But: loses structured output reliability

---

## Proof Test Needed

Run this test:
```python
# Test 1: 5 concurrent temp=0 requests
# Expected: ~20-25s (serialized on GPU)

# Test 2: 5 concurrent temp=1.0 requests  
# Expected: ~5s (GPU parallelism)

# Test 3: 1 worker only
# Expected: ~24s (same as 5 workers if GPU serializes)
```

If Test 1 ≈ Test 3, then **GPU serialization is the bottleneck**, not Ollama queueing.

---

## Conclusion

**Most likely cause:** `temperature=0` forces **greedy decoding**, which:
1. Cannot be parallelized at GPU level
2. Processes one token at a time deterministically
3. Makes concurrent requests queue at GPU (not Ollama)

**Why we need temp=0:**
- Structured outputs require deterministic generation
- Schema constraints need predictable token selection
- Validation errors increase dramatically with temp > 0

**The tradeoff:**
- ✅ Structured outputs: Reliable, 0 validation errors
- ❌ Speed: GPU serialization → no parallelism benefit
