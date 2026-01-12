# Release Daemon Script

**Created:** January 12, 2026  
**Location:** `~/Desktop/Release_Daemon.command`  
**Purpose:** One-click daemon release automation

## What It Does

This script automates the entire daemon release process:

1. **Bumps version** - Increments patch version (e.g., 1.1.18 → 1.1.19)
2. **Builds DMG** - Creates macOS installer package
3. **Creates GitHub release** - Tags and creates release on Skipthepodcast.com repo
4. **Uploads DMG** - Attaches DMG to GitHub release
5. **Commits Knowledge_Chipper** - Commits version bump and changes
6. **Pushes Knowledge_Chipper** - Pushes to main branch
7. **Commits GetReceipts** - Commits any sync changes
8. **Pushes GetReceipts** - Pushes to main branch

## How to Use

### Simple Method (Recommended)

1. **Double-click** `Release_Daemon.command` on your Desktop
2. Terminal window opens and runs automatically
3. Watch the progress (takes 2-3 minutes)
4. Press any key when done

### Command Line Method

```bash
~/Desktop/Release_Daemon.command
```

## Prerequisites

### Required

- ✅ **Git** - Already installed
- ✅ **Python 3.11+** - Already installed
- ✅ **PyInstaller** - Already in requirements
- ✅ **Xcode Command Line Tools** - Already installed

### Optional (Recommended)

- **GitHub CLI (`gh`)** - For automatic DMG upload
  ```bash
  brew install gh
  gh auth login
  ```
  
  Without `gh`, you'll need to manually upload the DMG to the GitHub release.

## What It Changes

### Files Modified

**In Knowledge_Chipper:**
- `daemon/__init__.py` - Version number bumped
- `dist/GetReceiptsDaemon-{version}-macos.dmg` - New DMG created
- Git tag `v{version}` created
- All uncommitted changes committed and pushed

**In GetReceipts:**
- Any uncommitted changes committed and pushed

### Git Operations

```bash
# Knowledge_Chipper
git tag -a v1.1.19 -m "Release v1.1.19"
git push origin v1.1.19
git add -A
git commit -m "Release daemon v1.1.19"
git push origin main

# GetReceipts
git add -A
git commit -m "Update for daemon v1.1.19"
git push origin main
```

## Example Output

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║                      🚀 Daemon Auto-Release Script                           ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

📋 Step 1: Bumping version...
   Current version: 1.1.18
   New version: 1.1.19
   ✓ Version bumped to 1.1.19

🔨 Step 2: Building DMG package...
   This may take 2-3 minutes...
   ✓ DMG built successfully

📦 Step 3: Creating GitHub release...
   ✓ Tag v1.1.19 pushed to GitHub
   ✓ DMG uploaded to GitHub Release

💾 Step 4: Committing changes in Knowledge_Chipper...
   ✓ Changes committed in Knowledge_Chipper

🚀 Step 5: Pushing Knowledge_Chipper to main...
   ✓ Knowledge_Chipper pushed to main

💾 Step 6: Committing changes in GetReceipts...
   ⚠ No changes to commit in GetReceipts

🚀 Step 7: Pushing GetReceipts to main...
   ⚠ No commits to push in GetReceipts

╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║                          ✨ Release Complete! ✨                              ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

  Version: v1.1.19
  DMG: dist/GetReceiptsDaemon-1.1.19-macos.dmg
  GitHub Release: https://github.com/msg43/Skipthepodcast.com/releases/tag/v1.1.19

  ✓ Version bumped
  ✓ DMG built
  ✓ GitHub release created
  ✓ DMG uploaded
  ✓ Knowledge_Chipper committed and pushed
  ✓ GetReceipts committed and pushed

Next steps:
  1. Verify release at: https://github.com/msg43/Skipthepodcast.com/releases
  2. Test daemon installation from DMG
  3. Users will auto-update to v1.1.19 within 24 hours
