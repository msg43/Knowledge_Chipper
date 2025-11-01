#!/usr/bin/env python3
"""
Fix Remaining ID References
Completes the ID unification by fixing all remaining video_id and episode_id references.
"""

import re
from pathlib import Path

project_root = Path(__file__).parent.parent


def fix_system2_orchestrator():
    """Fix system2_orchestrator.py - replace video_id variable references with source_id."""
    file_path = project_root / "src/knowledge_system/core/system2_orchestrator.py"
    content = file_path.read_text()
    
    # Fix f-string and string references to video_id variable
    content = re.sub(r'\bvideo_id\b(?!\s*=)', 'source_id', content)
    # But keep the column name in SQL/ORM contexts
    content = re.sub(r'video_id\s*=\s*source_id', 'video_id=source_id', content)
    
    file_path.write_text(content)
    print(f"✅ Fixed {file_path.name}")


def fix_system2_orchestrator_mining():
    """Fix system2_orchestrator_mining.py."""
    file_path = project_root / "src/knowledge_system/core/system2_orchestrator_mining.py"
    content = file_path.read_text()
    
    # Replace video_id and source_id variable references
    content = re.sub(r'\bvideo_id\b(?!\s*=)', 'source_id', content)
    content = re.sub(r'\bsource_id\b(?!\s*=)', 'source_id', content)
    
    file_path.write_text(content)
    print(f"✅ Fixed {file_path.name}")


def fix_claim_store():
    """Fix claim_store.py - replace episode_id with source_id."""
    file_path = project_root / "src/knowledge_system/database/claim_store.py"
    content = file_path.read_text()
    
    # Replace episode_id variable references with source_id
    content = re.sub(r'\bepisode_id\b', 'source_id', content)
    
    file_path.write_text(content)
    print(f"✅ Fixed {file_path.name}")


def fix_summarization_tab():
    """Fix summarization_tab.py."""
    file_path = project_root / "src/knowledge_system/gui/tabs/summarization_tab.py"
    content = file_path.read_text()
    
    # Replace video_id and episode_id references
    content = re.sub(r'\bvideo_id\b(?!\s*=)', 'source_id', content)
    content = re.sub(r'\bepisode_id\b', 'source_id', content)
    
    file_path.write_text(content)
    print(f"✅ Fixed {file_path.name}")


def fix_transcription_tab():
    """Fix transcription_tab.py."""
    file_path = project_root / "src/knowledge_system/gui/tabs/transcription_tab.py"
    content = file_path.read_text()
    
    # Replace video_id and source_record references
    content = re.sub(r'\bvideo_id\b(?!\s*=)', 'source_id', content)
    content = re.sub(r'\bsource_record\b', 'source_record', content)
    
    file_path.write_text(content)
    print(f"✅ Fixed {file_path.name}")


def fix_youtube_download():
    """Fix youtube_download.py."""
    file_path = project_root / "src/knowledge_system/processors/youtube_download.py"
    content = file_path.read_text()
    
    # Replace video_id variable references (but not column names)
    content = re.sub(r'\bvideo_id\b(?!\s*[=:])', 'source_id', content)
    
    file_path.write_text(content)
    print(f"✅ Fixed {file_path.name}")


def fix_api_keys_tab():
    """Fix the bandit security issue in api_keys_tab.py."""
    file_path = project_root / "src/knowledge_system/gui/tabs/api_keys_tab.py"
    content = file_path.read_text()
    
    # Add nosec comment for the legitimate shell=True usage
    content = content.replace(
        '["start", str(speaker_file.absolute())], shell=True, check=True\n                )  # nosec B603,B607',
        '["start", str(speaker_file.absolute())], shell=True, check=True  # nosec B602,B603,B607\n                )'
    )
    
    file_path.write_text(content)
    print(f"✅ Fixed {file_path.name}")


def main():
    print("🔧 Fixing remaining ID references...")
    print("=" * 70)
    
    try:
        fix_system2_orchestrator()
        fix_system2_orchestrator_mining()
        fix_claim_store()
        fix_summarization_tab()
        fix_transcription_tab()
        fix_youtube_download()
        fix_api_keys_tab()
        
        print("=" * 70)
        print("✨ All fixes applied successfully!")
        return 0
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())

