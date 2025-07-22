"""
File I/O utilities for Knowledge System.
Provides safe file operations, naming conventions, and error handling.
"""

import hashlib
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Union

from ..errors import (
    FileSystemError,
    FileNotFoundError,
    FilePermissionError,
    DirectoryError,
)
from ..logger import get_logger

logger = get_logger(__name__)


def safe_filename(
    filename: str,
    max_length: int = 255,
    replacement_char: str = "_",
    preserve_extension: bool = True,
) -> str:
    """
    Create a safe filename by removing or replacing problematic characters.

    Args:
        filename: Original filename
        max_length: Maximum filename length
        replacement_char: Character to replace problematic characters with
        preserve_extension: Whether to preserve the file extension

    Returns:
        Safe filename string
    """
    if not filename:
        return "unnamed_file"

    # Split extension if preserving
    if preserve_extension and "." in filename and filename.strip("."):
        # Normal case: filename has content beyond dots
        name_part, ext_part = filename.rsplit(".", 1)
        ext_part = f".{ext_part}"
    else:
        # Special case: filename is all dots or no extension
        name_part = filename
        ext_part = ""

    # Characters that are problematic in filenames
    problematic_chars = r'<>:"/\|?*'
    control_chars = "".join(chr(i) for i in range(32))

    # Replace problematic characters
    safe_name = name_part
    for char in problematic_chars + control_chars:
        safe_name = safe_name.replace(char, replacement_char)

    # Remove leading/trailing whitespace and dots
    safe_name = safe_name.strip(". ")

    # Handle empty name
    if not safe_name:
        safe_name = "unnamed"

    # Avoid reserved Windows names
    reserved_names = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    }

    if safe_name.upper() in reserved_names:
        safe_name = f"{safe_name}_file"

    # Truncate if necessary, considering extension
    if ext_part:
        max_name_length = max_length - len(ext_part)
        if len(safe_name) > max_name_length:
            safe_name = safe_name[:max_name_length].rstrip(". ")
    else:
        if len(safe_name) > max_length:
            safe_name = safe_name[:max_length].rstrip(". ")

    # Final check for empty name after all processing
    if not safe_name:
        safe_name = "unnamed"

    return safe_name + ext_part


