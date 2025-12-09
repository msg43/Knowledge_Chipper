"""
Base Batch Client Interface

Provides abstract base class and data models for batch API clients.
Supports OpenAI and Anthropic batch APIs with cache tracking.
"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class BatchStatus(Enum):
    """Status of a batch job."""
    PENDING = "pending"
    VALIDATING = "validating"
    IN_PROGRESS = "in_progress"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass
class BatchRequest:
    """A single request to be included in a batch."""
    custom_id: str              # Unique ID for tracking (e.g., "source_id:segment_id")
    messages: list[dict]        # Chat messages
    model: str                  # Model to use
    temperature: float = 0.1
    max_tokens: int = 4000
    response_format: dict | None = None  # Optional JSON mode config
    
    def to_openai_format(self) -> dict:
        """Convert to OpenAI batch request format."""
        body = {
            "model": self.model,
            "messages": self.messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if self.response_format:
            body["response_format"] = self.response_format
        
        return {
            "custom_id": self.custom_id,
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": body
        }
    
    def to_anthropic_format(self) -> dict:
        """Convert to Anthropic batch request format."""
        return {
            "custom_id": self.custom_id,
            "params": {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "messages": self.messages
            }
        }


@dataclass
class BatchJob:
    """Represents a batch job submitted to a provider."""
    batch_id: str
    provider: str               # "openai" or "anthropic"
    status: BatchStatus
    created_at: datetime
    request_count: int
    completed_count: int = 0
    failed_count: int = 0
    input_file_id: str | None = None    # OpenAI file ID
    output_file_id: str | None = None   # OpenAI output file ID
    error_message: str | None = None
    metadata: dict = field(default_factory=dict)
    
    # Cache metrics
    total_input_tokens: int = 0
    cached_tokens: int = 0
    
    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        if self.total_input_tokens == 0:
            return 0.0
        return self.cached_tokens / self.total_input_tokens
    
    @property
    def is_complete(self) -> bool:
        """Check if batch is in a terminal state."""
        return self.status in (
            BatchStatus.COMPLETED,
            BatchStatus.FAILED,
            BatchStatus.EXPIRED,
            BatchStatus.CANCELLED
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "batch_id": self.batch_id,
            "provider": self.provider,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "request_count": self.request_count,
            "completed_count": self.completed_count,
            "failed_count": self.failed_count,
            "input_file_id": self.input_file_id,
            "output_file_id": self.output_file_id,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "total_input_tokens": self.total_input_tokens,
            "cached_tokens": self.cached_tokens,
        }


@dataclass
class BatchResult:
    """Result of a single request within a batch."""
    custom_id: str
    success: bool
    content: str | None = None      # Response content if success
    error: str | None = None        # Error message if failed
    usage: dict | None = None       # Token usage stats
    
    @property
    def tokens_input(self) -> int:
        """Get input token count."""
        if self.usage:
            return self.usage.get("prompt_tokens", 0)
        return 0
    
    @property
    def tokens_output(self) -> int:
        """Get output token count."""
        if self.usage:
            return self.usage.get("completion_tokens", 0)
        return 0
    
    @property
    def tokens_cached(self) -> int:
        """Get cached token count (OpenAI prompt caching)."""
        if self.usage:
            return self.usage.get("cached_tokens", 0)
        return 0
    
    def parse_json_content(self) -> dict | None:
        """Parse content as JSON, returning None if invalid."""
        if not self.content:
            return None
        try:
            return json.loads(self.content)
        except json.JSONDecodeError:
            return None


@dataclass
class BatchPipelineResult:
    """Result of the full batch pipeline."""
    miner_outputs: dict[str, Any]
    evaluation: Any  # FlagshipEvaluationOutput
    episodes_processed: int
    segments_processed: int
    cache_stats: dict = field(default_factory=dict)
    
    @property
    def total_cost_savings(self) -> float:
        """Calculate total savings from caching."""
        return self.cache_stats.get("cost_savings", 0.0)


class BaseBatchClient(ABC):
    """Abstract base class for batch API clients."""
    
    # Subclasses should override this
    MAX_REQUESTS_PER_BATCH: int = 10000
    
    @abstractmethod
    async def create_batch(
        self, 
        requests: list[BatchRequest], 
        metadata: dict | None = None
    ) -> BatchJob:
        """
        Create and submit a batch job.
        
        Args:
            requests: List of batch requests
            metadata: Optional metadata to attach to the batch
            
        Returns:
            BatchJob with batch_id and initial status
        """
        pass
    
    @abstractmethod
    async def get_status(self, batch_id: str) -> BatchJob:
        """
        Get current status of a batch job.
        
        Args:
            batch_id: The batch ID to check
            
        Returns:
            Updated BatchJob with current status
        """
        pass
    
    @abstractmethod
    async def get_results(self, batch_id: str) -> list[BatchResult]:
        """
        Get results of a completed batch.
        
        Args:
            batch_id: The batch ID to retrieve results for
            
        Returns:
            List of BatchResult objects
        """
        pass
    
    @abstractmethod
    async def cancel(self, batch_id: str) -> bool:
        """
        Cancel a batch job.
        
        Args:
            batch_id: The batch ID to cancel
            
        Returns:
            True if cancellation was successful
        """
        pass
    
    @abstractmethod
    async def list_batches(self, limit: int = 20) -> list[BatchJob]:
        """
        List recent batch jobs.
        
        Args:
            limit: Maximum number of batches to return
            
        Returns:
            List of BatchJob objects
        """
        pass
    
    def chunk_requests(
        self, 
        requests: list[BatchRequest], 
        max_per_batch: int | None = None
    ) -> list[list[BatchRequest]]:
        """
        Split requests into chunks that fit within batch limits.
        
        Args:
            requests: All requests to chunk
            max_per_batch: Override for max requests per batch
            
        Returns:
            List of request chunks
        """
        max_size = max_per_batch or self.MAX_REQUESTS_PER_BATCH
        chunks = []
        for i in range(0, len(requests), max_size):
            chunks.append(requests[i:i + max_size])
        return chunks

