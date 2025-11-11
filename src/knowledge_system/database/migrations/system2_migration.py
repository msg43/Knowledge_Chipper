"""
System 2 migration script.

This migration:
1. Enables WAL mode for better concurrency
2. Adds updated_at columns to existing tables
3. Creates new job orchestration and LLM tracking tables
"""

from sqlalchemy import text
from sqlalchemy.orm import Session


def migrate_to_system2(session: Session):
    """Execute System 2 migration."""

    print("Starting System 2 migration...")

    # 1. Enable WAL mode
    print("1. Enabling WAL mode...")
    session.execute(text("PRAGMA journal_mode=WAL"))
    session.commit()

    # Verify WAL is enabled
    result = session.execute(text("PRAGMA journal_mode")).scalar()
    if result and result.lower() == "wal":
        print("   ✓ WAL mode enabled")
    else:
        print(f"   ✗ Failed to enable WAL mode, current mode: {result}")

    # 2. Add updated_at columns to existing tables
    tables_to_update = ["claims", "people", "concepts", "jargon", "episodes"]

    for table in tables_to_update:
        print(f"2. Adding updated_at to {table}...")
        try:
            # Check if column already exists
            result = session.execute(text(f"PRAGMA table_info({table})"))
            columns = [row[1] for row in result]

            if "updated_at" not in columns:
                session.execute(
                    text(
                        f"""
                    ALTER TABLE {table}
                    ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                """
                    )
                )
                session.commit()
                print(f"   ✓ Added updated_at to {table}")
            else:
                print(f"   - updated_at already exists in {table}")
        except Exception as e:
            # Table might not exist yet
            print(f"   - Skipping {table}: {str(e)}")

    # 2.5 Add missing columns for System 2
    print("2.5. Adding missing System 2 columns...")

    # Add missing columns to episodes table
    episode_columns = [
        ("subtitle", "TEXT"),
        ("description", "TEXT"),
        ("processed_at", "TIMESTAMP"),
    ]

    try:
        result = session.execute(text("PRAGMA table_info(episodes)"))
        existing_cols = [row[1] for row in result]

        for col_name, col_type in episode_columns:
            if col_name not in existing_cols:
                session.execute(
                    text(f"ALTER TABLE episodes ADD COLUMN {col_name} {col_type}")
                )
                print(f"   ✓ Added {col_name} to episodes")
            else:
                print(f"   - {col_name} already exists in episodes")
        session.commit()
    except Exception as e:
        print(f"   - Error updating episodes table: {str(e)}")

    # Add missing columns to claims table
    claim_columns = [
        ("original_text", "TEXT"),
        ("evaluator_notes", "TEXT"),
        ("upload_timestamp", "TIMESTAMP"),
        ("upload_error", "TEXT"),
        ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ("domain", "TEXT"),  # Broad field classification
    ]

    try:
        result = session.execute(text("PRAGMA table_info(claims)"))
        existing_cols = [row[1] for row in result]

        for col_name, col_type in claim_columns:
            if col_name not in existing_cols:
                session.execute(
                    text(f"ALTER TABLE claims ADD COLUMN {col_name} {col_type}")
                )
                print(f"   ✓ Added {col_name} to claims")
            else:
                print(f"   - {col_name} already exists in claims")
        session.commit()
    except Exception as e:
        print(f"   - Error updating claims table: {str(e)}")

    # 3. Create new System 2 tables
    print("3. Creating System 2 tables...")

    # Get connection from session
    conn = session.connection()

    # Check which tables already exist
    existing_tables = (
        session.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        .scalars()
        .all()
    )

    new_tables = ["job", "job_run", "llm_request", "llm_response"]

    for table in new_tables:
        if table not in existing_tables:
            print(f"   Creating {table} table...")
        else:
            print(f"   - {table} table already exists")

    # Create tables using SQLAlchemy metadata
    # This will only create tables that don't exist
    from ..system2_models import Job, JobRun, LLMRequest, LLMResponse

    Job.metadata.create_all(bind=conn)
    JobRun.metadata.create_all(bind=conn)
    LLMRequest.metadata.create_all(bind=conn)
    LLMResponse.metadata.create_all(bind=conn)

    session.commit()
    print("   ✓ System 2 tables created")

    # 4. Create indexes for performance
    print("4. Creating indexes...")

    indexes = [
        ("idx_job_type_status", "job", "job_type, created_at"),
        ("idx_job_run_status", "job_run", "job_id, status"),
        ("idx_llm_request_job", "llm_request", "job_run_id"),
        ("idx_claims_updated", "claims", "updated_at"),
        ("idx_episodes_updated", "episodes", "updated_at"),
    ]

    for idx_name, table, columns in indexes:
        try:
            session.execute(
                text(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({columns})")
            )
            print(f"   ✓ Created index {idx_name}")
        except Exception as e:
            print(f"   - Failed to create index {idx_name}: {str(e)}")

    session.commit()

    print("\nSystem 2 migration completed!")

    # 5. Verify migration
    print("\n5. Verifying migration...")

    # Check all expected tables exist
    final_tables = (
        session.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        .scalars()
        .all()
    )

    set(new_tables + tables_to_update)
    existing = set(final_tables)

    if all(table in existing for table in new_tables):
        print("   ✓ All System 2 tables exist")
    else:
        missing = [t for t in new_tables if t not in existing]
        print(f"   ✗ Missing tables: {missing}")

    return True


if __name__ == "__main__":
    # Standalone execution for manual migration
    import os
    import sys

    sys.path.append(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    )

    from knowledge_system.database.service import DatabaseService

    # Use the standard database service to get the correct path
    db_service = DatabaseService()

    with db_service.get_session() as session:
        migrate_to_system2(session)
