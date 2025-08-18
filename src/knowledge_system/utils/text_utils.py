"""
Text processing utilities for the knowledge system
Text processing utilities for the knowledge system.
"""

import re
import time
from dataclasses import dataclass
from pathlib import Path

from ..logger import get_logger

logger = get_logger(__name__)

# Cache for dynamic model context windows
_model_context_cache = {}
_cache_timestamp = 0
_cache_ttl = 300  # 5 minutes


# Model context window definitions
MODEL_CONTEXT_WINDOWS = {
    # OpenAI models - specific versions
    "gpt-3.5-turbo-0125": 16385,
    "gpt-3.5-turbo-1106": 16385,
    "gpt-4-0613": 8192,
    "gpt-4-0125-preview": 128000,  # Current GPT-4 preview model
    "gpt-4-turbo-2024-04-09": 128000,
    "gpt-4o-2024-05-13": 128000,
    "gpt-4o-2024-08-06": 128000,
    "gpt-4o-mini-2024-07-18": 128000,
    # Legacy OpenAI model names for backwards compatibility
    "gpt-3.5-turbo": 16385,
    "gpt-4": 8192,
    "gpt-4-turbo": 128000,
    "gpt-4-turbo-preview": 128000,
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    # Anthropic models - specific versions
    "claude-3-haiku-20240307": 200000,
    "claude-3-sonnet-20240229": 200000,
    "claude-3-opus-20240229": 200000,
    "claude-3-5-sonnet-20240620": 200000,
    "claude-3-5-sonnet-20241022": 200000,
    "claude-3-5-haiku-20241022": 200000,
    "claude-instant-1.2": 100000,
    # Local models - specific versions
    "llama2:7b-chat": 4096,
    "llama2:13b-chat": 4096,
    "llama3.1:8b-instruct": 128000,
    "llama3.2:1b": 128000,
    "llama3.2:3b": 128000,
    "llama3.2:3b-instruct": 128000,
    "llama3.2:latest": 128000,  # Latest llama3.2 variant
    "mistral:7b-instruct-v0.2": 32768,
    "codellama:7b-instruct": 16384,
    "codellama:13b-instruct": 16384,
    "phi3:3.8b-mini-instruct": 128000,
    "qwen2.5:7b-instruct": 32768,
    "qwen2.5:14b-instruct": 32768,
    "qwen2.5:32b-instruct": 32768,
    "qwen2.5:72b-instruct-q6_K": 32768,
    "qwen2.5-coder:7b-instruct": 32768,
    # Legacy local model names for backwards compatibility
    "llama2-7b": 4096,
    "llama2-13b": 4096,
    "llama2-70b": 4096,
    "codellama-7b": 16384,
    "codellama-13b": 16384,
    "codellama-34b": 16384,
    "mistral-7b": 32768,
    "mixtral-8x7b": 32768,
    # Default fallback
    "default": 4096,
}


@dataclass
class ChunkingConfig:
    """Configuration for intelligent text chunking."""

    max_chunk_tokens: int
    overlap_tokens: int = 200
    min_chunk_tokens: int = 500
    prefer_sentence_boundaries: bool = True
    prefer_paragraph_boundaries: bool = True
    safety_margin_ratio: float = 0.15  # 15% safety margin


@dataclass
class TextChunk:
    """Represents a chunk of text with metadata."""

    content: str
    chunk_id: int
    start_position: int
    end_position: int
    token_count: int
    has_sentence_boundary: bool = False
    has_paragraph_boundary: bool = False


@dataclass
class ChunkingSummary:
    """Summary of the chunking process."""

    total_chunks: int
    total_tokens: int
    avg_chunk_size: int
    overlap_tokens: int
    chunking_strategy: str
    estimated_cost_factor: float  # Multiplier for cost estimation


def estimate_tokens_improved(text: str, model: str = "default") -> int:
    """
    Improved token estimation that considers model-specific tokenization
    Improved token estimation that considers model-specific tokenization.

    Args:
        text: Text to estimate tokens for
        model: Model name for better estimation

    Returns:
        Estimated token count
    """
    if not text:
        return 0

    # More sophisticated estimation based on model type
    if any(claude in model.lower() for claude in ["claude", "anthropic"]):
        # Anthropic models tend to have slightly different tokenization
        # Use a more conservative estimate
        return int(len(text) / 3.5)
    elif "gpt" in model.lower():
        # OpenAI GPT models - standard estimation
        # Account for more efficient tokenization in newer models
        if any(model_name in model.lower() for model_name in ["gpt-4o", "gpt-4-turbo"]):
            return int(len(text) / 4.2)
        else:
            return int(len(text) / 4.0)
    elif any(
        local_name in model.lower()
        for local_name in ["llama", "mistral", "qwen", "codellama"]
    ):
        # Local models often have different tokenization patterns
        return int(len(text) / 3.8)
    else:
        # Default estimation
        return int(len(text) / 4.0)


