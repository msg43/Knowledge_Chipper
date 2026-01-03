# Test Notarization Before Posting to Forums

**Date Created:** December 29, 2025  
**Purpose:** Test if notarization issue has resolved after 3-month wait

## Why Test First?

It's been 3 months since the original issue (September 25, 2025). This is enough time for:
- ✅ Certificate propagation delays (usually 24-72 hours)
- ✅ Apple infrastructure fixes
- ✅ Account provisioning issues
- ✅ Backend database updates

## Quick Test Procedure

### Option 1: Use Existing Test Script (Recommended)

```bash
cd /Users/matthewgreer/Projects/Knowledge_Chipper

# Run the simple test notarization script
./scripts/test_notarization_simple.sh
```

This creates a minimal test package and submits it for notarization.

### Option 2: Test with Real Package

```bash
cd /Users/matthewgreer/Projects/Knowledge_Chipper

# Run the debug build script with enhanced logging
./scripts/build_signed_notarized_pkg_debug.sh
```

### Option 3: Manual Quick Test

```bash
# 1. Verify certificates are still installed
security find-identity -v -p codesigning | grep "Developer ID"

# Expected output:
# 1) XXXXXXXXXX "Developer ID Application: Matthew Seymour Greer (W2AT7M9482)"
# 2) XXXXXXXXXX "Developer ID Installer: Matthew Seymour Greer (W2AT7M9482)"

# 2. Check certificate expiration
security find-certificate -c "Developer ID Application: Matthew Seymour Greer" -p | openssl x509 -noout -dates

# 3. Create a simple test app
mkdir -p /tmp/TestApp.app/Contents/MacOS
echo '#!/bin/bash\necho "Test"' > /tmp/TestApp.app/Contents/MacOS/TestApp
chmod +x /tmp/TestApp.app/Contents/MacOS/TestApp

# 4. Create Info.plist
cat > /tmp/TestApp.app/Contents/Info.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>TestApp</string>
    <key>CFBundleIdentifier</key>
    <string>com.test.notarization</string>
    <key>CFBundleName</key>
    <string>TestApp</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
</dict>
</plist>
EOF

# 5. Sign the app
codesign --sign "Developer ID Application: Matthew Seymour Greer (W2AT7M9482)" \
  --timestamp \
  --options runtime \
  --verbose \
  /tmp/TestApp.app

# 6. Create a PKG
productbuild --component /tmp/TestApp.app /Applications \
  --sign "Developer ID Installer: Matthew Seymour Greer (W2AT7M9482)" \
  /tmp/TestNotarization.pkg

# 7. Submit for notarization
# You'll need your credentials:
xcrun notarytool submit /tmp/TestNotarization.pkg \
  --apple-id "YOUR_APPLE_ID" \
  --team-id "W2AT7M9482" \
  --password "YOUR_APP_SPECIFIC_PASSWORD" \
  --wait

# 8. Note the submission ID for your records
```

## Interpreting Results

### ✅ SUCCESS: Notarization Works
If you see:
```
Successfully received submission info
  id: [some-uuid]
  status: Accepted
```

**Action:** Update NOTARIZATION_FINAL_STATUS.md with success note. No need to post to forums!

### ❌ FAILURE: Same Error
If you see:
```
"The binary is not signed with a valid Developer ID certificate."
```

**Action:** 
1. Save the NEW submission ID
2. Update APPLE_FORUM_POST.md with:
   - Current date
   - New submission ID
   - Note that issue persists after 3 months
3. POST to forums using APPLE_FORUM_POST.md

### ⚠️ DIFFERENT ERROR
If you see a different error:

**Action:**
1. Review the specific error message
2. Check Apple's documentation for that specific error
3. May need to revise forum post with new information

## Check Your Credentials

Before testing, verify you have:

```bash
# Check environment variables (if using scripts)
echo $APPLE_ID
echo $APPLE_TEAM_ID
echo $APP_PASSWORD  # Should be app-specific password

# Or check stored keychain profile
xcrun notarytool store-credentials --list
```

If credentials aren't set up:
```bash
# Store credentials securely
xcrun notarytool store-credentials "Skip-the-Podcast-Notary" \
  --apple-id "your@email.com" \
  --team-id "W2AT7M9482" \
  --password "xxxx-xxxx-xxxx-xxxx"
```

## Expected Timeline

- **Signing:** < 1 minute
- **PKG creation:** < 1 minute  
- **Upload:** 1-5 minutes (depending on size/connection)
- **Notarization processing:** 5-15 minutes typically
- **Total:** ~20-30 minutes for full test

## Troubleshooting Test Failures

### "No identity found"
Your certificates may have expired or been removed.
```bash
# Check certificate status on developer.apple.com
open https://developer.apple.com/account/resources/certificates/list
```

### "Authentication failed"
Check your app-specific password:
```bash
# Create new app-specific password
open https://appleid.apple.com/account/manage
```

### Upload hangs
Check network/proxy issues:
```bash
# Test connectivity
curl -I https://developer.apple.com
ping apple.com
```

## Record Your Results

Create a file: `docs/notarization_retest_results_$(date +%Y%m%d).md`

Include:
- Date and time of test
- Submission ID
- Full output (success or error)
- Next steps taken

This documentation helps if you need to contact Apple Support again.

