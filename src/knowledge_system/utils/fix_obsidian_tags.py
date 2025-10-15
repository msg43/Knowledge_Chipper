"""
Utility script to fix Obsidian tag issues in existing markdown files.

This script scans markdown files and converts YAML frontmatter tags
to proper Obsidian hashtags for better tag visibility and functionality.
"""

import sys
from pathlib import Path

# Add the src directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from knowledge_system.logger import get_logger  # noqa: E402
from knowledge_system.utils.obsidian_tags import (
    add_obsidian_hashtags_to_content,
)  # noqa: E402

logger = get_logger(__name__)


def fix_markdown_file_tags(file_path: Path, dry_run: bool = False) -> bool:
    """
    Fix Obsidian tags in a single markdown file.

    Args:
        file_path: Path to the markdown file
        dry_run: If True, only report what would be changed

    Returns:
        True if file was modified (or would be modified in dry run)
    """
    try:
        # Read current content
        with open(file_path, encoding="utf-8") as f:
            original_content = f.read()

        # Process content
        updated_content = add_obsidian_hashtags_to_content(original_content)

        # Check if changes were made
        if original_content == updated_content:
            return False

        if dry_run:
            print(f"Would update: {file_path}")
            # Show what tags would be added
            lines = updated_content.split("\n")
            for i, line in enumerate(lines):
                if line.startswith("#") and not line.startswith("# "):
                    print(f"  Would add tags: {line}")
                    break
            return True

        # Write updated content
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(updated_content)

        print(f"Updated: {file_path}")
        return True

    except Exception as e:
        logger.error(f"Error processing {file_path}: {e}")
        return False


def fix_directory_tags(
    directory: Path, dry_run: bool = False, recursive: bool = True
) -> int:
    """
    Fix Obsidian tags in all markdown files in a directory.

    Args:
        directory: Directory to scan
        dry_run: If True, only report what would be changed
        recursive: If True, scan subdirectories

    Returns:
        Number of files modified (or would be modified in dry run)
    """
    if not directory.exists():
        logger.error(f"Directory does not exist: {directory}")
        return 0

    pattern = "**/*.md" if recursive else "*.md"
    markdown_files = list(directory.glob(pattern))

    if not markdown_files:
        print(f"No markdown files found in {directory}")
        return 0

    print(f"Found {len(markdown_files)} markdown files in {directory}")

    modified_count = 0
    for file_path in markdown_files:
        if fix_markdown_file_tags(file_path, dry_run):
            modified_count += 1

    if dry_run:
        print(f"\nDry run complete. Would modify {modified_count} files.")
    else:
        print(f"\nCompleted. Modified {modified_count} files.")

    return modified_count


def main():
    """Command-line interface for fixing Obsidian tags."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Fix Obsidian tag issues in markdown files"
    )
    parser.add_argument("path", help="Path to markdown file or directory to process")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without making changes",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Don't scan subdirectories (only for directory input)",
    )

    args = parser.parse_args()

    path = Path(args.path)

    if not path.exists():
        print(f"Error: Path does not exist: {path}")
        sys.exit(1)

    if path.is_file():
        if path.suffix.lower() != ".md":
            print(f"Error: File is not a markdown file: {path}")
            sys.exit(1)

        if fix_markdown_file_tags(path, args.dry_run):
            print("File processed successfully.")
        else:
            print("No changes needed.")

    elif path.is_dir():
        modified_count = fix_directory_tags(
            path, dry_run=args.dry_run, recursive=not args.no_recursive
        )

        if modified_count == 0:
            print("No files needed modification.")

    else:
        print(f"Error: Path is neither a file nor directory: {path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