def _detect_context_window_from_ollama(model: str) -> int | None:
    """
    Detect context window by querying Ollama for model information
    Detect context window by querying Ollama for model information.

    Args:
        model: Model name

    Returns:
        Context window size in tokens, or None if not available
    """
    try:
        from ..utils.ollama_manager import get_ollama_manager

        ollama_manager = get_ollama_manager()
        if not ollama_manager.is_service_running():
            return None

        # Get available models from Ollama
        available_models = ollama_manager.get_available_models()

        # Find the model
        model_info = None
        for model_obj in available_models:
            if model_obj.name == model:
                model_info = model_obj
                break

        if not model_info:
            return None

        # Intelligent mapping based on model family and parameters
        family = model_info.family.lower()
        parameters = model_info.parameters.lower()

        # Map based on known model families
        if "llama" in family:
            if "3.2" in model or "3.1" in model:
                return 128000  # Llama 3.1/3.2 series have 128K context
            elif "70b" in parameters or "70b" in model:
                return 4096  # Larger models often have smaller context due to memory
            else:
                return 128000  # Most modern Llama variants support 128K

        elif "mistral" in family:
            if "7b" in parameters:
                return 32768  # Mistral 7B variants typically 32K
            else:
                return 32768

        elif "qwen" in family:
            if "2.5" in model:
                return 32768  # Qwen 2.5 series
            else:
                return 32768

        elif "phi" in family:
            return 128000  # Phi models typically have large context windows

        elif "codellama" in family:
            return 16384  # CodeLlama typically 16K

        # For unknown families, make educated guess based on parameters
        if "1b" in parameters or "3b" in parameters:
            return 128000  # Smaller models often have larger context windows
        elif "7b" in parameters or "8b" in parameters:
            return 128000  # Standard size
        elif "13b" in parameters or "14b" in parameters:
            return 32768  # Larger models, smaller context
        elif "70b" in parameters or "32b" in parameters:
            return 4096  # Very large models, limited context

        # Default for unknown cases
        return 32768

    except Exception as e:
        logger.debug(f"Failed to detect context window from Ollama for {model}: {e}")
        return None


def get_model_context_window(model: str) -> int:
    """
    Get the context window size for a specific model with dynamic detection
    Get the context window size for a specific model with dynamic detection.

    Args:
        model: Model name

    Returns:
        Context window size in tokens
    """
    global _cache_timestamp

    # Normalize model name
    model_normalized = model.lower().strip()
    current_time = time.time()

    # Check cache first (includes custom models and fresh dynamic detections)
    if model_normalized in _model_context_cache:
        # For cached entries, check if they need refresh (except custom additions)
        if (
            current_time - _cache_timestamp < _cache_ttl
            or model_normalized not in MODEL_CONTEXT_WINDOWS
        ):
            return _model_context_cache[model_normalized]

    # Check static definitions (most reliable)
    if model_normalized in MODEL_CONTEXT_WINDOWS:
        context_size = MODEL_CONTEXT_WINDOWS[model_normalized]
        _model_context_cache[model_normalized] = context_size
        return context_size

    # Check for partial matches in static definitions
    for known_model, context_size in MODEL_CONTEXT_WINDOWS.items():
        if known_model in model_normalized or model_normalized in known_model:
            _model_context_cache[model_normalized] = context_size
            return context_size

    # Try dynamic detection from Ollama
    dynamic_context = _detect_context_window_from_ollama(model_normalized)
    if dynamic_context:
        logger.info(
            f"📡 Dynamically detected context window for '{model}': {dynamic_context:,} tokens"
        )
        _model_context_cache[model_normalized] = dynamic_context
        _cache_timestamp = current_time
        return dynamic_context

    # Default fallback
    logger.warning(
        f"⚠️ Unknown model '{model}', using default context window of {MODEL_CONTEXT_WINDOWS['default']:,} tokens"
    )
    default_context = MODEL_CONTEXT_WINDOWS["default"]
    _model_context_cache[model_normalized] = default_context
    return default_context


def refresh_model_context_cache() -> None:
    """
    Force refresh of the model context window cache

    Force refresh of the model context window cache.
    Useful when new models are installed or Ollama is restarted.
    """
    global _cache_timestamp
    _model_context_cache.clear()
    _cache_timestamp = 0
    logger.info("🔄 Model context window cache refreshed")


