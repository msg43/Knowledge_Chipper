"""
Summarizer Processor using Unified LLM Providers

Refactored to use shared LLM provider utilities, eliminating duplicate API calling code.
"""

from typing import List, Union, Optional, Dict, Any, Callable, Tuple
from pathlib import Path
import time
from knowledge_system.processors.base import BaseProcessor, ProcessorResult
from knowledge_system.config import get_settings
from knowledge_system.logger import get_logger
from knowledge_system.utils.progress import SummarizationProgress, CancellationToken
from knowledge_system.utils.text_utils import (
    calculate_chunking_config, create_intelligent_chunks, 
    generate_chunk_summary_prompt, reassemble_chunk_summaries, get_chunking_summary
)
from knowledge_system.utils.llm_providers import UnifiedLLMClient

logger = get_logger(__name__)


class SummarizerProcessor(BaseProcessor):
    """Summarizes text using various LLM providers via unified client."""

    @property
    def supported_formats(self) -> List[str]:
        return [".txt", ".md", ".json"]

    def __init__(
        self,
        provider: str = "openai",
        model: Optional[str] = None,
        max_tokens: int = 500,
    ):
        super().__init__()
        self.provider = provider
        self.model = model
        self.max_tokens = max_tokens
        self.settings = get_settings()

        # Set default model based on provider
        if not self.model:
            if provider == "openai":
                self.model = self.settings.llm.model
            elif provider == "anthropic":
                self.model = self.settings.llm.model
            elif provider == "local":
                self.model = self.settings.llm.local_model
            else:
                self.model = "gpt-4o-mini-2024-07-18"  # fallback

        # Create unified LLM client
        self.llm_client = UnifiedLLMClient(
            provider=self.provider,
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=0.3
        )

    def validate_input(self, input_data: Union[str, Path]) -> bool:
        if isinstance(input_data, str):
            return len(input_data.strip()) > 0
        elif isinstance(input_data, Path):
            return input_data.exists() and input_data.is_file()
        return False

    def _read_text_from_file(self, file_path: Path) -> str:
        """Read text content from file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            raise

    def _generate_prompt(
        self, text: str, style: str = "general", template: Optional[Union[str, Path]] = None
    ) -> str:
        """Generate summarization prompt."""
        # Style-specific prompts
        style_prompts = {
            "bullet": "Create a concise bullet-point summary of the following text:",
            "paragraph": "Write a clear paragraph summary of the following text:",
            "structured": "Create a well-structured summary with key points organized by topics:",
            "academic": "Provide an academic-style summary with methodology, findings, and conclusions:",
            "executive": "Create an executive summary highlighting key business insights and recommendations:",
            "general": "Summarize the following text, capturing the main ideas and important details:",
        }

        if template:
            # Use custom template
            if isinstance(template, Path):
                try:
                    with open(template, "r", encoding="utf-8") as f:
                        prompt_template = f.read()
                    return prompt_template.replace("{text}", text)
                except Exception as e:
                    logger.warning(f"Could not load template {template}: {e}")
                    # Fall back to style-based prompt
            else:
                return str(template).replace("{text}", text)

        # Use style-based prompt
        style_prompt = style_prompts.get(style, style_prompts["general"])
        return f"{style_prompt}\n\nText:\n{text}\n\nSummary:"

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text (rough approximation)."""
        # Rough approximation: 1 token ≈ 4 characters for English text
        return len(text) // 4

    def _call_llm_provider(self, prompt: str, progress_callback: Optional[Callable[[SummarizationProgress], None]] = None) -> Dict[str, Any]:
        """Call the LLM provider using unified client."""
        def llm_progress_callback(progress_data):
            """Adapt generic progress to SummarizationProgress."""
            if progress_callback and isinstance(progress_data, dict):
                progress_callback(SummarizationProgress(
                    status=progress_data.get("status", "generating"),
                    current_step=progress_data.get("current_step", "Generating..."),
                    percent=progress_data.get("percent", 50.0),
                    model_name=progress_data.get("model_name", self.model),
                    provider=progress_data.get("provider", self.provider),
                    tokens_generated=progress_data.get("tokens_generated", 0),
                    speed_tokens_per_sec=progress_data.get("speed_tokens_per_sec", 0)
                ))

        return self.llm_client.generate_dict(prompt, llm_progress_callback)

    def _setup_chunking_config(
        self,
        text: str,
        style: str,
        prompt_template: Optional[Union[str, Path]],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Tuple[List[Any], str, Any]:
        """
        Set up chunking configuration and create chunks.
        
        Returns:
            Tuple of (chunks, base_prompt, chunking_config)
        """
        logger.info(f"Setting up chunking configuration (model: {self.model})")
        
        # Check for cancellation
        if cancellation_token:
            cancellation_token.throw_if_cancelled()
            cancellation_token.wait_if_paused()
        
        # Generate base prompt for chunking calculation
        base_prompt = self._generate_prompt("PLACEHOLDER_TEXT", style, prompt_template)
        
        # Ensure model is not None
        model = self.model or "gpt-4o-mini-2024-07-18"
        
        # Calculate optimal chunking configuration
        chunking_config = calculate_chunking_config(
            text=text,
            model=model,
            prompt_template=base_prompt,
            max_output_tokens=self.max_tokens,
            style=style
        )
        
        # Override with user preferences if provided
        if hasattr(self, 'chunk_overlap') and getattr(self, 'chunk_overlap', None) is not None:
            chunking_config.overlap_tokens = getattr(self, 'chunk_overlap')
        if hasattr(self, 'min_chunk_size') and getattr(self, 'min_chunk_size', None) is not None:
            chunking_config.min_chunk_tokens = getattr(self, 'min_chunk_size')
        
        # Check for cancellation after configuration
        if cancellation_token:
            cancellation_token.throw_if_cancelled()
            cancellation_token.wait_if_paused()
        
        # Create intelligent chunks
        chunks = create_intelligent_chunks(text, chunking_config, model)
        
        if not chunks:
            raise ValueError("Failed to create text chunks")
        
        logger.info(f"Created {len(chunks)} chunks for processing")
        
        return chunks, base_prompt, chunking_config

    def _process_chunks_batch(
        self,
        chunks: List[Any],
        base_prompt: str,
        style: str,
        progress_callback: Optional[Callable[[SummarizationProgress], None]] = None,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Tuple[List[str], Dict[str, int]]:
        """
        Process all chunks and return summaries with statistics.
        
        Returns:
            Tuple of (chunk_summaries, processing_stats)
        """
        chunk_summaries = []
        total_prompt_tokens = 0
        total_completion_tokens = 0
        
        for i, chunk in enumerate(chunks):
            # Check for cancellation
            if cancellation_token:
                cancellation_token.throw_if_cancelled()
                cancellation_token.wait_if_paused()
            
            # Update progress
            if progress_callback:
                progress_callback(SummarizationProgress(
                    status="processing_chunks",
                    current_step=f"Processing chunk {i+1}/{len(chunks)}...",
                    percent=20.0 + (60.0 * (i / len(chunks))),
                    chunk_number=i+1,
                    total_chunks=len(chunks),
                    model_name=self.model,
                    provider=self.provider
                ))
            
            # Generate prompt for this chunk
            chunk_prompt = generate_chunk_summary_prompt(
                chunk=chunk,
                base_prompt=base_prompt,
                chunk_index=i,
                total_chunks=len(chunks),
                style=style
            )
            
            # Process the chunk
            chunk_result = self._call_llm_provider(chunk_prompt, progress_callback)
            chunk_summary = chunk_result["summary"]
            chunk_summaries.append(chunk_summary)
            
            # Accumulate statistics
            total_prompt_tokens += chunk_result.get("prompt_tokens", 0)
            total_completion_tokens += chunk_result.get("completion_tokens", 0)
        
        processing_stats = {
            "total_prompt_tokens": total_prompt_tokens,
            "total_completion_tokens": total_completion_tokens,
            "chunks_processed": len(chunks)
        }
        
        return chunk_summaries, processing_stats

    def _reassemble_summaries(
        self,
        chunk_summaries: List[str],
        style: str,
        base_prompt: str,
        progress_callback: Optional[Callable[[SummarizationProgress], None]] = None,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Tuple[str, Dict[str, int]]:
        """
        Reassemble chunk summaries into final summary.
        
        Returns:
            Tuple of (final_summary, additional_stats)
        """
        additional_stats = {
            "reassembly_prompt_tokens": 0,
            "reassembly_completion_tokens": 0
        }
        
        # Process reassembly only if we have multiple chunks
        if len(chunk_summaries) > 1:
            try:
                # Ensure model is not None
                model = self.model or "gpt-4o-mini-2024-07-18"
                
                # Generate reassembly prompt
                reassembly_prompt = reassemble_chunk_summaries(
                    chunk_summaries=chunk_summaries,
                    original_style=style,
                    original_prompt_template=base_prompt,
                    model=model,
                    max_output_tokens=self.max_tokens
                )
                
                # Check for cancellation before final API call
                if cancellation_token:
                    cancellation_token.throw_if_cancelled()
                    cancellation_token.wait_if_paused()
                
                final_result = self._call_llm_provider(reassembly_prompt, progress_callback)
                final_summary = final_result["summary"]
                
                # Track reassembly statistics
                additional_stats["reassembly_prompt_tokens"] = final_result.get("prompt_tokens", 0)
                additional_stats["reassembly_completion_tokens"] = final_result.get("completion_tokens", 0)
                
            except Exception as e:
                logger.error(f"Error during reassembly: {e}")
                # Fallback: join chunk summaries with separator
                final_summary = "\n\n---\n\n".join(chunk_summaries)
        else:
            # Single chunk - use it directly
            final_summary = chunk_summaries[0] if chunk_summaries else ""
        
        return final_summary, additional_stats

    def _process_with_chunking(
        self,
        text: str,
        style: str = "general",
        prompt_template: Optional[Union[str, Path]] = None,
        progress_callback: Optional[Callable[[SummarizationProgress], None]] = None,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        """
        Process text using intelligent chunking.
        
        Args:
            text: Input text to summarize
            style: Summary style
            prompt_template: Optional custom prompt template
            progress_callback: Progress callback function
            cancellation_token: Token for cancellation/pause control
            
        Returns:
            Dictionary with summary and metadata
        """
        logger.info(f"Processing with intelligent chunking (model: {self.model})")
        
        # Step 1: Setup chunking configuration and create chunks
        chunks, base_prompt, chunking_config = self._setup_chunking_config(
            text, style, prompt_template, cancellation_token
        )
        
        # Step 2: Process all chunks
        chunk_summaries, processing_stats = self._process_chunks_batch(
            chunks, base_prompt, style, progress_callback, cancellation_token
        )
        
        # Step 3: Reassemble summaries
        final_summary, reassembly_stats = self._reassemble_summaries(
            chunk_summaries, style, base_prompt, progress_callback, cancellation_token
        )
        
        # Step 4: Prepare final results
        total_prompt_tokens = processing_stats["total_prompt_tokens"] + reassembly_stats["reassembly_prompt_tokens"]
        total_completion_tokens = processing_stats["total_completion_tokens"] + reassembly_stats["reassembly_completion_tokens"]
        
        return {
            "summary": final_summary,
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "total_tokens": total_prompt_tokens + total_completion_tokens,
            "model": self.model,
            "provider": self.provider,
            "chunks_processed": processing_stats["chunks_processed"],
            "chunking_summary": get_chunking_summary(chunking_config)
        }

    def process(
        self,
        input_data: Any,
        dry_run: bool = False,
        progress_callback: Optional[Callable[[SummarizationProgress], None]] = None,
        **kwargs: Any,
    ) -> ProcessorResult:
        """Process input and generate summary using unified LLM client."""
        # Extract parameters from kwargs for backwards compatibility
        style = kwargs.get('style', 'general')
        prompt_template = kwargs.get('prompt_template', None)
        
        start_time = time.time()

        try:
            # Send initial progress update
            if progress_callback:
                progress_callback(SummarizationProgress(
                    status="loading_file",
                    current_step="Reading input text...",
                    percent=10.0,
                    model_name=self.model,
                    provider=self.provider
                ))

            # Get text content
            if isinstance(input_data, str):
                text = input_data
                input_path = None
            else:
                input_path = Path(input_data)
                text = self._read_text_from_file(input_path)

            if not text.strip():
                return ProcessorResult(
                    success=False,
                    errors=["Empty or invalid input text"],
                    dry_run=dry_run,
                )

            # Send tokenization progress update
            if progress_callback:
                estimated_tokens = self._estimate_tokens(text)
                progress_callback(SummarizationProgress(
                    status="tokenizing",
                    current_step="Analyzing text and generating prompt...",
                    percent=30.0,
                    total_tokens=estimated_tokens,
                    model_name=self.model,
                    provider=self.provider
                ))

            # Check if we need chunking for large texts
            estimated_tokens = self._estimate_tokens(text)
            
            if estimated_tokens > 8000:  # Use chunking for large texts
                if progress_callback:
                    progress_callback(SummarizationProgress(
                        status="chunking",
                        current_step="Text is large, using intelligent chunking...",
                        percent=40.0,
                        total_tokens=estimated_tokens,
                        model_name=self.model,
                        provider=self.provider
                    ))
                
                result_stats = self._process_with_chunking(
                    text, style, prompt_template, progress_callback, kwargs.get('cancellation_token')
                )
            else:
                # Generate prompt for small texts
                prompt = self._generate_prompt(text, style, prompt_template)

                if dry_run:
                    return ProcessorResult(
                        success=True,
                        data=f"[DRY RUN] Would summarize {len(text)} characters using {self.provider}",
                        metadata={
                            "provider": self.provider,
                            "model": self.model,
                            "style": style,
                            "estimated_tokens": estimated_tokens,
                            "dry_run": True,
                        },
                        dry_run=True,
                    )

                # Send generation progress update
                if progress_callback:
                    progress_callback(SummarizationProgress(
                        status="generating",
                        current_step="Generating summary...",
                        percent=50.0,
                        total_tokens=estimated_tokens,
                        model_name=self.model,
                        provider=self.provider
                    ))

                # Call LLM provider using unified client
                result_stats = self._call_llm_provider(prompt, progress_callback)

            processing_time = time.time() - start_time

            # Send completion progress update
            if progress_callback:
                progress_callback(SummarizationProgress(
                    status="completed",
                    current_step="Summary generation complete!",
                    percent=100.0,
                    tokens_processed=result_stats.get("prompt_tokens", 0),
                    total_tokens=result_stats.get("total_tokens", 0),
                    tokens_generated=result_stats.get("completion_tokens", 0),
                    speed_tokens_per_sec=result_stats.get("total_tokens", 0) / processing_time if processing_time > 0 else 0,
                    model_name=self.model,
                    provider=self.provider
                ))

            # Calculate additional statistics
            compression_ratio = (
                len(result_stats["summary"]) / len(text) if len(text) > 0 else 0
            )
            tokens_per_second = (
                result_stats["total_tokens"] / processing_time
                if processing_time > 0
                else 0
            )

            # Prepare metadata
            metadata = {
                "provider": self.provider,
                "model": self.model,
                "style": style,
                "input_length": len(text),
                "output_length": len(result_stats["summary"]),
                "compression_ratio": compression_ratio,
                "processing_time": processing_time,
                "tokens_per_second": tokens_per_second,
                "prompt_tokens": result_stats.get("prompt_tokens", 0),
                "completion_tokens": result_stats.get("completion_tokens", 0),
                "total_tokens": result_stats.get("total_tokens", 0),
            }

            # Add chunking info if available
            if "chunks_processed" in result_stats:
                metadata["chunks_processed"] = result_stats["chunks_processed"]
                metadata["chunking_summary"] = result_stats.get("chunking_summary", "")

            return ProcessorResult(
                success=True,
                data=result_stats["summary"],
                metadata=metadata,
                dry_run=dry_run,
            )

        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"Summarization failed: {e}"
            logger.error(error_msg)

            if progress_callback:
                progress_callback(SummarizationProgress(
                    status="failed",
                    current_step=f"Error: {str(e)}",
                    percent=0.0,
                    model_name=self.model,
                    provider=self.provider
                ))

            return ProcessorResult(
                success=False,
                errors=[error_msg],
                metadata={
                    "provider": self.provider,
                    "model": self.model,
                    "style": style,
                    "processing_time": processing_time,
                },
                dry_run=dry_run,
            )


def fetch_summary(
    text: Union[str, Path],
    provider: str = "openai",
    style: str = "general",
    max_tokens: int = 500,
) -> Optional[str]:
    """Convenience function to get a summary using unified LLM providers."""
    processor = SummarizerProcessor(provider=provider, max_tokens=max_tokens)
    result = processor.process(text, style=style)
    return result.data if result.success else None

