# yt-dlp Update Guide

## Why yt-dlp Updates Are Critical

YouTube frequently changes their API and signature extraction methods to prevent downloading. When these changes occur, older versions of yt-dlp will break immediately, causing all YouTube downloads to fail.

**The system doesn't break when yt-dlp updates - it breaks when you DON'T update.**

## Current Version Policy

- **Minimum version**: 2025.9.26
- **Policy**: Use `>=` constraint to allow automatic updates
- **Source of truth**: `pyproject.toml` (per project standards)

## How to Update yt-dlp

### Option 1: Using Make (Recommended)
```bash
make update-ytdlp
```
This will check your current version and upgrade if needed.

### Option 2: Manual Update
```bash
pip install --upgrade yt-dlp
```

### Option 3: Scripted Update
```bash
./scripts/update_ytdlp.sh
```

## Checking Your Current Version

```bash
pip show yt-dlp | grep Version
```

Or check the latest available version:
```bash
pip index versions yt-dlp | grep LATEST
```

## Update Frequency

**Recommended**: Check for updates weekly or whenever YouTube downloads start failing.

yt-dlp typically releases updates:
- Multiple times per month during active YouTube changes
- Sometimes daily when YouTube makes breaking changes
- At minimum, monthly maintenance releases

## Automated Update Options

### Option 1: GitHub Dependabot
Add to `.github/dependabot.yml`:
```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
    allow:
      - dependency-name: "yt-dlp"
```

### Option 2: Cron Job (macOS)
Add to your crontab (`crontab -e`):
```bash
# Check for yt-dlp updates weekly on Monday at 9 AM
0 9 * * 1 cd /Users/matthewgreer/Projects/Knowledge_Chipper && source venv/bin/activate && pip install --upgrade yt-dlp
```

### Option 3: Pre-Launch Check
Add to your startup script or GUI initialization to check on launch (with user notification).

## Troubleshooting

### YouTube Downloads Failing
**First step**: Update yt-dlp
```bash
make update-ytdlp
```

### Version Conflicts
If you see version conflicts between `pyproject.toml` and `requirements.txt`:
1. Check `pyproject.toml` - this is the source of truth
2. Regenerate `requirements.txt` if needed
3. Update your environment: `pip install -e .`

### After Update, Still Failing
If downloads still fail after updating:
1. Clear yt-dlp cache: `yt-dlp --rm-cache-dir`
2. Check if YouTube is blocking your IP (try with VPN/proxy)
3. Check yt-dlp GitHub issues: https://github.com/yt-dlp/yt-dlp/issues

## Integration with CI/CD

For production deployments, consider:
1. Testing yt-dlp updates in staging before production
2. Monitoring yt-dlp GitHub releases for breaking changes
3. Having a rollback plan if an update causes issues

## Version History

- **2025.9.26**: Current minimum version (set October 2025)
  - Includes latest YouTube signature extraction fixes
  - Improved format selection
- **2023.12.0**: Previous pinned version (outdated)
  - Would not work with current YouTube API
