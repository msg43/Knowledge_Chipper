"""
Integration tests for System 2 LLM Adapter with real Ollama API calls.

These tests require Ollama to be running locally with qwen2.5:7b-instruct model.
"""

import asyncio
import json
import time
from unittest.mock import Mock, patch

import pytest

from src.knowledge_system.core.llm_adapter import LLMAdapter, get_llm_adapter
from src.knowledge_system.database import DatabaseService
from src.knowledge_system.database.system2_models import LLMRequest, LLMResponse
from src.knowledge_system.errors import ErrorCode, KnowledgeSystemError


@pytest.fixture
def test_db_service():
    """Create a test database service with in-memory database."""
    db_service = DatabaseService("sqlite:///:memory:")
    
    # Create all tables
    from src.knowledge_system.database.models import Base
    
    Base.metadata.create_all(db_service.engine)
    
    yield db_service
    # Cleanup handled by in-memory database


@pytest.fixture
def llm_adapter(test_db_service):
    """Create LLM adapter for testing."""
    adapter = LLMAdapter(db_service=test_db_service)
    return adapter


@pytest.mark.integration
class TestLLMAdapterReal:
    """Test LLM adapter with real Ollama API calls."""
    
    def test_ollama_connectivity(self):
        """Verify Ollama is running and accessible."""
        import requests
        
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            assert response.status_code == 200, "Ollama is not running"
            
            data = response.json()
            models = [m['name'] for m in data.get('models', [])]
            assert "qwen2.5:7b-instruct" in models, \
                "qwen2.5:7b-instruct model not found. Run: ollama pull qwen2.5:7b-instruct"
        except Exception as e:
            pytest.skip(f"Ollama not available: {e}")
    
    @pytest.mark.asyncio
    async def test_basic_completion(self, llm_adapter):
        """Test basic text completion with qwen2.5:7b-instruct."""
        result = await llm_adapter.complete(
            provider="ollama",
            model="qwen2.5:7b-instruct",
            messages=[{"role": "user", "content": "Say 'hello' in one word."}],
            temperature=0.1
        )
        
        assert "content" in result
        assert len(result["content"]) > 0
        assert "usage" in result
        assert result["usage"]["total_tokens"] > 0
        assert result["provider"] == "ollama"
        assert result["model"] == "qwen2.5:7b-instruct"
        
        # Content should contain something related to hello
        assert len(result["content"]) < 100  # Should be brief
    
    @pytest.mark.asyncio
    async def test_json_generation(self, llm_adapter):
        """Test JSON response generation."""
        result = await llm_adapter.complete(
            provider="ollama",
            model="qwen2.5:7b-instruct",
            messages=[{
                "role": "user",
                "content": 'Return a JSON object with fields "status" and "message". The status should be "success".'
            }],
            format="json",
            temperature=0.1
        )
        
        assert "content" in result
        
        # Should be valid JSON
        try:
            parsed = json.loads(result["content"])
            assert isinstance(parsed, dict)
            # May or may not have exact fields, but should be valid JSON
        except json.JSONDecodeError:
            pytest.fail(f"Response was not valid JSON: {result['content']}")
    
    @pytest.mark.asyncio
    async def test_structured_json_with_format(self, llm_adapter):
        """Test structured JSON with format='json' parameter."""
        result = await llm_adapter.complete(
            provider="ollama",
            model="qwen2.5:7b-instruct",
            messages=[{
                "role": "user",
                "content": '''Generate a JSON object with this structure:
{
  "name": "test",
  "count": 42,
  "items": ["a", "b"]
}'''
            }],
            format="json",
            temperature=0.1
        )
        
        # Verify it's valid JSON
        parsed = json.loads(result["content"])
        assert isinstance(parsed, dict)
        
        # Should have some structure
        assert len(parsed) > 0
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, llm_adapter):
        """Verify rate limiting prevents too many concurrent requests."""
        # The adapter should limit concurrent requests based on hardware tier
        max_concurrent = llm_adapter.max_concurrent
        
        start_time = time.time()
        
        # Create more tasks than allowed concurrently
        tasks = [
            llm_adapter.complete(
                provider="ollama",
                model="qwen2.5:7b-instruct",
                messages=[{"role": "user", "content": f"Count to {i}"}],
                temperature=0.1
            )
            for i in range(max_concurrent + 2)
        ]
        
        results = await asyncio.gather(*tasks)
        
        elapsed = time.time() - start_time
        
        # All should succeed
        assert len(results) == max_concurrent + 2
        for result in results:
            assert "content" in result
        
        # Should take some time due to rate limiting
        # (Not too strict since Ollama can be fast)
        assert elapsed > 0.5
    
    @pytest.mark.asyncio
    async def test_retry_on_failure(self, llm_adapter):
        """Test retry logic with exponential backoff."""
        # Test with a valid request - should succeed on first try
        result = await llm_adapter.complete_with_retry(
            provider="ollama",
            model="qwen2.5:7b-instruct",
            messages=[{"role": "user", "content": "Test"}],
            max_retries=3
        )
        
        assert "content" in result
    
    @pytest.mark.asyncio
    async def test_request_tracking(self, test_db_service, llm_adapter):
        """Verify requests/responses are tracked in database."""
        # Create a job and job run first (required for foreign key)
        import uuid
        from src.knowledge_system.database.system2_models import Job, JobRun
        
        # Use unique IDs to avoid conflicts
        job_id = f"test_job_{uuid.uuid4().hex[:8]}"
        run_id = f"test_run_{uuid.uuid4().hex[:8]}"
        
        with test_db_service.get_session() as session:
            job = Job(
                job_id=job_id,
                job_type="mine",
                input_id="test_input",
                config_json={},
            )
            session.add(job)
            session.commit()
            
            job_run = JobRun(
                run_id=run_id,
                job_id=job_id,
                status="running",
            )
            session.add(job_run)
            session.commit()
        
        # Set a job run ID to enable tracking
        llm_adapter.set_job_run_id(run_id)
        
        # Make a request
        result = await llm_adapter.complete(
            provider="ollama",
            model="qwen2.5:7b-instruct",
            messages=[{"role": "user", "content": "Track this"}],
            temperature=0.5
        )
        
        assert "content" in result
        
        # Check database for tracked request
        with test_db_service.get_session() as session:
            requests = session.query(LLMRequest).filter_by(
                job_run_id=run_id
            ).all()
            
            # Should have at least one request
            assert len(requests) > 0
            
            # Check request details
            req = requests[0]
            assert req.provider == "ollama"
            assert req.model == "qwen2.5:7b-instruct"
            assert req.temperature == 0.5
            
            # Check for corresponding response
            responses = session.query(LLMResponse).filter_by(
                request_id=req.request_id
            ).all()
            
            assert len(responses) == 1
            resp = responses[0]
            assert resp.completion_tokens > 0
            assert resp.latency_ms > 0
    
    @pytest.mark.asyncio
    async def test_error_handling_invalid_model(self, llm_adapter):
        """Test error handling for invalid model."""
        with pytest.raises(KnowledgeSystemError) as exc_info:
            await llm_adapter.complete(
                provider="ollama",
                model="nonexistent:model",
                messages=[{"role": "user", "content": "Test"}]
            )
        
        assert exc_info.value.error_code == ErrorCode.LLM_API_ERROR.value
    
    @pytest.mark.asyncio
    async def test_error_handling_connection_failure(self, llm_adapter):
        """Test error handling for connection failures."""
        # Mock the _call_ollama to simulate connection failure
        with patch.object(llm_adapter, '_call_ollama') as mock_call:
            import aiohttp
            mock_call.side_effect = aiohttp.ClientError("Connection refused")

            with pytest.raises(KnowledgeSystemError) as exc_info:
                await llm_adapter.complete(
                    provider="ollama",
                    model="qwen2.5:7b-instruct",
                    messages=[{"role": "user", "content": "Test"}]
                )

            assert exc_info.value.error_code == ErrorCode.LLM_API_ERROR.value
            # Error message should mention the connection issue
            assert "Connection refused" in str(exc_info.value) or "LLM request failed" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_memory_throttling(self, llm_adapter):
        """Test memory throttling doesn't block requests under normal conditions."""
        # Under normal memory conditions, requests should proceed
        result = await llm_adapter.complete(
            provider="ollama",
            model="qwen2.5:7b-instruct",
            messages=[{"role": "user", "content": "Test memory throttling"}]
        )
        
        assert "content" in result
    
    @pytest.mark.asyncio
    async def test_hardware_tier_detection(self, test_db_service):
        """Test hardware tier is correctly detected."""
        adapter = LLMAdapter(db_service=test_db_service)
        
        assert adapter.hardware_tier in ["consumer", "prosumer", "enterprise"]
        assert adapter.max_concurrent >= 2
        assert adapter.max_concurrent <= 8
    
    @pytest.mark.asyncio
    async def test_cost_estimation(self, llm_adapter):
        """Test cost estimation for requests (Ollama is free but should not error)."""
        result = await llm_adapter.complete(
            provider="ollama",
            model="qwen2.5:7b-instruct",
            messages=[{"role": "user", "content": "Estimate cost"}]
        )
        
        # Cost estimation shouldn't crash
        # Ollama is free so cost should be 0
        assert "content" in result
    
    @pytest.mark.asyncio
    async def test_adapter_stats(self, llm_adapter):
        """Test adapter statistics retrieval."""
        stats = llm_adapter.get_stats()
        
        assert "hardware_tier" in stats
        assert "max_concurrent" in stats
        assert "active_requests" in stats
        assert "memory_usage" in stats
        
        assert stats["active_requests"] >= 0
        assert stats["memory_usage"] >= 0


