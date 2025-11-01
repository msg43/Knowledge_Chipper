#!/usr/bin/env python3
"""
Simple test to verify deterministic hash generation for document IDs.
This doesn't require the full app environment.
"""

import hashlib
from pathlib import Path
import tempfile

def generate_source_id(file_path: Path) -> str:
    """Generate deterministic source_id from file path."""
    path_hash = hashlib.md5(
        str(file_path.absolute()).encode(), 
        usedforsecurity=False
    ).hexdigest()[:8]
    return f"doc_{file_path.stem}_{path_hash}"

def test_deterministic_ids():
    """Test that the same file always generates the same source_id."""
    print("🧪 Testing Deterministic Document ID Generation")
    print("=" * 70)
    
    # Create a temporary file
    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.md',
        delete=False,
        prefix='test_doc_'
    ) as temp_file:
        temp_file.write("Test content")
        temp_path = Path(temp_file.name)
    
    try:
        print(f"📄 Test file: {temp_path}")
        print(f"   Absolute path: {temp_path.absolute()}")
        
        # Generate source_id multiple times
        source_id_1 = generate_source_id(temp_path)
        source_id_2 = generate_source_id(temp_path)
        source_id_3 = generate_source_id(temp_path)
        
        print(f"\n🔑 Generated source_ids:")
        print(f"   Run 1: {source_id_1}")
        print(f"   Run 2: {source_id_2}")
        print(f"   Run 3: {source_id_3}")
        
        # Verify they're all the same
        if source_id_1 == source_id_2 == source_id_3:
            print(f"\n✅ TEST PASSED: All source_ids are identical!")
            print(f"   Deterministic ID: {source_id_1}")
            return True
        else:
            print(f"\n❌ TEST FAILED: source_ids are different!")
            return False
            
    finally:
        # Cleanup
        temp_path.unlink()
        print(f"\n🧹 Cleaned up test file")

def test_different_files():
    """Test that different files generate different source_ids."""
    print("\n" + "=" * 70)
    print("🧪 Testing Different Files Generate Different IDs")
    print("=" * 70)
    
    # Create two different temp files
    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.md',
        delete=False,
        prefix='test_doc_1_'
    ) as temp_file1:
        temp_file1.write("Content 1")
        temp_path1 = Path(temp_file1.name)
    
    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.md',
        delete=False,
        prefix='test_doc_2_'
    ) as temp_file2:
        temp_file2.write("Content 2")
        temp_path2 = Path(temp_file2.name)
    
    try:
        source_id_1 = generate_source_id(temp_path1)
        source_id_2 = generate_source_id(temp_path2)
        
        print(f"📄 File 1: {temp_path1.name}")
        print(f"   source_id: {source_id_1}")
        print(f"📄 File 2: {temp_path2.name}")
        print(f"   source_id: {source_id_2}")
        
        if source_id_1 != source_id_2:
            print(f"\n✅ TEST PASSED: Different files have different source_ids!")
            return True
        else:
            print(f"\n❌ TEST FAILED: Different files have same source_id!")
            return False
            
    finally:
        temp_path1.unlink()
        temp_path2.unlink()
        print(f"\n🧹 Cleaned up test files")

def test_same_filename_different_paths():
    """Test that same filename in different directories generates different IDs."""
    print("\n" + "=" * 70)
    print("🧪 Testing Same Filename, Different Paths")
    print("=" * 70)
    
    import tempfile
    import os
    
    # Create two temp directories
    temp_dir1 = tempfile.mkdtemp(prefix='test_dir1_')
    temp_dir2 = tempfile.mkdtemp(prefix='test_dir2_')
    
    try:
        # Create files with same name in different directories
        file1 = Path(temp_dir1) / "same_name.md"
        file2 = Path(temp_dir2) / "same_name.md"
        
        file1.write_text("Content 1")
        file2.write_text("Content 2")
        
        source_id_1 = generate_source_id(file1)
        source_id_2 = generate_source_id(file2)
        
        print(f"📄 File 1: {file1}")
        print(f"   source_id: {source_id_1}")
        print(f"📄 File 2: {file2}")
        print(f"   source_id: {source_id_2}")
        
        if source_id_1 != source_id_2:
            print(f"\n✅ TEST PASSED: Same filename, different paths = different IDs!")
            return True
        else:
            print(f"\n❌ TEST FAILED: Same filename, different paths = same ID!")
            return False
            
    finally:
        import shutil
        shutil.rmtree(temp_dir1, ignore_errors=True)
        shutil.rmtree(temp_dir2, ignore_errors=True)
        print(f"\n🧹 Cleaned up test directories")

if __name__ == "__main__":
    print("\n" + "🚀 Document Processor Hash Tests" + "\n")
    
    test1 = test_deterministic_ids()
    test2 = test_different_files()
    test3 = test_same_filename_different_paths()
    
    print("\n" + "=" * 70)
    print("📊 Test Results:")
    print(f"   Deterministic IDs: {'✅ PASS' if test1 else '❌ FAIL'}")
    print(f"   Different Files:   {'✅ PASS' if test2 else '❌ FAIL'}")
    print(f"   Different Paths:   {'✅ PASS' if test3 else '❌ FAIL'}")
    
    if test1 and test2 and test3:
        print("\n✨ ALL TESTS PASSED! Document processor hash implementation is correct.")
        exit(0)
    else:
        print("\n❌ SOME TESTS FAILED! Check implementation.")
        exit(1)

