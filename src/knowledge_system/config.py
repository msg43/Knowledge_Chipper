"""
Configuration management for Knowledge System

Configuration management for Knowledge System.
Supports YAML files, environment variables, and settings persistence.
"""

import os
from pathlib import Path
from typing import Any

import yaml  # type: ignore
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_valid_whisper_models() -> list[str]:
    """Get simplified, user-friendly Whisper model names."""
    # Simplified model list - removed confusing version suffixes
    # medium maps to medium.en (English-only, faster)
    # large maps to large-v3 (latest and best general purpose)
    return ["tiny", "base", "small", "medium", "large"]


class AppConfig(BaseModel):
    """Application-level configuration."""

    name: str = "Skip the Podcast Desktop"
    version: str = "0.0.0"  # runtime will prefer package __version__
    debug: bool = False

    # Update Settings
    auto_check_updates: bool = Field(
        default=True,
        description="Automatically check for updates when the app launches",
    )
    update_channel: str = Field(
        default="stable", description="Update channel: stable, beta, or dev"
    )


class PathsConfig(BaseModel):
    """Configuration for file paths using macOS standard locations."""

    # Base data directory - defaults to proper macOS Application Support
    data_dir: str = Field(
        default="",
        description="Base data directory (auto-configured to macOS standard location)",
    )
    # Output directory - defaults to proper user Documents
    output_dir: str = Field(
        default="",
        description="Output directory (auto-configured to user Documents)",
    )
    # Cache directory - defaults to proper macOS Cache
    cache_dir: str = Field(
        default="",
        description="Cache directory (auto-configured to macOS standard location)",
    )

    # Input/output paths - auto-configured to standard locations
    input_dir: str = Field(
        default="",
        description="Input directory (auto-configured to user Documents)",
    )
    output: str = Field(
        default="",
        description="Output path (auto-configured to user Documents)",
    )
    transcripts: str = Field(
        default="",
        description="Transcripts directory (auto-configured)",
    )
    summaries: str = Field(
        default="",
        description="Summaries directory (auto-configured)",
    )
    mocs: str = Field(
        default="",
        description="Maps of Content directory (auto-configured)",
    )
    cache: str = Field(
        default="",
        description="Cache directory (auto-configured)",
    )
    logs_dir: str = Field(
        default="", description="Logs directory (auto-configured to macOS standard)"
    )

    # Additional paths for backward compatibility
    input: str = Field(
        default="",
        description="Input directory (auto-configured)",
    )
    logs: str = Field(
        default="", description="Logs directory (alias for logs_dir, auto-configured)"
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
        default="medium", pattern="^(tiny|base|small|medium|large)$"
    )
    device: str = Field(
        default="auto",
        pattern="^(auto|cpu|cuda|mps)$",
        description="Processing device: auto (detect best), cpu, cuda (NVIDIA), mps (Apple Silicon)",
    )
    diarization: bool = True
    min_words: int = Field(default=50, ge=1)
    use_whisper_cpp: bool = False


class TranscriptProcessingConfig(BaseModel):
    """Transcript processing and selection configuration."""

    # Priority order for transcript selection (highest to lowest)
    transcript_priority: list[str] = Field(
        default=["pdf_provided", "youtube_api", "whisper", "diarized"],
        description="Priority order for selecting which transcript to use for processing"
    )
    
    # Quality thresholds
    min_quality_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum quality score for transcript acceptance"
    )
    
    # Auto-matching settings for PDF transcripts
    youtube_matching_enabled: bool = Field(
        default=True,
        description="Enable automatic YouTube video matching for PDF transcripts"
    )
    youtube_matching_confidence_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Minimum confidence for auto-match acceptance"
    )
    youtube_matching_require_manual_review: bool = Field(
        default=True,
        description="Flag low-confidence matches for manual review"
    )
    
    # Search strategies (tried in order)
    youtube_matching_strategies: list[str] = Field(
        default=["database_fuzzy_match", "title_search", "metadata_search", "llm_query_generation"],
        description="YouTube matching strategies in priority order"
    )


