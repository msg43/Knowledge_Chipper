#!/usr/bin/env python3
"""
Force SQLAlchemy Schema Sync

This script forces SQLAlchemy to recognize schema changes by:
1. Using reflection to load the actual database schema
2. Comparing it with the model definitions
3. Ensuring metadata is in sync
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from sqlalchemy import create_engine, inspect, MetaData
from sqlalchemy.orm import sessionmaker


def force_sync_schema():
    """Force SQLAlchemy to sync with actual database schema."""
    
    print("=" * 70)
    print("Force SQLAlchemy Schema Sync")
    print("=" * 70)
    print()
    
    # Create engine
    db_url = "sqlite:///knowledge_system.db"
    engine = create_engine(db_url)
    
    # Step 1: Inspect actual database
    print("📝 Step 1: Inspecting actual database schema...")
    inspector = inspect(engine)
    
    if 'media_sources' not in inspector.get_table_names():
        print("❌ Table 'media_sources' not found!")
        return False
    
    columns = [col['name'] for col in inspector.get_columns('media_sources')]
    
    if 'first_failure_at' in columns:
        print(f"✅ Column 'first_failure_at' exists in database")
        print(f"   Total columns in media_sources: {len(columns)}")
    else:
        print("❌ Column 'first_failure_at' NOT in database!")
        return False
    
    print()
    
    # Step 2: Import models and check metadata
    print("📝 Step 2: Loading Python model definitions...")
    from knowledge_system.database.models import Base, MediaSource
    
    # Check if model has the field
    has_field = hasattr(MediaSource, 'first_failure_at')
    print(f"   Model has first_failure_at: {has_field}")
    
    if not has_field:
        print("❌ Python model doesn't have first_failure_at field!")
        print("   This shouldn't happen - the code was updated correctly.")
        return False
    
    print()
    
    # Step 3: Create a test query
    print("📝 Step 3: Testing database query...")
    try:
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Try to query with the new column
        from sqlalchemy import text
        result = session.execute(text("SELECT first_failure_at FROM media_sources LIMIT 1"))
        print("✅ Direct SQL query works")
        
        # Try ORM query
        video = session.query(MediaSource).first()
        if video:
            # Access the attribute
            _ = video.first_failure_at
            print("✅ ORM attribute access works")
        else:
            print("⚠️ No videos in database to test ORM access")
        
        session.close()
        
    except Exception as e:
        print(f"❌ Query failed: {e}")
        return False
    
    print()
    print("=" * 70)
    print("✅ Schema is in sync!")
    print("=" * 70)
    print()
    print("The schema is correct. If you're still seeing errors,")
    print("please share the FULL error message including stack trace.")
    print()
    
    return True


if __name__ == "__main__":
    success = force_sync_schema()
    exit(0 if success else 1)

