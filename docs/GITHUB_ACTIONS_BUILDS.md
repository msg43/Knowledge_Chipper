# GitHub Actions Automated Builds

This repository includes automated GitHub Actions workflows that build macOS app bundles whenever you create a release.

## How It Works

### Automatic Builds on Release
When you create a new release on GitHub, the workflow automatically:

1. **Tests across multiple macOS versions** (Monterey, Ventura, Sonoma)
2. **Builds the complete app bundle** with your custom icon
3. **Creates professional DMG disk image** for distribution
4. **Uploads to your GitHub release** for users to download

### Files Created
For each release, you'll get:
- `Knowledge_Chipper-v1.x.x-macOS.dmg` - Professional DMG disk image
- Compatibility report showing which macOS versions were tested

## Creating a Release

### Method 1: GitHub Web Interface
1. Go to your repository on GitHub
2. Click "Releases" → "Create a new release"
3. Create a new tag (e.g., `v1.3.0`)
4. Add release notes
5. Click "Publish release"
6. **The workflow will automatically start building!**

### Method 2: Command Line
```bash
# Tag your release
git tag v1.3.0
git push origin v1.3.0

# Create release on GitHub (requires GitHub CLI)
gh release create v1.3.0 --title "Version 1.3.0" --notes "Release notes here"
```

## Monitoring Builds

### Check Build Status
1. Go to the "Actions" tab in your GitHub repository
2. Look for "Build macOS App for Release" workflows
3. Click on a workflow run to see detailed logs

### Build Process
The workflow will:
- ✅ Test imports and icon loading
- ✅ Verify icon files exist and are valid
- ✅ Test build process on multiple macOS versions
- ✅ Create the full app bundle with custom icon
- ✅ Generate professional DMG disk image
- ✅ Upload DMG to your release

## macOS Compatibility

The workflow tests your app on:
- **macOS 12** (Monterey) - Released 2021
- **macOS 13** (Ventura) - Released 2022  
- **macOS 14** (Sonoma) - Released 2023

This ensures your app works on the most recent macOS versions that users are likely to have.

## Manual Testing

You can also trigger builds manually:
1. Go to "Actions" tab → "Build macOS App for Release"
2. Click "Run workflow"
3. Choose options:
   - ☑️ "Test build without release upload" for testing
   - ☐ Leave unchecked for normal release builds

## What Users Get

When users download your release, they get:
- ✅ Professional DMG disk image (industry standard)
- ✅ Self-contained macOS app bundle with custom icon
- ✅ All dependencies included
- ✅ Simple installation: mount DMG → drag to Applications
- ✅ Tested across multiple macOS versions

## Troubleshooting

### Build Fails
1. Check the Actions logs for specific error messages
2. Common issues:
   - Missing icon files (`chipper.png`, `chipper.ico`)
   - Python dependency conflicts
   - Build script permissions

### No Files Uploaded
1. Ensure you created a proper GitHub Release (not just a tag)
2. Check that the workflow completed successfully
3. Look in the "Assets" section of your release

### App Won't Run on User's Mac
1. Check the compatibility report
2. Ensure the user's macOS version is supported
3. User may need to right-click → "Open" to bypass security warnings

## Benefits

✅ **No manual building** - Happens automatically on release  
✅ **Cross-version testing** - Works on multiple macOS versions  
✅ **Professional distribution** - Industry-standard DMG format  
✅ **Custom icon included** - No more Python rocket ship  
✅ **Optimized compression** - Efficient zlib-compressed DMG  
✅ **Version tracking** - Each release gets its own build  
✅ **Cloud resources** - Uses GitHub's servers, not your machine  

## Your Workflow

```bash
# Development (fast, latest code, rocket icon)
python3 -m knowledge_system.gui

# Local testing (custom icon, local build)
./build_macos_app.sh && open /Applications/Knowledge_Chipper.app

# Release (automatic cloud build with custom icon)
git tag v1.3.0
git push origin v1.3.0
gh release create v1.3.0 --generate-notes
# GitHub automatically builds and provides downloads! 🎉
```
