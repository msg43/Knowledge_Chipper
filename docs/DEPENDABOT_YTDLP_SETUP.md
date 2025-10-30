# Dependabot for yt-dlp Updates

**Simple, automated yt-dlp update notifications via Pull Requests.**

## 🎯 What This Does

Dependabot automatically:
1. Checks PyPI weekly for yt-dlp updates
2. Creates a Pull Request with version changes
3. Includes changelog from GitHub releases
4. Sends you a notification (email + GitHub)

You just review, test, and merge. That's it.

## ⚡ Setup (30 seconds)

```bash
# Push the Dependabot configuration
git add .github/dependabot.yml
git commit -m "Add Dependabot for yt-dlp monitoring"
git push
```

**Done!** Dependabot is now monitoring yt-dlp.

## 📋 What You'll Get

When yt-dlp releases a new version, you'll receive a PR like this:

### PR Title
```
Bump yt-dlp from 2025.10.14 to 2025.11.01
```

### Files Changed
- `pyproject.toml` - Updated version pin
- `requirements.txt` - Updated version pin

### PR Description
- Current → New version
- Full changelog from GitHub releases
- Link to compare view

### Labels
- `dependencies`
- `python`
- `automated-pr`

## 🔔 Notifications

You'll be notified via:
- ✅ **Email** (if enabled in GitHub settings)
- ✅ **GitHub notifications** (bell icon)
- ✅ **Mobile app** (if installed)

**Configure notifications:**
1. Go to https://github.com/settings/notifications
2. Under "Watching", enable "Email"
3. Optionally enable "Web and Mobile"

**Install mobile app:**
- iOS: https://apps.apple.com/app/github/id1477376905
- Android: https://play.google.com/store/apps/details?id=com.github.android

## 📅 Schedule

Dependabot checks **weekly on Mondays at 9 AM PST**.

This is frequent enough for yt-dlp (they typically release weekly or bi-weekly).

## ✅ When You Get a PR

1. **Review the changelog** in the PR description
2. **Test the update:**
   ```bash
   # Option 1: Checkout the PR branch
   gh pr checkout <PR-number>
   pip install -r requirements.txt
   make test-ytdlp-update
   
   # Option 2: Test manually
   pip install yt-dlp==<new-version>
   # Test a YouTube download
   ```
3. **Merge the PR:**
   ```bash
   # Via CLI
   gh pr merge <PR-number>
   
   # Or click "Merge" in GitHub UI
   ```

## 🔧 Configuration

The configuration is in `.github/dependabot.yml`:

```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
      time: "09:00"
      timezone: "America/Los_Angeles"
    
    allow:
      - dependency-name: "yt-dlp"
```

### Customize Schedule

Want daily checks instead of weekly?

```yaml
schedule:
  interval: "daily"
  time: "09:00"
```

### Add Reviewers

Want to auto-assign PRs to yourself?

```yaml
reviewers:
  - "your-github-username"
assignees:
  - "your-github-username"
```

## 🧪 Testing

### Verify Dependabot is Active

```bash
# Check for Dependabot PRs
gh pr list --label "dependencies"

# Or visit in browser
# https://github.com/{owner}/{repo}/pulls?q=is:pr+label:dependencies
```

### Check Dependabot Status

Visit: `https://github.com/{owner}/{repo}/network/updates`

Or: Settings → Security → Dependabot

## 🔍 Why This Works

- **Automated** - No manual checking required
- **Actionable** - Gives you a mergeable PR, not just a notification
- **Safe** - You review and test before merging
- **Simple** - One file, zero maintenance
- **Reliable** - GitHub infrastructure, always running

## 📊 What's Monitored

Currently monitoring:
- `yt-dlp` - Critical for YouTube functionality
- `openai` - API changes can break functionality
- `anthropic` - API changes can break functionality

**Ignored (requires manual testing):**
- `torch` - Too large, needs careful testing
- `transformers` - Needs careful testing
- `PyQt6` - GUI changes need manual testing

## 🆘 Troubleshooting

### Not receiving PRs?

**Check Dependabot is enabled:**
1. Go to Settings → Security → Dependabot
2. Ensure "Dependabot version updates" is enabled

**Check configuration:**
```bash
# Validate YAML syntax
python3 -c "import yaml; yaml.safe_load(open('.github/dependabot.yml')); print('✅ Valid')"
```

**Check you're not already up to date:**
```bash
# Check current version
grep 'yt-dlp==' pyproject.toml

# Check latest version
pip index versions yt-dlp | grep LATEST
```

### Not receiving notifications?

**Check GitHub notification settings:**
1. Go to https://github.com/settings/notifications
2. Enable "Email" under "Watching"
3. Check spam folder

### PR conflicts?

If the PR has conflicts (rare), you can:
1. Close the PR
2. Manually update the versions
3. Dependabot will create a new PR next week

## 💡 Tips

1. **Don't ignore Dependabot PRs** - yt-dlp updates are time-sensitive
2. **Test before merging** - Always run `make test-ytdlp-update`
3. **Merge promptly** - YouTube can break at any time
4. **Check spam folder** - GitHub emails sometimes go to spam
5. **Install mobile app** - Get instant notifications

## 📚 Related Documentation

- [YT-DLP Update Guide](YT-DLP_UPDATE_GUIDE.md) - How to update yt-dlp
- [YT-DLP Upgrade Procedure](YT_DLP_UPGRADE_PROCEDURE.md) - Testing procedure
- [Dependabot Documentation](https://docs.github.com/en/code-security/dependabot) - Official docs

## 🎓 Commands

```bash
# Check for Dependabot PRs
gh pr list --label "dependencies"

# Checkout and test a PR
gh pr checkout <PR-number>
make test-ytdlp-update

# Merge a PR
gh pr merge <PR-number>

# Check current yt-dlp version
grep 'yt-dlp==' pyproject.toml

# Check latest yt-dlp version
pip index versions yt-dlp | grep LATEST
```

---

**Setup Time:** 30 seconds  
**Maintenance:** Zero  
**Benefit:** Never miss a critical yt-dlp update
