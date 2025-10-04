# Apple Notarization Troubleshooting Guide

## Overview

This guide helps resolve Apple notarization hanging issues for the Skip the Podcast Desktop app.

## Quick Diagnostics

I've created three scripts to help diagnose and fix notarization issues:

### 1. Diagnostic Script
Run this first to check your system configuration:
```bash
./scripts/diagnose_notarization_issues.sh
```

This checks:
- Network connectivity
- Apple service status
- Developer certificates
- Keychain status
- Environment variables
- Common system issues

### 2. Debug Notarization Script
Use this enhanced version with timeouts and detailed logging:
```bash
./scripts/build_signed_notarized_pkg_debug.sh
```

Features:
- 30-minute timeout (configurable)
- Verbose logging to `logs/notarization_TIMESTAMP.log`
- Detailed error reporting
- Network diagnostics
- Certificate validation

### 3. Simple Test Script
Isolate notarization issues with a minimal test:
```bash
./scripts/test_notarization_simple.sh
```

This creates a tiny test package to verify your notarization setup works.

## Common Causes of Hanging

### 1. Network Issues
**Symptoms:** Notarization hangs indefinitely during upload
**Solutions:**
- Check proxy settings: `unset HTTP_PROXY HTTPS_PROXY ALL_PROXY`
- Verify firewall isn't blocking Apple servers
- Test with: `ping apple.com` and `curl -I https://developer.apple.com`
- Try a different network connection

### 2. Large File Size
**Symptoms:** Upload starts but never completes
**Solutions:**
- Check package size: `du -h dist/*.pkg`
- Remove unnecessary files from the app bundle
- Ensure good upload bandwidth
- Consider using a wired connection

### 3. Authentication Issues
**Symptoms:** Hangs after authentication or immediate failure
**Solutions:**
- Verify app-specific password is correct
- Check Apple Developer account for pending agreements
- Ensure Team ID is correct
- Store credentials in keychain:
  ```bash
  xcrun notarytool store-credentials "Skip-the-Podcast-Notary" \
    --apple-id "your@email.com" \
    --team-id "TEAMID" \
    --password "xxxx-xxxx-xxxx-xxxx"
  ```

### 4. Certificate Problems
**Symptoms:** Signing works but notarization fails/hangs
**Solutions:**
- Verify certificates aren't expired
- Ensure using correct certificate types (Developer ID)
- Check keychain isn't locked
- Run: `security unlock-keychain`

### 5. Apple Service Issues
**Symptoms:** Random failures or timeouts
**Solutions:**
- Check: https://developer.apple.com/system-status/
- Try again during off-peak hours
- Use manual submission if automated fails

### 6. Unsigned Nested Components
**Symptoms:** Notarization rejected or hangs during analysis
**Solutions:**
- Sign all nested frameworks/dylibs first
- Use `--deep` flag cautiously
- Check with: `find "*.app" -name "*.dylib" -o -name "*.framework"`

## Step-by-Step Troubleshooting

### Step 1: Run Diagnostics
```bash
./scripts/diagnose_notarization_issues.sh
```
Fix any critical issues (marked with ✗) before proceeding.

### Step 2: Test Simple Notarization
```bash
./scripts/test_notarization_simple.sh
```
If this works, the issue is with your specific package.
If this fails, the issue is with your setup/network.

### Step 3: Use Debug Script
```bash
./scripts/build_signed_notarized_pkg_debug.sh
```
This provides detailed logging and implements timeouts.

### Step 4: Manual Notarization
If automated tools fail, try manual submission:

```bash
# Submit
xcrun notarytool submit "your.pkg" \
  --apple-id "your@email.com" \
  --team-id "TEAMID" \
  --password "xxxx-xxxx-xxxx-xxxx"

# Note the submission ID, then check status
xcrun notarytool info SUBMISSION_ID \
  --apple-id "your@email.com" \
  --team-id "TEAMID" \
  --password "xxxx-xxxx-xxxx-xxxx"

# If accepted, staple
xcrun stapler staple "your.pkg"
```

## Environment Setup

### Required Environment Variables
```bash
export DEVELOPER_ID_APPLICATION="Developer ID Application: Your Name (TEAMID)"
export DEVELOPER_ID_INSTALLER="Developer ID Installer: Your Name (TEAMID)"
export APPLE_ID="your@email.com"
export APPLE_TEAM_ID="TEAMID"
export APP_PASSWORD="xxxx-xxxx-xxxx-xxxx"
```

### Recommended Timeout Settings
```bash
# For CI/CD environments
export NOTARIZATION_TIMEOUT=1800  # 30 minutes

# For slow connections
export NOTARIZATION_TIMEOUT=3600  # 60 minutes
```

## Monitoring and Logs

### Check Active Processes
```bash
# See if notarytool is running
ps aux | grep notarytool

# Check system load
uptime

# Monitor network traffic
nettop -p notarytool
```

### Log Locations
- Notarization logs: `logs/notarization_*.log`
- Build logs: `build_*.log`
- System logs: `Console.app` → search for "notary"

## Prevention Tips

1. **Always test locally first** before CI/CD
2. **Use stored credentials** to avoid auth issues
3. **Implement timeouts** in scripts
4. **Monitor Apple system status** before releases
5. **Keep certificates updated** and backed up
6. **Test on clean systems** periodically

## Quick Commands Reference

```bash
# Check certificates
security find-identity -v -p codesigning

# Unlock keychain
security unlock-keychain

# List stored credentials
xcrun notarytool store-credentials --list

# Check recent submissions
xcrun notarytool history --keychain-profile "Skip-the-Podcast-Notary"

# Validate a notarized package
xcrun stapler validate "package.pkg"
```

## Contact for Help

If issues persist after following this guide:
1. Collect all logs from failed attempts
2. Run the diagnostic script and save output
3. Contact Apple Developer Support with:
   - Submission IDs
   - Error messages
   - Diagnostic output

## Related Documentation

- [Apple Notarization Documentation](https://developer.apple.com/documentation/security/notarizing_macos_software_before_distribution)
- [Notarytool Documentation](https://developer.apple.com/documentation/technotes/tn3147-migrating-to-the-latest-notarization-tool)
- [Code Signing Guide](https://developer.apple.com/library/archive/documentation/Security/Conceptual/CodeSigningGuide/Introduction/Introduction.html)
