#!/usr/bin/env python3
"""
WebShare Legacy Code Cleanup Script

Safely removes deprecated WebShare-specific code and configurations while
maintaining backward compatibility for existing users.
"""

import os
import re
import shutil
from pathlib import Path
from typing import List, Tuple


def find_project_root() -> Path:
    """Find the project root directory."""
    current = Path(__file__).parent
    while current.parent != current:
        if (current / "pyproject.toml").exists() or (current / "setup.py").exists():
            return current
        current = current.parent
    raise RuntimeError("Could not find project root")


def backup_file(file_path: Path) -> Path:
    """Create a backup of a file before modification."""
    backup_path = file_path.with_suffix(file_path.suffix + ".webshare_backup")
    shutil.copy2(file_path, backup_path)
    return backup_path


def add_deprecation_warning_to_function(content: str, function_name: str) -> str:
    """Add deprecation warning to a function."""
    warning = f"""    # DEPRECATED: This function uses WebShare which is being replaced by Bright Data
    # TODO: Consider migrating to Bright Data integration for better performance
    import warnings
    warnings.warn(
        f"{function_name} uses deprecated WebShare integration. "
        "Consider migrating to Bright Data for better cost efficiency.",
        DeprecationWarning,
        stacklevel=2
    )
    """

    # Find function definition and add warning
    pattern = rf'(def {function_name}\([^)]*\):[^\n]*\n(?:    """[^"]*?"""[^\n]*\n)?)'

    def add_warning(match):
        return match.group(1) + warning + "\n"

    return re.sub(pattern, add_warning, content, flags=re.MULTILINE | re.DOTALL)


def cleanup_webshare_references() -> list[tuple[Path, str]]:
    """
    Clean up WebShare references in the codebase.

    Returns:
        List of (file_path, action) tuples for changes made
    """
    project_root = find_project_root()
    changes_made = []

    # Files to process for WebShare cleanup
    files_to_process = [
        "src/knowledge_system/processors/youtube_transcript.py",
        "src/knowledge_system/processors/youtube_metadata.py",
        "src/knowledge_system/gui/tabs/youtube_tab.py",
        "src/knowledge_system/gui/workers/youtube_batch_worker.py",
    ]

    for rel_path in files_to_process:
        file_path = project_root / rel_path

        if not file_path.exists():
            print(f"⚠️  Skipping non-existent file: {file_path}")
            continue

        print(f"🔍 Processing: {file_path}")

        # Read current content
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        original_content = content

        # Add deprecation warnings to WebShare-specific functions
        webshare_functions = [
            "_validate_webshare_config",
            "_get_webshare_proxy_config",
            "setup_webshare_proxy",
        ]

        for func_name in webshare_functions:
            if f"def {func_name}" in content:
                content = add_deprecation_warning_to_function(content, func_name)
                changes_made.append(
                    (file_path, f"Added deprecation warning to {func_name}")
                )

        # Add deprecation comments to WebShare imports
        webshare_import_patterns = [
            (
                r"(from youtube_transcript_api\.proxies import WebshareProxyConfig)",
                r"\1  # DEPRECATED: Legacy WebShare support",
            ),
            (
                r"(import.*WebshareProxyConfig)",
                r"\1  # DEPRECATED: Legacy WebShare support",
            ),
        ]

        for pattern, replacement in webshare_import_patterns:
            if re.search(pattern, content):
                content = re.sub(pattern, replacement, content)
                changes_made.append(
                    (file_path, "Added deprecation comment to WebShare import")
                )

        # Update error messages to mention both WebShare and Bright Data
        webshare_error_patterns = [
            (
                r"WebShare credentials required",
                "Proxy credentials required (Bright Data recommended, WebShare legacy)",
            ),
            (
                r"WebShare proxy credentials",
                "Proxy credentials (Bright Data or WebShare legacy)",
            ),
            (
                r"configure WebShare",
                "configure Bright Data (recommended) or WebShare (legacy)",
            ),
        ]

        for pattern, replacement in webshare_error_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
                changes_made.append((file_path, f"Updated error message: {pattern}"))

        # Save changes if any were made
        if content != original_content:
            # Create backup first
            backup_path = backup_file(file_path)
            changes_made.append((file_path, f"Created backup at {backup_path}"))

            # Write updated content
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            changes_made.append((file_path, "Updated file with deprecation warnings"))
            print(f"✅ Updated: {file_path}")
        else:
            print(f"ℹ️  No changes needed: {file_path}")

    return changes_made


