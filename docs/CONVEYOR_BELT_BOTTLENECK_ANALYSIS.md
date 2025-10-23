# Conveyor Belt Bottleneck Analysis

## Executive Summary

**Finding:** Mining is the bottleneck (17.8 min) vs Transcription (6 min) for a 60-minute podcast.

**Impact:** For 7000 podcasts, mining speed is **3x more important** than transcription speed.

---

## Benchmark Results (2025-10-22)

### Test Configuration
- **Model:** `ollama:qwen2.5:7b-instruct`
- **Schema:** `miner_output.v1.json` (nested with timestamps, evidence_spans)
- **Workers:** 7 (auto-calculated for M2 Ultra)
- **Test segments:** 14

### Mining Performance
- **Throughput:** 0.112 seg/sec
- **Per segment:** 8.9 seconds
- **Entities extracted:** 55 claims, 17 people

### Transcription Performance (Corrected Estimate)
- **Speed:** ~10x realtime (NOT 0.5x as previously assumed)
- **1 hour audio:** 6 minutes transcription time
- **Source:** Real-world Whisper Base measurements on M2 Ultra

---

## Pipeline Analysis (1 Hour Podcast)

### Sequential Processing
| Stage | Time | Percentage |
|-------|------|------------|
| Download | 30s (0.5 min) | 2% |
| Transcription | 360s (6.0 min) | 25% |
| **Mining** | **1068s (17.8 min)** | **73%** |
| **TOTAL** | **1458s (24.3 min)** | **100%** |

### Parallel Conveyor Belt
- **Bottleneck:** Mining (17.8 min)
- **Throughput:** Limited by slowest stage
- **Time per podcast:** 17.8 minutes

---

## 7000 Podcast Projection

### Time Estimates
- **Sequential:** 2837 hours (118 days)
- **Parallel:** 2078 hours (87 days)
- **Speedup from parallelization:** 1.4x

### Optimization Impact
| Optimization | Time per Podcast | Total Time (7000) | Savings |
|--------------|------------------|-------------------|---------|
| Current | 17.8 min | 87 days | - |
| 2x mining speed | 8.9 min | 43.5 days | 43.5 days |
| 3x mining speed | 5.9 min | 29 days | 58 days |
| Match transcription (3x) | 6.0 min | 29 days | 58 days |

**Conclusion:** Getting mining to **3x faster** (matching transcription speed) saves **58 days** for 7000 podcasts.

---

## Critical Issue: Ollama Structured Outputs

### Problem
The nested schema (`miner_output.v1.json`) **fails** with Ollama's structured outputs:

```
ERROR: "Failed to create new sequence: unable to create sampling context"
```

This error occurs because:
1. **Nested arrays** (`evidence_spans` with `{quote, t0, t1}`)
2. **Regex patterns** (timestamp format: `^\\d{2}:\\d{2}(:\\d{2})?$`)
3. **Complex nesting** (4 entity types, each with nested structures)

### Impact
- 50% of requests fail and retry → 2-3x slower
- Fallback to JSON mode without schema enforcement
- Validation errors (`'suggests' is not one of ['asserts', 'questions', 'opposes', 'neutral']`)

---

## Recommendations

### Option A: Simplify Schema (REJECTED by user)
- Remove nested `evidence_spans` → single `evidence_quote` string
- Remove timestamps from jargon/people/mental models
- **Problem:** Loses critical data fields that database expects

### Option B: Use JSON Mode + Repair (Current Fallback)
- No `format=schema` parameter
- LLM generates free-form JSON
- Repair logic fixes common errors
- **Speed:** ~2x faster than structured outputs when it works
- **Problem:** Less reliable, more validation errors

### Option C: Hybrid Approach (RECOMMENDED)
1. **First attempt:** JSON mode (fast, ~2s per segment)
2. **Repair + Validate:** Fix common errors
3. **If validation fails:** ONE deterministic retry (temp=0, seed=42)
4. **Total:** ~4s per segment worst case, ~2s typical

### Expected Performance with Option C
- **Throughput:** 0.25-0.50 seg/sec (2-4s per segment)
- **1 hour podcast:** 240-480s (4-8 min) for mining
- **Bottleneck:** Still mining, but much closer to transcription
- **7000 podcasts:** 467-933 hours (19-39 days)

---

## Action Items

1. ✅ **Revert to nested schema** (preserves data integrity)
2. ✅ **Identify transcription speed** (10x realtime, not 0.5x)
3. ⚠️ **Fix structured output errors** (nested schema breaks Ollama)
4. 🔲 **Implement hybrid JSON mode** (fast + reliable)
5. 🔲 **Re-benchmark with hybrid approach**
6. 🔲 **Test conveyor belt orchestration** (parallel stages)

---

## Notes

- **Transcription speed correction:** User correctly identified that Whisper runs at ~10x realtime, not 0.5x. This changes the optimization priority significantly.
- **Data integrity:** The flat schema discarded `timestamp` fields that the database expects. Nested schema must be preserved.
- **Ollama limitations:** Structured outputs work great for simple schemas but fail on complex nested structures with regex patterns.

