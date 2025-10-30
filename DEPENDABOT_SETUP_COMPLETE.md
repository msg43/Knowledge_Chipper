# Dependabot Setup Complete ✅

**Simple, automated yt-dlp update notifications via Pull Requests.**

## What Was Added

**1 file:** `.github/dependabot.yml`  
**1 doc:** `docs/DEPENDABOT_YTDLP_SETUP.md`

That's it!

## What It Does

Dependabot automatically:
- ✅ Checks PyPI **weekly** (Mondays at 9 AM PST)
- ✅ Creates **Pull Requests** when yt-dlp updates are available
- ✅ Updates both `pyproject.toml` and `requirements.txt`
- ✅ Includes **changelog** from GitHub releases
- ✅ Sends **notifications** (email + GitHub + mobile)

## Deploy Now (30 seconds)

```bash
git add .github/dependabot.yml docs/DEPENDABOT_YTDLP_SETUP.md MANIFEST.md Makefile DEPENDABOT_SETUP_COMPLETE.md
git commit -m "Add Dependabot for automated yt-dlp monitoring"
git push
```

**Done!** Dependabot is now monitoring yt-dlp.

## What You'll Get

When yt-dlp releases a new version, you'll receive a PR:

**Title:** `Bump yt-dlp from 2025.10.14 to 2025.11.01`

**Files Changed:**
- `pyproject.toml` - Version updated
- `requirements.txt` - Version updated

**Description:**
- Full changelog from GitHub releases
- Link to compare view

**What You Do:**
1. Review changelog
2. Test: `make test-ytdlp-update`
3. Merge: Click "Merge" in GitHub UI

## Enable Notifications

**Email:**
1. Go to https://github.com/settings/notifications
2. Enable "Email" under "Watching"

**Mobile:**
- iOS: https://apps.apple.com/app/github/id1477376905
- Android: https://play.google.com/store/apps/details?id=com.github.android

## Commands

```bash
# Check for Dependabot PRs
gh pr list --label "dependencies"

# Test a PR
gh pr checkout <PR-number>
make test-ytdlp-update

# Merge a PR
gh pr merge <PR-number>
```

## Documentation

See `docs/DEPENDABOT_YTDLP_SETUP.md` for full details.

---

**Setup:** 30 seconds  
**Maintenance:** Zero  
**Benefit:** Never miss a critical yt-dlp update
