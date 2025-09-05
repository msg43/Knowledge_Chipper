"""
Process Isolation Configuration Management

Provides configuration settings and management for the process isolation system,
including resource limits, safety settings, and feature flags.

Configuration Hierarchy:
1. Default settings (defined here)
2. Environment variables
3. User configuration files
4. Runtime overrides
"""

import os
import platform
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil
import yaml

from ..logger import get_logger

logger = get_logger(__name__)


class ProcessIsolationConfig:
    """Configuration manager for process isolation settings."""

    # Default configuration
    DEFAULT_CONFIG = {
        "process_isolation": {
            "enabled": True,
            "max_restart_attempts": 3,
            "restart_backoff_seconds": [5, 10, 30],  # Exponential backoff
            "heartbeat_timeout_seconds": 60,
            "startup_timeout_seconds": 60,
            "shutdown_timeout_seconds": 10,
            "force_kill_timeout_seconds": 5,
        },
        "memory_management": {
            "memory_pressure_threshold": 85.0,  # Percentage
            "swap_pressure_threshold": 50.0,  # Percentage
            "growth_rate_threshold": 10.0,  # MB/s
            "emergency_cleanup_enabled": True,
            "adaptive_batch_sizing": True,
            "model_cache_limit_gb": 4.0,
            "max_concurrent_models": 2,
        },
        "checkpoint_system": {
            "enabled": True,
            "frequency": "per_file",  # per_file, time_based, adaptive
            "checkpoint_directory": None,  # None = auto-detect
            "max_checkpoint_age_days": 7,
            "auto_cleanup_enabled": True,
            "backup_checkpoints": True,
        },
        "resource_limits": {
            "max_memory_per_process_gb": None,  # None = auto-detect
            "max_cpu_cores": None,  # None = auto-detect
            "disk_space_warning_gb": 5.0,
            "network_timeout_seconds": 30,
            "file_operation_timeout_seconds": 300,
        },
        "safety_features": {
            "crash_detection_enabled": True,
            "auto_recovery_enabled": True,
            "memory_monitoring_enabled": True,
            "performance_monitoring_enabled": True,
            "error_reporting_enabled": True,
        },
        "performance_tuning": {
            "ipc_buffer_size": 8192,
            "message_queue_size": 1000,
            "progress_update_interval": 1.0,  # Seconds
            "stats_collection_interval": 30.0,  # Seconds
            "lazy_model_loading": True,
        },
        "compatibility": {
            "fallback_to_thread_mode": True,
            "legacy_checkpoint_support": True,
            "graceful_degradation": True,
        },
    }

    def __init__(self, config_file: str | None = None):
        """
        Initialize configuration manager.

        Args:
            config_file: Optional path to configuration file
        """
        self.config = self.DEFAULT_CONFIG.copy()
        self.config_file = config_file
        self.system_info = self._gather_system_info()

        # Load configuration from various sources
        self._load_system_defaults()
        self._load_environment_config()
        self._load_config_file()
        self._apply_runtime_optimizations()

        logger.info("Process isolation configuration loaded")

    def _gather_system_info(self) -> dict[str, Any]:
        """Gather system information for auto-configuration."""
        try:
            memory_gb = psutil.virtual_memory().total / (1024**3)
            cpu_count = psutil.cpu_count()

            return {
                "platform": platform.system(),
                "architecture": platform.machine(),
                "memory_gb": memory_gb,
                "cpu_count": cpu_count,
                "python_version": platform.python_version(),
            }
        except Exception as e:
            logger.warning(f"Failed to gather system info: {e}")
            return {}

    def _load_system_defaults(self):
        """Load system-specific default settings."""
        memory_gb = self.system_info.get("memory_gb", 8)
        cpu_count = self.system_info.get("cpu_count", 4)

        # Auto-configure memory limits
        if memory_gb < 4:
            # Low memory system
            self.config["memory_management"]["memory_pressure_threshold"] = 75.0
            self.config["memory_management"]["model_cache_limit_gb"] = 1.0
            self.config["memory_management"]["max_concurrent_models"] = 1
            self.config["resource_limits"]["max_memory_per_process_gb"] = 2.0
        elif memory_gb > 32:
            # High memory system
            self.config["memory_management"]["model_cache_limit_gb"] = 8.0
            self.config["memory_management"]["max_concurrent_models"] = 4
            self.config["resource_limits"]["max_memory_per_process_gb"] = 16.0
        else:
            # Default system
            self.config["resource_limits"]["max_memory_per_process_gb"] = (
                memory_gb * 0.8
            )

        # Auto-configure CPU limits
        self.config["resource_limits"]["max_cpu_cores"] = max(1, cpu_count - 1)

        # Platform-specific settings
        if self.system_info.get("platform") == "Darwin":  # macOS
            self.config["process_isolation"]["startup_timeout_seconds"] = 90
        elif self.system_info.get("platform") == "Windows":
            self.config["process_isolation"]["shutdown_timeout_seconds"] = 15

    def _load_environment_config(self):
        """Load configuration from environment variables."""
        env_mappings = {
            "KC_PROCESS_ISOLATION_ENABLED": ("process_isolation", "enabled", bool),
            "KC_MEMORY_THRESHOLD": (
                "memory_management",
                "memory_pressure_threshold",
                float,
            ),
            "KC_MAX_RESTART_ATTEMPTS": (
                "process_isolation",
                "max_restart_attempts",
                int,
            ),
            "KC_CHECKPOINT_ENABLED": ("checkpoint_system", "enabled", bool),
            "KC_AUTO_RECOVERY": ("safety_features", "auto_recovery_enabled", bool),
            "KC_MEMORY_LIMIT_GB": (
                "resource_limits",
                "max_memory_per_process_gb",
                float,
            ),
            "KC_FALLBACK_TO_THREADS": (
                "compatibility",
                "fallback_to_thread_mode",
                bool,
            ),
        }

        for env_var, (section, key, type_func) in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                try:
                    if type_func == bool:
                        value = value.lower() in ("true", "1", "yes", "on")
                    else:
                        value = type_func(value)

                    self.config[section][key] = value
                    logger.debug(f"Loaded {env_var} = {value}")
                except (ValueError, TypeError) as e:
                    logger.warning(
                        f"Invalid environment variable {env_var} = {value}: {e}"
                    )

    def _load_config_file(self):
        """Load configuration from file."""
        if not self.config_file:
            # Try to find default config file
            possible_locations = [
                Path.home()
                / ".config"
                / "knowledge_chipper"
                / "process_isolation.yaml",
                Path.cwd() / "config" / "process_isolation.yaml",
                Path(__file__).parent.parent.parent.parent
                / "config"
                / "process_isolation.yaml",
            ]

            for location in possible_locations:
                if location.exists():
                    self.config_file = str(location)
                    break

        if self.config_file and Path(self.config_file).exists():
            try:
                with open(self.config_file) as f:
                    file_config = yaml.safe_load(f)

                if file_config:
                    self._merge_config(self.config, file_config)
                    logger.info(f"Loaded configuration from {self.config_file}")

            except Exception as e:
                logger.error(f"Failed to load config file {self.config_file}: {e}")

    def _merge_config(self, base: dict[str, Any], override: dict[str, Any]):
        """Recursively merge configuration dictionaries."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value

    def _apply_runtime_optimizations(self):
        """Apply runtime optimizations based on system state."""
        # Adjust settings based on current system load
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory_percent = psutil.virtual_memory().percent

            # If system is under high load, be more conservative
            if cpu_percent > 80 or memory_percent > 80:
                self.config["memory_management"]["memory_pressure_threshold"] = 70.0
                self.config["process_isolation"]["max_restart_attempts"] = 2
                self.config["performance_tuning"]["progress_update_interval"] = 2.0
                logger.info("Applied conservative settings due to high system load")

        except Exception as e:
            logger.warning(f"Failed to apply runtime optimizations: {e}")

    def get(self, section: str, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self.config.get(section, {}).get(key, default)

    def set(self, section: str, key: str, value: Any):
        """Set a configuration value."""
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = value

    def is_enabled(self) -> bool:
        """Check if process isolation is enabled."""
        return self.get("process_isolation", "enabled", True)

    def should_fallback_to_threads(self) -> bool:
        """Check if should fallback to thread mode."""
        # Check for conditions that would require fallback
        if not self.is_enabled():
            return True

        # Check system requirements
        memory_gb = self.system_info.get("memory_gb", 0)
        if memory_gb < 2:  # Very low memory
            logger.warning("Falling back to thread mode due to low memory")
            return True

        # Check platform compatibility
        platform_name = self.system_info.get("platform")
        if platform_name not in ["Linux", "Darwin", "Windows"]:
            logger.warning(
                f"Platform {platform_name} may not fully support process isolation"
            )
            return self.get("compatibility", "fallback_to_thread_mode", True)

        return False

    def get_memory_limits(self) -> dict[str, float]:
        """Get memory limit configuration."""
        return {
            "pressure_threshold": self.get(
                "memory_management", "memory_pressure_threshold", 85.0
            ),
            "swap_threshold": self.get(
                "memory_management", "swap_pressure_threshold", 50.0
            ),
            "growth_rate_threshold": self.get(
                "memory_management", "growth_rate_threshold", 10.0
            ),
            "max_process_memory_gb": self.get(
                "resource_limits", "max_memory_per_process_gb"
            ),
            "cache_limit_gb": self.get(
                "memory_management", "model_cache_limit_gb", 4.0
            ),
        }

    def get_checkpoint_config(self) -> dict[str, Any]:
        """Get checkpoint system configuration."""
        config = self.config.get("checkpoint_system", {})

        # Auto-detect checkpoint directory if not specified
        if not config.get("checkpoint_directory"):
            checkpoint_dir = (
                Path.home() / ".cache" / "knowledge_chipper" / "checkpoints"
            )
            checkpoint_dir.mkdir(parents=True, exist_ok=True)
            config["checkpoint_directory"] = str(checkpoint_dir)

        return config

    def get_restart_policy(self) -> dict[str, Any]:
        """Get process restart policy configuration."""
        return {
            "max_attempts": self.get("process_isolation", "max_restart_attempts", 3),
            "backoff_seconds": self.get(
                "process_isolation", "restart_backoff_seconds", [5, 10, 30]
            ),
            "enabled": self.get("safety_features", "auto_recovery_enabled", True),
        }

    def save_config(self, file_path: str | None = None):
        """Save current configuration to file."""
        save_path = file_path or self.config_file
        if not save_path:
            save_path = (
                Path.home() / ".config" / "knowledge_chipper" / "process_isolation.yaml"
            )

        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(save_path, "w") as f:
                yaml.dump(self.config, f, default_flow_style=False, indent=2)
            logger.info(f"Configuration saved to {save_path}")
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")

    def validate_config(self) -> list[str]:
        """Validate configuration and return list of issues."""
        issues = []

        # Check memory settings
        memory_threshold = self.get("memory_management", "memory_pressure_threshold")
        if not 10 <= memory_threshold <= 95:
            issues.append(
                f"Memory pressure threshold {memory_threshold}% is outside safe range (10-95%)"
            )

        # Check restart attempts
        max_attempts = self.get("process_isolation", "max_restart_attempts")
        if not 0 <= max_attempts <= 10:
            issues.append(
                f"Max restart attempts {max_attempts} is outside reasonable range (0-10)"
            )

        # Check timeouts
        startup_timeout = self.get("process_isolation", "startup_timeout_seconds")
        if startup_timeout < 10:
            issues.append(f"Startup timeout {startup_timeout}s may be too short")

        # Check resource limits
        max_memory = self.get("resource_limits", "max_memory_per_process_gb")
        if max_memory and max_memory > self.system_info.get("memory_gb", 8):
            issues.append(f"Max process memory {max_memory}GB exceeds system memory")

        return issues

    def get_debug_info(self) -> dict[str, Any]:
        """Get debug information about the configuration."""
        return {
            "config_file": self.config_file,
            "system_info": self.system_info,
            "enabled": self.is_enabled(),
            "fallback_mode": self.should_fallback_to_threads(),
            "validation_issues": self.validate_config(),
        }


# Global configuration instance
_global_config = None


def get_process_isolation_config(
    config_file: str | None = None,
) -> ProcessIsolationConfig:
    """Get the global process isolation configuration instance."""
    global _global_config
    if _global_config is None:
        _global_config = ProcessIsolationConfig(config_file)
    return _global_config


def reset_global_config():
    """Reset the global configuration instance (for testing)."""
    global _global_config
    _global_config = None


# Configuration validation and helpers


def validate_system_requirements() -> dict[str, Any]:
    """Validate system requirements for process isolation."""
    requirements = {
        "min_memory_gb": 2.0,
        "min_python_version": "3.8",
        "supported_platforms": ["Linux", "Darwin", "Windows"],
    }

    results = {"meets_requirements": True, "issues": [], "warnings": []}

    try:
        # Check memory
        memory_gb = psutil.virtual_memory().total / (1024**3)
        if memory_gb < requirements["min_memory_gb"]:
            results["meets_requirements"] = False
            results["issues"].append(
                f"Insufficient memory: {memory_gb:.1f}GB < {requirements['min_memory_gb']}GB"
            )

        # Check Python version
        import sys

        python_version = sys.version_info
        min_version = tuple(map(int, requirements["min_python_version"].split(".")))
        if python_version[:2] < min_version:
            results["meets_requirements"] = False
            results["issues"].append(
                f"Python version {python_version[0]}.{python_version[1]} < {requirements['min_python_version']}"
            )

        # Check platform
        current_platform = platform.system()
        if current_platform not in requirements["supported_platforms"]:
            results["warnings"].append(f"Platform {current_platform} not fully tested")

        # Check available disk space
        try:
            disk_usage = psutil.disk_usage("/")
            free_gb = disk_usage.free / (1024**3)
            if free_gb < 5.0:
                results["warnings"].append(f"Low disk space: {free_gb:.1f}GB free")
        except Exception:
            pass

    except Exception as e:
        results["issues"].append(f"System check failed: {e}")
        results["meets_requirements"] = False

    return results
