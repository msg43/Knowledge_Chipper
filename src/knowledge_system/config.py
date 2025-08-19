"""
Configuration management for Knowledge System

Configuration management for Knowledge System.
Supports YAML files, environment variables, and settings persistence.
"""

import os
import re
from pathlib import Path
from typing import Any

import yaml  # type: ignore
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_valid_whisper_models() -> list[str]:
    """Extract valid Whisper model names from the configuration pattern."""
    # Extract from the pattern in TranscriptionConfig
    pattern = r"^(tiny|base|small|medium|large|large-v2|large-v3)$"
    # Parse the pattern to extract model names
    match = re.search(r"\((.*?)\)", pattern)
    if match:
        models_str = match.group(1)
        return [model.strip() for model in models_str.split("|")]
    # Fallback if pattern parsing fails
    return ["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"]


class AppConfig(BaseModel):
    """Application-level configuration."""

    name: str = "Knowledge_Chipper"
    version: str = "0.0.0"  # runtime will prefer package __version__
    debug: bool = False


class PathsConfig(BaseModel):
    """Configuration for file paths."""

    # Base data directory (user will need to set this)
    data_dir: str = Field(
        default="",
        description="Base data directory (must be configured by user)",
    )
    # Output directory (user will need to set this)
    output_dir: str = Field(
        default="",
        description="Output directory (must be configured by user)",
    )
    # Cache directory (user will need to set this)
    cache_dir: str = Field(
        default="",
        description="Cache directory (must be configured by user)",
    )

    # Input/output paths (user will need to set these)
    input_dir: str = Field(
        default="",
        description="Input directory (must be configured by user)",
    )
    output: str = Field(
        default="",
        description="Output path (must be configured by user)",
    )
    transcripts: str = Field(
        default="",
        description="Transcripts directory (must be configured by user)",
    )
    summaries: str = Field(
        default="",
        description="Summaries directory (must be configured by user)",
    )
    mocs: str = Field(
        default="",
        description="Maps of Content directory (must be configured by user)",
    )
    cache: str = Field(
        default="",
        description="Cache directory (must be configured by user)",
    )
    logs_dir: str = Field(default="./logs", description="Logs directory")

    # Additional paths for backward compatibility
    input: str = Field(
        default="",
        description="Input directory (must be configured by user)",
    )
    logs: str = Field(
        default="./logs", description="Logs directory (alias for logs_dir)"
    )

    @field_validator(
        "data_dir",
        "output_dir",
        "cache_dir",
        "logs_dir",
        "input",
        "output",
        "transcripts",
        "summaries",
        "mocs",
        "cache",
        "logs",
    )
    def expand_paths(cls, v: Any) -> str:
        """Expand user paths."""
        return str(Path(v).expanduser()) if v else v


class PerformanceConfig(BaseModel):
    """Performance and hardware optimization settings."""

    # Performance profile selection
    profile: str = Field(
        default="auto",
        description="Performance profile: auto, battery_saver, balanced, high_performance, maximum_performance",
    )

    # Hardware detection settings
    enable_hardware_detection: bool = Field(
        default=True, description="Enable automatic hardware detection for optimization"
    )

    # Override settings (None means use profile defaults)
    override_whisper_model: str | None = Field(
        default=None, description="Override whisper model regardless of profile"
    )

    override_device: str | None = Field(
        default=None, description="Override device selection regardless of profile"
    )

    override_batch_size: int | None = Field(
        default=None, description="Override batch size regardless of profile"
    )

    override_max_concurrent: int | None = Field(
        default=None, description="Override max concurrent files regardless of profile"
    )

    # Use case optimization
    optimize_for_use_case: str = Field(
        default="general",
        description="Use case for optimization: general, large_batch, mobile",
    )

    # Force specific hardware capabilities
    force_mps: bool = Field(
        default=False,
        description="Force MPS acceleration regardless of hardware detection",
    )

    force_coreml: bool = Field(
        default=False,
        description="Force CoreML acceleration regardless of hardware detection",
    )


