"""
Anthropic Batch API Client

Implements batch processing for Anthropic Claude models with:
- Message batches API
- Batch job creation and polling
- Result retrieval
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

from .batch_client import (
    BaseBatchClient,
    BatchJob,
    BatchRequest,
    BatchResult,
    BatchStatus,
)

logger = logging.getLogger(__name__)


class AnthropicBatchClient(BaseBatchClient):
    """Anthropic Message Batches API client."""
    
    MAX_REQUESTS_PER_BATCH = 10000
    
    def __init__(self, api_key: str | None = None):
        """
        Initialize Anthropic batch client.
        
        Args:
            api_key: Anthropic API key. If None, loads from settings.
        """
        self._api_key = api_key
        self._client = None
    
    def _get_client(self):
        """Get or create async Anthropic client."""
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic
            except ImportError:
                raise ImportError(
                    "Anthropic package not installed. Run: pip install anthropic"
                )
            
            api_key = self._api_key
            if not api_key:
                from ..config import get_settings
                settings = get_settings()
                api_key = settings.api_keys.anthropic_api_key
            
            if not api_key:
                raise ValueError("Anthropic API key not configured")
            
            self._client = AsyncAnthropic(api_key=api_key)
        
        return self._client
    
    async def create_batch(
        self, 
        requests: list[BatchRequest], 
        metadata: dict | None = None
    ) -> BatchJob:
        """
        Create and submit a batch job to Anthropic.
        
        Args:
            requests: List of batch requests
            metadata: Optional metadata for the batch
            
        Returns:
            BatchJob with batch_id and initial status
        """
        client = self._get_client()
        
        # Build Anthropic batch format
        batch_requests = []
        for req in requests:
            batch_requests.append(req.to_anthropic_format())
        
        logger.info(f"Creating Anthropic batch with {len(requests)} requests")
        
        # Create batch
        batch_response = await client.messages.batches.create(
            requests=batch_requests
        )
        
        logger.info(f"Created Anthropic batch: {batch_response.id}")
        
        return BatchJob(
            batch_id=batch_response.id,
            provider="anthropic",
            status=self._parse_status(batch_response.processing_status),
            created_at=datetime.now(),
            request_count=len(requests),
            metadata=metadata or {}
        )
    
    async def get_status(self, batch_id: str) -> BatchJob:
        """
        Get current status of a batch job.
        
        Args:
            batch_id: The batch ID to check
            
        Returns:
            Updated BatchJob with current status
        """
        client = self._get_client()
        
        batch_response = await client.messages.batches.retrieve(batch_id)
        
        # Parse request counts
        request_counts = batch_response.request_counts
        completed = request_counts.succeeded if request_counts else 0
        failed = (
            (request_counts.errored if request_counts else 0) +
            (request_counts.canceled if request_counts else 0) +
            (request_counts.expired if request_counts else 0)
        )
        total = (
            completed + failed +
            (request_counts.processing if request_counts else 0)
        )
        
        return BatchJob(
            batch_id=batch_id,
            provider="anthropic",
            status=self._parse_status(batch_response.processing_status),
            created_at=datetime.fromisoformat(
                batch_response.created_at.replace("Z", "+00:00")
            ) if hasattr(batch_response, "created_at") else datetime.now(),
            request_count=total,
            completed_count=completed,
            failed_count=failed,
            metadata={}
        )
    
    async def get_results(self, batch_id: str) -> list[BatchResult]:
        """
        Get results of a completed batch.
        
        Args:
            batch_id: The batch ID to retrieve results for
            
        Returns:
            List of BatchResult objects
        """
        client = self._get_client()
        
        logger.info(f"Retrieving results for Anthropic batch {batch_id}")
        
        results = []
        
        # Stream results from the batch
        async for result in client.messages.batches.results(batch_id):
            parsed_result = self._parse_result(result)
            results.append(parsed_result)
        
        logger.info(f"Retrieved {len(results)} results from batch {batch_id}")
        
        return results
    
    async def cancel(self, batch_id: str) -> bool:
        """
        Cancel a batch job.
        
        Args:
            batch_id: The batch ID to cancel
            
        Returns:
            True if cancellation was successful
        """
        client = self._get_client()
        
        try:
            await client.messages.batches.cancel(batch_id)
            logger.info(f"Cancelled Anthropic batch: {batch_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel Anthropic batch {batch_id}: {e}")
            return False
    
    async def list_batches(self, limit: int = 20) -> list[BatchJob]:
        """
        List recent batch jobs.
        
        Args:
            limit: Maximum number of batches to return
            
        Returns:
            List of BatchJob objects
        """
        client = self._get_client()
        
        batches_response = await client.messages.batches.list(limit=limit)
        
        jobs = []
        for batch in batches_response.data:
            request_counts = batch.request_counts
            completed = request_counts.succeeded if request_counts else 0
            failed = (
                (request_counts.errored if request_counts else 0) +
                (request_counts.canceled if request_counts else 0)
            )
            total = completed + failed + (request_counts.processing if request_counts else 0)
            
            jobs.append(BatchJob(
                batch_id=batch.id,
                provider="anthropic",
                status=self._parse_status(batch.processing_status),
                created_at=datetime.fromisoformat(
                    batch.created_at.replace("Z", "+00:00")
                ) if hasattr(batch, "created_at") else datetime.now(),
                request_count=total,
                completed_count=completed,
                failed_count=failed,
                metadata={}
            ))
        
        return jobs
    
    def _parse_status(self, status_str: str) -> BatchStatus:
        """Parse Anthropic batch status to BatchStatus enum."""
        status_map = {
            "in_progress": BatchStatus.IN_PROGRESS,
            "ended": BatchStatus.COMPLETED,
            "canceling": BatchStatus.CANCELLED,
            "canceled": BatchStatus.CANCELLED,
        }
        return status_map.get(status_str, BatchStatus.PENDING)
    
    def _parse_result(self, result: Any) -> BatchResult:
        """Parse a single result from the batch."""
        custom_id = result.custom_id
        
        # Check for error
        if result.result.type == "error":
            return BatchResult(
                custom_id=custom_id,
                success=False,
                error=str(result.result.error)
            )
        
        # Extract message content
        message = result.result.message
        content = ""
        
        for block in message.content:
            if hasattr(block, "text"):
                content += block.text
        
        # Build usage dict
        usage = {
            "prompt_tokens": message.usage.input_tokens,
            "completion_tokens": message.usage.output_tokens,
            "total_tokens": message.usage.input_tokens + message.usage.output_tokens,
            # Anthropic doesn't expose cached tokens in the same way
            "cached_tokens": 0
        }
        
        return BatchResult(
            custom_id=custom_id,
            success=True,
            content=content,
            usage=usage
        )


async def test_anthropic_batch_client():
    """Test the Anthropic batch client."""
    client = AnthropicBatchClient()
    
    # List existing batches
    batches = await client.list_batches(limit=5)
    print(f"Found {len(batches)} batches")
    
    for batch in batches:
        print(f"  {batch.batch_id}: {batch.status.value} ({batch.completed_count}/{batch.request_count})")


if __name__ == "__main__":
    asyncio.run(test_anthropic_batch_client())

