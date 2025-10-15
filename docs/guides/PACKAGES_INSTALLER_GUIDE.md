# Using Packages.app for Skip the Podcast Desktop Installer

## Why Packages.app?

The native macOS installer (`pkgbuild`/`productbuild`) has a "smart" behavior where it may not prompt for authentication if:
- The user is in the `admin` group
- The target directory (`/Applications`) has write permissions for the admin group
- No scripts explicitly require root at runtime

This results in the "Done or Trash" dialog instead of a password prompt.

**Packages.app solves this by allowing explicit control over authentication requirements.**

## Installation

1. **Download Packages.app**
   - Go to: http://s.sudre.free.fr/Software/Packages/about.html
   - Download the latest version
   - Open the DMG and drag Packages.app to Applications

2. **Install Command Line Tools** (optional but recommended)
   - Launch Packages.app
   - Menu: Packages → Install Command Line Tools
   - This installs `packagesbuild` for automation

## Using the Build Script

Once Packages.app is installed:

```bash
# Build the installer with forced authentication
./scripts/build_packages_installer.sh
```

This script:
1. Prepares the app bundle using the existing build process
2. Creates a Packages project file with authentication required
3. Builds the PKG using `packagesbuild`
4. Creates checksums
5. Outputs to `dist/Skip_the_Podcast_Desktop-VERSION.pkg`

## Key Differences from Native Build

### Native PKG (`build_pkg_installer.sh`):
- May show "Done or Trash" for admin users
- Less control over authentication
- Unpredictable behavior

### Packages.app PKG (`build_packages_installer.sh`):
- **Always prompts for admin password**
- Consistent behavior across macOS versions
- Professional installer UI
- Better error messages

## Manual Build with Packages.app GUI

If you prefer the GUI:

1. Open Packages.app
2. Create new Distribution project
3. Settings:
   - **Project → Settings → Options**
     - ✅ Require admin password for installation
     - Authorization: Administrator
4. Add your app to Payload
5. Add scripts if needed
6. Build

## Integration with Release Workflow

To use Packages.app in your release workflow:

```bash
# Quick release with Packages.app installer
./scripts/quick_app_release.sh --use-packages --bump-version --upload-release
```

(Note: You'd need to modify quick_app_release.sh to support --use-packages flag)

## Troubleshooting

### "packagesbuild: command not found"
- Install command line tools from Packages → Install Command Line Tools
- Or the script will try to install them automatically with sudo

### Build fails
- Check that app bundle exists in build_pkg/package_root
- Ensure Packages.app is installed in /Applications
- Check console output for specific errors

## Benefits

1. **Reliable Authentication**: Always prompts when configured
2. **Professional UI**: Matches Apple's installer style  
3. **Better Control**: Fine-grained permission settings
4. **Consistent**: Same behavior for all users
5. **Trusted**: Used by many professional Mac developers

## Summary

For production releases where you need guaranteed authentication prompts, use Packages.app. The small extra step of installing Packages.app is worth it for the reliability and professional result.