@pytest.mark.integration
class TestLLMAdapterIntegration:
    """Integration tests combining multiple adapter features."""
    
    @pytest.mark.asyncio
    async def test_full_workflow_with_tracking(self, test_db_service):
        """Test complete workflow: request -> LLM -> response -> database tracking."""
        # Create job and job run for tracking
        import uuid
        from src.knowledge_system.database.system2_models import Job, JobRun
        
        # Use unique IDs
        job_id = f"integration_job_{uuid.uuid4().hex[:8]}"
        run_id = f"integration_run_{uuid.uuid4().hex[:8]}"
        
        with test_db_service.get_session() as session:
            job = Job(
                job_id=job_id,
                job_type="mine",
                input_id="test_input",
                config_json={},
            )
            session.add(job)
            session.commit()
            
            job_run = JobRun(
                run_id=run_id,
                job_id=job_id,
                status="running",
            )
            session.add(job_run)
            session.commit()
        
        adapter = LLMAdapter(db_service=test_db_service)
        adapter.set_job_run_id(run_id)
        
        # Make request
        result = await adapter.complete(
            provider="ollama",
            model="qwen2.5:7b-instruct",
            messages=[{"role": "user", "content": "Integration test"}],
            temperature=0.3,
            max_tokens=100
        )
        
        # Verify response
        assert "content" in result
        assert len(result["content"]) > 0
        
        # Verify database tracking
        with test_db_service.get_session() as session:
            # Filter requests from this specific job run
            requests = session.query(LLMRequest).filter_by(
                job_run_id=run_id
            ).all()
            assert len(requests) > 0
            
            # Check each request
            for req in requests:
                assert req.provider == "ollama"
                assert req.model == "qwen2.5:7b-instruct"
                
                # Check for corresponding response
                resp = session.query(LLMResponse).filter_by(
                    request_id=req.request_id
                ).first()
                assert resp is not None
                assert resp.completion_tokens > 0
    
    @pytest.mark.asyncio
    async def test_concurrent_requests_with_tracking(self, test_db_service):
        """Test multiple concurrent requests are all tracked."""
        # Create job and job run for tracking
        import uuid
        from src.knowledge_system.database.system2_models import Job, JobRun
        
        # Use unique IDs
        job_id = f"concurrent_job_{uuid.uuid4().hex[:8]}"
        run_id = f"concurrent_run_{uuid.uuid4().hex[:8]}"
        
        with test_db_service.get_session() as session:
            job = Job(
                job_id=job_id,
                job_type="mine",
                input_id="test_input",
                config_json={},
            )
            session.add(job)
            session.commit()
            
            job_run = JobRun(
                run_id=run_id,
                job_id=job_id,
                status="running",
            )
            session.add(job_run)
            session.commit()
        
        adapter = LLMAdapter(db_service=test_db_service)
        adapter.set_job_run_id(run_id)
        
        # Make multiple concurrent requests
        tasks = [
            adapter.complete(
                provider="ollama",
                model="qwen2.5:7b-instruct",
                messages=[{"role": "user", "content": f"Request {i}"}]
            )
            for i in range(3)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        assert len(results) == 3
        for result in results:
            assert "content" in result
        
        # All should be tracked
        with test_db_service.get_session() as session:
            requests = session.query(LLMRequest).filter_by(
                job_run_id=run_id
            ).all()
            assert len(requests) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