class LLMConfig(BaseModel):
    """LLM configuration."""

    provider: str = Field(default="local", pattern="^(openai|claude|anthropic|google|local)$")
    model: str = Field(
        default="gpt-4o-mini-2024-07-18",
        description="Cloud model name for openai/anthropic/google providers"
    )
    max_tokens: int = Field(default=10000, ge=1, le=32000)
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    local_model: str = Field(
        default="qwen2.5:7b-instruct",
        description="Local model name for local provider (Ollama)",
    )
    # Summarization prompt controls
    summarization_prompt_max_chars: int = Field(
        default=8000,
        ge=1000,
        le=120000,
        description="Max characters of source text inserted into summarization prompts",
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
    # Generation caps for local providers
    num_predict: int = Field(
        default=600,
        ge=64,
        le=8192,
        description="Maximum tokens to generate in local model responses",
    )
    num_ctx: int = Field(
        default=4096,
        ge=1024,
        le=131072,
        description="Context window to request for local models (if applicable)",
    )
    use_stream: bool = Field(
        default=True,
        description="Use streaming responses for local providers when available",
    )


class APIKeysConfig(BaseModel):
    """API keys configuration."""

    # LLM Provider Keys
    openai_api_key: str | None = Field(default=None, alias="openai")
    anthropic_api_key: str | None = Field(default=None, alias="anthropic")
    google_api_key: str | None = Field(
        default=None,
        alias="google",
        description="Google AI API key for Gemini models. Get from: https://aistudio.google.com/apikey",
    )

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

    # PacketStream Proxy Credentials (alternative to Bright Data for residential proxies)
    packetstream_username: str | None = Field(
        default=None,
        description="PacketStream username for residential proxy access",
    )
    packetstream_auth_key: str | None = Field(
        default=None,
        description="PacketStream authentication key for proxy authentication",
    )

    # AnyIP.io Proxy Credentials
    anyip_api_key: str | None = Field(
        default=None,
        description="AnyIP.io API key (optional - only if using anyip provider)",
    )
    anyip_username: str | None = Field(
        default=None,
        description="AnyIP.io username (optional - only if using anyip provider)",
    )
    anyip_password: str | None = Field(
        default=None,
        description="AnyIP.io password (optional - only if using anyip provider)",
    )

    # Oxylabs.io Proxy Credentials
    oxylabs_username: str | None = Field(
        default=None,
        description="Oxylabs.io username (optional - only if using oxylabs provider)",
    )
    oxylabs_password: str | None = Field(
        default=None,
        description="Oxylabs.io password (optional - only if using oxylabs provider)",
    )

    # GonzoProxy.com Proxy Credentials
    gonzoproxy_api_key: str | None = Field(
        default=None,
        description="GonzoProxy.com API key (optional - only if using gonzoproxy provider)",
    )
    gonzoproxy_username: str | None = Field(
        default=None,
        description="GonzoProxy.com username (optional - only if using gonzoproxy provider)",
    )

    @field_validator("bright_data_api_key")
    @classmethod
    def validate_bright_data_api_key(cls, v: str | None) -> str | None:
        """Validate Bright Data API key format."""
        if v is None or v == "":
            return v

        # Accept common formats, including UUID-style keys from Bright Data
        # Only enforce a reasonable minimum length to avoid obvious mistakes
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

    @property
    def google(self) -> str | None:
        """Backward compatibility property for google_api_key."""
        return self.google_api_key


class ProcessingConfig(BaseModel):
    """Processing settings."""

    batch_size: int = Field(default=10, ge=1, le=100)
    concurrent_jobs: int = Field(default=2, ge=1, le=10)
    retry_attempts: int = Field(default=3, ge=1, le=10)
    timeout_seconds: int = Field(default=300, ge=30, le=3600)

    # Process Tab Defaults
    default_transcribe: bool = Field(
        default=True, description="Enable transcription by default"
    )
    default_summarize: bool = Field(
        default=True, description="Enable summarization by default"
    )


class FileWatcherConfig(BaseModel):
    """File watcher / monitor tab configuration."""

    default_file_patterns: str = Field(
        default="*.mp4,*.mp3,*.wav,*.m4a,*.pdf,*.txt,*.md",
        description="Default file patterns to watch",
    )
    default_debounce_delay: int = Field(
        default=5, ge=1, le=300, description="Default debounce delay in seconds"
    )
    default_recursive: bool = Field(
        default=True, description="Watch subdirectories by default"
    )
    default_auto_process: bool = Field(
        default=True, description="Auto-process new files by default"
    )
    default_system2_pipeline: bool = Field(
        default=False, description="Use System 2 pipeline by default"
    )


class YouTubeAPIConfig(BaseModel):
    """YouTube Data API v3 configuration."""
    
    enabled: bool = Field(
        default=False,
        description="Use YouTube Data API for metadata (recommended for reliability)"
    )
    api_key: str = Field(
        default="",
        description="YouTube Data API v3 key from Google Cloud Console"
    )
    quota_limit: int = Field(
        default=10000,
        ge=1,
        description="Daily quota limit (free tier: 10,000 units/day)"
    )
    fallback_to_ytdlp: bool = Field(
        default=True,
        description="Fall back to yt-dlp if API fails or quota exceeded"
    )
    batch_size: int = Field(
        default=50,
        ge=1,
        le=50,
        description="Videos per batch request (API max: 50)"
    )
    use_for_pdf_matching: bool = Field(
        default=True,
        description="Use API for PDF transcript matching (faster, more reliable)"
    )


class YouTubeProcessingConfig(BaseModel):
    """YouTube processing configuration."""

    # Proxy strict mode - prevents direct connections when proxy fails
    proxy_strict_mode: bool = Field(
        default=True,
        description="Block YouTube operations when proxy fails (prevents IP exposure). Set to False to allow direct fallback.",
    )

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

    # Intelligent pacing settings
    enable_intelligent_pacing: bool = Field(
        default=True,
        description="Enable intelligent pacing to optimize download timing based on processing pipeline",
    )

    pacing_base_delay: float = Field(
        default=5.0,
        ge=1.0,
        le=30.0,
        description="Base delay in seconds between downloads for intelligent pacing",
    )

    pacing_min_delay: float = Field(
        default=2.0,
        ge=1.0,
        le=15.0,
        description="Minimum delay in seconds between downloads",
    )

    pacing_max_delay: float = Field(
        default=15.0,
        ge=5.0,
        le=60.0,
        description="Maximum delay in seconds between downloads",
    )

    pacing_buffer_multiplier: float = Field(
        default=1.5,
        ge=1.0,
        le=3.0,
        description="Multiplier for download speed to stay ahead of processing pipeline",
    )

    pacing_rate_limit_multiplier: float = Field(
        default=2.0,
        ge=1.0,
        le=5.0,
        description="Multiplier for delays when rate limiting is detected",
    )

    # Cookie authentication settings (file upload only - browser extraction disabled for security)
    enable_cookies: bool = Field(
        default=True,
        description="Enable cookie-based authentication for YouTube downloads",
    )

    cookie_file_path: str | None = Field(
        default=None,
        description="Path to cookies.txt file (Netscape format). Browser extraction disabled to prevent accidentally using main account instead of throwaway.",
    )

    # Rate limiting for sequential downloads
    sequential_download_delay_min: float = Field(
        default=180.0,
        ge=0.0,
        le=600.0,
        description="Minimum delay in seconds between sequential YouTube downloads (default 3 minutes)",
    )

    sequential_download_delay_max: float = Field(
        default=300.0,
        ge=0.0,
        le=600.0,
        description="Maximum delay in seconds between sequential YouTube downloads (default 5 minutes)",
    )

    delay_randomization_percent: float = Field(
        default=25.0,
        ge=0.0,
        le=100.0,
        description="Percentage of randomization for sleep times (e.g., 25 = ±25%)",
    )

    disable_proxies_with_cookies: bool = Field(
        default=True,
        description="Automatically disable proxies when cookies are enabled (recommended for home IP usage)",
    )

    # Sleep period settings (Option B: Light sleep for human-like behavior)
    enable_sleep_period: bool = Field(
        default=True,
        description="Enable daily sleep period to mimic human behavior (recommended for large batches)",
    )

    sleep_start_hour: int = Field(
        default=0,
        ge=0,
        le=23,
        description="Hour to start sleep period (0-23, local time). Default 0 = midnight",
    )

    sleep_end_hour: int = Field(
        default=6,
        ge=0,
        le=23,
        description="Hour to end sleep period (0-23, local time). Default 6 = 6am",
    )

    sleep_timezone: str = Field(
        default="America/Los_Angeles",
        description="Timezone for sleep period (e.g., 'America/New_York', 'Europe/London')",
    )

    # Session-based download strategy (advanced anti-bot detection)
    enable_session_based_downloads: bool = Field(
        default=True,
        description="Enable session-based download strategy with duty cycles (recommended for large batches)",
    )

    sessions_per_day_min: int = Field(
        default=2,
        ge=1,
        le=10,
        description="Minimum number of download sessions per day",
    )

    sessions_per_day_max: int = Field(
        default=4,
        ge=1,
        le=10,
        description="Maximum number of download sessions per day",
    )

    session_duration_min: int = Field(
        default=60,
        ge=10,
        le=300,
        description="Minimum session duration in minutes",
    )

    session_duration_max: int = Field(
        default=180,
        ge=10,
        le=300,
        description="Maximum session duration in minutes",
    )

    max_downloads_per_session_min: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Minimum downloads per session cap",
    )

    max_downloads_per_session_max: int = Field(
        default=250,
        ge=10,
        le=1000,
        description="Maximum downloads per session cap",
    )

    # yt-dlp rate limiting and jitter
    rate_limit_min_mbps: float = Field(
        default=0.8,
        ge=0.1,
        le=10.0,
        description="Minimum download rate limit in MB/s (prevents looking like a bot)",
    )

    rate_limit_max_mbps: float = Field(
        default=1.5,
        ge=0.1,
        le=10.0,
        description="Maximum download rate limit in MB/s",
    )

    concurrent_downloads_min: int = Field(
        default=1,
        ge=1,
        le=5,
        description="Minimum concurrent downloads (1-2 recommended)",
    )

    concurrent_downloads_max: int = Field(
        default=2,
        ge=1,
        le=5,
        description="Maximum concurrent downloads",
    )

    # Jitter between files and requests
    sleep_interval_min: int = Field(
        default=8,
        ge=1,
        le=60,
        description="Minimum sleep interval between files in seconds",
    )

    sleep_interval_max: int = Field(
        default=25,
        ge=1,
        le=120,
        description="Maximum sleep interval between files in seconds",
    )

    sleep_requests: float = Field(
        default=0.8,
        ge=0.0,
        le=5.0,
        description="Sleep between HTTP requests in seconds (adds jitter)",
    )

    # Backoff on 429/403
    enable_auto_cooldown: bool = Field(
        default=True,
        description="Automatically detect rate limiting (429/403) and trigger cooldown",
    )

    cooldown_min_minutes: int = Field(
        default=45,
        ge=5,
        le=300,
        description="Minimum cooldown period in minutes when rate limited",
    )

    cooldown_max_minutes: int = Field(
        default=180,
        ge=5,
        le=300,
        description="Maximum cooldown period in minutes when rate limited",
    )

    # URL shuffling
    shuffle_urls: bool = Field(
        default=True,
        description="Shuffle URLs before download to avoid sequential hammering of single channel/playlist",
    )

    # Archive file for resume capability
    use_download_archive: bool = Field(
        default=True,
        description="Use download archive to prevent re-downloading already processed videos",
    )

    download_archive_path: str = Field(
        default="~/.knowledge_system/youtube_downloads.txt",
        description="Path to download archive file (tracks successfully downloaded videos)",
    )


