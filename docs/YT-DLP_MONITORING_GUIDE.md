# yt-dlp Release Monitoring & Risk Assessment Guide

This guide answers two critical questions:
1. **How do we know when a new yt-dlp version has been released?**
2. **How do we know what's in that version and whether it's risky?**

---

## Quick Answer

### 1. How to Know About New Releases

**Automated Tool (Recommended):**
```bash
make check-ytdlp-releases
```
This shows recent releases with risk assessment.

**Manual Options:**
- GitHub Watch: https://github.com/yt-dlp/yt-dlp (click "Watch" → "Custom" → "Releases")
- RSS Feed: https://github.com/yt-dlp/yt-dlp/releases.atom
- Email Notifications: GitHub can email you about releases

### 2. How to Assess Risk

**Automated Risk Assessment:**
Our script analyzes release notes for:
- 🔴 **CRITICAL**: Security fixes (update immediately)
- 🟠 **HIGH**: Breaking changes (test carefully)
- 🟢 **SAFE**: YouTube fixes (usually safe to update)
- 🟡 **MEDIUM**: Significant changes (test normally)
- 🟢 **LOW**: Maintenance updates (safe)

---

## Monitoring Methods

### Method 1: GitHub Watch (Best for Active Developers)

**Setup (One-time):**
1. Go to https://github.com/yt-dlp/yt-dlp
2. Click "Watch" button (top right)
3. Select "Custom"
4. Check "Releases"
5. Click "Apply"

**Result:**
- Get notifications for every release
- View in GitHub notifications dashboard
- Optional email notifications

**Pros:**
- ✅ Instant notifications
- ✅ Can see full release notes
- ✅ Free, no setup required

**Cons:**
- ❌ Can be noisy (yt-dlp releases frequently)
- ❌ Requires checking GitHub regularly

### Method 2: RSS Feed (Best for RSS Users)

**Setup:**
Add this feed to your RSS reader:
```
https://github.com/yt-dlp/yt-dlp/releases.atom
```

**Good RSS Readers:**
- **Mac**: Reeder, NetNewsWire (free), Feedly
- **Web**: Feedly, The Old Reader, Inoreader
- **CLI**: newsboat, rss2email

**Pros:**
- ✅ Consolidated with other feeds
- ✅ Read at your own pace
- ✅ No email clutter

**Cons:**
- ❌ Requires RSS reader
- ❌ Manual setup

### Method 3: Automated Script (Best for Weekly Checks)

**Our built-in tool:**
```bash
./scripts/check_ytdlp_changelog.sh
```

**What it does:**
1. Checks your current version
2. Fetches latest 5 releases from GitHub
3. Shows release notes with risk assessment
4. Provides update recommendation

**Example output:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 Current version: 2025.9.26
🆕 Latest version:  2025.10.15

📌 2025.9.26 (YOUR VERSION) - 2025-09-26
   Risk: 🟢 SAFE
   Key changes:
     • Fix YouTube signature extraction
     • Improve format selection

🆕 2025.10.15 (LATEST) - 2025-10-15
   Risk: 🟢 SAFE
   Key changes:
     • Fix YouTube throttling
     • Add support for new video formats

🎯 RECOMMENDATION:
   🟢 SAFE: 1 YouTube fix(es) available
   ACTION: Safe to update - run: make test-ytdlp-update
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Pros:**
- ✅ Risk assessment built-in
- ✅ Clear recommendations
- ✅ Fast (runs in seconds)

**Cons:**
- ❌ Manual execution required
- ❌ Depends on GitHub API (rate limits apply)

### Method 4: Cron Job (Best for Automation)

**Setup a weekly check:**
```bash
crontab -e
```

Add this line:
```bash
# Check yt-dlp releases every Monday at 9 AM
0 9 * * 1 cd /Users/matthewgreer/Projects/Knowledge_Chipper && /usr/local/bin/make check-ytdlp-releases > /tmp/ytdlp_check.log 2>&1 && cat /tmp/ytdlp_check.log
```

