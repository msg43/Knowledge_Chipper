# ⚠️ Notarization Issue Identified

## Problem Found
**You have no Apple Developer ID certificates installed on this system.**

This is why notarization is hanging/failing - you cannot sign or notarize without proper certificates.

## Diagnostic Results

### ✅ Working:
- Network connectivity to Apple
- Xcode 26.0.1 installed
- macOS 15.6.1 (latest)
- System architecture: arm64

### ❌ Missing:
- Developer ID Application certificate (for app signing)
- Developer ID Installer certificate (for PKG signing)
- Stored notarization credentials

## Step-by-Step Solution

### Step 1: Verify Apple Developer Account
1. Go to https://developer.apple.com/account/
2. Sign in with your Apple ID
3. Ensure you have an active membership ($99/year)
4. Accept any pending agreements

### Step 2: Create Certificates

#### Option A: Using Xcode (Easiest)
1. Open Xcode
2. Go to **Xcode → Settings → Accounts**
3. Add/select your Apple ID
4. Click **Manage Certificates...**
5. Click the **+** button and create:
   - Developer ID Application
   - Developer ID Installer

#### Option B: Using Developer Portal
1. Go to https://developer.apple.com/account/resources/certificates/list
2. Click **+** to create new certificate
3. Select **Developer ID Application**
4. Follow the Certificate Signing Request (CSR) instructions
5. Download and double-click the .cer file
6. Repeat for **Developer ID Installer**

### Step 3: Verify Installation
Run this command to confirm certificates are installed:
```bash
security find-identity -v -p codesigning | grep "Developer ID"
```

You should see:
```
1) XXXXXXXXXX "Developer ID Application: Your Name (TEAMID)"
2) XXXXXXXXXX "Developer ID Installer: Your Name (TEAMID)"
```

### Step 4: Create App-Specific Password
1. Go to https://appleid.apple.com/account/manage
2. Sign in with your Apple ID
3. Under **Security**, find **App-Specific Passwords**
4. Click **Generate Password**
5. Name it "Skip the Podcast Notarization"
6. Save the password (format: xxxx-xxxx-xxxx-xxxx)

### Step 5: Find Your Team ID
1. Go to https://developer.apple.com/account
2. Your Team ID is shown (10 characters like "W2AT7M9482")

### Step 6: Setup Credentials
Once certificates are installed, run:
```bash
./scripts/setup_notarization_credentials.sh
```

This will:
- Verify certificates are installed
- Store your credentials securely in keychain
- Test the connection to Apple

### Step 7: Test Notarization
After setup, test with the simple script:
```bash
./scripts/test_notarization_simple.sh
```

### Step 8: Build Your App
If the test passes, build your actual app:
```bash
./scripts/build_signed_notarized_pkg_debug.sh
```

## Alternative: Transfer from Another Mac

If you already have certificates on another Mac:

### On the Mac WITH certificates:
1. Open **Keychain Access**
2. Select **My Certificates**
3. Find both Developer ID certificates
4. Select them (Cmd+Click)
5. Right-click → **Export Items...**
6. Save as .p12 file with a strong password
7. Include the private keys when prompted

### On THIS Mac:
1. Copy the .p12 file
2. Double-click to import
3. Enter the password
4. Verify with: `security find-identity -v -p codesigning`

## Common Issues

### "Unknown Developer" on Certificate Creation
- Make sure you're signed into Xcode with the same Apple ID
- Your Apple ID must be added to the developer team

### Certificate Shows as "Untrusted"
- Open Keychain Access
- Find the certificate
- Double-click and set to "Always Trust"

### Multiple Team IDs
- If you're part of multiple teams, use the one that matches your app's bundle ID

## Next Steps

1. **Install certificates** (Steps 1-3)
2. **Run setup script** (Step 6)
3. **Test with simple package** (Step 7)
4. **Build your app** (Step 8)

The notarization hanging is definitely caused by the missing certificates. Once installed, the process should work smoothly and complete in 5-15 minutes.

## Need Help?

- Apple Developer Support: https://developer.apple.com/support/
- Certificate issues: https://developer.apple.com/help/account/manage-certificates/
- Your existing setup guide: `APPLE_SIGNING_SETUP.md`
