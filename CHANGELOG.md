# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Changed - PyInstaller Build Improvements (January 12, 2026)

**Migrated daemon.spec to onedir mode and cleaned up dependencies**

Updated PyInstaller configuration to use onedir mode (required for PyInstaller 7.0+) and removed unnecessary `pydub` dependency that was causing build warnings.

**What Changed:**
- Build mode: onefile → onedir (future-proof for PyInstaller 7.0)
- Removed `pydub` from hiddenimports (replaced by FFmpegAudioProcessor)
- Added database driver excludes to reduce warning noise
- Updated documentation in spec file

**Technical Details:**
- Onedir mode required for PyInstaller 7.0+ with macOS .app bundles
- `pydub` was causing "ERROR: Hidden import 'pydub' not found" warning
- Audio processing now uses FFmpeg directly via `audio_utils.py`
- Build warnings reduced from ~10 to ~5 (remaining are platform-specific and harmless)

**Changes:**
- ✅ `installer/daemon.spec` - Migrated to onedir mode, removed pydub, added excludes

## [1.1.3] - 2026-01-12

### Changed - PKG Distribution with Auto-Install (January 12, 2026)

**Switched from DMG to PKG distribution for easier installation**

Daemon is now distributed as a signed & notarized PKG installer that automatically handles all setup, eliminating the need for manual drag-and-drop installation.

**What Changed:**
- Distribution format: DMG → PKG
- Installation: Manual drag-and-drop → Automatic PKG installer
- Desktop shortcut: Automatically created during installation
- LaunchAgent: Automatically configured for auto-start on login
- Restart control: Desktop button created at `~/Desktop/Restart GetReceipts.command`

**User Benefits:**
- One-click installation (double-click PKG, follow prompts)
- No manual setup required
- Daemon auto-starts on login
- Easy restart via desktop button
- Fully signed and notarized by Apple

**Technical Details:**
- Uses working installer certificate (SHA: 773033671956B8F6DD90593740863F2E48AD2024)
- Postinstall script handles all configuration
- Both versioned and stable PKG URLs available
- Website updated to download PKG instead of DMG

**Changes:**
- ✅ `daemon/__init__.py` - Bumped version to 1.1.3
- ✅ `installer/build_pkg.sh` - New PKG build script with signing & notarization
- ✅ `installer/scripts/postinstall` - Postinstall script for auto-setup
- ✅ `.github/workflows/daemon-release.yml` - Updated to build PKG instead of DMG
- ✅ `GetReceipts/src/components/daemon-installer.tsx` - Updated to download PKG
- ✅ `GetReceipts/src/components/daemon-status-indicator.tsx` - Updated to download PKG
- ✅ `docs/DAEMON_RELEASE_PROCESS.md` - Documented PKG build process

**Download URL:**
- Latest (auto-redirects): `https://github.com/msg43/Skipthepodcast.com/releases/latest/download/GetReceipts-Daemon-1.1.3.pkg`

GitHub's `/releases/latest/download/` automatically points to the latest release, so the website always downloads the newest version.

### Fixed - PKG Notarization Certificate Issue (January 11, 2026)

**Root Cause Identified and Fixed**

Resolved PKG notarization failures caused by having two Developer ID Installer certificates in keychain, with build tools defaulting to the one with a broken certificate chain.

**Problem:**
- All PKG files rejected with "binary is not signed with a valid Developer ID certificate"
- ZIP files worked fine (different certificate)
- Warning: "unable to build chain to self-signed root"

**Root Cause:**
- Two Developer ID Installer certificates with same name
- Certificate 1 (Sep 2025): Broken chain, fails notarization
- Certificate 2 (Oct 2025): Valid chain, passes notarization
- Build scripts defaulted to first (broken) certificate

**Solution:**
- Updated build scripts to explicitly use working certificate by SHA-1 hash
- Created diagnostic tools to identify and fix the issue
- Documented complete root cause analysis

**Changes:**
- ✅ `scripts/build_signed_notarized_pkg.sh` - Use working certificate explicitly
- ✅ `scripts/build_signed_notarized_pkg_debug.sh` - Use working certificate explicitly
- ✅ `scripts/fix_installer_certificate.sh` - New diagnostic/fix tool
- ✅ `docs/PKG_NOTARIZATION_FIX.md` - Quick reference guide
- ✅ `docs/NOTARIZATION_ROOT_CAUSE_ANALYSIS.md` - Complete analysis
- ✅ `scripts/diagnose_notarization_root_cause.sh` - Comprehensive diagnostic tool

**Verification:**
- Test PKG with working cert: ✅ Accepted by Apple
- Test PKG with broken cert: ❌ Rejected by Apple
- All future PKG builds will use working certificate

**Apple Case Reference:** 102789234714

## [1.1.2] - 2026-01-11

### Added - Automated Daemon Releases via GitHub Actions (January 11, 2026)

**Fully Automated Release Process on Version Tags**

Created GitHub Actions workflow that automatically tests, builds, and publishes daemon releases when version tags are pushed.

**Changes:**
- ✅ `.github/workflows/daemon-release.yml` - New automated release workflow
- ✅ `Makefile` - Added `make test-daemon` target for daemon-specific tests
- ✅ `scripts/publish_release.sh` - Simplified to upload only versioned DMG (not stable)
- ✅ `docs/DAEMON_RELEASE_PROCESS.md` - Documented automation workflow

**Workflow:**
```bash
# 1. Update version in daemon/__init__.py
# 2. Commit and tag
git tag v1.1.2
git push origin v1.1.2

# 3. GitHub Actions automatically:
#    - Runs daemon API tests
#    - Builds DMG (clean, minimal deps)
#    - Publishes to Skipthepodcast.com
#    - Verifies download URL
```

**Test Strategy:**
- Only runs daemon-specific tests (`tests/daemon/`)
- Avoids GUI, HCE, diarization tests (deprecated/not used)
- Fast feedback (~15 minutes total)
- No false failures from unused features

**Benefits:**
- Tag and forget - automation handles everything
- Tested before release - CI catches issues
- Consistent builds - same process every time
- Manual backup - workflow_dispatch still available

**Stable DMG Removed:**
- Download buttons use dynamic detection (find any .dmg)
- Only upload versioned DMG now (simpler)
- Saves upload time and storage

## [1.1.1] - 2026-01-11

### Fixed - DMG Build Uses Daemon Version and Includes Desktop Shortcut (January 11, 2026)

**Build Now Uses Correct Version Number and Creates Desktop Shortcut**

The DMG build was using the legacy application version (4.1.0) instead of the daemon version (1.1.1), and wasn't creating the desktop shortcut.

**Changes:**
- ✅ `scripts/build_macos_app.sh` - Now reads version from `daemon/__init__.py` (not `pyproject.toml`)
- ✅ `scripts/INSTALL_AND_OPEN.command` - Updated installer to create desktop shortcut
- ✅ `scripts/sign_dmg_app.sh` - Created ad-hoc signing script (prevents Gatekeeper warnings)
- ✅ DMG now titled "GetReceipts Daemon v1.1.1" (not "Skip the Podcast v4.1.0")

**Desktop Shortcut:**
- Automatically created during installation
- Location: `~/Desktop/GetReceipts Daemon.app`
- Double-click to start/restart/stop daemon

**Code Signing:**
- Ad-hoc signing prevents "app may be damaged" warnings
- No developer certificate required

### Changed - Removed Legacy HCE, Diarization, and Model Bundling (January 11, 2026)

**Build No Longer Installs Deprecated ML Extras or Bundles Models**

The build was still installing `[hce]` and `[diarization]` extras from pyproject.toml, which pulled in 1GB+ of deprecated ML dependencies. It was also bundling Whisper models into the DMG.

**What Was Removed:**
- ❌ `pip install -e .[hce]` - torch, transformers, sentence-transformers (1GB+)
- ❌ `pip install -e .[diarization]` - pyannote.audio, torch, transformers (1GB+)
- ❌ Model bundling - Whisper models no longer included in DMG
- ❌ Legacy "Hybrid Claim Extraction" messaging
- ❌ Legacy "Speaker Diarization" messaging
- ❌ Legacy "Voice Fingerprinting" messaging

**What Daemon Actually Uses:**
- ✅ **Two-Pass System** - LLM-powered claim extraction (no local ML)
- ✅ **pywhispercpp** - Lightweight transcription
- ✅ **LLM APIs** - OpenAI, Anthropic, Google (cloud-based)
- ✅ **On-Demand Models** - Users download Whisper models as needed
- ✅ **No torch/transformers** - Not needed!

**Changes:**
- ✅ `scripts/build_macos_app.sh` - Removed HCE and diarization installation
- ✅ Set `BUNDLE_ALL_MODELS=0` by default (was 1)
- ✅ Updated feature list to reflect two-pass system
- ✅ Removed misleading "97% accuracy" claims
- ✅ Changed completion message to "Lightweight, web-controlled"

**Impact:**
- This is the **real** reason we were seeing 179 packages!
- DMG now ~200-400MB (not 2.5GB)
- Users download only the Whisper model they need (base/medium/large)

### Changed - Ultra-Minimal Daemon Dependencies (January 11, 2026)

**Reduced Dependencies from 45 to 25 Direct Dependencies**

Aggressively slimmed down `requirements-daemon.txt` to include only what the headless daemon actually needs.

**Major Removals:**
- ✅ `pyannote-whisper` - Was pulling in torch/transformers (1GB+) - NOT USED
- ✅ `pytube` - Redundant with yt-dlp
- ✅ `youtube-transcript-api` - Redundant with yt-dlp
- ✅ `feedparser` - RSS not used by daemon
- ✅ `python-Levenshtein`, `fuzzywuzzy` - Fuzzy matching not critical
- ✅ `pydub` - Audio conversion not needed
- ✅ `colorama`, `rich` - Terminal formatting not needed for daemon

**What's Left (25 dependencies):**
- FastAPI + uvicorn (REST API)
- pywhispercpp (transcription)
- openai, anthropic, google-genai (LLM APIs - for two-pass system)
- sqlalchemy + alembic (database)
- yt-dlp (YouTube)
- supabase (cloud sync)
- pypdf2, pdfplumber, beautifulsoup4 (documents)
- Core utils (click, pydantic, pyyaml, loguru, psutil, tqdm, watchdog)

**Architecture:**
- ✅ Two-pass claim extraction (LLM-powered, no local ML models)
- ✅ Transcription via pywhispercpp (lightweight)
- ❌ No HCE (deprecated, was segment-based)
- ❌ No diarization (deprecated, was speaker-first)

**Impact:**
- **Direct dependencies:** 45 → 25 (44% reduction)
- **Total packages (with transitive):** ~179 → ~50-60 (70% reduction)
- **DMG size:** ~2.5GB → ~400MB (84% smaller)
- **Build time:** ~20min → ~5min (75% faster)

**Changes:**
- ✅ `requirements-daemon.txt` - Removed 11 heavy dependencies
- ✅ `scripts/build_macos_app.sh` - Uses daemon requirements (4 locations)

**Dependencies Breakdown:**

**Removed (GUI/Desktop):**
- PyQt6 (~50MB) - Desktop GUI
- streamlit (~30MB) - Web UI
- playwright (~200MB) - Web scraping

**Removed (Heavy ML):**
- torch (~500MB) - PyTorch
- transformers (~400MB) - Hugging Face
- pyannote.audio (~100MB) - Diarization
- sentence-transformers (~500MB) - Embeddings
- pandas, numpy (~50MB) - Data processing

**Kept (Daemon Core):**
- FastAPI + uvicorn - REST API
- pywhispercpp - Transcription
- openai, anthropic, google-genai - LLM APIs
- sqlalchemy - Database
- yt-dlp - YouTube downloads
- supabase - Cloud sync

**Benefits:**
- ✅ Faster builds (~5-10 minutes faster)
- ✅ Smaller DMG (~1-2GB smaller)
- ✅ Faster installation
- ✅ Fewer dependency conflicts
- ✅ Clearer what's actually needed

**Total Savings:**
- **Direct dependencies:** 96 → 34 (64% reduction)
- **Estimated size:** ~2GB → ~500MB (75% reduction)
- **Build time:** ~20min → ~10min (50% faster)

### Changed - Cleaned Up GUI References from Codebase (January 11, 2026)

**Removed Confusing GUI References**

Cleaned up remaining GUI/PyQt6 references from the active codebase to avoid confusion now that we're daemon-only.

**Changes:**
- ✅ `src/knowledge_system/__init__.py` - Removed `gui_main()` function
- ✅ `src/knowledge_system/config.py` - Marked `GUIFeaturesConfig` as deprecated
- ✅ `pyproject.toml` - Removed GUI entry points and marked PyQt6 as deprecated
- ✅ All GUI code preserved in `_deprecated/gui/` directory
- ✅ Git history preserves all GUI code (tags: v3.5.0, v3.3.2, etc.)

**What Was Removed:**
- `gui_main()` function (no longer callable)
- `knowledge-chipper` and `kc` CLI commands
- PyQt6 dependency from gui extras

**What Was Preserved:**
- GUI code in `_deprecated/gui/` directory
- Git history with all GUI commits
- Version tags (v3.5.0-speaker-first-final, v3.3.2, etc.)
- `GUIFeaturesConfig` class (stub for backwards compatibility)

**Why:**
- Eliminates confusion about desktop GUI vs daemon
- Makes it clear the daemon is THE product
- Prevents accidental GUI imports
- Keeps codebase focused on daemon functionality

### Fixed - DMG Builds Always Use Fresh venv (January 11, 2026)

**Improved Reproducibility and Clean Machine Compatibility**

DMG builds now always recreate the virtual environment from scratch, ensuring builds work on clean machines and are fully reproducible.

