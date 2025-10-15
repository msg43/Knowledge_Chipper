# yt-dlp Management - Quick Start Guide

## Your Questions, Answered Simply

### 1. How do we know when a new yt-dlp version has been released?

**Best Option: GitHub Watch (2 minutes setup)**
1. Go to https://github.com/yt-dlp/yt-dlp
2. Click "Watch" button → "Custom" → Check "Releases" → Apply
3. Done! GitHub will notify you of new releases.

**Alternative: Weekly Check**
```bash
make check-ytdlp-releases
```

### 2. How do we know what's in that version and whether it's risky?

**Automated Risk Assessment:**
```bash
make check-ytdlp-releases
```

This shows:
- 🔴 CRITICAL → Security issues (update NOW)
- 🟠 HIGH → Breaking changes (careful testing)
- 🟢 SAFE → YouTube fixes (safe to update!)
- 🟡 MEDIUM → Normal changes (standard testing)
- 🟢 LOW → Minor fixes (safe to update)

---

## Weekly Workflow (10 Minutes)

### Monday Morning Routine

```bash
# 1. Check for updates
make check-ytdlp-releases

# 2. Look at the risk level
# If 🟢 SAFE or 🟢 LOW:

# 3. Test and update
make test-ytdlp-update

# 4. Follow the prompts, test manually when asked

# 5. If all tests pass, commit
git add requirements.txt pyproject.toml
git commit -m "Update yt-dlp to VERSION (tested)"
```

That's it!

---

## Emergency: YouTube Broke!

```bash
# 1. Quick check
make check-ytdlp-releases

# 2. If YouTube fix available:
make update-ytdlp

# 3. Test one video
knowledge-system youtube https://www.youtube.com/watch?v=dQw4w9WgXcQ

# 4. If works, manually update:
# Edit requirements.txt: yt-dlp==NEW_VERSION
# Edit pyproject.toml: yt-dlp==NEW_VERSION

# 5. Commit and release
git add requirements.txt pyproject.toml
git commit -m "Emergency: Update yt-dlp to fix YouTube"
```

---

## What You Have Now

### ✅ Monitoring
- GitHub Watch for notifications
- RSS feed option
- Automated cron job option
- Manual checker: `make check-ytdlp-releases`

### ✅ Risk Assessment
- Automatic analysis of release notes
- Clear risk levels (🔴🟠🟢🟡)
- Actionable recommendations
- Links to full details

### ✅ Testing Workflow
- Dev environment tests latest versions
- Production pins tested versions
- Semi-automated update process
- Clear commit messages

### ✅ Documentation
- `docs/YT-DLP_MONITORING_GUIDE.md` - Complete guide
- `docs/YT-DLP_QUICK_REFERENCE.md` - Cheat sheet
- `docs/YT-DLP_UPDATE_GUIDE.md` - Update procedures
- `YT-DLP_MONITORING_IMPLEMENTATION.md` - What was implemented

---

## Commands Cheat Sheet

```bash
# Check releases with risk assessment
make check-ytdlp-releases

# Full testing workflow (updates production pins)
make test-ytdlp-update

# Quick dev update (no pin update)
make update-ytdlp

# Setup notifications
./scripts/setup_ytdlp_notifications.sh

# Help menu
make help
```

---

## Try It Now!

```bash
make check-ytdlp-releases
```

See what's new and whether it's safe to update!

---

**Status:** You're on yt-dlp 2025.9.26 (latest as of Oct 11, 2025)

**Next Check:** Monday morning, or when YouTube breaks

**Full Details:** See `YT-DLP_MONITORING_IMPLEMENTATION.md`