class PodcastDiscoveryConfig(BaseModel):
    """Podcast discovery and YouTube-to-RSS mapping configuration."""

    enable_youtube_to_rss_mapping: bool = Field(
        default=True,
        description="Enable automatic mapping of YouTube URLs to native podcast RSS feeds",
    )

    podcast_index_api_key: str | None = Field(
        default=None,
        description="PodcastIndex.org API key (optional, has free tier). Get from: https://api.podcastindex.org/",
    )

    listen_notes_api_key: str | None = Field(
        default=None,
        description="ListenNotes.com API key (optional). Get from: https://www.listennotes.com/api/",
    )

    cache_mappings: bool = Field(
        default=True,
        description="Cache YouTube-to-RSS mappings to avoid repeated API calls",
    )

    mapping_cache_path: str = Field(
        default="~/.knowledge_system/podcast_mappings.json",
        description="Path to mapping cache file",
    )


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
    extract_claims: bool = True

    # Minimum thresholds
    min_people_mentions: int = Field(default=2, ge=1, le=10)
    min_tag_occurrences: int = Field(default=3, ge=1, le=10)
    min_claim_confidence: float = Field(default=0.7, ge=0.0, le=1.0)


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
        default=0,
        ge=0,
        le=1000,
        description="Maximum claims to extract per document (0 = unlimited)",
    )

    # Analysis settings
    include_contradictions: bool = Field(
        default=True, description="Include contradiction analysis"
    )
    include_relations: bool = Field(
        default=True, description="Include relationship mapping"
    )

    # NOTE: Tier thresholds removed - tiers are assigned by LLM in flagship evaluator,
    # not by numeric thresholds. See schemas/flagship_output.v1.json

    # Performance settings
    enable_embedding_cache: bool = Field(
        default=True, description="Use embedding cache for performance"
    )
    max_concurrent_stages: int = Field(
        default=1, ge=1, le=4, description="Maximum concurrent HCE pipeline stages"
    )


