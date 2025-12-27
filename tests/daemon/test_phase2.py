"""
Phase 2 Daemon Tests

Tests for the full processing pipeline:
1. API key configuration endpoint
2. Full pipeline integration (mocked)
3. Processing service with all stages

Note: Full pipeline tests require actual API keys and are marked as integration tests.
Unit tests use mocking to verify the pipeline structure.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from fastapi.testclient import TestClient

from daemon.main import app


@pytest.fixture
def client():
    """Create test client for the daemon app."""
    return TestClient(app)


class TestAPIKeyConfiguration:
    """Tests for /api/config/api-keys endpoint."""

    def test_get_api_key_status(self, client):
        """Can check API key configuration status."""
        response = client.get("/api/config/api-keys")
        assert response.status_code == 200
        
        data = response.json()
        assert "openai_configured" in data
        assert "anthropic_configured" in data
        assert isinstance(data["openai_configured"], bool)
        assert isinstance(data["anthropic_configured"], bool)

    def test_set_api_keys(self, client):
        """Can set API keys."""
        response = client.post(
            "/api/config/api-keys",
            json={
                "openai_api_key": "sk-test-key",
            },
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "configured"
        assert data["openai_configured"] is True

    def test_set_anthropic_key(self, client):
        """Can set Anthropic API key."""
        response = client.post(
            "/api/config/api-keys",
            json={
                "anthropic_api_key": "sk-ant-test-key",
            },
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "configured"
        assert data["anthropic_configured"] is True


class TestProcessingServiceIntegration:
    """Tests for the processing service with all stages."""

    def test_process_request_with_all_stages(self, client):
        """Can submit a request with all stages enabled."""
        response = client.post(
            "/api/process",
            json={
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "source_type": "youtube",
                "transcribe": True,
                "extract_claims": True,
                "auto_upload": True,
            },
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "queued"

    def test_job_status_has_stages(self, client):
        """Job status includes stage information."""
        # Submit job
        submit_response = client.post(
            "/api/process",
            json={
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "transcribe": True,
                "extract_claims": True,
                "auto_upload": True,
            },
        )
        job_id = submit_response.json()["job_id"]

        # Get status
        status_response = client.get(f"/api/jobs/{job_id}")
        data = status_response.json()

        assert "stages_complete" in data
        assert "stages_remaining" in data
        assert isinstance(data["stages_complete"], list)
        assert isinstance(data["stages_remaining"], list)

    def test_process_with_custom_llm_provider(self, client):
        """Can specify custom LLM provider."""
        response = client.post(
            "/api/process",
            json={
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "llm_provider": "anthropic",
                "llm_model": "claude-3-5-sonnet-20241022",
            },
        )
        assert response.status_code == 200
        assert "job_id" in response.json()


class TestProcessingServiceMocked:
    """Unit tests with mocked processors to verify pipeline structure."""

    def test_processing_service_stages_are_tracked(self):
        """Processing service properly tracks stages."""
        from daemon.services.processing_service import ProcessingService
        from daemon.models.schemas import ProcessRequest

        service = ProcessingService()
        
        # Verify the service initializes properly
        assert service.jobs == {}
        assert len(service.list_jobs()) == 0

    def test_prepare_upload_data_empty_extraction(self):
        """_prepare_upload_data handles empty extraction."""
        from daemon.services.processing_service import ProcessingService

        service = ProcessingService()
        
        # Empty job data
        result = service._prepare_upload_data({})
        assert result == {}

    def test_prepare_upload_data_with_extraction(self):
        """_prepare_upload_data properly formats extraction data."""
        from daemon.services.processing_service import ProcessingService
        from dataclasses import dataclass
        
        service = ProcessingService()
        
        # Mock extraction result
        @dataclass
        class MockExtraction:
            claims = [{"claim_text": "Test claim", "importance": 8}]
            people = [{"name": "John Doe"}]
            jargon = [{"term": "API", "definition": "Application Programming Interface"}]
            concepts = [{"name": "REST", "description": "Representational State Transfer"}]
        
        @dataclass
        class MockResult:
            extraction = MockExtraction()
        
        job_data = {
            "extraction_result": MockResult(),
            "source_id": "test123",
            "metadata": {"title": "Test Video", "channel": "Test Channel"},
        }
        
        result = service._prepare_upload_data(job_data)
        
        assert "episodes" in result
        assert "claims" in result
        assert "people" in result
        assert "jargon" in result
        assert "concepts" in result
        assert len(result["claims"]) == 1
        assert result["claims"][0]["claim_text"] == "Test claim"

