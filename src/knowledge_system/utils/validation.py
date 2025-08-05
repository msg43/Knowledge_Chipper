"""
Common validation utilities for processors.
Consolidates validation patterns used across the codebase.
"""

from pathlib import Path
from typing import Any, List, Union


def validate_file_input(
    input_data: Any, supported_formats: list[str], allow_directories: bool = False
) -> bool:
    """
    Validate file input data with support for multiple formats.

    Args:
        input_data: Input data to validate (file path, directory, or list)
        supported_formats: List of supported file extensions (e.g., ['.txt', '.md'])
        allow_directories: Whether to allow directory inputs

    Returns:
        True if input is valid, False otherwise
    """
    if isinstance(input_data, (str, Path)):
        path = Path(input_data)

        # Check if path exists
        if not path.exists():
            return False

        # Check if it's a directory (only if allowed)
        if path.is_dir():
            return allow_directories

        # Check if it's a file with supported format
        if path.is_file():
            return path.suffix.lower() in [fmt.lower() for fmt in supported_formats]

        return False

    elif isinstance(input_data, list):
        # Validate all items in the list
        return all(
            validate_file_input(item, supported_formats, allow_directories)
            for item in input_data
        )

    return False


def validate_audio_input(input_path: str | Path) -> bool:
    """
    Validate audio file input.

    Args:
        input_path: Path to audio file

    Returns:
        True if input is a valid audio file, False otherwise
    """
    audio_formats = [".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".mp4", ".webm"]
    return validate_file_input(input_path, audio_formats)


def validate_text_input(input_path: str | Path) -> bool:
    """
    Validate text file input.

    Args:
        input_path: Path to text file

    Returns:
        True if input is a valid text file, False otherwise
    """
    text_formats = [".txt", ".md", ".rst", ".json"]
    return validate_file_input(input_path, text_formats)


def validate_document_input(input_path: str | Path) -> bool:
    """
    Validate document file input.

    Args:
        input_path: Path to document file

    Returns:
        True if input is a valid document file, False otherwise
    """
    document_formats = [".pdf", ".docx", ".doc", ".txt", ".md", ".rtf"]
    return validate_file_input(input_path, document_formats)


def can_process_file(input_path: str | Path, supported_formats: list[str]) -> bool:
    """
    Check if a file can be processed based on its extension.

    Args:
        input_path: Path to file
        supported_formats: List of supported file extensions

    Returns:
        True if file can be processed, False otherwise
    """
    path = Path(input_path)
    return path.suffix.lower() in [fmt.lower() for fmt in supported_formats]


def validate_string_input(input_data: str | Path) -> bool:
    """
    Validate string input data.

    Args:
        input_data: Input data to validate

    Returns:
        True if input is a non-empty string, False otherwise
    """
    if isinstance(input_data, str):
        return len(input_data.strip()) > 0
    else:  # Path
        return input_data.exists() and input_data.is_file()


def validate_url_or_file_input(input_data: Any, url_validator: Any = None) -> bool:
    """
    Validate input that can be either a URL or a file containing URLs.

    Args:
        input_data: Input data to validate
        url_validator: Optional function to validate URLs

    Returns:
        True if input is valid, False otherwise
    """
    if isinstance(input_data, (str, Path)):
        input_str = str(input_data)

        # Check if it's a URL (if validator provided)
        if url_validator and url_validator(input_str):
            return True

        # Check if it's a file containing URLs
        if Path(input_str).exists():
            try:
                with open(input_str, encoding="utf-8") as f:
                    content = f.read()
                    if url_validator:
                        return any(
                            url_validator(line.strip()) for line in content.split("\n")
                        )
                    else:
                        return len(content.strip()) > 0
            except (OSError, UnicodeDecodeError):
                pass

    return False
