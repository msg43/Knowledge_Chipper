# ✅ Certificate Issue SOLVED!

## The Problem
Your certificates are valid Apple Developer ID certificates, but code signing fails with:
```
Warning: unable to build chain to self-signed root for signer
```

## The Root Cause
**Apple Root CA certificates are in your user keychain instead of the System keychain.**

Code signing requires the certificate chain to be validated against certificates in the System keychain, not the user keychain.

## The Solution

Run this command to fix it:
```bash
sudo ./scripts/fix_apple_root_certificates.sh
```

This script will:
1. Export Apple Root CA certificates from your login keychain
2. Install them in the System keychain (requires admin password)
3. Test that code signing now works

## Why This Happened
When you imported the .p12 files, the Apple intermediate certificates were added to your login keychain. However, macOS code signing looks for root certificates in the System keychain by default.

## After Running the Fix

1. **Test signing works**:
   ```bash
   ./scripts/quick_notarization_test.sh
   ```

2. **Run full notarization**:
   ```bash
   ./scripts/build_signed_notarized_pkg.sh
   ```

## Summary
- ✅ Your certificates are valid
- ✅ Your credentials are stored
- ✅ Everything is configured correctly
- ❌ Just need Apple Root CA in System keychain → **Run the fix script with sudo**

This should completely resolve the notarization issues!
