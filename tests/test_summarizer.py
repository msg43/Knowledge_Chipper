from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from knowledge_system.processors.summarizer import SummarizerProcessor, fetch_summary


class TestSummarizerProcessor:
    def test_init_with_defaults(self):
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.llm.model = "gpt-4"
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor()
            assert processor.provider == "openai"
            assert processor.max_tokens == 500

    def test_init_with_custom_params(self):
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor(
                provider="anthropic", model="claude-3", max_tokens=1000
            )
            assert processor.provider == "anthropic"
            assert processor.model == "claude-3"
            assert processor.max_tokens == 1000

    def test_init_with_local_provider(self):
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.llm.local_model = "llama3.2:3b"
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor(
                provider="local", model="qwen2.5:72b-instruct-q6_K", max_tokens=1000
            )
            assert processor.provider == "local"
            assert processor.model == "qwen2.5:72b-instruct-q6_K"
            assert processor.max_tokens == 1000

    def test_init_local_with_default_model(self):
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.llm.local_model = "llama3.2:3b"
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor(provider="local")
            assert processor.provider == "local"
            assert processor.model == "llama3.2:3b"

    def test_validate_input_string(self):
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor()
            assert processor.validate_input("Valid text") is True
            assert processor.validate_input("") is False
            assert processor.validate_input("   ") is False

    def test_validate_input_file(self):
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor()
            with (
                patch.object(Path, "exists", return_value=True),
                patch.object(Path, "is_file", return_value=True),
            ):
                assert processor.validate_input(Path("test.txt")) is True

            with patch.object(Path, "exists", return_value=False):
                assert processor.validate_input(Path("nonexistent.txt")) is False

    def test_can_process_string(self):
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor()
            assert processor.can_process("any string") is True

    def test_can_process_file(self):
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor()
            assert processor.can_process("test.txt") is True
            assert processor.can_process("test.md") is True
            assert processor.can_process("test.json") is True
            assert processor.can_process("test.pdf") is False
            assert processor.can_process("just text without extension") is True

    def test_supported_formats_property(self):
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor()
            assert processor.supported_formats == [".txt", ".md", ".json"]

    def test_openai_summarization_success(self):
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.llm.model = "gpt-4"
            mock_settings.api_keys.openai_api_key = "test_key"
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor(provider="openai")

            with patch.object(
                processor, "_call_openai", return_value="This is a summary"
            ):
                result = processor.process(
                    "This is a long text that needs summarization"
                )

                assert result.success is True
                assert result.data == "This is a summary"
                assert result.metadata["provider"] == "openai"
                assert result.metadata["style"] == "general"

    def test_anthropic_summarization_success(self):
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.llm.model = "claude-3"
            mock_settings.api_keys.anthropic_api_key = "test_key"
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor(provider="anthropic")

            with patch.object(
                processor, "_call_anthropic", return_value="Anthropic summary"
            ):
                result = processor.process("Text to summarize", style="bullet")

                assert result.success is True
                assert result.data == "Anthropic summary"
                assert result.metadata["provider"] == "anthropic"
                assert result.metadata["style"] == "bullet"

    def test_ollama_summarization_success(self):
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.llm.local_model = "llama3.2:3b"
            mock_settings.local_config.backend = "ollama"
            mock_settings.local_config.endpoint = "http://localhost:11434"
            mock_settings.local_config.timeout = 60
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor(provider="local")

            with patch.object(processor, "_call_ollama", return_value="Ollama summary"):
                result = processor.process("Text to summarize", style="general")

                assert result.success is True
                assert result.data == "Ollama summary"
                assert result.metadata["provider"] == "local"
                assert result.metadata["style"] == "general"

    def test_lmstudio_summarization_success(self):
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.llm.local_model = "qwen2.5:72b-instruct-q6_K"
            mock_settings.local_config.backend = "lmstudio"
            mock_settings.local_config.endpoint = "http://localhost:1234"
            mock_settings.local_config.timeout = 60
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor(provider="local")

            with patch.object(
                processor, "_call_lmstudio", return_value="LM Studio summary"
            ):
                result = processor.process("Text to summarize", style="academic")

                assert result.success is True
                assert result.data == "LM Studio summary"
                assert result.metadata["provider"] == "local"
                assert result.metadata["style"] == "academic"

    def test_unsupported_provider(self):
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor(provider="unsupported")
            result = processor.process("test text")

            assert result.success is False
            assert "Unsupported provider" in result.errors[0]

    def test_empty_input(self):
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor()
            result = processor.process("")

            assert result.success is False
            assert "Empty or invalid input text" in result.errors[0]

    def test_file_reading(self):
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor()

            with patch("builtins.open", create=True) as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = (
                    "File content"
                )

                with (
                    patch.object(Path, "exists", return_value=True),
                    patch.object(Path, "is_file", return_value=True),
                ):
                    with patch.object(
                        processor, "_call_openai", return_value="Summary"
                    ):
                        result = processor.process(Path("test.txt"))

                        assert result.success is True
                        assert result.data == "Summary"

    def test_batch_processing(self):
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor()

            with patch.object(processor, "process") as mock_process:
                mock_process.side_effect = [
                    MagicMock(success=True, data="summary1"),
                    MagicMock(success=True, data="summary2"),
                ]

                results = processor.process_batch(["text1", "text2"], style="academic")

                assert len(results) == 2
                assert all(r.success for r in results)
                assert results[0].data == "summary1"
                assert results[1].data == "summary2"

    def test_prompt_generation(self):
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor()

            prompt = processor._generate_prompt("test text", "bullet")
            assert "bullet points" in prompt

            prompt = processor._generate_prompt("test text", "academic")
            assert "academic-style" in prompt

            prompt = processor._generate_prompt("test text", "executive")
            assert "executive summary" in prompt

    def test_unsupported_local_backend(self):
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.local_config.backend = "unsupported"
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor(provider="local")

            with patch.object(
                processor,
                "_call_local",
                side_effect=ValueError("Unsupported local backend: unsupported"),
            ):
                result = processor.process("test text")

                assert result.success is False
                assert "Unsupported local backend" in result.errors[0]

    def test_call_ollama_api(self):
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.local_config.endpoint = "http://localhost:11434"
            mock_settings.local_config.timeout = 60
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor(provider="local", model="llama3.2:3b")

            with patch(
                "knowledge_system.processors.summarizer.requests.post"
            ) as mock_post:
                mock_response = MagicMock()
                mock_response.json.return_value = {
                    "response": "Ollama generated summary"
                }
                mock_response.raise_for_status.return_value = None
                mock_post.return_value = mock_response

                result = processor._call_ollama(
                    "Test prompt", mock_settings.local_config
                )

                assert result == "Ollama generated summary"
                mock_post.assert_called_once()

    def test_call_lmstudio_api(self):
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.local_config.endpoint = "http://localhost:1234"
            mock_settings.local_config.timeout = 60
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor(
                provider="local", model="qwen2.5:72b-instruct-q6_K"
            )

            with patch(
                "knowledge_system.processors.summarizer.requests.post"
            ) as mock_post:
                mock_response = MagicMock()
                mock_response.json.return_value = {
                    "choices": [{"message": {"content": "LM Studio generated summary"}}]
                }
                mock_response.raise_for_status.return_value = None
                mock_post.return_value = mock_response

                result = processor._call_lmstudio(
                    "Test prompt", mock_settings.local_config
                )

                assert result == "LM Studio generated summary"
                mock_post.assert_called_once()

    def test_call_ollama_api_error(self):
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.local_config.endpoint = "http://localhost:11434"
            mock_settings.local_config.timeout = 60
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor(provider="local")

            with patch(
                "knowledge_system.processors.summarizer.requests.post"
            ) as mock_post:
                mock_post.side_effect = requests.exceptions.RequestException(
                    "Connection error"
                )

                with pytest.raises(requests.exceptions.RequestException):
                    processor._call_ollama("Test prompt", mock_settings.local_config)

    def test_call_lmstudio_api_error(self):
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.local_config.endpoint = "http://localhost:1234"
            mock_settings.local_config.timeout = 60
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor(provider="local")

            with patch(
                "knowledge_system.processors.summarizer.requests.post"
            ) as mock_post:
                mock_post.side_effect = requests.exceptions.RequestException(
                    "Connection error"
                )

                with pytest.raises(requests.exceptions.RequestException):
                    processor._call_lmstudio("Test prompt", mock_settings.local_config)

    def test_process_with_custom_prompt_template(self, tmp_path):
        """Test processing with custom prompt template."""
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor(provider="openai", max_tokens=500)

            # Create a temporary prompt template file
            template_content = "Custom prompt template. Text: {text}, Style: {style}, Max tokens: {max_tokens}"
            template_file = tmp_path / "custom_template.txt"
            template_file.write_text(template_content)

            # Test with custom template in dry run mode
            result = processor.process(
                "Sample text to summarize",
                style="bullet",
                dry_run=True,
                prompt_template=template_file,
            )

            # In dry run mode, should show template info
            assert result.success is True
            assert "custom template" in result.data
            assert result.metadata.get("prompt_template") == str(template_file)
            assert result.dry_run is True

    def test_process_with_invalid_prompt_template(self):
        """Test processing with invalid prompt template file."""
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor(provider="openai", max_tokens=500)

            # Test with non-existent template file in dry run mode
            result = processor.process(
                "Sample text to summarize",
                style="bullet",
                dry_run=True,
                prompt_template="non_existent_file.txt",
            )

            # In dry run mode, should still show the template path even if
            # invalid
            assert result.success is True
            assert "custom template 'non_existent_file.txt'" in result.data
            assert result.metadata.get("prompt_template") == "non_existent_file.txt"
            assert result.dry_run is True

    def test_generate_prompt_with_template_placeholders(self, tmp_path):
        """Test prompt generation with template placeholders."""
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor(provider="openai", max_tokens=300)

            template_content = (
                "Analyze this: {text}\nStyle: {style}\nLimit: {max_tokens} tokens"
            )
            template_file = tmp_path / "placeholder_template.txt"
            template_file.write_text(template_content)

            prompt = processor._generate_prompt(
                "Test content", style="academic", prompt_template=template_file
            )

            # Check that placeholders are replaced
            assert "Test content" in prompt
            assert "academic" in prompt
            assert "300" in prompt
            assert "{text}" not in prompt
            assert "{style}" not in prompt
            assert "{max_tokens}" not in prompt


class TestFetchSummary:
    def test_fetch_summary_success(self):
        with patch(
            "knowledge_system.processors.summarizer.SummarizerProcessor"
        ) as mock_processor_class:
            mock_processor = MagicMock()
            mock_processor.process.return_value = MagicMock(
                success=True, data="summary"
            )
            mock_processor_class.return_value = mock_processor

            result = fetch_summary(
                "test text", provider="anthropic", style="bullet", max_tokens=1000
            )

            assert result == "summary"
            mock_processor_class.assert_called_once_with(
                provider="anthropic", max_tokens=1000
            )
            mock_processor.process.assert_called_once_with("test text", style="bullet")

    def test_fetch_summary_failure(self):
        with patch(
            "knowledge_system.processors.summarizer.SummarizerProcessor"
        ) as mock_processor_class:
            mock_processor = MagicMock()
            mock_processor.process.return_value = MagicMock(success=False, data=None)
            mock_processor_class.return_value = mock_processor

            result = fetch_summary("test text")

            assert result is None
