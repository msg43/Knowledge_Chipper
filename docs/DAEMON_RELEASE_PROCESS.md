# Daemon Release Process

**Last Updated:** January 13, 2026  
**Current Version:** See `daemon/__init__.py`

---

## Overview

The GetReceipts daemon (formerly "Skip the Podcast Desktop") is released as a **signed & notarized PKG installer** to the public repository at `https://github.com/msg43/Skipthepodcast.com`. 

**Architecture Change (January 2026):**
- ❌ **Old:** Desktop app with GUI (PyQt6) - **DEPRECATED**
- ✅ **New:** Background daemon controlled via GetReceipts.org web interface

The daemon is the only component users need. All interaction happens through the web browser.

---

## Version Management

### Single Version Number (Daemon Version)

**As of January 2026**, there is only **one version number** that matters:

**Daemon Version** (in `daemon/__init__.py`)
- The background service/API
- Used for GitHub release tags (e.g., v1.1.0)
- Used for PKG filenames (e.g., `GetReceipts-Daemon-1.1.3.pkg`)
- Reported by daemon's `/health` endpoint
- Used by auto-update checker

### Version Location

```
daemon/__init__.py
```

```python
__version__ = "X.Y.Z"  # Update this for each release
```

### Legacy Application Version (DEPRECATED)

The old `pyproject.toml` version (4.1.0) is **deprecated** and no longer used:
```toml
[project]
version = "4.1.0"  # LEGACY - No longer used for releases
```

This was for the old desktop GUI app which has been replaced by the web-controlled daemon.

### Release Naming

GitHub releases use the **daemon version**:
- Release tag: `v1.1.3`
- PKG filename: `GetReceipts-Daemon-1.1.3.pkg`
- Release title: "GetReceipts Daemon v1.1.3"

**Distribution Format:** Signed & Notarized PKG

**Download URL:** `https://github.com/msg43/Skipthepodcast.com/releases/latest/download/GetReceipts-Daemon-X.Y.Z.pkg`

---

## Release Workflow

### Automated Release (Recommended)

**GitHub Actions automatically builds and publishes releases when you push a version tag:**

```bash
# 1. Update daemon version
# Edit daemon/__init__.py
__version__ = "1.1.2"  # Increment version

# 2. Commit changes
git add daemon/__init__.py CHANGELOG.md
git commit -m "Release daemon v1.1.2"

# 3. Create and push tag
git tag v1.1.2
git push origin main
git push origin v1.1.2

# 4. GitHub Actions automatically:
#    - Runs daemon tests
#    - Builds signed & notarized PKG
#    - Publishes to Skipthepodcast.com
#    - Creates both versioned and stable PKG
#    - Verifies download URL works
```

**Monitor progress:** https://github.com/msg43/Knowledge_Chipper/actions

### Manual Release (Backup)

If automation fails or you need manual control:

#### Step 1: Update Daemon Version

```bash
# Edit daemon/__init__.py
__version__ = "1.1.2"  # Increment version (semantic versioning)
```

**Semantic Versioning:**
- **Major** (1.x.x): Breaking API changes
- **Minor** (x.1.x): New features, backwards compatible
- **Patch** (x.x.1): Bug fixes

#### Step 2: Build the PKG

Build the signed & notarized PKG installer:

```bash
cd /Users/matthewgreer/Projects/Knowledge_Chipper
bash installer/build_pkg.sh
```

This creates:
```
dist/GetReceipts-Daemon-{VERSION}.pkg
```

**Requirements:**
- Developer ID certificates installed
- App-specific password for notarization (set `APP_PASSWORD` env var)
- Python virtual environment with dependencies

### Step 3: Publish to GitHub

Use the publish script to release to the public repository:

```bash
bash scripts/publish_release.sh
```

This script:
1. ✅ Reads **daemon version** from `daemon/__init__.py` (e.g., 1.1.3)
2. ✅ Checks if PKG exists for that version
3. ✅ Builds PKG if needed
4. ✅ Creates a git tag in the public repo (e.g., v1.1.3)
5. ✅ Creates a GitHub release titled "GetReceipts Daemon v1.1.3"
6. ✅ Uploads versioned PKG: `GetReceipts-Daemon-1.1.3.pkg`

#### Step 4: Verify Release

Check the release page:
```
https://github.com/msg43/Skipthepodcast.com/releases/latest
```

