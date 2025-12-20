"""
Configuration for Claims-First Pipeline

Provides configuration dataclass and validation for claims-first processing options.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TranscriptSource(str, Enum):
    """Transcript source options."""
    AUTO = "auto"  # Try YouTube first, upgrade to Whisper if poor quality
    YOUTUBE = "youtube"  # Always use YouTube transcripts
    WHISPER = "whisper"  # Always use Whisper transcription


class EvaluatorModel(str, Enum):
    """Evaluator model options for Stage 2."""
    GEMINI = "gemini"  # Use Gemini for evaluation (budget)
    CLAUDE = "claude"  # Use Claude for evaluation (quality)
    CONFIGURABLE = "configurable"  # Let user choose based on content


@dataclass
class ClaimsFirstConfig:
    """
    Configuration for claims-first pipeline.
    
    Attributes:
        enabled: Whether to use claims-first pipeline (vs speaker-first)
        transcript_source: Which transcript source to use (auto, youtube, whisper)
        youtube_quality_threshold: Minimum quality score for YouTube transcripts (0.0-1.0)
        evaluator_model: Which LLM to use for claim evaluation
        lazy_attribution_min_importance: Minimum importance score for speaker attribution
        store_candidates: Whether to store candidate claims for re-evaluation
        context_window_seconds: Context window for speaker attribution (seconds)
        fuzzy_match_threshold: Threshold for fuzzy quote matching (0.0-1.0)
    """
    
    enabled: bool = False
    transcript_source: TranscriptSource = TranscriptSource.AUTO
    youtube_quality_threshold: float = 0.7
    evaluator_model: EvaluatorModel = EvaluatorModel.CONFIGURABLE
    lazy_attribution_min_importance: int = 7
    store_candidates: bool = True
    context_window_seconds: int = 60
    fuzzy_match_threshold: float = 0.7
    
    # Model-specific settings
    miner_model: str = "gemini-2.0-flash"
    evaluator_model_gemini: str = "gemini-2.0-flash"
    evaluator_model_claude: str = "claude-3-5-sonnet-20241022"
    attribution_model: str = "gemini-2.0-flash"
    
    def __post_init__(self):
        """Validate configuration values."""
        if not 0.0 <= self.youtube_quality_threshold <= 1.0:
            raise ValueError(f"youtube_quality_threshold must be 0.0-1.0, got {self.youtube_quality_threshold}")
        
        if not 0 <= self.lazy_attribution_min_importance <= 10:
            raise ValueError(f"lazy_attribution_min_importance must be 0-10, got {self.lazy_attribution_min_importance}")
        
        if not 0.0 <= self.fuzzy_match_threshold <= 1.0:
            raise ValueError(f"fuzzy_match_threshold must be 0.0-1.0, got {self.fuzzy_match_threshold}")
        
        if self.context_window_seconds < 10:
            raise ValueError(f"context_window_seconds must be >= 10, got {self.context_window_seconds}")
    
    @classmethod
    def from_dict(cls, config_dict: dict) -> "ClaimsFirstConfig":
        """Create config from dictionary (e.g., from YAML settings)."""
        # Handle enum conversions
        if "transcript_source" in config_dict:
            config_dict["transcript_source"] = TranscriptSource(config_dict["transcript_source"])
        if "evaluator_model" in config_dict:
            config_dict["evaluator_model"] = EvaluatorModel(config_dict["evaluator_model"])
        
        return cls(**config_dict)
    
    def to_dict(self) -> dict:
        """Convert config to dictionary for serialization."""
        return {
            "enabled": self.enabled,
            "transcript_source": self.transcript_source.value,
            "youtube_quality_threshold": self.youtube_quality_threshold,
            "evaluator_model": self.evaluator_model.value,
            "lazy_attribution_min_importance": self.lazy_attribution_min_importance,
            "store_candidates": self.store_candidates,
            "context_window_seconds": self.context_window_seconds,
            "fuzzy_match_threshold": self.fuzzy_match_threshold,
            "miner_model": self.miner_model,
            "evaluator_model_gemini": self.evaluator_model_gemini,
            "evaluator_model_claude": self.evaluator_model_claude,
            "attribution_model": self.attribution_model,
        }
    
    def get_evaluator_model_name(self) -> str:
        """Get the actual model name to use for evaluation based on config."""
        if self.evaluator_model == EvaluatorModel.GEMINI:
            return self.evaluator_model_gemini
        elif self.evaluator_model == EvaluatorModel.CLAUDE:
            return self.evaluator_model_claude
        else:
            # CONFIGURABLE - return the gemini one as default, let user override
            return self.evaluator_model_gemini


# Default configuration instance
DEFAULT_CONFIG = ClaimsFirstConfig()

