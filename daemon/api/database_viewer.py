"""
Database Viewer Service

Provides read-only access to the SQLite database for admin viewing.
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from daemon.config.settings import settings

logger = logging.getLogger(__name__)


class DatabaseViewer:
    """Service for viewing database contents."""

    def __init__(self):
        self.db_path = Path(settings.database_path)
        if not self.db_path.exists():
            logger.warning(f"Database not found at {self.db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """Get read-only database connection."""
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row  # Return rows as dicts
        return conn

    def get_table_names(self) -> list[str]:
        """Get all table names in database."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                )
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get table names: {e}")
            return []

    def get_table_info(self, table_name: str) -> dict[str, Any]:
        """Get metadata about a table."""
        try:
            with self._get_connection() as conn:
                # Get column info
                cursor = conn.execute(f"PRAGMA table_info({table_name})")
                columns = [
                    {
                        "name": row[1],
                        "type": row[2],
                        "notnull": bool(row[3]),
                        "default": row[4],
                        "pk": bool(row[5]),
                    }
                    for row in cursor.fetchall()
                ]

                # Get row count
                cursor = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
                row_count = cursor.fetchone()[0]

                return {
                    "table_name": table_name,
                    "columns": columns,
                    "row_count": row_count,
                }
        except Exception as e:
            logger.error(f"Failed to get table info for {table_name}: {e}")
            return {
                "table_name": table_name,
                "columns": [],
                "row_count": 0,
                "error": str(e),
            }

    def get_records(
        self,
        table_name: str,
        limit: int = 100,
        offset: int = 0,
        order_by: str | None = None,
    ) -> dict[str, Any]:
        """
        Get records from a table with pagination.

        Args:
            table_name: Name of the table
            limit: Maximum number of records to return
            offset: Number of records to skip
            order_by: Column to sort by (defaults to created_at DESC or first column)

        Returns:
            Dictionary with records, total_count, and metadata
        """
        try:
            with self._get_connection() as conn:
                # Get table info to determine sort column
                table_info = self.get_table_info(table_name)
                columns = [col["name"] for col in table_info["columns"]]

                if not columns:
                    return {
                        "table_name": table_name,
                        "records": [],
                        "total_count": 0,
                        "limit": limit,
                        "offset": offset,
                        "error": "No columns found",
                    }

                # Determine sort order
                if order_by is None:
                    # Try to find a timestamp column
                    timestamp_cols = [
                        "created_at",
                        "updated_at",
                        "processed_at",
                        "fetched_at",
                        "inserted_at",
                    ]
                    sort_col = next(
                        (col for col in timestamp_cols if col in columns), columns[0]
                    )
                    order_by = f"{sort_col} DESC"

                # Get total count
                cursor = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
                total_count = cursor.fetchone()[0]

                # Get records
                query = f"""
                    SELECT * FROM {table_name}
                    ORDER BY {order_by}
                    LIMIT ? OFFSET ?
                """
                cursor = conn.execute(query, (limit, offset))

                # Convert rows to dicts
                records = []
                for row in cursor.fetchall():
                    record = dict(row)
                    # Format datetime values for display
                    for key, value in record.items():
                        if value and isinstance(value, str):
                            # Try to parse as datetime
                            try:
                                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                                record[key] = dt.strftime("%Y-%m-%d %H:%M:%S")
                            except (ValueError, AttributeError):
                                pass
                    records.append(record)

                return {
                    "table_name": table_name,
                    "columns": columns,
                    "records": records,
                    "total_count": total_count,
                    "limit": limit,
                    "offset": offset,
                    "has_more": (offset + limit) < total_count,
                }

        except Exception as e:
            logger.error(f"Failed to get records from {table_name}: {e}")
            return {
                "table_name": table_name,
                "records": [],
                "total_count": 0,
                "limit": limit,
                "offset": offset,
                "error": str(e),
            }

    def get_database_summary(self) -> dict[str, Any]:
        """Get summary of all tables in database."""
        tables = self.get_table_names()
        table_summaries = []

        for table_name in tables:
            info = self.get_table_info(table_name)
            table_summaries.append(
                {
                    "name": table_name,
                    "row_count": info["row_count"],
                    "column_count": len(info["columns"]),
                }
            )

        # Get database file info
        db_size = 0
        last_modified = None
        if self.db_path.exists():
            db_size = self.db_path.stat().st_size
            last_modified = datetime.fromtimestamp(
                self.db_path.stat().st_mtime
            ).strftime("%Y-%m-%d %H:%M:%S")

        return {
            "database_path": str(self.db_path),
            "database_size_mb": round(db_size / (1024 * 1024), 2),
            "last_modified": last_modified,
            "table_count": len(tables),
            "tables": table_summaries,
        }


# Global instance
database_viewer = DatabaseViewer()

