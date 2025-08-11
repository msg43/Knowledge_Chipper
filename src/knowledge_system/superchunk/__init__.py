"""SuperChunk module package.

Hierarchical RAG pipeline for long transcripts without timestamps.
This package provides configuration, validators, and a model-agnostic
LLM adapter, along with processing stages implemented across modules.

Default window preset is Balanced with adaptive switching enabled.
"""

from .config import SuperChunkConfig
from .llm_adapter import SuperChunkLLMAdapter
from .validators import (
    Chunk,
    ClaimItem,
    GuideMap,
    JargonItem,
    Landmarks,
    LocalContradictionItem,
)

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
