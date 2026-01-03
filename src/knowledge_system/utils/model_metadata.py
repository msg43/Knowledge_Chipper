"""
Model Metadata Database

Tracks access requirements, tiers, and status for LLM models across providers.
Used to provide clear UX about which models users can access.
"""

from enum import Enum
from typing import Optional


class ModelStatus(str, Enum):
    """Model availability status."""
    PUBLIC = "public"           # Widely available to all API key holders
    GATED = "gated"            # Requires special access/approval
    EXPERIMENTAL = "experimental"  # Experimental/preview - may require allowlist
    DEPRECATED = "deprecated"   # No longer available
    TIER_RESTRICTED = "tier_restricted"  # Requires specific usage tier


class ModelMetadata:
    """Metadata about a model's access requirements."""
    
    def __init__(
        self,
        model_id: str,
        status: ModelStatus = ModelStatus.PUBLIC,
        tier_required: Optional[str] = None,
        note: Optional[str] = None,
        display_name: Optional[str] = None,
    ):
        self.model_id = model_id
        self.status = status
        self.tier_required = tier_required
        self.note = note
        self.display_name = display_name or model_id


# Known model metadata by provider
KNOWN_MODELS = {
    "openai": {
        # GPT-5.x series
        "gpt-5.2": ModelMetadata(
            "gpt-5.2",
            status=ModelStatus.GATED,
            note="Latest flagship - May require waitlist access"
        ),
        "gpt-5.1": ModelMetadata(
            "gpt-5.1",
            status=ModelStatus.GATED,
            note="May require special access"
        ),
        "gpt-4.1": ModelMetadata(
            "gpt-4.1",
            status=ModelStatus.PUBLIC,
            note="Generally available"
        ),
        
        # GPT-4o series (PUBLIC)
        "gpt-4o": ModelMetadata("gpt-4o", status=ModelStatus.PUBLIC),
        "gpt-4o-2024-11-20": ModelMetadata("gpt-4o-2024-11-20", status=ModelStatus.PUBLIC),
        "gpt-4o-2024-08-06": ModelMetadata("gpt-4o-2024-08-06", status=ModelStatus.PUBLIC),
        "gpt-4o-2024-05-13": ModelMetadata("gpt-4o-2024-05-13", status=ModelStatus.PUBLIC),
        "gpt-4o-mini": ModelMetadata("gpt-4o-mini", status=ModelStatus.PUBLIC),
        "gpt-4o-mini-2024-07-18": ModelMetadata("gpt-4o-mini-2024-07-18", status=ModelStatus.PUBLIC),
        
        # o1 series (TIER RESTRICTED)
        "o1": ModelMetadata(
            "o1",
            status=ModelStatus.TIER_RESTRICTED,
            tier_required="tier-5",
            note="Requires usage tier 5"
        ),
        "o1-preview": ModelMetadata(
            "o1-preview",
            status=ModelStatus.TIER_RESTRICTED,
            tier_required="tier-5",
            note="Requires usage tier 5"
        ),
        "o1-mini": ModelMetadata(
            "o1-mini",
            status=ModelStatus.TIER_RESTRICTED,
            tier_required="tier-5",
            note="Requires usage tier 5"
        ),
        
        # GPT-4 Turbo (PUBLIC)
        "gpt-4-turbo": ModelMetadata("gpt-4-turbo", status=ModelStatus.PUBLIC),
        "gpt-4-turbo-2024-04-09": ModelMetadata("gpt-4-turbo-2024-04-09", status=ModelStatus.PUBLIC),
        "gpt-4-0125-preview": ModelMetadata("gpt-4-0125-preview", status=ModelStatus.PUBLIC),
        
        # GPT-4 (PUBLIC)
        "gpt-4": ModelMetadata("gpt-4", status=ModelStatus.PUBLIC),
        "gpt-4-0613": ModelMetadata("gpt-4-0613", status=ModelStatus.PUBLIC),
        
        # GPT-3.5 Turbo (PUBLIC)
        "gpt-3.5-turbo": ModelMetadata("gpt-3.5-turbo", status=ModelStatus.PUBLIC),
        "gpt-3.5-turbo-0125": ModelMetadata("gpt-3.5-turbo-0125", status=ModelStatus.PUBLIC),
        
        # Open weight models
        "gpt-oss-120b": ModelMetadata(
            "gpt-oss-120b",
            status=ModelStatus.PUBLIC,
            note="Open weight model - runs locally"
        ),
        "gpt-oss-20b": ModelMetadata(
            "gpt-oss-20b",
            status=ModelStatus.PUBLIC,
            note="Open weight model - runs locally"
        ),
    },
    
    "anthropic": {
        # Claude 4.5 series
        "claude-opus-4.5": ModelMetadata(
            "claude-opus-4.5",
            status=ModelStatus.GATED,
            note="Latest Opus - May require specific plan"
        ),
        "claude-sonnet-4.5": ModelMetadata(
            "claude-sonnet-4.5",
            status=ModelStatus.GATED,
            note="May require specific plan"
        ),
        "claude-haiku-4.5": ModelMetadata(
            "claude-haiku-4.5",
            status=ModelStatus.PUBLIC,
            note="Generally available"
        ),
        
        # Claude 4 series
        "claude-opus-4-20250514": ModelMetadata(
            "claude-opus-4-20250514",
            status=ModelStatus.GATED,
            note="May require specific plan"
        ),
        "claude-sonnet-4-20250514": ModelMetadata(
            "claude-sonnet-4-20250514",
            status=ModelStatus.PUBLIC
        ),
        
        # Claude 3.5 series (PUBLIC)
        "claude-3-5-sonnet-20241022": ModelMetadata(
            "claude-3-5-sonnet-20241022",
            status=ModelStatus.PUBLIC,
            display_name="Claude 3.5 Sonnet (Oct 2024)"
        ),
        "claude-3-5-sonnet-20240620": ModelMetadata(
            "claude-3-5-sonnet-20240620",
            status=ModelStatus.PUBLIC,
            display_name="Claude 3.5 Sonnet (Jun 2024)"
        ),
        "claude-3-5-haiku-20241022": ModelMetadata(
            "claude-3-5-haiku-20241022",
            status=ModelStatus.PUBLIC,
            display_name="Claude 3.5 Haiku"
        ),
        "claude-3-5-sonnet-latest": ModelMetadata(
            "claude-3-5-sonnet-latest",
            status=ModelStatus.PUBLIC,
            display_name="Claude 3.5 Sonnet (Latest)"
        ),
        
        # Claude 3 series (PUBLIC)
        "claude-3-opus-20240229": ModelMetadata(
            "claude-3-opus-20240229",
            status=ModelStatus.PUBLIC,
            display_name="Claude 3 Opus"
        ),
        "claude-3-sonnet-20240229": ModelMetadata(
            "claude-3-sonnet-20240229",
            status=ModelStatus.PUBLIC,
            display_name="Claude 3 Sonnet"
        ),
        "claude-3-haiku-20240307": ModelMetadata(
            "claude-3-haiku-20240307",
            status=ModelStatus.PUBLIC,
            display_name="Claude 3 Haiku"
        ),
    },
    
    "google": {
        # Gemini 3 series
        "gemini-3-pro": ModelMetadata(
            "gemini-3-pro",
            status=ModelStatus.GATED,
            note="May require allowlist access"
        ),
        "gemini-3-flash": ModelMetadata(
            "gemini-3-flash",
            status=ModelStatus.GATED,
            note="May require allowlist access"
        ),
        "gemini-3-deep-think": ModelMetadata(
            "gemini-3-deep-think",
            status=ModelStatus.GATED,
            note="Requires AI Ultra subscription"
        ),
        
        # Gemini 2.5 series
        "gemini-2.5-flash-lite": ModelMetadata(
            "gemini-2.5-flash-lite",
            status=ModelStatus.PUBLIC
        ),
        "gemini-2.5-flash": ModelMetadata(
            "gemini-2.5-flash",
            status=ModelStatus.PUBLIC
        ),
        
        # Gemini 2.0 series (PUBLIC)
        "gemini-2.0-flash-exp": ModelMetadata(
            "gemini-2.0-flash-exp",
            status=ModelStatus.EXPERIMENTAL,
            note="Experimental - may have rate limits"
        ),
        "gemini-2.0-flash-thinking-exp": ModelMetadata(
            "gemini-2.0-flash-thinking-exp",
            status=ModelStatus.EXPERIMENTAL,
            note="Experimental thinking model"
        ),
        
        # Gemini 1.5 series (PUBLIC)
        "gemini-1.5-pro": ModelMetadata(
            "gemini-1.5-pro",
            status=ModelStatus.PUBLIC
        ),
        "gemini-1.5-pro-latest": ModelMetadata(
            "gemini-1.5-pro-latest",
            status=ModelStatus.PUBLIC
        ),
        "gemini-1.5-flash": ModelMetadata(
            "gemini-1.5-flash",
            status=ModelStatus.PUBLIC
        ),
        "gemini-1.5-flash-latest": ModelMetadata(
            "gemini-1.5-flash-latest",
            status=ModelStatus.PUBLIC
        ),
        
        # Gemini 1.0 series (PUBLIC)
        "gemini-pro": ModelMetadata(
            "gemini-pro",
            status=ModelStatus.PUBLIC
        ),
        
        # Experimental models
        "gemini-exp-1206": ModelMetadata(
            "gemini-exp-1206",
            status=ModelStatus.EXPERIMENTAL,
            note="Experimental - may require allowlist"
        ),
    },
}


