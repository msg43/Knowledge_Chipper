# Apple Developer Support Request - Notarization Certificate Validation Issue

**Copy the text below for your support ticket/email:**

---

**Subject:** Notarization Failing: Valid Developer ID Certificates Rejected (Team ID: W2AT7M9482)

**Priority:** High - Blocking production releases for 3+ months

---

## Issue Summary

Apple's notarization service has been consistently rejecting properly signed packages since September 2025, returning the error "The binary is not signed with a valid Developer ID certificate" despite certificates being valid on developer.apple.com and working correctly for local code signing.

## Account Information

- **Team ID:** W2AT7M9482
- **Apple ID:** Matt@rainfall.llc
- **Certificate Owner:** Matthew Seymour Greer
- **Issue Duration:** September 25, 2025 - Present (3+ months)

## Technical Details

### Certificates (Valid Until 2030)
- **Developer ID Application:** 631B103A493C26D8F1EF9324C67F5426711C45ED
  - Status: Valid on developer.apple.com
  - Expires: September 22, 2030
  - Created: September 21, 2025

- **Developer ID Installer:** 40BD7C59C03F68AC4B37EC4E431DC57A219109A8
  - Status: Valid on developer.apple.com  
  - Expires: September 22, 2030
  - Created: September 21, 2025

### Environment
- **macOS:** 15.6.1
- **Xcode:** 26.0.1
- **Architecture:** arm64 (Apple Silicon)

## Failed Notarization Submissions

### September 2025 (Original Attempts)
- `adeeed3d-4732-49c6-a33c-724da43f9a4a`
- `5a910f51-dc6d-4a5e-a1c7-b07f32376079`
- `3930147e-daf6-4849-8b0a-26774fd92c3c`
- `b7fc8e4e-e03c-44e1-a68e-98b0db38aa39`
- `d7dee4a1-68e8-44b5-85e9-05654425e044`

### December 29, 2025 (Re-test After Agreement Compliance)
- `da6fa563-ba21-4f9e-b677-80769bd23340`

**All submissions return identical error:**
```json
{
  "severity": "error",
  "message": "The binary is not signed with a valid Developer ID certificate.",
  "docUrl": "https://developer.apple.com/documentation/security/notarizing_macos_software_before_distribution/resolving_common_notarization_issues#3087721"
}
```

## What Works ✅

1. **Certificates verified on developer.apple.com** - Show as active and valid
2. **Local code signing succeeds** - `codesign --verify` passes without errors
3. **Package creation succeeds** - `productbuild` completes successfully
4. **Certificate chain verified** - Private keys properly paired with certificates
5. **Authentication successful** - Can connect to notarization service
6. **Upload successful** - Package uploads and processes (no 403/auth errors)
7. **Agreement compliance** - All agreements current and accepted as of December 29, 2025

## What Fails ❌

**Only** Apple's notarization service validation of the Developer ID certificates during the notarization process.

## Troubleshooting Steps Completed

1. ✅ Downloaded fresh certificates from Apple Developer Portal (September 2025)
2. ✅ Verified certificates are not expired
3. ✅ Confirmed certificate chain and trust settings locally
4. ✅ Tested with multiple different packages (production app + minimal test app)
5. ✅ Verified Team ID matches across all configurations
6. ✅ Confirmed no unsigned nested components
7. ✅ Waited 3+ months for potential propagation delays
8. ✅ Signed Apple Developer Program License Agreement (December 29, 2025)
9. ✅ Verified all agreements accepted and current
10. ✅ Re-tested with minimal 23KB test package - identical error

## Local Verification Commands

```bash
# Certificates present and valid
$ security find-identity -v
1) 631B103A493C26D8F1EF9324C67F5426711C45ED "Developer ID Application: Matthew Seymour Greer (W2AT7M9482)"
2) 40BD7C59C03F68AC4B37EC4E431DC57A219109A8 "Developer ID Installer: Matthew Seymour Greer (W2AT7M9482)"

# Certificate expiration check
$ security find-certificate -c "Developer ID Application: Matthew Seymour Greer (W2AT7M9482)" -p | openssl x509 -noout -dates
notBefore=Sep 21 16:45:04 2025 GMT
notAfter=Sep 22 16:45:03 2030 GMT

# Code signing verification
$ codesign --verify --deep --strict --verbose=2 [app]
[Success - no errors]

# Package signing verification  
$ productbuild --sign "Developer ID Installer: Matthew Seymour Greer (W2AT7M9482)" [options]
[Success - package created]
```

## Assessment

This appears to be an **Apple infrastructure issue** specific to Team ID W2AT7M9482. The behavior suggests:

- Certificates are valid in Apple's certificate database (developer.apple.com)
- Certificates work for local cryptographic operations
- Certificates are **not properly registered or recognized** in Apple's notarization service backend

The issue is:
- ❌ **Not** package-specific (affects all packages)
- ❌ **Not** configuration-specific (all local checks pass)
- ❌ **Not** time-based (persists for 3+ months)
- ❌ **Not** agreement-related (all agreements current)
- ✅ **Likely** a backend database/provisioning issue with Team ID W2AT7M9482

## Impact

This issue is blocking:
- Production releases of macOS desktop application
- Distribution to users (unsigned packages trigger security warnings)
- App Store distribution workflows
- CI/CD pipelines for automated builds

## Requested Action

Please investigate the following:

1. **Backend certificate registration:** Are these Developer ID certificates properly registered in the notarization service database for Team ID W2AT7M9482?

2. **Team provisioning status:** Is there a provisioning or account setup issue preventing notarization for this Team ID?

3. **Certificate propagation:** Could there be a propagation failure between the certificate issuance system and the notarization validation system?

4. **Database inconsistency:** Could there be a database inconsistency where certificates show as valid in one system but not in the notarization system?

Please escalate to Apple's notarization infrastructure team if needed. This appears to require backend investigation rather than client-side troubleshooting.

## Additional Information Available

- Full notarization logs from all submission IDs listed above
- Complete diagnostic output from local certificate verification
- Build scripts and signing configurations
- Screenshots from developer.apple.com showing certificate status

## Apple Support Case Information

**Case ID:** 102789234714  
**Submitted:** December 29/30, 2025

If there was a previous case from September 2025 contact regarding this issue, please reference and link it to this case.

## Urgency

This issue has blocked production releases for over 3 months. Any expedited assistance or escalation would be greatly appreciated.

Thank you for your help investigating this issue.

---

**End of support request text**

