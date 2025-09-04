# GitHub Release Setup Guide

This guide explains how to set up automated DMG releases to your public GitHub repository.

## Overview

The release system automatically:
1. Builds a DMG from your current version (from `pyproject.toml`)
2. Creates a tagged release on the public repository
3. Uploads the DMG as a release asset
4. Updates the public repository's README with version info

## Prerequisites

### 1. GitHub CLI (Required for automated releases)

Install GitHub CLI for full automation:

```bash
# Install via Homebrew
brew install gh

# Or download from: https://cli.github.com/
```

### 2. Authenticate with GitHub

Authenticate the GitHub CLI with your account:

```bash
gh auth login
```

Follow the prompts to:
- Choose GitHub.com
- Choose HTTPS
- Authenticate via web browser
- Grant necessary permissions

### 3. Verify Authentication

Test that you can access your public repository:

```bash
gh repo view msg43/Skipthepodcast.com
```

### 4. Repository Access

Ensure your account has **write access** to the public repository:
- You should be the owner or have push permissions
- The repository should exist (even if empty)

## Scripts Overview

### Main Scripts

1. **`scripts/release_dmg_to_public.sh`** - Main script to run for releases
2. **`scripts/publish_release.sh`** - Core release logic
3. **`scripts/build_macos_app.sh`** - Enhanced to suggest releases

### Quick Release Command

For a simple release, just run:

```bash
bash scripts/release_dmg_to_public.sh
```

This will:
- Check current version from `pyproject.toml`
- Build DMG if needed (or use existing)
- Create tagged release on public repository
- Upload DMG as release asset

## Manual Release Process

If you prefer manual control or the automation fails:

### 1. Build DMG

```bash
bash scripts/build_macos_app.sh --make-dmg --skip-install
```

### 2. Publish Release

```bash
# Publish with automatic build
bash scripts/publish_release.sh

# Or skip building and use existing DMG
bash scripts/publish_release.sh --skip-build

# Dry run to see what would happen
bash scripts/publish_release.sh --dry-run
```

## Workflow Integration

### Option 1: Manual Releases

After making changes and bumping version:

```bash
# Bump version (updates pyproject.toml and README.md)
python3 scripts/bump_version.py --part patch

# Commit version bump
git add .
git commit -m "Bump version to $(grep '^version' pyproject.toml | cut -d'"' -f2)"

# Build and release
bash scripts/release_dmg_to_public.sh
```

### Option 2: Integrated with Build Script

The build script now suggests running the release:

```bash
bash scripts/build_macos_app.sh --make-dmg --skip-install
# Will show: "📍 To publish to public repository: bash scripts/publish_release.sh"
```

## Configuration

### Public Repository Settings

The scripts are configured for:
- **Public Repo:** `https://github.com/msg43/Skipthepodcast.com`
- **Release Name:** `Knowledge Chipper v{version}`
- **DMG Name:** `Knowledge_Chipper-{version}.dmg`

To change the public repository, edit `scripts/publish_release.sh`:

```bash
PUBLIC_REPO_URL="https://github.com/your-username/your-repo.git"
PUBLIC_REPO_NAME="your-repo"
```

## Troubleshooting

### Common Issues

1. **"gh: command not found"**
   - Install GitHub CLI: `brew install gh`

2. **Authentication errors**
   - Run: `gh auth login` and follow prompts
   - Ensure you have access to the public repository

3. **Repository doesn't exist**
   - Create the repository on GitHub first
   - Make sure it's public
   - Ensure you have write access

4. **DMG build fails**
   - Check `logs/build_macos_app_clean2.log` for errors
   - Ensure all dependencies are installed
   - Try rebuilding with `--force-rebuild`

### Manual Fallback

If automation fails, you can manually:

1. Go to https://github.com/msg43/Skipthepodcast.com/releases
2. Click "Create a new release"
3. Create tag `v{version}` (e.g., `v3.1.1`)
4. Upload the DMG from `dist/Knowledge_Chipper-{version}.dmg`
5. Publish the release

## Security Notes

- Scripts only push to the public repository
- Private repository code is never uploaded
- Only the built DMG is shared publicly
- Authentication uses GitHub's official CLI

## Script Options

### publish_release.sh Options

```bash
--force-rebuild   # Force rebuild DMG even if it exists
--skip-build      # Use existing DMG, don't build
--dry-run         # Show what would be done without doing it
--help            # Show help message
```

### Example Usage

```bash
# Force rebuild and publish
bash scripts/publish_release.sh --force-rebuild

# Publish existing DMG without building
bash scripts/publish_release.sh --skip-build

# See what would happen without doing it
bash scripts/publish_release.sh --dry-run
```

## Version Management

The system automatically uses the version from `pyproject.toml` as the single source of truth:

1. **Version Detection:** Reads from `pyproject.toml`
2. **Tag Creation:** Creates `v{version}` tag
3. **Release Naming:** Names release "Knowledge Chipper v{version}"
4. **DMG Naming:** Names file `Knowledge_Chipper-{version}.dmg`

To bump version before release:

```bash
python3 scripts/bump_version.py --part patch    # 3.1.1 → 3.1.2
python3 scripts/bump_version.py --part minor    # 3.1.1 → 3.2.0
python3 scripts/bump_version.py --part major    # 3.1.1 → 4.0.0
```

## Support

If you encounter issues:

1. Check the troubleshooting section above
2. Run with `--dry-run` to see what would happen
3. Check GitHub CLI authentication: `gh auth status`
4. Verify repository access: `gh repo view msg43/Skipthepodcast.com`
