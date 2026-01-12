"""
Daemon Configuration

Loads from environment variables with sensible defaults.
All settings can be overridden with KC_ prefix environment variables.
"""

import json
import logging
import os
from pathlib import Path
from typing import Literal, Optional

from pydantic_settings import BaseSettings

# Initialize logger
logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Server Configuration
    host: str = "127.0.0.1"  # Localhost only for security
    port: int = 8765
    reload: bool = False  # True for development

    # CORS - Allow GetReceipts.org to connect
    cors_origins: list[str] = [
        "http://localhost:3000",  # GetReceipts dev
        "http://localhost:3001",  # GetReceipts dev (alternate port)
        "https://getreceipts.org",  # GetReceipts prod
        "https://www.getreceipts.org",  # GetReceipts www
    ]

    # Processing
    max_concurrent_jobs: int = 3
    job_timeout_seconds: int = 3600  # 1 hour

    # Processing Defaults (user configurable)
    default_whisper_model: Literal["tiny", "base", "small", "medium", "large-v3"] = "medium"
    default_llm_provider: Optional[Literal["openai", "anthropic", "google"]] = "anthropic"
    default_llm_model: Optional[str] = None  # Will use first validated model from provider API
    auto_upload_enabled: bool = True
    process_full_pipeline: bool = True

    # Feature Flags
    bypass_device_auth: bool = True  # Set to False to re-enable device authentication

    # Database - Use existing Knowledge_Chipper database
    # Default to project root, but can be overridden with KC_DATABASE_PATH env var
    database_path: str = os.path.expanduser(
        os.environ.get(
            "KC_DATABASE_PATH",
            "~/Projects/Knowledge_Chipper/knowledge_system.db"
        )
    )

    # Config file for persistence
    config_file_path: str = os.path.expanduser(
        "~/Library/Application Support/Knowledge_Chipper/daemon_config.json"
    )

    # GetReceipts API
    getreceipts_api_url: str = "https://getreceipts.org/api"

    # Device Auth (from existing system)
    device_credentials_path: str = os.path.expanduser(
        "~/.getreceipts/device_auth.json"
    )

    # Output directories - Use existing Knowledge_Chipper paths
    output_directory: str = os.path.expanduser("~/Documents/Knowledge_Chipper/output")
    downloads_directory: str = os.path.expanduser(
        "~/Documents/Knowledge_Chipper/output/downloads/youtube"
    )

    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = os.path.expanduser(
        "~/Library/Logs/KnowledgeChipper/daemon.log"
    )

    class Config:
        env_prefix = "KC_"  # Environment variables: KC_HOST, KC_PORT, etc.
        case_sensitive = False

    def save_config(self) -> None:
        """Save user-configurable settings to file, including API keys."""
        config_path = Path(self.config_file_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        user_config = {
            "default_whisper_model": self.default_whisper_model,
            "default_llm_provider": self.default_llm_provider,
            "default_llm_model": self.default_llm_model,
            "auto_upload_enabled": self.auto_upload_enabled,
            "process_full_pipeline": self.process_full_pipeline,
            # API Keys (securely stored)
            "api_keys": {
                "openai": os.environ.get("OPENAI_API_KEY", ""),
                "anthropic": os.environ.get("ANTHROPIC_API_KEY", ""),
                "google": os.environ.get("GOOGLE_API_KEY", ""),
            }
        }
        
        config_path.write_text(json.dumps(user_config, indent=2))
        
        # Set secure permissions (only owner can read/write)
        try:
            config_path.chmod(0o600)
        except Exception as e:
            logger.warning(f"Could not set secure permissions on config file: {e}")

    def load_config(self) -> None:
        """Load user-configurable settings from file, including API keys."""
        config_path = Path(self.config_file_path)
        if not config_path.exists():
            return
        
        try:
            user_config = json.loads(config_path.read_text())
            
            # Verify secure permissions
            try:
                mode = config_path.stat().st_mode
                if mode & 0o077:  # Check if group/others have any permissions
                    logger.warning(
                        f"Config file has insecure permissions. "
                        f"Run: chmod 600 '{config_path}'"
                    )
            except Exception:
                pass  # Don't fail on permission check
            if "default_whisper_model" in user_config:
                self.default_whisper_model = user_config["default_whisper_model"]
            if "default_llm_provider" in user_config:
                self.default_llm_provider = user_config["default_llm_provider"]
            if "default_llm_model" in user_config:
                self.default_llm_model = user_config["default_llm_model"]
            if "auto_upload_enabled" in user_config:
                self.auto_upload_enabled = user_config["auto_upload_enabled"]
            if "process_full_pipeline" in user_config:
                self.process_full_pipeline = user_config["process_full_pipeline"]
            
            # Load API keys into environment variables AND daemon API key store
            if "api_keys" in user_config:
                api_keys = user_config["api_keys"]
                
                # Load into environment (for compatibility)
                if api_keys.get("openai"):
                    os.environ["OPENAI_API_KEY"] = api_keys["openai"]
                    logger.info("✅ Loaded OpenAI API key from config")
                if api_keys.get("anthropic"):
                    os.environ["ANTHROPIC_API_KEY"] = api_keys["anthropic"]
                    logger.info("✅ Loaded Anthropic API key from config")
                if api_keys.get("google"):
                    os.environ["GOOGLE_API_KEY"] = api_keys["google"]
                    logger.info("✅ Loaded Google API key from config")
                
                # ALSO load into daemon API key store (works reliably in PyInstaller)
                try:
                    from daemon.services.api_key_store import load_from_config
                    load_from_config(user_config)
                    logger.info("✅ Loaded API keys into daemon key store")
                except Exception as e:
                    logger.warning(f"Failed to load API keys into daemon store: {e}")
                    
        except Exception as e:
            logger.warning(f"Failed to load config: {e}")
            pass  # Use defaults if config is invalid

    def get_device_id(self) -> Optional[str]:
        """Get device ID from credentials file."""
        creds_path = Path(self.device_credentials_path)
        if not creds_path.exists():
            return None
        try:
            creds = json.loads(creds_path.read_text())
            return creds.get("device_id")
        except Exception:
            return None

    def is_device_linked(self) -> bool:
        """Check if device is linked to a GetReceipts account."""
        creds_path = Path(self.device_credentials_path)
        if not creds_path.exists():
            return False
        try:
            creds = json.loads(creds_path.read_text())
            return bool(creds.get("device_id") and creds.get("device_key"))
        except Exception:
            return False


# Global settings instance
settings = Settings()

# Load saved config on startup
settings.load_config()
