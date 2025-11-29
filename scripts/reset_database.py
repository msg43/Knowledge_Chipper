#!/usr/bin/env python3
"""
Reset database and output directory for clean testing.

This script will:
1. Backup existing database
2. Delete database files
3. Optionally clean output directory
"""

import shutil
from datetime import datetime
from pathlib import Path


def backup_database(db_path: Path) -> Path | None:
    """Create a timestamped backup of the database."""
    if not db_path.exists():
        print(f"⚠️  Database not found: {db_path}")
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.with_suffix(f".backup.{timestamp}")
    
    try:
        shutil.copy2(db_path, backup_path)
        print(f"✅ Backed up database to: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"❌ Failed to backup database: {e}")
        return None


def delete_database(db_path: Path) -> bool:
    """Delete the database file."""
    if not db_path.exists():
        print(f"ℹ️  Database not found (already clean): {db_path}")
        return True
    
    try:
        db_path.unlink()
        print(f"✅ Deleted database: {db_path}")
        return True
    except Exception as e:
        print(f"❌ Failed to delete database: {e}")
        return False


def clean_output_directory(output_dir: Path, keep_structure: bool = True) -> int:
    """
    Clean output directory.
    
    Args:
        output_dir: Output directory path
        keep_structure: If True, keep directory structure but remove files
        
    Returns:
        Number of files deleted
    """
    if not output_dir.exists():
        print(f"ℹ️  Output directory not found: {output_dir}")
        return 0
    
    deleted_count = 0
    
    if keep_structure:
        # Remove only audio files, keep directory structure
        audio_extensions = ["m4a", "opus", "webm", "ogg", "mp3", "aac", "wav"]
        for ext in audio_extensions:
            for audio_file in output_dir.rglob(f"*.{ext}"):
                try:
                    audio_file.unlink()
                    deleted_count += 1
                except Exception as e:
                    print(f"❌ Failed to delete {audio_file}: {e}")
    else:
        # Remove entire directory and recreate
        try:
            shutil.rmtree(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            print(f"✅ Removed and recreated: {output_dir}")
        except Exception as e:
            print(f"❌ Failed to clean output directory: {e}")
            return 0
    
    print(f"✅ Deleted {deleted_count} audio files from output directory")
    return deleted_count


def main():
    """Main reset function."""
    print("=" * 80)
    print("DATABASE RESET SCRIPT")
    print("=" * 80)
    
    project_root = Path(__file__).parent.parent
    
    # Database paths - including the ACTUAL location the app uses!
    app_support_dir = Path.home() / "Library" / "Application Support" / "Knowledge Chipper"
    
    db_paths = [
        app_support_dir / "knowledge_system.db",  # THIS is where the app actually stores it!
        project_root / "data" / "knowledge_system.db",
        project_root / "output" / "knowledge_system.db",
    ]
    
    # Also clean up SQLite WAL files
    wal_files = [
        app_support_dir / "knowledge_system.db-wal",
        app_support_dir / "knowledge_system.db-shm",
    ]
    
    # Output directory
    output_dir = project_root / "output"
    
    # Confirm with user
    print("\n⚠️  WARNING: This will:")
    print("   1. Backup and delete all database files")
    print("   2. Delete all audio files from output directory")
    print("\nDatabases to reset:")
    for db_path in db_paths:
        if db_path.exists():
            print(f"   - {db_path}")
    
    response = input("\n❓ Continue? (yes/no): ").strip().lower()
    if response not in ["yes", "y"]:
        print("❌ Cancelled")
        return
    
    print("\n" + "=" * 80)
    print("BACKING UP DATABASES")
    print("=" * 80)
    
    # Backup databases
    for db_path in db_paths:
        backup_database(db_path)
    
    print("\n" + "=" * 80)
    print("DELETING DATABASES")
    print("=" * 80)
    
    # Delete databases
    for db_path in db_paths:
        delete_database(db_path)
    
    # Delete WAL files (SQLite Write-Ahead Log files)
    for wal_file in wal_files:
        if wal_file.exists():
            try:
                wal_file.unlink()
                print(f"✅ Deleted WAL file: {wal_file}")
            except Exception as e:
                print(f"❌ Failed to delete WAL file {wal_file}: {e}")

    
    print("\n" + "=" * 80)
    print("CLEANING OUTPUT DIRECTORY")
    print("=" * 80)
    
    # Clean output directory
    deleted_count = clean_output_directory(output_dir, keep_structure=True)
    
    print("\n" + "=" * 80)
    print("RESET COMPLETE")
    print("=" * 80)
    print("✅ Database reset successful!")
    print(f"✅ Deleted {deleted_count} audio files")
    print("\n💡 Next: Restart your application to create fresh database")


if __name__ == "__main__":
    main()
