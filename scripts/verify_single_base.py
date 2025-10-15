#!/usr/bin/env python3
"""
Verify that all expected tables are present in the unified Base.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.knowledge_system.database.models import Base

def verify_unified_base():
    """Verify all tables are present in unified Base."""
    
    # Get all tables from unified Base
    tables = sorted(Base.metadata.tables.keys())
    
    # Expected tables from all four original bases
    expected = [
        # Core models (MainBase)
        'media_sources',
        'transcripts',
        'summaries',
        'moc_extractions',
        'generated_files',
        'processing_jobs',
        'bright_data_sessions',
        'claim_tier_validations',
        'quality_ratings',
        'quality_metrics',
        
        # HCE models (HCEBase)
        'episodes',
        'claims',
        'people',
        'concepts',
        'jargon',
        
        # System2 models (System2Base - already used MainBase)
        'job',
        'job_run',
        'llm_request',
        'llm_response',
        
        # Speaker models (SpeakerBase)
        'speaker_voices',
        'speaker_assignments',
        'speaker_learning_history',
        'speaker_sessions',
        'channel_host_mappings',
        'speaker_processing_sessions',
    ]
    
    expected = sorted(expected)
    
    print("=" * 80)
    print("UNIFIED BASE VERIFICATION")
    print("=" * 80)
    
    # Check for missing tables
    missing = [t for t in expected if t not in tables]
    if missing:
        print(f"\n❌ MISSING TABLES ({len(missing)}):")
        for table in missing:
            print(f"   - {table}")
    else:
        print(f"\n✅ All {len(expected)} expected tables present!")
    
    # Check for unexpected tables
    unexpected = [t for t in tables if t not in expected]
    if unexpected:
        print(f"\n⚠️  UNEXPECTED TABLES ({len(unexpected)}):")
        for table in unexpected:
            print(f"   - {table}")
    
    # List all tables
    print(f"\n📋 ALL TABLES IN UNIFIED BASE ({len(tables)}):")
    for i, table in enumerate(tables, 1):
        status = "✓" if table in expected else "?"
        print(f"   {i:2d}. {status} {table}")
    
    # Verify foreign keys
    print(f"\n🔗 FOREIGN KEY VERIFICATION:")
    fk_count = 0
    for table_name, table in Base.metadata.tables.items():
        fks = list(table.foreign_keys)
        if fks:
            fk_count += len(fks)
            print(f"   {table_name}:")
            for fk in fks:
                print(f"      → {fk.column} references {fk.target_fullname}")
    
    print(f"\n   Total foreign keys: {fk_count}")
    
    # Summary
    print("\n" + "=" * 80)
    if not missing and not unexpected:
        print("✅ VERIFICATION PASSED - Single Base migration successful!")
    elif missing:
        print(f"❌ VERIFICATION FAILED - {len(missing)} tables missing")
    else:
        print(f"⚠️  VERIFICATION WARNING - {len(unexpected)} unexpected tables")
    print("=" * 80)
    
    return len(missing) == 0

if __name__ == "__main__":
    success = verify_unified_base()
    exit(0 if success else 1)