def add_custom_model_context(model: str, context_window: int) -> None:
    """
    Add a custom context window for a specific model
    Add a custom context window for a specific model.

    Args:
        model: Model name
        context_window: Context window size in tokens
    """
    model_normalized = model.lower().strip()
    # Mutate cache without rebinding
    _model_context_cache[model_normalized] = context_window
    logger.info(
        f"✅ Added custom context window for '{model}': {context_window:,} tokens"
    )


def get_cached_models() -> dict[str, int]:
    """
    Get all currently cached model context windows
    Get all currently cached model context windows.

    Returns:
        Dictionary of model names to context window sizes
    """
    return _model_context_cache.copy()


def calculate_chunking_config(
    text: str,
    model: str,
    prompt_template: str,
    max_output_tokens: int,
) -> ChunkingConfig:
    """
    Calculate optimal chunking configuration based on all parameters
    Calculate optimal chunking configuration based on all parameters.

    Args:
        text: Text to be chunked
        model: Model name
        prompt_template: The prompt template to be used
        max_output_tokens: Maximum tokens for output

    Returns:
        ChunkingConfig with optimal settings
    """
    context_window = get_model_context_window(model)

    # Estimate prompt tokens
    prompt_tokens = estimate_tokens_improved(prompt_template, model)

    # Add basic overhead for chunk processing instructions
    prompt_tokens += 50  # Standard overhead for chunk processing

    # Calculate safety margin
    safety_margin = int(context_window * 0.15)  # 15% safety margin

    # Calculate maximum tokens available for input text
    available_for_text = (
        context_window - prompt_tokens - max_output_tokens - safety_margin
    )

    # Ensure we have a reasonable minimum
    if available_for_text < 1000:
        logger.warning(
            f"Very limited space for text input: {available_for_text} tokens"
        )
        available_for_text = max(500, available_for_text)

    # Calculate overlap (10% of chunk size, minimum 100, maximum 500)
    overlap_tokens = max(100, min(500, int(available_for_text * 0.1)))

    # Calculate minimum chunk size (20% of max chunk size, minimum 300)
    min_chunk_tokens = max(300, int(available_for_text * 0.2))

    return ChunkingConfig(
        max_chunk_tokens=available_for_text,
        overlap_tokens=overlap_tokens,
        min_chunk_tokens=min_chunk_tokens,
        prefer_sentence_boundaries=True,
        prefer_paragraph_boundaries=True,
        safety_margin_ratio=0.15,
    )


def split_at_sentence_boundaries(text: str, max_length: int) -> list[str]:
    """
    Split text at sentence boundaries while respecting maximum length
    Split text at sentence boundaries while respecting maximum length.

    Args:
        text: Text to split
        max_length: Maximum character length per chunk

    Returns:
        List of text chunks split at sentence boundaries
    """
    if len(text) <= max_length:
        return [text]

    # Sentence ending patterns (more comprehensive)
    sentence_patterns = [
        r"(?<=[.!?])\s+(?=[A-Z])",  # Standard sentence endings
        r"(?<=[.!?])\s*\n+\s*",  # Sentence endings with newlines
        r"(?<=\.)\s+(?=\d+\.)",  # Numbered lists (1. 2. etc.)
        r"(?<=[.!?])\s*[-—]\s*",  # Sentence with dash
    ]

    chunks = []
    remaining_text = text

    while len(remaining_text) > max_length:
        # Find the best split point within the max_length
        best_split = None
        best_split_pos = 0

        # Try sentence patterns in order of preference
        for pattern in sentence_patterns:
            matches = list(re.finditer(pattern, remaining_text[:max_length]))
            if matches:
                # Use the last sentence boundary within the limit
                match = matches[-1]
                best_split = match.end()
                best_split_pos = best_split
                break

        if best_split is None:
            # No sentence boundary found, split at word boundary
            words = remaining_text[:max_length].split()
            if len(words) > 1:
                # Remove the last word to ensure we don't split in the middle
                best_split_pos = len(" ".join(words[:-1]))
            else:
                # Single long word, force split
                best_split_pos = max_length

        # Add chunk
        chunk = remaining_text[:best_split_pos].strip()
        if chunk:
            chunks.append(chunk)

        remaining_text = remaining_text[best_split_pos:].strip()

    # Add remaining text
    if remaining_text.strip():
        chunks.append(remaining_text.strip())

    return chunks