class ClaimsFirstConfig(BaseModel):
    """Claims-First Pipeline Configuration.
    
    The claims-first pipeline extracts claims before speaker attribution,
    inverting the traditional speaker-first approach. This reduces processing
    time and only attributes speakers to high-value claims.
    """
    
    # Master enable flag
    enabled: bool = Field(
        default=False,
        description="Enable claims-first pipeline (vs speaker-first)",
    )
    
    # Transcript source settings
    transcript_source: str = Field(
        default="auto",
        pattern="^(auto|youtube|whisper)$",
        description="Transcript source: auto (try YouTube first), youtube, or whisper",
    )
    youtube_quality_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum quality score for YouTube transcripts (0.0-1.0)",
    )
    
    # Evaluator model settings
    evaluator_model: str = Field(
        default="configurable",
        pattern="^(gemini|claude|configurable)$",
        description="Model for claim evaluation: gemini, claude, or configurable",
    )
    
    # Lazy speaker attribution settings
    lazy_attribution_min_importance: int = Field(
        default=7,
        ge=0,
        le=10,
        description="Minimum importance score for speaker attribution (0-10)",
    )
    context_window_seconds: int = Field(
        default=60,
        ge=10,
        le=300,
        description="Context window for speaker attribution (seconds)",
    )
    
    # Advanced settings
    store_candidates: bool = Field(
        default=True,
        description="Store candidate claims in database for re-evaluation",
    )
    fuzzy_match_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Threshold for fuzzy quote-to-timestamp matching",
    )
    
    # Model-specific settings
    miner_model: str = Field(
        default="gemini-2.0-flash",
        description="Model for claim mining stage",
    )
    evaluator_model_gemini: str = Field(
        default="gemini-2.0-flash",
        description="Gemini model for evaluation",
    )
    evaluator_model_claude: str = Field(
        default="claude-3-5-sonnet-20241022",
        description="Claude model for evaluation",
    )
    attribution_model: str = Field(
        default="gemini-2.0-flash",
        description="Model for speaker attribution",
    )


