"""
Tests for file I/O utilities.
"""

import hashlib
import os
import tempfile
from pathlib import Path

import pytest

from knowledge_system.utils.file_io import (
    safe_filename,
    ensure_directory,
    safe_copy,
    get_file_hash,
    get_file_info,
    format_file_size,
    find_files,
    atomic_write,
    overwrite_or_insert_summary_section,
)
from knowledge_system.errors import (
    FileSystemError,
    FileNotFoundError,
    DirectoryError,
)


class TestSafeFilename:
    """Test safe filename generation."""

    def test_basic_filename(self):
        """Test basic filename handling."""
        assert safe_filename("test.txt") == "test.txt"
        assert safe_filename("document.pdf") == "document.pdf"

    def test_problematic_characters(self):
        """Test handling of problematic characters."""
        # Test the specific acceptance criteria case
        assert safe_filename("test:file.mp4") == "test_file.mp4"

        # Test other problematic characters
        assert safe_filename("test<file>.txt") == "test_file_.txt"
        assert safe_filename('test"file".doc') == "test_file_.doc"
        assert safe_filename("test/path\\file.mp4") == "test_path_file.mp4"
        assert safe_filename("test|file?.txt") == "test_file_.txt"
        assert safe_filename("test*file.txt") == "test_file.txt"

    def test_control_characters(self):
        """Test handling of control characters."""
        # Control characters (ASCII 0-31)
        filename_with_ctrl = "test\x00\x01\x1ffile.txt"
        safe = safe_filename(filename_with_ctrl)
        assert safe == "test___file.txt"

    def test_empty_filename(self):
        """Test handling of empty filenames."""
        assert safe_filename("") == "unnamed_file"
        assert safe_filename("   ") == "unnamed"
        assert safe_filename("...") == "unnamed"

    def test_extension_preservation(self):
        """Test extension preservation."""
        assert (
            safe_filename(
    "test:file.mp4",
     preserve_extension=True) == "test_file.mp4"
        )
        assert (
            safe_filename(
    "test:file.mp4",
     preserve_extension=False) == "test_file.mp4"
        )
        assert safe_filename("test:file",
     preserve_extension=True) == "test_file"

    def test_reserved_names(self):
        """Test handling of reserved Windows names."""
        reserved_names = ["CON", "PRN", "AUX", "NUL", "COM1", "LPT1"]
        for name in reserved_names:
            result = safe_filename(name)
            assert result == f"{name}_file"

            # Test case insensitive
            result = safe_filename(name.lower())
            assert result == f"{name.lower()}_file"

    def test_length_truncation(self):
        """Test filename length truncation."""
        long_name = "a" * 300
        result = safe_filename(long_name + ".txt", max_length=255)
        assert len(result) <= 255
        assert result.endswith(".txt")

        # Test without extension
        result = safe_filename(long_name, max_length=100)
        assert len(result) <= 100

    def test_custom_replacement_char(self):
        """Test custom replacement character."""
        assert safe_filename("test:file.txt",
     replacement_char="-") == "test-file.txt"
        assert safe_filename("test<>file.txt",
     replacement_char="X") == "testXXfile.txt"


class TestEnsureDirectory:
    """Test directory creation."""

    def test_create_directory(self):
        """Test creating a new directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            new_dir = Path(temp_dir) / "test_dir"
            assert not new_dir.exists()

            result = ensure_directory(new_dir)
            assert result == new_dir
            assert new_dir.exists()
            assert new_dir.is_dir()

    def test_create_nested_directories(self):
        """Test creating nested directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            nested_dir = Path(temp_dir) / "level1" / "level2" / "level3"
            assert not nested_dir.exists()

            result = ensure_directory(nested_dir)
            assert result == nested_dir
            assert nested_dir.exists()
            assert nested_dir.is_dir()

    def test_existing_directory(self):
        """Test with existing directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            result = ensure_directory(temp_path)
            assert result == temp_path
            assert temp_path.exists()

    def test_string_path(self):
        """Test with string path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            new_dir = os.path.join(temp_dir, "string_dir")

            result = ensure_directory(new_dir)
            assert result == Path(new_dir)
            assert Path(new_dir).exists()