def create_intelligent_chunks(
    text: str, config: ChunkingConfig, model: str = "default"
) -> list[TextChunk]:
    """
    Create intelligent text chunks based on configuration and model
    Create intelligent text chunks based on configuration and model.

    Args:
        text: Text to chunk
        config: Chunking configuration
        model: Model name for token estimation

    Returns:
        List of TextChunk objects
    """
    if not text.strip():
        return []

    # Convert token limits to approximate character limits for splitting
    # Use a conservative ratio to ensure we don't exceed token limits
    chars_per_token = 3.5  # Conservative estimate
    max_chunk_chars = int(config.max_chunk_tokens * chars_per_token)

    # Choose splitting strategy based on preferences
    if config.prefer_paragraph_boundaries and "\n\n" in text:
        text_chunks = text.split("\n\n")
        strategy = "paragraph_boundaries"
    elif config.prefer_sentence_boundaries:
        text_chunks = split_at_sentence_boundaries(text, max_chunk_chars)
        strategy = "sentence_boundaries"
    else:
        # Simple word-boundary splitting
        words = text.split()
        words_per_chunk = max_chunk_chars // 5  # Rough estimate
        text_chunks = []
        for i in range(0, len(words), words_per_chunk):
            chunk_words = words[i : i + words_per_chunk]
            text_chunks.append(" ".join(chunk_words))
        strategy = "word_boundaries"

    # Create TextChunk objects with metadata
    chunks: list[TextChunk] = []
    current_position = 0

    for i, chunk_text in enumerate(text_chunks):
        chunk_text = chunk_text.strip()
        if not chunk_text:
            continue

        # Calculate actual token count for this chunk
        token_count = estimate_tokens_improved(chunk_text, model)

        # Check boundaries
        has_sentence_boundary = bool(re.search(r"[.!?]\s*$", chunk_text))
        has_paragraph_boundary = chunk_text.endswith("\n")

        chunk = TextChunk(
            content=chunk_text,
            chunk_id=len(chunks),
            start_position=current_position,
            end_position=current_position + len(chunk_text),
            token_count=token_count,
            has_sentence_boundary=has_sentence_boundary,
            has_paragraph_boundary=has_paragraph_boundary,
        )

        chunks.append(chunk)
        current_position += len(chunk_text)

    logger.info(f"Created {len(chunks)} chunks using {strategy} strategy")
    return chunks


def generate_chunk_summary_prompt(
    chunk: TextChunk,
    original_prompt_template: str,
    chunk_context: str = "",
    is_final_chunk: bool = False,
) -> str:
    """
    Generate a specialized prompt for summarizing a chunk
    Generate a specialized prompt for summarizing a chunk.

    Args:
        chunk: The text chunk to summarize
        original_prompt_template: Original prompt template
        chunk_context: Additional context about the chunk's position
        is_final_chunk: Whether this is the final chunk

    Returns:
        Specialized prompt for the chunk
    """
    # Create chunk-specific context

    # Create chunk-specific context
    chunk_info = f"This is chunk {chunk.chunk_id + 1}"
    if not is_final_chunk:
        chunk_info += " of a longer document"

    if chunk_context:
        chunk_info += f". Context: {chunk_context}"

    # Modify the original prompt to work better with chunks
    if "{text}" in original_prompt_template:
        chunk_prompt = original_prompt_template.replace("{text}", chunk.content)
    else:
        # Fallback if no {text} placeholder
        chunk_prompt = f"{original_prompt_template}\n\n{chunk.content}"

    # Add chunk-specific instructions
    chunk_instructions = f"""

{chunk_info}. Please provide a focused summary of this section that:
1. Captures the main points and key information
2. Maintains important details and context
3. Can be combined with other section summaries later

Text to summarize:
{chunk.content}"""

    return chunk_instructions


def reassemble_chunk_summaries(
    chunk_summaries: list[str],
    original_prompt_template: str,
    model: str,
    max_output_tokens: int,
) -> str:
    """
    Intelligently reassemble chunk summaries into a coherent final summary
    Intelligently reassemble chunk summaries into a coherent final summary.

    Args:
        chunk_summaries: List of individual chunk summaries
        original_prompt_template: Original prompt template
        model: Model name
        max_output_tokens: Maximum tokens for final output

    Returns:
        Final reassembled summary
    """
    if not chunk_summaries:
        return ""

    if len(chunk_summaries) == 1:
        return chunk_summaries[0]

    # Combine all chunk summaries
    combined_summaries = "\n\n".join(
        [f"Section {i+1}:\n{summary}" for i, summary in enumerate(chunk_summaries)]
    )

    # Create reassembly prompt
    reassembly_prompt = f"""I have summarized a long document in sections. Please create a final, coherent summary that combines these section summaries into a unified whole.

Section summaries to combine:
{combined_summaries}

Please create a final summary that:
1. Integrates all the key points from the sections
2. Eliminates redundancy and repetition
3. Maintains logical flow and coherence
4. Provides a comprehensive overview of the entire document

Final Summary:"""

    return reassembly_prompt