class ProcessingMode(str):
    """Processing mode for claim extraction."""
    REALTIME = "realtime"
    BATCH = "batch"
    AUTO = "auto"


class BatchProcessingConfig(BaseModel):
    """Configuration for batch and real-time processing."""

    # Mode selection
    mode: str = Field(
        default="realtime",
        pattern="^(realtime|batch|auto)$",
        description="Processing mode: realtime, batch, or auto",
    )
    auto_batch_threshold: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Segment count threshold for auto mode to switch to batch",
    )

    # Batch API settings
    batch_provider: str = Field(
        default="openai",
        pattern="^(openai|anthropic)$",
        description="Provider for batch processing",
    )
    batch_mining_model: str = Field(
        default="gpt-5-mini",
        description="Model for batch mining stage",
    )
    batch_flagship_model: str = Field(
        default="gpt-5-mini",
        description="Model for batch flagship evaluation",
    )
    batch_remine_model: str = Field(
        default="claude-3.7-sonnet",
        description="Model for re-mining flagged segments",
    )
    batch_remine_provider: str = Field(
        default="anthropic",
        pattern="^(openai|anthropic)$",
        description="Provider for re-mining (may differ from main batch provider)",
    )

    # Real-time settings (existing models)
    realtime_mining_model: str = Field(
        default="ollama://qwen2.5:72b-instruct",
        description="Model for real-time mining",
    )
    realtime_flagship_model: str = Field(
        default="ollama://qwen2.5:72b-instruct",
        description="Model for real-time flagship evaluation",
    )

    # Re-mining thresholds
    remine_enabled: bool = Field(
        default=True,
        description="Enable re-mining of low-confidence segments",
    )
    remine_confidence_threshold: float = Field(
        default=4.0,
        ge=0,
        le=10,
        description="Re-mine segments where avg confidence is below this threshold",
    )
    remine_empty_segments: bool = Field(
        default=True,
        description="Re-mine segments that produced 0 claims",
    )
    remine_max_percent: float = Field(
        default=15.0,
        ge=0,
        le=100,
        description="Maximum percentage of segments to re-mine",
    )

    # Prompt caching optimization (OpenAI)
    enable_cache_optimization: bool = Field(
        default=True,
        description="Order batches to maximize prompt cache hits",
    )
    sequential_batch_submission: bool = Field(
        default=True,
        description="Submit batches sequentially to warm cache",
    )
    batch_delay_seconds: int = Field(
        default=30,
        ge=0,
        le=300,
        description="Delay between batch submissions for cache warmup",
    )

    # Polling settings
    poll_interval_seconds: int = Field(
        default=60,
        ge=10,
        le=600,
        description="How often to poll for batch completion",
    )
    max_requests_per_batch: int = Field(
        default=10000,
        ge=100,
        le=50000,
        description="Maximum requests per batch submission",
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


class SpeakerIdentificationConfig(BaseModel):
    """Speaker identification and diarization configuration."""

    # Core speaker identification settings
    enable_speaker_assignment: bool = Field(
        default=True, description="Enable interactive speaker assignment dialog"
    )
    auto_show_assignment_dialog: bool = Field(
        default=True,
        description="Automatically show speaker assignment dialog after diarization",
    )
    enable_voice_learning: bool = Field(
        default=True,
        description="Learn voice patterns for future automatic suggestions",
    )
    confidence_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold for speaker suggestions",
    )
    max_speaker_suggestions: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Maximum number of speaker name suggestions to show",
    )

    # Color-coded transcript settings
    enable_color_coded_transcripts: bool = Field(
        default=False,  # Default to False to reduce processing overhead
        description="Generate color-coded HTML and enhanced markdown transcripts",
    )
    color_coded_by_default: bool = Field(
        default=False,  # Default to False to reduce processing overhead
        description="Enable color coding by default in transcription settings",
    )

    # Batch processing settings
    batch_processing_enabled: bool = Field(
        default=True,
        description="Enable batch speaker assignment for multiple recordings",
    )
    maintain_speaker_consistency: bool = Field(
        default=True,
        description="Try to maintain consistent speaker names across recordings in the same folder",
    )

    # Integration settings
    integrate_with_people_moc: bool = Field(
        default=True,
        description="Automatically add identified speakers to People MOC files",
    )
    update_people_yaml: bool = Field(
        default=True, description="Update People.yaml files with speaker information"
    )

    # Advanced diarization settings
    diarization_sensitivity: str = Field(
        default="dialogue",  # Changed from "conservative" for better quick-exchange capture
        pattern="^(dialogue|aggressive|balanced|conservative)$",
        description="Speaker detection sensitivity: dialogue (best for interviews with quick exchanges), aggressive (more speakers), balanced (default), conservative (fewer speakers)",
    )
    min_speaker_duration: float = Field(
        default=1.0,
        ge=0.1,
        le=10.0,
        description="Minimum duration in seconds for a speaker segment to be considered valid",
    )
    speaker_separation_threshold: float = Field(
        default=0.8,
        ge=0.1,
        le=1.0,
        description="Threshold for considering voices as different speakers (higher = fewer speakers)",
    )

    # Advanced settings
    enable_audio_playback: bool = Field(
        default=False,
        description="Enable audio playback in speaker assignment dialog (future feature)",
    )
    voice_fingerprinting_enabled: bool = Field(
        default=True,  # Now enabled by default for 97% accuracy
        description="Enable advanced voice fingerprinting for 97% accurate speaker recognition",
    )

    # Word-level speaker verification settings
    # When enabled, uses word timestamps from whisper.cpp for fine-grained attribution
    enable_word_level_verification: bool = Field(
        default=True,
        description="Enable word-level speaker verification for 4-7% DER (vs 10-15% segment-level)",
    )
    word_verification_confidence_gap: float = Field(
        default=0.15,
        ge=0.05,
        le=0.5,
        description="Similarity difference required to reassign word to different speaker",
    )
    word_verification_window_seconds: float = Field(
        default=0.5,
        ge=0.2,
        le=2.0,
        description="Minimum time window for voice extraction during word verification",
    )

    # Persistent speaker profiles
    # Stores voice fingerprints for recurring hosts across episodes
    enable_persistent_profiles: bool = Field(
        default=True,
        description="Store voice fingerprints for recurring speakers across episodes",
    )
    profile_accumulation_weight: float = Field(
        default=0.3,
        ge=0.1,
        le=1.0,
        description="Weight for new samples when updating speaker profile (0.1-1.0)",
    )
    min_profile_confidence: float = Field(
        default=0.7,
        ge=0.3,
        le=1.0,
        description="Minimum confidence required to use stored speaker profile",
    )

    # Performance tuning for word-level verification
    max_words_to_verify: int = Field(
        default=500,
        ge=50,
        le=5000,
        description="Maximum words to verify for performance (focus on transitions/short utterances)",
    )
    skip_verification_for_long_segments: bool = Field(
        default=True,
        description="Skip verification for segments > 3s where pyannote is already reliable",
    )

    # Learning and suggestion settings
    learn_from_corrections: bool = Field(
        default=True,
        description="Learn from user corrections to improve future suggestions",
    )
    suggestion_learning_weight: float = Field(
        default=1.0,
        ge=0.1,
        le=2.0,
        description="Weight for learning from user corrections",
    )
    cleanup_old_patterns_days: int = Field(
        default=90,
        ge=7,
        le=365,
        description="Days after which to clean up old, unused voice patterns",
    )


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


