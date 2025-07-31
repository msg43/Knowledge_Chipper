"""
Summarizer Processor using Unified LLM Providers

Refactored to use shared LLM provider utilities, eliminating duplicate API calling code.
"""

from typing import List, Union, Optional, Dict, Any, Callable, Tuple
from pathlib import Path
import time
import json
import hashlib
from datetime import datetime
import os
from knowledge_system.processors.base import BaseProcessor, ProcessorResult
from knowledge_system.config import get_settings
from knowledge_system.logger import get_logger
from knowledge_system.utils.progress import SummarizationProgress, CancellationToken
from knowledge_system.utils.cancellation import CancellationError
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
        return [".txt", ".md", ".json", ".html", ".htm"]

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
            suffix = file_path.suffix.lower()
            
            logger.info(f"📖 Reading file: {file_path} (size: {file_path.stat().st_size} bytes)")
            
            # Handle HTML files specially - extract text content
            if suffix in [".html", ".htm"]:
                from .html import fetch_html_text
                content = fetch_html_text(file_path)
            
            # Handle PDF files
            elif suffix == ".pdf":
                from .pdf import fetch_pdf_text
                content = fetch_pdf_text(file_path)
            
            # Handle regular text files
            else:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            
            logger.info(f"📖 Read {len(content)} characters from {file_path.name}")
            
            # Log first 200 chars for debugging
            preview = content[:200].replace('\n', '\\n').replace('\r', '\\r')
            logger.debug(f"📖 Content preview: {preview}...")
            
            return content
                    
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            raise

    def _build_summary_index(self, output_dir: Path) -> Dict[str, Dict[str, Any]]:
        """Build index of existing summaries in output directory."""
        summary_index = {}
        files_scanned = 0
        files_failed = 0
        
        logger.info(f"🔍 Building summary index from {output_dir}")
        
        # Get all summary files
        summary_patterns = ['*_summary.md', '*_summary.txt']
        all_summary_files = []
        for pattern in summary_patterns:
            all_summary_files.extend(output_dir.glob(pattern))
        
        total_files = len(all_summary_files)
        if total_files == 0:
            logger.info("No existing summary files found in output directory")
            return summary_index
        
        logger.info(f"Scanning {total_files} summary files...")
        
        for summary_file in all_summary_files:
            try:
                # Read file to extract source file info from metadata
                with open(summary_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                source_path = None
                summary_generated = None
                
                # Parse metadata from summary file
                for i, line in enumerate(lines[:20]):  # Check first 20 lines
                    if line.startswith('**Source Path:**'):
                        source_path = line.replace('**Source Path:**', '').strip()
                    elif line.startswith('**Generated:**'):
                        generated_str = line.replace('**Generated:**', '').strip()
                        try:
                            summary_generated = datetime.fromisoformat(generated_str)
                        except:
                            pass
                
                if source_path:
                    # Get summary file modification time as fallback
                    if not summary_generated:
                        summary_stat = summary_file.stat()
                        summary_generated = datetime.fromtimestamp(summary_stat.st_mtime)
                    
                    # Add to index
                    summary_index[source_path] = {
                        'summary_file': str(summary_file),
                        'summary_generated': summary_generated.isoformat(),
                        'summary_size': summary_file.stat().st_size
                    }
                    files_scanned += 1
                    
            except UnicodeDecodeError:
                logger.debug(f"Skipping {summary_file.name} - encoding error")
                files_failed += 1
            except Exception as e:
                logger.debug(f"Skipping {summary_file.name} - error: {e}")
                files_failed += 1
        
        logger.info(f"✅ Index built: Found {len(summary_index)} source-summary mappings")
        if files_failed > 0:
            logger.warning(f"⚠️  Skipped {files_failed} files due to errors")
        
        return summary_index

    def _check_needs_summarization(self, source_file: Path, summary_index: Dict[str, Dict[str, Any]]) -> Tuple[bool, str]:
        """Check if a source file needs summarization."""
        source_path_str = str(source_file.absolute())
        
        # Check if summary exists in index
        if source_path_str not in summary_index:
            return True, "No existing summary found"
        
        summary_info = summary_index[source_path_str]
        
        # Check if source file still exists
        if not source_file.exists():
            return False, "Source file no longer exists"
        
        # Get source file modification time
        source_mtime = datetime.fromtimestamp(source_file.stat().st_mtime)
        
        # Get summary generation time
        try:
            summary_generated = datetime.fromisoformat(summary_info['summary_generated'])
        except:
            # If we can't parse the generation time, summarize to be safe
            return True, "Cannot determine summary generation time"
        
        # Check if source was modified after summary was generated
        if source_mtime > summary_generated:
            time_diff = source_mtime - summary_generated
            return True, f"Source file modified {time_diff} after summary"
        
        # Check if summary file still exists
        summary_file = Path(summary_info['summary_file'])
        if not summary_file.exists():
            return True, "Summary file was deleted"
        
        return False, f"Summary is up-to-date (generated {summary_generated.strftime('%Y-%m-%d %H:%M')})"

    def _calculate_file_hash(self, file_path: Path, chunk_size: int = 8192) -> str:
        """Calculate SHA-256 hash of file content."""
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                while chunk := f.read(chunk_size):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.error(f"Failed to calculate hash for {file_path}: {e}")
            return ""

    def _save_index_to_file(self, index_file: Path, summary_index: Dict[str, Dict[str, Any]]) -> None:
        """Save summary index to JSON file."""
        try:
            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump(summary_index, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved index with {len(summary_index)} entries to {index_file}")
        except Exception as e:
            logger.error(f"Failed to save index file: {e}")

    def _update_index_file(self, index_file: Path, source_path: str, summary_info: Dict[str, Any]) -> None:
        """Update the index file with new summary information."""
        try:
            # Read existing index
            summary_index = {}
            if index_file.exists():
                with open(index_file, 'r', encoding='utf-8') as f:
                    summary_index = json.load(f)
            
            # Update with new info
            summary_index[source_path] = summary_info
            
            # Save updated index
            self._save_index_to_file(index_file, summary_index)
            
        except Exception as e:
            logger.error(f"Failed to update index file: {e}")

    def _generate_prompt(
        self, text: str, style: str = "general", template: Optional[Union[str, Path]] = None
    ) -> str:
        """Generate summarization prompt."""
        
        logger.info(f"🔧 _generate_prompt called with text length: {len(text)} chars, style: {style}, template: {template}")
        
        # Debug log first 200 chars of input text
        text_preview = text[:200].replace('\n', '\\n').replace('\r', '\\r')
        logger.debug(f"🔧 Input text preview: {text_preview}...")
        
        # Style-specific prompts
        style_prompts = {
            "bullet": "Create a concise bullet-point summary of the following text:",
            "paragraph": "Write a clear paragraph summary of the following text:",
            "structured": "Create a well-structured summary with key points organized by topics:",
            "academic": "Provide an academic-style summary with methodology, findings, and conclusions:",
            "executive": "Create an executive summary highlighting key business insights and recommendations:",
            "general": "Summarize the following text, capturing the main ideas and important details:",
        }

        final_prompt = ""
        
        if template:
            # Use custom template
            if isinstance(template, Path):
                try:
                    with open(template, "r", encoding="utf-8") as f:
                        prompt_template = f.read()
                    logger.info(f"🔧 Using custom template from file: {template}")
                    final_prompt = prompt_template.replace("{text}", text)
                except Exception as e:
                    logger.warning(f"Could not load template {template}: {e}")
                    # Fall back to style-based prompt
                    style_prompt = style_prompts.get(style, style_prompts["general"])
                    final_prompt = f"{style_prompt}\n\nText:\n{text}\n\nSummary:"
            else:
                logger.info(f"🔧 Using custom template string: {str(template)[:100]}...")
                final_prompt = str(template).replace("{text}", text)
        else:
            # Use style-based prompt
            logger.info(f"🔧 Using style-based prompt for style: {style}")
            style_prompt = style_prompts.get(style, style_prompts["general"])
            final_prompt = f"{style_prompt}\n\nText:\n{text}\n\nSummary:"
        
        logger.info(f"🔧 Generated prompt length: {len(final_prompt)} chars")
        
        # Debug log first 300 chars of final prompt 
        prompt_preview = final_prompt[:300].replace('\n', '\\n').replace('\r', '\\r')
        logger.debug(f"🔧 Final prompt preview: {prompt_preview}...")
        
        return final_prompt

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text (rough approximation)."""
        # Rough approximation: 1 token ≈ 4 characters for English text
        return len(text) // 4

    def _calculate_smart_chunking_threshold(self, text: str, style: str, prompt_template: Optional[Union[str, Path]]) -> int:
        """
        Calculate the intelligent chunking threshold based on model capabilities and user settings.
        
        Uses the same logic as calculate_chunking_config but returns just the threshold
        for the chunking decision.
        
        Args:
            text: Input text to analyze
            style: Summary style 
            prompt_template: Custom prompt template
            
        Returns:
            Maximum tokens that can be processed without chunking
        """
        from ..utils.text_utils import get_model_context_window, estimate_tokens_improved
        
        # Get model's actual context window
        model = self.model or "gpt-4o-mini-2024-07-18"
        context_window = get_model_context_window(model)
        
        # Generate a sample prompt to estimate prompt overhead
        sample_prompt = self._generate_prompt("PLACEHOLDER_TEXT", style, prompt_template)
        prompt_tokens = estimate_tokens_improved(sample_prompt.replace("PLACEHOLDER_TEXT", ""), model)
        
        # Add style-specific prompt overhead
        style_overhead = {
            "bullet": 50,      # "Provide as bullet points"
            "academic": 100,   # "Provide academic-style summary with key findings"
            "executive": 80,   # "Provide executive summary suitable for business context"
            "general": 30      # Basic prompt additions
        }
        prompt_tokens += style_overhead.get(style, 30)
        
        # Use user's max_tokens setting for response reservation
        max_output_tokens = self.max_tokens
        
        # Apply 5% safety margin (95% utilization as requested)
        safety_margin = int(context_window * 0.05)
        
        # Calculate maximum tokens available for input text
        available_for_text = context_window - prompt_tokens - max_output_tokens - safety_margin
        
        # Ensure we have a reasonable minimum (fallback for edge cases)
        if available_for_text < 1000:
            logger.warning(f"Very limited space for text input: {available_for_text} tokens. "
                         f"Context: {context_window}, Prompt: {prompt_tokens}, "
                         f"Max output: {max_output_tokens}, Safety: {safety_margin}")
            available_for_text = max(500, available_for_text)
        
        logger.info(f"🧠 Smart chunking threshold for {model}: {available_for_text:,} tokens "
                   f"(Context: {context_window:,}, Prompt: {prompt_tokens}, "
                   f"Response: {max_output_tokens}, Safety: {safety_margin})")
        
        return available_for_text

    def _call_llm_provider(self, prompt: str, progress_callback: Optional[Callable[[SummarizationProgress], None]] = None, cancellation_token: Optional[CancellationToken] = None) -> Dict[str, Any]:
        """Call the LLM provider using unified client with character-based progress tracking."""
        import time
        import threading
        
        logger.info(f"🚀 Calling LLM with prompt length: {len(prompt)} characters")
        
        # Debug log first and last 150 chars of prompt to see full structure
        if len(prompt) > 300:
            prompt_start = prompt[:150].replace('\n', '\\n').replace('\r', '\\r')
            prompt_end = prompt[-150:].replace('\n', '\\n').replace('\r', '\\r')
            logger.debug(f"🚀 Prompt start: {prompt_start}...")
            logger.debug(f"🚀 Prompt end: ...{prompt_end}")
        else:
            prompt_preview = prompt.replace('\n', '\\n').replace('\r', '\\r')
            logger.debug(f"🚀 Full prompt: {prompt_preview}")
        
        # Character-based progress tracking
        start_time = time.time()
        heartbeat_active = True
        prompt_chars = len(prompt)
        
        def heartbeat_worker():
            """Send character-based progress updates during LLM calls with cancellation support."""
            nonlocal heartbeat_active
            last_update = 0
            while heartbeat_active:
                # Check for cancellation more frequently (every 2 seconds instead of 10)
                for _ in range(5):  # Sleep in smaller chunks to be more responsive to cancellation
                    if not heartbeat_active:
                        return
                    # Check cancellation every 2 seconds
                    if cancellation_token:
                        try:
                            cancellation_token.throw_if_cancelled()
                        except CancellationError:
                            # Stop heartbeat on cancellation
                            heartbeat_active = False
                            logger.info("Heartbeat worker stopped due to cancellation")
                            return
                    time.sleep(2)
                
                elapsed = time.time() - start_time
                
                # Only send update if significant time has passed
                if heartbeat_active and progress_callback and elapsed - last_update >= 10:
                    # Estimate progress based on elapsed time and expected generation time
                    # This is still an approximation but better than fixed 75%
                    
                    # Rough estimate: simple prompts take 10-30s, complex ones take 1-5min
                    estimated_total_time = max(30, min(300, prompt_chars / 100))  # 30s to 5min range
                    estimated_progress = min(95.0, 75.0 + (elapsed / estimated_total_time) * 20.0)
                    
                    # Create time description
                    if elapsed < 60:
                        time_desc = f"{elapsed:.0f}s elapsed"
                    else:
                        time_desc = f"{elapsed/60:.1f}m elapsed"
                    
                    # Estimate remaining time more intelligently
                    if estimated_progress < 95:
                        remaining_time = (estimated_total_time - elapsed)
                        if remaining_time > 60:
                            eta_desc = f"ETA: {remaining_time/60:.1f}m"
                        else:
                            eta_desc = f"ETA: {remaining_time:.0f}s"
                    else:
                        eta_desc = "ETA: <10s"
                    
                    progress_callback(SummarizationProgress(
                        status="generating_llm",
                        current_step=f"🤖 {self.provider} {self.model} generating response... ({time_desc}) ({eta_desc})",
                        percent=estimated_progress,  # Dynamic progress instead of fixed 75%
                        elapsed_seconds=elapsed,
                        model_name=self.model,
                        provider=self.provider
                    ))
                    last_update = elapsed
        
        # Start heartbeat if we have a progress callback
        heartbeat_thread = None
        if progress_callback:
            heartbeat_thread = threading.Thread(target=heartbeat_worker, daemon=True)
            heartbeat_thread.start()
        
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

        try:
            # Check cancellation before making the LLM call
            if cancellation_token:
                cancellation_token.throw_if_cancelled()
            
            result = self.llm_client.generate_dict(prompt, llm_progress_callback)
            logger.info(f"🚀 LLM returned result with {result.get('completion_tokens', 0)} completion tokens")
            return result
        except CancellationError:
            logger.info("LLM call cancelled")
            raise
        finally:
            # Stop heartbeat
            heartbeat_active = False
            if heartbeat_thread and heartbeat_thread.is_alive():
                heartbeat_thread.join(timeout=1)

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
            Tuple of (chunks, original_prompt_template, chunking_config)
        """
        logger.info(f"Setting up chunking configuration (model: {self.model})")
        
        # Check for cancellation
        if cancellation_token:
            cancellation_token.throw_if_cancelled()
            cancellation_token.wait_if_paused()
        
        # Generate base prompt for chunking calculation (but don't return it)
        base_prompt = self._generate_prompt("PLACEHOLDER_TEXT", style, prompt_template)
        
        # Get the original prompt template content for chunk processing
        if prompt_template:
            if isinstance(prompt_template, Path):
                try:
                    with open(prompt_template, "r", encoding="utf-8") as f:
                        original_template = f.read()
                except Exception as e:
                    logger.warning(f"Could not load template {prompt_template}: {e}")
                    # Fall back to style-based template
                    original_template = self._get_style_template(style)
            else:
                original_template = str(prompt_template)
        else:
            # Use style-based template
            original_template = self._get_style_template(style)
        
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
        
        return chunks, original_template, chunking_config

    def _get_style_template(self, style: str) -> str:
        """Get default template for a given style."""
        style_templates = {
            "bullet": "Create a concise bullet-point summary of the following text:\n\n{text}\n\nSummary:",
            "paragraph": "Write a clear paragraph summary of the following text:\n\n{text}\n\nSummary:",
            "structured": "Create a well-structured summary with key points organized by topics:\n\n{text}\n\nSummary:",
            "academic": "Provide an academic-style summary with methodology, findings, and conclusions:\n\n{text}\n\nSummary:",
            "executive": "Create an executive summary highlighting key business insights and recommendations:\n\n{text}\n\nSummary:",
            "general": "Summarize the following text, capturing the main ideas and important details:\n\n{text}\n\nSummary:",
        }
        return style_templates.get(style, style_templates["general"])

    def _process_chunks_batch(
        self,
        chunks: List[Any],
        original_prompt_template: str,
        style: str,
        progress_callback: Optional[Callable[[SummarizationProgress], None]] = None,
        cancellation_token: Optional[CancellationToken] = None,
        total_characters: Optional[int] = None,
        current_file_size: Optional[int] = None,
    ) -> Tuple[List[str], Dict[str, int]]:
        """
        Process all chunks and return summaries with statistics.
        
        Args:
            chunks: List of text chunks to process
            original_prompt_template: The original prompt template with {text} placeholders
            style: Summary style
            progress_callback: Optional progress callback
            cancellation_token: Optional cancellation token
        
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
            
            # Update progress with character tracking
            if progress_callback:
                chars_completed = int((total_characters or 0) * (0.20 + (0.60 * (i / len(chunks)))))
                file_chars_done = int((current_file_size or 0) * (0.20 + (0.60 * (i / len(chunks)))))
                progress_callback(SummarizationProgress(
                    status="processing_chunks",
                    current_step=f"Processing chunk {i+1}/{len(chunks)}...",
                    percent=20.0 + (60.0 * (i / len(chunks))),
                    chunk_number=i+1,
                    total_chunks=len(chunks),
                    model_name=self.model,
                    provider=self.provider,
                    total_characters=total_characters,
                    characters_completed=chars_completed,
                    current_file_size=current_file_size,
                    current_file_chars_done=file_chars_done
                ))
            
            # Generate prompt for this chunk
            chunk_prompt = generate_chunk_summary_prompt(
                chunk=chunk,
                original_prompt_template=original_prompt_template,
                style=style,
                chunk_context=f"Chunk {i+1} of {len(chunks)}",
                is_final_chunk=(i == len(chunks) - 1)
            )
            
            # Process the chunk with cancellation support
            chunk_result = self._call_llm_provider(chunk_prompt, progress_callback, cancellation_token)
            chunk_summary = chunk_result["summary"]
            chunk_summaries.append(chunk_summary)
            
            # Update progress after chunk completion with character tracking
            if progress_callback:
                chars_completed = int((total_characters or 0) * (0.20 + (0.60 * ((i + 1) / len(chunks)))))
                file_chars_done = int((current_file_size or 0) * (0.20 + (0.60 * ((i + 1) / len(chunks)))))
                progress_callback(SummarizationProgress(
                    status="chunk_completed",
                    current_step=f"Completed chunk {i+1}/{len(chunks)}",
                    percent=20.0 + (60.0 * ((i + 1) / len(chunks))),
                    chunk_number=i+1,
                    total_chunks=len(chunks),
                    model_name=self.model,
                    provider=self.provider,
                    total_characters=total_characters,
                    characters_completed=chars_completed,
                    current_file_size=current_file_size,
                    current_file_chars_done=file_chars_done
                ))
            
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
        original_prompt_template: str,
        progress_callback: Optional[Callable[[SummarizationProgress], None]] = None,
        cancellation_token: Optional[CancellationToken] = None,
        total_characters: Optional[int] = None,
        current_file_size: Optional[int] = None,
    ) -> Tuple[str, Dict[str, int]]:
        """
        Reassemble chunk summaries into final summary.
        
        Args:
            chunk_summaries: List of individual chunk summaries
            style: Summary style
            original_prompt_template: The original prompt template with {text} placeholders
            progress_callback: Optional progress callback
            cancellation_token: Optional cancellation token
        
        Returns:
            Tuple of (final_summary, additional_stats)
        """
        # Update progress for reassembly phase with character tracking
        if progress_callback:
            chars_completed = int((total_characters or 0) * 0.85)
            file_chars_done = int((current_file_size or 0) * 0.85)
            progress_callback(SummarizationProgress(
                status="reassembling",
                current_step="Assembling final summary from chunks...",
                percent=85.0,
                model_name=self.model,
                provider=self.provider,
                total_characters=total_characters,
                characters_completed=chars_completed,
                current_file_size=current_file_size,
                current_file_chars_done=file_chars_done
            ))
        
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
                    original_prompt_template=original_prompt_template,
                    model=model,
                    max_output_tokens=self.max_tokens
                )
                
                # Check for cancellation before final API call
                if cancellation_token:
                    cancellation_token.throw_if_cancelled()
                    cancellation_token.wait_if_paused()
                
                final_result = self._call_llm_provider(reassembly_prompt, progress_callback, cancellation_token)
                final_summary = final_result["summary"]
                
                # Track reassembly statistics
                additional_stats["reassembly_prompt_tokens"] = final_result.get("prompt_tokens", 0)
                additional_stats["reassembly_completion_tokens"] = final_result.get("completion_tokens", 0)
                
            except CancellationError:
                # Re-raise cancellation errors
                raise
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
        total_characters: Optional[int] = None,
        current_file_size: Optional[int] = None,
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
        chunks, original_prompt_template, chunking_config = self._setup_chunking_config(
            text, style, prompt_template, cancellation_token
        )
        
        # Step 2: Process all chunks
        chunk_summaries, processing_stats = self._process_chunks_batch(
            chunks, original_prompt_template, style, progress_callback, cancellation_token,
            total_characters, current_file_size
        )
        
        # Step 3: Reassemble summaries
        final_summary, reassembly_stats = self._reassemble_summaries(
            chunk_summaries, style, original_prompt_template, progress_callback, cancellation_token,
            total_characters, current_file_size
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
            "chunking_summary": get_chunking_summary(chunks, chunking_config)
        }

    def process(
        self,
        input_data: Any,
        dry_run: bool = False,
        progress_callback: Optional[Callable[[SummarizationProgress], None]] = None,
        cancellation_token: Optional[CancellationToken] = None,
        **kwargs: Any,
    ) -> ProcessorResult:
        """Process input and generate summary using unified LLM client."""
        # Extract parameters from kwargs for backwards compatibility
        style = kwargs.get('style', 'general')
        prompt_template = kwargs.get('prompt_template', None)
        # Also extract cancellation_token from kwargs if not passed as parameter
        if cancellation_token is None:
            cancellation_token = kwargs.get('cancellation_token', None)
        
        start_time = time.time()

        try:
            # Get text content first to set up character tracking
            if isinstance(input_data, str):
                text = input_data
                input_path = None
                logger.info(f"🔧 Processing string input of {len(text)} characters")
            else:
                input_path = Path(input_data)
                text = self._read_text_from_file(input_path)
                logger.info(f"🔧 Processing file input: {input_path} -> {len(text)} characters")

            if not text.strip():
                logger.error(f"🔧 Empty or invalid input text after reading")
                return ProcessorResult(
                    success=False,
                    errors=["Empty or invalid input text"],
                    dry_run=dry_run,
                )
            
            logger.info(f"🔧 Text validation passed: {len(text)} characters available for processing")

            # Set up character-based tracking
            total_characters = len(text)
            current_file_size = total_characters
            
            # Send initial progress update with character tracking
            if progress_callback:
                progress_callback(SummarizationProgress(
                    status="starting",
                    current_step="Starting summarization...",
                    percent=0.0,
                    model_name=self.model,
                    provider=self.provider,
                    total_characters=total_characters,
                    characters_completed=0,
                    current_file_size=current_file_size,
                    current_file_chars_done=0
                ))

            # Send reading progress update
            if progress_callback:
                progress_callback(SummarizationProgress(
                    status="loading_file",
                    current_step="Reading input text...",
                    percent=5.0,
                    model_name=self.model,
                    provider=self.provider,
                    total_characters=total_characters,
                    characters_completed=int(total_characters * 0.05),
                    current_file_size=current_file_size,
                    current_file_chars_done=int(current_file_size * 0.05)
                ))

            # Send tokenization progress update with character tracking
            if progress_callback:
                estimated_tokens = self._estimate_tokens(text)
                progress_callback(SummarizationProgress(
                    status="analyzing",
                    current_step="Analyzing text and generating prompt...",
                    percent=15.0,
                    tokens_processed=estimated_tokens,
                    model_name=self.model,
                    provider=self.provider,
                    total_characters=total_characters,
                    characters_completed=int(total_characters * 0.15),
                    current_file_size=current_file_size,
                    current_file_chars_done=int(current_file_size * 0.15)
                ))

            # Check if we need chunking for large texts
            estimated_tokens = self._estimate_tokens(text)
            chunking_threshold = self._calculate_smart_chunking_threshold(text, style, prompt_template)
            
            if estimated_tokens > chunking_threshold:  # Use intelligent chunking decision
                if progress_callback:
                    progress_callback(SummarizationProgress(
                        status="chunking",
                        current_step=f"📄 Text is large ({estimated_tokens:,} > {chunking_threshold:,} tokens), using intelligent chunking...",
                        percent=40.0,
                        tokens_processed=estimated_tokens,
                        model_name=self.model,
                        provider=self.provider,
                        total_characters=total_characters,
                        characters_completed=int(total_characters * 0.40),
                        current_file_size=current_file_size,
                        current_file_chars_done=int(current_file_size * 0.40)
                    ))
                
                result_stats = self._process_with_chunking(
                    text, style, prompt_template, progress_callback, cancellation_token,
                    total_characters, current_file_size
                )
            else:
                # Send progress update for single-unit processing
                if progress_callback:
                    utilization = (estimated_tokens / chunking_threshold) * 100 if chunking_threshold > 0 else 0
                    progress_callback(SummarizationProgress(
                        status="generating",
                        current_step=f"✅ Text fits in model capacity ({estimated_tokens:,} ≤ {chunking_threshold:,} tokens, {utilization:.1f}% utilization), processing as single unit...",
                        percent=40.0,
                        tokens_processed=estimated_tokens,
                        model_name=self.model,
                        provider=self.provider,
                        total_characters=total_characters,
                        characters_completed=int(total_characters * 0.40),
                        current_file_size=current_file_size,
                        current_file_chars_done=int(current_file_size * 0.40)
                    ))
                
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

                # Send generation progress update with character tracking
                if progress_callback:
                    chars_completed = int(total_characters * 0.50)
                    file_chars_done = int(current_file_size * 0.50)
                    progress_callback(SummarizationProgress(
                        status="generating",
                        current_step="Generating summary...",
                        percent=50.0,
                        tokens_processed=estimated_tokens,
                        model_name=self.model,
                        provider=self.provider,
                        total_characters=total_characters,
                        characters_completed=chars_completed,
                        current_file_size=current_file_size,
                        current_file_chars_done=file_chars_done
                    ))

                # Call LLM provider using unified client with cancellation support
                result_stats = self._call_llm_provider(prompt, progress_callback, cancellation_token)

            processing_time = time.time() - start_time

            # Send completion progress update with character tracking
            if progress_callback:
                progress_callback(SummarizationProgress(
                    status="completed",
                    current_step="Summary generation complete!",
                    percent=100.0,
                    tokens_processed=result_stats.get("prompt_tokens", 0),
                    tokens_generated=result_stats.get("completion_tokens", 0),
                    speed_tokens_per_sec=result_stats.get("total_tokens", 0) / processing_time if processing_time > 0 else 0,
                    model_name=self.model,
                    provider=self.provider,
                    total_characters=total_characters,
                    characters_completed=total_characters,
                    current_file_size=current_file_size,
                    current_file_chars_done=current_file_size
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

            # Send final completion progress update
            if progress_callback:
                progress_callback(SummarizationProgress(
                    status="completed",
                    current_step="Summary generation complete!",
                    percent=100.0,
                    model_name=self.model,
                    provider=self.provider
                ))

            return ProcessorResult(
                success=True,
                data=result_stats["summary"],
                metadata=metadata,
                dry_run=dry_run,
            )

        except CancellationError as e:
            processing_time = time.time() - start_time
            logger.info(f"Summarization cancelled: {e}")

            if progress_callback:
                progress_callback(SummarizationProgress(
                    status="cancelled",
                    current_step="Processing cancelled",
                    percent=0.0,
                    model_name=self.model,
                    provider=self.provider,
                    total_characters=total_characters,
                    characters_completed=0,
                    current_file_size=current_file_size,
                    current_file_chars_done=0
                ))

            return ProcessorResult(
                success=False,
                errors=[f"Processing cancelled: {e}"],
                metadata={
                    "provider": self.provider,
                    "model": self.model,
                    "style": style,
                    "processing_time": processing_time,
                    "cancelled": True,
                },
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
                    provider=self.provider,
                    total_characters=total_characters,
                    characters_completed=0,
                    current_file_size=current_file_size,
                    current_file_chars_done=0
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

