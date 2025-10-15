# PKG Release Process Guide

## Quick Release Commands

### Option 1: Build and Release in One Command
```bash
# Build everything and create GitHub release automatically
./scripts/build_complete_pkg.sh --upload-release
```

### Option 2: Manual Release Process
```bash
# 1. Build components locally first
./scripts/build_complete_pkg.sh --build-only

# 2. Create GitHub release manually
./scripts/create_github_release.sh
```

### Option 3: Version Bump and Release
```bash
# Bump version and release
./scripts/release_pkg_to_public.sh --bump-version

# Bump specific version part
./scripts/release_pkg_to_public.sh --bump-version --bump-part minor
```

## Detailed Release Process

### Step 1: Prepare Release

1. **Ensure you're on the right branch**:
   ```bash
   git checkout main
   git pull origin main
   ```

2. **Check current version**:
   ```bash
   python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])"
   ```

3. **Optional: Bump version** (if not using auto-bump):
   ```bash
   # Bump patch version (3.2.22 -> 3.2.23)
   ./scripts/bump_version.py --part patch

   # Bump minor version (3.2.22 -> 3.3.0)
   ./scripts/bump_version.py --part minor

   # Bump major version (3.2.22 -> 4.0.0)
   ./scripts/bump_version.py --part major
   ```

### Step 2: Build Components

The build system will create these components:

1. **Python Framework** (~40MB):
   ```bash
   ./scripts/build_python_framework.sh
   ```

2. **AI Models Bundle** (~1.2GB):
   ```bash
   ./scripts/bundle_ai_models.sh
   ```

3. **FFmpeg Package** (~48MB):
   ```bash
   ./scripts/bundle_ffmpeg.sh
   ```

4. **PKG Installer** (~10MB):
   ```bash
   ./scripts/build_pkg_installer.sh
   ```

Or build everything at once:
```bash
./scripts/build_complete_pkg.sh
```

### Step 3: Create GitHub Release

#### Automatic Release (Recommended)
```bash
./scripts/create_github_release.sh
```

This will:
- ✅ Create a new GitHub release with version tag
- ✅ Upload all PKG components  
- ✅ Generate comprehensive release notes
- ✅ Create checksums for verification
- ✅ Set up download URLs

#### Manual GitHub Release

If you prefer manual control:

1. **Create the release via GitHub CLI**:
   ```bash
   # Get current version
   VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])")
   
   # Create draft release
   gh release create "v$VERSION" \
       --title "Skip the Podcast Desktop v$VERSION" \
       --notes-file dist/release_notes_$VERSION.md \
       --draft
   ```

2. **Upload components**:
   ```bash
   cd dist
   gh release upload "v$VERSION" \
       "Skip_the_Podcast_Desktop-$VERSION.pkg" \
       "python-framework-3.13-macos.tar.gz" \
       "ai-models-bundle.tar.gz" \
       "ffmpeg-macos-universal.tar.gz" \
       "checksums_$VERSION.txt"
   ```

3. **Publish the release**:
   ```bash
   gh release edit "v$VERSION" --draft=false
   ```

## GitHub Release Structure

Your GitHub release will contain:

```
Skip the Podcast Desktop v3.2.23
├── Skip_the_Podcast_Desktop-3.2.23.pkg (10MB) ← Main installer
├── python-framework-3.13-macos.tar.gz (40MB)   ← Python runtime
├── ai-models-bundle.tar.gz (1.2GB)              ← AI models
├── ffmpeg-macos-universal.tar.gz (48MB)         ← Media processing
├── checksums_3.2.23.txt                         ← Verification
└── Release notes with installation instructions
```

## Installation Instructions for Users

When you create a release, users will see these instructions:

### For New Users:
1. Download `Skip_the_Podcast_Desktop-X.X.X.pkg`
2. Double-click to install
3. Follow installer prompts
4. Wait for components to download (3-6GB based on hardware)
5. Launch from Applications

### Hardware-Optimized Downloads:
- **M2/M3 Ultra (64GB+ RAM)**: Downloads ~6GB total
- **M2/M3 Max (32GB+ RAM)**: Downloads ~5GB total  
- **M2/M3 Pro (16GB+ RAM)**: Downloads ~3.5GB total
- **Base Systems**: Downloads ~3GB total

## Verification

Users can verify downloads:
```bash
# Verify PKG installer
shasum -a 256 -c checksums_X.X.X.txt
```

## Release Notes Template

The release script automatically generates comprehensive release notes including:

- ✅ **What's New** section
- ✅ **Installation instructions**
- ✅ **Hardware optimization details**
- ✅ **Component breakdown**
- ✅ **System requirements**
- ✅ **Troubleshooting links**

## Monitoring Releases

After release, monitor:

1. **Download statistics**:
   ```bash
   gh release view v$VERSION --json assets
   ```

2. **Installation success rate** (via user feedback)

3. **Component download performance** (via GitHub insights)

## Rollback Procedure

If a release has issues:

1. **Create hotfix release**:
   ```bash
   ./scripts/bump_version.py --part patch
   ./scripts/build_complete_pkg.sh --upload-release
   ```

2. **Or rollback to previous version**:
   - Mark problematic release as pre-release
   - Point users to previous stable release
   - Fix issues and create new release

## Prerequisites

### Required Tools:
- ✅ **GitHub CLI**: `brew install gh`
- ✅ **GitHub authentication**: `gh auth login`
- ✅ **macOS PKG tools**: `pkgbuild`, `productbuild` (included with Xcode)
- ✅ **Python 3.13+**: For build scripts

### Required Permissions:
- ✅ **Write access** to GitHub repository
- ✅ **Release creation** permissions
- ✅ **Large file upload** capability (for 1.2GB AI models)

## Troubleshooting

### Common Issues:

1. **GitHub CLI not authenticated**:
   ```bash
   gh auth login
   ```

2. **Large file upload timeouts**:
   - Use stable internet connection
   - Upload during off-peak hours
   - Consider splitting very large components

3. **PKG build failures**:
   ```bash
   # Check logs
   tail -f /tmp/pkg_installation_test.log
   
   # Test individual components
   ./scripts/test_pkg_installation.sh --verbose
   ```

4. **Version conflicts**:
   ```bash
   # Check current version
   git tag --list | tail -5
   
   # Ensure version bump is correct
   python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])"
   ```

## Success Metrics

A successful release should have:
- ✅ **All components uploaded** without corruption
- ✅ **Checksums verify correctly**
- ✅ **Release notes are comprehensive**
- ✅ **Download URLs work** from fresh browsers
- ✅ **PKG installs successfully** on clean macOS systems

---

## Ready to Release?

Use this command to create your first PKG release:

```bash
./scripts/build_complete_pkg.sh --upload-release
```

This will handle everything automatically: build components, create release, upload files, and generate release notes.
