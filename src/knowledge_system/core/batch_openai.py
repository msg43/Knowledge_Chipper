"""
OpenAI Batch API Client

Implements batch processing for OpenAI models with:
- JSONL file upload
- Batch job creation and polling
- Result download and parsing
- Prompt cache metrics tracking
"""

import asyncio
import io
import json
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


class OpenAIBatchClient(BaseBatchClient):
    """OpenAI Batch API client with prompt caching support."""
    
    MAX_REQUESTS_PER_BATCH = 50000
    
    def __init__(self, api_key: str | None = None):
        """
        Initialize OpenAI batch client.
        
        Args:
            api_key: OpenAI API key. If None, loads from settings.
        """
        self._api_key = api_key
        self._client = None
    
    def _get_client(self):
        """Get or create async OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError:
                raise ImportError(
                    "OpenAI package not installed. Run: pip install openai"
                )
            
            api_key = self._api_key
            if not api_key:
                from ..config import get_settings
                settings = get_settings()
                api_key = settings.api_keys.openai_api_key
            
            if not api_key:
                raise ValueError("OpenAI API key not configured")
            
            self._client = AsyncOpenAI(api_key=api_key)
        
        return self._client
    
    async def create_batch(
        self, 
        requests: list[BatchRequest], 
        metadata: dict | None = None
    ) -> BatchJob:
        """
        Create and submit a batch job to OpenAI.
        
        Args:
            requests: List of batch requests
            metadata: Optional metadata for the batch
            
        Returns:
            BatchJob with batch_id and initial status
        """
        client = self._get_client()
        
        # Build JSONL content
        jsonl_lines = []
        for req in requests:
            line = req.to_openai_format()
            jsonl_lines.append(json.dumps(line))
        
        jsonl_content = "\n".join(jsonl_lines)
        
        logger.info(f"Uploading batch file with {len(requests)} requests")
        
        # Upload file
        file_response = await client.files.create(
            file=io.BytesIO(jsonl_content.encode("utf-8")),
            purpose="batch"
        )
        
        logger.info(f"Uploaded batch file: {file_response.id}")
        
        # Create batch
        batch_metadata = metadata or {}
        batch_response = await client.batches.create(
            input_file_id=file_response.id,
            endpoint="/v1/chat/completions",
            completion_window="24h",
            metadata=batch_metadata
        )
        
        logger.info(f"Created batch: {batch_response.id}")
        
        return BatchJob(
            batch_id=batch_response.id,
            provider="openai",
            status=self._parse_status(batch_response.status),
            created_at=datetime.now(),
            request_count=len(requests),
            input_file_id=file_response.id,
            metadata=batch_metadata
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
        
        batch_response = await client.batches.retrieve(batch_id)
        
        # Parse request counts
        request_counts = batch_response.request_counts
        completed = request_counts.completed if request_counts else 0
        failed = request_counts.failed if request_counts else 0
        total = request_counts.total if request_counts else 0
        
        return BatchJob(
            batch_id=batch_id,
            provider="openai",
            status=self._parse_status(batch_response.status),
            created_at=datetime.fromtimestamp(batch_response.created_at),
            request_count=total,
            completed_count=completed,
            failed_count=failed,
            input_file_id=batch_response.input_file_id,
            output_file_id=batch_response.output_file_id,
            error_message=self._get_error_message(batch_response),
            metadata=batch_response.metadata or {}
        )
    
    async def get_results(self, batch_id: str) -> list[BatchResult]:
        """
        Get results of a completed batch.
        
        Args:
            batch_id: The batch ID to retrieve results for
            
        Returns:
            List of BatchResult objects with cache metrics
        """
        client = self._get_client()
        
        # Get batch to find output file
        batch_response = await client.batches.retrieve(batch_id)
        
        if not batch_response.output_file_id:
            logger.warning(f"Batch {batch_id} has no output file")
            return []
        
        # Download output file
        logger.info(f"Downloading results from {batch_response.output_file_id}")
        file_content = await client.files.content(batch_response.output_file_id)
        
        # Parse JSONL results
        results = []
        total_tokens = 0
        cached_tokens = 0
        
        for line in file_content.text.strip().split("\n"):
            if not line:
                continue
            
            try:
                result_data = json.loads(line)
                result = self._parse_result(result_data)
                results.append(result)
                
                # Track cache metrics
                if result.usage:
                    total_tokens += result.tokens_input
                    cached_tokens += result.tokens_cached
                    
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse result line: {e}")
                continue
        
        # Log cache metrics
        cache_hit_rate = cached_tokens / total_tokens if total_tokens > 0 else 0
        logger.info(
            f"Batch {batch_id} cache hit rate: {cache_hit_rate:.1%} "
            f"({cached_tokens:,}/{total_tokens:,} tokens)"
        )
        
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
            await client.batches.cancel(batch_id)
            logger.info(f"Cancelled batch: {batch_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel batch {batch_id}: {e}")
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
        
        batches_response = await client.batches.list(limit=limit)
        
        jobs = []
        for batch in batches_response.data:
            request_counts = batch.request_counts
            jobs.append(BatchJob(
                batch_id=batch.id,
                provider="openai",
                status=self._parse_status(batch.status),
                created_at=datetime.fromtimestamp(batch.created_at),
                request_count=request_counts.total if request_counts else 0,
                completed_count=request_counts.completed if request_counts else 0,
                failed_count=request_counts.failed if request_counts else 0,
                input_file_id=batch.input_file_id,
                output_file_id=batch.output_file_id,
                metadata=batch.metadata or {}
            ))
        
        return jobs
    
    def _parse_status(self, status_str: str) -> BatchStatus:
        """Parse OpenAI batch status to BatchStatus enum."""
        status_map = {
            "validating": BatchStatus.VALIDATING,
            "in_progress": BatchStatus.IN_PROGRESS,
            "finalizing": BatchStatus.FINALIZING,
            "completed": BatchStatus.COMPLETED,
            "failed": BatchStatus.FAILED,
            "expired": BatchStatus.EXPIRED,
            "cancelled": BatchStatus.CANCELLED,
            "cancelling": BatchStatus.CANCELLED,
        }
        return status_map.get(status_str, BatchStatus.PENDING)
    
    def _parse_result(self, result_data: dict) -> BatchResult:
        """Parse a single result from the output file."""
        custom_id = result_data.get("custom_id", "")
        response = result_data.get("response", {})
        error = result_data.get("error")
        
        if error:
            return BatchResult(
                custom_id=custom_id,
                success=False,
                error=str(error)
            )
        
        # Extract response body
        body = response.get("body", {})
        choices = body.get("choices", [])
        usage = body.get("usage", {})
        
        content = None
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content", "")
        
        return BatchResult(
            custom_id=custom_id,
            success=True,
            content=content,
            usage=usage
        )
    
    def _get_error_message(self, batch_response: Any) -> str | None:
        """Extract error message from batch response."""
        if hasattr(batch_response, "errors") and batch_response.errors:
            errors = batch_response.errors
            if hasattr(errors, "data") and errors.data:
                return str(errors.data[0])
        return None


async def test_openai_batch_client():
    """Test the OpenAI batch client."""
    client = OpenAIBatchClient()
    
    # List existing batches
    batches = await client.list_batches(limit=5)
    print(f"Found {len(batches)} batches")
    
    for batch in batches:
        print(f"  {batch.batch_id}: {batch.status.value} ({batch.completed_count}/{batch.request_count})")


if __name__ == "__main__":
    asyncio.run(test_openai_batch_client())

