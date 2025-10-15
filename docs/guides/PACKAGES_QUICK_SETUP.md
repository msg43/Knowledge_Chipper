# Quick Packages.app Setup for Smooth Installation

## 1. Download and Install Packages.app (2 minutes)

```bash
# Download Packages.app
curl -L -o ~/Downloads/Packages.dmg "http://s.sudre.free.fr/Software/files/Packages.dmg"

# Mount the DMG
hdiutil attach ~/Downloads/Packages.dmg

# Copy to Applications
cp -R /Volumes/Packages/Packages.app /Applications/

# Unmount
hdiutil detach /Volumes/Packages

# Install command line tools
sudo installer -pkg "/Applications/Packages.app/Contents/Resources/Packages_Command_Line_Tools.pkg" -target /
```

## 2. Build with Packages.app

```bash
# Use the Packages.app builder
./scripts/build_packages_installer.sh
```

## 3. Benefits

With Packages.app, your installer will:
- ✅ **NO malware warnings** (properly structured installer)
- ✅ **Always prompt for password** (reliable authentication)
- ✅ **Professional appearance** (no "Done or Trash" confusion)
- ✅ **Smooth user experience** (one click, one password, done)

## Why This Solves Your Issues

1. **Malware Warning**: The native macOS tools create "unusual" installer structures that trigger Gatekeeper. Packages.app creates standard, recognized installers.

2. **Authentication**: Packages.app has explicit control over when to require admin rights, unlike the native tools which try to be "smart".

3. **Professional Polish**: Packages.app is used by many commercial Mac apps for a reason - it just works.

## Alternative: Code Signing (Permanent Solution)

If you want to eliminate ALL warnings forever:
1. Get Apple Developer account ($99/year)
2. Code sign the installer
3. Notarize with Apple
4. Zero warnings, perfect experience

But Packages.app should eliminate the worst issues immediately.