Or send email notifications:
```bash
# Email notification if updates available
0 9 * * 1 cd /Users/matthewgreer/Projects/Knowledge_Chipper && /Users/matthewgreer/Projects/Knowledge_Chipper/scripts/check_ytdlp_changelog.sh | grep -q "LATEST" && mail -s "yt-dlp update available" your@email.com < /tmp/ytdlp_check.log
```

**Pros:**
- ✅ Fully automated
- ✅ Scheduled checks

**Cons:**
- ❌ Requires cron setup
- ❌ May miss urgent updates between checks

---

## Risk Assessment System

Our script analyzes release notes for specific keywords to assess risk:

### 🔴 CRITICAL (Security Issues)
**Keywords:** `security`, `vulnerability`, `CVE`, `exploit`

**Example Release Notes:**
> "Fix security vulnerability in cookie handling (CVE-2024-1234)"

**Action:** Update immediately, test minimally, release emergency patch

**Why Critical:**
- Security vulnerabilities can expose user data
- Exploits could compromise systems
- Often have active attacks in the wild

### 🟠 HIGH (Breaking Changes)
**Keywords:** `breaking`, `incompatible`, `removed`, `deprecated`

**Example Release Notes:**
> "Breaking: Removed support for legacy format selection"
> "Deprecated: --old-flag replaced with --new-flag"

**Action:** Test carefully, check if your code uses affected features

**Why High Risk:**
- Could break your existing code
- May require code changes
- Could cause runtime errors

### 🟢 SAFE (YouTube Fixes)
**Keywords:** `youtube`, `signature`, `extractor`, `format`, `throttling`

**Example Release Notes:**
> "Fix YouTube signature extraction"
> "Improve format selection for YouTube videos"
> "Work around YouTube throttling"

**Action:** Safe to update - these are the main reason we update

**Why Safe:**
- Usually isolated to YouTube extractor
- Don't change API or behavior
- Fix actual user problems (broken downloads)

### 🟡 MEDIUM (Significant Changes)
**Keywords:** `changed`, `modified`, `refactor`, `rewrite`

**Example Release Notes:**
> "Refactor download manager for better performance"
> "Changed default user agent"

**Action:** Test normally with standard workflow

**Why Medium Risk:**
- Internal changes that might have edge cases
- Could affect performance or behavior
- Usually backward compatible but worth testing

### 🟢 LOW (Maintenance)
**Default for:** Bug fixes, minor improvements, documentation

**Example Release Notes:**
> "Fix typo in error message"
> "Improve documentation"
> "Minor performance improvement"

**Action:** Safe to update

**Why Low Risk:**
- Small, isolated changes
- Unlikely to break anything
- Good to stay current

---

## Practical Workflow

### Weekly Check (10 minutes on Monday)

```bash
# 1. Check what's new
make check-ytdlp-releases

# 2. Read the risk assessment

# 3. If safe/low risk:
make test-ytdlp-update

# 4. If high risk:
# Read full release notes at GitHub
# Test more carefully
# Check if your code uses affected features
```

### Before Each DMG Release

```bash
# Always check before building release
make check-ytdlp-releases

# Ensure you're on a tested version
# Consider updating if YouTube fixes available
```

### Emergency Response

**Scenario: YouTube downloads suddenly fail**

```bash
# 1. Check if it's a known issue
make check-ytdlp-releases

# 2. Look for YouTube-related fixes in recent releases
# If latest version has YouTube fixes:

# 3. Emergency update
make update-ytdlp

# 4. Quick test
knowledge-system youtube [test-url]

# 5. If works, update production pins
# (See emergency workflow in YT-DLP_QUICK_REFERENCE.md)
```

---

## Understanding Release Notes

### What to Look For

#### ✅ Good Signs (Safe to Update)
- "Fix YouTube [something]"
- "Work around [site] changes"
- "Improve format selection"
- "Update extractor for [site]"
- Bug fixes for specific issues

#### ⚠️ Warning Signs (Test Carefully)
- "Breaking change"
- "Removed support for"
- "Changed default behavior"
- "Refactored [major component]"
- "Requires Python X.X+"

#### 🔴 Urgent (Update Immediately)
- "Security fix"
- "CVE-"
- "Vulnerability"
- Any security-related mention

