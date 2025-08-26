"""
Database Schema Versioning and Migration System

Implements Alembic-based database schema versioning for the Knowledge System SQLite database.
This allows for safe schema updates and rollbacks in future versions.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    from alembic import command
    from alembic.config import Config
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import Engine
except ImportError:
    # Alembic is optional - system works without it
    command = None
    Config = None
    MigrationContext = None
    Operations = None
    ScriptDirectory = None
    create_engine = None
    text = None
    Engine = None

from ..logger import get_logger
from .service import DatabaseService

logger = get_logger(__name__)


class DatabaseMigrationManager:
    """Manages database schema migrations using Alembic."""

    def __init__(self, database_service: DatabaseService | None = None):
        """Initialize the migration manager."""
        self.db_service = database_service or DatabaseService()
        self.db_path = self.db_service.db_path
        self.migrations_dir = Path(__file__).parent / "migrations"

        # Check if Alembic is available
        self.alembic_available = all(
            [
                command,
                Config,
                MigrationContext,
                Operations,
                ScriptDirectory,
                create_engine,
                text,
                Engine,
            ]
        )

        if not self.alembic_available:
            logger.warning(
                "Alembic not available - schema versioning disabled. "
                "Install with: pip install alembic"
            )

    def is_alembic_available(self) -> bool:
        """Check if Alembic is available for migrations."""
        return self.alembic_available

    def initialize_migrations(self) -> bool:
        """Initialize Alembic migrations for the database."""
        if not self.alembic_available:
            logger.error("Alembic not available - cannot initialize migrations")
            return False

        try:
            # Create migrations directory if it doesn't exist
            self.migrations_dir.mkdir(parents=True, exist_ok=True)

            # Create alembic.ini configuration
            alembic_ini_path = self.migrations_dir.parent / "alembic.ini"

            if not alembic_ini_path.exists():
                self._create_alembic_config(alembic_ini_path)

            # Initialize Alembic in the migrations directory
            if not (self.migrations_dir / "alembic.ini").exists():
                os.chdir(self.migrations_dir)
                alembic_cfg = Config(str(alembic_ini_path))
                command.init(alembic_cfg, str(self.migrations_dir))
                logger.info(f"Initialized Alembic migrations in {self.migrations_dir}")

            return True

        except Exception as e:
            logger.error(f"Failed to initialize Alembic migrations: {e}")
            return False

    def _create_alembic_config(self, config_path: Path) -> None:
        """Create an Alembic configuration file."""
        config_content = f"""# Alembic Configuration for Knowledge System

[alembic]
# Path to migration scripts
script_location = {self.migrations_dir}

# Template used to generate migration files
file_template = %%(year)d%%(month).2d%%(day).2d_%%(hour).2d%%(minute).2d_%%(rev)s_%%(slug)s

# sys.path path, will be prepended to sys.path if present.
prepend_sys_path = .

# Timezone to use when rendering the date within the migration file
timezone =

# Maximum length of characters to apply to the "slug" field
truncate_slug_length = 40

# Set to 'true' to run the environment during the 'revision' command
revision_environment = false

# Set to 'true' to allow .pyc and .pyo files without
# a source .py file to be detected as revisions in the
# versions/ directory
sourceless = false

# Version path separator; As mentioned above, this is the character used to split
# version_locations. The default within new alembic.ini files is "os", which uses
# os.pathsep. If this key is omitted entirely, it falls back to the legacy
# behavior of splitting on spaces and/or commas.
version_path_separator = :

# The output encoding used when revision files
# are written from script.py.mako
output_encoding = utf-8

sqlalchemy.url = sqlite:///{self.db_path}

[post_write_hooks]
# Post-write hooks define scripts or Python functions that are run
# on newly generated revision scripts.

