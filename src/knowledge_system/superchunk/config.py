from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Optional

from ..config import get_settings


class WindowPreset(str, Enum):
    PRECISION = "precision"
    BALANCED = "balanced"
    NARRATIVE = "narrative"


@dataclass
class WindowSettings:
    min_tokens: int
    max_tokens: int
    overlap_tokens: int


@dataclass
class SuperChunkConfig:
    """Configuration for SuperChunk pipeline.

    Defaults follow docs/plan.md. Balanced preset by default with adaptive switching enabled.
    """

    preset: WindowPreset = WindowPreset.BALANCED
    adaptive_switching: bool = True

    # Preset windows (tokens)
    precision: WindowSettings = field(
        default_factory=lambda: WindowSettings(
            min_tokens=2500, max_tokens=3500, overlap_tokens=280
        )
    )
    balanced: WindowSettings = field(
        default_factory=lambda: WindowSettings(
            min_tokens=4000, max_tokens=5000, overlap_tokens=280
        )
    )
    narrative: WindowSettings = field(
        default_factory=lambda: WindowSettings(
            min_tokens=5000, max_tokens=8000, overlap_tokens=280
        )
    )

    # Extraction counts and caps
    non_obvious_claims_count: int = 7
    max_local_contradictions: int = 3
    jargon_terms_count: int = 5
    max_quote_words: int = 50

    # Verification
    verify_top_percent: float = 0.2
    min_confidence: float = 0.7
    exclude_if_confidence_delta_below: float = -0.3

    # Retrieval
    topk_linking: int = 20
    topk_section: int = 10
    dedupe_threshold: float = 0.88
    neighbor_threshold: float = 0.70

    # Performance
    max_concurrent_calls: int = 3
    batch_size: int = 10
    circuit_breaker: int = 3
    cooldown_seconds: int = 60

    # Temperatures
    temperature_mapper: float = 0.1
    temperature_extract: float = 0.1
    temperature_link: float = 0.3
    temperature_synth: float = 0.5
    temperature_verify: float = 0.0

    def get_window(self) -> WindowSettings:
        if self.preset == WindowPreset.PRECISION:
            return self.precision
        if self.preset == WindowPreset.NARRATIVE:
            return self.narrative
        return self.balanced

    @staticmethod
    def from_global_settings() -> "SuperChunkConfig":
        settings = get_settings()
        _ = settings
        return SuperChunkConfig()

    def with_overrides(
        self,
        *,
        preset: Optional[str] = None,
        verify_top_percent: Optional[float] = None,
        max_quote_words: Optional[int] = None,
        max_concurrent_calls: Optional[int] = None,
    ) -> "SuperChunkConfig":
        cfg = SuperChunkConfig(**self.__dict__)
        if preset:
            try:
                cfg.preset = WindowPreset(preset)
            except Exception:
                pass
        if verify_top_percent is not None:
            cfg.verify_top_percent = verify_top_percent
        if max_quote_words is not None:
            cfg.max_quote_words = max_quote_words
        if max_concurrent_calls is not None:
            cfg.max_concurrent_calls = max_concurrent_calls
        return cfg