def ensure_directory(path: Union[str, Path]) -> Path:
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        path: Directory path to create

    Returns:
        Path object for the directory

    Raises:
        DirectoryError: If directory cannot be created
    """
    path = Path(path)

    try:
        path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Directory ensured: {path}")
        return path
    except PermissionError as e:
        raise DirectoryError(
            f"Permission denied creating directory: {path}",
            context={"path": str(path), "error": str(e)},
            cause=e,
        )
    except OSError as e:
        raise DirectoryError(
            f"Failed to create directory: {path}",
            context={"path": str(path), "error": str(e)},
            cause=e,
        )


def safe_copy(
    src: Union[str, Path],
    dst: Union[str, Path],
    overwrite: bool = False,
    create_dirs: bool = True,
) -> Path:
    """
    Safely copy a file with error handling and validation.

    Args:
        src: Source file path
        dst: Destination file path
        overwrite: Whether to overwrite existing files
        create_dirs: Whether to create destination directories

    Returns:
        Path to the copied file

    Raises:
        FileNotFoundError: If source file doesn't exist
        FilePermissionError: If permission denied
        FileSystemError: For other file operation errors
    """
    src_path = Path(src)
    dst_path = Path(dst)

    # Validate source file
    if not src_path.exists():
        raise FileNotFoundError(
            f"Source file not found: {src_path}", context={"source": str(src_path)}
        )

    if not src_path.is_file():
        raise FileSystemError(
            f"Source is not a file: {src_path}",
            context={"source": str(src_path), "type": "not_file"},
        )

    # Check destination
    if dst_path.exists() and not overwrite:
        raise FileSystemError(
            f"Destination file already exists: {dst_path}",
            context={"destination": str(dst_path), "overwrite": overwrite},
        )

    # Create destination directory if needed
    if create_dirs:
        ensure_directory(dst_path.parent)

    try:
        shutil.copy2(src_path, dst_path)
        logger.debug(f"File copied: {src_path} -> {dst_path}")
        return dst_path
    except PermissionError as e:
        raise FilePermissionError(
            f"Permission denied copying file: {src_path} -> {dst_path}",
            context={"source": str(src_path), "destination": str(dst_path)},
            cause=e,
        )
    except OSError as e:
        raise FileSystemError(
            f"Failed to copy file: {src_path} -> {dst_path}",
            context={"source": str(src_path), "destination": str(dst_path)},
            cause=e,
        )


def safe_move(
    src: Union[str, Path],
    dst: Union[str, Path],
    overwrite: bool = False,
    create_dirs: bool = True,
) -> Path:
    """
    Safely move a file with error handling and validation.

    Args:
        src: Source file path
        dst: Destination file path
        overwrite: Whether to overwrite existing files
        create_dirs: Whether to create destination directories

    Returns:
        Path to the moved file

    Raises:
        FileNotFoundError: If source file doesn't exist
        FilePermissionError: If permission denied
        FileSystemError: For other file operation errors
    """
    src_path = Path(src)
    dst_path = Path(dst)

    # Validate source file
    if not src_path.exists():
        raise FileNotFoundError(
            f"Source file not found: {src_path}", context={"source": str(src_path)}
        )

    # Check destination
    if dst_path.exists() and not overwrite:
        raise FileSystemError(
            f"Destination file already exists: {dst_path}",
            context={"destination": str(dst_path), "overwrite": overwrite},
        )

    # Create destination directory if needed
    if create_dirs:
        ensure_directory(dst_path.parent)

    try:
        shutil.move(str(src_path), str(dst_path))
        logger.debug(f"File moved: {src_path} -> {dst_path}")
        return dst_path
    except PermissionError as e:
        raise FilePermissionError(
            f"Permission denied moving file: {src_path} -> {dst_path}",
            context={"source": str(src_path), "destination": str(dst_path)},
            cause=e,
        )
    except OSError as e:
        raise FileSystemError(
            f"Failed to move file: {src_path} -> {dst_path}",
            context={"source": str(src_path), "destination": str(dst_path)},
            cause=e,
        )


def safe_delete(path: Union[str, Path], missing_ok: bool = True) -> bool:
    """
    Safely delete a file or directory.

    Args:
        path: Path to delete
        missing_ok: Whether to ignore missing files

    Returns:
        True if file was deleted, False if it didn't exist and missing_ok=True

    Raises:
        FileNotFoundError: If file doesn't exist and missing_ok=False
        FilePermissionError: If permission denied
        FileSystemError: For other file operation errors
    """
    path = Path(path)

    if not path.exists():
        if missing_ok:
            return False
        else:
            raise FileNotFoundError(
                f"Path not found: {path}", context={"path": str(path)}
            )

    try:
        if path.is_file():
            path.unlink()
            logger.debug(f"File deleted: {path}")
        elif path.is_dir():
            shutil.rmtree(path)
            logger.debug(f"Directory deleted: {path}")
        else:
            raise FileSystemError(
                f"Path is neither file nor directory: {path}",
                context={"path": str(path)},
            )
        return True
    except PermissionError as e:
        raise FilePermissionError(
            f"Permission denied deleting: {path}", context={"path": str(path)}, cause=e
        )
    except OSError as e:
        raise FileSystemError(
            f"Failed to delete: {path}", context={"path": str(path)}, cause=e
        )


def get_file_hash(
    path: Union[str, Path],
    algorithm: str = "md5",
    chunk_size: int = 8192,
) -> str:
    """
    Calculate hash of a file.

    Args:
        path: File path
        algorithm: Hash algorithm (md5, sha1, sha256, etc.)
        chunk_size: Size of chunks to read

    Returns:
        Hex digest of the file hash

    Raises:
        FileNotFoundError: If file doesn't exist
        FileSystemError: For other file operation errors
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
    f"File not found: {path}", context={
        "path": str(path)})

    try:
        hasher = hashlib.new(algorithm)
        with open(path, "rb") as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()
    except ValueError as e:
        raise FileSystemError(
            f"Invalid hash algorithm: {algorithm}",
            context={"algorithm": algorithm, "path": str(path)},
            cause=e,
        )
    except OSError as e:
        raise FileSystemError(
            f"Failed to read file for hashing: {path}",
            context={"path": str(path), "algorithm": algorithm},
            cause=e,
        )