Verify:
- ✅ PKG file present: `GetReceipts-Daemon-1.1.3.pkg`
- ✅ Release title: "GetReceipts Daemon v1.1.3"
- ✅ Download URL works: `https://github.com/msg43/Skipthepodcast.com/releases/latest/download/GetReceipts-Daemon-1.1.3.pkg`
- ✅ PKG is signed and notarized (check with `pkgutil --check-signature`)

**Note:** The `/releases/latest/download/` URL automatically redirects to the latest release's asset, so the website always downloads the newest version.

---

## GitHub Actions Automation

### Overview

The daemon release process is **fully automated** via GitHub Actions. When you push a version tag, it automatically tests, builds, and publishes the release.

### Workflow File

[`.github/workflows/daemon-release.yml`](.github/workflows/daemon-release.yml)

### How It Works

```mermaid
flowchart LR
    A[Push version tag] --> B[Run Tests]
    B --> C[Build PKG]
    C --> D[Notarize]
    D --> E[Publish Release]
    E --> F[Verify Download]
```

**Jobs:**
1. **Test** (Ubuntu) - Run daemon API tests (~30 seconds)
2. **Build** (macOS) - Create signed PKG (~5 minutes)
3. **Notarize** (macOS) - Apple notarization (~10-15 minutes)
4. **Publish** (macOS) - Upload to Skipthepodcast.com (~1 minute)

### Using Automation

```bash
# 1. Update version
vim daemon/__init__.py  # Change __version__ = "1.1.2"

# 2. Update CHANGELOG.md
vim CHANGELOG.md  # Add release notes

# 3. Commit and tag
git add daemon/__init__.py CHANGELOG.md
git commit -m "Release daemon v1.1.2"
git tag v1.1.2
git push origin main
git push origin v1.1.2

# 4. Monitor progress
open https://github.com/msg43/Knowledge_Chipper/actions

# 5. Verify release
open https://github.com/msg43/Skipthepodcast.com/releases/latest
```

### What Gets Tested

**Daemon-specific tests only** (no false failures):
- ✅ Health endpoint (`/health`)
- ✅ Process endpoint (`/process`)
- ✅ Jobs endpoint (`/jobs`)
- ✅ Config endpoint (`/config`)
- ✅ Daemon imports and initialization

**NOT tested** (avoid false failures):
- ❌ GUI tests (deprecated)
- ❌ HCE tests (not used)
- ❌ Diarization tests (not used)
- ❌ Heavy ML tests (models download on-demand)

### Manual Testing

Test locally before pushing tag:

```bash
# Run daemon tests
make test-daemon

# Build PKG locally
export APP_PASSWORD="your-notarization-password"
bash installer/build_pkg.sh

# Verify everything works before tagging
```

### Troubleshooting Automation

**If workflow fails:**
1. Check Actions tab: https://github.com/msg43/Knowledge_Chipper/actions
2. Review error logs
3. Fix issue and create new tag (e.g., v1.1.3)
4. Or use manual release as backup

**Manual workflow trigger:**
- Go to Actions tab
- Select "Daemon Release" workflow
- Click "Run workflow"
- Useful for testing without creating tags

---

## Download URLs

### Latest Release URL

This URL always points to the latest release page:
```
https://github.com/msg43/Skipthepodcast.com/releases/latest
```

**Versioned Download URL:**
```
https://github.com/msg43/Skipthepodcast.com/releases/download/v1.1.3/GetReceipts-Daemon-1.1.3.pkg
```

**Used by:**
- GetReceipts.org download buttons
- Daemon auto-update system
- Installation scripts

---

## GetReceipts.org Integration

Download links on GetReceipts.org point to the GitHub releases page:

```typescript
window.open("https://github.com/msg43/Skipthepodcast.com/releases/latest", "_blank");
```

---

## Why PKG Instead of DMG?

**Current Distribution (January 2026):**

We use signed & notarized PKG installers for the following benefits:

**Benefits of PKG:**
- ✅ One-click installation (no drag-and-drop needed)
- ✅ Automatic setup of LaunchAgent (auto-start on login)
- ✅ Desktop restart button created automatically
- ✅ Professional installer experience
- ✅ Signed and notarized by Apple

---

## Auto-Update System

The daemon includes an auto-update system that checks for new releases automatically.

### When Updates Are Checked

The daemon checks for updates in two scenarios:
1. **On Startup** - Every time the daemon starts or restarts
2. **Every 24 Hours** - While running, checks periodically

### How It Works

1. **Check for Updates**
   - Daemon queries GitHub releases API
   - Compares current version with latest release