```

## Error Handling

The script uses `set -e` to exit immediately on any error. If something fails:

1. **Check the error message** - It will show which step failed
2. **Fix the issue** manually
3. **Run the script again** - It's idempotent (safe to re-run)

### Common Issues

**"DMG build failed"**
- Check `installer/build_dmg.sh` output
- Ensure PyInstaller is installed: `pip install pyinstaller`
- Check for Python syntax errors in daemon code

**"Git push failed"**
- Ensure you're authenticated with GitHub
- Check internet connection
- Verify no merge conflicts

**"gh command not found"**
- Install GitHub CLI: `brew install gh`
- Or manually upload DMG at: https://github.com/msg43/Skipthepodcast.com/releases

**"Permission denied"**
- Make sure script is executable: `chmod +x ~/Desktop/Release_Daemon.command`

## Safety Features

- ✅ **Version validation** - Won't overwrite existing releases
- ✅ **DMG verification** - Checks DMG exists before uploading
- ✅ **Git safety** - Only commits if there are changes
- ✅ **Exit on error** - Stops immediately if any step fails
- ✅ **Colored output** - Easy to spot errors and success

## Manual Override

If you need to do any step manually:

### Just bump version
```bash
cd /Users/matthewgreer/Projects/Knowledge_Chipper
# Edit daemon/__init__.py manually
```

### Just build DMG
```bash
cd /Users/matthewgreer/Projects/Knowledge_Chipper
bash installer/build_dmg.sh
```

### Just create release
```bash
cd /Users/matthewgreer/Projects/Knowledge_Chipper
git tag -a v1.1.19 -m "Release v1.1.19"
git push origin v1.1.19
gh release create v1.1.19 dist/GetReceiptsDaemon-1.1.19-macos.dmg \
  --repo msg43/Skipthepodcast.com \
  --title "Daemon v1.1.19" \
  --notes "Release notes here"
```

## Automation Flow

```
┌─────────────────────────────────────────┐
│ 1. Read current version from __init__.py│
└─────────────────┬───────────────────────┘
                  ▼
┌─────────────────────────────────────────┐
│ 2. Increment patch (1.1.18 → 1.1.19)   │
└─────────────────┬───────────────────────┘
                  ▼
┌─────────────────────────────────────────┐
│ 3. Update __init__.py with new version │
└─────────────────┬───────────────────────┘
                  ▼
┌─────────────────────────────────────────┐
│ 4. Run installer/build_dmg.sh           │
└─────────────────┬───────────────────────┘
                  ▼
┌─────────────────────────────────────────┐
│ 5. Create and push git tag v1.1.19     │
└─────────────────┬───────────────────────┘
                  ▼
┌─────────────────────────────────────────┐
│ 6. Upload DMG to GitHub Release         │
└─────────────────┬───────────────────────┘
                  ▼
┌─────────────────────────────────────────┐
│ 7. Commit changes in Knowledge_Chipper  │
└─────────────────┬───────────────────────┘
                  ▼
┌─────────────────────────────────────────┐
│ 8. Push Knowledge_Chipper to main       │
└─────────────────┬───────────────────────┘
                  ▼
┌─────────────────────────────────────────┐
│ 9. Commit changes in GetReceipts        │
└─────────────────┬───────────────────────┘
                  ▼
┌─────────────────────────────────────────┐
│ 10. Push GetReceipts to main            │
└─────────────────┬───────────────────────┘
                  ▼
┌─────────────────────────────────────────┐
│ ✅ Release Complete!                    │
└─────────────────────────────────────────┘
```

## Testing

Before using in production, test with a dry run:

```bash
# Make a backup of __init__.py
cp daemon/__init__.py daemon/__init__.py.backup

# Run the script
~/Desktop/Release_Daemon.command

# Verify everything looks good
# If not, restore backup and fix issues
```

## Rollback

If you need to undo a release:

```bash
# Delete the tag locally and remotely
git tag -d v1.1.19
git push origin :refs/tags/v1.1.19

# Delete the GitHub release
gh release delete v1.1.19 --repo msg43/Skipthepodcast.com --yes

# Revert the version bump commit
git revert HEAD
git push origin main
```

## Best Practices

1. **Always review CHANGELOG.md** before releasing
2. **Test the daemon** locally before releasing
3. **Check GitHub Actions** are passing
4. **Verify the DMG** installs and runs correctly
5. **Monitor auto-update** within 24 hours of release

## Troubleshooting

### Script won't run
```bash
# Make sure it's executable
chmod +x ~/Desktop/Release_Daemon.command

# Run from terminal to see errors
bash ~/Desktop/Release_Daemon.command
```

### Build fails
```bash
# Check Python environment
python3 --version  # Should be 3.11+

# Check PyInstaller
pip list | grep pyinstaller

# Check for syntax errors
cd /Users/matthewgreer/Projects/Knowledge_Chipper
python3 -m py_compile daemon/main.py
```

### Git push fails
```bash
# Check authentication
gh auth status

# Check remote
git remote -v

# Check branch
git branch
```

## Related Documentation

- `docs/DAEMON_RELEASE_PROCESS.md` - Manual release process
- `installer/build_dmg.sh` - DMG build script
- `scripts/release_daemon.sh` - Generic release script
- `CHANGELOG.md` - Version history

---

**Last Updated:** January 12, 2026  
**Script Version:** 1.0  
**Status:** ✅ Ready for production use