def get_file_info(path: Union[str, Path]) -> Dict[str, Any]:
    """
    Get comprehensive information about a file.

    Args:
        path: File path

    Returns:
        Dictionary with file information

    Raises:
        FileNotFoundError: If file doesn't exist
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
    f"File not found: {path}", context={
        "path": str(path)})

    try:
        stat = path.stat()

        info = {
            "path": str(path),
            "absolute_path": str(path.absolute()),
            "name": path.name,
            "stem": path.stem,
            "suffix": path.suffix,
            "parent": str(path.parent),
            "size_bytes": stat.st_size,
            "size_human": format_file_size(stat.st_size),
            "created": stat.st_ctime,
            "modified": stat.st_mtime,
            "accessed": stat.st_atime,
            "is_file": path.is_file(),
            "is_dir": path.is_dir(),
            "is_symlink": path.is_symlink(),
            "permissions": oct(stat.st_mode)[-3:],
        }

        # Add hash for small files
        if path.is_file() and stat.st_size < 10 * 1024 * 1024:  # < 10MB
            try:
                info["md5"] = get_file_hash(path, "md5")
            except Exception:
                info["md5"] = None

        return info
    except OSError as e:
        raise FileSystemError(
            f"Failed to get file info: {path}", context={"path": str(path)}, cause=e
        )


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted size string
    """
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB", "PB"]
    i = 0
    size = float(size_bytes)

    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1

    return f"{size:.1f} {size_names[i]}"


def find_files(
    directory: Union[str, Path],
    pattern: str = "*",
    recursive: bool = True,
    include_dirs: bool = False,
) -> List[Path]:
    """
    Find files matching a pattern.

    Args:
        directory: Directory to search
        pattern: Glob pattern to match
        recursive: Whether to search recursively
        include_dirs: Whether to include directories in results

    Returns:
        List of matching paths

    Raises:
        DirectoryError: If directory doesn't exist or can't be accessed
    """
    directory = Path(directory)

    if not directory.exists():
        raise DirectoryError(
            f"Directory not found: {directory}", context={"directory": str(directory)}
        )

    if not directory.is_dir():
        raise DirectoryError(
            f"Path is not a directory: {directory}",
            context={"directory": str(directory)},
        )

    try:
        if recursive:
            matches = list(directory.rglob(pattern))
        else:
            matches = list(directory.glob(pattern))

        if not include_dirs:
            matches = [p for p in matches if p.is_file()]

        return sorted(matches)
    except OSError as e:
        raise DirectoryError(
            f"Failed to search directory: {directory}",
            context={"directory": str(directory), "pattern": pattern},
            cause=e,
        )


def atomic_write(
    path: Union[str, Path],
    content: Union[str, bytes],
    encoding: str = "utf-8",
    create_dirs: bool = True,
) -> Path:
    """
    Atomically write content to a file.

    Args:
        path: Target file path
        content: Content to write
        encoding: Text encoding (for string content)
        create_dirs: Whether to create parent directories

    Returns:
        Path to the written file

    Raises:
        FileSystemError: If write operation fails
    """
    path = Path(path)

    if create_dirs:
        ensure_directory(path.parent)

    # Write to temporary file first
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb" if isinstance(content, bytes) else "w",
            dir=path.parent,
            delete=False,
            encoding=encoding if isinstance(content, str) else None,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(content)
            temp_file.flush()
            os.fsync(temp_file.fileno())

        # Atomic move to final location
        temp_path.replace(path)
        logger.debug(f"File written atomically: {path}")
        return path
    except Exception as e:
        # Clean up temporary file on error
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass

        raise FileSystemError(
            f"Failed to write file atomically: {path}",
            context={
    "path": str(path),
     "content_type": type(content).__name__},
            cause=e,
        )


