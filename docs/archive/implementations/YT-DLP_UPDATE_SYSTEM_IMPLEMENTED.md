# yt-dlp Update System - Implementation Complete

## Problem Solved

**Original Issue**: "Our whole system breaks if yt-dlp updates"

**Actually**: System breaks when you DON'T update (YouTube changes constantly)

**Risk**: Auto-updating could also break the system (untested versions)

## Solution Implemented: Industry Best Practice

**Staged Deployment with Tested Pins**

- ✅ Development: Test latest versions freely
- ✅ Production: Ship only tested, pinned versions
- ✅ Workflow: Weekly testing + emergency patches
- ✅ Balance: Stay current without breaking user installs

## What Was Implemented

### 1. Dual Requirements Strategy

**requirements-dev.txt** (Development)
```python
yt-dlp>=2025.9.26  # Allows testing latest versions
```

**requirements.txt** (Production/Build)
```python
yt-dlp==2025.9.26  # Exact tested version for users
```

**pyproject.toml** (Package metadata)
```python
"yt-dlp==2025.9.26"  # Matches requirements.txt
```

### 2. Testing Workflow Script

**scripts/test_ytdlp_update.sh**
- Checks for updates
- Installs latest version
- Runs automated tests (import, version, YouTube info extraction)
- Prompts for manual testing
- Updates production pins if all passes
- Shows commit instructions

### 3. Quick Update Script

**scripts/update_ytdlp.sh**
- Quick version check and update
- For development environment only
- Doesn't update production pins

### 4. Make Commands

```bash
make install              # Dev setup (uses requirements-dev.txt)
make update-ytdlp         # Quick check/update (dev only)
make test-ytdlp-update    # Full testing workflow (updates production)
```

### 5. Documentation

- **docs/DEPENDENCY_UPDATE_STRATEGY.md**: Full strategy guide
- **docs/YT-DLP_UPDATE_GUIDE.md**: Update procedures
- **docs/YT-DLP_QUICK_REFERENCE.md**: Quick reference cheat sheet

## How It Works

### Weekly Workflow (Recommended)

```bash
# Monday morning
make test-ytdlp-update
# → Tests update
# → Prompts for manual verification  
# → Updates production pins if passes
# → Shows what to commit

git add requirements.txt pyproject.toml
git commit -m "Update yt-dlp to VERSION (tested)"
```

### Emergency Workflow (YouTube Broke)

```bash
make update-ytdlp  # Quick update
# Test manually
# Edit requirements.txt and pyproject.toml manually
git commit -m "Emergency: Update yt-dlp to fix YouTube"
make build  # Rebuild DMG
```

## Key Design Decisions

### ✅ Pin Exact Versions for Users
**Why**: Desktop apps should ship predictable, tested versions
**How**: `yt-dlp==2025.9.26` in requirements.txt and pyproject.toml

### ✅ Allow Flexible Versions in Dev  
**Why**: Need to test updates before releasing
**How**: `yt-dlp>=2025.9.26` in requirements-dev.txt

### ✅ Manual Promotion After Testing
**Why**: Human verification catches issues automation might miss
**How**: Semi-automated workflow with manual approval gates

### ❌ NO Auto-Update on Launch
**Why**: Could break production without testing
**How**: DMG bundles exact version, users update by downloading new DMG

### ❌ NO Pre-Commit Auto-Update
**Why**: Could cause commit failures and build inconsistencies  
**How**: Separate workflow for updating, commit only after testing

## File Changes Made

### Modified
- ✅ `requirements.txt`: Pinned yt-dlp==2025.9.26
- ✅ `pyproject.toml`: Pinned yt-dlp==2025.9.26
- ✅ `Makefile`: Added update commands, updated install command

### Created
- ✅ `requirements-dev.txt`: Development requirements with flexible versions
- ✅ `scripts/update_ytdlp.sh`: Quick update script
- ✅ `scripts/test_ytdlp_update.sh`: Full testing workflow
- ✅ `docs/DEPENDENCY_UPDATE_STRATEGY.md`: Complete strategy guide
- ✅ `docs/YT-DLP_UPDATE_GUIDE.md`: Update procedures
- ✅ `docs/YT-DLP_QUICK_REFERENCE.md`: Quick reference

## Build Process Integration

Your existing build scripts already use `requirements.txt`:

```bash
# scripts/build_macos_app.sh (line 847)
sudo -H "$MACOS_PATH/venv/bin/python" -m pip install -r "$MACOS_PATH/requirements.txt"
```

✅ No changes needed! Builds will use pinned versions automatically.

## Current Status

- **Current Version**: yt-dlp 2025.9.26 (latest as of 2025-10-11)
- **Status**: ✅ Tested and working
- **Next Check**: Monday, 2025-10-18 (or when YouTube breaks)

## Comparison to Other Approaches

### ❌ Approach 1: Auto-update on Launch
```python
if update_available():
    auto_update()  # RISKY!
```
**Problem**: Users get untested versions, could break production

### ❌ Approach 2: Never Update
```python
yt-dlp==2023.12.0  # Old version
```
**Problem**: YouTube changes break downloads, users can't use app

### ✅ Approach 3: Staged Testing (Implemented)
```python
# Dev: test latest
# Prod: ship tested
# Weekly: promote after testing
```
**Result**: Stay current AND stable

## Matches Industry Standards

This implementation matches how major desktop applications handle critical dependencies:

- **VS Code**: Tests Electron updates, pins for releases
- **Slack**: Pins all dependencies, staged rollout
- **Docker Desktop**: Tests updates extensively before shipping
- **Chrome**: Automated testing + staged deployment

## Next Steps for You

### This Week
1. ✅ System is set up and working
2. ✅ Current version (2025.9.26) is latest and tested

### Next Week (Monday)
```bash
make test-ytdlp-update
```

### If YouTube Breaks
```bash
make update-ytdlp
# Test manually
# Update pins
# Emergency release
```

### Optional: Automate Testing
- Set up GitHub Actions for weekly automated tests
- See `docs/DEPENDENCY_UPDATE_STRATEGY.md` for CI/CD examples

## Summary

You now have a **production-grade dependency management system** that:

- ✅ Prevents breaking changes from reaching users
- ✅ Enables testing latest versions in development  
- ✅ Provides clear workflow for updates
- ✅ Balances stability and currency
- ✅ Matches industry best practices
- ✅ Integrates with existing build system
- ✅ Supports emergency patches when needed

**The system won't break when yt-dlp updates, because you test updates before shipping them to users.**

---

**Implementation Date**: October 11, 2025  
**Current yt-dlp Version**: 2025.9.26  
**Status**: ✅ Production Ready
