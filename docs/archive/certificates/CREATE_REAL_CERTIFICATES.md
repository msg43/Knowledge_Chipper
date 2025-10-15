# How to Create REAL Apple Developer ID Certificates

## Prerequisites
- Active Apple Developer account ($99/year)
- Must be done on the Mac where you'll use the certificates

## Step-by-Step Process

### 1. Create Developer ID Application Certificate

#### Using Xcode (Easiest):
1. Open **Xcode**
2. Go to **Xcode → Settings → Accounts**
3. Select your Apple ID
4. Click **Manage Certificates...**
5. Click **+** button → **Developer ID Application**
6. Certificate will be created and installed automatically

#### Using Apple Developer Portal:
1. Go to https://developer.apple.com/account/resources/certificates/add
2. Select **Developer ID Application**
3. Click **Continue**
4. Open **Keychain Access** on your Mac
5. Go to **Keychain Access → Certificate Assistant → Request a Certificate from a Certificate Authority**
6. Enter your email and name
7. Select **Saved to disk**
8. Upload the CSR file to Apple
9. Download the certificate
10. Double-click to install

### 2. Create Developer ID Installer Certificate
Repeat the same process but select **Developer ID Installer**

### 3. Export for Backup
After both certificates are installed:
1. Open **Keychain Access**
2. Find both Developer ID certificates
3. Select them with their private keys (expand with arrow)
4. Right-click → **Export 2 items...**
5. Save as .p12 with password
6. This creates a backup you can use on other Macs

### 4. Test the New Certificates
```bash
# List certificates
security find-identity -v -p codesigning

# Test signing
echo '#!/bin/bash' > /tmp/test
codesign -s "Developer ID Application: Your Name (TEAMID)" --timestamp /tmp/test -v

# Should output: /tmp/test: signed generic [test]
```

### 5. Update Your Scripts
Replace the certificate names in your scripts with your new ones:
```bash
DEVELOPER_ID_APPLICATION="Developer ID Application: Your Name (TEAMID)"
DEVELOPER_ID_INSTALLER="Developer ID Installer: Your Name (TEAMID)"
```

## Important Notes
- Certificates are tied to your Apple Developer account
- Team ID will be different (not W2AT7M9482)
- Certificate names will have your name/company
- CSR must be created on the Mac where you'll sign

## After Creating Real Certificates
1. Re-import to this Mac if needed
2. Update stored credentials
3. Test notarization - it will work!