def backup_file(
    path: Union[str, Path],
    backup_dir: Optional[Union[str, Path]] = None,
    max_backups: int = 5,
) -> Optional[Path]:
    """
    Create a backup of a file.

    Args:
        path: File to backup
        backup_dir: Directory for backups (default: same as original file)
        max_backups: Maximum number of backups to keep

    Returns:
        Path to the backup file, or None if file doesn't exist

    Raises:
        FileSystemError: If backup operation fails
    """
    path = Path(path)

    if not path.exists():
        return None

    if backup_dir:
        backup_dir = Path(backup_dir)
        ensure_directory(backup_dir)
    else:
        backup_dir = path.parent

    # Generate backup filename
    timestamp = int(path.stat().st_mtime)
    backup_name = f"{path.stem}.backup.{timestamp}{path.suffix}"
    backup_path = backup_dir / backup_name

    # Copy file to backup location
    safe_copy(path, backup_path, overwrite=False)

    # Clean up old backups
    cleanup_old_backups(backup_dir, path.name, max_backups)

    logger.info(f"File backed up: {path} -> {backup_path}")
    return backup_path


def cleanup_old_backups(
    backup_dir: Path,
    original_name: str,
    max_backups: int,
) -> None:
    """Clean up old backup files, keeping only the most recent ones."""
    pattern = f"{Path(original_name).stem}.backup.*{Path(original_name).suffix}"
    backups = find_files(backup_dir, pattern, recursive=False)

    if len(backups) > max_backups:
        # Sort by modification time and delete oldest
        backups.sort(key=lambda p: p.stat().st_mtime)
        for old_backup in backups[:-max_backups]:
            safe_delete(old_backup)
            logger.debug(f"Old backup deleted: {old_backup}")


def read_file_chunks(
    path: Union[str, Path],
    chunk_size: int = 8192,
) -> Generator[bytes, None, None]:
    """
    Read a file in chunks for memory-efficient processing.

    Args:
        path: File path
        chunk_size: Size of each chunk

    Yields:
        File chunks as bytes

    Raises:
        FileNotFoundError: If file doesn't exist
        FileSystemError: For read errors
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
    f"File not found: {path}", context={
        "path": str(path)})

    try:
        with open(path, "rb") as f:
            while chunk := f.read(chunk_size):
                yield chunk
    except OSError as e:
        raise FileSystemError(
            f"Failed to read file: {path}",
            context={"path": str(path), "chunk_size": chunk_size},
            cause=e,
        )


def overwrite_or_insert_summary_section(
    md_path: Path, new_summary: str) -> None:
    """
    Overwrite the ## Summary section in a markdown file with new_summary.
    If the section does not exist, insert it before ## Full Transcript, or at the end if not found.
    """
    md_path = Path(md_path)
    with open(md_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    summary_header = "## Summary"
    transcript_header = "## Full Transcript"
    summary_start = None
    summary_end = None
    transcript_start = None

    # Find section positions
    for i, line in enumerate(lines):
        if line.strip() == summary_header:
            summary_start = i
        elif line.strip() == transcript_header:
            transcript_start = i
        elif line.strip().startswith("##") and i > 0:
            # Mark end of summary if we already found it
            if summary_start is not None and summary_end is None and i > summary_start:
                summary_end = i

    if summary_start is not None:
        # Overwrite existing summary section
        if summary_end is None:
            # No section after summary, find the transcript section or end of
            # file
            if transcript_start is not None:
                summary_end = transcript_start
            else:
                summary_end = len(lines)
        new_section = [
    summary_header +
    "\n",
    "\n",
    new_summary.strip() +
    "\n",
     "\n"]
        new_lines = lines[:summary_start] + new_section + lines[summary_end:]
    else:
        # Insert new summary section
        new_section = [
    summary_header +
    "\n",
    "\n",
    new_summary.strip() +
    "\n",
     "\n"]
        if transcript_start is not None:
            # Insert before transcript section
            new_lines = lines[:transcript_start] + \
                new_section + lines[transcript_start:]
        else:
            # Insert at end if no transcript section found
            if len(lines) == 0:
                new_lines = new_section
            else:
                if not lines[-1].endswith("\n"):
                    lines[-1] += "\n"
                new_lines = lines + ["\n"] + new_section

    with open(md_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