class TestSafeCopy:
    """Test safe file copying."""

    def test_copy_file(self):
        """Test basic file copying."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create source file
            src_file = temp_path / "source.txt"
            src_file.write_text("test content")

            # Copy file
            dst_file = temp_path / "destination.txt"
            result = safe_copy(src_file, dst_file)

            assert result == dst_file
            assert dst_file.exists()
            assert dst_file.read_text() == "test content"

    def test_copy_with_directory_creation(self):
        """Test copying with directory creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create source file
            src_file = temp_path / "source.txt"
            src_file.write_text("test content")

            # Copy to nested destination
            dst_file = temp_path / "subdir" / "destination.txt"
            result = safe_copy(src_file, dst_file, create_dirs=True)

            assert result == dst_file
            assert dst_file.exists()
            assert dst_file.read_text() == "test content"

    def test_copy_nonexistent_source(self):
        """Test copying nonexistent source file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            src_file = temp_path / "nonexistent.txt"
            dst_file = temp_path / "destination.txt"

            with pytest.raises(FileNotFoundError):
                safe_copy(src_file, dst_file)

    def test_copy_existing_destination_no_overwrite(self):
        """Test copying to existing destination without overwrite."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create source and destination files
            src_file = temp_path / "source.txt"
            src_file.write_text("source content")

            dst_file = temp_path / "destination.txt"
            dst_file.write_text("destination content")

            with pytest.raises(FileSystemError):
                safe_copy(src_file, dst_file, overwrite=False)

    def test_copy_existing_destination_with_overwrite(self):
        """Test copying to existing destination with overwrite."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create source and destination files
            src_file = temp_path / "source.txt"
            src_file.write_text("source content")

            dst_file = temp_path / "destination.txt"
            dst_file.write_text("destination content")

            result = safe_copy(src_file, dst_file, overwrite=True)

            assert result == dst_file
            assert dst_file.read_text() == "source content"


class TestGetFileHash:
    """Test file hashing."""

    def test_hash_file(self):
        """Test basic file hashing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test file
            test_file = temp_path / "test.txt"
            content = "test content for hashing"
            test_file.write_text(content)

            # Calculate hash
            file_hash = get_file_hash(test_file, "md5")

            # Verify hash
            expected_hash = hashlib.md5(content.encode()).hexdigest()
            assert file_hash == expected_hash

    def test_different_algorithms(self):
        """Test different hash algorithms."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            test_file = temp_path / "test.txt"
            content = "test content"
            test_file.write_text(content)

            # Test multiple algorithms
            algorithms = ["md5", "sha1", "sha256"]
            for algorithm in algorithms:
                file_hash = get_file_hash(test_file, algorithm)
                expected_hash = hashlib.new(
    algorithm, content.encode()).hexdigest()
                assert file_hash == expected_hash

    def test_hash_nonexistent_file(self):
        """Test hashing nonexistent file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            nonexistent_file = temp_path / "nonexistent.txt"

            with pytest.raises(FileNotFoundError):
                get_file_hash(nonexistent_file)

    def test_invalid_algorithm(self):
        """Test invalid hash algorithm."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            test_file = temp_path / "test.txt"
            test_file.write_text("content")

            with pytest.raises(FileSystemError):
                get_file_hash(test_file, "invalid_algorithm")


class TestGetFileInfo:
    """Test file information retrieval."""

    def test_file_info(self):
        """Test getting file information."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test file
            test_file = temp_path / "test.txt"
            content = "test content"
            test_file.write_text(content)

            info = get_file_info(test_file)

            # Check basic properties
            assert info["name"] == "test.txt"
            assert info["stem"] == "test"
            assert info["suffix"] == ".txt"
            assert info["size_bytes"] == len(content)
            assert info["is_file"] is True
            assert info["is_dir"] is False
            assert "md5" in info  # Should include hash for small files

    def test_directory_info(self):
        """Test getting directory information."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            info = get_file_info(temp_path)

            assert info["is_file"] is False
            assert info["is_dir"] is True
            assert "md5" not in info or info["md5"] is None

    def test_nonexistent_file_info(self):
        """Test getting info for nonexistent file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            nonexistent_file = temp_path / "nonexistent.txt"

            with pytest.raises(FileNotFoundError):
                get_file_info(nonexistent_file)