### Example Real Release Notes

**Safe Update (2025.9.26):**
```
- [YouTube] Fix signature extraction
- [YouTube] Improve format selection for premium content
- [Vimeo] Update extractor
- Fix progress bar display issue
```
**Assessment:** 🟢 SAFE - YouTube fixes, update recommended

**Risky Update (Hypothetical):**
```
- Breaking: Changed download hook signature
- Removed deprecated format selectors
- Requires Python 3.10+
- Refactored entire downloader engine
```
**Assessment:** 🟠 HIGH - Multiple breaking changes, test carefully

---

## Automation Options

### Option 1: GitHub Actions (Best for CI/CD)

Create `.github/workflows/check-ytdlp.yml`:

```yaml
name: Check yt-dlp Updates

on:
  schedule:
    - cron: '0 9 * * 1'  # Every Monday at 9 AM
  workflow_dispatch:  # Allow manual trigger

jobs:
  check-ytdlp:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'
      
      - name: Install yt-dlp
        run: pip install yt-dlp
      
      - name: Check for updates
        run: |
          CURRENT=$(cat requirements.txt | grep yt-dlp | cut -d'=' -f3)
          LATEST=$(pip index versions yt-dlp | grep LATEST | awk '{print $2}')
          echo "Current: $CURRENT"
          echo "Latest: $LATEST"
          
          if [ "$CURRENT" != "$LATEST" ]; then
            echo "::warning::yt-dlp update available: $CURRENT → $LATEST"
            echo "Check releases: https://github.com/yt-dlp/yt-dlp/releases"
          fi
```

This will:
- Run automatically every Monday
- Create a warning if updates available
- Visible in GitHub Actions dashboard

### Option 2: macOS Notification

Create a notification script:

```bash
#!/bin/bash
# ~/scripts/ytdlp-notify.sh

cd /Users/matthewgreer/Projects/Knowledge_Chipper
OUTPUT=$(./scripts/check_ytdlp_changelog.sh 2>&1)

if echo "$OUTPUT" | grep -q "LATEST.*available"; then
    osascript -e 'display notification "yt-dlp update available! Check changelog." with title "Knowledge Chipper"'
fi
```

Add to cron:
```bash
0 9 * * 1 ~/scripts/ytdlp-notify.sh
```

---

## FAQ

**Q: How often does yt-dlp release updates?**  
A: Varies widely - can be daily during YouTube changes, or weekly/monthly otherwise. Average ~2-4 releases per month.

**Q: Do I need to update for every release?**  
A: No. Update when: (1) weekly check shows YouTube fixes, (2) YouTube downloads break, (3) security issues.

**Q: What if I miss an update?**  
A: Not a problem. You can jump multiple versions. The risk assessment will show all changes between your version and latest.

**Q: Are there breaking changes often?**  
A: Rarely. yt-dlp is generally backward compatible. Breaking changes are clearly marked in release notes.

**Q: What if the GitHub API is rate limited?**  
A: The script falls back to showing the direct URL. You can also use RSS feeds which don't have rate limits.

**Q: Can I automate the update process entirely?**  
A: Not recommended for production. Auto-checking is fine, but updates should be tested before shipping to users.

---

## Quick Reference

### Commands
```bash
# Check for updates with risk assessment
make check-ytdlp-releases

# Full update workflow
make test-ytdlp-update

# Quick version check
make update-ytdlp
```

### URLs
- **Releases**: https://github.com/yt-dlp/yt-dlp/releases
- **RSS Feed**: https://github.com/yt-dlp/yt-dlp/releases.atom
- **Issues**: https://github.com/yt-dlp/yt-dlp/issues

### Risk Levels
- 🔴 CRITICAL → Update immediately
- 🟠 HIGH → Test carefully  
- 🟢 SAFE → Safe to update
- 🟡 MEDIUM → Test normally
- 🟢 LOW → Safe to update

---

**Next Steps:**
1. Choose a monitoring method (GitHub Watch recommended)
2. Add weekly check to your calendar/cron
3. Use `make check-ytdlp-releases` before updates
