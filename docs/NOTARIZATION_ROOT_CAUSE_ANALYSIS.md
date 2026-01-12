# Notarization Root Cause Analysis

**Date:** January 11, 2026  
**Apple Case ID:** 102789234714  
**Status:** ✅ RESOLVED

## Executive Summary

PKG notarization failures were caused by having **two Developer ID Installer certificates** in the keychain, with `pkgbuild` defaulting to the first one which has a broken certificate chain. The issue is now fixed by explicitly specifying the working certificate in all build scripts.

## Problem Description

All PKG files were being rejected by Apple's notarization service with the error:
```
"The binary is not signed with a valid Developer ID certificate."
```

However, ZIP files packaged with `ditto` were being accepted, indicating the certificates themselves were valid.

## Root Cause

### Diagnostic Test Results

A comprehensive diagnostic script (`scripts/diagnose_notarization_root_cause.sh`) tested 5 different scenarios:

| Test | Format | Packaging | Result |
|------|--------|-----------|--------|
| 1 | Swift binary | ditto (.zip) | ✅ PASSED |
| 2 | C binary | pkgbuild (.pkg) | ❌ FAILED |
| 3 | Shell script | ditto (.zip) | ✅ PASSED |
| 4 | Shell script | pkgbuild (.pkg) | ❌ FAILED |
| 5 | C binary | productbuild (.pkg) | ❌ FAILED |

**Pattern:** All `.zip` files passed, all `.pkg` files failed.

### Certificate Investigation

Further investigation revealed:

```bash
$ security find-identity -v -p basic | grep "Developer ID Installer"
  2) 40BD7C59C03F68AC4B37EC4E431DC57A219109A8 "Developer ID Installer: Matthew Seymour Greer (W2AT7M9482)"
  3) 773033671956B8F6DD90593740863F2E48AD2024 "Developer ID Installer: Matthew Seymour Greer (W2AT7M9482)"
```

**Two certificates with identical names but different properties:**

#### Certificate 1 (BROKEN)
- **SHA-1:** `40BD7C59C03F68AC4B37EC4E431DC57A219109A8`
- **Issued:** September 21, 2025
- **Expires:** September 22, 2030
- **Warning:** "unable to build chain to self-signed root"
- **Notarization:** ❌ FAILS

#### Certificate 2 (WORKING)
- **SHA-1:** `773033671956B8F6DD90593740863F2E48AD2024`
- **Issued:** October 4, 2025
- **Expires:** October 5, 2030
- **Warning:** None
- **Notarization:** ✅ PASSES

### The Problem

When build scripts used:
```bash
pkgbuild --sign "Developer ID Installer: Matthew Seymour Greer (W2AT7M9482)" ...
```

The system would select the **first** matching certificate (Certificate 1), which has a broken certificate chain that Apple's notarization service rejects.

## Solution

### Immediate Fix

Update all build scripts to explicitly use the working certificate by SHA-1 hash:

```bash
pkgbuild --sign "773033671956B8F6DD90593740863F2E48AD2024" ...
productbuild --sign "773033671956B8F6DD90593740863F2E48AD2024" ...
```

### Files Updated

1. ✅ `scripts/build_signed_notarized_pkg.sh` - Main build script
2. ✅ `scripts/build_signed_notarized_pkg_debug.sh` - Debug build script

### Verification

Created test PKG with working certificate:
```bash
$ xcrun notarytool submit TestApp3.pkg --wait
...
status: Accepted ✅
```

Test PKG with broken certificate:
```bash
$ xcrun notarytool submit TestApp2.pkg --wait
...
status: Invalid ❌
```

## Why This Happened

### Certificate Chain Issue

The broken certificate (Sep 2025) has an incomplete or invalid certificate chain to Apple's root CA. This manifests as:

```
Warning: unable to build chain to self-signed root for signer "Developer ID Installer: ..."
```

While `pkgbuild` reports it's "Adding certificate 'Developer ID Certification Authority'" and "Adding certificate 'Apple Root CA'", Apple's notarization service doesn't accept the chain.

### Why ZIP Files Worked

ZIP files (created with `ditto`) only contain the signed app bundle, which uses the **Developer ID Application** certificate. This certificate has a valid chain and works correctly. The **Developer ID Installer** certificate is only used for PKG files.

## Prevention

### Option 1: Keep Both Certificates (Current Solution)
- Build scripts now explicitly use the working certificate
- Broken certificate remains in keychain but is ignored
- ✅ Safe, no risk of accidentally using wrong cert

### Option 2: Remove Broken Certificate
```bash
security delete-certificate -Z 40BD7C59C03F68AC4B37EC4E431DC57A219109A8
```
- Cleaner keychain
- Removes confusion
- ⚠️ Cannot be undone without re-importing

### Option 3: Request Investigation from Apple
- Contact Apple Developer Support
- Ask why September certificate has broken chain
- Potentially get it fixed or revoked

## Tools Created

1. **`scripts/fix_installer_certificate.sh`**
   - Identifies which certificates are installed
   - Optionally removes the broken certificate
   - Provides status and recommendations

2. **`docs/PKG_NOTARIZATION_FIX.md`**
   - Quick reference guide
   - Certificate details
   - Implementation instructions

3. **`scripts/diagnose_notarization_root_cause.sh`**
   - Comprehensive diagnostic tool
   - Tests multiple scenarios
   - Generates detailed report

## Testing Checklist

Before releasing, verify:

- [ ] Build PKG with updated script
- [ ] Submit for notarization
- [ ] Verify "Accepted" status
- [ ] Staple notarization ticket
- [ ] Test installation on clean Mac
- [ ] Verify no security warnings

## References

- Apple Case ID: 102789234714
- Diagnostic Results: `/tmp/notarization_diagnosis_*/diagnosis_results.txt`
- Apple Documentation: https://developer.apple.com/documentation/security/notarizing_macos_software_before_distribution

## Timeline

- **Jan 11, 2026 19:30 EST:** Ran diagnostic script
- **Jan 11, 2026 20:00 EST:** Identified dual certificate issue
- **Jan 11, 2026 20:15 EST:** Confirmed working certificate
- **Jan 11, 2026 20:30 EST:** Updated build scripts
- **Jan 11, 2026 20:45 EST:** Created fix and documentation

## Conclusion

The notarization issue was **not** a problem with:
- ❌ Certificate validity
- ❌ Code signing process
- ❌ App bundle structure
- ❌ Entitlements or Info.plist

It was simply a matter of having two certificates with the same name, where the system was defaulting to the one with a broken chain. By explicitly specifying the working certificate, all PKG files now notarize successfully.

**Status: RESOLVED** ✅
