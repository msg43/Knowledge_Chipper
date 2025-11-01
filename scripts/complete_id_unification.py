#!/usr/bin/env python3
"""
Complete ID Unification Script
Handles bulk renaming of video_id/media_id to source_id across the codebase.
"""

import re
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

def replace_in_file(file_path: Path, replacements: list[tuple[str, str]]) -> int:
    """Apply multiple replacements to a file. Returns number of changes made."""
    try:
        content = file_path.read_text(encoding='utf-8')
        original_content = content
        changes = 0
        
        for old, new in replacements:
            if old in content:
                content = content.replace(old, new)
                changes += 1
        
        if content != original_content:
            file_path.write_text(content, encoding='utf-8')
            print(f"✅ Updated {file_path.relative_to(project_root)}: {changes} replacements")
            return changes
        return 0
    except Exception as e:
        print(f"❌ Error updating {file_path}: {e}")
        return 0

def main():
    """Main execution function."""
    print("🚀 Starting ID Unification - Bulk Rename Operations")
    print("=" * 70)
    
    total_changes = 0
    
    # Define file-specific replacements
    files_to_update = {
        # Audio Processor - rename media_id to source_id, update db calls
        "src/knowledge_system/processors/audio_processor.py": [
            ("media_id = ", "source_id = "),
            ("kwargs.get(\"media_id\")", "kwargs.get(\"source_id\")"),
            ("kwargs[\"media_id\"]", "kwargs[\"source_id\"]"),
            ("db_service.get_video(", "db_service.get_source("),
            ("db_service.create_video(", "db_service.create_source("),
            ("db_service.update_video(", "db_service.update_source("),
            ("db_service.get_video_by_file_path(", "db_service.get_source_by_file_path("),
            ("video_metadata", "source_metadata"),
        ],
        
        # YouTube Download Processor
        "src/knowledge_system/processors/youtube_download.py": [
            ("video_id = ", "source_id = "),
            ("db_service.create_video(", "db_service.create_source("),
            ("db_service.get_video(", "db_service.get_source("),
            ("db_service.update_video(", "db_service.update_source("),
        ],
        
        # System2 Orchestrator
        "src/knowledge_system/core/system2_orchestrator.py": [
            ("video_id = ", "source_id = "),
            ("video_id:", "source_id:"),
            ("video_id,", "source_id,"),
            ("db_service.video_exists(", "db_service.source_exists("),
            ("db_service.get_video(", "db_service.get_source("),
            ("db_service.create_video(", "db_service.create_source("),
        ],
        
        # Mining Orchestrator
        "src/knowledge_system/core/system2_orchestrator_mining.py": [
            ("video_id = ", "source_id = "),
            ("db_service.get_video(", "db_service.get_source("),
            ("episode_id.replace(\"episode_\", \"\")", "source_id"),
        ],
        
        # Transcription Tab
        "src/knowledge_system/gui/tabs/transcription_tab.py": [
            ("video_id = ", "source_id = "),
            ("video_record = db_service.get_video(", "source_record = db_service.get_source("),
            ("if video_record:", "if source_record:"),
            ("video_record.", "source_record."),
        ],
        
        # Summarization Tab
        "src/knowledge_system/gui/tabs/summarization_tab.py": [
            ("video_id = ", "source_id = "),
            ("episode_id = f\"episode_{video_id}\"", "# source_id used directly, no episode_ prefix"),
            ("episode_id = Path(file_path).stem", "source_id = Path(file_path).stem"),
        ],
        
        # Process Tab
        "src/knowledge_system/gui/tabs/process_tab.py": [
            ("episode_id = file_obj.stem", "source_id = file_obj.stem"),
            ("input_id=episode_id", "input_id=source_id"),
        ],
        
        # Monitor Tab
        "src/knowledge_system/gui/tabs/monitor_tab.py": [
            ("episode_id = file_path.stem", "source_id = file_path.stem"),
            ("input_id=episode_id", "input_id=source_id"),
        ],
        
        # Speaker Processor
        "src/knowledge_system/processors/speaker_processor.py": [
            ("SELECT episode_id FROM episodes WHERE video_id", "SELECT source_id FROM segments WHERE source_id"),
        ],
    }
    
    # Apply replacements
    for file_path_str, replacements in files_to_update.items():
        file_path = project_root / file_path_str
        if file_path.exists():
            changes = replace_in_file(file_path, replacements)
            total_changes += changes
        else:
            print(f"⚠️  File not found: {file_path_str}")
    
    print("=" * 70)
    print(f"✨ ID Unification Complete: {total_changes} total changes made")
    print("\nNext steps:")
    print("1. Add source_id to transcript YAML (audio_processor.py)")
    print("2. Fix Process Tab ID extraction")
    print("3. Fix document processor deterministic IDs")
    print("4. Run integration tests")
    
    return 0 if total_changes > 0 else 1

if __name__ == "__main__":
    sys.exit(main())

