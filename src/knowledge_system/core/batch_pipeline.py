"""
Batch Pipeline Orchestrator

Orchestrates the 3-stage batch processing pipeline:
1. Mining - Extract claims, jargon, people, concepts
2. Flagship Evaluation - Rank and filter claims
3. Re-mining - Re-process flagged segments with stronger model

Features:
- Sequential batch submission for prompt cache warmup
- Cache metrics tracking
- Progress reporting
- Database persistence
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from .batch_anthropic import AnthropicBatchClient
from .batch_client import (
    BaseBatchClient,
    BatchJob,
    BatchPipelineResult,
    BatchRequest,
    BatchResult,
    BatchStatus,
)
from .batch_openai import OpenAIBatchClient

logger = logging.getLogger(__name__)


class BatchPipelineConfig:
    """Configuration for the batch pipeline."""
    
    def __init__(
        self,
        # Provider and model settings
        batch_provider: str = "openai",
        batch_mining_model: str = "gpt-5-mini",
        batch_flagship_model: str = "gpt-5-mini",
        batch_remine_provider: str = "anthropic",
        batch_remine_model: str = "claude-3.7-sonnet",
        
        # Re-mining settings
        remine_enabled: bool = True,
        remine_confidence_threshold: float = 4.0,
        remine_empty_segments: bool = True,
        remine_max_percent: float = 15.0,
        
        # Cache optimization
        enable_cache_optimization: bool = True,
        sequential_batch_submission: bool = True,
        batch_delay_seconds: int = 30,
        
        # Polling and limits
        poll_interval_seconds: int = 60,
        max_requests_per_batch: int = 10000,
    ):
        self.batch_provider = batch_provider
        self.batch_mining_model = batch_mining_model
        self.batch_flagship_model = batch_flagship_model
        self.batch_remine_provider = batch_remine_provider
        self.batch_remine_model = batch_remine_model
        
        self.remine_enabled = remine_enabled
        self.remine_confidence_threshold = remine_confidence_threshold
        self.remine_empty_segments = remine_empty_segments
        self.remine_max_percent = remine_max_percent
        
        self.enable_cache_optimization = enable_cache_optimization
        self.sequential_batch_submission = sequential_batch_submission
        self.batch_delay_seconds = batch_delay_seconds
        
        self.poll_interval_seconds = poll_interval_seconds
        self.max_requests_per_batch = max_requests_per_batch


class BatchPipeline:
    """Orchestrates batch processing with prompt caching optimization."""
    
    def __init__(
        self,
        config: BatchPipelineConfig | None = None,
        db_service: Any = None,
    ):
        """
        Initialize batch pipeline.
        
        Args:
            config: Pipeline configuration
            db_service: Database service for persistence
        """
        self.config = config or BatchPipelineConfig()
        self.db = db_service
        
        # Initialize clients lazily
        self._openai_client: OpenAIBatchClient | None = None
        self._anthropic_client: AnthropicBatchClient | None = None
        
        # Load miner prompt template
        self.miner_prompt_template = self._load_miner_prompt()
        self.flagship_prompt_template = self._load_flagship_prompt()
        
        # Cache stats
        self._cache_stats = {
            "total_input_tokens": 0,
            "cached_tokens": 0,
            "cost_savings": 0.0
        }
    
    def _load_miner_prompt(self) -> str:
        """Load the unified miner prompt template."""
        prompt_path = (
            Path(__file__).parent.parent / 
            "processors" / "hce" / "prompts" / "unified_miner.txt"
        )
        if prompt_path.exists():
            return prompt_path.read_text()
        
        logger.warning(f"Miner prompt not found at {prompt_path}")
        return ""
    
    def _load_flagship_prompt(self) -> str:
        """Load the flagship evaluator prompt template."""
        prompt_path = (
            Path(__file__).parent.parent / 
            "processors" / "hce" / "prompts" / "flagship_evaluator.txt"
        )
        if prompt_path.exists():
            return prompt_path.read_text()
        
        logger.warning(f"Flagship prompt not found at {prompt_path}")
        return ""
    
    def _get_client(self, provider: str) -> BaseBatchClient:
        """Get or create batch client for provider."""
        if provider == "openai":
            if self._openai_client is None:
                self._openai_client = OpenAIBatchClient()
            return self._openai_client
        elif provider == "anthropic":
            if self._anthropic_client is None:
                self._anthropic_client = AnthropicBatchClient()
            return self._anthropic_client
        else:
            raise ValueError(f"Unknown provider: {provider}")
    
    async def process_episodes(
        self,
        episodes: list[Any],  # list[EpisodeBundle]
        progress_callback: Callable[[str], None] | None = None
    ) -> BatchPipelineResult:
        """
        Process multiple episodes through 3-stage batch pipeline.
        
        Args:
            episodes: List of EpisodeBundle objects
            progress_callback: Optional callback for progress updates
            
        Returns:
            BatchPipelineResult with all outputs
        """
        total_segments = sum(len(ep.segments) for ep in episodes)
        logger.info(
            f"Starting batch pipeline: {len(episodes)} episodes, "
            f"{total_segments} segments"
        )
        
        def report(stage: str, pct: float, msg: str = ""):
            if progress_callback:
                progress_callback(f"[{stage}] {pct:.0f}% - {msg}")
        
        # ═══════════════════════════════════════════════════════════════
        # STAGE 1: MINING (with cache optimization)
        # ═══════════════════════════════════════════════════════════════
        report("Mining", 0, f"Submitting {total_segments} segments to batch API")
        
        mining_jobs = await self._submit_mining_batches(episodes)
        report("Mining", 10, f"Submitted {len(mining_jobs)} batches, waiting for completion")
        
        mining_results = await self._wait_for_completion(
            mining_jobs,
            "mining",
            lambda pct: report("Mining", 10 + pct * 0.3, "Processing")
        )
        miner_outputs = self._parse_mining_results(mining_results, episodes)
        report("Mining", 40, f"Complete: {len(mining_results)} segments processed")
        
        # ═══════════════════════════════════════════════════════════════
        # STAGE 2: FLAGSHIP EVALUATION
        # ═══════════════════════════════════════════════════════════════
        report("Flagship", 40, "Preparing claim evaluation batch")
        
        flagship_jobs = await self._submit_flagship_batch(miner_outputs, episodes)
        report("Flagship", 45, f"Submitted {len(flagship_jobs)} batches")
        
        flagship_results = await self._wait_for_completion(
            flagship_jobs,
            "flagship",
            lambda pct: report("Flagship", 45 + pct * 0.2, "Evaluating claims")
        )
        evaluation = self._parse_flagship_results(flagship_results, episodes)
        
        claims_accepted = sum(
            len(e.get("accepted_claims", [])) for e in evaluation.values()
        )
        report("Flagship", 65, f"Complete: {claims_accepted} claims accepted")
        
        # ═══════════════════════════════════════════════════════════════
        # STAGE 3: RE-MINING (if enabled)
        # ═══════════════════════════════════════════════════════════════
        if self.config.remine_enabled:
            flagged = self._identify_segments_to_remine(episodes, evaluation)
            
            if flagged:
                report(
                    "Re-mining", 65, 
                    f"Re-mining {len(flagged)} flagged segments with "
                    f"{self.config.batch_remine_model}"
                )
                
                remine_jobs = await self._submit_remine_batch(flagged)
                remine_results = await self._wait_for_completion(
                    remine_jobs,
                    "remine",
                    lambda pct: report("Re-mining", 65 + pct * 0.25, "Processing")
                )
                
                miner_outputs = self._merge_remine_results(
                    miner_outputs, remine_results, flagged
                )
                report(
                    "Re-mining", 90, 
                    f"Complete: merged {len(remine_results)} re-mined segments"
                )
            else:
                report("Re-mining", 90, "No segments flagged for re-mining")
        else:
            report("Re-mining", 90, "Re-mining disabled")
        
        report("Complete", 100, "Batch pipeline finished")
        
        return BatchPipelineResult(
            miner_outputs=miner_outputs,
            evaluation=evaluation,
            episodes_processed=len(episodes),
            segments_processed=total_segments,
            cache_stats=self._cache_stats.copy()
        )
    
    async def _submit_mining_batches(
        self,
        episodes: list[Any]
    ) -> list[BatchJob]:
        """Submit mining batches optimized for prompt caching."""
        
        # Build all requests
        requests = self._build_mining_requests(episodes)
        
        # Sort requests to maximize cache hits
        if self.config.enable_cache_optimization:
            requests = self._sort_for_cache_hits(requests)
        
        # Split into batches
        client = self._get_client(self.config.batch_provider)
        batches = client.chunk_requests(
            requests, self.config.max_requests_per_batch
        )
        
        jobs = []
        for i, batch in enumerate(batches):
            logger.info(
                f"Submitting mining batch {i+1}/{len(batches)} "
                f"({len(batch)} requests)"
            )
            
            job = await client.create_batch(batch, metadata={
                "stage": "mining",
                "batch_number": i + 1,
                "total_batches": len(batches)
            })
            jobs.append(job)
            
            if self.db:
                await self._save_batch_job(job, "mining")
            
            # Sequential submission for cache warmup
            if (self.config.sequential_batch_submission and 
                i < len(batches) - 1):
                logger.info(
                    f"Waiting {self.config.batch_delay_seconds}s for cache warmup..."
                )
                await asyncio.sleep(self.config.batch_delay_seconds)
        
        return jobs
    
    async def _submit_flagship_batch(
        self,
        miner_outputs: dict[str, Any],
        episodes: list[Any]
    ) -> list[BatchJob]:
        """Submit flagship evaluation batch requests."""
        
        requests = []
        for episode in episodes:
            source_id = episode.source_id
            outputs = miner_outputs.get(source_id, {})
            
            # Collect all claims from this episode
            all_claims = []
            for seg_id, output in outputs.items():
                claims = output.get("claims", [])
                all_claims.extend(claims)
            
            if not all_claims:
                continue
            
            # Build flagship prompt
            prompt = self._build_flagship_prompt(all_claims, episode)
            
            req = BatchRequest(
                custom_id=f"flagship:{source_id}",
                messages=[{"role": "user", "content": prompt}],
                model=self.config.batch_flagship_model,
                temperature=0.2,
                max_tokens=6000,
                response_format={"type": "json_object"}
            )
            requests.append(req)
        
        if not requests:
            return []
        
        # Submit batch
        client = self._get_client(self.config.batch_provider)
        batches = client.chunk_requests(
            requests, self.config.max_requests_per_batch
        )
        
        jobs = []
        for i, batch in enumerate(batches):
            job = await client.create_batch(batch, metadata={
                "stage": "flagship",
                "batch_number": i + 1,
                "total_batches": len(batches)
            })
            jobs.append(job)
            
            if self.db:
                await self._save_batch_job(job, "flagship")
        
        return jobs
    
    async def _submit_remine_batch(
        self,
        segments: list[tuple[Any, Any]]  # list[(episode, segment)]
    ) -> list[BatchJob]:
        """Submit re-mining batch with stronger model."""
        
        requests = []
        for episode, segment in segments:
            prompt = self._build_cache_optimized_prompt(segment)
            
            req = BatchRequest(
                custom_id=f"remine:{episode.source_id}:{segment.segment_id}",
                messages=[{"role": "user", "content": prompt}],
                model=self.config.batch_remine_model,
                temperature=0.1,
                max_tokens=4000,
                response_format={"type": "json_object"}
            )
            requests.append(req)
        
        # Use remine provider (may be different)
        client = self._get_client(self.config.batch_remine_provider)
        batches = client.chunk_requests(
            requests, self.config.max_requests_per_batch
        )
        
        jobs = []
        for i, batch in enumerate(batches):
            job = await client.create_batch(batch, metadata={
                "stage": "remine",
                "batch_number": i + 1,
                "total_batches": len(batches)
            })
            jobs.append(job)
            
            if self.db:
                await self._save_batch_job(job, "remine")
        
        return jobs
    
    async def _wait_for_completion(
        self,
        jobs: list[BatchJob],
        stage: str,
        progress_callback: Callable[[float], None] | None = None
    ) -> dict[str, BatchResult]:
        """Poll until all batch jobs complete."""
        
        results: dict[str, BatchResult] = {}
        pending = list(jobs)
        
        while pending:
            await asyncio.sleep(self.config.poll_interval_seconds)
            
            for job in pending[:]:
                client = self._get_client(job.provider)
                status = await client.get_status(job.batch_id)
                
                logger.debug(
                    f"Batch {job.batch_id} status: {status.status.value} "
                    f"({status.completed_count}/{status.request_count})"
                )
                
                if status.status == BatchStatus.COMPLETED:
                    batch_results = await client.get_results(job.batch_id)
                    
                    for result in batch_results:
                        results[result.custom_id] = result
                        
                        # Update cache stats
                        if result.usage:
                            self._cache_stats["total_input_tokens"] += result.tokens_input
                            self._cache_stats["cached_tokens"] += result.tokens_cached
                    
                    pending.remove(job)
                    logger.info(
                        f"Batch {job.batch_id} completed: {len(batch_results)} results"
                    )
                    
                elif status.status == BatchStatus.FAILED:
                    logger.error(
                        f"Batch {job.batch_id} failed: {status.error_message}"
                    )
                    pending.remove(job)
                
                elif status.status in (BatchStatus.EXPIRED, BatchStatus.CANCELLED):
                    logger.warning(
                        f"Batch {job.batch_id} {status.status.value}"
                    )
                    pending.remove(job)
            
            # Report progress
            if progress_callback and jobs:
                completed = len(jobs) - len(pending)
                progress_callback(completed / len(jobs))
        
        return results
    
    def _build_mining_requests(
        self,
        episodes: list[Any]
    ) -> list[BatchRequest]:
        """Build batch requests with cache-optimized prompt structure."""
        
        requests = []
        for episode in episodes:
            for segment in episode.segments:
                # CRITICAL: Static content FIRST, dynamic content LAST
                prompt = self._build_cache_optimized_prompt(segment)
                
                req = BatchRequest(
                    custom_id=f"{episode.source_id}:{segment.segment_id}",
                    messages=[{"role": "user", "content": prompt}],
                    model=self.config.batch_mining_model,
                    temperature=0.1,
                    max_tokens=4000,
                    response_format={"type": "json_object"}
                )
                requests.append(req)
        
        return requests
    
    def _build_cache_optimized_prompt(self, segment: Any) -> str:
        """
        Build prompt with static prefix for caching.
        
        Structure:
        [STATIC PREFIX - ~2,500 tokens - CACHED]
        - Instructions
        - Examples
        - Schema
        - Output format
        
        [DYNAMIC SUFFIX - ~750 tokens - NOT CACHED]
        - Segment data
        """
        # Build dynamic segment data (not cached)
        segment_data = {
            "segment_id": segment.segment_id,
            "speaker": segment.speaker,
            "timestamp_start": segment.t0,
            "timestamp_end": segment.t1,
            "text": segment.text,
        }
        
        # Combine: static FIRST, dynamic LAST
        return (
            f"{self.miner_prompt_template}\n\n"
            f"SEGMENT TO ANALYZE:\n{json.dumps(segment_data, indent=2)}"
        )
    
    def _build_flagship_prompt(
        self,
        claims: list[dict],
        episode: Any
    ) -> str:
        """Build flagship evaluation prompt."""
        
        claims_json = json.dumps(claims, indent=2)
        
        return (
            f"{self.flagship_prompt_template}\n\n"
            f"EPISODE: {episode.source_id}\n"
            f"TOTAL CLAIMS: {len(claims)}\n\n"
            f"CLAIMS TO EVALUATE:\n{claims_json}"
        )
    
    def _sort_for_cache_hits(
        self,
        requests: list[BatchRequest]
    ) -> list[BatchRequest]:
        """
        Sort requests to maximize prompt prefix cache hits.
        
        Strategy: Group by source_id so similar content is processed together.
        The static prompt prefix is identical, so ordering doesn't affect that.
        But grouping similar content may help with any content-based caching.
        """
        return sorted(requests, key=lambda r: r.custom_id.split(":")[0])
    
    def _parse_mining_results(
        self,
        results: dict[str, BatchResult],
        episodes: list[Any]
    ) -> dict[str, dict[str, Any]]:
        """Parse mining results into structured output."""
        
        outputs: dict[str, dict[str, Any]] = {}
        
        for custom_id, result in results.items():
            if ":" not in custom_id:
                continue
            
            parts = custom_id.split(":")
            source_id = parts[0]
            segment_id = parts[1] if len(parts) > 1 else ""
            
            if source_id not in outputs:
                outputs[source_id] = {}
            
            if result.success and result.content:
                parsed = result.parse_json_content()
                if parsed:
                    outputs[source_id][segment_id] = parsed
                else:
                    outputs[source_id][segment_id] = {
                        "claims": [],
                        "jargon": [],
                        "people": [],
                        "mental_models": [],
                        "error": "Failed to parse JSON"
                    }
            else:
                outputs[source_id][segment_id] = {
                    "claims": [],
                    "jargon": [],
                    "people": [],
                    "mental_models": [],
                    "error": result.error or "Unknown error"
                }
        
        return outputs
    
    def _parse_flagship_results(
        self,
        results: dict[str, BatchResult],
        episodes: list[Any]
    ) -> dict[str, Any]:
        """Parse flagship evaluation results."""
        
        evaluations: dict[str, Any] = {}
        
        for custom_id, result in results.items():
            if not custom_id.startswith("flagship:"):
                continue
            
            source_id = custom_id.replace("flagship:", "")
            
            if result.success and result.content:
                parsed = result.parse_json_content()
                if parsed:
                    evaluations[source_id] = parsed
                else:
                    evaluations[source_id] = {"error": "Failed to parse JSON"}
            else:
                evaluations[source_id] = {"error": result.error or "Unknown error"}
        
        return evaluations
    
    def _identify_segments_to_remine(
        self,
        episodes: list[Any],
        evaluation: dict[str, Any]
    ) -> list[tuple[Any, Any]]:
        """Identify segments that need re-mining."""
        
        flagged: list[tuple[Any, Any]] = []
        
        for episode in episodes:
            source_id = episode.source_id
            eval_data = evaluation.get(source_id, {})
            
            # Get low confidence claims
            evaluated_claims = eval_data.get("evaluated_claims", [])
            low_conf_segments: set[str] = set()
            
            for claim in evaluated_claims:
                confidence = claim.get("confidence_final", 10)
                if confidence < self.config.remine_confidence_threshold:
                    # Extract segment IDs from evidence spans
                    for evidence in claim.get("evidence_spans", []):
                        seg_id = evidence.get("segment_id")
                        if seg_id:
                            low_conf_segments.add(seg_id)
            
            # Get empty segments (if enabled)
            empty_segments: set[str] = set()
            if self.config.remine_empty_segments:
                segments_with_claims = set()
                for claim in evaluated_claims:
                    for evidence in claim.get("evidence_spans", []):
                        seg_id = evidence.get("segment_id")
                        if seg_id:
                            segments_with_claims.add(seg_id)
                
                all_seg_ids = {s.segment_id for s in episode.segments}
                empty_segments = all_seg_ids - segments_with_claims
            
            # Combine and cap
            all_flagged = low_conf_segments | empty_segments
            max_to_remine = int(
                len(episode.segments) * self.config.remine_max_percent / 100
            )
            
            flagged_ids = list(all_flagged)[:max_to_remine]
            
            # Find actual segment objects
            for segment in episode.segments:
                if segment.segment_id in flagged_ids:
                    flagged.append((episode, segment))
        
        logger.info(f"Identified {len(flagged)} segments for re-mining")
        return flagged
    
    def _merge_remine_results(
        self,
        miner_outputs: dict[str, dict[str, Any]],
        remine_results: dict[str, BatchResult],
        flagged_segments: list[tuple[Any, Any]]
    ) -> dict[str, dict[str, Any]]:
        """Merge re-mined results back into main outputs."""
        
        for custom_id, result in remine_results.items():
            if not custom_id.startswith("remine:"):
                continue
            
            parts = custom_id.replace("remine:", "").split(":")
            if len(parts) < 2:
                continue
            
            source_id = parts[0]
            segment_id = parts[1]
            
            if result.success and result.content:
                parsed = result.parse_json_content()
                if parsed and source_id in miner_outputs:
                    # Replace with re-mined output
                    miner_outputs[source_id][segment_id] = parsed
                    logger.debug(
                        f"Merged re-mined output for {source_id}:{segment_id}"
                    )
        
        return miner_outputs
    
    async def _save_batch_job(self, job: BatchJob, stage: str):
        """Save batch job to database."""
        if not self.db:
            return
        
        try:
            # This would use the database service to save the job
            # For now, just log
            logger.debug(f"Would save batch job {job.batch_id} to database")
        except Exception as e:
            logger.warning(f"Failed to save batch job: {e}")
    
    def get_cache_stats(self) -> dict[str, Any]:
        """Get accumulated cache statistics."""
        stats = self._cache_stats.copy()
        
        if stats["total_input_tokens"] > 0:
            stats["cache_hit_rate"] = (
                stats["cached_tokens"] / stats["total_input_tokens"]
            )
            # Estimate cost savings (assuming $0.25/M for uncached, $0.125/M for cached)
            uncached_cost = stats["total_input_tokens"] * 0.25 / 1_000_000
            cached_cost = (
                (stats["total_input_tokens"] - stats["cached_tokens"]) * 0.25 / 1_000_000 +
                stats["cached_tokens"] * 0.125 / 1_000_000
            )
            stats["cost_savings"] = uncached_cost - cached_cost
        else:
            stats["cache_hit_rate"] = 0.0
            stats["cost_savings"] = 0.0
        
        return stats

