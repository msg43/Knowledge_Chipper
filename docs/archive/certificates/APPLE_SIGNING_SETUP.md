# Apple Developer Signing Setup Guide

## Prerequisites

1. **Apple Developer Account** ($99/year)
   - Sign up at: https://developer.apple.com

2. **Install Certificates**
   - Go to: https://developer.apple.com/account/resources/certificates/list
   - Create/download:
     - **Developer ID Application** certificate (for signing apps)
     - **Developer ID Installer** certificate (for signing PKGs)
   - Double-click .cer files to install in Keychain

3. **App-Specific Password**
   - Go to: https://appleid.apple.com/account/manage
   - Sign in → Security → App-Specific Passwords → Generate
   - Save this password securely

4. **Find Your Team ID**
   - Go to: https://developer.apple.com/account
   - Look for Team ID (10 characters, like "ABC123DEF4")

## Building Signed & Notarized PKG

### First Time Setup
```bash
# Run the build script - it will prompt for credentials
./scripts/build_signed_notarized_pkg.sh

# Enter when prompted:
# - Apple ID email
# - Team ID
# - App-specific password
# - Choose to save in keychain (recommended)
```

### Subsequent Builds
```bash
# If you saved credentials, just run:
./scripts/build_signed_notarized_pkg.sh
```

### Environment Variables (Optional)
```bash
# Set these to avoid prompts:
export DEVELOPER_ID_APPLICATION="Developer ID Application: Your Name (TEAMID)"
export DEVELOPER_ID_INSTALLER="Developer ID Installer: Your Name (TEAMID)"
export APPLE_ID="your@email.com"
export APPLE_TEAM_ID="ABC123DEF4"
export APP_PASSWORD="xxxx-xxxx-xxxx-xxxx"

./scripts/build_signed_notarized_pkg.sh
```

## What Happens

1. **Signs the app** with Developer ID Application certificate
2. **Builds PKG** and signs with Developer ID Installer certificate
3. **Uploads to Apple** for notarization (malware scan)
4. **Waits for approval** (usually 5-15 minutes)
5. **Staples ticket** to PKG for offline verification
6. **Creates final PKG** with zero security warnings!

## Troubleshooting

### "Certificate not found"
- Make sure you've installed both Developer ID certificates
- Check in Keychain Access app → My Certificates

### "Notarization failed"
- Check the log output for specific issues
- Common problems:
  - Missing `--options runtime` flag (fixed in script)
  - Unsigned nested components
  - Invalid bundle structure

### "Unable to find identity"
- Your certificates might be in a different keychain
- Try: `security list-keychains` to see all keychains
- Try: `security find-identity -v` to list all identities

## Benefits

With proper signing and notarization:
- ✅ **No security warnings** at all
- ✅ **No right-click → Open** needed
- ✅ **Professional appearance**
- ✅ **Works with Gatekeeper** on all settings
- ✅ **Can be distributed anywhere** (not just direct download)
- ✅ **Automatic updates** work smoothly
- ✅ **PKG installer works properly** (no more "Done or Trash"!)
