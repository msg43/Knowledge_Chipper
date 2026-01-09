# Reply to Apple Developer Support

**Case ID:** 102789234714  
**Date:** January 6, 2026

---

**Copy the text below for your reply:**

---

Hi,

Thank you for your guidance on focusing on the packaging rather than the certificate. Following your recommendation, I ran systematic tests and identified the exact root cause.

## Summary

**The Developer ID Application certificate works perfectly. The Developer ID Installer certificate has a broken chain.**

## Test Results

I created an automated diagnostic that tested 5 different combinations:

| Test | Executable | Packaging | Result |
|------|------------|-----------|--------|
| 1 | Compiled Swift binary | ditto (.zip) | ✅ **Accepted** |
| 2 | Compiled C binary | pkgbuild (.pkg) | ❌ Invalid |
| 3 | Shell script | ditto (.zip) | ✅ **Accepted** |
| 4 | Shell script | pkgbuild (.pkg) | ❌ Invalid |
| 5 | Compiled C binary | productbuild (.pkg) | ❌ Invalid |

**Pattern:** Every `.zip` passes. Every `.pkg` fails.

## The Issue

When signing with the Installer certificate, this warning appears:
```
Warning: unable to build chain to self-signed root for signer "Developer ID Installer: Matthew Seymour Greer (W2AT7M9482)"
```

This warning does NOT appear when signing `.app` bundles with the Application certificate.

The Installer certificate can sign locally, but Apple's notarization service cannot verify the chain.

## Successful Submission IDs (Proof)

These `.zip` submissions were **Accepted**:
- `7ca64ebb-963f-494e-8d62-6e6875503d82` (Swift binary)
- `9eebce4a-a9e3-4732-9117-7aa4c16b65a5` (Shell script)
- `9d893597-23ff-45fc-af6a-c7b34b3588e1` (DMG)
- `982856dc-448f-442d-9e0a-d604b5d9d651` (DMG with polish)

## Workaround

I'm now distributing as `.dmg` instead of `.pkg`, which uses the working Application certificate. This unblocks my releases.

## Question

Is there anything that can be done to fix the Developer ID Installer certificate chain? Should I:
1. Revoke and regenerate the Installer certificate?
2. Download and install intermediate certificates?
3. Something else?

The Installer certificate shows as valid on developer.apple.com (expires 2030), but the notarization service rejects packages signed with it.

Thank you for your help!

---

**Certificate Details (for reference):**
- Team ID: W2AT7M9482
- Developer ID Application: 631B103A493C26D8F1EF9324C67F5426711C45ED (working)
- Developer ID Installer: 40BD7C59C03F68AC4B37EC4E431DC57A219109A8 (broken chain)