class TestFormatFileSize:
    """Test file size formatting."""

    def test_bytes(self):
        """Test byte formatting."""
        assert format_file_size(0) == "0 B"
        assert format_file_size(1) == "1.0 B"
        assert format_file_size(512) == "512.0 B"

    def test_kilobytes(self):
        """Test kilobyte formatting."""
        assert format_file_size(1024) == "1.0 KB"
        assert format_file_size(1536) == "1.5 KB"

    def test_megabytes(self):
        """Test megabyte formatting."""
        assert format_file_size(1024 * 1024) == "1.0 MB"
        assert format_file_size(int(1.5 * 1024 * 1024)) == "1.5 MB"

    def test_gigabytes(self):
        """Test gigabyte formatting."""
        assert format_file_size(1024 * 1024 * 1024) == "1.0 GB"

    def test_large_sizes(self):
        """Test very large file sizes."""
        tb_size = 1024 * 1024 * 1024 * 1024
        assert format_file_size(tb_size) == "1.0 TB"


class TestFindFiles:
    """Test file finding functionality."""

    def test_find_files_basic(self):
        """Test basic file finding."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test files
            (temp_path / "file1.txt").write_text("content1")
            (temp_path / "file2.txt").write_text("content2")
            (temp_path / "file3.log").write_text("content3")

            # Find all files
            files = find_files(temp_path, "*", recursive=False)
            assert len(files) == 3

            # Find txt files
            txt_files = find_files(temp_path, "*.txt", recursive=False)
            assert len(txt_files) == 2

    def test_find_files_recursive(self):
        """Test recursive file finding."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create nested structure
            (temp_path / "file1.txt").write_text("content")
            subdir = temp_path / "subdir"
            subdir.mkdir()
            (subdir / "file2.txt").write_text("content")

            # Non-recursive
            files = find_files(temp_path, "*.txt", recursive=False)
            assert len(files) == 1

            # Recursive
            files = find_files(temp_path, "*.txt", recursive=True)
            assert len(files) == 2

    def test_find_nonexistent_directory(self):
        """Test finding files in nonexistent directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            nonexistent_dir = temp_path / "nonexistent"

            with pytest.raises(DirectoryError):
                find_files(nonexistent_dir)


class TestAtomicWrite:
    """Test atomic file writing."""

    def test_atomic_write_string(self):
        """Test atomic writing of string content."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            target_file = temp_path / "test.txt"
            content = "test content"

            result = atomic_write(target_file, content)

            assert result == target_file
            assert target_file.exists()
            assert target_file.read_text() == content

    def test_atomic_write_bytes(self):
        """Test atomic writing of bytes content."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            target_file = temp_path / "test.bin"
            content = b"binary content"

            result = atomic_write(target_file, content)

            assert result == target_file
            assert target_file.exists()
            assert target_file.read_bytes() == content

    def test_atomic_write_with_directory_creation(self):
        """Test atomic writing with directory creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            target_file = temp_path / "subdir" / "test.txt"
            content = "test content"

            result = atomic_write(target_file, content, create_dirs=True)

            assert result == target_file
            assert target_file.exists()
            assert target_file.read_text() == content