def get_chunking_summary(
    chunks: list[TextChunk], config: ChunkingConfig
) -> ChunkingSummary:
    """
    Generate a summary of the chunking process
    Generate a summary of the chunking process.

    Args:
        chunks: List of created chunks
        config: Chunking configuration used

    Returns:
        ChunkingSummary with process information
    """
    if not chunks:
        return ChunkingSummary(
            total_chunks=0,
            total_tokens=0,
            avg_chunk_size=0,
            overlap_tokens=config.overlap_tokens,
            chunking_strategy="none",
            estimated_cost_factor=1.0,
        )

    total_tokens = sum(chunk.token_count for chunk in chunks)
    avg_chunk_size = total_tokens // len(chunks)

    # Determine strategy used
    strategy = "sentence_boundaries"
    if any(chunk.has_paragraph_boundary for chunk in chunks):
        strategy = "paragraph_boundaries"
    elif not any(chunk.has_sentence_boundary for chunk in chunks):
        strategy = "word_boundaries"

    # Estimate cost factor (chunking increases processing cost)
    cost_factor = 1.0 + (len(chunks) - 1) * 0.1  # 10% overhead per additional chunk

    return ChunkingSummary(
        total_chunks=len(chunks),
        total_tokens=total_tokens,
        avg_chunk_size=avg_chunk_size,
        overlap_tokens=config.overlap_tokens,
        chunking_strategy=strategy,
        estimated_cost_factor=cost_factor,
    )


# Existing functions remain unchanged
def load_interjections(interjections_file: Path) -> set[str]:
    """
    Load interjections from a text file
    Load interjections from a text file.

    Args:
        interjections_file: Path to the text file containing interjections

    Returns:
        Set of interjection strings to strip
    """
    interjections = set()

    try:
        if interjections_file.exists():
            with open(interjections_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith(
                        "#"
                    ):  # Skip empty lines and comments
                        interjections.add(line)
            logger.info(
                f"Loaded {len(interjections)} interjections from {interjections_file}"
            )
        else:
            logger.warning(f"Interjections file not found: {interjections_file}")
    except Exception as e:
        logger.error(f"Error loading interjections from {interjections_file}: {e}")

    return interjections


def strip_interjections(text: str, interjections: set[str]) -> str:
    """
    Strip interjections from text
    Strip interjections from text.

    Args:
        text: The text to process
        interjections: Set of interjection strings to remove

    Returns:
        Text with interjections removed
    """
    if not interjections:
        return text

    # Create a regex pattern that matches any of the interjections
    # Escape special regex characters and join with | for alternation
    escaped_interjections = [re.escape(interjection) for interjection in interjections]
    pattern = "|".join(escaped_interjections)

    # Remove the interjections and clean up extra whitespace
    cleaned_text = re.sub(pattern, "", text)
    cleaned_text = re.sub(
        r"\s+", " ", cleaned_text
    )  # Replace multiple spaces with single space
    cleaned_text = cleaned_text.strip()

    return cleaned_text


def strip_bracketed_content(text: str) -> str:
    """
    Strip ANY content between brackets from text
    Strip ANY content between brackets from text.

    Args:
        text: The text to process

    Returns:
        Text with all bracketed content removed

    Examples:
        >>> strip_bracketed_content("Hello [music] world [applause]")
        "Hello world"
        >>> strip_bracketed_content("The speaker said [inaudible] something important")
        "The speaker said something important"
    """
    if not text:
        return text

    # Remove any content between square brackets including the brackets
    # This pattern matches [ followed by any characters (non-greedy) followed by ]
    cleaned_text = re.sub(r"\[.*?\]", "", text)

    # Clean up extra whitespace that might be left behind
    cleaned_text = re.sub(
        r"\s+", " ", cleaned_text
    )  # Replace multiple spaces with single space
    cleaned_text = cleaned_text.strip()

    return cleaned_text


def get_default_interjections_file() -> Path:
    """
    Get the default path to the interjections file
    Get the default path to the interjections file.

    Returns:
        Path to the default interjections file
    """
    # Look for the file in the data directory relative to the project root

    # Look for the file in the data directory relative to the project root
    project_root = Path(__file__).parent.parent.parent.parent
    return project_root / "data" / "interjections.txt"
