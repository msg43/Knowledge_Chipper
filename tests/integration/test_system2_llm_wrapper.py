"""
Integration tests for System2LLM wrapper.

Tests that System2LLM properly wraps LLMAdapter with:
- Sync/async compatibility
- JSON generation
- Structured output for Ollama
- Error handling and retries
- Job run ID tracking
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from knowledge_system.processors.hce.models.llm_system2 import (
    System2LLM,
    create_system2_llm,
)


class TestSystem2LLMBasics:
    """Test basic System2LLM functionality."""

    def test_import(self):
        """Test that System2LLM can be imported."""
        assert System2LLM is not None

    def test_initialization(self):
        """Test System2LLM initialization with different providers."""
        # Test with defaults
        llm = System2LLM()
        assert llm.provider == "ollama"
        assert llm.model == "qwen2.5:7b-instruct"

        # Test with OpenAI
        llm = System2LLM(provider="openai", model="gpt-4")
        assert llm.provider == "openai"
        assert llm.model == "gpt-4"

        # Test with default models
        llm = System2LLM(provider="anthropic")
        assert llm.model == "claude-3-sonnet"

    def test_factory_function(self):
        """Test create_system2_llm factory function."""
        llm = create_system2_llm(provider="openai", model="gpt-3.5-turbo")
        assert isinstance(llm, System2LLM)
        assert llm.provider == "openai"
        assert llm.model == "gpt-3.5-turbo"


class TestSystem2LLMCompletion:
    """Test completion functionality."""

    @patch("knowledge_system.processors.hce.models.llm_system2.get_llm_adapter")
    def test_complete_calls_adapter(self, mock_get_adapter):
        """Test that complete() properly calls the LLM adapter."""
        # Mock the adapter
        mock_adapter = MagicMock()
        mock_adapter.complete_with_retry = AsyncMock(
            return_value={"content": "Test response"}
        )
        mock_get_adapter.return_value = mock_adapter

        llm = System2LLM(provider="openai", model="gpt-3.5-turbo")

        # Call complete
        result = llm.complete("Test prompt")

        # Verify it returns the content
        assert result == "Test response"

    @patch("knowledge_system.processors.hce.models.llm_system2.get_llm_adapter")
    def test_complete_handles_empty_response(self, mock_get_adapter):
        """Test that complete() handles empty responses gracefully."""
        mock_adapter = MagicMock()
        mock_adapter.complete_with_retry = AsyncMock(return_value={})
        mock_get_adapter.return_value = mock_adapter

        llm = System2LLM(provider="openai")
        result = llm.complete("Test")

        # Should return empty string if no content
        assert result == ""


class TestSystem2LLMJsonGeneration:
    """Test JSON generation functionality."""

    @patch("knowledge_system.processors.hce.models.llm_system2.get_llm_adapter")
    def test_generate_json_valid_response(self, mock_get_adapter):
        """Test JSON generation with valid JSON response."""
        mock_adapter = MagicMock()
        mock_adapter.complete_with_retry = AsyncMock(
            return_value={"content": '{"key": "value", "number": 42}'}
        )
        mock_get_adapter.return_value = mock_adapter

        llm = System2LLM(provider="openai")
        result = llm.generate_json("Generate JSON")

        assert isinstance(result, dict)
        assert result["key"] == "value"
        assert result["number"] == 42

    @patch("knowledge_system.processors.hce.models.llm_system2.get_llm_adapter")
    def test_generate_json_extracts_from_text(self, mock_get_adapter):
        """Test JSON extraction from text with surrounding content."""
        mock_adapter = MagicMock()
        mock_adapter.complete_with_retry = AsyncMock(
            return_value={
                "content": 'Here is the JSON: {"extracted": true} and more text'
            }
        )
        mock_get_adapter.return_value = mock_adapter

        llm = System2LLM(provider="openai")
        result = llm.generate_json("Generate JSON")

        assert isinstance(result, dict)
        assert result["extracted"] is True

    @patch("knowledge_system.processors.hce.models.llm_system2.get_llm_adapter")
    def test_generate_json_invalid_response(self, mock_get_adapter):
        """Test JSON generation with invalid JSON raises error."""
        from knowledge_system.errors import KnowledgeSystemError

        mock_adapter = MagicMock()
        mock_adapter.complete_with_retry = AsyncMock(
            return_value={"content": "This is not JSON at all"}
        )
        mock_get_adapter.return_value = mock_adapter

        llm = System2LLM(provider="openai")

        with pytest.raises(KnowledgeSystemError):
            llm.generate_json("Generate JSON")


class TestSystem2LLMStructuredOutput:
    """Test structured JSON generation (Ollama)."""

    @patch("knowledge_system.processors.hce.models.llm_system2.get_llm_adapter")
    def test_structured_json_ollama(self, mock_get_adapter):
        """Test structured JSON generation for Ollama."""
        mock_adapter = MagicMock()
        mock_adapter.complete_with_retry = AsyncMock(
            return_value={"content": '{"structured": "output"}'}
        )
        mock_get_adapter.return_value = mock_adapter

        llm = System2LLM(provider="ollama", model="qwen2.5:7b-instruct")
        result = llm.generate_structured_json("Generate", "schema_name")

        assert isinstance(result, dict)
        assert result["structured"] == "output"

    @patch("knowledge_system.processors.hce.models.llm_system2.get_llm_adapter")
    def test_structured_json_non_ollama_fallback(self, mock_get_adapter):
        """Test structured JSON falls back to regular JSON for non-Ollama."""
        mock_adapter = MagicMock()
        mock_adapter.complete_with_retry = AsyncMock(
            return_value={"content": '{"fallback": true}'}
        )
        mock_get_adapter.return_value = mock_adapter

        llm = System2LLM(provider="openai")
        result = llm.generate_structured_json("Generate", "schema_name")

        assert isinstance(result, dict)
        assert result["fallback"] is True


class TestSystem2LLMTracking:
    """Test job run ID tracking."""

    @patch("knowledge_system.processors.hce.models.llm_system2.get_llm_adapter")
    def test_set_job_run_id(self, mock_get_adapter):
        """Test that job run ID is properly set on adapter."""
        mock_adapter = MagicMock()
        mock_get_adapter.return_value = mock_adapter

        llm = System2LLM(provider="openai")
        llm.set_job_run_id("test-job-123")

        # Verify adapter's set_job_run_id was called
        mock_adapter.set_job_run_id.assert_called_once_with("test-job-123")

    @patch("knowledge_system.processors.hce.models.llm_system2.get_llm_adapter")
    def test_get_stats(self, mock_get_adapter):
        """Test that stats are retrieved from adapter."""
        mock_adapter = MagicMock()
        mock_adapter.get_stats.return_value = {
            "hardware_tier": "prosumer",
            "max_concurrent": 4,
            "active_requests": 1,
        }
        mock_get_adapter.return_value = mock_adapter

        llm = System2LLM(provider="openai")
        stats = llm.get_stats()

        assert stats["hardware_tier"] == "prosumer"
        assert stats["max_concurrent"] == 4
        mock_adapter.get_stats.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
