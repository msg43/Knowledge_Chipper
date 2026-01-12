"""
API Key Store for Daemon

Stores API keys in memory so they can be accessed by Knowledge_Chipper code
without relying on environment variables (which don't work reliably in PyInstaller apps).
"""

# Module-level storage for API keys
_api_keys = {
    "openai": None,
    "anthropic": None,
    "google": None,
}


def set_api_key(provider: str, key: str) -> None:
    """Set an API key for a provider."""
    if provider in _api_keys:
        _api_keys[provider] = key


def get_api_key(provider: str) -> str | None:
    """Get an API key for a provider."""
    return _api_keys.get(provider)


def load_from_config(config_dict: dict) -> None:
    """Load API keys from daemon config dictionary."""
    api_keys = config_dict.get("api_keys", {})
    if api_keys.get("openai"):
        set_api_key("openai", api_keys["openai"])
    if api_keys.get("anthropic"):
        set_api_key("anthropic", api_keys["anthropic"])
    if api_keys.get("google"):
        set_api_key("google", api_keys["google"])