class CloudConfig(BaseModel):
    """Cloud configuration for Supabase access and storage."""

    # Hardcoded Supabase connection for all users
    supabase_url: str = Field(
        default="https://sdkxuiqcwlmbpjvjdpkj.supabase.co",
        description="Hardcoded Supabase project URL for all users",
    )
    supabase_key: str = Field(
        default="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNka3h1aXFjd2xtYnBqdmpkcGtqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTU4MTU3MzQsImV4cCI6MjA3MTM5MTczNH0.VoP6yX3GwyVjylgioTGchQYwPQ_K2xQFdHP5ani0vts",
        description="Hardcoded Supabase anon key for all users",
    )
    supabase_bucket: str | None = Field(
        default=None, description="Default storage bucket name"
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
    transcript_processing: TranscriptProcessingConfig = Field(
        default_factory=TranscriptProcessingConfig
    )
    llm: LLMConfig = Field(default_factory=LLMConfig)
    local_config: LocalLLMConfig = Field(default_factory=LocalLLMConfig)
    api_keys: APIKeysConfig = Field(default_factory=APIKeysConfig)
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    file_watcher: FileWatcherConfig = Field(default_factory=FileWatcherConfig)
    youtube_api: YouTubeAPIConfig = Field(default_factory=YouTubeAPIConfig)
    youtube_processing: YouTubeProcessingConfig = Field(
        default_factory=YouTubeProcessingConfig
    )
    podcast_discovery: PodcastDiscoveryConfig = Field(
        default_factory=PodcastDiscoveryConfig
    )
    moc: MOCConfig = Field(default_factory=MOCConfig)
    hce: HCEConfig = Field(default_factory=HCEConfig)
    claims_first: ClaimsFirstConfig = Field(default_factory=ClaimsFirstConfig)
    batch_processing: BatchProcessingConfig = Field(default_factory=BatchProcessingConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    speaker_identification: SpeakerIdentificationConfig = Field(
        default_factory=SpeakerIdentificationConfig
    )
    gui_features: GUIFeaturesConfig = Field(default_factory=GUIFeaturesConfig)
    cloud: CloudConfig = Field(default_factory=CloudConfig)

    # Proxy Configuration
    proxy_provider: str = Field(
        default="packetstream",
        description="Preferred proxy provider: packetstream, anyip, oxylabs, gonzoproxy, brightdata, or direct",
    )
    proxy_failover_enabled: bool = Field(
        default=True,
        description="Enable automatic failover to other proxy providers if preferred fails",
    )

    def __init__(self, config_path: str | Path | None = None, **kwargs) -> None:
        """Initialize settings from YAML file and environment variables."""

        # Import here to avoid circular imports
        try:
            from .utils.macos_paths import get_config_dir, get_default_paths

            macos_paths_available = True
        except ImportError:
            macos_paths_available = False

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

        # Set up default paths using macOS standards
        if macos_paths_available:
            default_macos_paths = get_default_paths()
            config_dir = get_config_dir()

            # Apply default paths if not overridden
            if "paths" not in kwargs:
                kwargs["paths"] = {}

            for key, value in default_macos_paths.items():
                if key not in kwargs["paths"] or not kwargs["paths"][key]:
                    kwargs["paths"][key] = value

        # Load from YAML file if provided
        if config_path:
            config_data = load_yaml_static(config_path)
            kwargs.update(config_data)
        else:
            # Try to load from default locations (including new macOS standard location)
            default_paths = [
                Path("config/settings.yaml"),
                Path("../config/settings.yaml"),  # Handle running from src/ directory
                Path("settings.yaml"),
            ]

            # Add macOS standard config location
            if macos_paths_available:
                default_paths.extend(
                    [
                        config_dir / "settings.yaml",
                        Path.home()
                        / ".knowledge-system"
                        / "settings.yaml",  # Legacy fallback
                    ]
                )
            else:
                default_paths.append(
                    Path.home() / ".knowledge-system" / "settings.yaml"
                )

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
        ]

        # Add macOS standard config location for credentials
        if macos_paths_available:
            credentials_paths.extend(
                [
                    config_dir / "credentials.yaml",
                    Path.home()
                    / ".knowledge-system"
                    / "credentials.yaml",  # Legacy fallback
                ]
            )
        else:
            credentials_paths.append(
                Path.home() / ".knowledge-system" / "credentials.yaml"
            )

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

                        # Merge other sections if they exist (deep-merge dict sections)
                        for key, value in cred_data.items():
                            if key == "api_keys":
                                continue  # handled above
                            if (
                                key in kwargs
                                and isinstance(kwargs[key], dict)
                                and isinstance(value, dict)
                            ):
                                # Deep merge for dict sections like 'cloud'
                                kwargs[key].update(value)
                            else:
                                kwargs[key] = value
                        break
                except (FileNotFoundError, PermissionError, yaml.YAMLError, KeyError):
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

        # Google API key fallback from environment
        # Accept common env var names for Gemini/Google AI
        if not api_keys.get("google_api_key") and not api_keys.get("google"):
            env_google = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
            if env_google:
                api_keys["google"] = env_google

        # Bright Data API key fallback from environment
        # Accept common env var names for convenience
        if not api_keys.get("bright_data_api_key"):
            env_bd = (
                os.getenv("BRIGHT_DATA_API_KEY")
                or os.getenv("BRIGHTDATA_API_KEY")
                or os.getenv("BD_API_KEY")
            )
            if env_bd:
                api_keys["bright_data_api_key"] = env_bd

        # Remove WebShare env loads - Bright Data only
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
