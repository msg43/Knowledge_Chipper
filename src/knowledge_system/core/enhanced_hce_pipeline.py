#!/usr/bin/env python3
"""
Enhanced HCE Pipeline with Dynamic Parallelization

Integrates the dynamic parallelization system with the existing
Hybrid Claim Extractor (HCE) pipeline for optimal performance.
"""

import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .dynamic_parallelization import get_parallelization_manager
from .parallel_processor import (
    initialize_parallel_processor,
    process_evaluation_parallel,
    process_mining_parallel,
)

logger = logging.getLogger(__name__)


class EnhancedHCEPipeline:
    """
    Enhanced HCE Pipeline with intelligent parallelization and resource management.

    Features:
    - Dynamic worker scaling based on hardware capabilities
    - FP16 model optimization for high-end systems
    - Real-time resource monitoring and adjustment
    - Job completion-based worker management
    - Memory-aware parallelization
    """

    def __init__(self, hardware_specs: dict[str, Any]):
        self.hardware_specs = hardware_specs
        self.processor = initialize_parallel_processor(hardware_specs)
        self.manager = get_parallelization_manager()

        # Performance tracking
        self.processing_stats = {
            "total_chunks_processed": 0,
            "total_claims_extracted": 0,
            "total_claims_evaluated": 0,
            "avg_mining_time": 0.0,
            "avg_evaluation_time": 0.0,
            "parallelization_efficiency": 0.0,
        }

        logger.info(
            f"Enhanced HCE Pipeline initialized for {hardware_specs.get('chip_type', 'Unknown')} "
            f"with {hardware_specs.get('memory_gb', 16)}GB RAM"
        )

    async def process_document_parallel(
        self,
        content: str,
        miner_func: Callable[[str], dict[str, Any]],
        evaluator_func: Callable[[dict[str, Any]], dict[str, Any]],
        chunk_size: int = 2000,
        overlap: int = 200,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> dict[str, Any]:
        """
        Process document with enhanced parallelization.

        Args:
            content: Document content to process
            miner_func: Mining function for claim extraction
            evaluator_func: Evaluation function for claim scoring
            chunk_size: Size of content chunks
            overlap: Overlap between chunks
            progress_callback: Progress callback function

        Returns:
            Processed results with claims and metadata
        """
        start_time = time.time()

        # Step 1: Chunk content
        if progress_callback:
            progress_callback("Chunking content", 0, 100)

        chunks = self._create_chunks(content, chunk_size, overlap)
        logger.info(f"Created {len(chunks)} chunks for parallel processing")

        # Step 2: Parallel mining (Stage A)
        if progress_callback:
            progress_callback("Mining claims", 10, 100)

        mining_start = time.time()
        mining_results = await process_mining_parallel(
            chunks,
            miner_func,
            self.hardware_specs,
            lambda completed, total: (
                progress_callback(
                    f"Mining claims ({completed}/{total})",
                    10 + (completed * 40) // total,
                    100,
                )
                if progress_callback
                else None
            ),
        )
        mining_time = time.time() - mining_start

        # Step 3: Aggregate mining results
        all_claims = []
        for result in mining_results:
            if result and "claims" in result:
                all_claims.extend(result["claims"])

        logger.info(
            f"Mining completed: {len(all_claims)} claims extracted in {mining_time:.2f}s"
        )

        # Step 4: Parallel evaluation (Stage B)
        if progress_callback:
            progress_callback("Evaluating claims", 50, 100)

        evaluation_start = time.time()
        evaluation_results = await process_evaluation_parallel(
            all_claims,
            evaluator_func,
            self.hardware_specs,
            lambda completed, total: (
                progress_callback(
                    f"Evaluating claims ({completed}/{total})",
                    50 + (completed * 40) // total,
                    100,
                )
                if progress_callback
                else None
            ),
        )
        evaluation_time = time.time() - evaluation_start

        # Step 5: Aggregate final results
        final_claims = [result for result in evaluation_results if result]

        total_time = time.time() - start_time

        # Update performance stats
        self._update_performance_stats(
            len(chunks),
            len(all_claims),
            len(final_claims),
            mining_time,
            evaluation_time,
            total_time,
        )

        if progress_callback:
            progress_callback("Processing complete", 100, 100)

        logger.info(
            f"HCE Pipeline completed: {len(final_claims)} final claims in {total_time:.2f}s "
            f"(Mining: {mining_time:.2f}s, Evaluation: {evaluation_time:.2f}s)"
        )

        return {
            "claims": final_claims,
            "metadata": {
                "total_chunks": len(chunks),
                "total_claims_extracted": len(all_claims),
                "total_claims_evaluated": len(final_claims),
                "mining_time": mining_time,
                "evaluation_time": evaluation_time,
                "total_time": total_time,
                "parallelization_efficiency": self.processing_stats[
                    "parallelization_efficiency"
                ],
                "hardware_optimization": self._get_hardware_optimization_status(),
            },
        }

    def _create_chunks(self, content: str, chunk_size: int, overlap: int) -> list[str]:
        """Create overlapping chunks from content"""
        chunks = []
        start = 0

        while start < len(content):
            end = min(start + chunk_size, len(content))
            chunk = content[start:end]
            chunks.append(chunk)
            start = end - overlap

            if start >= len(content):
                break

        return chunks

    def _update_performance_stats(
        self,
        chunks_processed: int,
        claims_extracted: int,
        claims_evaluated: int,
        mining_time: float,
        evaluation_time: float,
        total_time: float,
    ):
        """Update performance statistics"""
        self.processing_stats["total_chunks_processed"] += chunks_processed
        self.processing_stats["total_claims_extracted"] += claims_extracted
        self.processing_stats["total_claims_evaluated"] += claims_evaluated

        # Calculate average times
        if self.processing_stats["total_chunks_processed"] > 0:
            self.processing_stats["avg_mining_time"] = (
                self.processing_stats["avg_mining_time"] + mining_time
            ) / 2

        if self.processing_stats["total_claims_evaluated"] > 0:
            self.processing_stats["avg_evaluation_time"] = (
                self.processing_stats["avg_evaluation_time"] + evaluation_time
            ) / 2

        # Calculate parallelization efficiency
        sequential_time_estimate = (mining_time + evaluation_time) * 2  # Rough estimate
        if sequential_time_estimate > 0:
            self.processing_stats["parallelization_efficiency"] = (
                sequential_time_estimate / total_time
            )

    def _get_hardware_optimization_status(self) -> dict[str, Any]:
        """Get current hardware optimization status"""
        memory_gb = self.hardware_specs.get("memory_gb", 16)
        chip_type = self.hardware_specs.get("chip_type", "").lower()

        # Determine optimization level
        if memory_gb >= 64 and ("ultra" in chip_type or "max" in chip_type):
            optimization_level = "Maximum"
            model_type = "Qwen2.5-14B FP16"
            parallelization_level = "Aggressive"
        elif memory_gb >= 32 and ("max" in chip_type or "pro" in chip_type):
            optimization_level = "High"
            model_type = "Qwen2.5-14B FP16"
            parallelization_level = "Moderate"
        elif memory_gb >= 16:
            optimization_level = "Balanced"
            model_type = "Qwen2.5-7B"
            parallelization_level = "Conservative"
        else:
            optimization_level = "Basic"
            model_type = "Qwen2.5-3B"
            parallelization_level = "Minimal"

        return {
            "optimization_level": optimization_level,
            "model_type": model_type,
            "parallelization_level": parallelization_level,
            "memory_gb": memory_gb,
            "chip_type": chip_type,
        }

    def get_resource_status(self) -> dict[str, Any]:
        """Get current resource utilization status"""
        resource_status = self.processor.get_resource_status()
        resource_status["processing_stats"] = self.processing_stats
        resource_status[
            "hardware_optimization"
        ] = self._get_hardware_optimization_status()
        return resource_status

    def save_performance_data(self, filepath: Path):
        """Save performance data for analysis"""
        self.processor.save_performance_data(filepath)

        # Also save HCE-specific stats
        hce_stats_file = filepath.parent / f"hce_stats_{filepath.stem}.json"
        import json

        with open(hce_stats_file, "w") as f:
            json.dump(
                {
                    "processing_stats": self.processing_stats,
                    "hardware_optimization": self._get_hardware_optimization_status(),
                    "hardware_specs": self.hardware_specs,
                },
                f,
                indent=2,
            )

        logger.info(f"Saved HCE performance data to {hce_stats_file}")

    def shutdown(self):
        """Shutdown the enhanced HCE pipeline"""
        self.processor.shutdown()
        logger.info("Enhanced HCE Pipeline shutdown complete")


# Convenience function for creating and using the enhanced pipeline
def create_enhanced_hce_pipeline(hardware_specs: dict[str, Any]) -> EnhancedHCEPipeline:
    """Create an enhanced HCE pipeline with dynamic parallelization"""
    return EnhancedHCEPipeline(hardware_specs)


# Integration function for existing code
async def process_with_enhanced_hce(
    content: str,
    miner_func: Callable[[str], dict[str, Any]],
    evaluator_func: Callable[[dict[str, Any]], dict[str, Any]],
    hardware_specs: dict[str, Any],
    chunk_size: int = 2000,
    overlap: int = 200,
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> dict[str, Any]:
    """
    Process content with enhanced HCE pipeline and dynamic parallelization.

    This is a drop-in replacement for existing HCE processing functions.
    """
    pipeline = create_enhanced_hce_pipeline(hardware_specs)

    try:
        return await pipeline.process_document_parallel(
            content, miner_func, evaluator_func, chunk_size, overlap, progress_callback
        )
    finally:
        pipeline.shutdown()
