"""
Phase 1 Daemon Tests

Tests for the minimal FastAPI daemon functionality:
1. Health endpoint responds
2. Process endpoint accepts YouTube URL and returns job ID
3. Jobs endpoint returns job status

These tests use FastAPI's TestClient for synchronous testing.
"""

import sys
from pathlib import Path

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


class TestHealthEndpoint:
    """Tests for /api/health endpoint."""

    def test_health_endpoint_returns_200(self, client):
        """Daemon responds to health check with 200 OK."""
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_health_endpoint_returns_healthy_status(self, client):
        """Health response includes healthy status."""
        response = client.get("/api/health")
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_endpoint_includes_version(self, client):
        """Health response includes version string."""
        response = client.get("/api/health")
        data = response.json()
        assert "version" in data
        assert isinstance(data["version"], str)

    def test_health_endpoint_includes_capabilities(self, client):
        """Health response includes capabilities list."""
        response = client.get("/api/health")
        data = response.json()
        assert "capabilities" in data
        assert "youtube_download" in data["capabilities"]


class TestProcessEndpoint:
    """Tests for /api/process endpoint."""

    def test_process_endpoint_accepts_youtube_url(self, client):
        """Can submit YouTube URL and get 200 response."""
        response = client.post(
            "/api/process",
            json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        )
        assert response.status_code == 200

    def test_process_endpoint_returns_job_id(self, client):
        """Process response includes job_id."""
        response = client.post(
            "/api/process",
            json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        )
        data = response.json()
        assert "job_id" in data
        assert isinstance(data["job_id"], str)
        assert len(data["job_id"]) > 0

    def test_process_endpoint_returns_queued_status(self, client):
        """Process response shows job is queued."""
        response = client.post(
            "/api/process",
            json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        )
        data = response.json()
        assert data["status"] == "queued"


class TestJobsEndpoint:
    """Tests for /api/jobs/{id} endpoint."""

    def test_job_status_returns_valid_status(self, client):
        """Can query job status after submitting."""
        # First, submit a job
        submit_response = client.post(
            "/api/process",
            json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        )
        job_id = submit_response.json()["job_id"]

        # Then query its status
        status_response = client.get(f"/api/jobs/{job_id}")
        assert status_response.status_code == 200

        data = status_response.json()
        assert data["job_id"] == job_id
        assert data["status"] in [
            "queued",
            "downloading",
            "transcribing",
            "extracting",
            "uploading",
            "complete",
            "failed",
        ]

    def test_job_status_includes_progress(self, client):
        """Job status includes progress field."""
        # Submit a job
        submit_response = client.post(
            "/api/process",
            json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        )
        job_id = submit_response.json()["job_id"]

        # Query status
        status_response = client.get(f"/api/jobs/{job_id}")
        data = status_response.json()

        assert "progress" in data
        assert 0.0 <= data["progress"] <= 1.0

    def test_nonexistent_job_returns_404(self, client):
        """Querying nonexistent job returns 404."""
        response = client.get("/api/jobs/nonexistent-job-id")
        assert response.status_code == 404


class TestJobsListEndpoint:
    """Tests for /api/jobs endpoint (list all jobs)."""

    def test_jobs_list_returns_200(self, client):
        """Jobs list endpoint returns 200."""
        response = client.get("/api/jobs")
        assert response.status_code == 200

    def test_jobs_list_includes_counts(self, client):
        """Jobs list includes total, active, completed, failed counts."""
        response = client.get("/api/jobs")
        data = response.json()

        assert "total" in data
        assert "active" in data
        assert "completed" in data
        assert "failed" in data
        assert "jobs" in data

