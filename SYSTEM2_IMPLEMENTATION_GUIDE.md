# System 2 Architecture - Complete Implementation Guide

## Executive Summary

System 2 is an architectural upgrade designed to add enterprise-grade features to the Knowledge Chipper:
- Job tracking and resumability
- Centralized LLM management with rate limiting
- Request/response auditing
- Hardware-aware concurrency

**Current Status:** ~30% implemented. The infrastructure exists but the core processing logic is not connected.

**Estimated Effort:** 2-3 weeks full-time development

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [What's Already Built](#whats-already-built)
3. [What's Missing](#whats-missing)
4. [Implementation Tasks](#implementation-tasks)
5. [Testing Strategy](#testing-strategy)
6. [Migration Path](#migration-path)

---

## Architecture Overview

### System 2 Components

```
┌─────────────────────────────────────────────────────────────┐
│                         GUI / CLI                            │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   System2Orchestrator                        │
│  • Job tracking (job/job_run tables)                        │
│  • Checkpoint persistence                                    │
│  • Auto-process chaining                                     │
└──────────────┬───────────────────────────────┬──────────────┘
               │                               │
               ▼                               ▼
┌──────────────────────────┐    ┌─────────────────────────────┐
│      LLMAdapter          │    │   Processing Pipelines      │
│  • Rate limiting         │    │  • HCE Pipeline             │
│  • Request tracking      │    │  • Transcription            │
│  • Cost estimation       │    │  • Summarization            │
│  • Hardware-aware        │    │  • Upload                   │
└──────────────────────────┘    └─────────────────────────────┘
               │                               │
               ▼                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    SQLite Database                           │
│  • job, job_run (tracking)                                  │
│  • llm_request, llm_response (auditing)                     │
│  • episodes, claims, etc. (HCE data)                        │
└─────────────────────────────────────────────────────────────┘
```

### Design Philosophy

System 2 is a **wrapper layer** that adds observability and reliability without changing the core processing logic. Think of it as middleware that:
- Tracks what's happening (job records)
- Enables recovery (checkpoints)
- Manages resources (LLM rate limiting)
- Provides audit trails (request/response logging)

---

## What's Already Built

### ✅ Database Schema (100% Complete)

**Location:** `src/knowledge_system/database/system2_models.py`

```python
class Job(Base):
    """Top-level job records"""
    job_id = Column(String(100), primary_key=True)
    job_type = Column(String(50))  # 'transcribe', 'mine', 'flagship', 'upload', 'pipeline'
    input_id = Column(String(100))
    config_json = Column(JSONEncodedType)
    auto_process = Column(String(5))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

class JobRun(Base):
    """Individual execution attempts"""
    run_id = Column(String(100), primary_key=True)
    job_id = Column(String(100), ForeignKey('job.job_id'))
    attempt_number = Column(Integer)
    status = Column(String(20))  # 'queued', 'running', 'succeeded', 'failed'
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    checkpoint_json = Column(JSONEncodedType)
    metrics_json = Column(JSONEncodedType)
    error_code = Column(String(50))
    error_message = Column(Text)

class LLMRequest(Base):
    """All LLM API calls"""
    request_id = Column(String(100), primary_key=True)
    job_run_id = Column(String(100))
    provider = Column(String(50))
    model = Column(String(100))
    request_payload = Column(JSONEncodedType)
    created_at = Column(DateTime)

class LLMResponse(Base):
    """LLM responses with metrics"""
    response_id = Column(String(100), primary_key=True)
    request_id = Column(String(100), ForeignKey('llm_request.request_id'))
    response_payload = Column(JSONEncodedType)
    response_time_ms = Column(Integer)
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
    estimated_cost = Column(Float)
    created_at = Column(DateTime)
```

**Status:** Tables exist, migrations applied, ready to use.

---

### ✅ System2Orchestrator Infrastructure (60% Complete)

**Location:** `src/knowledge_system/core/system2_orchestrator.py`

**What Works:**
```python
class System2Orchestrator:
    def create_job(self, job_type, input_id, config, auto_process):
        """✅ Creates job record in database"""
        
    def create_job_run(self, job_id, checkpoint):
        """✅ Creates job run record"""
        
    def update_job_run_status(self, run_id, status, error_code, error_message, metrics):
        """✅ Updates job run status"""
        
    def save_checkpoint(self, run_id, checkpoint_data):
        """✅ Saves checkpoint to database"""
        
    def load_checkpoint(self, run_id):
        """✅ Loads checkpoint from database"""
        
    def track_llm_request(self, provider, model, payload):
        """✅ Tracks LLM request in database"""
        
    def track_llm_response(self, request_id, response_payload, response_time_ms):
        """✅ Tracks LLM response in database"""
```

**What's Missing:**
```python
    async def _process_transcribe(self, video_id, config, checkpoint, run_id):
        """❌ TODO: Implement transcription with checkpoint support"""
        return {"status": "completed", "output_id": f"episode_{video_id}"}
        
    async def _process_mine(self, episode_id, config, checkpoint, run_id):
        """❌ TODO: Implement mining with checkpoint support"""
        return {"status": "completed", "output_id": episode_id}
        
    async def _process_flagship(self, episode_id, config, checkpoint, run_id):
        """❌ TODO: Implement flagship with checkpoint support"""
        return {"status": "completed", "output_id": episode_id}
        
    async def _process_upload(self, episode_id, config, checkpoint, run_id):
        """❌ TODO: Implement upload with checkpoint support"""
        return {"status": "completed", "output_id": episode_id}
        
    async def _process_pipeline(self, video_id, config, checkpoint, run_id):
        """❌ TODO: Implement full pipeline with checkpoint support"""
        return {"status": "completed", "output_id": f"episode_{video_id}"}
```

---

### ⚠️ LLMAdapter (40% Complete)

**Location:** `src/knowledge_system/core/llm_adapter.py`

**What Works:**
```python
class LLMAdapter:
    def __init__(self, db_service, hardware_specs):
        """✅ Hardware detection and tier assignment"""
        self.hardware_tier = self._determine_hardware_tier(specs)
        self.max_concurrent = self.CONCURRENCY_LIMITS[self.hardware_tier]
        
    async def complete(self, provider, model, messages, temperature, max_tokens):
        """✅ Rate limiting infrastructure"""
        await rate_limiter.acquire()
        await self.memory_throttler.check_and_wait()
        async with self.semaphore:
            # ... but then calls mock API
            
    def _estimate_cost(self, provider, model, response):
        """✅ Cost estimation logic"""
```

**What's Missing:**
```python
    async def _call_provider(self, provider, model, messages, **kwargs):
        """❌ PLACEHOLDER - Returns mock responses instead of real API calls"""
        # This is a placeholder - in reality, this would call the actual provider APIs
        # For now, return a mock response
        logger.info(f"Calling {provider} API with model {model}")
        await asyncio.sleep(0.5)  # Simulate delay
        
        mock_content = "This is a mock LLM response for System 2 testing."
        return {
            "content": mock_content,
            "usage": {"prompt_tokens": 100, "completion_tokens": 20},
            "model": model,
            "provider": provider,
        }
```

**Needs:**
- OpenAI API integration
- Anthropic API integration
- Google Gemini API integration
- Ollama API integration
- Proper error handling for each provider
- Retry logic with exponential backoff

---

### ✅ System2Logger (100% Complete)

**Location:** `src/knowledge_system/core/system2_logger.py`

**Status:** Fully implemented and working. Provides structured logging with correlation IDs.

---

## What's Missing

### 1. System2Orchestrator Processing Methods (Critical)

**Priority:** HIGH  
**Estimated Effort:** 3-5 days  
**Complexity:** Medium

#### Task 1.1: Implement `_process_mine()`

**Purpose:** Extract claims, jargon, people, and mental models from transcripts.

**Current Code:**
```python
async def _process_mine(
    self,
    episode_id: str,
    config: dict[str, Any],
    checkpoint: dict[str, Any] | None,
    run_id: str,
) -> dict[str, Any]:
    """Process mining job."""
    # TODO: Implement mining with checkpoint support
    logger.info(f"Processing mining for {episode_id}")
    return {"status": "completed", "output_id": episode_id}
```

**Required Implementation:**
```python
async def _process_mine(
    self,
    episode_id: str,
    config: dict[str, Any],
    checkpoint: dict[str, Any] | None,
    run_id: str,
) -> dict[str, Any]:
    """Process mining job with checkpoint support."""
    try:
        # 1. Load transcript from database or file
        file_path = config.get("file_path")
        if not file_path:
            raise KnowledgeSystemError(
                f"No file_path in config for episode {episode_id}",
                ErrorCode.INVALID_INPUT
            )
        
        # 2. Parse transcript into segments
        from ..processors.hce.types import EpisodeBundle
        from ..processors.hce.unified_miner import mine_episode_unified
        
        # Load and parse the transcript
        transcript_text = Path(file_path).read_text()
        segments = self._parse_transcript_to_segments(transcript_text, episode_id)
        
        episode = EpisodeBundle(
            episode_id=episode_id,
            segments=segments,
            metadata=config.get("metadata", {})
        )
        
        # 3. Check for checkpoint and resume if available
        start_segment = 0
        if checkpoint and "last_segment" in checkpoint:
            start_segment = checkpoint["last_segment"] + 1
            logger.info(f"Resuming from segment {start_segment}")
        
        # 4. Get miner model from config
        miner_model = config.get("miner_model", "openai:gpt-4o-mini")
        
        # 5. Run mining with progress tracking
        miner_outputs = []
        total_segments = len(segments)
        
        for i in range(start_segment, total_segments):
            # Mine this segment
            segment_output = await self._mine_single_segment(
                segments[i], miner_model, run_id
            )
            miner_outputs.append(segment_output)
            
            # Save checkpoint every 10 segments
            if i % 10 == 0:
                self.save_checkpoint(run_id, {
                    "last_segment": i,
                    "partial_results": len(miner_outputs)
                })
            
            # Update metrics
            self.update_job_run_status(
                run_id, 
                "running",
                metrics={
                    "segments_processed": i + 1,
                    "total_segments": total_segments,
                    "progress_percent": ((i + 1) / total_segments) * 100
                }
            )
        
        # 6. Store results in database
        from ..database.hce_operations import store_mining_results
        store_mining_results(self.db_service, episode_id, miner_outputs)
        
        # 7. Return success with metrics
        return {
            "status": "succeeded",
            "output_id": episode_id,
            "result": {
                "claims_extracted": sum(len(o.claims) for o in miner_outputs),
                "jargon_extracted": sum(len(o.jargon) for o in miner_outputs),
                "people_extracted": sum(len(o.people) for o in miner_outputs),
                "mental_models_extracted": sum(len(o.mental_models) for o in miner_outputs),
            }
        }
        
    except Exception as e:
        logger.error(f"Mining failed for {episode_id}: {e}")
        raise KnowledgeSystemError(
            f"Mining failed: {str(e)}",
            ErrorCode.PROCESSING_FAILED
        )

async def _mine_single_segment(
    self,
    segment: Segment,
    miner_model: str,
    run_id: str
) -> UnifiedMinerOutput:
    """Mine a single segment with LLM tracking."""
    from ..processors.hce.unified_miner import UnifiedMiner
    from ..processors.hce.model_uri_parser import parse_model_uri
    
    # Parse model URI
    provider, model = parse_model_uri(miner_model)
    
    # Create LLM instance that uses System2 adapter
    from ..processors.hce.models.llm_system2 import System2LLM
    llm = System2LLM(provider=provider, model=model)
    llm.set_job_run_id(run_id)  # Connect to this job run
    
    # Create miner and process segment
    prompt_path = Path(__file__).parent.parent / "processors" / "hce" / "prompts" / "unified_miner.txt"
    miner = UnifiedMiner(llm, prompt_path)
    
    return miner.mine_segment(segment)

def _parse_transcript_to_segments(
    self,
    transcript_text: str,
    episode_id: str
) -> list[Segment]:
    """Parse transcript text into segments."""
    from ..processors.hce.types import Segment
    
    # Parse the transcript format (assumes markdown with timestamps)
    segments = []
    lines = transcript_text.split('\n')
    
    current_segment = None
    for line in lines:
        # Look for timestamp markers like [00:01:23]
        if line.startswith('[') and ']' in line:
            if current_segment:
                segments.append(current_segment)
            
            # Extract timestamp and text
            timestamp_end = line.index(']')
            timestamp = line[1:timestamp_end]
            text = line[timestamp_end+1:].strip()
            
            current_segment = Segment(
                segment_id=f"seg_{len(segments):04d}",
                episode_id=episode_id,
                t0=timestamp,
                t1=timestamp,  # Will be updated with next segment
                speaker="Unknown",
                text=text
            )
        elif current_segment:
            # Continue current segment text
            current_segment.text += " " + line.strip()
    
    if current_segment:
        segments.append(current_segment)
    
    return segments
```

**Files to Create/Modify:**
- `src/knowledge_system/core/system2_orchestrator.py` - Add implementation
- `src/knowledge_system/database/hce_operations.py` - Add `store_mining_results()`
- Test file: `tests/test_system2_mining.py`

**Dependencies:**
- HCE pipeline (already exists)
- Model URI parser (already exists)
- Database operations (needs new helper functions)

---

#### Task 1.2: Implement `_process_flagship()`

**Purpose:** Evaluate and rank extracted claims.

**Estimated Effort:** 2 days

**Required Implementation:**
```python
async def _process_flagship(
    self,
    episode_id: str,
    config: dict[str, Any],
    checkpoint: dict[str, Any] | None,
    run_id: str,
) -> dict[str, Any]:
    """Process flagship evaluation with checkpoint support."""
    try:
        # 1. Load mining results from database
        from ..database.hce_operations import load_mining_results
        miner_outputs = load_mining_results(self.db_service, episode_id)
        
        if not miner_outputs:
            raise KnowledgeSystemError(
                f"No mining results found for episode {episode_id}",
                ErrorCode.PROCESSING_FAILED
            )
        
        # 2. Generate content summary
        content_summary = self._generate_content_summary(miner_outputs)
        
        # 3. Get flagship model from config
        flagship_model = config.get("flagship_judge_model", "openai:gpt-4o-mini")
        
        # 4. Run flagship evaluation
        from ..processors.hce.flagship_evaluator import evaluate_claims_flagship
        evaluation_output = evaluate_claims_flagship(
            content_summary,
            miner_outputs,
            flagship_model
        )
        
        # 5. Store results in database
        from ..database.hce_operations import store_flagship_results
        store_flagship_results(self.db_service, episode_id, evaluation_output)
        
        # 6. Return success with metrics
        return {
            "status": "succeeded",
            "output_id": episode_id,
            "result": {
                "claims_evaluated": evaluation_output.total_claims_processed,
                "claims_accepted": evaluation_output.claims_accepted,
                "claims_rejected": evaluation_output.claims_rejected,
            }
        }
        
    except Exception as e:
        logger.error(f"Flagship evaluation failed for {episode_id}: {e}")
        raise KnowledgeSystemError(
            f"Flagship evaluation failed: {str(e)}",
            ErrorCode.PROCESSING_FAILED
        )
```

---

#### Task 1.3: Implement `_process_transcribe()`

**Purpose:** Transcribe audio/video to text.

**Estimated Effort:** 2 days

**Required Implementation:**
```python
async def _process_transcribe(
    self,
    video_id: str,
    config: dict[str, Any],
    checkpoint: dict[str, Any] | None,
    run_id: str,
) -> dict[str, Any]:
    """Process transcription with checkpoint support."""
    try:
        # 1. Get file path from config
        file_path = config.get("file_path")
        if not file_path:
            raise KnowledgeSystemError(
                f"No file_path in config for video {video_id}",
                ErrorCode.INVALID_INPUT
            )
        
        # 2. Check for existing transcript in checkpoint
        if checkpoint and "transcript_path" in checkpoint:
            transcript_path = checkpoint["transcript_path"]
            logger.info(f"Using cached transcript from {transcript_path}")
        else:
            # 3. Run transcription
            from ..processors.transcription import transcribe_audio
            
            transcript_result = await transcribe_audio(
                file_path,
                model=config.get("whisper_model", "base"),
                language=config.get("language", "en"),
                run_id=run_id
            )
            
            # 4. Save transcript to file
            output_dir = Path(config.get("output_dir", "output/transcripts"))
            output_dir.mkdir(parents=True, exist_ok=True)
            transcript_path = output_dir / f"{video_id}.md"
            transcript_path.write_text(transcript_result["text"])
            
            # 5. Save checkpoint with transcript path
            self.save_checkpoint(run_id, {
                "transcript_path": str(transcript_path),
                "duration": transcript_result.get("duration", 0)
            })
        
        # 6. Store transcript in database
        from ..database.operations import store_transcript
        episode_id = f"episode_{video_id}"
        store_transcript(self.db_service, episode_id, transcript_path)
        
        # 7. Return success
        return {
            "status": "succeeded",
            "output_id": episode_id,
            "result": {
                "transcript_path": str(transcript_path),
                "video_id": video_id,
                "episode_id": episode_id
            }
        }
        
    except Exception as e:
        logger.error(f"Transcription failed for {video_id}: {e}")
        raise KnowledgeSystemError(
            f"Transcription failed: {str(e)}",
            ErrorCode.PROCESSING_FAILED
        )
```

---

#### Task 1.4: Implement `_process_upload()`

**Purpose:** Upload processed results to cloud storage.

**Estimated Effort:** 1 day

**Required Implementation:**
```python
async def _process_upload(
    self,
    episode_id: str,
    config: dict[str, Any],
    checkpoint: dict[str, Any] | None,
    run_id: str,
) -> dict[str, Any]:
    """Process upload with checkpoint support."""
    try:
        # 1. Get upload configuration
        upload_config = config.get("upload_config", {})
        provider = upload_config.get("provider", "s3")
        bucket = upload_config.get("bucket")
        
        if not bucket:
            raise KnowledgeSystemError(
                "No bucket specified in upload config",
                ErrorCode.INVALID_INPUT
            )
        
        # 2. Gather files to upload
        files_to_upload = []
        
        # Transcript
        transcript_path = config.get("transcript_path")
        if transcript_path:
            files_to_upload.append(("transcript", transcript_path))
        
        # Mining results (export from database)
        mining_export = self._export_mining_results(episode_id)
        if mining_export:
            files_to_upload.append(("mining", mining_export))
        
        # 3. Check checkpoint for already uploaded files
        uploaded_files = []
        if checkpoint and "uploaded_files" in checkpoint:
            uploaded_files = checkpoint["uploaded_files"]
        
        # 4. Upload files
        from ..cloud.uploader import CloudUploader
        uploader = CloudUploader(provider, bucket)
        
        for file_type, file_path in files_to_upload:
            if file_path in uploaded_files:
                logger.info(f"Skipping already uploaded {file_type}: {file_path}")
                continue
            
            # Upload file
            remote_path = f"{episode_id}/{file_type}/{Path(file_path).name}"
            await uploader.upload(file_path, remote_path)
            
            # Update checkpoint
            uploaded_files.append(file_path)
            self.save_checkpoint(run_id, {"uploaded_files": uploaded_files})
        
        # 5. Return success
        return {
            "status": "succeeded",
            "output_id": episode_id,
            "result": {
                "uploaded_files": len(uploaded_files),
                "bucket": bucket,
                "provider": provider
            }
        }
        
    except Exception as e:
        logger.error(f"Upload failed for {episode_id}: {e}")
        raise KnowledgeSystemError(
            f"Upload failed: {str(e)}",
            ErrorCode.PROCESSING_FAILED
        )
```

---

#### Task 1.5: Implement `_process_pipeline()`

**Purpose:** Run complete end-to-end pipeline (transcribe → mine → flagship → upload).

**Estimated Effort:** 1 day

**Required Implementation:**
```python
async def _process_pipeline(
    self,
    video_id: str,
    config: dict[str, Any],
    checkpoint: dict[str, Any] | None,
    run_id: str,
) -> dict[str, Any]:
    """Process complete pipeline with checkpoint support."""
    try:
        # 1. Determine pipeline stages from config
        stages = config.get("stages", ["transcribe", "mine", "flagship"])
        
        # 2. Check checkpoint for completed stages
        completed_stages = []
        if checkpoint and "completed_stages" in checkpoint:
            completed_stages = checkpoint["completed_stages"]
        
        results = {}
        
        # 3. Run each stage in sequence
        for stage in stages:
            if stage in completed_stages:
                logger.info(f"Skipping completed stage: {stage}")
                continue
            
            logger.info(f"Running pipeline stage: {stage}")
            
            # Create sub-job for this stage
            stage_job_id = self.create_job(
                job_type=stage,
                input_id=video_id if stage == "transcribe" else f"episode_{video_id}",
                config=config,
                auto_process=False
            )
            
            # Process the stage
            stage_result = await self.process_job(stage_job_id, resume_from_checkpoint=True)
            
            if stage_result["status"] != "succeeded":
                raise KnowledgeSystemError(
                    f"Pipeline stage '{stage}' failed",
                    ErrorCode.PROCESSING_FAILED
                )
            
            results[stage] = stage_result["result"]
            
            # Update checkpoint
            completed_stages.append(stage)
            self.save_checkpoint(run_id, {
                "completed_stages": completed_stages,
                "results": results
            })
        
        # 4. Return success
        return {
            "status": "succeeded",
            "output_id": f"episode_{video_id}",
            "result": {
                "stages_completed": len(completed_stages),
                "stages": completed_stages,
                "results": results
            }
        }
        
    except Exception as e:
        logger.error(f"Pipeline failed for {video_id}: {e}")
        raise KnowledgeSystemError(
            f"Pipeline failed: {str(e)}",
            ErrorCode.PROCESSING_FAILED
        )
```

---

### 2. LLMAdapter Real API Implementation (Critical)

**Priority:** HIGH  
**Estimated Effort:** 4-5 days  
**Complexity:** Medium-High

#### Task 2.1: Replace Mock with Real API Calls

**Current Code:**
```python
async def _call_provider(
    self,
    provider: str,
    model: str,
    messages: list[dict[str, str]],
    **kwargs,
) -> dict[str, Any]:
    """Make the actual API call to the provider."""
    # This is a placeholder - in reality, this would call the actual provider APIs
    # For now, return a mock response
    logger.info(f"Calling {provider} API with model {model}")
    await asyncio.sleep(0.5)
    
    mock_content = "This is a mock LLM response for System 2 testing."
    return {
        "content": mock_content,
        "usage": {"prompt_tokens": 100, "completion_tokens": 20},
        "model": model,
        "provider": provider,
    }
```

**Required Implementation:**

```python
async def _call_provider(
    self,
    provider: str,
    model: str,
    messages: list[dict[str, str]],
    **kwargs,
) -> dict[str, Any]:
    """Make the actual API call to the provider."""
    
    if provider == "openai":
        return await self._call_openai(model, messages, **kwargs)
    elif provider == "anthropic":
        return await self._call_anthropic(model, messages, **kwargs)
    elif provider == "google":
        return await self._call_google(model, messages, **kwargs)
    elif provider == "ollama":
        return await self._call_ollama(model, messages, **kwargs)
    else:
        raise KnowledgeSystemError(
            f"Unknown provider: {provider}",
            ErrorCode.INVALID_INPUT
        )

async def _call_openai(
    self,
    model: str,
    messages: list[dict[str, str]],
    **kwargs
) -> dict[str, Any]:
    """Call OpenAI API."""
    import openai
    from openai import AsyncOpenAI
    
    try:
        # Get API key from environment
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise KnowledgeSystemError(
                "OPENAI_API_KEY not set",
                ErrorCode.CONFIGURATION_ERROR
            )
        
        # Create client
        client = AsyncOpenAI(api_key=api_key)
        
        # Make API call
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens"),
        )
        
        # Extract response
        content = response.choices[0].message.content
        usage = response.usage
        
        return {
            "content": content,
            "usage": {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
            },
            "model": response.model,
            "provider": "openai",
        }
        
    except openai.RateLimitError as e:
        # Trigger backoff
        self.rate_limiters["openai"].trigger_backoff()
        raise KnowledgeSystemError(
            f"OpenAI rate limit exceeded: {e}",
            ErrorCode.LLM_RATE_LIMIT
        )
    except openai.APIError as e:
        raise KnowledgeSystemError(
            f"OpenAI API error: {e}",
            ErrorCode.LLM_API_ERROR
        )
    except Exception as e:
        raise KnowledgeSystemError(
            f"OpenAI call failed: {e}",
            ErrorCode.LLM_API_ERROR
        )

async def _call_anthropic(
    self,
    model: str,
    messages: list[dict[str, str]],
    **kwargs
) -> dict[str, Any]:
    """Call Anthropic Claude API."""
    import anthropic
    from anthropic import AsyncAnthropic
    
    try:
        # Get API key
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise KnowledgeSystemError(
                "ANTHROPIC_API_KEY not set",
                ErrorCode.CONFIGURATION_ERROR
            )
        
        # Create client
        client = AsyncAnthropic(api_key=api_key)
        
        # Convert messages format (Anthropic uses different format)
        system_message = None
        claude_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                claude_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        
        # Make API call
        response = await client.messages.create(
            model=model,
            max_tokens=kwargs.get("max_tokens", 1024),
            system=system_message,
            messages=claude_messages,
            temperature=kwargs.get("temperature", 0.7),
        )
        
        # Extract response
        content = response.content[0].text
        usage = response.usage
        
        return {
            "content": content,
            "usage": {
                "prompt_tokens": usage.input_tokens,
                "completion_tokens": usage.output_tokens,
                "total_tokens": usage.input_tokens + usage.output_tokens,
            },
            "model": response.model,
            "provider": "anthropic",
        }
        
    except anthropic.RateLimitError as e:
        self.rate_limiters["anthropic"].trigger_backoff()
        raise KnowledgeSystemError(
            f"Anthropic rate limit exceeded: {e}",
            ErrorCode.LLM_RATE_LIMIT
        )
    except Exception as e:
        raise KnowledgeSystemError(
            f"Anthropic call failed: {e}",
            ErrorCode.LLM_API_ERROR
        )

async def _call_ollama(
    self,
    model: str,
    messages: list[dict[str, str]],
    **kwargs
) -> dict[str, Any]:
    """Call Ollama local API."""
    import aiohttp
    
    try:
        # Ollama runs locally on port 11434
        url = "http://localhost:11434/api/chat"
        
        # Prepare request
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.7),
            }
        }
        
        # Add format for JSON mode if requested
        if kwargs.get("format") == "json":
            payload["format"] = "json"
        
        # Make API call
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise KnowledgeSystemError(
                        f"Ollama API error: {error_text}",
                        ErrorCode.LLM_API_ERROR
                    )
                
                result = await response.json()
        
        # Extract response
        content = result["message"]["content"]
        
        # Ollama doesn't provide token counts, estimate them
        prompt_tokens = sum(len(m["content"].split()) for m in messages) * 1.3
        completion_tokens = len(content.split()) * 1.3
        
        return {
            "content": content,
            "usage": {
                "prompt_tokens": int(prompt_tokens),
                "completion_tokens": int(completion_tokens),
                "total_tokens": int(prompt_tokens + completion_tokens),
            },
            "model": model,
            "provider": "ollama",
        }
        
    except aiohttp.ClientError as e:
        raise KnowledgeSystemError(
            f"Ollama connection failed: {e}. Is Ollama running?",
            ErrorCode.LLM_API_ERROR
        )
    except Exception as e:
        raise KnowledgeSystemError(
            f"Ollama call failed: {e}",
            ErrorCode.LLM_API_ERROR
        )

async def _call_google(
    self,
    model: str,
    messages: list[dict[str, str]],
    **kwargs
) -> dict[str, Any]:
    """Call Google Gemini API."""
    import google.generativeai as genai
    
    try:
        # Get API key
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise KnowledgeSystemError(
                "GOOGLE_API_KEY not set",
                ErrorCode.CONFIGURATION_ERROR
            )
        
        # Configure client
        genai.configure(api_key=api_key)
        
        # Create model
        gemini_model = genai.GenerativeModel(model)
        
        # Convert messages to Gemini format (single prompt)
        prompt = "\n\n".join([
            f"{msg['role']}: {msg['content']}"
            for msg in messages
        ])
        
        # Make API call
        response = await gemini_model.generate_content_async(
            prompt,
            generation_config={
                "temperature": kwargs.get("temperature", 0.7),
                "max_output_tokens": kwargs.get("max_tokens", 1024),
            }
        )
        
        # Extract response
        content = response.text
        
        # Gemini doesn't provide detailed token counts
        prompt_tokens = len(prompt.split()) * 1.3
        completion_tokens = len(content.split()) * 1.3
        
        return {
            "content": content,
            "usage": {
                "prompt_tokens": int(prompt_tokens),
                "completion_tokens": int(completion_tokens),
                "total_tokens": int(prompt_tokens + completion_tokens),
            },
            "model": model,
            "provider": "google",
        }
        
    except Exception as e:
        raise KnowledgeSystemError(
            f"Google Gemini call failed: {e}",
            ErrorCode.LLM_API_ERROR
        )
```

**Dependencies to Add:**
```python
# pyproject.toml or requirements.txt
openai>=1.0.0
anthropic>=0.8.0
google-generativeai>=0.3.0
aiohttp>=3.9.0
```

---

### 3. Connect System2LLM to LLMAdapter (Critical)

**Priority:** HIGH  
**Estimated Effort:** 1 day  
**Complexity:** Low

**Current Issue:** `System2LLM` (used by HCE pipeline) calls `LLMAdapter`, but `LLMAdapter` returns mock responses.

**Required Changes:**

**File:** `src/knowledge_system/processors/hce/models/llm_system2.py`

**Current Code:**
```python
class System2LLM:
    def __init__(self, provider="ollama", model=None, temperature=0.7, max_tokens=None):
        self.provider = provider
        self.model = model or self._get_default_model(provider)
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.adapter = get_llm_adapter()  # ✅ Already gets the adapter
```

**Status:** ✅ Already connected! Once LLMAdapter is fixed (Task 2.1), System2LLM will automatically work.

---

### 4. Database Helper Functions (Medium Priority)

**Priority:** MEDIUM  
**Estimated Effort:** 2 days  
**Complexity:** Low

**Required Functions:**

**File:** `src/knowledge_system/database/hce_operations.py` (create new file)

```python
"""
Database operations for HCE (Human-Centric Extraction) data.
"""

from typing import Any, Dict, List
from sqlalchemy.orm import Session
from .models import Episode, Claim, Jargon, Person, Concept
from ..processors.hce.types import UnifiedMinerOutput, FlagshipEvaluationOutput


def store_mining_results(
    db_service,
    episode_id: str,
    miner_outputs: List[UnifiedMinerOutput]
) -> None:
    """Store mining results in database."""
    with db_service.get_session() as session:
        # Ensure episode exists
        episode = session.query(Episode).filter_by(episode_id=episode_id).first()
        if not episode:
            episode = Episode(episode_id=episode_id)
            session.add(episode)
        
        # Store claims
        for output in miner_outputs:
            for claim_data in output.claims:
                claim = Claim(
                    episode_id=episode_id,
                    claim_id=claim_data.get("claim_id"),
                    canonical=claim_data.get("text"),
                    claim_type=claim_data.get("type"),
                    tier=claim_data.get("tier", "C"),
                    first_mention_ts=claim_data.get("timestamp"),
                    scores_json=claim_data.get("scores", {}),
                )
                session.add(claim)
            
            # Store jargon
            for jargon_data in output.jargon:
                jargon = Jargon(
                    episode_id=episode_id,
                    term_id=jargon_data.get("term_id"),
                    term=jargon_data.get("term"),
                    category=jargon_data.get("category"),
                    definition=jargon_data.get("definition"),
                    evidence_json=jargon_data.get("evidence", []),
                )
                session.add(jargon)
            
            # Store people
            for person_data in output.people:
                person = Person(
                    episode_id=episode_id,
                    mention_id=person_data.get("mention_id"),
                    surface=person_data.get("name"),
                    normalized=person_data.get("normalized_name"),
                    entity_type=person_data.get("type", "person"),
                    confidence=person_data.get("confidence"),
                )
                session.add(person)
            
            # Store mental models
            for model_data in output.mental_models:
                concept = Concept(
                    episode_id=episode_id,
                    model_id=model_data.get("model_id"),
                    name=model_data.get("name"),
                    definition=model_data.get("definition"),
                    first_mention_ts=model_data.get("timestamp"),
                    aliases_json=model_data.get("aliases", []),
                    evidence_json=model_data.get("evidence", []),
                )
                session.add(concept)
        
        session.commit()


def load_mining_results(
    db_service,
    episode_id: str
) -> List[UnifiedMinerOutput]:
    """Load mining results from database."""
    with db_service.get_session() as session:
        # Load all claims for this episode
        claims = session.query(Claim).filter_by(episode_id=episode_id).all()
        jargon = session.query(Jargon).filter_by(episode_id=episode_id).all()
        people = session.query(Person).filter_by(episode_id=episode_id).all()
        concepts = session.query(Concept).filter_by(episode_id=episode_id).all()
        
        # Convert to UnifiedMinerOutput format
        # (Group by segment if needed, or return as single output)
        output = UnifiedMinerOutput({
            "claims": [
                {
                    "claim_id": c.claim_id,
                    "text": c.canonical,
                    "type": c.claim_type,
                    "tier": c.tier,
                    "timestamp": c.first_mention_ts,
                    "scores": c.scores_json,
                }
                for c in claims
            ],
            "jargon": [
                {
                    "term_id": j.term_id,
                    "term": j.term,
                    "category": j.category,
                    "definition": j.definition,
                    "evidence": j.evidence_json,
                }
                for j in jargon
            ],
            "people": [
                {
                    "mention_id": p.mention_id,
                    "name": p.surface,
                    "normalized_name": p.normalized,
                    "type": p.entity_type,
                    "confidence": p.confidence,
                }
                for p in people
            ],
            "mental_models": [
                {
                    "model_id": c.model_id,
                    "name": c.name,
                    "definition": c.definition,
                    "timestamp": c.first_mention_ts,
                    "aliases": c.aliases_json,
                    "evidence": c.evidence_json,
                }
                for c in concepts
            ],
        })
        
        return [output]


def store_flagship_results(
    db_service,
    episode_id: str,
    evaluation_output: FlagshipEvaluationOutput
) -> None:
    """Store flagship evaluation results in database."""
    with db_service.get_session() as session:
        # Update claim tiers based on evaluation
        for claim_data in evaluation_output.evaluated_claims:
            claim = session.query(Claim).filter_by(
                episode_id=episode_id,
                claim_id=claim_data.get("claim_id")
            ).first()
            
            if claim:
                claim.tier = claim_data.get("tier", "C")
                claim.scores_json = claim_data.get("scores", {})
        
        session.commit()


def store_transcript(
    db_service,
    episode_id: str,
    transcript_path: str
) -> None:
    """Store transcript reference in database."""
    with db_service.get_session() as session:
        episode = session.query(Episode).filter_by(episode_id=episode_id).first()
        if not episode:
            episode = Episode(episode_id=episode_id)
            session.add(episode)
        
        # Store transcript path in metadata
        if not episode.metadata_json:
            episode.metadata_json = {}
        episode.metadata_json["transcript_path"] = str(transcript_path)
        
        session.commit()
```

---

### 5. GUI Integration Fix (High Priority)

**Priority:** HIGH  
**Estimated Effort:** 2 hours  
**Complexity:** Low

**Current Issue:** GUI calls System2Orchestrator but expects different status values.

**File:** `src/knowledge_system/gui/tabs/summarization_tab.py`

**Line 186:** Change status check
```python
# Current (wrong):
if result["status"] == "succeeded":

# Should be:
if result.get("status") == "succeeded":
```

**Line 210:** Better error message
```python
# Current:
error_msg = result.get("error", "Unknown error")

# Should be:
error_msg = result.get("error_message", result.get("error", "Processing failed"))
```

**OR: Bypass System2 Entirely (Recommended for now)**

Replace `_run_with_system2_orchestrator()` to use `SummarizerProcessor` directly:

```python
def _run_with_system2_orchestrator(self) -> None:
    """Run summarization using the working HCE pipeline."""
    try:
        from ...processors.summarizer import SummarizerProcessor
        from ...utils.progress import SummarizationProgress
        
        # Get settings
        provider = self.gui_settings.get("provider", "openai")
        model = self.gui_settings.get("model", "gpt-4o-mini")
        
        # Create processor
        processor = SummarizerProcessor(
            provider=provider,
            model=model,
            max_tokens=1000,
            hce_options={
                "miner_model": f"{provider}:{model}",
                "use_skim": True,
            }
        )
        
        success_count = 0
        failure_count = 0
        
        for i, file_path in enumerate(self.files):
            if self.should_stop:
                break
            
            # Emit progress
            progress = SummarizationProgress(
                current_file=file_path,
                total_files=len(self.files),
                completed_files=i,
                current_step=f"Processing {Path(file_path).name}",
                percent=(i / len(self.files)) * 100.0,
                provider=provider,
                model_name=model,
            )
            self.progress_updated.emit(progress)
            
            try:
                # Process file
                result = processor.process(file_path)
                
                if result:
                    success_count += 1
                    self.file_completed.emit(i + 1, len(self.files))
                else:
                    failure_count += 1
                    
            except Exception as e:
                failure_count += 1
                logger.error(f"Processing failed for {file_path}: {e}")
        
        self.processing_finished.emit(success_count, failure_count, len(self.files))
        
    except Exception as e:
        self.processing_error.emit(str(e))
```

---

## Testing Strategy

### Unit Tests

**File:** `tests/test_system2_orchestrator.py`

```python
import pytest
from knowledge_system.core.system2_orchestrator import System2Orchestrator
from knowledge_system.database import DatabaseService


@pytest.fixture
def orchestrator():
    """Create test orchestrator with in-memory database."""
    db_service = DatabaseService(":memory:")
    return System2Orchestrator(db_service)


def test_create_job(orchestrator):
    """Test job creation."""
    job_id = orchestrator.create_job(
        job_type="mine",
        input_id="test_episode",
        config={"test": "config"},
        auto_process=False
    )
    
    assert job_id is not None
    assert len(job_id) == 16  # Deterministic ID length


def test_create_job_run(orchestrator):
    """Test job run creation."""
    job_id = orchestrator.create_job("mine", "test_episode", {})
    run_id = orchestrator.create_job_run(job_id)
    
    assert run_id is not None
    assert run_id.startswith(job_id)


@pytest.mark.asyncio
async def test_process_mine(orchestrator):
    """Test mining process."""
    # Create test transcript file
    test_file = Path("test_transcript.md")
    test_file.write_text("""
[00:00:01] Speaker: This is a test claim about AI.
[00:00:05] Speaker: Machine learning is a subset of AI.
    """)
    
    try:
        # Create job
        job_id = orchestrator.create_job(
            job_type="mine",
            input_id="test_episode",
            config={"file_path": str(test_file)}
        )
        
        # Process job
        result = await orchestrator.process_job(job_id)
        
        # Verify result
        assert result["status"] == "succeeded"
        assert "claims_extracted" in result["result"]
        assert result["result"]["claims_extracted"] > 0
        
    finally:
        test_file.unlink()


@pytest.mark.asyncio
async def test_checkpoint_resume(orchestrator):
    """Test checkpoint save and resume."""
    # Create job that will be interrupted
    job_id = orchestrator.create_job(
        job_type="mine",
        input_id="test_episode",
        config={"file_path": "large_file.md"}
    )
    
    # Start processing (will save checkpoint)
    run_id = orchestrator.create_job_run(job_id)
    
    # Simulate checkpoint save
    orchestrator.save_checkpoint(run_id, {
        "last_segment": 50,
        "partial_results": 25
    })
    
    # Load checkpoint
    checkpoint = orchestrator.load_checkpoint(run_id)
    
    assert checkpoint is not None
    assert checkpoint["last_segment"] == 50
    assert checkpoint["partial_results"] == 25
```

---

### Integration Tests

**File:** `tests/integration/test_system2_pipeline.py`

```python
import pytest
from pathlib import Path
from knowledge_system.core.system2_orchestrator import System2Orchestrator


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_pipeline():
    """Test complete pipeline: transcribe → mine → flagship."""
    orchestrator = System2Orchestrator()
    
    # Create test audio file (mock)
    test_audio = Path("test_audio.mp3")
    # ... create test file ...
    
    try:
        # Create pipeline job
        job_id = orchestrator.create_job(
            job_type="pipeline",
            input_id="test_video",
            config={
                "file_path": str(test_audio),
                "stages": ["transcribe", "mine", "flagship"]
            },
            auto_process=True
        )
        
        # Process pipeline
        result = await orchestrator.process_job(job_id)
        
        # Verify all stages completed
        assert result["status"] == "succeeded"
        assert len(result["result"]["completed_stages"]) == 3
        assert "transcribe" in result["result"]["completed_stages"]
        assert "mine" in result["result"]["completed_stages"]
        assert "flagship" in result["result"]["completed_stages"]
        
    finally:
        test_audio.unlink()


@pytest.mark.integration
def test_llm_adapter_real_calls():
    """Test LLM adapter makes real API calls."""
    from knowledge_system.core.llm_adapter import get_llm_adapter
    
    adapter = get_llm_adapter()
    
    # Test OpenAI
    response = await adapter.complete(
        provider="openai",
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Say 'test'"}]
    )
    
    assert response["content"] != "This is a mock LLM response"
    assert "test" in response["content"].lower()
    assert response["usage"]["total_tokens"] > 0
```

---

## Migration Path

### Phase 1: Fix LLM Adapter (Week 1)

1. **Day 1-2:** Implement real API calls for all providers
2. **Day 3:** Test with actual API keys
3. **Day 4:** Update error handling and retries
4. **Day 5:** Integration testing

**Deliverable:** LLM Adapter that makes real API calls

---

### Phase 2: Implement Core Processing (Week 2)

1. **Day 1-2:** Implement `_process_mine()` with checkpoints
2. **Day 2-3:** Implement `_process_flagship()`
3. **Day 4:** Implement `_process_transcribe()`
4. **Day 5:** Testing and bug fixes

**Deliverable:** Working mining, flagship, and transcription

---

### Phase 3: Complete Pipeline (Week 3)

1. **Day 1:** Implement `_process_upload()`
2. **Day 2:** Implement `_process_pipeline()` with chaining
3. **Day 3:** Create database helper functions
4. **Day 4:** Fix GUI integration
5. **Day 5:** End-to-end testing

**Deliverable:** Complete System 2 implementation

---

## Success Criteria

### Minimum Viable Implementation

- ✅ LLM Adapter makes real API calls (not mocks)
- ✅ `_process_mine()` extracts claims from transcripts
- ✅ Results are stored in database
- ✅ GUI can process files successfully
- ✅ Checkpoints save and restore correctly

### Full Implementation

- ✅ All 5 processing methods implemented
- ✅ All 4 LLM providers working (OpenAI, Anthropic, Google, Ollama)
- ✅ Checkpoint resume works for interrupted jobs
- ✅ LLM request/response tracking in database
- ✅ Auto-process chaining between stages
- ✅ Hardware-aware concurrency limits working
- ✅ Complete test coverage (>80%)
- ✅ Documentation updated

---

## Alternative: Quick Fix (Bypass System2)

If you need the GUI working immediately, you can bypass System2:

**File:** `src/knowledge_system/gui/tabs/summarization_tab.py`

**Line 133:** Replace entire `_run_with_system2_orchestrator()` method with:

```python
def _run_with_system2_orchestrator(self) -> None:
    """Run summarization using direct HCE pipeline (System2 bypass)."""
    try:
        from ...processors.summarizer import SummarizerProcessor
        
        processor = SummarizerProcessor(
            provider=self.gui_settings.get("provider", "openai"),
            model=self.gui_settings.get("model", "gpt-4o-mini"),
            max_tokens=1000,
            hce_options={
                "miner_model": f"{self.gui_settings.get('provider')}:{self.gui_settings.get('model')}",
                "use_skim": True,
            }
        )
        
        success_count = 0
        failure_count = 0
        
        for i, file_path in enumerate(self.files):
            try:
                result = processor.process(file_path)
                if result:
                    success_count += 1
                else:
                    failure_count += 1
            except Exception as e:
                failure_count += 1
                logger.error(f"Failed: {e}")
        
        self.processing_finished.emit(success_count, failure_count, len(self.files))
        
    except Exception as e:
        self.processing_error.emit(str(e))
```

**Estimated Time:** 30 minutes  
**Result:** GUI works immediately, System2 can be completed later

---

## Questions for Decision Making

1. **Timeline:** Do you need the GUI working immediately, or can you wait 2-3 weeks for full System2?

2. **Scope:** Do you want to complete all of System2, or just the minimum to make it work?

3. **Testing:** Do you have API keys for OpenAI, Anthropic, Google Gemini for testing?

4. **Priority:** Is System2 tracking/resumability critical, or is basic functionality more important?

5. **Resources:** How many developer hours per week can be allocated to this?

---

## Recommended Approach

**For Immediate Needs:**
→ Use the "Quick Fix" to bypass System2 and make GUI work now (30 minutes)

**For Long-Term:**
→ Implement System2 properly over 2-3 weeks following the phases above

**Rationale:**
- Quick fix gets you working immediately
- System2 is valuable but not critical for basic functionality
- Can implement System2 incrementally without blocking users
- Allows testing each component thoroughly

---

## Contact & Support

If you have questions while implementing:

1. Check existing HCE pipeline code in `src/knowledge_system/processors/hce/`
2. Review working CLI implementation in `src/knowledge_system/commands/summarize.py`
3. Test each component individually before integration
4. Use the database schema as the contract between components

Good luck! 🚀