def get_model_metadata(provider: str, model_id: str) -> ModelMetadata:
    """
    Get metadata for a specific model.
    
    Returns known metadata if available, otherwise returns default PUBLIC status.
    """
    provider = provider.lower()
    
    if provider in KNOWN_MODELS and model_id in KNOWN_MODELS[provider]:
        return KNOWN_MODELS[provider][model_id]
    
    # Default for unknown models
    return ModelMetadata(
        model_id,
        status=ModelStatus.PUBLIC,
        note="Access requirements unknown"
    )


def get_status_badge(status: ModelStatus) -> str:
    """Get emoji badge for model status."""
    badges = {
        ModelStatus.PUBLIC: "✅",
        ModelStatus.GATED: "🔒",
        ModelStatus.EXPERIMENTAL: "🧪",
        ModelStatus.DEPRECATED: "⚠️",
        ModelStatus.TIER_RESTRICTED: "⭐",
    }
    return badges.get(status, "")


def get_status_label(status: ModelStatus) -> str:
    """Get human-readable label for model status."""
    labels = {
        ModelStatus.PUBLIC: "Public",
        ModelStatus.GATED: "Gated",
        ModelStatus.EXPERIMENTAL: "Experimental",
        ModelStatus.DEPRECATED: "Deprecated",
        ModelStatus.TIER_RESTRICTED: "Tier Required",
    }
    return labels.get(status, "Unknown")

