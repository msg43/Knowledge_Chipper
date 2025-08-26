"""
Intelligent Text Chunking for Knowledge System.

Provides advanced chunking strategies for optimal processing of documents
through AI models, with support for:
- Semantic boundary detection
- Topic coherence preservation
- Dynamic chunk sizing based on content density
- Cross-chunk context preservation
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from ..utils.text_utils import (
    estimate_tokens_improved,
    get_model_context_window,
    ChunkingConfig,
    TextChunk
)
from ..logger import get_logger

logger = get_logger(__name__)


class ChunkingStrategy(Enum):
    """Available chunking strategies."""
    SEMANTIC = "semantic"  # Topic-based boundaries
    STRUCTURAL = "structural"  # Section/paragraph boundaries
    SLIDING_WINDOW = "sliding_window"  # Fixed-size with overlap
    HYBRID = "hybrid"  # Combines semantic and structural


@dataclass
class EnhancedTextChunk(TextChunk):
    """Enhanced chunk with additional metadata."""
    topic_keywords: List[str] = field(default_factory=list)
    semantic_coherence: float = 0.0
    chunk_type: str = "content"  # content, header, summary, etc.
    context_before: Optional[str] = None
    context_after: Optional[str] = None
    parent_section: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class IntelligentChunker:
    """Advanced text chunking with multiple strategies."""
    
    # Semantic markers for boundaries
    SECTION_MARKERS = [
        r"^#{1,6}\s+",  # Markdown headers
        r"^[IVX]+\.\s+",  # Roman numerals
        r"^\d+\.\s+",  # Numbered sections
        r"^(Chapter|Section|Part)\s+\d+",  # Explicit sections
        r"^(Introduction|Conclusion|Abstract|Summary|References)",  # Common sections
    ]
    
    # Topic transition indicators
    TOPIC_TRANSITIONS = [
        "however", "moreover", "furthermore", "in contrast",
        "on the other hand", "additionally", "nevertheless",
        "in conclusion", "to summarize", "in summary",
        "turning to", "moving on to", "next we consider"
    ]
    
    def __init__(self, 
                 strategy: ChunkingStrategy = ChunkingStrategy.HYBRID,
                 model: str = "gpt-4",
                 preserve_context: bool = True):
        """
        Initialize the intelligent chunker.
        
        Args:
            strategy: Chunking strategy to use
            model: Model name for token estimation
            preserve_context: Whether to preserve context between chunks
        """
        self.strategy = strategy
        self.model = model
        self.preserve_context = preserve_context
        self.context_window = get_model_context_window(model)
    
    def chunk_text(self,
                   text: str,
                   config: ChunkingConfig,
                   metadata: Optional[Dict[str, Any]] = None) -> List[EnhancedTextChunk]:
        """
        Chunk text using the configured strategy.
        
        Args:
            text: Text to chunk
            config: Chunking configuration
            metadata: Optional metadata about the text
            
        Returns:
            List of enhanced text chunks
        """
        if not text.strip():
            return []
        
        # Choose chunking method based on strategy
        if self.strategy == ChunkingStrategy.SEMANTIC:
            return self._semantic_chunking(text, config, metadata)
        elif self.strategy == ChunkingStrategy.STRUCTURAL:
            return self._structural_chunking(text, config, metadata)
        elif self.strategy == ChunkingStrategy.SLIDING_WINDOW:
            return self._sliding_window_chunking(text, config, metadata)
        else:  # HYBRID
            return self._hybrid_chunking(text, config, metadata)
    
    def _semantic_chunking(self,
                          text: str,
                          config: ChunkingConfig,
                          metadata: Optional[Dict[str, Any]] = None) -> List[EnhancedTextChunk]:
        """Chunk based on semantic boundaries and topic coherence."""
        chunks = []
        
        # First, identify major sections
        sections = self._identify_sections(text)
        
        for section_idx, (section_text, section_title) in enumerate(sections):
            # Identify topic transitions within section
            paragraphs = section_text.split("\n\n")
            current_chunk_parts = []
            current_tokens = 0
            
            for para in paragraphs:
                para_tokens = estimate_tokens_improved(para, self.model)
                
                # Check if adding this paragraph would exceed limit
                if current_tokens + para_tokens > config.max_chunk_tokens and current_chunk_parts:
                    # Create chunk from accumulated paragraphs
                    chunk_text = "\n\n".join(current_chunk_parts)
                    chunks.append(self._create_enhanced_chunk(
                        chunk_text,
                        len(chunks),
                        section_title=section_title,
                        chunk_type="content"
                    ))
                    
                    # Start new chunk with overlap if configured
                    if config.overlap_tokens > 0 and self.preserve_context:
                        # Include last paragraph as context
                        current_chunk_parts = [current_chunk_parts[-1], para]
                        current_tokens = estimate_tokens_improved("\n\n".join(current_chunk_parts), self.model)
                    else:
                        current_chunk_parts = [para]
                        current_tokens = para_tokens
                else:
                    current_chunk_parts.append(para)
                    current_tokens += para_tokens
            
            # Don't forget the last chunk
            if current_chunk_parts:
                chunk_text = "\n\n".join(current_chunk_parts)
                chunks.append(self._create_enhanced_chunk(
                    chunk_text,
                    len(chunks),
                    section_title=section_title,
                    chunk_type="content"
                ))
        
        return self._add_context_to_chunks(chunks)
    
    def _structural_chunking(self,
                            text: str,
                            config: ChunkingConfig,
                            metadata: Optional[Dict[str, Any]] = None) -> List[EnhancedTextChunk]:
        """Chunk based on document structure (headers, sections)."""
        chunks = []
        sections = self._identify_sections(text)
        
        for section_idx, (section_text, section_title) in enumerate(sections):
            section_tokens = estimate_tokens_improved(section_text, self.model)
            
            if section_tokens <= config.max_chunk_tokens:
                # Section fits in one chunk
                chunks.append(self._create_enhanced_chunk(
                    section_text,
                    len(chunks),
                    section_title=section_title,
                    chunk_type="section"
                ))
            else:
                # Need to split section
                sub_chunks = self._split_large_section(section_text, section_title, config)
                chunks.extend(sub_chunks)
        
        return self._add_context_to_chunks(chunks)
    
    def _sliding_window_chunking(self,
                                text: str,
                                config: ChunkingConfig,
                                metadata: Optional[Dict[str, Any]] = None) -> List[EnhancedTextChunk]:
        """Traditional sliding window approach with fixed-size chunks."""
        chunks = []
        
        # Convert to approximate character count
        chars_per_token = 4
        max_chars = config.max_chunk_tokens * chars_per_token
        overlap_chars = config.overlap_tokens * chars_per_token
        
        start = 0
        while start < len(text):
            end = min(start + max_chars, len(text))
            
            # Try to find a good break point
            if end < len(text):
                # Look for sentence end
                for i in range(end, max(start, end - 100), -1):
                    if text[i] in '.!?':
                        end = i + 1
                        break
            
            chunk_text = text[start:end]
            chunks.append(self._create_enhanced_chunk(
                chunk_text,
                len(chunks),
                chunk_type="window"
            ))
            
            # Move start with overlap
            start = end - overlap_chars if end < len(text) else end
        
        return chunks
    
    def _hybrid_chunking(self,
                        text: str,
                        config: ChunkingConfig,
                        metadata: Optional[Dict[str, Any]] = None) -> List[EnhancedTextChunk]:
        """Combine semantic and structural approaches."""
        # Start with structural chunking
        structural_chunks = self._structural_chunking(text, config, metadata)
        
        # Refine with semantic boundaries
        refined_chunks = []
        for chunk in structural_chunks:
            if chunk.token_count > config.max_chunk_tokens * 0.8:
                # Large chunk - check for semantic breaks
                sub_chunks = self._refine_chunk_semantically(chunk, config)
                refined_chunks.extend(sub_chunks)
            else:
                refined_chunks.append(chunk)
        
        # Merge small adjacent chunks if possible
        final_chunks = self._merge_small_chunks(refined_chunks, config)
        
        return final_chunks
    
    def _identify_sections(self, text: str) -> List[Tuple[str, str]]:
        """Identify document sections based on headers and markers."""
        sections = []
        current_section = []
        current_title = "Introduction"
        
        lines = text.split("\n")
        for line in lines:
            # Check if line is a section header
            is_header = False
            for pattern in self.SECTION_MARKERS:
                if re.match(pattern, line, re.IGNORECASE):
                    # Save previous section
                    if current_section:
                        sections.append(("\n".join(current_section), current_title))
                    
                    # Start new section
                    current_title = line.strip()
                    current_section = []
                    is_header = True
                    break
            
            if not is_header:
                current_section.append(line)
        
        # Don't forget the last section
        if current_section:
            sections.append(("\n".join(current_section), current_title))
        
        # If no sections found, treat whole text as one section
        if not sections:
            sections = [(text, "Document")]
        
        return sections
    
    def _create_enhanced_chunk(self,
                              text: str,
                              chunk_id: int,
                              section_title: Optional[str] = None,
                              chunk_type: str = "content") -> EnhancedTextChunk:
        """Create an enhanced chunk with metadata."""
        # Extract topic keywords (simple version - could use NLP)
        keywords = self._extract_keywords(text)
        
        # Calculate semantic coherence (placeholder - could use embeddings)
        coherence = self._calculate_coherence(text)
        
        return EnhancedTextChunk(
            content=text,
            chunk_id=chunk_id,
            start_position=0,  # Would be calculated in real implementation
            end_position=len(text),
            token_count=estimate_tokens_improved(text, self.model),
            has_sentence_boundary=text.rstrip().endswith(('.', '!', '?')),
            has_paragraph_boundary=text.endswith('\n'),
            topic_keywords=keywords,
            semantic_coherence=coherence,
            chunk_type=chunk_type,
            parent_section=section_title,
            metadata={}
        )
    
    def _extract_keywords(self, text: str, top_n: int = 5) -> List[str]:
        """Extract key terms from text (simplified version)."""
        # This is a placeholder - in production, use TF-IDF or similar
        words = re.findall(r'\b[a-z]+\b', text.lower())
        word_freq = {}
        
        for word in words:
            if len(word) > 4 and word not in ['the', 'and', 'for', 'that', 'this']:
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # Get top N most frequent words
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, freq in sorted_words[:top_n]]
    
    def _calculate_coherence(self, text: str) -> float:
        """Calculate semantic coherence score (placeholder)."""
        # In production, this could use embeddings to measure topic consistency
        # For now, return a simple metric based on transition words
        transition_count = sum(1 for word in self.TOPIC_TRANSITIONS if word in text.lower())
        return min(1.0, 0.8 + (transition_count * 0.05))
    
    def _add_context_to_chunks(self, chunks: List[EnhancedTextChunk]) -> List[EnhancedTextChunk]:
        """Add context information to chunks."""
        if not self.preserve_context:
            return chunks
        
        for i, chunk in enumerate(chunks):
            # Add previous context
            if i > 0:
                prev_chunk = chunks[i-1]
                # Get last paragraph or last 200 chars
                context_text = prev_chunk.content.split('\n\n')[-1]
                if len(context_text) > 200:
                    context_text = "..." + context_text[-197:]
                chunk.context_before = context_text
            
            # Add next context
            if i < len(chunks) - 1:
                next_chunk = chunks[i+1]
                # Get first paragraph or first 200 chars
                context_text = next_chunk.content.split('\n\n')[0]
                if len(context_text) > 200:
                    context_text = context_text[:197] + "..."
                chunk.context_after = context_text
        
        return chunks
    
    def _split_large_section(self,
                            text: str,
                            section_title: str,
                            config: ChunkingConfig) -> List[EnhancedTextChunk]:
        """Split a large section into smaller chunks."""
        chunks = []
        paragraphs = text.split("\n\n")
        current_chunk = []
        current_tokens = 0
        
        for para in paragraphs:
            para_tokens = estimate_tokens_improved(para, self.model)
            
            if current_tokens + para_tokens > config.max_chunk_tokens and current_chunk:
                chunk_text = "\n\n".join(current_chunk)
                chunks.append(self._create_enhanced_chunk(
                    chunk_text,
                    len(chunks),
                    section_title=section_title,
                    chunk_type="section_part"
                ))
                current_chunk = [para]
                current_tokens = para_tokens
            else:
                current_chunk.append(para)
                current_tokens += para_tokens
        
        if current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            chunks.append(self._create_enhanced_chunk(
                chunk_text,
                len(chunks),
                section_title=section_title,
                chunk_type="section_part"
            ))
        
        return chunks
    
    def _refine_chunk_semantically(self,
                                  chunk: EnhancedTextChunk,
                                  config: ChunkingConfig) -> List[EnhancedTextChunk]:
        """Refine a chunk by finding semantic boundaries."""
        # Look for topic transitions
        text = chunk.content
        paragraphs = text.split("\n\n")
        
        # Find strong transition points
        split_points = []
        for i, para in enumerate(paragraphs[:-1]):
            # Check if next paragraph starts with transition
            next_para = paragraphs[i+1]
            for transition in self.TOPIC_TRANSITIONS:
                if next_para.lower().startswith(transition):
                    split_points.append(i+1)
                    break
        
        if not split_points:
            return [chunk]
        
        # Create new chunks at split points
        refined_chunks = []
        start = 0
        
        for split in split_points:
            chunk_text = "\n\n".join(paragraphs[start:split])
            refined_chunks.append(self._create_enhanced_chunk(
                chunk_text,
                chunk.chunk_id + len(refined_chunks),
                section_title=chunk.parent_section,
                chunk_type="refined"
            ))
            start = split
        
        # Last chunk
        if start < len(paragraphs):
            chunk_text = "\n\n".join(paragraphs[start:])
            refined_chunks.append(self._create_enhanced_chunk(
                chunk_text,
                chunk.chunk_id + len(refined_chunks),
                section_title=chunk.parent_section,
                chunk_type="refined"
            ))
        
        return refined_chunks
    
    def _merge_small_chunks(self,
                           chunks: List[EnhancedTextChunk],
                           config: ChunkingConfig) -> List[EnhancedTextChunk]:
        """Merge small adjacent chunks if they fit within limits."""
        if len(chunks) <= 1:
            return chunks
        
        merged_chunks = []
        current_chunk = chunks[0]
        
        for next_chunk in chunks[1:]:
            combined_tokens = current_chunk.token_count + next_chunk.token_count
            
            # Check if we can merge
            if (combined_tokens <= config.max_chunk_tokens * 0.9 and
                current_chunk.parent_section == next_chunk.parent_section):
                # Merge chunks
                current_chunk = self._create_enhanced_chunk(
                    current_chunk.content + "\n\n" + next_chunk.content,
                    len(merged_chunks),
                    section_title=current_chunk.parent_section,
                    chunk_type="merged"
                )
            else:
                # Can't merge, save current and start new
                merged_chunks.append(current_chunk)
                current_chunk = next_chunk
        
        # Don't forget the last chunk
        merged_chunks.append(current_chunk)
        
        return merged_chunks


def create_optimal_chunks(text: str,
                         model: str = "gpt-4",
                         strategy: ChunkingStrategy = ChunkingStrategy.HYBRID,
                         prompt_template: str = "",
                         max_output_tokens: int = 2000) -> List[EnhancedTextChunk]:
    """
    Create optimal chunks for the given text and model.
    
    Args:
        text: Text to chunk
        model: Model name
        strategy: Chunking strategy to use
        prompt_template: Prompt template (for calculating overhead)
        max_output_tokens: Maximum output tokens
        
    Returns:
        List of enhanced text chunks
    """
    # Calculate chunking configuration
    from ..utils.text_utils import calculate_chunking_config
    config = calculate_chunking_config(text, model, prompt_template, max_output_tokens)
    
    # Create chunker and process text
    chunker = IntelligentChunker(strategy=strategy, model=model)
    chunks = chunker.chunk_text(text, config)
    
    logger.info(f"Created {len(chunks)} chunks using {strategy.value} strategy")
    return chunks