class TestIntegration:
    """Integration tests for file utilities."""

    def test_safe_filename_acceptance_criteria(self):
        """Test the specific acceptance criteria."""
        # This is the exact test case from the acceptance criteria
        result = safe_filename("test:file.mp4")
        assert result == "test_file.mp4"

        # Test that the result is a valid filename (no problematic characters)
        problematic_chars = r'<>:"/\|?*'
        for char in problematic_chars:
            assert char not in result

    def test_complete_workflow(self):
        """Test complete file operations workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Test safe filename generation
            unsafe_name = "test:file?.txt"
            safe_name = safe_filename(unsafe_name)
            assert safe_name == "test_file_.txt"

            # Create file with safe name
            original = temp_path / safe_name
            original.write_text("original content")

            # Copy file
            copy = temp_path / "copy.txt"
            safe_copy(original, copy)

            # Verify operations
            assert copy.read_text() == "original content"

            # Get file info
            info = get_file_info(copy)
            assert info["name"] == "copy.txt"
            assert info["is_file"] is True


def test_overwrite_or_insert_summary_section_overwrite(tmp_path):
    """Test overwriting an existing ## Summary section."""
    md_content = """# Test Document

## Metadata
- Title: Test Video
- URL: https://example.com

## Full Transcript
This is the transcript content.

## Summary
Old summary content.

## Notes
Some notes here.
"""
    md_file = tmp_path / "test.md"
    md_file.write_text(md_content)

    new_summary = "This is the new summary content."
    overwrite_or_insert_summary_section(md_file, new_summary)

    updated_content = md_file.read_text()
    assert "## Summary" in updated_content
    assert new_summary in updated_content
    assert "Old summary content" not in updated_content
    assert "## Notes" in updated_content  # Other sections preserved


def test_overwrite_or_insert_summary_section_insert_after_transcript(tmp_path):
    """Test inserting a ## Summary section after ## Full Transcript."""
    md_content = """# Test Document

## Metadata
- Title: Test Video

## Full Transcript
This is the transcript content.

## Notes
Some notes here.
"""
    md_file = tmp_path / "test.md"
    md_file.write_text(md_content)

    new_summary = "This is the new summary content."
    overwrite_or_insert_summary_section(md_file, new_summary)

    updated_content = md_file.read_text()
    lines = updated_content.split("\n")

    # Find positions of sections
    transcript_pos = None
    summary_pos = None
    notes_pos = None

    for i, line in enumerate(lines):
        if line.strip() == "## Metadata":
            pass
        elif line.strip() == "## Full Transcript":
            transcript_pos = i
        elif line.strip() == "## Summary":
            summary_pos = i
        elif line.strip() == "## Notes":
            notes_pos = i

    # Summary should be inserted after transcript but before notes
    assert summary_pos is not None
    assert transcript_pos is not None
    assert notes_pos is not None
    assert transcript_pos < summary_pos < notes_pos
    assert new_summary in updated_content


def test_overwrite_or_insert_summary_section_insert_at_end(tmp_path):
    """Test inserting a ## Summary section at the end when no transcript section exists."""
    md_content = """# Test Document

## Metadata
- Title: Test Video

## Notes
Some notes here.
"""
    md_file = tmp_path / "test.md"
    md_file.write_text(md_content)

    new_summary = "This is the new summary content."
    overwrite_or_insert_summary_section(md_file, new_summary)

    updated_content = md_file.read_text()
    lines = updated_content.split("\n")

    # Summary should be at the end
    assert lines[-2].strip() == new_summary
    assert "## Summary" in updated_content


def test_overwrite_or_insert_summary_section_empty_file(tmp_path):
    """Test inserting a ## Summary section in an empty file."""
    md_file = tmp_path / "empty.md"
    md_file.write_text("")

    new_summary = "This is the new summary content."
    overwrite_or_insert_summary_section(md_file, new_summary)

    updated_content = md_file.read_text()
    assert "## Summary" in updated_content
    assert new_summary in updated_content


def test_overwrite_or_insert_summary_section_preserves_content(tmp_path):
    """Test that other content is preserved when overwriting summary."""
    md_content = """# Test Document

## Metadata
- Title: Test Video
- Author: Test Author

## Full Transcript
This is the transcript content.
It has multiple lines.

## Summary
Old summary content.

## Notes
Some notes here.
More notes.
"""
    md_file = tmp_path / "test.md"
    md_file.write_text(md_content)

    new_summary = "This is the new summary content."
    overwrite_or_insert_summary_section(md_file, new_summary)

    updated_content = md_file.read_text()

    # Check that other sections are preserved
    assert "## Metadata" in updated_content
    assert "## Full Transcript" in updated_content
    assert "## Notes" in updated_content
    assert "Test Video" in updated_content
    assert "Test Author" in updated_content
    assert "This is the transcript content" in updated_content
    assert "Some notes here" in updated_content

    # Check that old summary is replaced
    assert "Old summary content" not in updated_content
    assert new_summary in updated_content
