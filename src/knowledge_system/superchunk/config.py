from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from ..config import get_settings
from ..utils.text_utils import get_model_context_window


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

    # LLM configuration (passed from summarizer)
    provider: str | None = None
    model: str | None = None

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
            min_tokens=4000,
            max_tokens=6000,
            overlap_tokens=280,  # Reduced to fit in 8k models
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
        # If model is specified, calculate dynamic windows
        if self.model:
            return self._get_dynamic_window()

        # Otherwise use preset defaults
        if self.preset == WindowPreset.PRECISION:
            return self.precision
        if self.preset == WindowPreset.NARRATIVE:
            return self.narrative
        return self.balanced

    def _get_dynamic_window(self) -> WindowSettings:
        """Calculate window settings dynamically based on model's context window."""
        if not self.model:
            return self.get_window()  # Fallback to preset

        # Get the model's actual context window
        context_window = get_model_context_window(self.model)

        # Calculate appropriate window sizes based on context
        # Reserve space for: safety margin, output tokens, and prompt overhead
        if context_window >= 100000:  # 128k models (GPT-4o, Claude 3)
            # Use ~75% of context for very large models
            max_window = min(75000, int(context_window * 0.75))
            min_window = max_window - 10000
            overlap = 500
        elif context_window >= 30000:  # 32k+ models
            # Use ~70% of context for large models
            max_window = min(20000, int(context_window * 0.70))
            min_window = max_window - 5000
            overlap = 400
        elif context_window >= 15000:  # 16k models (GPT-3.5-turbo)
            # Use ~60% of context for medium models
            max_window = min(9000, int(context_window * 0.60))
            min_window = max_window - 2000
            overlap = 300
        elif context_window >= 8000:  # 8k models (GPT-4)
            # Use ~50% of context for standard models
            max_window = min(4000, int(context_window * 0.50))
            min_window = max_window - 1000
            overlap = 280
        else:  # 4k models
            # Use ~40% of context for small models
            max_window = min(1600, int(context_window * 0.40))
            min_window = max_window - 400
            overlap = 200

        # Adjust based on preset preferences
        if self.preset == WindowPreset.PRECISION:
            # Precision mode: smaller windows for accuracy
            max_window = int(max_window * 0.7)
            min_window = int(min_window * 0.7)
        elif self.preset == WindowPreset.NARRATIVE:
            # Narrative mode: larger windows for context
            max_window = int(max_window * 1.2)
            min_window = int(min_window * 1.2)

        return WindowSettings(
            min_tokens=max(1000, min_window),  # Never go below 1000 tokens
            max_tokens=max(1500, max_window),  # Never go below 1500 tokens
            overlap_tokens=overlap,
        )

    @staticmethod
    def from_global_settings() -> SuperChunkConfig:
        settings = get_settings()
        _ = settings
        return SuperChunkConfig()

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary of this configuration.

        Converts Enum and nested dataclasses to plain Python types that json can handle.
        """
        return {
            "preset": (
                self.preset.value
                if isinstance(self.preset, WindowPreset)
                else str(self.preset)
            ),
            "adaptive_switching": bool(self.adaptive_switching),
            "provider": self.provider,
            "model": self.model,
            # windows
            "precision": asdict(self.precision),
            "balanced": asdict(self.balanced),
            "narrative": asdict(self.narrative),
            # extraction caps
            "non_obvious_claims_count": int(self.non_obvious_claims_count),
            "max_local_contradictions": int(self.max_local_contradictions),
            "jargon_terms_count": int(self.jargon_terms_count),
            "max_quote_words": int(self.max_quote_words),
            # verification
            "verify_top_percent": float(self.verify_top_percent),
            "min_confidence": float(self.min_confidence),
            "exclude_if_confidence_delta_below": float(
                self.exclude_if_confidence_delta_below
            ),
            # retrieval
            "topk_linking": int(self.topk_linking),
            "topk_section": int(self.topk_section),
            "dedupe_threshold": float(self.dedupe_threshold),
            "neighbor_threshold": float(self.neighbor_threshold),
            # performance
            "max_concurrent_calls": int(self.max_concurrent_calls),
            "batch_size": int(self.batch_size),
            "circuit_breaker": int(self.circuit_breaker),
            "cooldown_seconds": int(self.cooldown_seconds),
            # temperatures
            "temperature_mapper": float(self.temperature_mapper),
            "temperature_extract": float(self.temperature_extract),
            "temperature_link": float(self.temperature_link),
            "temperature_synth": float(self.temperature_synth),
            "temperature_verify": float(self.temperature_verify),
        }

    def with_overrides(
        self,
        *,
        preset: str | None = None,
        verify_top_percent: float | None = None,
        max_quote_words: int | None = None,
        max_concurrent_calls: int | None = None,
    ) -> SuperChunkConfig:
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
