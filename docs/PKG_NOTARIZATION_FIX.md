# PKG Notarization Fix

## Problem Identified

You have **two** Developer ID Installer certificates in your keychain:

1. **Certificate 1** (SHA-1: `40BD7C59C03F68AC4B37EC4E431DC57A219109A8`)
   - Issued: Sep 21, 2025
   - **Status: BROKEN** - Fails notarization with "The binary is not signed with a valid Developer ID certificate"
   - Shows warning: "unable to build chain to self-signed root"

2. **Certificate 2** (SHA-1: `773033671956B8F6DD90593740863F2E48AD2024`)
   - Issued: Oct 4, 2025
   - **Status: WORKING** - Passes notarization successfully
   - No warnings

## Root Cause

When you use `pkgbuild` or `productbuild` with just the certificate name, it defaults to the first matching certificate in your keychain, which happens to be the broken one. The broken certificate has an incomplete or invalid certificate chain that Apple's notarization service rejects.

## Solution

**Always specify the working certificate by its SHA-1 hash** when signing PKG files:

```bash
# WRONG (uses first certificate, which is broken)
pkgbuild --sign "Developer ID Installer: Matthew Seymour Greer (W2AT7M9482)" ...

# CORRECT (uses second certificate, which works)
pkgbuild --sign "773033671956B8F6DD90593740863F2E48AD2024" ...
```

## Verification

### Test Results:
- ✅ PKG signed with certificate 2 (`773033...`): **Accepted**
- ❌ PKG signed with certificate 1 (`40BD7C...`): **Invalid**
- ✅ ZIP files (using Application certificate): **Accepted** (both work)

### Commands to verify:
```bash
# List all installer certificates
security find-identity -v -p basic | grep "Developer ID Installer"

# Expected output:
#   2) 40BD7C59C03F68AC4B37EC4E431DC57A219109A8 "Developer ID Installer: ..." (BROKEN)
#   3) 773033671956B8F6DD90593740863F2E48AD2024 "Developer ID Installer: ..." (WORKING)
```

## Recommended Actions

### Option 1: Update Build Scripts (Recommended)
Update all build scripts to use the working certificate hash:
- `scripts/build_daemon_pkg.sh`
- `scripts/build_dmg.sh`
- Any other scripts using `pkgbuild` or `productbuild`

### Option 2: Remove Broken Certificate
Delete the broken certificate from your keychain:
```bash
security delete-certificate -Z 40BD7C59C03F68AC4B37EC4E431DC57A219109A8
```

**Warning:** Only do this if you're certain you don't need it for other projects.

### Option 3: Request New Certificate from Apple
If the broken certificate was supposed to work, contact Apple Developer Support to investigate why the certificate chain is broken.

## Implementation

See `scripts/fix_pkg_signing.sh` for automated fix that updates all build scripts.

## Date Discovered
January 11, 2026

## Apple Case Reference
Case ID: 102789234714
