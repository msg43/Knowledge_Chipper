"""
macOS Standard Paths Utility

Provides proper macOS directory paths following Apple's guidelines.
"""

import os
import sys
from pathlib import Path

from ..logger import get_logger

logger = get_logger(__name__)


def get_application_support_dir() -> Path:
    """Get the Application Support directory for Knowledge Chipper."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "Knowledge Chipper"
    elif os.name == "nt":  # Windows
        appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        base = Path(appdata) / "Knowledge Chipper"
    else:  # Linux/Unix
        base = Path.home() / ".knowledge_chipper"

    base.mkdir(parents=True, exist_ok=True)
    return base


def get_cache_dir() -> Path:
    """Get the cache directory for Knowledge Chipper."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches" / "Knowledge Chipper"
    elif os.name == "nt":  # Windows
        localappdata = os.environ.get(
            "LOCALAPPDATA", str(Path.home() / "AppData" / "Local")
        )
        base = Path(localappdata) / "Knowledge Chipper" / "Cache"
    else:  # Linux/Unix
        base = Path.home() / ".cache" / "knowledge_chipper"

    base.mkdir(parents=True, exist_ok=True)
    return base


def get_logs_dir() -> Path:
    """Get the logs directory for Knowledge Chipper."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Logs" / "Knowledge Chipper"
    elif os.name == "nt":  # Windows
        localappdata = os.environ.get(
            "LOCALAPPDATA", str(Path.home() / "AppData" / "Local")
        )
        base = Path(localappdata) / "Knowledge Chipper" / "Logs"
    else:  # Linux/Unix
        base = Path.home() / ".local" / "share" / "knowledge_chipper" / "logs"

    base.mkdir(parents=True, exist_ok=True)
    return base


def get_user_data_dir() -> Path:
    """Get the user data directory (documents/output) for Knowledge Chipper."""
    if sys.platform == "darwin":
        base = Path.home() / "Documents" / "Knowledge Chipper"
    elif os.name == "nt":  # Windows
        documents = Path.home() / "Documents"
        base = documents / "Knowledge Chipper"
    else:  # Linux/Unix
        base = Path.home() / "Documents" / "Knowledge Chipper"

    base.mkdir(parents=True, exist_ok=True)
    return base


def get_config_dir() -> Path:
    """Get the configuration directory for Knowledge Chipper."""
    if sys.platform == "darwin":
        # On macOS, config goes in Application Support
        base = get_application_support_dir() / "Config"
    elif os.name == "nt":  # Windows
        appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        base = Path(appdata) / "Knowledge Chipper" / "Config"
    else:  # Linux/Unix
        config_home = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
        base = Path(config_home) / "knowledge_chipper"

    base.mkdir(parents=True, exist_ok=True)
    return base


def get_default_paths() -> dict[str, str]:
    """Get all default paths for Knowledge Chipper following macOS standards."""
    app_support = get_application_support_dir()
    cache_dir = get_cache_dir()
    logs_dir = get_logs_dir()
    user_data = get_user_data_dir()
    config_dir = get_config_dir()

    # Create subdirectories
    output_dir = user_data / "Output"
    input_dir = user_data / "Input"
    transcripts_dir = output_dir / "Transcripts"
    summaries_dir = output_dir / "Summaries"
    mocs_dir = output_dir / "MOCs"
    exports_dir = output_dir / "Exports"
    thumbnails_dir = cache_dir / "Thumbnails"
    models_dir = cache_dir / "Models"

    # Create all subdirectories
    for directory in [
        output_dir,
        input_dir,
        transcripts_dir,
        summaries_dir,
        mocs_dir,
        exports_dir,
        thumbnails_dir,
        models_dir,
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    return {
        # Primary directories
        "data_dir": str(app_support),
        "output_dir": str(output_dir),
        "cache_dir": str(cache_dir),
        "logs_dir": str(logs_dir),
        "config_dir": str(config_dir),
        # Specific output directories
        "output": str(output_dir),
        "transcripts": str(transcripts_dir),
        "summaries": str(summaries_dir),
        "mocs": str(mocs_dir),
        "exports": str(exports_dir),
        # Cache subdirectories
        "cache": str(cache_dir),
        "thumbnails": str(thumbnails_dir),
        "models": str(models_dir),
        # Input directory (user can choose, default to user data)
        "input_dir": str(input_dir),
        "input": str(input_dir),
        # Logs (alias)
        "logs": str(logs_dir),
    }


def migrate_legacy_data(legacy_project_dir: Path) -> bool:
    """
    Migrate data from legacy project directory to proper macOS locations.

    This is for future use if we ever need to migrate existing user data.
    Currently not needed since there are no existing users.
    """
    try:
        logger.info("Starting legacy data migration...")

        # Get new standard locations
        app_support = get_application_support_dir()
        config_dir = get_config_dir()
        user_data = get_user_data_dir()

        # Migration mapping
        migrations = [
            # Database
            (
                legacy_project_dir / "knowledge_system.db",
                app_support / "knowledge_system.db",
            ),
            # Configuration
            (legacy_project_dir / "config", config_dir),
            # State
            (legacy_project_dir / "state", app_support / "state"),
            # Output
            (legacy_project_dir / "output", user_data / "Output"),
        ]

        migrated_count = 0
        for source, destination in migrations:
            if source.exists():
                logger.info(f"Migrating {source} → {destination}")

                if source.is_file():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    import shutil

                    shutil.copy2(source, destination)
                else:
                    import shutil

                    if destination.exists():
                        shutil.rmtree(destination)
                    shutil.copytree(source, destination)

                migrated_count += 1

        logger.info(f"Migration completed: {migrated_count} items migrated")
        return True

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False


def log_paths_info():
    """Log information about current paths (for debugging)."""
    paths = get_default_paths()
    logger.info("macOS Standard Paths Configuration:")
    for key, path in paths.items():
        logger.info(f"  {key}: {path}")