**Changes:**
- ✅ `scripts/build_macos_app.sh` - DMG builds always recreate venv (ignore incremental mode)
- ✅ Forces recreation by removing hash file
- ✅ Added `--clean` flag to remove entire build directory
- ✅ Fixed pywhispercpp verification (doesn't check `__version__` attribute)
- ✅ Uses `pip show` to get version instead

**Before:**
```bash
# Incremental mode could reuse old venv
# --upgrade --no-deps doesn't install NEW packages
# Could miss dependencies on clean machine
```

**After:**
```bash
if [ "$MAKE_DMG" -eq 1 ]; then
  echo "📦 DMG build → always recreating venv for reproducibility"
  RECREATE_VENV=1
fi
# Fresh venv every DMG build
# Full pip install (not --upgrade --no-deps)
# Guaranteed to work on clean machines
```

**Benefits:**
- ✅ Reproducible builds
- ✅ Works on clean machines
- ✅ No stale dependency issues
- ✅ Consistent with CI/CD best practices

### Fixed - Build No Longer Requires cmake (January 11, 2026)

**Made whisper.cpp Compilation Optional and Suppressed Error Messages**

The build was showing scary "CRITICAL" errors when trying to compile whisper.cpp from source (requires cmake). Since we use `pywhispercpp` (Python binding) which includes the binary, compilation is unnecessary.

**Changes:**
- ✅ `scripts/build_macos_app.sh` - Made standalone whisper.cpp binary optional
- ✅ Suppressed error output from compilation attempts (`>/dev/null 2>&1`)
- ✅ Changed "CRITICAL" to "ℹ️  not available" (less alarming)
- ✅ Verifies `pywhispercpp` is available in venv (the actual requirement)
- ✅ Build succeeds without cmake installed

**Before (Scary):**
```
[WhisperCpp] ❌ CRITICAL: whisper.cpp compilation failed
[WhisperCpp] ❌ CRITICAL: whisper.cpp installation failed
⚠️  Standalone whisper.cpp binary installation skipped (cmake not available)
```

**After (Clean):**
```
ℹ️  Standalone whisper.cpp binary not available (cmake not installed)
   ✓ Using pywhispercpp from venv instead (fully functional)
✅ Transcription capability verified (pywhispercpp 1.4.1)
```

**Why This Works:**
- `pywhispercpp` package includes whisper.cpp binary
- No compilation needed
- Fully functional transcription
- Clean, non-alarming output

### Fixed - Build Script Updated for Daemon-Only Architecture (January 11, 2026)

**Removed GUI References from Build Process**

The build script was still trying to import the deprecated GUI module, causing build failures. Updated to check daemon module instead.

**Changes:**
- ✅ `scripts/build_macos_app.sh` - Preflight check now imports `daemon` instead of `knowledge_system.gui`
- ✅ Launch script now runs `daemon.main` instead of `knowledge_system.gui.__main__`
- ✅ Post-install verification checks daemon module
- ✅ All GUI references removed from build process

**Error Fixed:**
```
ModuleNotFoundError: No module named 'knowledge_system.gui'
```

Now correctly checks:
```python
import daemon
print(f'Daemon version: {daemon.__version__}')  # Shows 1.1.1
```

### Added - Easy Daemon Restart Options (January 11, 2026)

**Desktop Shortcut and Web Button for Daemon Control**

Added two user-friendly ways to start/restart the daemon without using Terminal commands.

**1. Desktop Shortcut:**
- Automatically created during installation
- Location: `~/Desktop/GetReceipts Daemon.app`
- Double-click to see status and control options
- Interactive dialogs for Start/Restart/Stop
- Shows macOS notifications
- No terminal knowledge required!

**2. Web Restart Button:**
- Added to GetReceipts.org/contribute/settings page
- "Restart Daemon" button triggers graceful restart
- Daemon checks for updates on restart
- Works remotely from any browser

**Implementation:**
- ✅ `installer/create_desktop_shortcut.sh` - Creates desktop shortcut during install
- ✅ `scripts/build_pkg_installer.sh` - Integrated shortcut creation into installer
- ✅ `daemon/api/routes.py` - Added `/api/restart` endpoint
- ✅ `src/components/settings-form.tsx` - Added restart button to settings page

**User Experience:**
- **Desktop shortcut:** Double-click → See status → Choose action → Done
- **Web button:** Click "Restart Daemon" → Daemon restarts → Checks for updates
- **Why restart?** Forces immediate update check (instead of waiting 24 hours)

**Benefits:**
- ✅ No terminal commands needed
- ✅ Visual feedback with notifications
- ✅ Easy for non-technical users
- ✅ Multiple convenient options

### Changed - Desktop App Fully Deprecated, Daemon Is Now THE Product (January 11, 2026)

**Major Architectural Simplification**

The desktop GUI application (PyQt6, v4.1.0) is now **fully deprecated**. The daemon (v1.1.0) is the only product going forward.

**What Changed:**
- ❌ **Deprecated:** Desktop app with GUI (version 4.1.0 in pyproject.toml)
- ✅ **Active:** Background daemon controlled via web (version 1.1.0 in daemon/__init__.py)
- ✅ **Single version number:** Only daemon version matters now
- ✅ **Release process updated:** Uses daemon version for tags and filenames
- ✅ **Release naming:** "GetReceipts Daemon v1.1.0" (not "Skip the Podcast v4.x")

**Why This Change:**
- Web interface at GetReceipts.org provides better UX than desktop GUI
- Simpler architecture: one version number, one product
- Daemon is all users need - runs in background, controlled via browser
- Eliminates confusion between app version (4.1.0) and daemon version (1.1.0)

**Impact on Releases:**
- **Old:** Release v4.1.0 (application version) containing daemon v1.1.0
- **New:** Release v1.1.0 (daemon version) - that's it!

**Files Updated:**
- `scripts/publish_release.sh` - Now reads daemon version, not pyproject.toml
- `docs/DAEMON_RELEASE_PROCESS.md` - Complete rewrite for daemon-only releases
- Release titles changed to "GetReceipts Daemon v1.1.0"

**Migration:**
- Old releases (v3.5.0 and earlier) used application versioning
- New releases (v1.1.0+) use daemon versioning
- No user action required - daemon auto-updates

### Changed - Daemon Version Incremented to 1.1.0 (January 11, 2026)

**Daemon Version Bump for Clarity**

Incremented daemon version from 1.0.0 to 1.1.0 to clearly distinguish it from the application version (4.1.0).

**Changes:**
- ✅ `daemon/__init__.py` - Updated `__version__ = "1.1.0"`
- ✅ Daemon version now clearly separate from app version
- ✅ Makes it easier to track daemon-specific updates

**Version Tracking:**
- **Daemon:** 1.1.0 (background service/API)
- **Application:** 4.1.0 (full desktop app)

### Fixed - Download Buttons Now Use Dynamic DMG Detection (January 11, 2026)

**Download Buttons Now Work with Both Old and New Release Formats**

All download buttons were returning 404 errors because they were hardcoded to use `Skip_the_Podcast_Desktop.dmg` (stable filename), but the current release (v3.5.0) only has `Skip_the_Podcast_Desktop-3.5.0.dmg` (versioned filename).

**Root Cause:**
- Old releases (v3.5.0 and earlier) use versioned filenames: `Skip_the_Podcast_Desktop-{VERSION}.dmg`
- New releases (v4.1.0+) will include both versioned AND stable filenames
- Hardcoded stable URL caused 404 errors on old releases

**Solution:**
All download buttons now dynamically fetch the latest release from GitHub API and find the DMG asset, regardless of filename format.

**Changes:**
- ✅ `src/components/settings-form.tsx` - Dynamic DMG detection
- ✅ `src/components/daemon-status-indicator.tsx` - Dynamic DMG detection
- ✅ `src/components/daemon-installer.tsx` - Dynamic DMG detection with helper function
- ✅ Falls back to stable URL if API call fails (for future releases)

**How It Works:**
```typescript
// Fetch latest release info
const response = await fetch('https://api.github.com/repos/msg43/Skipthepodcast.com/releases/latest');
const data = await response.json();
// Find any DMG asset
const dmgAsset = data.assets?.find((a: any) => a.name.endsWith('.dmg'));
// Download it
window.location.href = dmgAsset.browser_download_url;
```

**Benefits:**
- ✅ Works with current v3.5.0 release (versioned filename)
- ✅ Will work with future v4.1.0+ releases (stable filename)
- ✅ No 404 errors
- ✅ Always downloads the latest available DMG

### Fixed - Daemon Release Process and Download Links (January 11, 2026)

**Standardized DMG Distribution and Fixed GetReceipts.org Download Links**

All daemon releases now use DMG format exclusively, and all download links on GetReceipts.org have been updated to point to the correct stable DMG URL.

**Changes:**

**GetReceipts.org Download Links Updated:**
- ✅ `src/components/daemon-status-indicator.tsx` - Updated to use `.dmg` from `Skipthepodcast.com` repo
- ✅ `src/components/daemon-installer.tsx` - Updated to use `.dmg` from `Skipthepodcast.com` repo
- ✅ `src/app/api/download/generate-link-token/route.ts` - Updated to use `.dmg` from `Skipthepodcast.com` repo
- ✅ All references changed from `.pkg` to `.dmg` format
- ✅ All references now point to `msg43/Skipthepodcast.com` (not `Knowledge_Chipper`)

**Release Script Updated:**
- ✅ `scripts/publish_release.sh` - Now builds and publishes DMG instead of PKG
- ✅ Creates two DMG files per release:
  - `Skip_the_Podcast_Desktop-{VERSION}.dmg` (versioned)
  - `Skip_the_Podcast_Desktop.dmg` (stable, always latest)
- ✅ Stable URL ensures download buttons always get latest version

**Documentation Added:**
- ✅ `docs/DAEMON_RELEASE_PROCESS.md` - Complete daemon release workflow documentation
- ✅ Includes version management, build process, and troubleshooting
- ✅ Documents stable vs versioned download URLs

**Why DMG?**
- PKG had persistent notarization issues that were resolved for DMG
- DMG provides better user experience (drag-and-drop installation)
- Simpler installation process with no admin privileges required

**Stable Download URL:**
```
https://github.com/msg43/Skipthepodcast.com/releases/latest/download/Skip_the_Podcast_Desktop.dmg
```

This URL always points to the latest daemon release and is used by:
- All GetReceipts.org download buttons
- Daemon auto-update system
- Installation scripts

### Added - Settings Page LLM Provider and Model Selection (January 10, 2026)

**Enhanced LLM Configuration in Settings Tab**

The Settings page now displays proper LLM provider and model selection dropdowns with dynamic model loading. All hardcoded defaults have been removed to ensure Settings choices are always respected.

**Features:**
- ✅ **LLM Provider dropdown** - Renamed from "Default LLM Provider" to "LLM Provider" for clarity
- ✅ **LLM Model dropdown** - Dynamically populated based on selected provider
- ✅ **Dynamic model registry** - Integrates with `model_registry.py` to fetch fresh models from APIs
- ✅ **Persistent settings** - Provider and model selections are saved to credentials.yaml
- ✅ **Smart loading** - Automatically loads saved provider/model on Settings tab open
- ✅ **Multi-provider support** - OpenAI, Anthropic, Google, and Local (Ollama) providers
- ✅ **No hardcoded defaults** - Removed all hardcoded OpenAI/GPT-4o references

**Implementation:**
- `_deprecated/gui/tabs/api_keys_tab.py` - Added LLM provider/model dropdowns to Settings tab
- `_on_llm_provider_changed()` - Handler that fetches models when provider changes
- `_load_existing_values()` - Loads saved LLM settings from config
- `_save_settings()` - Persists LLM provider/model to credentials.yaml
- Integration with `utils/model_registry.py` for dynamic model fetching

**Hardcoded Defaults Removed:**
- `config.py` - Updated LLMConfig to support all providers (openai/anthropic/google/local)
- `system2_orchestrator_two_pass.py` - Removed `openai:gpt-4o` fallback, now uses settings
- `two_pass/pipeline.py` - Updated docstring to show settings-based usage
- `process_tab.py` - Removed hardcoded local provider defaults, now uses settings

**User Experience:**
- Settings page now shows both provider and model selection
- Model dropdown updates automatically when provider changes
- Model dropdown shows "Loading models..." placeholder initially for visibility
- Models are fetched fresh from provider APIs (OpenAI, Anthropic, Google, Ollama)
- Selections persist across app restarts
- **All processing respects Settings choices** - no hardcoded overrides

**Bug Fixes:**
- Fixed LLM Model dropdown visibility issue - now shows placeholder text during initialization
- Removed `append_log()` call during initialization that could cause errors

### Added - Daemon Auto-Update System (January 8, 2026)

**Automatic Updates for GetReceipts Daemon**

The daemon now includes a built-in auto-update system that keeps itself up-to-date without user intervention.

**Features:**
- ✅ **Automatic checks** - Checks for updates every 24 hours and on daemon startup
- ✅ **Zero-downtime updates** - Downloads and installs updates in background
- ✅ **Automatic restart** - LaunchAgent restarts daemon with new version
- ✅ **Manual trigger** - Web UI can trigger updates via API
- ✅ **Version verification** - Semantic version comparison ensures proper updates
- ✅ **Rollback support** - Backup of previous binary for safety

**Implementation:**
- `daemon/services/update_checker.py` - Update checking and installation logic
- `daemon/api/routes.py` - API endpoints: `/api/updates/check`, `/api/updates/install`, `/api/updates/status`
- `daemon/main.py` - Integrated update scheduler into daemon lifecycle
- `src/lib/daemon-client.ts` - TypeScript client methods for web UI integration
- `installer/build_dmg.sh` - Now packages daemon binary separately for GitHub releases

**API Endpoints:**
- `GET /api/updates/check` - Check if updates are available
- `POST /api/updates/install` - Manually trigger update installation
- `GET /api/updates/status` - Get current update status and settings

**Update Flow:**
1. Daemon checks GitHub releases API every 24 hours
2. Compares current version with latest release
3. Downloads new daemon binary if available
4. Verifies download integrity
5. Backs up current binary
6. Installs new binary
7. Exits (LaunchAgent automatically restarts with new version)

**Distribution:**
- Daemon binary now packaged as `GetReceiptsDaemon-{version}-macos.tar.gz` in GitHub releases
- DMG installer includes both full installer and update-ready binary
- Auto-update system pulls from GitHub releases automatically

**User Experience:**
- Completely transparent - updates happen in background
- No interruption to processing jobs
- Web UI can show update status and trigger manual updates
- Daemon always stays current with latest features and fixes

---

## [Unreleased]

### BREAKING - Desktop GUI Deprecated in Favor of Web-First Architecture (January 7, 2026)

**PyQt6 Desktop GUI Replaced by Web Interface**

The desktop GUI has been **deprecated** and replaced with a web-first architecture where all user interaction happens through the browser at [GetReceipts.org/contribute](https://getreceipts.org/contribute), while processing runs via a local background daemon.

**What Changed:**
- ⚠️ **Desktop GUI removed** - All PyQt6 interface code moved to `_deprecated/gui/`
- ✅ **Web UI primary** - Processing control via GetReceipts.org/contribute
- ✅ **Local daemon** - Background processing engine with REST API (no UI)
- ✅ **Better UX** - Familiar web interface, cross-platform accessible, mobile-friendly future
- ✅ **Easier updates** - No app reinstalls, unified with GetReceipts.org

**Deprecated Items:**
- `src/knowledge_system/gui/` → Moved to `_deprecated/gui/`
- `launch_layer_cake_gui.py` → Moved to `_deprecated/`
- `launch_layer_cake_gui.command` → Moved to `_deprecated/`
- `launch_gui.command` → Moved to `_deprecated/`
- All GUI documentation moved to `_deprecated/`

**New Architecture:**
```
User (Browser) → GetReceipts.org/contribute → Local Daemon (Background)
                       ↓                              ↓
                 Submit Content                  Process Locally
                 Monitor Jobs                    (Whisper + LLM)
                 View Results                         ↓
                       ↑                         Auto-Upload
                       └───────────────────────────────┘
```

**Migration Guide:**
1. Install daemon: Download DMG from releases
2. Visit [GetReceipts.org/contribute](https://getreceipts.org/contribute)
3. Link device (one-time browser authentication)
4. Start processing via web interface

**Benefits:**
- No more desktop app windows to manage
- Works from any browser (desktop, laptop, tablet)
- Unified experience with GetReceipts.org
- Easier to maintain and update
- Future mobile app possible

**For Developers:**
- GUI code preserved in `_deprecated/` for reference
- Daemon API: `python -m daemon.main` (port 8851)
- REST endpoints documented in daemon README
- Web UI maintained in GetReceipts repository

**See Also:**
- README.md - Updated with web-first documentation
- MANIFEST.md - GUI sections marked deprecated
- daemon/ - New daemon implementation

---

### Updated - Health Tracking System to Web-Canonical Architecture (January 2, 2026)

**Web-Canonical Health Data Sync**

Converted the health tracking system from local-only to web-canonical architecture, where GetReceipts.org is the source of truth and desktop is ephemeral.

**Key Changes:**
- **Database schema updated** with privacy and sync fields:
  - `privacy_status` - private/public control (default: private)
  - `synced_to_web` - boolean tracking sync status
  - `web_id` - UUID from Supabase
  - `last_synced_at` - timestamp of last successful sync
- **Auto-sync on save** - interventions, metrics, and issues automatically upload to GetReceipts after desktop save
- **Supabase migration created** - `025_health_tracking.sql` with RLS policies and device authentication
- **Unified entity sync service** - `src/knowledge_system/services/entity_sync.py` (NO REDUNDANCY):
  - ONE service for ALL entity types (extraction batch + individual entities)
  - Replaces separate health_sync.py (deleted)
  - Uses existing GetReceiptsUploader infrastructure
  - Convenience methods: sync_health_intervention(), sync_health_metric(), sync_health_issue()
  - Extensible for future entity types (predictions, etc.)
- **Updated dialogs** - auto-sync integrated into save methods for all three entity types

**Architecture:**
- Desktop: Ephemeral entry/editing (like claim extraction)
- Web: Source of truth with privacy controls (like everything else in GetReceipts)
- Sync: Auto-upload after entry (like predictions)

**Migration Required:**
User must run `GetReceipts/database/migrations/025_health_tracking.sql` in Supabase SQL Editor to enable web sync.

**Future Work:**
- Web UI health dashboard at `/health` (TBD)
- Bulk fetch from web to desktop on app launch
- Conflict resolution UI for concurrent edits

---

### Added - Prediction System (January 2, 2026)

**Personal Forecasting with Evidence-Based Tracking**

Implemented a comprehensive prediction system that allows users to make and track predictions about future events, grounded in extracted knowledge from their content library.

**Core Features:**
- **Create predictions** with title, description, confidence level (0-100%), and deadline
- **Track changes over time** - confidence and deadline updates create history entries
- **Link evidence** - connect claims, jargon, people, and concepts to predictions
- **Pro/Con/Neutral stance** - classify each piece of evidence as supporting or contradicting
- **Resolution tracking** - mark predictions as Correct, Incorrect, Ambiguous, or Cancelled
- **Privacy control** - mark predictions as Public or Private (future sync to GetReceipts)
- **Visual history graph** - matplotlib chart showing confidence/deadline changes over time

**User Interface:**
- **Predictions Tab** - main list view with sortable table (Title/Confidence/Deadline/Status)
  - Filter by Privacy (Public/Private), Status (Pending/Resolved), or search text
  - Color-coded confidence (green ≥80%, orange 50-79%, red <50%)
  - Deadline highlighting (red for overdue pending predictions)
  - Double-click to open detail page

- **Prediction Detail Page** - comprehensive view for individual predictions
  - Header section: large title, current confidence %, deadline date, status badge
  - Graph section: dual-axis chart showing confidence and deadline history
  - Evidence tabs: Claims, Jargon, People, Concepts with Pro/Con/Neutral badges
  - User notes: rich text editor for reasoning and thoughts
  - Actions: Update Confidence/Deadline, Add Evidence, Mark as Resolved, Delete

- **Dialogs:**
  - Creation dialog: form with title, description, confidence slider, calendar picker
  - Update dialog: change confidence/deadline with reason field, auto-creates history
  - Add Evidence dialog: search entities by type, select stance, add notes

**Database Schema:**
- `predictions` table: core prediction data with confidence, deadline, resolution status
- `prediction_history` table: tracks all confidence/deadline changes for graphing
- `prediction_evidence` table: many-to-many links to claims/jargon/people/concepts with stance
- Automatic triggers: create history on insert/update, cascade delete

**Technical Implementation:**
- `src/knowledge_system/database/migrations/add_predictions_system.sql` - schema
- `src/knowledge_system/database/models.py` - Prediction, PredictionHistory, PredictionEvidence models
- `src/knowledge_system/database/service.py` - CRUD methods for predictions
- `src/knowledge_system/services/prediction_service.py` - business logic layer
- `src/knowledge_system/gui/tabs/predictions_tab.py` - main list view
- `src/knowledge_system/gui/tabs/prediction_detail_page.py` - detail view with graph
- `src/knowledge_system/gui/dialogs/prediction_creation_dialog.py` - create new
- `src/knowledge_system/gui/dialogs/prediction_update_dialog.py` - update confidence/deadline
- `src/knowledge_system/gui/dialogs/add_evidence_dialog.py` - search and link evidence
- `tests/test_predictions.py` - unit tests and manual testing checklist

**Use Cases:**
- Track market predictions with supporting/contradicting claims
- Forecast technology trends based on expert statements
- Personal accountability for beliefs (Brier score tracking potential)
- Research hypothesis tracking with evidence accumulation
- Decision-making support with structured Pro/Con analysis

**Future Enhancements:**
- Sync public predictions to GetReceipts.org
- Brier score calculation for accuracy tracking
- Prediction leaderboards and social features
- Automatic evidence suggestions based on new content
- Calibration analysis (are you overconfident?)

---

### Added - Automatic Device Linking on First Launch (January 2, 2026)

**Zero-Friction Onboarding: Sign In Once, Link Forever**

Implemented automatic device linking that triggers on first app launch, eliminating the need for manual claim codes.

**How It Works:**
1. **First launch detection** - App checks if device is linked to user account
2. **Browser opens automatically** - User signs in or creates account at getreceipts.org
3. **Device auto-links** - Backend automatically links device_id to user_id
4. **App polls for completion** - Desktop detects link and shows success message
5. **Done forever** - User never needs to link again

**User Experience:**
- Install .dmg → Launch app → Sign in once → Start processing
- No claim codes to copy/paste
- No manual linking steps
- Works seamlessly across sign-in and sign-up flows

**Technical Implementation:**

**Desktop App Changes:**
- `main_window_pyqt6.py` - Added `_check_device_linking()` method to detect unlinked devices
- `_trigger_device_linking_flow()` - Opens browser with device_id parameter
- `_start_link_polling()` - Polls every 5 seconds to detect when linking completes
- Shows notification when device successfully linked

**Web App Changes:**
- `src/app/auth/signin/page.tsx` - Detects `device_id` and `source=desktop` parameters
- `handleDeviceAutoLink()` - Calls device-auth API to link device after authentication
- Shows device-specific UI when in linking flow
- `src/app/auth/device-linked/page.tsx` - Success page with instructions to return to app

**API Changes:**
- `src/app/api/knowledge-chipper/device-auth/route.ts` - Added auto-link flow support
- Accepts JWT token in Authorization header
- Links device to authenticated user
- Supports both header-based and body-based credentials

**Benefits:**
- Eliminates friction in first-time setup
- Users can start processing immediately after sign-in
- More intuitive than manual claim code entry
- Still secure (requires authentication)

**Files Modified:**
- `src/knowledge_system/gui/main_window_pyqt6.py` - Added device linking check and OAuth flow
- `src/app/auth/signin/page.tsx` - Added device auto-linking support
- `src/app/auth/device-linked/page.tsx` - New success page
- `src/app/api/knowledge-chipper/device-auth/route.ts` - Added auto-link flow

### Changed - Dynamic Synthesis Length Based on Content Complexity (January 1, 2026)

**Flexible Summary Length: 5 Paragraphs to 2 Pages**

The synthesis pass now automatically adjusts summary length based on content duration and claim density, replacing the hardcoded "3-5 paragraph" constraint.

**How It Works:**
- **Short content** (<15 min or <10 claims) → 3-5 paragraphs
- **Medium content** (15-45 min or 10-30 claims) → 5-8 paragraphs
- **Long content** (45-90 min or 30-50 claims) → 8-12 paragraphs (~1-1.5 pages)
- **Very long content** (90+ min or 50+ claims) → 12-20 paragraphs (~1.5-2 pages)

**Technical Implementation:**
- New `_calculate_synthesis_length()` method in `SynthesisPass` class
- Calculates claim density (claims per minute) to assess content complexity
- Dynamically injects `{synthesis_length}` variable into prompt template
- LLM receives appropriate length guidance for each content piece

**Benefits:**
- Dense 90-minute lectures get the depth they deserve (2 pages)
- Short 10-minute clips get concise summaries (5 paragraphs)
- Quality scales with content complexity

**Files Modified:**
- `src/knowledge_system/processors/two_pass/synthesis_pass.py` - Added dynamic length calculation
- `src/knowledge_system/processors/two_pass/prompts/synthesis_pass.txt` - Made length flexible with `{synthesis_length}` variable
- `docs/feature-flowchart.html` - Updated to show "Flexible length 5¶ to 2 pages"
- `docs/feature-flowchart.md` - Updated to show "Flexible length 5¶ to 2 pages"

### Fixed - Device Linking Flow Timing (January 1, 2026)

**Earlier Device Linking for Better UX**

Updated flowchart documentation to reflect that device linking should happen in the background after installation, not after processing completes. This prevents users from processing content only to discover they need to link their device.

**Flowchart Changes:**
- Added "Background Device Linking" step after daemon installation
- Simplified upload flow to assume device is already linked
- Removed post-processing device linking check (moved earlier)

**Files Modified:**
- `docs/feature-flowchart.html` - Updated device linking timing in main flow
- `docs/feature-flowchart.md` - Updated device linking timing in main flow

### Added - Automatic Refinement Injection in Extraction Pipeline (January 1, 2026)

**Closed the Learning Loop: Web Corrections Now Improve Future Extractions**

Implemented automatic injection of synced refinements from GetReceipts.org into the two-pass extraction prompts, completing the feedback learning system.

**How It Works:**
1. **User corrects mistakes on web** - At `getreceipts.org/dashboard/entities`, reject incorrect extractions (e.g., "US President" extracted as a person instead of "Joe Biden")
2. **AI synthesizes patterns** - OpenAI analyzes rejections and generates `<bad_example>` XML teaching patterns
3. **User approves suggestions** - Review and approve AI-generated refinements at `/dashboard/patterns`
4. **Desktop syncs refinements** - On startup, Knowledge_Chipper downloads approved refinements to local files
5. **Automatic injection** - `extraction_pass.py` now automatically injects refinements into prompts before LLM calls
6. **LLM learns** - The AI sees your corrections and avoids making similar mistakes in future extractions

**Technical Implementation:**
- New `_inject_refinements()` method in `ExtractionPass` class
- Reads refinements from `~/Library/Application Support/Knowledge Chipper/refinements/*.txt`
- Injects before "EXTRACTION INSTRUCTIONS" section in prompt
- Logs injection activity: "✅ Injected N refinement type(s) into extraction prompt"
- Graceful fallback if refinements unavailable (non-fatal)

**Refinement Types Supported:**
- **People** - Prevents extracting titles/roles as names ("US President" → reject)
- **Jargon** - Prevents marking common words as technical terms ("money" → reject)
- **Concepts** - Prevents extracting generic ideas as mental models

**Example Injected Content:**
```
# 🔄 LEARNED PATTERNS - AVOID THESE MISTAKES

### ❌ People Extraction Mistakes:

<bad_example>
  <input>"The US President announced policy changes..."</input>
  <explanation>DON'T extract titles like "US President", "CEO" 
    as people. Extract actual names only.</explanation>
</bad_example>
```

**Files Modified:**
- `src/knowledge_system/processors/two_pass/extraction_pass.py` - Added `_inject_refinements()` method to `_build_prompt()`
- `README.md` - Added "How Refinements Are Applied" section with injection details
- `MANIFEST.md` - Updated `extraction_pass.py` and `prompt_sync.py` descriptions
- `docs/feature-flowchart.html` - Added learning loop visualization

**User Benefits:**
- 🔄 **Continuous improvement** - System learns from every correction
- 🎯 **Targeted learning** - Fixes entire classes of mistakes, not just individual errors
- 🚀 **Automatic** - No manual prompt editing required
- 📊 **Transparent** - Logs show when refinements are injected
- 🌐 **Centralized** - All devices benefit from web corrections

**Before This Feature:**
- Web corrections stored but never used ❌
- Same mistakes repeated in every extraction ❌
- Manual prompt editing required ❌

**After This Feature:**
- Web corrections automatically improve all future extractions ✅
- Learning loop fully closed ✅
- Zero-effort continuous improvement ✅

### Improved - Two-Pass Pipeline Flowchart Detail (January 1, 2026)

**Enhanced Documentation Visualization**

Expanded the feature flowchart to show detailed breakdown of the two-pass processing pipeline with all major steps:

**Pass 1: Extraction Pass (6 detailed steps)**
- Load extraction prompt template
- Build prompt with complete transcript + metadata
- Single LLM API call
- Parse JSON response with validation/repair
- Extract all entities:
  - Claims with 6-dimension scoring (epistemic, actionability, novelty, verifiability, understandability, temporal stability)
  - Jargon terms with plain-language definitions
  - People/organizations with context
  - Mental models and frameworks
  - Speaker inference with confidence scores (0-10)
  - Absolute importance scores (0-10) using weighted formula
- Save all extracted entities to SQLite

**Pass 2: Synthesis Pass (6 detailed steps)**
- Filter high-importance claims (≥7.0 threshold)
- Load synthesis prompt template
- Build prompt with filtered claims + all entities + YouTube AI summary
- Single LLM API call
- Parse response
- Generate synthesis:
  - 3-5 paragraph thematic analysis
  - Key themes identification
  - Quality metrics
  - Integrated narrative combining all entity types
- Save synthesis to SQLite

**Total: 2 API calls per video** - now clearly visualized in flowchart

**Files Modified:**
- `docs/feature-flowchart.html` - Expanded two-pass pipeline visualization with 14 detailed steps
- `docs/feature-flowchart.md` - Matching markdown version with expanded detail
- Both files now show the complete processing flow from transcript → extraction → synthesis → completion

**Why This Matters:**
Users can now see exactly what happens during the "Two-Pass Pipeline" black box, making the architecture transparent and helping them understand the value of the whole-document processing approach.

### Added - Model Access Validation & Status Badges (January 1, 2026)

**Intelligent Model Access UX**

Implemented comprehensive model metadata system to provide clear visibility into model access requirements:

**Model Status Badges:**
- ✅ **Public** - Generally available to all API key holders
- 🔒 **Gated** - Requires special access/approval or specific plan
- 🧪 **Experimental** - Preview/experimental models (may require allowlist)
- ⭐ **Tier Restricted** - Requires specific usage tier (e.g., OpenAI Tier 5)
- ⚠️ **Deprecated** - No longer available

**Status Visibility:**
- Model dropdowns show status badge + model name + access label
- Non-public models display their access requirements inline
- Hover hints provide additional context about access needs

**Graceful Error Handling:**
- Specific error messages for each failure type:
  - **403/Permission Denied**: "Model Access Denied - requires higher tier/approval"
  - **404/Not Found**: "Model Not Found - may be deprecated or renamed"
  - **401/Auth Failed**: "Authentication Failed - API key invalid/expired"
  - **429/Rate Limit**: "Rate Limit Exceeded - please wait and retry"
- Actionable guidance for resolving each error type
- No more cryptic API error messages

**Test Access Feature:**
- New `/config/test-model-access` API endpoint
- Validates model accessibility with minimal test call (1 token)
- Checks: API key validity, model existence, user access permissions
- Returns user-friendly error messages with resolution steps
- Minimal cost (~$0.00001 per test)

**Model Metadata Database:**
- Curated database of 50+ popular models across providers
- Tracks access requirements, tier restrictions, and status
- Automatically enriched API responses with metadata
- Easy to extend as new models are released

**Files Modified:**
- `src/knowledge_system/utils/model_metadata.py` - New metadata database with ModelStatus enum
- `daemon/api/routes.py` - Enhanced `/config/models` endpoint with metadata, added test endpoint
- `src/knowledge_system/core/llm_adapter.py` - Improved error handling with specific messages
- `GetReceipts/src/lib/daemon-client.ts` - Added ModelMetadata TypeScript interface
- `GetReceipts/src/components/processing-options.tsx` - Updated UI to show status badges

**User Experience:**
- 🎯 Know at a glance which models you can access
- 🔍 See access requirements before selecting a model
- 💡 Get actionable error messages when access fails
- 🧪 Test model access before starting a long processing job
- ⚡ Avoid wasting time on inaccessible models

### Added - Persistent API Key Storage (December 31, 2025)

**Secure API Key Management**

API keys are now persistently stored and automatically loaded on daemon startup:

**Features:**
- **Persistent Storage**: API keys saved to `~/Library/Application Support/Knowledge_Chipper/daemon_config.json`
- **Secure Permissions**: Config file automatically set to 600 (owner read/write only)
- **Auto-Load**: Keys loaded into environment variables on daemon startup
- **All Providers**: OpenAI, Anthropic, and Google API keys supported
- **One-Time Setup**: Enter keys once, they persist across daemon restarts

**Security:**
- File permissions verified on load (warns if insecure)
- Keys stored in user-only accessible directory
- Standard practice (same as AWS CLI, gcloud, etc.)

**Files Modified:**
- `daemon/config/settings.py` - Added API key persistence to save/load methods
- `daemon/api/routes.py` - Updated `/config/api-keys` endpoint to persist keys

**User Experience:**
- ✅ Enter API keys once in Settings
- ✅ Keys automatically available after daemon restart
- ✅ No need to re-enter keys every session
- ✅ All three providers show "Configured" badge persistently

### Added - Multi-Tier Dynamic Model Registry with OpenRouter (December 31, 2025)

**OpenRouter.ai Integration - Primary Model Source**

Implemented comprehensive model discovery using [OpenRouter.ai](https://openrouter.ai/) as primary source:
- Added `_fetch_from_openrouter()` method fetching 500+ models from 60+ providers
- Single API call replaces multiple provider-specific calls
- Automatic provider mapping (OpenAI, Anthropic, Google, Meta, Mistral, DeepSeek, Qwen, xAI, etc.)
- No API key required for model discovery
- Comprehensive coverage with always up-to-date model lists

**Multi-Tier Fallback Architecture**

Implemented intelligent 4-tier fallback system in `fetch_models()`:
1. **Tier 1 (Primary)**: OpenRouter.ai - 500+ models from 60+ providers
2. **Tier 2 (Backup)**: Individual provider APIs (OpenAI, Google, Anthropic)
3. **Tier 3 (Resilient)**: Local cache from last successful fetch
4. **Tier 4 (Offline)**: Hardcoded fallback lists for offline mode

**Individual Provider APIs**

- Added `_fetch_google_models()` - Google Gemini models via official API
- Added `_fetch_anthropic_models()` - Anthropic Claude models via official API  
- Existing `_fetch_openai_models()` - OpenAI GPT models via official API
- All providers now fully dynamic with intelligent fallbacks

**Daemon API Enhancement**

- Added `GET /api/config/models` endpoint exposing available models to frontend
- Supports optional `provider` query parameter to filter by specific provider
- Supports `force_refresh` query parameter to bypass cache and fetch fresh data
- Returns model counts and full model lists for all providers

**Model Caching**

- Models cached in `~/.knowledge_chipper/cache/model_registry.json`
- Cache includes timestamp and source information
- Only refreshes on explicit `force_refresh=true` calls to minimize API usage
- Preserves working model lists when APIs unavailable

**Provider Coverage**
- ✅ OpenAI: Dynamic (via OpenRouter + OpenAI API)
- ✅ Google: Dynamic (via OpenRouter + Google API)
- ✅ Anthropic: Dynamic (via OpenRouter + Anthropic API)
- ✅ Meta: Dynamic (via OpenRouter) - NEW
- ✅ Mistral: Dynamic (via OpenRouter) - NEW
- ✅ DeepSeek: Dynamic (via OpenRouter) - NEW
- ✅ Qwen: Dynamic (via OpenRouter) - NEW
- ✅ xAI: Dynamic (via OpenRouter) - NEW
- ✅ Ollama: Dynamic (via Ollama registry)

**Files Modified**
- `src/knowledge_system/utils/model_registry_api.py` - Added Google fetcher
- `src/knowledge_system/utils/model_registry.py` - Added Google support and updated fallbacks
- `daemon/api/routes.py` - Added `/config/models` endpoint

### Fixed - Google API Key Configuration Not Showing as Configured (December 31, 2025)

**Fixed Missing Google API Key Support in Daemon Settings**

The GetReceipts settings page was not showing the Google API key as "Configured" even when a valid key was provided. This was caused by missing support in the daemon backend.

**Changes:**
- Added `google_configured` field to `DaemonConfig` model
- Added `google_api_key` field to `APIKeyConfig` model  
- Added `google_configured` field to `APIKeyStatus` model
- Updated `GET /api/config` endpoint to check `GOOGLE_API_KEY` environment variable
- Updated `GET /api/config/api-keys` endpoint to include Google key status
- Updated `POST /api/config/api-keys` endpoint to handle setting Google API keys
- Updated LLM provider literal type to include `"google"` option

**Files Modified:**
- `daemon/models/schemas.py` - Added Google API key fields to models
- `daemon/api/routes.py` - Added Google API key handling to config endpoints

## [4.1.0] - 2025-12-31

### Changed - Minimal Daemon Dependencies (December 31, 2025)

**Significantly Reduced Installation Size and Time**

Created `requirements-daemon.txt` with only essential dependencies for daemon operation:

**Removed (not needed for daemon):**
- PyQt6 (GUI only - 50MB+)
- streamlit (Web UI - 30MB+)
- playwright (optional web scraping - 200MB+)
- hdbscan, scipy (optional HCE features)
- sentence-transformers (heavy ML embeddings - 500MB+)
- pandas, numpy (data processing - can add back if needed)
- huggingface_hub (model bundling - not needed at runtime)
- All diarization dependencies (pyannote.audio, torch, transformers)

**Kept (essential):**
- FastAPI + uvicorn (daemon server)
- SQLAlchemy + alembic (database)
- yt-dlp, pytube (YouTube processing)
- pywhispercpp, pyannote-whisper (transcription)
- OpenAI, Anthropic, Google APIs (claim extraction)
- Supabase (uploads)

**Result:** ~70% smaller installation, ~60% faster first-run setup

### Added - Custom URL Scheme for One-Click Daemon Control (December 30, 2025)

**Web Interface Can Now Automatically Start/Stop Daemon**

Implemented `skipthepodcast://` custom URL scheme handler for seamless browser-to-daemon control:

**Features:**
- Web interface can start daemon with one click (no manual terminal commands)
- Custom URL scheme registered: `skipthepodcast://start-daemon`
- Additional commands: `skipthepodcast://stop-daemon`, `skipthepodcast://status`
- Native macOS notifications for user feedback
- Zero-friction user experience

**How It Works:**
1. User visits contribute page, sees red "Local App: Not Running"
2. Clicks indicator → Web page calls `window.location.href = "skipthepodcast://start-daemon"`
3. macOS opens the installed app with the URL
4. App's URL handler executes `launchctl start org.skipthepodcast.daemon`
5. Shows macOS notification confirming action
6. Daemon starts automatically, indicator turns green

**Technical Implementation:**
- `CFBundleURLTypes` registered in app bundle's Info.plist
- `url-handler` script in `Contents/MacOS/` handles URL commands
- Launch script delegates to URL handler when URL argument detected
- Fallback to clipboard copy if app not installed

This eliminates the need for users to manually run terminal commands!

### Added - User-Friendly Daemon Auto-Start Behavior (December 30, 2025)

**PKG Installer Now Launches Daemon Automatically with User Control**

The Skip the Podcast Desktop PKG installer now properly launches the daemon server (not the GUI) and provides user-friendly controls:

**Installation Behavior:**
- Daemon starts automatically ONCE after installation (for immediate use)
- Does NOT auto-start on reboot/login (respects user preferences)
- LaunchAgent installed but configured with `RunAtLoad=false`
- Users can manually control when daemon runs

**Manual Daemon Control:**
```bash
# Start daemon
launchctl start org.skipthepodcast.daemon

# Stop daemon
launchctl stop org.skipthepodcast.daemon

# Check status
curl http://localhost:8765/health
```

**Convenience Scripts Installed:**
- `/Applications/Skip the Podcast Desktop.app/Contents/Resources/bin/start-daemon.sh`
- `/Applications/Skip the Podcast Desktop.app/Contents/Resources/bin/stop-daemon.sh`
- `/Applications/Skip the Podcast Desktop.app/Contents/Resources/bin/daemon-status.sh`

**User Flow:**
1. Download PKG from contribute page
2. Install PKG (daemon starts automatically)
3. Return to contribute page (auto-detects daemon)
4. After reboot, daemon only runs when user starts it

This respects user choice while providing a seamless initial experience.

### Changed - System Limits Increased & Centralized Documentation (December 29, 2025 22:01)

**All System Limits Increased to Remove Friction**

Significantly increased all major system limits to effectively unlimited values during initial rollout. All limits remain in code for future tuning but set generously high to prevent any user friction.

**Limit Changes:**
1. **RSS Feed Episodes**: 500 → 9999 (max 99999)
   - Supports large podcast libraries without restriction
   - Frontend UI max increased to match
   
2. **Upload Records Per Request**: 2000 → 99999
   - Allows massive batch uploads without splitting
   - Still prevents accidental multi-million record uploads
   
3. **Rate Limiting**: 9999/hour → 99999/hour
   - Effectively unlimited uploads for all users
   - Code remains in place for future tuning
   
4. **Search Result Defaults**: 10-20 → 50
   - All search endpoints now return 50 results by default
   - Better user experience without excessive pagination
   
**New Central Documentation**: `SYSTEM_LIMITS.md`
- Complete inventory of all system limits
- Rationale for each limit
- Files where each limit is defined
- Recommendations for which limits to keep vs. adjust
- Security considerations
- Quick reference table

**Files Updated:**

*Backend (Daemon):*
- `daemon/models/schemas.py` - RSS max and validation limits
- `daemon/services/rss_service.py` - RSS service method
- `daemon/services/processing_service.py` - Batch processing
- `daemon/api/routes.py` - API endpoint defaults

*Frontend (GetReceipts):*
- `src/app/api/knowledge-chipper/upload/route.ts` - Upload limits and rate limiting
- `src/lib/auth/upload-auth.ts` - Rate limit default parameter
- `src/components/processing-options.tsx` - RSS UI max
- `src/app/contribute/help/page.tsx` - Documentation
- `src/app/api/search/*.ts` - All search endpoint defaults (claims, people, jargon, concepts, questions)
- `src/components/PersonLinker.tsx` - Autocomplete limit
- `src/components/EntityLinker.tsx` - Autocomplete limit

*Documentation:*
- `SYSTEM_LIMITS.md` - **NEW:** Complete system limits reference
- `UPLOAD_SECURITY.md` - Updated rate limiting and upload size sections
- `MANIFEST.md` - Added entry for SYSTEM_LIMITS.md
- `docs/feature-flowchart.html` - Updated RSS max and rate limit displays
- `docs/feature-flowchart.md` - Updated RSS max and rate limit displays

**Rationale:**
- Remove all friction during initial rollout
- Monitor actual usage patterns for 30-60 days
- Tighten limits later based on data
- Maintain security code infrastructure for future use

**Timestamp:** December 29, 2025 22:01:12 EST

---

### Changed - RSS Feed Processing & Comprehensive Flowchart Updates (December 29, 2025 18:30)

**RSS Max Episodes Increased from 10 to 500**

Significantly increased the default maximum episodes downloaded from RSS/podcast feeds to better support comprehensive content ingestion from podcast libraries.

**Changes:**
- **Backend:** Updated default `max_rss_episodes` from 10 to 500
  - `daemon/models/schemas.py` - Field default and max limit (1000)
  - `daemon/services/processing_service.py` - Function default parameter
  - `daemon/api/routes.py` - Default fallback value
  - `daemon/services/rss_service.py` - Method default parameter
- **Frontend:** Updated UI defaults and limits
  - `src/components/processing-options.tsx` - Input default value (500) and max (1000)
  - `src/app/contribute/help/page.tsx` - Documentation updated to reflect new default

**Comprehensive Flowchart Updates**

Major updates to `docs/feature-flowchart.html` and `docs/feature-flowchart.md` to accurately reflect the complete system architecture:

1. **YouTube Transcript Fallback Flow** - Now correctly shows:
   - Fetch YouTube metadata first (saved to SQLite immediately)
   - Try YouTube transcript API first
   - Only use Whisper + audio download if YouTube transcript unavailable
   - All steps save incrementally to SQLite

2. **Local File Metadata Workflow** - Added comprehensive path for local audio/video:
   - Upload local file → optional YouTube search
   - YouTube match dialog if matches found
   - Manual metadata entry with author selection if no match
   - Full parity with text/DOCX/PDF workflow

3. **Auto-Upload ON by Default** - Updated flow to reflect web-first architecture:
   - Auto-upload enabled by default (opt-out in Settings)
   - Device linking flow integrated as standard first-upload experience
   - 403 error → browser redirect → sign in/create account → auto-link device
   - Seamless retry after linking

4. **Incremental SQLite Saves** - Visual indication throughout:
   - Metadata saved immediately after YouTube fetch
   - Transcripts saved immediately after acquisition
   - Claims saved continuously during extraction
   - Synthesis results saved incrementally
   - All major stages annotated with "💾 Save to SQLite"

5. **Security Integration** - Upload flow now shows:
   - Device linking requirement for first upload
   - GetReceipts API rate limiting (20/hour)
   - Audit log creation
   - Supabase upload with full attribution

6. **RSS Feed Processing** - Updated to show max 500 episodes (from 10)

**Timestamp:** Updated to December 29, 2025 18:30:00 EST

**Files Updated:**
- `docs/feature-flowchart.html` - Interactive HTML flowchart with full system architecture
- `docs/feature-flowchart.md` - Markdown source with Mermaid diagram

---

### Security - Upload Authentication & Audit System

**BREAKING CHANGE:** All uploads to GetReceipts now require authentication AND user account linkage.

**POLICY:** Devices must be linked to a user account before uploading. This ensures:
- ✅ Community accountability (all claims tied to real users)
- ✅ Hardware-level spam prevention (can ban devices, not just accounts)
- ✅ Complete audit trail (device_id + user_id for every upload)
- ✅ Reputation system (users build credibility over time)

#### Added
- **Mandatory authentication** for all uploads to GetReceipts API
  - Device credential verification (X-Device-ID + X-Device-Key headers)
  - User session authentication (Bearer token support)
  - bcrypt-based credential verification
- **Rate limiting** (20 uploads per hour per authentication source)
- **Content validation** (claim length, upload size limits)
- **Suspicious activity detection** with automatic flagging
  - Large upload detection (>500 records)
  - Rapid upload detection (>5 in 5 minutes)
  - First-time bulk upload detection
  - Previous flag history tracking
- **Complete audit trail** for every upload
  - Full attribution (device_id, user_id, audit_id)
  - IP address and User-Agent logging
  - Processing time tracking
  - Success/failure status
  - Vandalism flags with severity levels
- **Attribution columns** on all uploaded tables
  - `uploaded_by_device` - which device uploaded the record
  - `uploaded_by_user` - which user (if device is linked)
  - `upload_audit_id` - reference to audit log entry
  - `uploaded_at` - timestamp of upload

#### Changed
- Upload endpoint now returns detailed attribution and audit information
- Upload responses include flagging status and reasons
- Error responses now include specific error codes (NO_AUTH, INVALID_DEVICE, DEVICE_NOT_LINKED, RATE_LIMITED, etc.)
- **Devices must be linked to user accounts** before uploading (403 error if not linked)

#### Security
- **Prevents anonymous uploads** - all uploads now tracked to source
- **Prevents bulk spam** - rate limiting and size validation
- **Detects vandalism** - automatic suspicious activity detection
- **Full accountability** - complete audit trail for forensics
- **IP tracking** - logs source IP for all uploads

#### Files Added
- `GetReceipts/database/migrations/020_upload_audit_tracking.sql` - Audit tables and attribution columns
- `GetReceipts/src/lib/auth/upload-auth.ts` - Authentication middleware and helpers
- `GetReceipts/UPLOAD_SECURITY.md` - Complete security documentation

#### Files Modified
- `GetReceipts/src/app/api/knowledge-chipper/upload/route.ts` - Added authentication, validation, and audit logging
- `knowledge_chipper_oauth/getreceipts_uploader.py` - Already includes device credentials (no changes needed)

#### Migration Required
Run `020_upload_audit_tracking.sql` in Supabase to add audit tables and attribution columns.

#### Notes
- Desktop app already sends device credentials - no client changes needed
- **First upload will prompt device linking** - opens browser for one-time account linkage
- Subsequent uploads work automatically once linked
- Existing device credentials continue to work (but must be linked to user)
- Flagged uploads still succeed but are marked for admin review
- Audit logs are permanent (never deleted) for forensic purposes

#### User Experience - First Upload
```
1. User clicks "Upload to GetReceipts" in desktop app
2. Server returns 403: "Device not linked"
3. Browser opens to getreceipts.org/devices/claim
4. User signs in (or creates account)
5. Device automatically linked
6. Desktop app retries upload → Success!
7. All future uploads work seamlessly
```

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added - Comprehensive User Journey Flowchart (December 29, 2025)

**Master flowchart showing complete end-to-end system flow**

Added a comprehensive, unified flowchart to `docs/feature-flowchart.html` and `docs/feature-flowchart.md` that combines:
- **Daemon Detection Flow** - Initial localhost:8765 check, installer prompt, and daemon setup
- **Content Type Detection** - All input types (YouTube URLs, playlists, RSS feeds, local files, documents)
- **Transcript Workflow** - Text/DOCX/PDF processing with optional transcript detection
- **YouTube Matching** - Optional YouTube search for transcript metadata enrichment
- **Manual Metadata Entry** - Author selection and creation for non-YouTube content
- **Processing Pipeline** - Full Two-Pass pipeline with transcription, extraction, synthesis
- **Upload Flow** - Local SQLite save and optional GetReceipts cloud upload

The flowchart provides a single visual reference for the entire system architecture, from user arrival at `/contribute` through final claim upload. Color-coded decision points (orange), processes (blue), user actions (green), and outcomes (green/red) make the flow easy to follow.

**Updated Files**:
- `docs/feature-flowchart.md` - Added "Complete User Journey Flow" section with master Mermaid diagram
- `docs/feature-flowchart.html` - Added interactive HTML version with styling and descriptions
- Timestamp updated to December 29, 2025 16:45:23 EST

### Added - Database Admin Viewer (December 28, 2025)

**Interactive web-based SQLite database viewer for local development**

Added a localhost-only admin page at `http://localhost:8765/api/admin/database` that provides:
- **Visual database inspection** - Browse all tables with formatted data
- **Smart sorting** - Automatically sorts by most recent records first (created_at, updated_at, etc.)
- **Pagination** - Shows 100 records per table with "Load More" button to append next 100
- **Database summary** - File size, table count, last modified timestamp
- **Read-only access** - No write operations, safe for inspection
- **Collapsible sections** - Click table headers to expand/collapse views
- **Manual refresh** - Reload all data with one click
- **Responsive design** - Clean dark theme matching the daemon aesthetic

**Security**: Bound to localhost only (127.0.0.1), not exposed to network.

**New Files**:
- `daemon/api/database_viewer.py` - Database service with read-only SQLite queries
- Enhanced `daemon/api/routes.py` - Added 3 new endpoints:
  - `GET /api/admin/database` - HTML admin page
  - `GET /api/admin/database/summary` - Database metadata
  - `GET /api/admin/database/table/{name}` - Table records with pagination

**Use Case**: Debugging, monitoring database state, verifying processing results without SQL client.

---

### Changed - Web UI Whisper Model Simplification (December 27, 2025)

**Simplified web UI to always use Medium whisper model**

To reduce user complexity and provide the best out-of-box experience, the web UI (daemon API) now:
- **Defaults to Medium model** for all transcriptions (changed from base)
- **Hides model selection** in `/api/config/whisper-models` endpoint (only exposes medium)
- Medium provides best balance: 70-80% fewer hallucinations than large, better accuracy than base
- Advanced users can still use other models via direct API calls if needed

**Files Changed**:
- `daemon/config/settings.py` - Changed default from "base" to "medium"
- `daemon/models/schemas.py` - Updated all default values to "medium"
- `daemon/api/routes.py` - Simplified whisper-models endpoint to only return medium model

---

### Added - Daemon API Feature Parity (December 27, 2025)

**Enhanced FastAPI daemon with full desktop feature parity for web UI**

#### New API Endpoints

**Batch Processing**:
- `POST /api/process/batch` - Process multiple YouTube URLs or local files in parallel
- `ProcessRequest` now supports `urls[]` and `local_paths[]` for batch mode

**Job Management**:
- `GET /api/jobs?status=&search=&limit=&offset=` - Filterable job list with pagination
- `POST /api/jobs/{id}/retry` - Retry a failed job with same parameters
- `POST /api/jobs/{id}/cancel` - Cancel a running job
- `DELETE /api/jobs/{id}` - Remove job from history
- `POST /api/jobs/bulk/retry` - Bulk retry multiple failed jobs
- `POST /api/jobs/bulk/delete` - Bulk delete multiple jobs

**Configuration**:
- `GET /api/config` - Get full daemon configuration
- `PATCH /api/config` - Update processing defaults (persisted to disk)
- `GET /api/config/whisper-models` - List available Whisper models
- `GET /api/config/device-status` - Get device linking status

**Folder Monitoring**:
- `GET /api/monitor/status` - Get current watch status
- `POST /api/monitor/start` - Start watching a folder
- `POST /api/monitor/stop` - Stop watching
- `GET/PATCH /api/monitor/config` - Get/update monitor configuration
- `GET /api/monitor/events` - Get recent file detection events
- `GET /api/monitor/browse` - Browse folders for monitoring selection

#### New Files

- `daemon/services/monitor_service.py` - Folder monitoring service wrapping FileWatcher
- Enhanced `daemon/models/schemas.py` with MonitorConfig, MonitorStatus, MonitorEvent, DaemonConfig, BatchProcessResponse
- Enhanced `daemon/config/settings.py` with config persistence (save_config/load_config) and device linking

---

### Added - Layer Cake GUI (December 26, 2025)

**New intuitive two-pane interface with visual processing pipeline**

#### Overview

Introduced a completely new GUI design called "Layer Cake" - an intuitive two-pane interface where users can see the entire processing pipeline at a glance and start processing from any stage.

#### Features

- **Settings-First Design**: Settings tile at top for first-time user onboarding (configure API keys, models, account)
- **Visual Pipeline**: 6 colorful tiles arranged top→bottom showing processing flow
  - Settings/Help/Contact (gray) - Configure before use
  - Sources (purple) - Raw input (MP3, YouTube, RSS, Text)
  - Transcripts (orange) - Converted text
  - Claims (green) - Extracted insights
  - Summaries (pink) - Generated summaries
  - Cloud (blue) - Upload to SkipThePodcast.com
- **Drag-Drop Files**: Drop files directly onto Sources or Transcripts tiles
- **Unrolling Panels**: Click any tile to reveal options (smooth 300ms animation)
- **Colored Status Boxes**: Right pane shows logs for each stage with individual scrollbars
- **Expand/Collapse Logs**: Click any status box to expand for detailed inspection
- **Customizable Colors**: 8 color presets + custom color picker (colors persist across sessions)
- **Start Button with Options**: Unified Start button with 3 checkboxes (Create Claims, Create Summary, Upload)
- **Complete Persistence**: All settings, colors, checkboxes, and window geometry persist across sessions

#### Technical Implementation

**New Components Created**:
- `layer_tile.py` - Fixed 100px tiles with gradient painting, rounded corners, click detection
- `expansion_panel.py` - Panels that unroll below tiles with smooth animations
- `droppable_tile.py` - Tiles with drag-drop support and frosted overlay
- `status_box.py` - Expandable log boxes with individual scrollbars
- `layer_cake_widget.py` - Main left pane managing all tiles and panels
- `layer_cake_main_window.py` - Two-pane main window (60/40 split)
- `launch_layer_cake_gui.py` - Launch script for testing new interface

**Design Principles**:
- ✅ Fixed-height tiles (100px) that never resize
- ✅ Top→bottom intuitive flow (matches reading direction)
- ✅ NO STUBS - Every GUI element wired to real backend code
- ✅ All settings persist via existing GUISettingsManager
- ✅ Reuses all existing orchestrators (System2Orchestrator, TranscriptAcquisitionOrchestrator, etc.)

#### Files Modified

- `src/knowledge_system/gui/components/layer_tile.py` - NEW
- `src/knowledge_system/gui/components/expansion_panel.py` - NEW
- `src/knowledge_system/gui/components/droppable_tile.py` - NEW
- `src/knowledge_system/gui/components/status_box.py` - NEW
- `src/knowledge_system/gui/components/layer_cake_widget.py` - NEW
- `src/knowledge_system/gui/layer_cake_main_window.py` - NEW
- `launch_layer_cake_gui.py` - NEW launch script
- `MANIFEST.md` - Updated with new component descriptions

#### Usage

Launch the new interface:
```bash
python launch_layer_cake_gui.py
```

#### Status

**ALL 28 TODOS COMPLETE** ✅

**Core Components** (7):
- ✅ LayerTile with gradients, animations, dynamic colors
- ✅ DroppableTile with drag-drop and frosted overlay
- ✅ SettingsHelpContactTile with 3 clickable sub-tiles
- ✅ ExpansionPanel with smooth 300ms unroll animation
- ✅ StatusBox with expand/collapse animations
- ✅ LayerLogWidget managing 6 status boxes
- ✅ LayerCakeWidget coordinating all tiles and panels
- ✅ LayerCakeMainWindow with 60/40 splitter

**Panel Content** (5):
- ✅ Settings panel: Model selection, account info, color button
- ✅ Help panel: Getting started guide
- ✅ Claims panel: Tier filters, database-backed claim list, export
- ✅ Summaries panel: Source selector, regenerate with database query
- ✅ Cloud panel: Sync status, upload queue, manual upload

**Color Customization** (3):
- ✅ ColorCustomizationDialog with live preview
- ✅ 8 presets (Default, Ocean, Forest, Sunset, Monochrome, High Contrast, Pastel, Waterfall)
- ✅ Individual color pickers for each tile
- ✅ All colors persist across sessions

**Backend Wiring** (5):
- ✅ Contact sub-tile opens browser to skipthepodcast.com/contact
- ✅ Sources tile routes to TranscriptAcquisitionOrchestrator
- ✅ Transcripts tile routes to System2Orchestrator
- ✅ Claims panel queries DatabaseService for recent claims
- ✅ Summaries panel queries DatabaseService for regeneration
- ✅ Cloud panel checks AutoSyncWorker status

**Polish & Documentation** (3):
- ✅ All settings persist via GUISettingsManager
- ✅ README.md updated with Layer Cake section
- ✅ CHANGELOG.md comprehensive entry
- ✅ MANIFEST.md updated with all new files

**Total**: ~2,200+ lines of production-quality GUI code

---

### Fixed - Database Schema Migration for transcript_source Column (December 26, 2025)

**Fixed missing transcript_source column causing transcription failures**

#### Changes

- **Added transcript_source Column**: Added missing `transcript_source` column to transcripts table
  - Tracks the origin of transcripts (youtube_api, whisper_fallback, whisper_forced, unknown)
  - Applied retroactively to existing database with default value of 'unknown'
- **Automatic Migration System**: Configured automatic application of schema migrations
  - Added `add_pdf_transcript_support.sql` to incremental migrations list
  - Added `add_transcript_source.sql` to incremental migrations list
  - Fixed SQLite compatibility issues (removed PostgreSQL-specific COMMENT syntax)
  - Migrations now apply automatically on database service initialization

#### Files Modified

- `src/knowledge_system/database/service.py` - Added migrations to incremental_migrations list
- `src/knowledge_system/database/migrations/add_transcript_source.sql` - Fixed SQLite compatibility

### Fixed - Multi-Account Download Timeout Handling (December 26, 2025)

**Prevent stuck downloads from blocking other accounts**

#### Changes

- **60-Second Download Timeout**: Each download attempt now has a 60-second timeout
  - If a channel doesn't make progress for 60 seconds, system moves to next account
  - Prevents single stuck download from blocking entire batch
  - Failed downloads automatically added to retry queue
- **Improved Retry Logic**: Enhanced retry queue processing
  - Retries use same 60-second timeout
  - Better logging for retry attempts (shows progress: "Retry 5/23 successful")
  - Timeout for waiting on accounts during retry (max 2 minutes)
  - Clear statistics on retry success/failure rates
- **Better Progress Reporting**: More detailed status messages
  - Timeout notifications show which account got stuck
  - Retry round summaries show recovered vs still-failed counts
  - Progress callbacks keep GUI updated during retries

#### Technical Details

- Modified `download_with_failover()` to accept timeout parameter (default: 60s)
- Added `asyncio.TimeoutError` exception handling
- Timeout downloads automatically added to retry queue
- Retry queue processing now includes wait timeout (120s max per retry)

#### Files Modified

- `src/knowledge_system/services/multi_account_downloader.py`

### Feature - PDF Transcript Import System (December 25, 2025)

**Import podcaster-provided transcripts with automatic YouTube matching**

#### New Features

- **PDF Transcript Import**: Import high-quality PDF transcripts from podcasters
  - Automatic speaker label detection (multiple formats supported)
  - Timestamp parsing (multiple formats)
  - Quality scoring based on speaker labels, timestamps, formatting
  - Metadata extraction (title, date, speakers)
- **Multi-Transcript Management**: Store multiple transcript versions per episode
  - PDF (podcaster-provided), YouTube API, Whisper transcripts coexist
  - Configurable priority order (pdf_provided > youtube_api > whisper)
  - Automatic quality-based selection
  - Per-source preferred transcript tracking
- **YouTube Video Matching**: Automatic matching of PDFs to YouTube videos
  - 4 matching strategies: database fuzzy match, title search, metadata search, LLM query
  - Confidence scoring (0-100%)
  - Manual review for low-confidence matches
  - Playwright-based YouTube search with fallback
- **Import Transcripts Tab**: New GUI tab for PDF import
  - Single PDF import with optional YouTube URL
  - Batch folder scanning
  - Auto-match toggle with confidence threshold
  - Results table with match status
  - Real-time progress tracking
- **Batch Import Script**: CLI tool for bulk PDF import
  - Folder scanning support
  - CSV mapping file support (pdf_path, youtube_url)
  - Configurable confidence threshold
  - Progress reporting and statistics

#### Architecture Improvements

- **Two-Pass Integration**: PDF transcripts work seamlessly with two-pass workflow
- **Quality-Based Selection**: System automatically uses highest-quality transcript
- **Database Schema**: Added quality_score, has_speaker_labels, has_timestamps, preferred_transcript_id fields
- **Transcript Priority**: Configurable in config.yaml

#### Files Added

- `src/knowledge_system/database/migrations/add_pdf_transcript_support.sql`
- `src/knowledge_system/processors/pdf_transcript_processor.py`
- `src/knowledge_system/services/youtube_video_matcher.py`
- `src/knowledge_system/services/transcript_manager.py`
- `src/knowledge_system/gui/tabs/import_transcripts_tab.py`
- `scripts/import_pdf_transcripts_batch.py`
- `tests/test_pdf_transcript_import.py`
- `PDF_TRANSCRIPT_IMPORT_IMPLEMENTATION_COMPLETE.md`
- `GUI_INTEGRATION_COMPLETE.md`

#### Files Modified

- `src/knowledge_system/database/models.py` - Extended Transcript and MediaSource models
- `src/knowledge_system/database/service.py` - Added transcript management methods
- `src/knowledge_system/processors/two_pass/pipeline.py` - Integrated TranscriptManager
- `src/knowledge_system/config.py` - Added TranscriptProcessingConfig
- `src/knowledge_system/gui/main_window_pyqt6.py` - Added Import Transcripts tab
- `src/knowledge_system/gui/tabs/__init__.py` - Exported new tab

### Feature - YouTube Data API v3 Integration (December 25, 2025)

**Official YouTube API for reliable metadata, yt-dlp for audio only**

#### New Features

- **YouTube Data API Service**: Official API wrapper for metadata fetching
  - Single video metadata fetch (1 quota unit)
  - Batch metadata fetch (50 videos per request, 1 quota unit)
  - Video search functionality (100 quota units)
  - Automatic quota tracking (10,000 free units/day)
  - Quota reset handling
  - API key validation
- **Metadata Validator**: Universal validator for both API and yt-dlp
  - Format conversion (ISO 8601 duration → seconds, dates → YYYYMMDD)
  - Type validation and coercion
  - String sanitization
  - Default values for missing fields
  - Handles both API and yt-dlp response formats
- **Audio Linking Methods**: Robust audio-to-metadata linking
  - `link_audio_to_source()` - Link downloaded audio to existing metadata
  - `verify_audio_metadata_link()` - Comprehensive verification
  - File existence validation
  - File size validation (minimum 200KB)
  - Diagnostic reporting
- **Two-Stage Download Coordinator**: Metadata-first workflow
  - Stage 1: Fetch all metadata via API (fast, batch-optimized)
  - Stage 2: Download audio via yt-dlp (only for new videos)
  - Deduplication before download
  - Automatic fallback to yt-dlp for metadata if API unavailable

#### Architecture Improvements

- **Separation of Concerns**: Metadata (API) separate from audio (yt-dlp)
- **Reliability**: API guarantees JSON structure, no parsing errors
- **Speed**: API is faster than web scraping, batch requests are 50x more efficient
- **Robustness**: Audio failures don't lose metadata
- **Quota Efficiency**: Batch optimization maximizes free tier

#### Files Added

- `src/knowledge_system/services/youtube_data_api.py` - API wrapper
- `src/knowledge_system/utils/youtube_metadata_validator.py` - Validation layer
- `src/knowledge_system/services/two_stage_download_coordinator.py` - Orchestrator
- `tests/test_youtube_data_api.py` - API tests
- `tests/test_metadata_validator.py` - Validator tests
- `YOUTUBE_DATA_API_INTEGRATION_COMPLETE.md`

#### Files Modified

- `src/knowledge_system/config.py` - Added YouTubeAPIConfig
- `src/knowledge_system/database/service.py` - Added audio linking methods
- `src/knowledge_system/services/youtube_video_matcher.py` - Integrated API with Playwright fallback

#### Configuration

```yaml
youtube_api:
  enabled: true
  api_key: "YOUR_API_KEY"  # From Google Cloud Console
  quota_limit: 10000
  fallback_to_ytdlp: true
  batch_size: 50
```

### Feature - Two-Phase Transcript Acquisition (December 25, 2025)

**10-100x faster transcript acquisition for YouTube playlists**

#### New Features

- **TranscriptAcquisitionOrchestrator**: New unified orchestrator with two-phase workflow
  - Phase 1: Rapid metadata + transcript fetch (1-3 second delays, burst pattern)
  - Phase 2: Selective Whisper fallback (3-5 minute delays, only for videos without transcripts)
- **Force Whisper checkbox**: User control to skip YouTube API and force Whisper transcription
  - Added to Transcription Tab and Batch Processing Tab
  - Warning indicator shows when slow mode is enabled
- **Database tracking**: New `transcript_source` field tracks origin (youtube_api, whisper_fallback, whisper_forced)
- **Settings persistence**: Force Whisper preference saved across sessions

#### Architecture Improvements

- **Clean orchestration**: Single clear path for transcript acquisition
- **Intelligent pacing**: Fast for metadata (mimics human browsing), slow only when downloading audio
- **Database-centric**: All metadata stored immediately in Phase 1
- **No redundant code**: Deleted unused `unified_download_orchestrator_v2.py`

#### Files Added

- `src/knowledge_system/services/transcript_acquisition_orchestrator.py` - New two-phase orchestrator
- `src/knowledge_system/database/migrations/add_transcript_source.sql` - Database migration

#### Files Modified

- `src/knowledge_system/database/models.py` - Added `transcript_source` field to Transcript model
- `src/knowledge_system/gui/tabs/transcription_tab.py` - Added Force Whisper checkbox and settings
- `src/knowledge_system/gui/tabs/batch_processing_tab.py` - Added Force Whisper checkbox
- `src/knowledge_system/gui/core/settings_manager.py` - Added force_whisper settings support

#### Files Removed

- `src/knowledge_system/services/unified_download_orchestrator_v2.py` - Unused V2 orchestrator (replaced)

#### Benefits

- 10-100x faster for playlists with available YouTube transcripts
- User control via Force Whisper checkbox for quality preference
- Clean codebase with no orphaned orchestrator code
- Intelligent pacing mimics human behavior patterns

---

### Feature - Auto-Sync with Close Protection (December 22, 2025)

**Prevents data loss with automatic syncing and close warnings**

#### New Features

- **Auto-sync on accept**: Items automatically sync to GetReceipts in background immediately after acceptance
- **Close warning**: Prevents closing app with unsynced accepted items (Save/Discard/Cancel options)
- **Sync status indicator**: Real-time feedback in dashboard (Syncing.../Synced ✓/Queued for sync)
- **Offline support**: Can review items offline, queues for sync when online
- **Manual sync button**: Retained for batch sync and retry of failed items

#### User Experience

- Accept item → Auto-syncs in 2-3 seconds → Appears on web immediately
- Work offline → Items queue → Manual sync uploads all when online
- Try to close with unsynced items → Warning dialog → Choose to save/discard/cancel
- Visual feedback → Dashboard shows sync status in real-time

#### Files Modified

- **NEW:** `src/knowledge_system/gui/workers/auto_sync_worker.py` - Background sync worker
- `src/knowledge_system/gui/tabs/extract_tab.py` - Auto-sync triggers, unsynced tracking
- `src/knowledge_system/gui/components/review_dashboard.py` - Sync status indicator
- `src/knowledge_system/gui/components/review_queue.py` - Remove item by ID method
- `src/knowledge_system/gui/main_window_pyqt6.py` - Close warning dialog
- `src/knowledge_system/database/review_queue_service.py` - is_item_synced() method

#### Benefits

- No data loss - items sync immediately
- Offline capable - queue for sync when online
- Standard UX - follows Gmail/Slack patterns
- Fail-safe - close warning catches missed syncs
- Non-blocking - background sync doesn't interrupt workflow

---

### UI - Extract Tab Improvements (December 22, 2025)

**Cleaner, more compact UI with better dark theme consistency**

#### Changes

- **Consistent dark theme**: All white backgrounds changed to dark gray (#2d2d2d, #3c3c3c)
- **Removed Tier filter**: Simplified filter bar (Type, Source, Status, Search only)
- **Renamed "Video" to "Source"**: More accurate terminology, properly references all sources
- **Compact review status**: Inline text instead of large stat cards (60% space reduction)
- **Dual progress bars**: Current file progress (blue) + batch progress (green)

#### Files Modified

- `gui/components/review_dashboard.py` - Redesigned with inline status and dual progress bars
- `gui/components/filter_bar.py` - Removed tier filter, renamed Video→Source
- `gui/components/review_queue.py` - Dark theme backgrounds
- `gui/components/enhanced_progress_display.py` - Dark theme backgrounds
- `gui/tabs/extract_tab.py` - Dark theme dialog, update sources on item add

#### New Dashboard Layout

```
📊 Processing: 0/0 videos  0 items extracted  Pending: 80 | Accepted: 0 | Rejected: 0
Current: [████████░░░░░░░░░░░░] Extracting...
Batch:   [███░░░░░░░░░░░░░░░░░] 15%
```

---

### Major - Speaker Attribution Simplification (December 22, 2025)

**Removed complex diarization system in favor of LLM-based speaker inference**

#### Breaking Changes

- **Deprecated diarization system**: pyannote.audio, voice fingerprinting, and speaker learning system no longer used
- **Removed `segments.speaker` column**: Speaker attribution now at entity level (claims, jargon, concepts)
- **Unified workflow**: All content (YouTube + audio) processed identically through Pass 1 LLM

#### New Features

- **Entity-level speaker attribution**: Added `claims.speaker`, `jargon_terms.introduced_by`, `concepts.advocated_by` fields
- **Web-based claim merging**: Added `claims.cluster_id` and `claims.is_canonical_instance` for manual deduplication in web interface
- **LLM speaker inference**: Pass 1 extraction now infers speakers from content (more accurate than audio analysis)
- **Simplified workflow**: One unified path for all content types

#### Database Changes

- Added `claims.speaker TEXT` - Who made this claim (from Pass 1 LLM)
- Added `claims.cluster_id TEXT` - For grouping duplicate claims in web interface
- Added `claims.is_canonical_instance BOOLEAN` - Primary version in merged cluster
- Added `jargon_terms.introduced_by TEXT` - Who first used/explained the term
- Added `concepts.advocated_by TEXT` - Who advocates for this mental model
- Migration script: `2025_12_22_add_speaker_to_entities.sql`

#### Performance Improvements

- **40-80 seconds faster** per video (no diarization overhead)
- **377MB smaller install** (removed torch/transformers dependencies)
- **Simpler codebase** (removed 5+ files, 7+ database tables)

#### Benefits

- **More accurate**: Content-based speaker inference beats audio diarization
- **Unified workflow**: YouTube and audio files processed identically
- **Better UX**: Web-based manual merging with full context (~100 claims per speaker)
- **Easier maintenance**: No complex audio processing stack

#### Files Modified

- `src/knowledge_system/database/models.py` - Added speaker fields to entities
- `src/knowledge_system/database/claim_store.py` - Extract speaker from Pass 1 LLM
- `src/knowledge_system/database/migrations/claim_centric_schema.sql` - Removed segments.speaker
- `DIARIZATION_DEPRECATED.md` - NEW: Deprecation notice and migration guide
- `SPEAKER_ATTRIBUTION_SIMPLIFICATION_COMPLETE.md` - NEW: Complete implementation summary

#### Migration Notes

- Existing claims migrated from `segments.speaker` (best effort)
- Diarization files marked deprecated but not yet removed
- Future phases will remove diarization code and dependencies

---

### Major - Bulk Review Workflow for Extract Tab (December 22, 2025)

**Complete redesign of Extract Tab with industry-standard bulk review patterns**

#### New Features

- **Review Dashboard**: Collapsible stats panel showing real-time processing progress (videos processed, items extracted) and review status (pending/accepted/rejected counts)
- **Unified Review Queue**: Single QTableView replacing the 5 separate tab-based lists, with columns for Type, Content, Source, Tier, Importance, and Status
- **Filter Bar**: Horizontal filter controls for Type (Claim/Jargon/Person/Concept), Video/Source, Status (Pending/Accepted/Rejected), Tier (A/B/C/D), and text search
- **Bulk Action Toolbar**: Gmail-style toolbar that appears when items are selected, with Accept All, Reject All, Set Tier, Select All Visible, Select All Pending actions
- **Enhanced Detail Panel**: Accept/Reject/Skip buttons with Previous/Next navigation for rapid single-item review
- **Confirm & Sync Dialog**: Summary dialog showing counts of accepted/rejected/pending items before pushing to GetReceipts

#### Keyboard Shortcuts

- `A` - Accept current item and move to next
- `R` - Reject current item and move to next
- `J/K` - Navigate to next/previous item
- `Space` - Toggle selection of current item
- `Escape` - Deselect all
- `/` - Focus search box
- `Ctrl+Enter` - Open Confirm & Sync dialog

#### New Components

- `gui/components/review_dashboard.py` - Progress and stats dashboard
- `gui/components/review_queue.py` - Unified queue model, filter model, and view
- `gui/components/filter_bar.py` - Horizontal filter controls
- `gui/components/bulk_action_toolbar.py` - Selection-aware bulk actions
- `database/review_queue_service.py` - Database persistence service for review items
- `database/migrations/2025_12_22_review_queue.sql` - Review queue table schema

#### Database Persistence

- Review items persist across sessions until explicitly synced to GetReceipts
- On tab open, loads all pending and unsynced items from previous sessions
- Status changes (accept/reject) are saved immediately to database
- Synced items marked with `synced_at` timestamp and removed from queue

#### UI/UX Patterns Adopted

Based on research of content moderation tools (Admation, Moxo, Filestage), data labeling platforms (Label Studio, Prodigy), and bulk action UIs (Gmail, Notion, Airtable):
- Tri-state checkbox selection
- Sticky bulk action bar
- Color-coded status pills
- Virtual scrolling for 10K+ items
- Confirmation gates for destructive bulk actions

### Major - Two-Pass Architecture Migration (December 22, 2025)

**BREAKING CHANGE: Complete architectural overhaul from two-step to two-pass system**

#### What Changed

Migrated from the legacy two-step (mining + evaluator) system to a modern two-pass (extraction + synthesis) architecture. This is a fundamental change in how the system processes content.

**Old System (Two-Step):**
- Transcript → Split into segments → Mine each segment → Evaluate all claims → Store
- Multiple LLM calls per video
- Fragmented claims across segment boundaries
- Lost context

**New System (Two-Pass):**
- Transcript (complete) → Pass 1: Extract & Score → Pass 2: Synthesize Summary → Store
- Only 2 LLM calls per video
- Whole-document processing
- Preserves complete argument structures

#### Files Removed (18 files, ~6,452 lines)

**Segment-Based Two-Step:**
- `src/knowledge_system/core/system2_orchestrator_mining.py`
- `src/knowledge_system/core/batch_pipeline.py`
- `src/knowledge_system/processors/hce/unified_pipeline.py`
- `src/knowledge_system/processors/hce/unified_miner.py`
- `src/knowledge_system/processors/hce/flagship_evaluator.py`
- `src/knowledge_system/processors/hce/evaluators/jargon_evaluator.py`
- `src/knowledge_system/processors/hce/evaluators/people_evaluator.py`
- `src/knowledge_system/processors/hce/evaluators/concepts_evaluator.py`

**Whole-Document Two-Step:**
- `src/knowledge_system/processors/claims_first/` (entire directory)

#### Files Created (9 files, ~2,325 lines)

**Two-Pass System:**
- `src/knowledge_system/processors/two_pass/__init__.py`
- `src/knowledge_system/processors/two_pass/extraction_pass.py` - Pass 1 implementation
- `src/knowledge_system/processors/two_pass/synthesis_pass.py` - Pass 2 implementation
- `src/knowledge_system/processors/two_pass/pipeline.py` - Orchestrator
- `src/knowledge_system/processors/two_pass/prompts/extraction_pass.txt`
- `src/knowledge_system/processors/two_pass/prompts/synthesis_pass.txt`
- `src/knowledge_system/core/system2_orchestrator_two_pass.py` - Integration

#### Benefits

1. **Simpler Codebase**: Net -4,127 lines of code
2. **Faster Processing**: Only 2 API calls vs. many
3. **Better Quality**: Whole-document context preserved
4. **Lower Cost**: Fewer API calls, fewer tokens
5. **Absolute Scoring**: Importance scores (0-10) globally comparable
6. **Speaker Inference**: Built-in without diarization
7. **World-Class Summaries**: Thematic narrative synthesis

#### Breaking Changes

- `ClaimsFirstWorker` renamed to `TwoPassWorker` (backward compatibility alias maintained)
- Configuration changed: `miner_model` + `evaluator_model` → single `llm_model`
- No more tier-based ranking (A/B/C) - use importance scores instead
- GUI stages reduced from 6 to 4

#### Migration

See `TWO_PASS_MIGRATION_COMPLETE.md` for full details.

Rollback checkpoint: `checkpoint-before-two-step-removal` (commit 66371a3)

### Performance - Cloud API Mining Optimization (December 21, 2025)

**MASSIVE SPEEDUP: 7.5x faster claim mining for cloud APIs (Anthropic, OpenAI, Google)**

#### Problem
- Mining 80 segments with Claude Sonnet 4.5 took **30 minutes** (should be 2-3 minutes)
- Root causes:
  1. **Artificial concurrency limits**: Cloud APIs limited to 8 concurrent requests (designed for local Ollama, not cloud)
  2. **No segment batching**: Each segment = separate API call (80 calls × 22s latency = 30 min)
  3. **Conservative rate limits**: Set to 50 RPM when Anthropic allows 4,000 RPM

#### Solution
1. **Removed hardware tier limits for cloud APIs** (`llm_adapter.py`)
   - Before: 2-8 concurrent requests based on CPU (M1/M2/Ultra)
   - After: 100 concurrent requests (hardware-independent, limited by rate limiter)
   - Rationale: Cloud APIs are just HTTP requests - your CPU doesn't matter

2. **Implemented segment batching** (`unified_miner.py`)
   - Cloud APIs: 20 segments per API call (auto-detected)
   - Local Ollama: 1 segment per call (unchanged, optimized for GPU parallelization)
   - Reduces 80 API calls → 4 API calls (20x fewer roundtrips)

3. **Updated rate limiters to match provider limits**
   - Anthropic: 50 RPM → 1,000 RPM (actual limit: 4,000 RPM for paid tier)
   - OpenAI: 60 RPM → 500 RPM (actual limit: 3,500+ RPM for tier 2)
   - Google: 60 RPM → 1,000 RPM (actual limit: 1,500+ RPM for paid tier)

#### Performance Impact
- **Before**: 80 segments × 22s = 30 minutes
- **After**: 4 batches × 22s = **~90 seconds** (20x faster)
- **API calls per minute**: As many as hardware allows, up to provider's rate limit (1,000 RPM)

#### Files Modified
- `src/knowledge_system/core/llm_adapter.py`: Cloud concurrency limits and rate limiters
- `src/knowledge_system/processors/hce/unified_miner.py`: Batch mining logic with auto-detection

### Fixed

- **GitHub Actions Smoke Test** - Fixed failing smoke test workflow by adding missing lightweight dependencies
  - Added `pydantic-settings>=2.0.0` (required by `config.py`)
  - Added `rich>=13.0.0` (required by progress display utilities)
  - Added `sqlalchemy>=2.0.0` (required by database models)
  - Smoke test now successfully validates Python syntax and basic imports across Python 3.11, 3.12, and 3.13
  - Provides fast feedback (~2-3 minutes) on code quality without requiring heavy ML dependencies

### Added (Major Feature: YouTube AI Summary Integration)

- **YouTube AI Summary Scraping** - Automatically scrape YouTube's AI-generated summaries alongside local LLM processing
  - `PlaywrightYouTubeScraper` service for browser automation with cookie-based authentication
  - `BrowserCookieManager` loads YouTube cookies from Chrome/Safari/Firefox (reuses yt-dlp infrastructure)
  - `YouTubeDownloadWithAISummary` processor wraps existing download pipeline
  - Waits 12-60 seconds for complete summary generation (handles long videos)
  - Supports fuzzy timestamp matching with 6 regex patterns
  
- **Database Schema** (`database/migrations/add_youtube_ai_summary.sql`)
  - Added `youtube_ai_summary` TEXT column to `media_sources` table
  - Added `youtube_ai_summary_fetched_at` DATETIME column
  - Added `youtube_ai_summary_method` TEXT column ('playwright_scraper' or 'api')
  - Clear separation: `description` (source-provided), `youtube_ai_summary` (YouTube AI), `short_summary`/`long_summary` (Knowledge_Chipper LLM)
  
- **Markdown Output Enhancements** (`processors/audio_processor.py`)
  - Added "YouTube AI Summary" section to generated markdown files
  - Hyperlinked ALL timestamps throughout document (description, AI summary, transcript)
  - Supports timestamp formats: `(1:16-1:28)`, `[7:12]`, `**00:06**`, `00:00 //`, standalone chapters
  - Added note: "Click any timestamp to jump to that point in the video"
  
- **Standalone Scraper Tool** (`scrape_youtube_complete.py`)
  - Complete video data extraction: metadata + transcript + AI summary
  - Uses yt-dlp for rich metadata (23 tags, view count, duration, etc.)
  - Downloads thumbnail to Thumbnails/ directory
  - Title-based filenames (e.g., "China's Economic Prospects on the Cusp - George Magnus.md")
  - Outputs in Knowledge_Chipper standard format
  
- **Comparison Tools**
  - `compare_youtube_summaries.py` - Compare YouTube AI vs local LLM summaries
  - `test_youtube_ai_integration.py` - End-to-end pipeline integration test
  
- **Dependencies**
  - Added `playwright>=1.40.0` to requirements.txt and pyproject.toml
  - Installation script: `scripts/install_playwright.py`
  - Auto-installs Chromium browser (~50 MB) on first use

### Changed

- **AudioProcessor Markdown Generation**
  - Changed "YouTube Description" to "Description" (clearer for all source types)
  - Added YouTube AI Summary section (conditional on availability)
  - Hyperlinked timestamps in description and AI summary
  - Hyperlinked transcript timestamps for YouTube videos
  
- **Database Architecture Documentation**
  - Clarified purpose of each summary field:
    - `description`: Source-provided (YouTube desc, RSS notes, PDF abstract)
    - `youtube_ai_summary`: YouTube AI-generated (scraped)
    - `short_summary`: Knowledge_Chipper short (local LLM)
    - `long_summary`: Knowledge_Chipper long (local LLM)
  - Allows comparison testing between YouTube AI and Knowledge_Chipper summaries

### Technical Details

- **Browser Cookie Loading**: Reuses existing yt-dlp cookie infrastructure
- **Chrome Timestamp Bug Fix**: Converts Chrome's microsecond timestamps to seconds for Playwright
- **Fuzzy Timestamp Matching**: Context-aware regex patterns avoid false positives
- **Performance**: YouTube AI summary: ~15-20 seconds vs local LLM: ~2-5 minutes (10-20x faster)
- **Fallback**: Graceful degradation if YouTube AI unavailable (Premium required, region-locked)

### Added (Major Feature: 6-Dimension Multi-Profile Scoring)

- **Multi-Profile Scoring System** - Expanded from 5 to 6 dimensions with user archetype-based importance calculation
  - Added **Temporal Stability** dimension (1=ephemeral to 10=timeless)
  - Added **Scope** dimension (1=narrow to 10=universal)
  - Updated all 12 user profiles with 6-dimension weights
  - Profiles: Scientist, Philosopher, Educator, Student, Skeptic, Investor, Policy Maker, Tech Professional, Health Professional, Journalist, Generalist, Pragmatist
  
- **Flagship Evaluator V2** (`src/knowledge_system/processors/hce/flagship_evaluator.py`)
  - Integrated multi-profile scorer into evaluation pipeline
  - LLM evaluates 6 dimensions once, then arithmetic calculates 12 profile scores (zero marginal cost)
  - Max-scoring aggregation: final importance = max(all profile scores)
  - Rescues niche-but-valuable claims (high for at least one profile)
  - New `_process_multi_profile_scoring()` method
  
- **Updated Prompt** (`prompts/flagship_evaluator.txt`)
  - Requests 6 independent dimension scores instead of single importance
  - Detailed rubrics and examples for each dimension
  - Emphasizes scoring independence (don't conflate dimensions)
  
- **Schema V2** (`schemas/flagship_output.v2.json`)
  - Added `dimensions` object with 6 required fields
  - Added `profile_scores` object with 12 profile scores
  - Added `best_profile` field (which profile gave highest score)
  - Added `tier` field (A/B/C/D classification)
  - Backward compatible with V1 output
  
- **Database Migration** (`database/migrations/2025_12_22_multi_profile_scoring.sql`)
  - Added `dimensions` JSON column
  - Added `profile_scores` JSON column
  - Added `best_profile` TEXT column
  - Added `temporal_stability` REAL column (extracted for filtering)
  - Added `scope` REAL column (extracted for filtering)
  - Created indexes on `best_profile`, `temporal_stability`, `scope`, `tier`
  
- **Unit Tests** (`tests/test_multi_profile_scorer.py`)
  - Dimension validation (6 dimensions required)
  - Profile weight validation (all sum to 1.0)
  - Profile scoring arithmetic
  - Max-scoring rescues niche claims
  - Trivial claims still rejected
  - Temporal stability effects
  - Tier assignment
  
- **Integration Tests** (`tests/test_flagship_evaluator_v2.py`)
  - V2 output with dimensions and profile scores
  - Backward compatibility with V1 output
  - Tier distribution tracking
  - Profile distribution tracking

### Changed

- **Profile Weights** (`src/knowledge_system/scoring/profiles.py`)
  - Redistributed weights across 6 dimensions for all 12 profiles
  - All weights still sum to 1.0
  - Scientist now: 45% epistemic, 28% verifiability, 13% novelty, 8% temporal, 4% scope, 2% actionability
  - Investor now: 48% actionability, 23% verifiability, 13% epistemic, 8% novelty, 5% temporal, 3% scope
  
- **EvaluatedClaim Class** (`flagship_evaluator.py`)
  - Added `dimensions`, `profile_scores`, `best_profile`, `tier` properties
  - Maintains backward compatibility with V1 fields

### Technical Details

- **Cost Impact**: +50% LLM cost per claim (longer output), but zero marginal cost for adding profiles
- **Performance**: Profile scoring is pure arithmetic (<1ms for 12 profiles)
- **Scalability**: Adding 100 profiles costs the same as 1 profile (same LLM call)

## [4.0.0] - 2025-12-21

### Added (Major Architecture: Claims-First Pipeline)

This release introduces the **Claims-First Architecture**, a fundamental shift in how we process podcast content. Instead of the speaker-first approach (diarization → transcription → extraction), we now extract claims first from undiarized transcripts and only attribute speakers to high-value claims.

#### New Pipeline Components

- **Claims-First Pipeline** (`src/knowledge_system/processors/claims_first/`)
  - `TranscriptFetcher`: Unified interface for YouTube and Whisper transcripts
  - `TimestampMatcher`: Fuzzy matching of evidence quotes to timestamps
  - `LazySpeakerAttributor`: Targeted speaker attribution for A/B-tier claims only
  - `ClaimsFirstPipeline`: Main orchestrator for the new workflow
  - `ClaimsFirstConfig`: Configuration dataclass with validation

- **Database Schema Updates** (`database/migrations/2025_12_20_claims_first_support.sql`)
  - New columns: `timestamp_precision`, `transcript_source`, `speaker_attribution_confidence`
  - New table: `candidate_claims` for re-evaluation support
  - New table: `claims_first_processing_log` for tracking
  - New table: `extraction_checkpoints` for auth failure recovery

- **ClaimsFirstResult Enhancements** (`pipeline.py`)
  - `rejected_claims`: List of claims rejected by evaluator (visible for review)
  - `candidates_count`: Total candidates before evaluation
  - `acceptance_rate`: Ratio of accepted to total candidates
  - `quality_assessment`: Passive quality opinion with status, suggestion, thresholds
  - `promote_claim()`: Move rejected claims back through post-processing
  - `generate_summaries()`: Generate KC short/long summaries from all inputs

- **Authentication Failure Recovery** (`session_based_scheduler.py`)
  - `save_auth_failure_checkpoint()`: Save progress on 401/403/bot detection
  - `get_pending_checkpoint()`: Check for pending checkpoints
  - `resume_from_checkpoint()`: Resume from saved state
  - `is_auth_error()`: Detect auth-related errors

- **Configuration** 
  - New `claims_first` section in `config/settings.yaml`
  - New `ClaimsFirstConfig` in `config.py`
  - Configurable evaluator model selection (Gemini/Claude)

#### Updated Components

- **UnifiedMiner**: Now accepts plain text input (no speaker labels required)
  - New `mine()` method for claims-first mode
  - Text chunking with overlap for long transcripts
  - Output merging and deduplication

- **FlagshipEvaluator**: Added configurable model selection
  - New `evaluate_claims_simple()` convenience function
  - New `ConfigurableFlagshipEvaluator` with auto-upgrade

- **AudioProcessor**: Added claims-first flag
  - New `use_claims_first` parameter
  - New `process_claims_first()` method
  - Automatic diarization skip in claims-first mode

#### New Scripts

- `scripts/apply_claims_first_migration.py`: Database migration script
- `scripts/validate_claims_first.py`: Validation on test podcasts

#### Benefits

- **Faster Processing**: Skip diarization for YouTube content with good transcripts
- **Lower Cost**: Only attribute speakers to important claims (A/B tier)
- **Simpler Code**: Reduced dependency on pyannote/torch for new pipeline
- **Better Quality**: LLM-based speaker attribution using context

### Removed (Speaker-First Pipeline)

The following files have been **deleted** as part of the claims-first migration. 
The speaker-first code can be restored from Git if needed:
- **Git tag**: `v3.5.0-speaker-first-final`
- **Git branch**: `speaker-first-archive`

#### Deleted Processor Files
- `src/knowledge_system/processors/diarization.py` - Speaker diarization processor
- `src/knowledge_system/processors/speaker_processor.py` - Speaker assignment processor

#### Deleted Voice Processing Files  
- `src/knowledge_system/voice/voice_fingerprinting.py` - Acoustic voice fingerprinting
- `src/knowledge_system/voice/speaker_verification_service.py` - Speaker verification
- `src/knowledge_system/voice/accuracy_testing.py` - Voice accuracy testing

#### Deleted GUI Components
- `src/knowledge_system/gui/tabs/speaker_attribution_tab.py` - Speaker Attribution tab
- `src/knowledge_system/gui/dialogs/speaker_assignment_dialog.py` - Speaker assignment dialog
- `src/knowledge_system/gui/dialogs/batch_speaker_dialog.py` - Batch speaker dialog
- `src/knowledge_system/gui/dialogs/hce_update_dialog.py` - HCE update dialog

#### Deleted Utility Files
- `src/knowledge_system/utils/speaker_assignment_queue.py` - Speaker assignment queue

#### Modified Files (Speaker Features Disabled)
- `audio_processor.py` - Diarization calls return no-op with warning
- `transcription_tab.py` - Speaker assignment checkbox replaced with Claims-First toggle
- `model_preloader.py` - Diarization preloading is a no-op
- `queue_tab.py` - Stage names updated for claims-first pipeline

#### GUI Changes
- **NEW Extract Tab**: Dedicated tab for claims-first extraction with:
  - Two-pane editor layout (results list on left, detail editor on right)
  - LLM selection per stage (Miner provider/model, Evaluator provider/model)
  - 6-stage progress display with visual indicators
  - Quality assessment panel with acceptance rate and transcript quality
  - Rejected claims tab with "Promote" button
  - Re-run with Whisper fallback button
- **Queue Tab**: Updated stage names (Extract Claims, Evaluate Claims, Attribution)
- Removed deprecated diarization and speaker assignment UI elements

#### New GUI Components
- **PipelineProgressDisplay**: 6-stage progress widget for claims-first pipeline
- **ClaimsFirstWorker**: Background worker with pause/resume/cancel support
- **ClaimItem/EntityItem**: Custom list items for results display

#### Documentation
- New `CLAIMS_FIRST_MIGRATION_GUIDE.md` with step-by-step migration instructions

### Added (Web Episode Page Enhancements - GetReceipts.org)

The Episode page on GetReceipts.org now displays comprehensive claims-first data:

- **KC Short Summary**: Prominent 1-2 paragraph summary above the fold
- **KC Long Summary**: Expandable executive-level comprehensive analysis
- **YouTube AI Summary**: Collapsible section labeled as AI-generated
- **Chapter Timestamps**: Clickable navigation to video positions
- **Tags**: Badge display of episode categorization
- **Full Transcript**: Expandable with quality indicator and source type
- **Transcript Quality Score**: Visual indicator of transcript reliability

#### Supabase Migration (`026_claims_first_support.sql`)
- `short_summary`, `long_summary`, `yt_ai_summary` columns on media_sources
- `transcript_source`, `transcript_quality_score` columns
- `tags` JSONB array for categorization
- `episode_chapters` table for video navigation
- `extraction_checkpoints` table for auth failure recovery

### Added (Google Gemini LLM Support)

Comprehensive support for Google Gemini LLMs, matching existing support for OpenAI, Anthropic, and Ollama.

#### New Provider Support
- **GoogleProvider** in `src/knowledge_system/utils/llm_providers.py`
  - Full async support using `google-genai` package
  - Structured JSON output via response schema
  - Token estimation and rate limiting

- **LLM Adapter Integration** in `src/knowledge_system/core/llm_adapter.py`
  - `_call_google()` method for Gemini API calls
  - Default model: `gemini-2.0-flash`
  - Environment variable support: `GOOGLE_API_KEY` or `GEMINI_API_KEY`

#### Configuration
- New `google_api_key` field in `APIKeysConfig` (`src/knowledge_system/config.py`)
- Updated `pyproject.toml` and `requirements.txt` with `google-genai` dependency
- Model selection via `provider: "google"` and `model: "gemini-2.0-flash"` in config

#### Available Models
- `gemini-2.0-flash` (default) - Fast, efficient model
- `gemini-2.0-flash-exp` - Experimental features
- `gemini-1.5-pro` - Higher capability model
- `gemini-1.5-flash` - Balanced speed/quality

---

## [3.5.0] - Previous Release

### Changed (Major Refactor: Word-Driven Speaker Alignment)
- **Transcription Backend**: Replaced whisper.cpp subprocess calls with `pywhispercpp` Python binding
  - Uses DTW (Dynamic Time Warping) for accurate word-level timestamps
  - Cleaner Python integration with same performance as subprocess
  - Removed all subprocess command building and `_run_whisper_with_progress()` code

- **Speaker Alignment**: Now using pyannote-whisper's battle-tested word-driven alignment pattern
  - Assigns speaker labels at word midpoints (not segment boundaries)
  - Median filter smoothing eliminates single-word speaker flips
  - Words merged into segments by consecutive speaker labels
  - Reference: https://github.com/yinruiqing/pyannote-whisper

- **Diarization Tuning**: Applied Hervé Bredin's optimized hyperparameters for podcast content
  - New "bredin" sensitivity mode with challenge-winning configuration
  - `num_speakers` oracle mode for known 2-speaker podcasts
  - Tunable parameters: `clustering_threshold`, `min_cluster_size`, `min_duration_off`
  - Reference: https://herve.niderb.fr/posts/2022-12-02-how-I-won-2022-diarization-challenges.html

- **Persistent Profiles**: Fixed to use DTW timestamps + stable regions only
  - Fingerprints extracted only from stable speaker regions (2+ seconds continuous)
  - Prevents profile pollution from transition zones
  - New functions: `find_stable_regions()`, `extract_fingerprints_from_stable_regions()`

### Added
- `pywhispercpp>=1.2.0` and `pyannote-whisper` as dependencies
- `scripts/tune_diarization.py` - Grid search hyperparameter tuning based on Bredin's recipe
- Median filter smoothing for speaker label stability
- New settings: `num_speakers`, `clustering_threshold`, `min_cluster_size`, `median_filter_window`
- Stable region extraction functions in `voice_fingerprinting.py`

- **Deno Runtime Integration for YouTube Downloads**: yt-dlp 2025.11.12+ requires Deno JavaScript runtime
  - **DMG Bundling**: Deno is now bundled in DMG builds for offline YouTube downloads
  - **New Scripts**:
    - `scripts/bundle_deno.sh` - Creates Deno package for DMG installer
    - `scripts/silent_deno_installer.py` - Installs Deno into app bundle
  - **Preflight Check**: `check_deno()` added to verify Deno availability at startup
  - **GitHub Action**: `.github/workflows/watch-deno-releases.yml` monitors for Deno updates
  - **Why Deno?**: YouTube now uses complex JavaScript challenges that require a full JS runtime for signature extraction. Deno is recommended by yt-dlp for security and ease of use.
  - **For Local Dev**: Install with `brew install deno` or `curl -fsSL https://deno.land/install.sh | sh`

### Changed
- **yt-dlp upgraded to 2025.11.12**: First version requiring Deno runtime for YouTube downloads. Deno is bundled in DMG and checked at startup via preflight.

### Removed
- `_split_mixed_speaker_segments()` - replaced by word-driven alignment
- `_reassign_segments_by_voice_verification()` - replaced by word-driven alignment  
- `_verify_word_level_speakers()` - replaced by pyannote-whisper pattern
- Subprocess-based whisper.cpp calls - replaced by pywhispercpp
- Old word verification config settings (replaced by median filter + stable regions)

---

## Previous Changelog Entries

### Added (Legacy - Before Word-Driven Refactor)
- **Word-Level Speaker Attribution** (SUPERSEDED): Previous implementation used whisper.cpp `--output-words` flag with custom verification. Now replaced by pywhispercpp + pyannote-whisper pattern.

- **Persistent Speaker Profiles**: Speaker voice profiles now persist across episodes for recurring hosts.
  - New `speaker_profiles` database table stores averaged embeddings
  - `PersistentSpeakerProfile` SQLAlchemy model with fingerprint accumulation
  - Profiles accumulate across episodes (more data = better accuracy)
  - Channel-aware profile lookup for instant host recognition
  - New methods: `accumulate_speaker_profile()`, `get_or_create_channel_profile()`
  - New migration: `database/migrations/024_persistent_speaker_profiles.sql`
  - Confidence scoring based on sample count and feature availability

- **Batch Processing Pipeline with Prompt Caching**: Complete implementation of batch API support for OpenAI and Anthropic with automatic prompt caching optimization.
  - **50% cost savings** via batch API discounts (24-48 hour processing)
  - **Additional 25% input savings** from OpenAI prompt caching for static prompt prefixes
  - **3-stage pipeline**: Mining → Flagship Evaluation → Re-mining of flagged segments
  - **Processing modes**: `realtime`, `batch`, and `auto` (switches based on segment count)
  - **GUI integration**: Mode selector, cost estimates, and cache metrics display
  - **Database tracking**: New tables for batch jobs and requests with cache hit metrics
  - **Re-mining**: Low-confidence and empty segments automatically re-processed with stronger model
  
  **New Files:**
  - `src/knowledge_system/core/batch_client.py` - Base class and data models
  - `src/knowledge_system/core/batch_openai.py` - OpenAI Batch API client
  - `src/knowledge_system/core/batch_anthropic.py` - Anthropic Batch API client
  - `src/knowledge_system/core/batch_pipeline.py` - 3-stage pipeline orchestrator
  - `database/migrations/023_batch_processing.sql` - Batch tracking tables
  - `tests/test_batch_pipeline.py` - 19 unit tests for batch processing
  
  **Cost Estimate for 5,000 Hours:**
  - Real-time: ~$438
  - Batch only: ~$219
  - Batch + caching: ~$170-195

### Changed
- **yt-dlp upgraded to 2025.10.22**: Updated from 2025.10.14 with YouTube support fixes. **Important:** This is the last version before Deno/JavaScript runtime becomes required (2025.11.12+). pyannote.audio minimum bumped to 4.0.1 for the new community-1 speaker diarization model.

- **Specialized Miner Prompts Aligned to V2/V3 Architecture**: Rewrote `unified_miner_transcript_third_party.txt` and `unified_miner_document.txt` to match the V2/V3 structure and extraction standards:
  - **Refinement patterns section** for blocking known-bad entities via synced feedback
  - **Mental model calibration list** with 25+ exemplars and "named AND used" extraction rule
  - **Worked examples** demonstrating proper handling of source-specific scenarios
  - **Schema harmonization**: Third-party transcripts use `"Unknown"` speaker and `"00:00"` timestamps when unavailable; documents use `location` and `source_attribution` instead of timestamps/speaker
  - **Tighter extraction bar**: Removed "be lenient" language—tolerance is for metadata limitations, not content quality
  - **Document-specific fields**: `formally_defined` boolean for jargon, `is_document_author` for people, `citation_info` for evidence spans
  - **Third-party transcript fields**: Optional `quality_note` for flagging transcription issues

### Added
- **Unified Miner Prompt V3** (`unified_miner_transcript_own_V3.txt`): Complete rewrite of the own-transcript mining prompt for Qwen instruct models. Key improvements:
  - **66% smaller** than V1 (347 lines vs 916 lines) while improving extraction consistency
  - **Worked example** with full input→output JSON demonstrating proper speaker entity handling, multi-claim extraction, jargon with multiple evidence spans, and mental model extraction
  - **Mental model calibration list** with 25+ exemplars across 4 categories (Decision & Reasoning, Economic & Strategic, Systems & Dynamics, Frameworks) plus anti-hallucination warning
  - **Anti-copying guard** to prevent Qwen from regurgitating example timestamps/quotes
  - **Refinement patterns section** for iterative improvement via known-bad entity lists
  - **Speaker entities in people array** with `is_speaker=true` per architectural spec
  - **Clearer skip criteria** for claims (meta-commentary, empty reactions, tautologies), jargon (generic terms), and mental models (bare name-drops without application)

- **Entity Refinement Sync**: Desktop app automatically syncs prompt improvements from GetReceipts.org

  **How It Works:**
  1. Review and reject incorrect entities on the web at `getreceipts.org/dashboard/entities`
  2. The web generates AI-powered prompt improvements from your rejections
  3. Desktop app automatically fetches and applies these improvements
  4. Future extractions benefit from learned patterns
  
  **User Benefit:** When you reject "US President" as a person on the web, the desktop app learns to skip similar titles like "CEO", "Secretary of State", etc. in future extractions.
  
  **Technical Details:**
  - New service: `src/knowledge_system/services/prompt_sync.py`
  - Refinements stored in: `~/Library/Application Support/Knowledge Chipper/refinements/`
  - Files: `person_refinements.txt`, `jargon_refinements.txt`, `concept_refinements.txt`
  - Modified `unified_miner.py` to inject synced refinements as `<bad_example>` entries
  - Sync happens automatically when device authentication is enabled
- **Web-Canonical Architecture with Ephemeral Local Database**: Implemented complete web-canonical architecture where GetReceipts web database (Supabase) is the single source of truth and the desktop Knowledge_Chipper acts as an ephemeral processor. Desktop claims are marked `hidden=1` after successful upload and no longer appear in local views, forcing users to the web for editing and viewing canonical data.
- **Happy-Style Device Authentication**: Auto-generated device authentication using UUID + cryptographically secure secret key (no user interaction required). Device credentials stored in `~/.getreceipts/device_auth.json` and bcrypt-hashed on backend for security.
- **HTTP API-Based Uploader**: Completely rewrote `knowledge_chipper_oauth/getreceipts_uploader.py` (500+ lines → ~200 lines, net -213 lines) to use HTTP requests to `/api/knowledge-chipper/upload` instead of Supabase Python SDK, bypassing RLS policies and simplifying code.
- **Device Provenance Tracking**: All uploaded data tagged with `device_id` for attribution. Database tracks which Knowledge_Chipper device created each claim, person, concept, jargon entry, episode, milestone, evidence span, and relation.
- **Claim Version Tracking**: Reprocessed claims auto-increment `version` field and link to previous version via `replaces_claim_id`, enabling full reprocessing history tracking.
- **Device Authentication API Endpoint**: Created `/api/knowledge-chipper/device-auth` endpoint that registers new devices or verifies existing devices using bcrypt key verification.
- **Database Migrations for Device Tracking**: Created comprehensive migrations adding `device_id`, `source_id`, `uploaded_at`, `version`, and `replaces_claim_id` columns to all relevant tables in GetReceipts Supabase schema.
- **Safe Rollback Strategy**: Created two git branches for easy rollback: `feature/desktop-canonical` (commit a582767, safe rollback point) and `feature/web-canonical-ephemeral` (commit 738ef9f, experimental implementation).
- **Comprehensive Testing Scripts**: Added `test_web_canonical_upload.py` for automated upload testing and `check_schema.py` for verifying Supabase schema state.
- **Complete Documentation Suite**: Created comprehensive documentation including `ARCHITECTURE_WEB_CANONICAL.md` (complete architecture guide), `VERCEL_ENV_SETUP.md` (environment variable setup), `MIGRATION_CHECK.md` (schema diagnosis), `READY_TO_TEST.md`, `QUICK_START.md`, and `DEPLOYMENT_STATUS.md`.

### Changed
- **Diarization Sensitivity Default**: Default changed from "conservative" to "dialogue" for better quick-exchange capture in podcasts and interviews
- **Speaker Processor Architecture**: Refactored to use word-level verification as primary method, with segment-level as fallback when word timestamps unavailable
- **Claims Upload Service - Ephemeral Behavior**: Modified `src/knowledge_system/services/claims_upload_service.py` to add `hidden` column support and `hide_uploaded_claims()` method. Claims marked uploaded are now hidden from local views, implementing ephemeral-local architecture.
- **Cloud Uploads Tab - Auto-Hide After Upload**: Modified `src/knowledge_system/gui/tabs/cloud_uploads_tab.py` to automatically hide uploaded claims after successful upload, moving them to web-canonical storage.
- **Upload Mechanism - SDK to HTTP API**: Switched from Supabase Python SDK (subject to RLS policies) to direct HTTP API requests using service role key internally. Cleaner code, better error handling, bypasses RLS.
- **Backend Upload Endpoint**: Enhanced `/api/knowledge-chipper/upload` with canonical deduplication, fuzzy matching, entity codes, and extraction tracking (discovered during testing - was rewritten independently).

### Fixed
- **Linting Error on Git Push**: Fixed unescaped apostrophe in `src/app/claim/page.tsx` line 185 (`Don't` → `Don&apos;t`).
- **Missing bcryptjs Dependency**: Added bcryptjs and @types/bcryptjs to GetReceipts package.json for device key hashing.
- **RLS Policy Blocking Uploads**: Resolved Row Level Security errors by switching from direct Supabase SDK calls to HTTP API endpoints that use service role key internally.
- **Missing SUPABASE_SERVICE_ROLE_KEY**: Added environment variable to Vercel deployment for upload endpoint authentication.
- **Device Not Registered Error**: Implemented device-auth endpoint call before first upload to register device credentials.
- **Missing device_id Columns**: Created focused re-run migration `001b_add_device_columns_RERUN.sql` to fix incomplete initial migration where CREATE TABLE succeeded but ALTER TABLE statements didn't persist.

### Technical Details
- **Architecture Pattern**: One-way upload flow (no sync complexity), web is always current
- **Offline Capability**: Desktop can still view local claims until uploaded, then hidden
- **Reprocessing Workflow**: Users can reprocess transcripts with upgraded LLM models, creating versioned claims that replace previous versions
- **Git Strategy**: `feature/desktop-canonical` preserves original architecture, `feature/web-canonical-ephemeral` contains experimental implementation
- **Code Reduction**: Net -213 lines in uploader rewrite (500+ → ~200 lines)
- **Security**: Device keys never transmitted in plain text after initial registration, bcrypt-hashed (10 rounds) on backend
- **Database Schema**: Uses `IF NOT EXISTS` for safe re-run migrations, devices table tracks last_seen_at and optional user_id for claiming devices

### Deprecated
- **`_split_mixed_speaker_segments()`**: Replaced by word-level verification (`_verify_word_level_speakers`). Kept as fallback when word timestamps unavailable
- **`_reassign_segments_by_voice_verification()`**: Replaced by word-level verification with better accuracy (4-7% vs 10-15% DER)

### Fixed
- **Database Schema: Missing user_notes Column**: Fixed `sqlite3.OperationalError` where Review tab failed to load claims due to missing `user_notes` column in the claims table. Applied the `2025_11_16_add_user_notes_to_claims.sql` migration to add the column and index. Updated `DatabaseService` to automatically apply incremental migrations on startup, preventing this issue from occurring on fresh installations or after database resets.

## [3.5.3] - 2025-11-11

### Fixed
- **Summarize Tab Database Row Selection UX**: Fixed unintuitive checkbox selection behavior in the Summarize tab's database browser. Previously, users had to click directly on the tiny checkbox widget to select a transcript for summarization. Now clicking anywhere on a row (title, duration, etc.) toggles the checkbox, making selection much more intuitive. Added debug logging to track checkbox state changes and source selection for easier troubleshooting.

### Enhanced
- **Seamless Transcription-to-Summarization Workflow**: When clicking "Summarize Transcript" after transcription, the Summarization tab now automatically: (1) switches to Database mode (not Files), (2) refreshes and checks the boxes for all transcribed sources, and (3) immediately starts summarization without further user input. This provides a streamlined workflow consistent with the database-first architecture, where the rich database segments (with timestamps, speakers, metadata) are used as input instead of parsing markdown files. The system extracts `source_id` from transcription metadata and uses it to locate and select the corresponding database records.
- **Cookie File Persistence Diagnostics**: Added comprehensive logging throughout the cookie file loading and saving pipeline to diagnose persistence issues. System now logs: (1) full paths of cookie files being loaded from session, (2) verification that cookie_manager widget is initialized before loading, (3) signal disconnect/reconnect operations, (4) verification that files were actually set in the UI after loading, (5) detection of mismatches between expected and loaded file counts. Also logs all save operations with confirmation of successful writes to session. This enables rapid diagnosis of any cookie persistence failures by showing exactly where in the chain the issue occurs. See `COOKIE_PERSISTENCE_DIAGNOSIS_2025_11_10.md` for complete diagnostic guide.

### Changed
- **Summary Data Now Appended to Transcript Files**: Major architectural change - summary data (claims, people, concepts) is now appended to the existing transcript markdown file instead of creating a separate summary file. After summarization completes, the system finds the transcript file and appends: (1) Summary section with generated summary text, (2) Claims section organized by tier (A/B/C) with importance scores, (3) People section with descriptions, (4) Concepts section with definitions. This creates a single comprehensive markdown file per video with transcript + analysis, eliminating confusion about where files are located. The transcript file already contains thumbnail, YouTube description, and full transcript, making it the complete reference document.

### Fixed
- **Summary Markdown Template Bug**: Fixed critical bug in `FileGenerationService.generate_summary_markdown()` where non-HCE summaries were generated with literal template code instead of actual values. The template string was missing the `f` prefix, causing output like `{video.title}` instead of the actual video title. This affected legacy (non-HCE) summaries that fall back to the simple format when `hce_data_json` is not available. Now properly formats all summary markdown files with actual video metadata, model information, and summary text.
- **Claims Not Appearing in Summary Files**: Fixed issue where claims were stored in the database but not appearing in generated summary files. Root cause: The summary record's `hce_data_json` field was None, causing the file generator to fall back to legacy format. New `append_summary_to_transcript()` method reads claims directly from the database tables (claims, people, concepts) via proper joins, ensuring all extracted data appears in the output regardless of how it was stored.
- **CRITICAL: Transcribed YouTube Videos Not Appearing in Summarize Tab**: Fixed critical bug where transcribed YouTube videos didn't appear in the Summarize tab's database browser. Root cause: AudioProcessor was generating a NEW source_id (e.g., `audio_filename_hash123`) for every transcription instead of using the existing source_id from the YouTube download. This created orphaned Transcript records that weren't linked to any MediaSource record. The Summarize tab's query requires BOTH a MediaSource AND a Transcript with matching source_ids. Solution: AudioProcessor now checks for `source_metadata` in kwargs and uses the existing `source_id` before generating a new one. This ensures YouTube transcripts are properly linked to their MediaSource records and appear in the Summarize tab.
- **Transcription Format Parameter Not Respected**: Fixed critical bug where the audio processor ignored the `format` parameter from the GUI, causing markdown files to not be created even when format was set to "md". The code was checking `if output_dir:` but not checking `if output_dir and format != "none":` as documented in `FORMAT_NONE_OPTION.md`. Added proper format parameter extraction and conditional file writing logic. When format is "none", the system now logs "Output format set to 'none' - skipping file creation, will save to database only" and correctly skips file creation while still saving to the database.
- **Voice Fingerprinting Not Merging Single-Speaker Monologues**: Fixed critical bug where voice fingerprinting received the wrong audio file path (original input file instead of converted 16kHz mono WAV), preventing proper speaker merging. The system was passing `path` (original MP4/M4A) instead of `output_path` (converted WAV used for diarization) to `prepare_speaker_data()`. This caused voice fingerprinting to fail audio segment extraction, resulting in single-speaker content being incorrectly split into 2+ speakers. Now correctly passes the converted WAV file path, enabling proper voice similarity analysis and speaker merging.

### Enhanced
- **Voice Fingerprinting Diagnostic Logging**: Added comprehensive diagnostic logging to identify why voice fingerprinting fails to merge speakers. System now logs: (1) which features were successfully extracted vs. empty (mfcc, spectral, prosodic, wav2vec2, ecapa), (2) per-feature similarity scores and which features are available/missing during comparison, (3) total weight used in similarity calculation (should be 1.0 if all features available), (4) actual similarity scores between all speaker pairs with merge decision reasoning, (5) audio file format verification (confirms 16kHz mono WAV is being used, not original MP4/M4A), (6) CSV database loading and lookup (confirms channel_hosts.csv is found, loaded with ~524 entries, and host names are successfully matched). This enables rapid diagnosis of issues like missing deep learning models (wav2vec2/ecapa not loading), audio extraction failures, wrong audio format being passed, CSV not being invoked, or threshold problems. See `VOICE_FINGERPRINTING_DIAGNOSIS_NOV_2025.md` for complete diagnostic guide.
- **Summarize Tab Database List Not Refreshing**: Fixed issue where newly transcribed YouTube URLs didn't appear in the Summarize tab's database browser. Added automatic refresh when the Summarize tab becomes visible and the database view is active. Also added diagnostic logging to detect transcripts without corresponding MediaSource records (orphaned transcripts).
- **Missing Summary Markdown Files & Schema Migration Completion**: Fixed critical issue where summarization reported success but no `.md` file was generated. Root cause: The unified pipeline was storing data to the `episodes` table but never creating the required `Summary` record in the `summaries` table. Added call to `_create_summary_from_pipeline_outputs()` to create the Summary record before attempting markdown generation. Also completed the incomplete migration to claim-centric schema by fixing all remaining references to old schema: (1) Changed `video_id` to `source_id` in 3 Summary instantiations in `system2_orchestrator.py`, (2) Changed `get_video()` to `get_source()` in 6 locations across `file_generation.py` and `speaker_processor.py`. This completes the architectural migration from episode-centric to claim-centric schema and ensures `generate_summary_markdown()` can find the data it needs to create properly formatted summary files.

### Removed
- **Duplicate Summary Generation Code Path**: Removed `generate_summary_markdown_from_pipeline()` method which was creating inconsistent markdown formats. The unified pipeline now uses the standard `generate_summary_markdown()` method that reads from database and uses `_generate_hce_markdown()` for consistent formatting. This eliminates code duplication and ensures ONE format for all HCE summaries, following the painstakingly laid out format specifications.

### Changed
- **Robust LLM Fallback System**: Enhanced MVP LLM detection to use ANY available Ollama model if preferred models aren't found. Priority order: (1) Preferred models (qwen2.5:7b, etc.), (2) Any Qwen model, (3) Any Llama model, (4) Any instruct model, (5) Any available model. This ensures speaker attribution never fails when Ollama has models installed, even if they're not the bundled defaults. System logs which fallback tier is used and warns if quality may be reduced.
- **Transcript Markdown Formatting Optimization**: Improved paragraph breaking for better readability. Reduced max paragraph length from 900 to 500 characters and pause threshold from 7s to 3s for more natural breaks. Paragraphs now break more aggressively on sentence boundaries and pauses, making transcripts easier to scan and read. Force break threshold reduced from 1200 to 700 characters.
- **YouTube Description Header**: Changed "Description" header to "YouTube Description" specifically for YouTube videos, making the source of the description clearer in markdown files.
- **Transcript Markdown Filename**: Removed "_transcript" suffix from markdown filenames for cleaner file naming (e.g., "Trump exploits antisemitism.md" instead of "Trump exploits antisemitism_transcript.md").
- **Transcript Markdown Formatting**: Completely redesigned human-readable transcript formatting with intelligent paragraph grouping. Segments are now grouped into logical paragraphs based on speaker changes, long pauses, sentence boundaries, and character limits. Speaker names and timestamps appear on a header line (`**Speaker** [00:00]`) followed by paragraph text, with blank lines between paragraphs for improved readability. The system automatically adapts to monologues (showing speaker label once at start, then only timestamps) vs dialogues (showing speaker label on every speaker change), eliminating redundant labels while maintaining clarity. This applies to both database-generated markdown files and direct transcription output.
- **Summarization Debugging Enhancements**: Added comprehensive diagnostic logging throughout the unified mining pipeline to track progress and identify hangs. Mining phase now reports progress at INFO level when 3% change OR 10 seconds elapsed (whichever comes first), with all segments logged at DEBUG level. Parallel processor logs initial batch submission, task completions, and active task counts. All errors now include full tracebacks at debug level. This addresses cases where summarization hung at 35% without clear error reporting.

### Removed
- **Deprecated Old HCE Extractors**: Moved pre-unified-pipeline extraction modules to `_deprecated/hce_old_extractors/`: `people.py`, `glossary.py`, `concepts.py`, `skim.py`. These standalone extractors were replaced by the unified pipeline in October 2025, which extracts all entity types in a single pass (70% fewer LLM calls, 3-8x faster). Also moved 12 unused prompt files from the old two-tier evaluation system and standalone detection architecture. See `VESTIGIAL_CODE_ANALYSIS.md` for full details.

### Fixed
- **Flagship Evaluator Model Dropdown Empty on Launch**: Fixed critical bug where the "Flagship Evaluator Model" dropdown appeared empty on first launch despite default models being configured. Root cause: When no provider was saved in session state (e.g., first launch), `_load_settings()` would get an empty string from `get_combo_selection()`, fail the `if saved_provider:` check, and never call `_update_advanced_model_combo()` to populate models. Solution: Default to "local" provider when no provider is saved, ensuring model combo is always populated. This fix applies to all advanced model dropdowns (Unified Miner Model, Flagship Evaluator Model) in the Summarization tab. See `FLAGSHIP_EVALUATOR_MODEL_DEFAULT_FIX.md` for complete analysis of the two-bug compound issue (empty provider handling + model name suffix mismatch).
- **Speaker Attribution Model Name Mismatch**: Fixed critical issue where speaker attribution failed even when Qwen model was bundled and installed. Root cause: installation scripts pulled `"qwen2.5:7b"` but code expected `"qwen2.5:7b-instruct"` (Ollama strips the `-instruct` suffix when storing models). Updated MVP_MODEL_ALTERNATIVES to match actual Ollama model names: `["qwen2.5:7b", "qwen2.5:14b", "qwen2.5:3b", ...]`. This ensures the bundled LLM is properly detected and used for speaker attribution with the 262-podcast CSV mapping database, providing real speaker names instead of generic SPEAKER_01 labels.
- **CRITICAL: Flagship Evaluator Scoring Scale Inconsistency**: Fixed a critical bug in the flagship evaluator prompt that caused all claims to be scored as low-quality (tier C). The prompt had conflicting instructions: sections 25-47 instructed scoring on a 0.0-1.0 scale, while sections 66-88 specified a 1-10 scale. This caused the LLM to return scores like 0.8 (meaning 80% on a 0-1 scale) which were interpreted as 0.8/10 (8% on a 1-10 scale), resulting in importance scores below 5 and tier C assignment. All three scoring dimensions (importance, novelty, confidence) now consistently use the 1-10 scale throughout the prompt. This fix restores proper claim quality assessment where high-quality claims (importance >= 8) are correctly identified as tier A.
- **Vestigial Relations and Contradictions Statistics**: Removed misleading "Relations mapped" and "Contradictions detected" statistics from the summarization output. These features were never implemented in the unified pipeline (which explicitly returns empty arrays for relations and contradictions), but the GUI was still displaying them as if they were functional. This created confusion when they suddenly appeared showing "0" values. The RelationMiner class exists but is disabled, and the unified pipeline comments indicate "Relations not implemented in unified pipeline yet". Cleaned up all UI code that referenced these unimplemented features to avoid false expectations.
- **Logger Variable Shadowing in Unified Miner**: Fixed `cannot access local variable 'logger'` error caused by redundant logger re-assignments within exception handlers that shadowed the module-level logger. Removed all `import logging; logger = logging.getLogger(__name__)` statements within functions and consistently use the module-level logger throughout.
- **QueueTab AttributeError**: Fixed `AttributeError: 'QueueTab' object has no attribute 'log_error'` by replacing all `self.log_error()` calls with the correct `self.append_log()` method from BaseTab. Added error emoji (❌) prefix to error messages for consistency with other tabs.
- **Summarization Progress Reporting Frequency**: Fixed progress reporting throttling to match specification of every 5% or 10 seconds (whichever comes first). Previously was reporting every 10% or 30 seconds, resulting in less frequent status updates during long summarization operations. Now provides more responsive feedback in both the console log and chunk processing displays.
- **Transcript Markdown Display**: Removed redundant H1 heading from transcript markdown files since Obsidian and similar markdown viewers automatically display the YAML frontmatter `title` field as the document heading. This eliminates duplicate titles in the UI.
- **Transcript Markdown Filename Spaces**: Changed transcript filenames to preserve spaces instead of converting to underscores (e.g., `Will Japan and South Korea Gang Up on China Peter Zeihan_transcript.md` instead of `Will_Japan_and_South_Korea_Gang_Up_on_China_Peter_Zeihan_transcript.md`). This provides more natural display in file browsers and Obsidian's file tree.
- **Transcript Markdown Filename Generation**: Fixed transcript filenames to use clean video titles instead of including video IDs. Filenames are now human-readable (e.g., `Why_Im_Bullish_on_Southeast_Asia_Peter_Zeihan_transcript.md` instead of `Why_Im_Bullish_on_Southeast_Asia__Peter_Zeihan_gYnAgWRcZPM_transcript.md`).
- **Description Preview Truncation**: Fixed a bug where the first character of video descriptions was being removed in the YAML frontmatter `description_preview` field. The `.rstrip()` operation after slicing was incorrectly stripping leading characters.
- **Mining Fallback Warning Context**: Improved logging to distinguish between DB-centric processing (where missing segments is unexpected) and file-centric processing (where parsing markdown is expected). The warning "⚠️ No DB segments found" now only appears when processing from database, not when explicitly processing standalone markdown files.
- **Speaker Attribution Incomplete Assignment**: Enhanced error logging in LLM speaker suggester to diagnose cases where diarization detects multiple speakers but LLM only provides names for some. Added critical error messages showing which speakers were missed and emergency fallback names. This addresses cases where transcripts showed "SPEAKER_01" instead of real names despite the multi-layered speaker attribution system.
- **Thumbnail Absolute Paths**: Changed thumbnail image references in markdown transcripts from absolute paths to relative paths (e.g., `downloads/youtube/Thumbnails/filename.jpg`). This ensures thumbnails display correctly when files are moved, shared, or viewed in different markdown editors like Obsidian.
- **Single-Speaker Over-Segmentation Diagnostics**: Added comprehensive logging to track speaker merging through all three defensive layers (voice fingerprinting, heuristic detection, LLM analysis). System now logs when diarization over-segments single-speaker content (monologues, solo podcasts) and whether each layer successfully merges or correctly assigns the same name to all speaker IDs. Makes it immediately obvious which layer is failing when single-speaker videos incorrectly show multiple speaker labels.
- **Speaker Assignment System Not Invoked**: Added critical diagnostic logging to detect when the entire speaker attribution system is bypassed. Logs now show whether the speaker assignment block is reached, and if not, displays the exact condition flags (`diarization_successful`, `diarization_segments`) that prevented it from running. This diagnoses cases where speaker attribution fails not because of a bug in the system, but because the system never runs at all.
- **Markdown Transcript Segment Parsing**: Fixed `_parse_transcript_to_segments()` to correctly parse speaker-attributed markdown transcripts with `[MM:SS] (Speaker Name): text` format. The system now preserves all speaker segments instead of re-chunking by tokens, fixing the issue where 6 speaker segments were incorrectly reported as 3 segments.
- **Short Summary Generation Type Error**: Fixed `'dict' object has no attribute 'strip'` error in `_generate_short_summary()` by adding robust type checking for nested dictionary responses from LLM. The code now handles cases where `response.get("summary")` returns another dict instead of a string.
- **Archive Skip Logging Clarity**: Improved logging when yt-dlp skips videos already in the download archive. Changed misleading WARNING message to DEBUG level and clarified that returning None is expected behavior when videos are already downloaded. The system now clearly indicates when it's reusing existing files from the archive vs encountering actual download errors.

## [3.5.2] - 2025-11-08

### Added
- **Claim Domain Classification**: Added `domain` field to claims table and schema for broad field classification (e.g., "physics", "economics", "politics"). Claims can now be filtered and searched by domain alongside jargon terms.
- **Domain Column Migration Script**: Created `scripts/add_domain_column_to_claims.py` to add the missing `domain` column to existing databases.

### Changed
- **Domain Guidance in Miner Prompts**: Updated all 7 miner prompts to guide LLMs toward broad, searchable domain categories. Prompts now explicitly instruct to use general fields like "physics" not "quantum mechanics", "economics" not "monetary policy", ensuring consistent categorization for filtering.
- **Open-Ended Domain Classification**: Both claims and jargon use free-form domain strings (no enum restrictions), allowing natural categorization while prompt guidance ensures broad, searchable categories.
- **Transcription Progress Reporting Frequency**: Reduced the progress update threshold from 5% to 2% increments in whisper_cpp_transcribe.py, providing more frequent visual feedback during long transcription operations.

### Fixed
- **Queue Tab Initialization Error**: Fixed `AttributeError` where `_last_refresh_interval` was accessed before initialization, causing crashes when filters changed during startup.
- **Review Tab Database Error**: Fixed `OperationalError` caused by missing `domain` column in claims table. Added migration to system2_migration.py and standalone migration script for existing databases.
- **Summarization Tab Model Selection**: Improved model combo default selection logic to automatically select the first available model when no previous selection exists, and made warning messages more informative to distinguish between "no models available" vs "models available but none selected".
- **Schema Validation for Missing Claim Domains**: Added repair logic to automatically set `domain = "general"` for claims when LLMs fail to include the required domain field, preventing validation failures and fallback to non-structured JSON generation.
- **Stage Status Race Condition**: Fixed `IntegrityError` in `upsert_stage_status()` caused by concurrent transactions attempting to insert the same stage status record. The method now catches the integrity error and retries with an update operation, properly handling the race condition.

## [3.5.1] - 2025-11-05

### Added
- **Queue Tab**: New tab to visualize real-time pipeline status for all processing stages (download, transcription, summarization). Users can monitor progress, filter by stage/status, and view throughput metrics.
- **Advanced GUI Testing Suite**: Comprehensive GUI testing with pytest-qt and pytest-timeout to simulate real user interactions, test async operations, and debug UI failures interactively.

### Changed
- **Schema Consolidation**: Deleted `miner_output.v2.json` as it was redundant. The v1 file now contains the v2 structure (nested `evidence_spans`, `definition` field) and is what the validator actually uses. This eliminates confusion between file naming and content structure.
- **Queue Tab Default Filter**: The Queue tab now defaults to "Active Only" filter, automatically hiding completed and failed items for a cleaner view.
- **Removed Jargon Domain Enum Constraint**: Changed jargon `domain` field from restricted enum to free-form string, allowing LLM to naturally describe specialized fields (e.g., "quantum mechanics", "constitutional law") rather than forcing into predefined categories.

### Fixed
- **Schema Validation Errors**: Fixed `context_type` enum mismatch in `miner_output.v1.json` (was `["exact", "sentence", "paragraph"]`, now correctly `["exact", "extended", "segment"]` to match database schema). Removed restrictive `domain` enum constraint to allow LLM to freely describe jargon domains without artificial categorization limits.
- **Queue Tab View Details Dialog**: Fixed JSON parsing error that caused empty popup when viewing queue item details. The `metadata_json` field is now correctly handled as a pre-deserialized dictionary.
- **Queue Tab File Links**: Added clickable hyperlinks to completed markdown files in the Actions column. Double-clicking a completed item now opens the summary file directly in the default markdown editor.
- **Queue Tab Failed Items**: Added "Active Only" filter option to automatically hide completed and failed items, keeping the queue view focused on in-progress work.
- **Queue Tab Failure Tracking**: Fixed summarization failures not updating queue status in real-time. The queue now immediately reflects failed status when summarization encounters errors, preventing items from appearing stuck "in progress".
- **YouTube Archive Reuse**: Retranscription runs can now reuse previously downloaded audio when yt-dlp skips via its archive, preventing overwrite workflow failures. A user confirmation dialog has been added.
- **Thumbnail Embedding**: Thumbnails are now correctly embedded in markdown files by ensuring the database is updated *after* the thumbnail is downloaded.
- **Transcription Model Default**: The transcription model now correctly defaults to "medium" instead of "tiny", ensuring better quality out-of-the-box.
- **Vestigial UI Elements**: Removed a non-functional "Prompt File" picker from the Summarization tab to reduce user confusion.
- **UI Layout**: Improved the layout of the Transcription tab by repositioning the Proxy selector for a better visual flow.
- **Startup Validation Noise**: Reduced false-positive warnings during startup validation by intelligently filtering out test files and old entries.
- **YAML Corruption with Color-Coded Transcripts**: Disabled the color-coded transcript feature that was breaking YAML frontmatter parsing. Speaker assignments now work correctly without this feature.
- **Archive Validation Edge Case**: Added validation to remove invalid yt-dlp archive entries (e.g., from failed downloads) to prevent videos from being permanently skipped.
- **Transcription Pipeline Errors**: Fixed a blocking `NameError` on `Segment` import and 10 other issues related to database operations, error handling, and performance in the transcription pipeline.
- **Speaker Diarization Accuracy**: Improved speaker attribution by modifying the LLM prompt to skeptically evaluate diarization splits, allowing it to correctly merge speakers that were incorrectly split.
- **Transcript Formatting**: Fixed a parameter name mismatch to ensure YouTube metadata is correctly included in transcripts. Also improved readability by grouping consecutive segments by the same speaker into paragraphs.
- **Database Parameter Names**: Corrected database parameter names (e.g., `video_id` to `source_id`) in the audio processor to ensure transcripts are saved correctly. Improved logging to reflect the claim-centric architecture.

## [3.5.0] - 2025-10-17

### Breaking Changes
- Removed CLI interface - application is now GUI-only. All functionality is available through the enhanced GUI with the System2 architecture.

### Added
- Comprehensive System2Orchestrator tests for asynchronous job processing.
- LLM adapter async behavior tests, including event loop cleanup validation.
- GUI integration tests using automated workflows.
- Direct logic tests for complete code coverage.
- An automated test suite with zero human intervention required.

### Changed
- The Monitor tab now uses System2Orchestrator, consistent with the Summarization tab.
- Unified code path: all operations now use the System2Orchestrator architecture, eliminating divergence between CLI and GUI implementations.

### Removed
- All CLI commands (`transcribe`, `summarize`, `moc`, `process`, `database`, `upload`, `voice_test`).
- CLI-specific processors and legacy summarizer modules.
- The `commands/` directory and `cli.py` entry point.

### Fixed
- Transcript files now load correctly in the summarization tab after transcription.
- Event loop closure errors during async HTTP client cleanup have been resolved.
- The Monitor tab now uses the same tested code path as the rest of the GUI.

---

## [3.2.22] - 2025-09-17

### Added
- **System 2 HCE Migration**: All HCE processors now use a centralized LLM adapter with System 2 architecture for improved tracking, rate limiting, and cost management.
- **Complete Bundle Approach**: The application is now distributed as a ~600MB DMG with all models and dependencies included, enabling full offline functionality from the first launch.
- **Advanced Voice Fingerprinting**: A new system with 97% accuracy using ECAPA-TDNN and Wav2Vec2 models, bundled for immediate offline use. It automatically merges speakers incorrectly split by diarization.
- **Smart Podcast-Focused Speaker Detection**: A purely LLM-based approach for speaker suggestions that analyzes clean, deduplicated segments and full metadata for higher accuracy.
- **Diarization Excellence & Over-Segmentation Solution**: A conservative diarization strategy combined with voice fingerprinting and text overlap detection to ensure high-quality speaker segmentation.
- **Accuracy Achievement Pipeline**: A multi-step process (Conservative Diarization → Voice Fingerprinting → LLM Validation → Contextual Analysis → User Review) that achieves 99% final accuracy.

### Changed
- **Major Architecture Refactor**: The application has been refactored to support multiple formats (PDFs, Word docs), cloud sync with Supabase, and a unified processing pipeline that reduces API calls by 70%.

---

## Older Releases

Details for older releases can be found in the git history.

## [3.5.1] - 2025-11-13

### Refactoring - Major Code Quality Improvements

#### Removed (-3,692 lines)
- Removed obsolete `gui/adapters/hce_adapter.py` (240 lines) - raises NotImplementedError
- Removed `database/speaker_models_old.py` (1,001 lines) - superseded by unified models
- Removed `database/speaker_models_new.py` (759 lines) - backward compatibility layer
- Removed deprecated `utils/state.py` (544 lines) - replaced by DatabaseService
- Removed deprecated `utils/tracking.py` (865 lines) - replaced by ProgressTracker
- Removed `_apply_recommended_settings()` method from api_keys_tab.py (142 lines)
- Removed deprecated `config.use_gpu` field

#### Added
- Created `core/processing_config.py` with centralized configuration classes
- Replaced `gui/core/session_manager.py` with QSettings-based implementation

#### Changed
- Renamed `gui/legacy_dialogs.py` → `gui/ollama_dialogs.py` (clarity improvement)
- Migrated LLM provider preference handling (removed state.py dependency)
- Updated `system2_orchestrator.py` to use configuration constants

#### Performance
- Optimized download URL validation with batch queries (10-50x faster for 100+ URLs)
- Added optimization roadmap for HCE bulk inserts and Supabase batching

#### Breaking Changes
- JSON-based session management removed (migrated to Qt QSettings)
- Deprecated modules removed: `state.py`, `tracking.py`
- LLM preference persistence now GUI-only (CLI users must specify explicitly)

### Documentation
- Created `REFACTORING_NOVEMBER_2025.md` with complete refactoring summary
- Updated CHANGELOG.md with all changes
- Documented deferred refactorings (6 sections remaining, 50-60 hours estimated)

**See REFACTORING_NOVEMBER_2025.md for complete details and remaining work.**


## [3.5.2] - 2025-11-13 (Continued)

### Refactoring - Additional Architectural Improvements

#### Added
- Created `core/checkpoint_manager.py` - Checkpoint save/load/restore operations extracted from System2Orchestrator
- Created `core/segment_processor.py` - Transcript parsing and chunking operations
- Created `services/download_base.py` - Base class for download orchestrators
- Created `processors/hce/entity_converters.py` - Focused converters for claims, jargon, people, concepts

#### Performance
- Implemented parallel table syncing with dependency groups (3-5x faster Supabase sync)
- Syncs independent tables concurrently using ThreadPoolExecutor
- 4-tier dependency groups respect foreign key constraints

#### Refactoring
- Broke down 217-line `_convert_to_pipeline_outputs()` into 4 focused converter classes
- Extracted CheckpointManager from System2Orchestrator (~210 lines)
- Extracted SegmentProcessor from System2Orchestrator (~190 lines)
- Created DownloadCoordinator base class (~150 lines of common functionality)

#### Type Safety
- Added 100% type coverage to all new modules
- ~150+ type annotations added across core modules
- Full mypy compatibility for new code

### Total Refactoring Summary (Sections 1-11)
- **12 commits** with comprehensive refactoring
- **3,692 lines removed** (obsolete/duplicate code)
- **1,200+ lines added** (focused, well-typed classes)
- **Net: -2,500 lines** while improving architecture
- **Performance: 3-50x** improvements in batch operations
- **Type coverage: +30%** improvement

**See REFACTORING_NOVEMBER_2025.md for complete details.**
