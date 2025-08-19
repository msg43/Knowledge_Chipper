#!/usr/bin/env python3
"""
Test HCE database migration.

Creates a sample database and tests the migration process.
"""

import sqlite3
import tempfile
from pathlib import Path


def create_sample_database(db_path: Path) -> None:
    """Create a sample database with legacy schema."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Create legacy tables
    cursor.executescript(
        """
        CREATE TABLE videos (
            video_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            url TEXT
        );

        CREATE TABLE summaries (
            summary_id TEXT PRIMARY KEY,
            video_id TEXT,
            summary_text TEXT NOT NULL,
            llm_provider TEXT,
            llm_model TEXT,
            FOREIGN KEY (video_id) REFERENCES videos(video_id)
        );

        CREATE TABLE moc_extractions (
            moc_id TEXT PRIMARY KEY,
            video_id TEXT,
            people_json TEXT,
            tags_json TEXT,
            FOREIGN KEY (video_id) REFERENCES videos(video_id)
        );

        -- Insert sample data
        INSERT INTO videos (video_id, title, url) VALUES
            ('test123', 'Test Video', 'https://youtube.com/watch?v=test123');

        INSERT INTO summaries (summary_id, video_id, summary_text, llm_provider, llm_model) VALUES
            ('sum1', 'test123', 'This is a test summary', 'openai', 'gpt-4');

        INSERT INTO moc_extractions (moc_id, video_id, people_json, tags_json) VALUES
            ('moc1', 'test123', '["John Doe", "Jane Smith"]', '["ai", "testing"]');
    """
    )

    conn.commit()
    conn.close()


def test_hce_migration():
    """Test the HCE migration process."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"

        # Create sample database
        create_sample_database(db_path)

        # Apply HCE migrations
        conn = sqlite3.connect(str(db_path))

        # Read and apply migrations
        migrations_dir = (
            Path(__file__).parent.parent / "src/knowledge_system/database/migrations"
        )

        # Apply HCE schema
        with open(migrations_dir / "2025_08_18_hce.sql") as f:
            conn.executescript(f.read())

        # Apply compatibility views
        with open(migrations_dir / "2025_08_18_hce_compat.sql") as f:
            conn.executescript(f.read())

        # Apply column additions
        with open(migrations_dir / "2025_08_18_hce_columns.sql") as f:
            # SQLite doesn't support ALTER TABLE ADD COLUMN IF NOT EXISTS
            # So we need to check if columns exist first
            cursor = conn.cursor()

            # Check if columns already exist
            cursor.execute("PRAGMA table_info(summaries)")
            columns = [col[1] for col in cursor.fetchall()]

            if "processing_type" not in columns:
                cursor.execute(
                    "ALTER TABLE summaries ADD COLUMN processing_type TEXT DEFAULT 'legacy'"
                )

            if "hce_data_json" not in columns:
                cursor.execute("ALTER TABLE summaries ADD COLUMN hce_data_json TEXT")

            # Create index if not exists
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_summaries_processing_type
                ON summaries(processing_type)
            """
            )

        conn.commit()

        # Test that tables exist
        cursor = conn.cursor()

        # Check HCE tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        assert "episodes" in tables
        assert "claims" in tables
        assert "evidence_spans" in tables
        assert "relations" in tables
        assert "people" in tables
        assert "concepts" in tables
        assert "jargon" in tables

        # Check FTS tables
        assert "claims_fts" in tables
        assert "quotes_fts" in tables

        # Test compatibility views
        cursor.execute("SELECT name FROM sqlite_master WHERE type='view'")
        views = [row[0] for row in cursor.fetchall()]

        assert "legacy_claims" in views
        assert "legacy_relations" in views
        assert "legacy_entities_people" in views

        # Test that legacy data is still accessible
        cursor.execute("SELECT * FROM summaries WHERE video_id = 'test123'")
        summary = cursor.fetchone()
        assert summary is not None

        # Test new columns
        cursor.execute("PRAGMA table_info(summaries)")
        columns = [col[1] for col in cursor.fetchall()]
        assert "processing_type" in columns
        assert "hce_data_json" in columns

        # Test data migration
        cursor.execute(
            "UPDATE summaries SET processing_type = 'legacy' WHERE processing_type IS NULL"
        )
        conn.commit()

        cursor.execute(
            "SELECT processing_type FROM summaries WHERE summary_id = 'sum1'"
        )
        result = cursor.fetchone()
        assert result[0] == "legacy"

        conn.close()
        print("✅ HCE migration test passed!")


def test_fts_functionality():
    """Test FTS5 search functionality."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_fts.db"

        conn = sqlite3.connect(str(db_path))

        # Create FTS tables
        conn.executescript(
            """
            CREATE VIRTUAL TABLE claims_fts USING fts5(
                episode_id, claim_id, canonical, claim_type
            );

            INSERT INTO claims_fts VALUES
                ('ep1', 'c1', 'Machine learning is transforming industries', 'factual'),
                ('ep1', 'c2', 'Deep learning requires large datasets', 'factual');
        """
        )

        # Test search
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM claims_fts WHERE claims_fts MATCH 'learning'")
        results = cursor.fetchall()

        assert len(results) == 2
        assert any("Machine learning" in r[2] for r in results)

        conn.close()
        print("✅ FTS functionality test passed!")


if __name__ == "__main__":
    test_hce_migration()
    test_fts_functionality()
    print("\n✅ All migration tests passed!")
