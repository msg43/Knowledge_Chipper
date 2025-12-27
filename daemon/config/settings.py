"""
Daemon Configuration

Loads from environment variables with sensible defaults.
All settings can be overridden with KC_ prefix environment variables.
"""

import os
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Server Configuration
    host: str = "127.0.0.1"  # Localhost only for security
    port: int = 8765
    reload: bool = False  # True for development

    # CORS - Allow GetReceipts.org to connect
    cors_origins: list[str] = [
        "http://localhost:3000",  # GetReceipts dev
        "https://getreceipts.org",  # GetReceipts prod
        "https://www.getreceipts.org",  # GetReceipts www
    ]

    # Processing
    max_concurrent_jobs: int = 3
    job_timeout_seconds: int = 3600  # 1 hour

    # Database - Use existing Knowledge_Chipper database
    database_path: str = os.path.expanduser(
        "~/Library/Application Support/Knowledge_Chipper/knowledge_system.db"
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


# Global settings instance
settings = Settings()

