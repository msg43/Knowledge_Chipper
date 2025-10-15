# Manual Certificate Import Guide

I've opened **Keychain Access** for you. The .p12 files need to be imported manually due to keychain security restrictions.

## Steps to Import Certificates:

### 1. In Keychain Access:
- Select **login** keychain (left sidebar)
- Go to **File → Import Items...**

### 2. Import First Certificate:
- Navigate to: `docs/internal/Certificates.p12`
- Click **Open**
- Enter password: `katana`
- Enter your macOS password if prompted

### 3. Import Second Certificate:
- Go to **File → Import Items...** again
- Navigate to: `docs/internal/Certificates2.p12`
- Click **Open**
- Enter password: `katana`
- Enter your macOS password if prompted

### 4. Set Key Access Permissions:
After importing, for EACH private key (look for key icons 🔑):
1. Right-click the private key
2. Select **Get Info**
3. Click **Access Control** tab
4. Select **Allow all applications to access this item**
5. Click **Save Changes**
6. Enter your macOS password

### 5. Verify Installation:
Run this command to verify:
```bash
security find-identity -v -p codesigning
```

You should see:
```
2 valid identities found
  1) ... "Developer ID Application: Matthew Seymour Greer (W2AT7M9482)"
  2) ... "Developer ID Installer: Matthew Seymour Greer (W2AT7M9482)"
```

## Alternative: Drag and Drop
You can also simply:
1. Open Finder to `docs/internal/`
2. Drag both .p12 files into Keychain Access
3. Enter password `katana` for each
4. Follow steps 4-5 above

## If Still Having Issues:
1. Make sure you're importing to the **login** keychain, not System
2. Try restarting Keychain Access
3. Make sure no other apps are using the certificates

Once the certificates show as valid identities, you can continue with:
```bash
./scripts/setup_notarization_credentials.sh
./scripts/test_notarization_simple.sh
```
