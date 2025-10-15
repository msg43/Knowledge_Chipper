# yt-dlp Quick Reference Guide

## TL;DR - Industry Best Practice

✅ **DO**: Test updates in development, then pin tested versions for production  
❌ **DON'T**: Auto-update on launch or in production without testing

## The Problem

- YouTube changes their API frequently → old yt-dlp versions break
- But: yt-dlp updates could introduce bugs → can't auto-update in production
- Solution: **Staged testing workflow**

## Your Setup (After Implementation)

### Development Environment
- Uses `requirements-dev.txt`
- Allows `yt-dlp>=2025.9.26` (can update freely)
- Test latest versions before releasing to users

### Production (DMG Builds)
- Uses `requirements.txt` and `pyproject.toml`
- Pins `yt-dlp==2025.9.26` (exact tested version)
- Users get stable, tested versions only

## Weekly Workflow (Recommended)

### Monday Morning: Test Updates

```bash
# Full testing workflow (recommended)
make test-ytdlp-update
```

This will:
1. ✅ Check for updates
2. ✅ Install latest version
3. ✅ Run automated tests
4. ✅ Prompt for manual testing
5. ✅ Update production pins if all passes
6. ✅ Show you what to commit

**Time required**: 10-15 minutes

### Quick Check (If You're in a Hurry)

```bash
# Just check/update version
make update-ytdlp
```

⚠️ This updates your dev environment but doesn't update production pins.

## Emergency: YouTube Just Broke

When YouTube downloads suddenly fail:

```bash
# 1. Quick update
make update-ytdlp

# 2. Test ONE video
knowledge-system youtube https://www.youtube.com/watch?v=dQw4w9WgXcQ

# 3. If works, manually update pins
# Edit requirements.txt: yt-dlp==NEW_VERSION
# Edit pyproject.toml: yt-dlp==NEW_VERSION

# 4. Commit and release
git add requirements.txt pyproject.toml
git commit -m "Emergency: Update yt-dlp to fix YouTube breakage"
make build  # Build new DMG
```

**Trade-off**: Ship working-but-minimally-tested > broken-but-"stable"

## File Structure

```
requirements-dev.txt     # Development: yt-dlp>=2025.9.26 (flexible)
├─ requirements.txt      # Production: yt-dlp==2025.9.26 (pinned)
└─ pyproject.toml        # Production: yt-dlp==2025.9.26 (pinned)
```

**Single source of truth**: `pyproject.toml` → reflected in `requirements.txt`

## Commands Cheat Sheet

```bash
# Development setup (installs requirements-dev.txt)
make install

# Check current version
pip show yt-dlp | grep Version

# Quick update (dev only)
make update-ytdlp

# Full testing workflow (updates production pins)
make test-ytdlp-update

# Build DMG (uses pinned versions)
./scripts/build_macos_app.sh --make-dmg
```

## What Happens in Each Environment

### Developer's Machine
```bash
make install
# → Installs requirements-dev.txt
# → Gets yt-dlp>=2025.9.26 (latest available)
# → Can test updates before releasing
```

### Build Process (DMG Creation)
```bash
./scripts/build_macos_app.sh --make-dmg
# → Uses requirements.txt
# → Gets yt-dlp==2025.9.26 (exact pin)
# → Ensures reproducible builds
```

### User's Machine (After Installing DMG)
```
# Built-in app bundle contains:
# → yt-dlp==2025.9.26 (tested version)
# → Never auto-updates
# → User must download new DMG for updates
```

## Version History Tracking

When you update, document it:

```python
# requirements.txt
yt-dlp==2025.10.15  # Last tested: 2025-10-15 - Fixed age-gate bypass

# pyproject.toml  
"yt-dlp==2025.10.15",  # Last tested: 2025-10-15 - See docs/DEPENDENCY_UPDATE_STRATEGY.md
```

This helps you track:
- When you last tested
- What was fixed/changed
- Rollback point if needed

## Rollback Process

If an update breaks things:

```bash
# 1. Revert to last known-good version
git log requirements.txt  # Find last good commit
git checkout COMMIT_HASH requirements.txt pyproject.toml

# 2. Reinstall
pip install -r requirements.txt --force-reinstall

# 3. Verify works
knowledge-system youtube [test-url]

# 4. Commit rollback
git add requirements.txt pyproject.toml
git commit -m "Rollback: yt-dlp NEW_VERSION broke X, reverting to OLD_VERSION"
```

## Monitoring Strategy

### GitHub Watch
- Watch: https://github.com/yt-dlp/yt-dlp/releases
- Enable notifications for new releases
- Check release notes for critical fixes

### User Reports
- YouTube failures will be reported by users first
- Have clear update instructions for users
- Fast emergency patch workflow ready

### Automated (Optional)
- GitHub Actions can run weekly tests
- Auto-create PR if tests pass
- See `docs/DEPENDENCY_UPDATE_STRATEGY.md` for implementation

## FAQ

**Q: Why not just use `yt-dlp>=2025.9.26` everywhere?**  
A: Users would get untested versions. Desktop apps should ship known-good versions.

**Q: Why not auto-update on app launch?**  
A: Updates could break the app. Users expect stability, not surprise updates.

**Q: What if I forget to update?**  
A: YouTube will break, users will complain, you do emergency update. That's why weekly testing is recommended.

**Q: Can I automate this?**  
A: Partially - you can automate testing, but human verification is recommended before shipping to users.

**Q: What if yt-dlp releases multiple times per week?**  
A: You don't need every release. Update when: (1) weekly schedule, (2) YouTube breaks, (3) critical security fix.

## This Matches How Big Apps Work

- **VS Code**: Pins Electron version, tests updates before releasing
- **Slack**: Pins all dependencies, staged rollout
- **Chrome**: Tests updates extensively before auto-updating

You're doing it right! 🎉
