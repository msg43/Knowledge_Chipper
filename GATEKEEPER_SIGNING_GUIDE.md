# macOS Gatekeeper and Code Signing Guide

## The Problem

Users see "cannot be opened" or "move to trash?" dialogs when trying to run Skip the Podcast Desktop because:
- The app is not signed with a valid Apple Developer certificate
- The app is not notarized by Apple
- macOS Gatekeeper blocks unsigned apps downloaded from the internet

## Current State

The app uses **ad-hoc signing** (`codesign --sign -`), which:
- ✅ Creates a signature
- ❌ Doesn't satisfy Gatekeeper
- ❌ Still shows security warnings

## Solutions

### Option 1: Apple Developer Certificate (Recommended)

**Cost**: $99/year for Apple Developer Program

**Benefits**:
- No security warnings for users
- Professional appearance
- Can distribute through Mac App Store
- Automatic updates work smoothly

**Implementation**:
```bash
# 1. Get Apple Developer account
# 2. Create Developer ID Application certificate
# 3. Update build script:
CERT_NAME="Developer ID Application: Your Name (TEAMID)"
codesign --force --deep --sign "$CERT_NAME" "$APP_PATH"

# 4. Notarize the app:
xcrun notarytool submit "$DMG_PATH" --apple-id your@email.com --team-id TEAMID --wait

# 5. Staple the notarization:
xcrun stapler staple "$DMG_PATH"
```

### Option 2: Homebrew Distribution

**Cost**: Free

**Benefits**:
- Bypasses some Gatekeeper checks
- Easy installation for technical users
- Automatic updates via `brew upgrade`

**Implementation**:
```ruby
# homebrew-cask formula
cask "skip-the-podcast-desktop" do
  version "3.2.14"
  sha256 "actual_sha256_here"
  
  url "https://github.com/skipthepodcast/releases/download/v#{version}/Skip_the_Podcast_Desktop-#{version}.dmg"
  name "Skip the Podcast Desktop"
  desc "Knowledge management system for media content"
  homepage "https://github.com/skipthepodcast/desktop"
  
  app "Skip the Podcast Desktop.app"
end
```

### Option 3: Improved First-Run Experience (Current Workaround)

Update the DMG to include clear instructions and automation:

```bash
#!/bin/bash
# first_run_setup.sh - Add to DMG root

echo "🚀 Skip the Podcast Desktop - First Run Setup"
echo "==========================================="
echo ""
echo "This setup will prepare the app to run on your Mac."
echo ""

# 1. Copy to Applications
if [ ! -d "/Applications/Skip the Podcast Desktop.app" ]; then
    echo "📦 Installing app to Applications..."
    cp -R "Skip the Podcast Desktop.app" /Applications/
fi

# 2. Remove quarantine
echo "🛡️ Configuring macOS security..."
xattr -dr com.apple.quarantine "/Applications/Skip the Podcast Desktop.app" 2>/dev/null

# 3. Open the app using the bypass method
echo "🎉 Setup complete! Launching app..."
open -a "Skip the Podcast Desktop" --args --first-run

echo ""
echo "✅ If the app doesn't open:"
echo "   1. Right-click the app in Applications"
echo "   2. Choose 'Open'"
echo "   3. Click 'Open' in the dialog"
```

### Option 4: Web-Based Installer

Create a web installer that:
1. Downloads the app without quarantine
2. Installs directly to /Applications
3. Configures permissions correctly

```python
# web_installer.py
import urllib.request
import zipfile
import subprocess
import os

def install_app():
    # Download without quarantine
    urllib.request.urlretrieve(
        "https://example.com/app.zip",
        "app.zip",
        reporthook=download_progress
    )
    
    # Extract to Applications
    with zipfile.ZipFile("app.zip", 'r') as zip_ref:
        zip_ref.extractall("/Applications/")
    
    # No quarantine attribute when downloaded via Python!
    
    # Launch app
    subprocess.run(["open", "-a", "Skip the Podcast Desktop"])
```

## Current Workarounds for Users

### Method 1: Right-Click to Open
1. Right-click the app in Applications
2. Select "Open" from the menu
3. Click "Open" in the security dialog
4. App will remember this choice

### Method 2: System Settings
1. Try to open the app normally
2. Go to System Settings → Privacy & Security
3. Find "Skip the Podcast Desktop was blocked"
4. Click "Open Anyway"

### Method 3: Terminal Command
```bash
# Remove quarantine attribute
sudo xattr -dr com.apple.quarantine "/Applications/Skip the Podcast Desktop.app"
```

## Comparison of Approaches

| Approach | Cost | User Experience | Maintenance | Professional |
|----------|------|----------------|-------------|--------------|
| Apple Certificate | $99/year | Seamless | Low | ⭐⭐⭐⭐⭐ |
| Homebrew | Free | Technical users only | Medium | ⭐⭐⭐⭐ |
| First-run script | Free | One extra step | Low | ⭐⭐⭐ |
| Current (manual) | Free | Confusing | High support | ⭐⭐ |

## Recommendation

**Short term**: Implement the improved first-run setup script in the DMG

**Long term**: Get an Apple Developer certificate for the best user experience

## Technical Notes

### Why Ad-hoc Signing Doesn't Work

Ad-hoc signing (`--sign -`) creates a signature but:
- Has no identity associated with it
- Is not trusted by Gatekeeper
- Only prevents "damaged app" errors, not "unidentified developer" errors

### Quarantine Attribute

The `com.apple.quarantine` extended attribute:
- Added to all downloaded files
- Triggers Gatekeeper check on first run
- Can be removed with `xattr -d`
- Not added when files are created locally

### Notarization Requirements

Since macOS 10.15 (Catalina):
- All apps must be notarized
- Even with valid certificate
- Automated via `notarytool`
- Takes 5-10 minutes typically
