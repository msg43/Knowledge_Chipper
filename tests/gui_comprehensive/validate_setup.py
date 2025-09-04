#!/usr/bin/env python3
"""
Simple validation script for GUI comprehensive testing setup.
Checks if test data files are properly generated and ready for testing.
"""

import sys
from pathlib import Path


def main():
    """Validate the GUI comprehensive testing setup."""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent
    fixtures_dir = project_root / "tests" / "fixtures" / "sample_files"
    
    print("GUI Comprehensive Testing Setup Validation")
    print("=" * 50)
    print(f"Project root: {project_root}")
    print(f"Fixtures directory: {fixtures_dir}")
    print()
    
    # Check if fixtures directory exists
    if not fixtures_dir.exists():
        print("❌ Fixtures directory does not exist")
        print("Run the setup script first:")
        print(f"  cd {script_dir}")
        print("  ./setup_test_data.sh")
        return False
    
    # Check subdirectories
    subdirs = ["audio", "video", "documents"]
    missing_dirs = []
    for subdir in subdirs:
        subdir_path = fixtures_dir / subdir
        if not subdir_path.exists():
            missing_dirs.append(subdir)
    
    if missing_dirs:
        print(f"❌ Missing subdirectories: {', '.join(missing_dirs)}")
        return False
    
    # Check for files in each subdirectory
    required_files = {
        "audio": [
            "short_speech_30s.mp3", "short_speech_30s.aac", 
            "conversation_2min.wav", "music_with_speech.m4a",
            "interview_10min.flac", "podcast_excerpt.ogg",
            "conference_talk_30min.wav"
        ],
        "video": [
            "tutorial_3min.mp4", "interview_5min.webm",
            "webinar_10min.mp4", "conference_talk_15min.mov",
            "full_lecture_45min.mp4"
        ],
        "documents": [
            "meeting_notes.txt", "blog_post.md", 
            "news_article.html", "research_paper.txt",
            "technical_spec.txt", "large_manual_100pages.txt"
        ]
    }
    
    all_files_present = True
    total_files = 0
    found_files = 0
    
    for subdir, files in required_files.items():
        subdir_path = fixtures_dir / subdir
        print(f"\nChecking {subdir} files:")
        
        for filename in files:
            file_path = subdir_path / filename
            total_files += 1
            if file_path.exists():
                found_files += 1
                file_size = file_path.stat().st_size
                print(f"  ✅ {filename} ({file_size:,} bytes)")
            else:
                print(f"  ❌ {filename} (missing)")
                all_files_present = False
    
    print(f"\nFile Summary:")
    print(f"  Total expected: {total_files}")
    print(f"  Found: {found_files}")
    print(f"  Missing: {total_files - found_files}")
    
    # Check for additional/optional files
    additional_files = []
    for subdir in subdirs:
        subdir_path = fixtures_dir / subdir
        if subdir_path.exists():
            for file_path in subdir_path.iterdir():
                if file_path.is_file() and file_path.name not in required_files[subdir]:
                    additional_files.append(f"{subdir}/{file_path.name}")
    
    if additional_files:
        print(f"\nAdditional files found:")
        for additional_file in additional_files:
            print(f"  📁 {additional_file}")
    
    # Check setup script
    setup_script = script_dir / "setup_test_data.sh"
    print(f"\nSetup script: {setup_script}")
    if setup_script.exists():
        print("  ✅ setup_test_data.sh found")
        if setup_script.stat().st_mode & 0o111:
            print("  ✅ Script is executable")
        else:
            print("  ⚠️  Script is not executable (run: chmod +x setup_test_data.sh)")
    else:
        print("  ❌ setup_test_data.sh not found")
    
    # Final assessment
    print("\n" + "=" * 50)
    if all_files_present and found_files >= total_files * 0.8:  # Allow for 80% coverage
        print("✅ Setup validation PASSED")
        print("You can now run GUI comprehensive tests:")
        print("  python3 main_test_runner.py smoke")
        print("  python3 main_test_runner.py comprehensive")
        return True
    else:
        print("❌ Setup validation FAILED")
        if found_files < total_files * 0.5:
            print("Most test files are missing. Run the setup script:")
            print(f"  cd {script_dir}")
            print("  ./setup_test_data.sh")
        else:
            print("Some test files are missing, but you may be able to run limited tests.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
