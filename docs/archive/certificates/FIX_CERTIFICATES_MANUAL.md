# Quick Fix: Trust the Certificates

You have both certificates and private keys installed, but they're not linked properly. Here's the fix:

## In Keychain Access:

### 1. Trust the Certificates
For EACH Developer ID certificate (Application and Installer):

1. **Double-click** the certificate (not the key)
2. **Expand** the "Trust" section at the top
3. Change **"When using this certificate"** to **"Always Trust"**
4. Or specifically set **"Code Signing"** to **"Always Trust"**
5. **Close** the window
6. **Enter your macOS password** when prompted

### 2. Verify It Worked
After trusting both certificates, run:
```bash
security find-identity -v -p codesigning
```

You should now see:
```
2 valid identities found
  1) ... "Developer ID Application: Matthew Seymour Greer (W2AT7M9482)"
  2) ... "Developer ID Installer: Matthew Seymour Greer (W2AT7M9482)"
```

## Why This Happens

The .p12 files were imported correctly (we can see both certificates and keys), but macOS doesn't automatically trust them for code signing. Setting them to "Always Trust" links the certificates with their private keys and makes them valid signing identities.

## If Still Not Working

1. **Restart Keychain Access** after setting trust
2. **Unlock your keychain**: `security unlock-keychain`
3. **Check key permissions**: Right-click each "Imported Private Key" → Get Info → Access Control → "Allow all applications"

Once this shows 2 valid identities, you can continue with notarization!
