# Notarization Rejects Valid Developer ID Certificates - Apple Infrastructure Issue?

### Environment
- **macOS:** 15.6.1
- **Xcode:** 26.0.1
- **Architecture:** arm64 (Apple Silicon)
- **Team ID:** W2AT7M9482
- **Certificate Status:** Valid until 2030 (verified on developer.apple.com)

### Problem
Apple's notarization service consistently rejected properly signed packages with error:
```
"The binary is not signed with a valid Developer ID certificate."
```

Despite:
- ✅ Valid certificates on developer.apple.com
- ✅ Local signing succeeds (`codesign --verify` passes)
- ✅ Proper certificate/key pairing verified
- ✅ Package structure correct

### Failed Submission IDs

**September 2025:**
```
adeeed3d-4732-49c6-a33c-724da43f9a4a
5a910f51-dc6d-4a5e-a1c7-b07f32376079
3930147e-daf6-4849-8b0a-26774fd92c3c
b7fc8e4e-e03c-44e1-a68e-98b0db38aa39
d7dee4a1-68e8-44b5-85e9-05654425e044
```

**December 29, 2025 (after fixing agreement issue):**
```
da6fa563-ba21-4f9e-b677-80769bd23340
```

### What I've Tried
1. Re-downloaded fresh certificates from Apple Developer Portal
2. Verified certificate chain locally
3. Tested with multiple different builds
4. Confirmed Team ID matches across all configurations
5. Verified no unsigned nested components
6. Waited 3 months for potential propagation delays
7. Signed updated Apple Developer Program License Agreement (December 29, 2025)
8. Verified all agreements are current and accepted
9. Re-tested with minimal test package - same error persists

### Local Verification
```bash
# Certificates present and valid
security find-identity -v -p codesigning | grep "Developer ID"
1) XXXXXXXXXX "Developer ID Application: Matthew Seymour Greer (W2AT7M9482)"
2) XXXXXXXXXX "Developer ID Installer: Matthew Seymour Greer (W2AT7M9482)"

# Signing succeeds
codesign --verify --deep --strict --verbose=2 [app] → Success
```

### Question
This appears similar to [thread #784184](https://developer.apple.com/forums/thread/784184). After 3 months and ensuring all agreements are signed, the issue persists with identical error. 

The certificates work for local signing but Apple's notarization service rejects them. Could this be:
- Backend infrastructure issue with Team ID W2AT7M9482?
- Certificate not properly registered in Apple's notarization database?
- Known issue requiring Apple Support intervention?

Has anyone else experienced valid Developer ID certificates being rejected specifically by the notarization service while working locally?

**Note:** Also contacted Apple Developer Support directly. Case ID: **102789234714** (December 29, 2025). Posting here to see if others have experienced this and found workarounds.