# Logging configuration
[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
"""

        with open(config_path, "w", encoding="utf-8") as f:
            f.write(config_content)

        logger.info(f"Created Alembic configuration: {config_path}")

    def create_migration(self, message: str) -> str | None:
        """Create a new migration file."""
        if not self.alembic_available:
            logger.error("Alembic not available - cannot create migration")
            return None

        try:
            alembic_cfg = self._get_alembic_config()
            if alembic_cfg is None:
                return None

            # Create a new revision
            revision = command.revision(alembic_cfg, autogenerate=True, message=message)
            logger.info(f"Created migration: {revision}")
            return revision

        except Exception as e:
            logger.error(f"Failed to create migration: {e}")
            return None

    def upgrade_database(self, revision: str = "head") -> bool:
        """Upgrade database to a specific revision."""
        if not self.alembic_available:
            logger.warning("Alembic not available - skipping database upgrade")
            return True  # Not an error if Alembic isn't available

        try:
            alembic_cfg = self._get_alembic_config()
            if alembic_cfg is None:
                return False

            command.upgrade(alembic_cfg, revision)
            logger.info(f"Upgraded database to revision: {revision}")
            return True

        except Exception as e:
            logger.error(f"Failed to upgrade database: {e}")
            return False

    def downgrade_database(self, revision: str) -> bool:
        """Downgrade database to a specific revision."""
        if not self.alembic_available:
            logger.error("Alembic not available - cannot downgrade database")
            return False

        try:
            alembic_cfg = self._get_alembic_config()
            if alembic_cfg is None:
                return False

            command.downgrade(alembic_cfg, revision)
            logger.info(f"Downgraded database to revision: {revision}")
            return True

        except Exception as e:
            logger.error(f"Failed to downgrade database: {e}")
            return False

    def get_current_revision(self) -> str | None:
        """Get the current database revision."""
        if not self.alembic_available:
            return None

        try:
            engine = create_engine(f"sqlite:///{self.db_path}")
            with engine.connect() as connection:
                context = MigrationContext.configure(connection)
                return context.get_current_revision()

        except Exception as e:
            logger.error(f"Failed to get current revision: {e}")
            return None

    def get_migration_history(self) -> list[dict[str, Any]]:
        """Get the migration history."""
        if not self.alembic_available:
            return []

        try:
            alembic_cfg = self._get_alembic_config()
            if alembic_cfg is None:
                return []

            script_dir = ScriptDirectory.from_config(alembic_cfg)
            revisions = []

            for revision in script_dir.walk_revisions():
                revisions.append(
                    {
                        "revision": revision.revision,
                        "down_revision": revision.down_revision,
                        "branch_labels": revision.branch_labels,
                        "depends_on": revision.depends_on,
                        "doc": revision.doc,
                        "is_head": revision.is_head,
                        "is_merge_point": revision.is_merge_point,
                    }
                )

            return revisions

        except Exception as e:
            logger.error(f"Failed to get migration history: {e}")
            return []

    def _get_alembic_config(self) -> Config | None:
        """Get Alembic configuration."""
        try:
            alembic_ini_path = self.migrations_dir.parent / "alembic.ini"

            if not alembic_ini_path.exists():
                logger.error(
                    "Alembic configuration not found. Run initialize_migrations() first."
                )
                return None

            alembic_cfg = Config(str(alembic_ini_path))
            alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{self.db_path}")
            return alembic_cfg

        except Exception as e:
            logger.error(f"Failed to get Alembic configuration: {e}")
            return None

    def check_schema_compatibility(self) -> dict[str, Any]:
        """Check if current database schema is compatible with the application."""
        result = {
            "compatible": True,
            "current_revision": None,
            "expected_revision": "head",
            "alembic_available": self.alembic_available,
            "issues": [],
            "recommendations": [],
        }

        if not self.alembic_available:
            result["recommendations"].append(
                "Install Alembic for better schema management: pip install alembic"
            )
            return result

        try:
            # Check if database exists and has tables
            if not self.db_service.db_path.exists():
                result["issues"].append("Database does not exist")
                result["compatible"] = False
                result["recommendations"].append(
                    "Run 'knowledge-system database initdb' to create database"
                )
                return result

            # Get current revision
            current_revision = self.get_current_revision()
            result["current_revision"] = current_revision

            if current_revision is None:
                result["issues"].append("Database has no migration tracking")
                result["recommendations"].append(
                    "Initialize Alembic migrations and stamp current version"
                )

            # Check if migrations are needed
            alembic_cfg = self._get_alembic_config()
            if alembic_cfg:
                script_dir = ScriptDirectory.from_config(alembic_cfg)
                head_revision = script_dir.get_current_head()

                if current_revision != head_revision:
                    result["compatible"] = False
                    result["issues"].append(
                        f"Database schema outdated: {current_revision} -> {head_revision}"
                    )
                    result["recommendations"].append(
                        "Run 'knowledge-system database upgrade' to update schema"
                    )

        except Exception as e:
            result["compatible"] = False
            result["issues"].append(f"Schema check failed: {e}")
            logger.error(f"Schema compatibility check failed: {e}")

        return result


# Convenience functions for CLI usage
def init_migrations(db_service: DatabaseService | None = None) -> bool:
    """Initialize database migrations."""
    manager = DatabaseMigrationManager(db_service)
    return manager.initialize_migrations()


def create_migration(
    message: str, db_service: DatabaseService | None = None
) -> str | None:
    """Create a new migration."""
    manager = DatabaseMigrationManager(db_service)
    return manager.create_migration(message)


def upgrade_database(
    revision: str = "head", db_service: DatabaseService | None = None
) -> bool:
    """Upgrade database schema."""
    manager = DatabaseMigrationManager(db_service)
    return manager.upgrade_database(revision)


def check_schema_compatibility(
    db_service: DatabaseService | None = None,
) -> dict[str, Any]:
    """Check database schema compatibility."""
    manager = DatabaseMigrationManager(db_service)
    return manager.check_schema_compatibility()


def apply_quality_rating_migration(db_service: DatabaseService | None = None) -> bool:
    """Apply the quality rating migration to add quality rating tables."""
    if db_service is None:
        db_service = DatabaseService()

    # Check if SQLAlchemy text is available
    if text is None:
        try:
            from sqlalchemy import text as sql_text
        except ImportError:
            logger.error("SQLAlchemy not available - cannot apply migration")
            return False
    else:
        sql_text = text

    try:
        # Read and execute the quality rating migration SQL
        migration_path = Path(__file__).parent / "migrations" / "2025_01_15_quality_ratings.sql"

        if not migration_path.exists():
            logger.error(f"Quality rating migration file not found: {migration_path}")
            return False

        with open(migration_path, 'r', encoding='utf-8') as f:
            migration_sql = f.read()

        # Execute the migration
        with db_service.get_session() as session:
            # Split by semicolon and execute each statement
            statements = [stmt.strip() for stmt in migration_sql.split(';') if stmt.strip()]

            for statement in statements:
                if statement:
                    session.execute(sql_text(statement))

            session.commit()

        logger.info("Successfully applied quality rating migration")
        return True

    except Exception as e:
        logger.error(f"Failed to apply quality rating migration: {e}")
        return False


def apply_claim_tier_validation_migration(db_service: DatabaseService | None = None) -> bool:
    """Apply the claim tier validation migration to add claim validation tables."""
    if db_service is None:
        db_service = DatabaseService()

    # Check if SQLAlchemy text is available
    if text is None:
        try:
            from sqlalchemy import text as sql_text
        except ImportError:
            logger.error("SQLAlchemy not available - cannot apply migration")
            return False
    else:
        sql_text = text

    try:
        # Read and execute the claim tier validation migration SQL
        migration_path = Path(__file__).parent / "migrations" / "2025_01_15_claim_tier_validation.sql"

        if not migration_path.exists():
            logger.error(f"Claim tier validation migration file not found: {migration_path}")
            return False

        with open(migration_path, 'r', encoding='utf-8') as f:
            migration_sql = f.read()

        # Execute the migration
        with db_service.get_session() as session:
            # Split by semicolon and execute each statement
            statements = [stmt.strip() for stmt in migration_sql.split(';') if stmt.strip()]

            for statement in statements:
                if statement:
                    session.execute(sql_text(statement))

            session.commit()

        logger.info("Successfully applied claim tier validation migration")
        return True

    except Exception as e:
        logger.error(f"Failed to apply claim tier validation migration: {e}")
        return False
