# Batch Processing Integration Strategy

**Date:** October 27, 2025

## Current State

**Problem:** `IntelligentProcessingCoordinator` exists but is **NOT integrated** with the current UnifiedHCEPipeline.

**Files:**
- `/Users/matthewgreer/Projects/Knowledge_Chipper/src/knowledge_system/core/intelligent_processing_coordinator.py` - Vestigial batch coordinator
- `/Users/matthewgreer/Projects/Knowledge_Chipper/src/knowledge_system/core/batch_processor.py` - Legacy batch processor

## Recommended Approach

### ✅ Use System2Orchestrator for ALL Processing

**Why:**
- System2 already handles single-file processing with full checkpoint support
- UnifiedHCEPipeline is only accessible through System2
- Job tracking and progress callbacks are built into System2
- No need to maintain parallel code paths

### Implementation Strategy

#### Option 1: Simple Sequential Batch (Recommended)

```python
class System2BatchProcessor:
    """Batch processor using System2Orchestrator for consistent pipeline."""
    
    def __init__(self, db_service: DatabaseService):
        self.orchestrator = System2Orchestrator(db_service)
    
    async def process_batch(
        self,
        urls: list[str],
        config: dict,
        progress_callback: Callable | None = None
    ) -> dict:
        """Process multiple URLs using same pipeline as single files."""
        batch_id = f"batch_{int(time.time())}"
        
        jobs = []
        for i, url in enumerate(urls):
            # Create mining job for each URL
            job_id = self.orchestrator.create_job(
                job_type="mine",
                input_id=url,
                config=config
            )
            jobs.append((i, job_id, url))
        
        # Process all jobs sequentially (respects parallelization settings)
        results = []
        for i, job_id, url in jobs:
            try:
                result = await self.orchestrator.process_job(
                    job_id,
                    resume_from_checkpoint=True
                )
                results.append({
                    "url": url,
                    "status": "success",
                    "result": result
                })
                
                if progress_callback:
                    progress_callback(
                        "batch_progress",
                        int((i + 1) / len(jobs) * 100),
                        f"Completed {i+1}/{len(jobs)}"
                    )
            except Exception as e:
                results.append({
                    "url": url,
                    "status": "failed",
                    "error": str(e)
                })
        
        return {
            "batch_id": batch_id,
            "total": len(jobs),
            "succeeded": len([r for r in results if r["status"] == "success"]),
            "failed": len([r for r in results if r["status"] == "failed"]),
            "results": results
        }
```

#### Option 2: Parallel Batch (Advanced)

For processing multiple URLs in parallel (not recommended initially):

```python
async def process_batch_parallel(
    self,
    urls: list[str],
    config: dict,
    max_concurrent: int = 3
) -> dict:
    """Process multiple URLs in parallel with concurrency limit."""
    import asyncio
    
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_with_limit(url, job_id):
        async with semaphore:
            return await self.orchestrator.process_job(job_id)
    
    # Create all jobs
    job_ids = [
        self.orchestrator.create_job("mine", url, config)
        for url in urls
    ]
    
    # Process in parallel with limit
    results = await asyncio.gather(*[
        process_with_limit(url, job_id)
        for url, job_id in zip(urls, job_ids)
    ], return_exceptions=True)
    
    return {"results": results}
```

## Cleanup Tasks

### ✅ Remove Vestigial Code

1. **Delete or refactor** `intelligent_processing_coordinator.py`
   - Remove from `System2Orchestrator.__init__()` if instantiated there
   - Or clearly document it's not used

2. **Update** `batch_processor.py`
   - Refactor to use System2Orchestrator instead of custom pipeline
   - Or delete if not used

### ✅ Integration Points

**GUI Integration:**
- Add batch mode to existing tabs (YouTube download tab, etc.)
- Use System2BatchProcessor instead of IntelligentProcessingCoordinator

**CLI Integration:**
- Add batch command that uses System2BatchProcessor
- Leverage existing checkpoint/resume functionality

## Benefits of System2-Based Batch Processing

1. **Single Code Path** - Same pipeline for batch and single files
2. **Checkpoint Support** - Can resume interrupted batch jobs
3. **Progress Tracking** - Built-in job tracking database
4. **Consistent Results** - No dual implementations to maintain
5. **Parallelization** - UnifiedHCEPipeline already handles parallel segment processing

## Migration Path

1. ✅ Create `System2BatchProcessor` class
2. ✅ Test with small batch (3-5 URLs)
3. ✅ Update GUI to use new batch processor
4. ✅ Delete `IntelligentProcessingCoordinator`
5. ✅ Update documentation

## Status

**Current:** Vestigial code exists but not integrated  
**Recommended:** Implement System2BatchProcessor (Option 1)  
**Timeline:** Low priority - batch processing not critical for current workflow
