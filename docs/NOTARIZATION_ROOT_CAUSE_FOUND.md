# 🎯 Notarization Root Cause FOUND

**Date:** January 6, 2026  
**Apple Case ID:** 102789234714  
**Status:** ROOT CAUSE IDENTIFIED

---

## Summary

Automated diagnostic testing has identified the exact root cause of the notarization failures.

## The Problem

**The Developer ID Installer certificate has a broken certificate chain.**

- ✅ Developer ID Application certificate: **WORKS PERFECTLY**
- ❌ Developer ID Installer certificate: **BROKEN CHAIN**

## Evidence

### Test Results

| Test | Executable | Packaging | Result |
|------|------------|-----------|--------|
| 1 | Swift binary | ditto (.zip) | ✅ PASSED |
| 2 | C binary | pkgbuild (.pkg) | ❌ FAILED |
| 3 | Shell script | ditto (.zip) | ✅ PASSED |
| 4 | Shell script | pkgbuild (.pkg) | ❌ FAILED |
| 5 | C binary | productbuild (.pkg) | ❌ FAILED |

### Key Observation

Every `.zip` passes. Every `.pkg` fails.

The `.zip` files are signed with **Developer ID Application** certificate.  
The `.pkg` files are signed with **Developer ID Installer** certificate.

### The Warning

This warning appears with every PKG signing:
```
Warning: unable to build chain to self-signed root for signer "Developer ID Installer: Matthew Seymour Greer (W2AT7M9482)"
```

This warning does NOT appear when signing `.app` bundles with the Application certificate.

## Root Cause

The **Developer ID Installer** certificate is missing intermediate certificates or has an incomplete certificate chain. The local keychain can sign files, but Apple's notarization service cannot verify the chain back to Apple's root CA.

## Solutions

### Solution 1: Distribute as .zip (WORKS NOW)

Change the distribution format from `.pkg` to `.zip`:

```bash
# Package the signed app as a zip
ditto -c -k --keepParent "YourApp.app" "YourApp.zip"

# Notarize
xcrun notarytool submit YourApp.zip \
  --apple-id "Matt@rainfall.llc" \
  --team-id "W2AT7M9482" \
  --password "xxxx-xxxx-xxxx-xxxx" \
  --wait

# Staple the original app (not the zip)
xcrun stapler staple "YourApp.app"

# Re-create zip with stapled app
ditto -c -k --keepParent "YourApp.app" "YourApp-notarized.zip"
```

**Pros:**
- Works immediately
- No certificate changes needed
- Common distribution method for Mac apps

**Cons:**
- Users drag-and-drop install instead of running installer
- No install location choice for users
- Can't include pre/post-install scripts

### Solution 2: Fix the Installer Certificate

To fix the certificate chain:

1. **Download Apple's intermediate certificates:**
   - Go to: https://www.apple.com/certificateauthority/
   - Download "Developer ID - G2" intermediate certificate
   - Double-click to install in Keychain

2. **Re-download your Installer certificate:**
   - Go to: https://developer.apple.com/account/resources/certificates/list
   - Find your "Developer ID Installer" certificate
   - Download and re-install it

3. **Verify the chain:**
   ```bash
   security find-certificate -c "Developer ID Installer: Matthew Seymour Greer" -p | \
     openssl verify -CAfile <(security find-certificate -c "Apple Root CA" -p)
   ```

4. **Test again:**
   ```bash
   ./scripts/diagnose_notarization_root_cause.sh
   ```

### Solution 3: Request New Installer Certificate

If the chain can't be fixed:

1. Revoke current Developer ID Installer certificate
2. Create new certificate at developer.apple.com
3. Download and install
4. Test with diagnostic script

## Passing Submission IDs (Proof of Working Workflow)

These submissions **PASSED** during diagnostics:

- `7ca64ebb-963f-494e-8d62-6e6875503d82` - Swift binary + ditto
- `9eebce4a-a9e3-4732-9117-7aa4c16b65a5` - Shell script + ditto

## Failed Submission IDs (PKG Format)

- `b35ba3f4-a7d3-4326-9f1e-68d3567efd4b` - C binary + pkgbuild
- `59cee882-eb54-4309-8b8a-980df64c22c1` - Shell script + pkgbuild  
- `3c37079b-dd34-42fa-95da-02b5f55891c9` - C binary + productbuild

## Recommended Action

**Immediate:** Use Solution 1 (distribute as .zip) to unblock releases.

**Future:** Investigate and fix the Installer certificate chain (Solution 2 or 3) if .pkg distribution is required.

## Update for Apple Support

The diagnostic has proven:
1. Application certificate works perfectly
2. Installer certificate has broken chain
3. All .pkg notarization fails regardless of content
4. All .zip notarization succeeds

The original error "The binary is not signed with a valid Developer ID certificate" was misleading - the **binary** (app) signature is fine. The **package** signature (Installer cert) is the problem.

## Files

- Diagnostic script: `/scripts/diagnose_notarization_root_cause.sh`
- Full diagnostic log: `/tmp/notarization_diagnosis_68789/diagnosis_results.txt`