def create_migration_guide() -> Path:
    """Create a migration guide for users with WebShare configurations."""
    project_root = find_project_root()
    guide_path = project_root / "config" / "WEBSHARE_TO_BRIGHTDATA_MIGRATION.md"

    guide_content = """# WebShare to Bright Data Migration Guide

## Overview

This guide helps you migrate from deprecated WebShare proxy configuration to the new Bright Data integration.

## Why Migrate?

- ✅ **Cost Savings**: Pay-per-request instead of monthly subscriptions
- ✅ **Better Reliability**: Direct YouTube API integration
- ✅ **Improved Performance**: Optimized for YouTube processing
- ✅ **Future Support**: Active development and maintenance

## Migration Steps

### 1. Get Bright Data Credentials

1. Sign up at [brightdata.com](https://brightdata.com/)
2. Create a YouTube API Scraper account
3. Note your API key (starts with `bd_` or `2`)

### 2. Configure Bright Data

**Option A: Using GUI (Recommended)**
1. Open Knowledge System
2. Go to "API Keys" tab
3. Enter your Bright Data API Key
4. Save settings

**Option B: Environment Variables**
```bash
export BRIGHT_DATA_API_KEY="your_api_key_here"
```

### 3. Test Migration

Process a test video to verify Bright Data is working:

```bash
knowledge-system process "https://youtube.com/watch?v=dQw4w9WgXcQ" --transcribe
```

Look for log messages indicating "Using Bright Data" instead of "Using WebShare".

### 4. Remove WebShare Configuration (Optional)

Once Bright Data is working, you can optionally remove WebShare credentials:

1. Clear WebShare Username and Password in GUI
2. Remove `WEBSHARE_USERNAME` and `WEBSHARE_PASSWORD` environment variables
3. Remove webshare entries from `config/credentials.yaml`

## Rollback Plan

If you need to rollback to WebShare:

1. Re-enter your WebShare credentials in the API Keys tab
2. Remove or comment out the Bright Data API Key
3. Restart the application

The system will automatically fall back to WebShare when Bright Data is not configured.

## Troubleshooting

### "Bright Data credentials incomplete"
- Verify your API key is correct
- Check that `BD_CUST`, `BD_ZONE`, and `BD_PASS` environment variables are set (if using proxy mode)

### "Using WebShare for..." messages
- This indicates Bright Data is not configured or credentials are invalid
- Verify your Bright Data API key in the GUI

### High costs with Bright Data
- Enable deduplication (enabled by default)
- Check `knowledge-system database stats` for usage patterns
- Monitor costs with `knowledge-system database budget --budget 100`

## Support

- **Documentation**: See `config/bright_data_setup.md`
- **Cost Monitoring**: Use `knowledge-system database` commands
- **Issues**: Check application logs for detailed error messages

---

*This migration guide will be removed when WebShare support is fully deprecated.*
"""

    with open(guide_path, "w", encoding="utf-8") as f:
        f.write(guide_content)

    return guide_path


def main():
    """Main cleanup function."""
    print("🧹 WebShare Legacy Code Cleanup")
    print("=" * 40)

    try:
        # Perform cleanup
        changes = cleanup_webshare_references()

        if changes:
            print(f"\n✅ Cleanup completed! Made {len(changes)} changes:")
            for file_path, action in changes:
                print(f"   • {file_path.name}: {action}")
        else:
            print("\nℹ️  No changes were needed - files already up to date")

        # Create migration guide
        guide_path = create_migration_guide()
        print(f"\n📚 Created migration guide: {guide_path}")

        print("\n🎉 WebShare cleanup completed successfully!")
        print("\nNext steps:")
        print("1. Test the application to ensure everything works")
        print("2. Share the migration guide with users")
        print("3. Monitor for any deprecation warnings in logs")

    except Exception as e:
        print(f"\n❌ Cleanup failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
