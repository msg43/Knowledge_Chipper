from unittest.mock import patch, MagicMock
from pathlib import Path
from knowledge_system.processors.summarizer import SummarizerProcessor, fetch_summary
from knowledge_system.processors.base import ProcessorResult


class TestSummarizationPipeline:
    """Integration tests for the summarization pipeline."""

    def test_summarize_transcription_output(self):
        """Test summarizing transcription output."""
        transcription_text = """
        This is a long transcription of a video about artificial intelligence.
        The speaker discusses various topics including machine learning, neural networks,
        and the future of AI technology. They mention that AI has made significant
        progress in recent years and will continue to evolve rapidly.
        """

        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.llm.model = "gpt-4"
            mock_settings.api_keys.openai_api_key = "test_key"
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor(provider="openai")

            with patch.object(
                processor,
                "_call_openai",
                return_value="AI technology has advanced significantly and will continue evolving rapidly.",
            ):
                result = processor.process(transcription_text, style="general")

                assert result.success is True
                assert "AI technology" in result.data
                assert result.metadata["provider"] == "openai"
                assert result.metadata["style"] == "general"
                assert result.metadata["input_length"] > 0
                assert result.metadata["summary_length"] > 0

    def test_summarize_with_different_styles(self):
        """Test summarizing with different styles."""
        text = """
        Machine learning algorithms require large datasets for training.
        The quality of the data significantly impacts model performance.
        Data preprocessing is essential for good results.
        """

        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.llm.model = "gpt-4"
            mock_settings.api_keys.openai_api_key = "test_key"
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor(provider="openai")

            # Test bullet style
            with patch.object(
                processor,
                "_call_openai",
                return_value="• Large datasets needed\n• Data quality matters\n• Preprocessing essential",
            ):
                result = processor.process(text, style="bullet")
                assert result.success is True
                assert result.metadata["style"] == "bullet"

            # Test academic style
            with patch.object(
                processor,
                "_call_openai",
                return_value="Key findings indicate that machine learning requires substantial datasets and quality data preprocessing for optimal performance.",
            ):
                result = processor.process(text, style="academic")
                assert result.success is True
                assert result.metadata["style"] == "academic"

            # Test executive style
            with patch.object(
                processor,
                "_call_openai",
                return_value="ML success depends on quality data and proper preprocessing.",
            ):
                result = processor.process(text, style="executive")
                assert result.success is True
                assert result.metadata["style"] == "executive"

    def test_summarize_from_file(self):
        """Test summarizing text from a file."""
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.llm.model = "gpt-4"
            mock_settings.api_keys.openai_api_key = "test_key"
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor(provider="openai")

            with patch("builtins.open", create=True) as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = (
                    "File content to summarize"
                )

                with (
                    patch.object(Path, "exists", return_value=True),
                    patch.object(Path, "is_file", return_value=True),
                ):
                    with patch.object(
                        processor, "_call_openai", return_value="Summarized content"
                    ):
                        result = processor.process(Path("test.txt"))

                        assert result.success is True
                        assert result.data == "Summarized content"

    def test_batch_summarization(self):
        """Test batch summarization of multiple texts."""
        texts = [
            "First text about technology.",
            "Second text about science.",
            "Third text about innovation.",
        ]

        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.llm.model = "gpt-4"
            mock_settings.api_keys.openai_api_key = "test_key"
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor(provider="openai")

            with patch.object(processor, "process") as mock_process:
                mock_process.side_effect = [
                    ProcessorResult(success=True, data="Summary 1"),
                    ProcessorResult(success=True, data="Summary 2"),
                    ProcessorResult(success=True, data="Summary 3"),
                ]

                results = processor.process_batch(texts, style="general")

                assert len(results) == 3
                assert all(r.success for r in results)
                assert results[0].data == "Summary 1"
                assert results[1].data == "Summary 2"
                assert results[2].data == "Summary 3"

    def test_anthropic_summarization(self):
        """Test summarization using Anthropic provider."""
        text = "This is a test text for Anthropic summarization."

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
                result = processor.process(text)

                assert result.success is True
                assert result.data == "Anthropic summary"
                assert result.metadata["provider"] == "anthropic"


class TestConvenienceFunctions:
    """Test convenience functions for summarization."""

    def test_fetch_summary_success(self):
        """Test fetch_summary convenience function."""
        with patch(
            "knowledge_system.processors.summarizer.SummarizerProcessor"
        ) as mock_processor_class:
            mock_processor = MagicMock()
            mock_processor.process.return_value = ProcessorResult(
                success=True, data="Summary"
            )
            mock_processor_class.return_value = mock_processor

            result = fetch_summary(
                "test text", provider="openai", style="bullet", max_tokens=1000
            )

            assert result == "Summary"
            mock_processor_class.assert_called_once_with(
                provider="openai", max_tokens=1000
            )
            mock_processor.process.assert_called_once_with(
                "test text", style="bullet")

    def test_fetch_summary_failure(self):
        """Test fetch_summary when processing fails."""
        with patch(
            "knowledge_system.processors.summarizer.SummarizerProcessor"
        ) as mock_processor_class:
            mock_processor = MagicMock()
            mock_processor.process.return_value = ProcessorResult(
                success=False, data=None
            )
            mock_processor_class.return_value = mock_processor

            result = fetch_summary("test text")

            assert result is None

    def test_fetch_summary_with_file(self):
        """Test fetch_summary with file path."""
        with patch(
            "knowledge_system.processors.summarizer.SummarizerProcessor"
        ) as mock_processor_class:
            mock_processor = MagicMock()
            mock_processor.process.return_value = ProcessorResult(
                success=True, data="File summary"
            )
            mock_processor_class.return_value = mock_processor

            result = fetch_summary(Path("test.txt"), provider="anthropic")

            assert result == "File summary"
            mock_processor.process.assert_called_once_with(
                Path("test.txt"), style="general"
            )


class TestErrorHandling:
    """Test error handling in summarization pipeline."""

    def test_empty_input_handling(self):
        """Test handling of empty input."""
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor()
            result = processor.process("")

            assert result.success is False
            assert "Empty or invalid input text" in result.errors[0]

    def test_unsupported_provider_handling(self):
        """Test handling of unsupported provider."""
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor(provider="unsupported")
            result = processor.process("test text")

            assert result.success is False
            assert "Unsupported provider" in result.errors[0]

    def test_api_error_handling(self):
        """Test handling of API errors."""
        with patch(
            "knowledge_system.processors.summarizer.get_settings"
        ) as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.llm.model = "gpt-4"
            mock_settings.api_keys.openai_api_key = "test_key"
            mock_get_settings.return_value = mock_settings

            processor = SummarizerProcessor(provider="openai")

            with patch.object(
                processor, "_call_openai", side_effect=Exception("API Error")
            ):
                result = processor.process("test text")

                assert result.success is False
                assert "API Error" in result.errors[0]