2. **Download Update**
   - Downloads latest PKG from GitHub releases
   - Verifies integrity

3. **Install Update**
   - Runs PKG installer
   - LaunchAgent automatically restarts daemon

### Configuration

Auto-update settings in daemon:
```python
# daemon/services/update_checker.py
CHECK_INTERVAL_HOURS = 24  # Check every 24 hours
GITHUB_REPO = "msg43/Skipthepodcast.com"  # Checks releases here
```

---

## How to Restart the Daemon

### Method 1: Desktop Shortcut (Easiest)

Double-click the **"GetReceipts Daemon"** icon on your desktop:
- Shows current status (running/stopped)
- Offers to Start/Restart/Stop
- Shows notifications
- No terminal required!

**Location:** `~/Desktop/GetReceipts Daemon.app`

### Method 2: Web Button (Convenient)

Visit GetReceipts.org/contribute/settings and click **"Restart Daemon"** button:
- Restarts daemon remotely
- Checks for updates immediately
- Works from any browser

### Method 3: Terminal Command

```bash
# Restart the daemon
launchctl stop org.skipthepodcast.daemon
launchctl start org.skipthepodcast.daemon
```

Or use the convenience scripts:

```bash
# Stop daemon
/Applications/Skip\ the\ Podcast\ Desktop.app/Contents/Resources/bin/stop-daemon.sh

# Start daemon
/Applications/Skip\ the\ Podcast\ Desktop.app/Contents/Resources/bin/start-daemon.sh

# Check status
/Applications/Skip\ the\ Podcast\ Desktop.app/Contents/Resources/bin/daemon-status.sh
```

### Method 4: Restart macOS

The daemon will automatically start when you log back in (if configured to run at load).

### Why Restart?

Restarting the daemon will:
- ✅ Check for updates immediately (instead of waiting 24 hours)
- ✅ Apply any configuration changes
- ✅ Clear any stuck processes
- ✅ Reload the latest code if manually updated

---

## Troubleshooting

### Issue: Download link returns 404

**Cause:** Release not published or PKG file missing

**Solution:**
1. Check release exists: `https://github.com/msg43/Skipthepodcast.com/releases/latest`
2. Verify PKG file is uploaded
3. Re-run release script if needed: `bash scripts/release_daemon.sh`

### Issue: Version mismatch

**Cause:** Daemon version in `__init__.py` doesn't match release tag

**Solution:**
1. Update `daemon/__init__.py` with correct version
2. Rebuild PKG: `bash installer/build_pkg.sh`
3. Re-publish release

### Issue: Old version still downloading

**Cause:** GitHub CDN cache

**Solution:**
- Wait 5-10 minutes for CDN to update
- Use versioned URL for immediate access

### Issue: Notarization fails

**Cause:** Missing or invalid Apple credentials

**Solution:**
1. Verify `APP_PASSWORD` environment variable is set
2. Check Apple Developer certificate is valid
3. Review notarization log for specific errors

---

## Release Checklist

Before publishing a new daemon release:

- [ ] Update version in `daemon/__init__.py`
- [ ] Update CHANGELOG.md with release notes
- [ ] Test daemon locally
- [ ] Run `bash scripts/release_daemon.sh` (handles everything automatically)
- [ ] Verify release on GitHub:
  - [ ] Tagged correctly (e.g., v1.1.3)
  - [ ] Title is "GetReceipts Daemon v1.1.3"
  - [ ] PKG file uploaded
- [ ] Test download from GitHub releases page
- [ ] Verify daemon auto-update detects new version

**Note:** Only the daemon version matters now. The old pyproject.toml version (4.1.0) is deprecated.

---

## Quick Reference

### One-Click Release (Recommended)
```bash
bash scripts/release_daemon.sh
```

### Build PKG Only
```bash
export APP_PASSWORD="your-notarization-password"
bash installer/build_pkg.sh
```

### Check Current Daemon Version
```bash
python3 -c "from daemon import __version__; print(__version__)"
```

### Test Download URL
```bash
curl -I https://github.com/msg43/Skipthepodcast.com/releases/latest
```

---

## Related Documentation

- `docs/DAEMON_AUTO_UPDATE_IMPLEMENTATION.md` - Auto-update system details
- `RELEASE_DAEMON_SCRIPT.md` - One-click release script documentation
- `CHANGELOG.md` - Version history
- `README.md` - User-facing documentation
- `scripts/release_daemon.sh` - Release automation script
- `installer/build_pkg.sh` - PKG build script