class ThreadManagementConfig(BaseModel):
    """Thread management and resource allocation settings."""

    # OpenMP thread count - optimized for system
    omp_num_threads: int = Field(
        default_factory=lambda: max(1, min(8, os.cpu_count() or 4)),
        ge=1,
        le=32,
        description="Number of OpenMP threads for transcription processing",
    )

    # Maximum concurrent files to process simultaneously
    max_concurrent_files: int = Field(
        default_factory=lambda: max(1, min(4, (os.cpu_count() or 4) // 2)),
        ge=1,
        le=16,
        description="Maximum number of files to process simultaneously",
    )

    # Per-process thread limits
    per_process_thread_limit: int = Field(
        default_factory=lambda: max(1, min(4, (os.cpu_count() or 4) // 2)),
        ge=1,
        le=16,
        description="Thread limit per individual transcription process",
    )

    # Enable/disable parallel processing
    enable_parallel_processing: bool = Field(
        default=True, description="Enable parallel processing of multiple files"
    )

    # Process files sequentially instead of in parallel
    sequential_processing: bool = Field(
        default=False,
        description="Process files one at a time to avoid resource contention",
    )

    # Additional environment variables for performance tuning
    tokenizers_parallelism: bool = Field(
        default=False, description="Enable tokenizer parallelism (may cause warnings)"
    )

    pytorch_enable_mps_fallback: bool = Field(
        default=True, description="Enable MPS fallback for PyTorch on macOS"
    )


class TranscriptionConfig(BaseModel):
    """Transcription settings."""

    whisper_model: str = Field(
        default="base", pattern="^(tiny|base|small|medium|large|large-v2|large-v3)$"
    )
    use_gpu: bool = True
    diarization: bool = False
    min_words: int = Field(default=50, ge=1)
    use_whisper_cpp: bool = False


class LLMConfig(BaseModel):
    """LLM configuration."""

    provider: str = Field(default="openai", pattern="^(openai|claude|local)$")
    model: str = "gpt-4o-mini-2024-07-18"
    max_tokens: int = Field(default=10000, ge=1, le=32000)
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    local_model: str = Field(
        default="qwen2.5-coder:7b-instruct",
        description="Local model name for local provider",
    )


class LocalLLMConfig(BaseModel):
    """Local LLM configuration."""

    base_url: str = "http://localhost:11434"
    model: str = "qwen2.5-coder:7b-instruct"
    max_tokens: int = Field(default=10000, ge=1, le=32000)
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    timeout: int = Field(
        default=300, ge=30, le=3600, description="Request timeout in seconds"
    )
    backend: str = Field(
        default="ollama", description="Local LLM backend (ollama, lmstudio, etc.)"
    )


class APIKeysConfig(BaseModel):
    """API keys configuration."""

    # LLM Provider Keys
    openai_api_key: str | None = Field(default=None, alias="openai")
    anthropic_api_key: str | None = Field(default=None, alias="anthropic")

    # Webshare Proxy Keys (Required for YouTube)
    webshare_username: str | None = Field(default=None)
    webshare_password: str | None = Field(default=None)

    # HuggingFace for local models
    huggingface_token: str | None = Field(default=None, alias="hf_token")

    # Bright Data API Key (for YouTube processing)
    bright_data_api_key: str | None = Field(
        default=None,
        description="Bright Data API key for YouTube metadata, transcripts, and audio downloads",
    )

    # Bright Data Proxy Credentials (for residential proxy sessions)
    bright_data_customer_id: str | None = Field(
        default=None,
        description="Bright Data customer ID for proxy sessions (BD_CUST environment variable)",
    )
    bright_data_zone_id: str | None = Field(
        default=None,
        description="Bright Data zone ID for residential proxies (BD_ZONE environment variable)",
    )
    bright_data_password: str | None = Field(
        default=None,
        description="Bright Data zone password for proxy authentication (BD_PASS environment variable)",
    )

    @field_validator("bright_data_api_key")
    @classmethod
    def validate_bright_data_api_key(cls, v: str | None) -> str | None:
        """Validate Bright Data API key format."""
        if v is None or v == "":
            return v

        # Basic format validation - Bright Data API keys typically start with specific prefixes
        if not v.startswith(
            ("bd_", "brd_", "2")
        ):  # Common Bright Data API key prefixes
            raise ValueError(
                "Bright Data API key should start with 'bd_', 'brd_', or be numeric"
            )

        # Minimum length check
        if len(v) < 10:
            raise ValueError("Bright Data API key is too short")

        return v

    class Config:
        """Pydantic model configuration."""

        extra = "allow"  # Allow extra fields for backward compatibility

    # Backward compatibility properties
    @property
    def openai(self) -> str | None:
        """Backward compatibility property for openai_api_key."""
        return self.openai_api_key

    @property
    def anthropic(self) -> str | None:
        """Backward compatibility property for anthropic_api_key."""
        return self.anthropic_api_key


class ProcessingConfig(BaseModel):
    """Processing settings."""

    batch_size: int = Field(default=10, ge=1, le=100)
    concurrent_jobs: int = Field(default=2, ge=1, le=10)
    retry_attempts: int = Field(default=3, ge=1, le=10)
    timeout_seconds: int = Field(default=300, ge=30, le=3600)


class YouTubeProcessingConfig(BaseModel):
    """YouTube processing configuration."""

    # Delay settings for rate limiting
    disable_delays_with_proxy: bool = Field(
        default=False,
        description="Automatically disable delays when rotating proxies are configured",
    )

    use_proxy_delays: bool = Field(
        default=True,
        description="Use delays when proxies are configured (overridden by disable_delays_with_proxy)",
    )

    # Delay ranges (in seconds)
    metadata_delay_min: float = Field(default=0.5, ge=0.0, le=10.0)
    metadata_delay_max: float = Field(default=2.0, ge=0.0, le=10.0)
    transcript_delay_min: float = Field(default=1.0, ge=0.0, le=10.0)
    transcript_delay_max: float = Field(default=3.0, ge=0.0, le=10.0)
    api_batch_delay_min: float = Field(default=1.0, ge=0.0, le=10.0)
    api_batch_delay_max: float = Field(default=3.0, ge=0.0, le=10.0)


class MOCConfig(BaseModel):
    """MOC (Maps of Content) configuration."""

    # MOC generation settings
    default_theme: str = Field(
        default="topical", pattern="^(topical|chronological|hierarchical)$"
    )
    default_depth: int = Field(default=2, ge=1, le=5)

    # Content extraction settings
    extract_people: bool = True
    extract_tags: bool = True
    extract_mental_models: bool = True
    extract_jargon: bool = True
    extract_beliefs: bool = True

    # Minimum thresholds
    min_people_mentions: int = Field(default=2, ge=1, le=10)
    min_tag_occurrences: int = Field(default=3, ge=1, le=10)
    min_belief_confidence: float = Field(default=0.7, ge=0.0, le=1.0)


class HCEConfig(BaseModel):
    """HCE (Hybrid Claim Extractor) configuration."""

    # Pipeline model configuration
    miner_model: str = Field(
        default="gpt-4o-mini-2024-07-18", description="Model for claim mining stage"
    )
    judge_model: str = Field(
        default="gpt-4o-mini-2024-07-18", description="Model for claim judging stage"
    )
    embedder_model: str = Field(
        default="all-MiniLM-L6-v2", description="Model for embedding generation"
    )
    reranker_model: str = Field(
        default="ms-marco-MiniLM-L-6-v2", description="Model for reranking claims"
    )

    # Claim extraction settings
    default_min_claim_tier: str = Field(
        default="all",
        pattern="^(A|B|C|all)$",
        description="Minimum claim tier to include",
    )
    max_claims_per_document: int | None = Field(
        default=None,
        ge=1,
        le=1000,
        description="Maximum claims to extract per document",
    )

    # Analysis settings
    include_contradictions: bool = Field(
        default=True, description="Include contradiction analysis"
    )
    include_relations: bool = Field(
        default=True, description="Include relationship mapping"
    )

    # Tier thresholds (confidence scores)
    tier_a_threshold: float = Field(
        default=0.85, ge=0.0, le=1.0, description="Minimum confidence for Tier A claims"
    )
    tier_b_threshold: float = Field(
        default=0.65, ge=0.0, le=1.0, description="Minimum confidence for Tier B claims"
    )

    # Performance settings
    enable_embedding_cache: bool = Field(
        default=True, description="Use embedding cache for performance"
    )
    max_concurrent_stages: int = Field(
        default=1, ge=1, le=4, description="Maximum concurrent HCE pipeline stages"
    )


class MonitoringConfig(BaseModel):
    """Monitoring and logging configuration."""

    # Logging settings
    log_level: str = Field(
        default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$"
    )
    log_file_max_size: int = Field(default=10, ge=1, le=100)  # MB
    log_file_backup_count: int = Field(default=5, ge=1, le=20)

    # Performance monitoring
    enable_performance_tracking: bool = True
    track_processing_times: bool = True
    track_resource_usage: bool = True


class GUIFeaturesConfig(BaseModel):
    """GUI feature toggles configuration."""

    # Tab visibility settings
    show_process_management_tab: bool = Field(
        default=False, description="Show the Process Management tab in the GUI"
    )
    show_file_watcher_tab: bool = Field(
        default=True, description="Show the File Watcher tab in the GUI"
    )

    # Other GUI feature toggles can be added here in the future
    enable_advanced_features: bool = Field(
        default=False, description="Enable advanced/experimental GUI features"
    )


class Settings(BaseSettings):
    """Main settings class with YAML support and validation."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="forbid"
    )

    # Configuration sections
    app: AppConfig = Field(default_factory=AppConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    thread_management: ThreadManagementConfig = Field(
        default_factory=ThreadManagementConfig
    )
    transcription: TranscriptionConfig = Field(default_factory=TranscriptionConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    local_config: LocalLLMConfig = Field(default_factory=LocalLLMConfig)
    api_keys: APIKeysConfig = Field(default_factory=APIKeysConfig)
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    youtube_processing: YouTubeProcessingConfig = Field(
        default_factory=YouTubeProcessingConfig
    )
    moc: MOCConfig = Field(default_factory=MOCConfig)
    hce: HCEConfig = Field(default_factory=HCEConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    gui_features: GUIFeaturesConfig = Field(default_factory=GUIFeaturesConfig)

    def __init__(self, config_path: str | Path | None = None, **kwargs) -> None:
        """Initialize settings from YAML file and environment variables."""

        # Static YAML loading function for use before super().__init__()
        def load_yaml_static(path: str | Path) -> dict[str, Any]:
            """Load YAML configuration file (static version for init)."""
            path = Path(path)
            try:
                with open(path, encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                print(f"Failed to load config from {path}: {e}")
                return {}

        # Load from YAML file if provided
        if config_path:
            config_data = load_yaml_static(config_path)
            kwargs.update(config_data)
        else:
            # Try to load from default locations
            default_paths = [
                Path("config/settings.yaml"),
                Path("../config/settings.yaml"),  # Handle running from src/ directory
                Path("settings.yaml"),
                Path.home() / ".knowledge-system" / "settings.yaml",
            ]

            for path in default_paths:
                if path.exists():
                    config_data = load_yaml_static(path)
                    kwargs.update(config_data)
                    break

        # CREDENTIALS: Also load from dedicated credentials file
        credentials_paths = [
            Path("config/credentials.yaml"),
            Path("../config/credentials.yaml"),  # Handle running from src/ directory
            Path("credentials.yaml"),
            Path.home() / ".knowledge-system" / "credentials.yaml",
        ]

        for cred_path in credentials_paths:
            if cred_path.exists():
                try:
                    cred_data = load_yaml_static(cred_path)
                    # Merge credentials into kwargs, properly handling api_keys section
                    if cred_data:
                        if "api_keys" in cred_data:
                            # Ensure api_keys section exists in kwargs
                            if "api_keys" not in kwargs:
                                kwargs["api_keys"] = {}
                            # Merge api_keys data, giving priority to credentials file
                            kwargs["api_keys"].update(cred_data["api_keys"])

                        # Merge other sections if they exist
                        for key, value in cred_data.items():
                            if key != "api_keys":  # api_keys already handled above
                                kwargs[key] = value
                        break
                except Exception:
                    pass  # Silently continue if credentials file can't be loaded

        # Load API keys from environment if not provided
        if "api_keys" not in kwargs:
            kwargs["api_keys"] = {}

        api_keys = kwargs["api_keys"]

        # Only load from environment if not already set in credentials file
        if not api_keys.get("openai_api_key") and not api_keys.get("openai"):
            env_openai = os.getenv("OPENAI_API_KEY")
            if env_openai:
                api_keys["openai"] = env_openai

        if not api_keys.get("anthropic_api_key") and not api_keys.get("anthropic"):
            env_anthropic = os.getenv("ANTHROPIC_API_KEY")
            if env_anthropic:
                api_keys["anthropic"] = env_anthropic

        if not api_keys.get("webshare_username"):
            api_keys["webshare_username"] = os.getenv("WEBSHARE_USERNAME")
        if not api_keys.get("webshare_password"):
            api_keys["webshare_password"] = os.getenv("WEBSHARE_PASSWORD")

        super().__init__(**kwargs)

    def _load_yaml(self, path: str | Path) -> dict[str, Any]:
        """Load YAML configuration file."""
        path = Path(path)
        try:
            with open(path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            raise ValueError(f"Failed to load config from {path}: {e}")

    def to_yaml(self, path: str | Path) -> None:
        """Save settings to YAML file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict and remove None values
        data = self.model_dump(exclude_none=True)

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, indent=2)

    @classmethod
    def from_file(cls, path: str | Path) -> "Settings":
        """Load settings from file."""
        return cls(config_path=path)

    def get_effective_config(self) -> dict[str, Any]:
        """Get effective configuration with performance profile applied."""
        from .utils.hardware_detection import PerformanceProfile, get_hardware_detector

        # Get hardware detector
        detector = get_hardware_detector()

        # Determine performance profile
        if self.performance.profile == "auto":
            # Auto-select based on hardware and use case
            profile = detector.recommend_profile(self.performance.optimize_for_use_case)
        else:
            # Use specified profile
            try:
                profile = PerformanceProfile(self.performance.profile)
            except ValueError:
                # Fallback to balanced if invalid profile
                profile = PerformanceProfile.BALANCED

        # Get profile configuration
        profile_config = detector.get_performance_profile(profile)

        # Apply overrides
        if self.performance.override_whisper_model:
            profile_config["whisper_model"] = self.performance.override_whisper_model
        if self.performance.override_device:
            profile_config["device"] = self.performance.override_device
        if self.performance.override_batch_size:
            profile_config["batch_size"] = self.performance.override_batch_size
        if self.performance.override_max_concurrent:
            profile_config[
                "max_concurrent_files"
            ] = self.performance.override_max_concurrent

        # Apply force settings
        if self.performance.force_mps:
            profile_config["device"] = "mps"
            profile_config["use_coreml"] = False
        if self.performance.force_coreml:
            profile_config["use_coreml"] = True

        # Update thread management config
        effective_config = self.model_dump()
        effective_config["thread_management"].update(profile_config)
        effective_config["transcription"]["whisper_model"] = profile_config[
            "whisper_model"
        ]

        # Add hardware info
        effective_config["hardware"] = detector.get_hardware_report()
        effective_config["performance_profile"] = profile.value

        return effective_config


# Global settings instance
_settings: Settings | None = None


def get_settings(
    config_path: str | Path | None = None, reload: bool = False
) -> Settings:
    """Get or create the global settings instance."""
    global _settings

    if _settings is None or reload:
        _settings = Settings(config_path=config_path)

    return _settings


def apply_performance_profile(settings: Settings) -> dict[str, Any]:
    """Apply performance profile to settings and return effective configuration."""
    return settings.get_effective_config()


def get_hardware_optimized_settings() -> dict[str, Any]:
    """Get hardware-optimized settings for the current system."""
    from .utils.hardware_detection import get_hardware_detector

    detector = get_hardware_detector()

    # Get recommended profile
    profile = detector.recommend_profile("general")
    config = detector.get_performance_profile(profile)

    return {
        "hardware_specs": detector.get_hardware_report(),
        "recommended_profile": profile.value,
        "optimized_config": config,
    }
