"""
Feedback Reasons Configuration Loader

Singleton that loads feedback_reasons.yaml and provides:
- get_reasons(entity_type, verdict) -> {key: label}
- get_label(entity_type, verdict, key) -> label or None
- get_all_reasons() -> full config dict (for API)
- validate_reason(entity_type, verdict, key) -> bool
"""

import yaml
from pathlib import Path
from typing import Optional

from ..logger import get_logger

logger = get_logger(__name__)


class FeedbackConfig:
    """
    Soft-coded feedback reasons loaded from YAML.
    
    Adding a reason to the YAML automatically propagates to:
    - API endpoint (Web UI buttons)
    - Prompt injection (human-readable labels)
    - TasteEngine validation
    """
    
    CONFIG_PATH = Path(__file__).parent.parent / "data" / "feedback_reasons.yaml"
    
    # Minimal fallback if YAML missing
    DEFAULT_CONFIG = {
        "claim": {
            "reject": {"other": "Other"},
            "accept": {"other": "Other"}
        },
        "person": {
            "reject": {"other": "Other"},
            "accept": {"other": "Other"}
        },
        "jargon": {
            "reject": {"other": "Other"},
            "accept": {"other": "Other"}
        },
        "concept": {
            "reject": {"other": "Other"},
            "accept": {"other": "Other"}
        }
    }
    
    def __init__(self):
        self._config = self._load_config()
    
    def _load_config(self) -> dict:
        """Load YAML config, fall back to defaults if missing."""
        if not self.CONFIG_PATH.exists():
            logger.warning(f"Feedback config not found at {self.CONFIG_PATH}, using defaults")
            return self.DEFAULT_CONFIG
        
        try:
            with open(self.CONFIG_PATH, 'r') as f:
                config = yaml.safe_load(f)
            
            # Remove schema_version from entity types
            config.pop('schema_version', None)
            
            logger.info(f"Loaded feedback config with {len(config)} entity types")
            return config
            
        except Exception as e:
            logger.error(f"Failed to load feedback config: {e}")
            return self.DEFAULT_CONFIG
    
    def get_reasons(self, entity_type: str, verdict: str) -> dict[str, str]:
        """Get {key: label} dict for entity type and verdict."""
        entity_config = self._config.get(entity_type, {})
        return entity_config.get(verdict, {"other": "Other"})
    
    def get_label(self, entity_type: str, verdict: str, key: str) -> Optional[str]:
        """Get human-readable label for a reason key."""
        reasons = self.get_reasons(entity_type, verdict)
        return reasons.get(key)
    
    def validate_reason(self, entity_type: str, verdict: str, key: str) -> bool:
        """Check if a reason key is valid for entity type and verdict."""
        reasons = self.get_reasons(entity_type, verdict)
        return key in reasons
    
    def get_all_reasons(self) -> dict:
        """Get full config dict (for API endpoint)."""
        return self._config
    
    def reload(self):
        """Reload config from disk (for hot-reload)."""
        self._config = self._load_config()


# Module-level singleton
_feedback_config: Optional[FeedbackConfig] = None


def get_feedback_config() -> FeedbackConfig:
    """Get the global FeedbackConfig instance."""
    global _feedback_config
    if _feedback_config is None:
        _feedback_config = FeedbackConfig()
    return _feedback_config
