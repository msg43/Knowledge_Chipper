"""SuperChunk module package.

Hierarchical RAG pipeline for long transcripts without timestamps.
This package provides configuration, validators, and a model-agnostic
LLM adapter, along with processing stages implemented across modules.

Default window preset is Balanced with adaptive switching enabled.
"""

from .config import SuperChunkConfig
from .validators import (
    ClaimItem,
    LocalContradictionItem,
    JargonItem,
    Landmarks,
    Chunk,
    GuideMap,
)
from .llm_adapter import SuperChunkLLMAdapter

__all__ = [
    "SuperChunkConfig",
    "ClaimItem",
    "LocalContradictionItem",
    "JargonItem",
    "Landmarks",
    "Chunk",
    "GuideMap",
    "SuperChunkLLMAdapter",
]
