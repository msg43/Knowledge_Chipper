# Notarization Diagnostic Plan

**Date:** December 30, 2025  
**Apple Case ID:** 102789234714  
**Apple Support Response:** Focus on "The binary is not signed" - packaging issue, not certificate issue

---

## Apple's Key Insight

> "There's nothing wrong with your Developer ID certificate but rather there's something wrong with your packaging that's preventing the notary service from verifying its code signature."

This shifts our investigation from certificates → packaging process.

---

## Diagnostic Strategy

Work from **known-good** (Xcode's native workflow) toward our **custom scripts** to isolate where the problem is introduced.

### Phase 1: Establish Baseline with Xcode ✅ / ❌

**Goal:** Confirm notarization works with Apple's recommended workflow

1. Create new macOS App project in Xcode
2. Archive with Product > Archive
3. Export with Custom > Direct Distribution > Export
4. Package with `ditto` as Apple recommends
5. Notarize with `notarytool`

**If this succeeds:** Our certificates are fine, problem is in our scripts  
**If this fails:** Something deeper is wrong with the account/certificates

### Phase 2: Test Our App with Xcode Workflow

**Goal:** Test if our actual app can be notarized using Xcode's workflow

1. Open Skip the Podcast Desktop in Xcode
2. Archive with Product > Archive
3. Export with Direct Distribution
4. Notarize with `notarytool`

**If this succeeds:** Problem is in our build/sign scripts  
**If this fails:** Problem is in our app structure or code

### Phase 3: Compare Packaging Methods

**Goal:** Identify what our scripts do differently

Compare:
- Xcode's signing flags vs our codesign command
- Xcode's archive structure vs our package structure
- Xcode's entitlements vs our entitlements
- Xcode's Info.plist handling vs ours

### Phase 4: Fix and Verify

**Goal:** Update our scripts to match working Xcode workflow

---

## Phase 1: Xcode Baseline Test

### Step 1.1: Create Test Project

```bash
# Open Xcode
open -a Xcode
```

In Xcode:
1. File → New → Project
2. macOS → App
3. Name: "NotaryTest"
4. Interface: SwiftUI
5. Language: Swift
6. Bundle ID: `com.greer.notarytest` (or similar)
7. Team: Select "Matthew Seymour Greer (W2AT7M9482)"

### Step 1.2: Archive

1. Select "Any Mac" as destination
2. Product → Archive
3. Wait for archive to complete

### Step 1.3: Export for Direct Distribution

1. In Xcode Organizer (Window → Organizer)
2. Select the archive
3. Click "Distribute App"
4. Choose: Custom → Direct Distribution
5. Choose: Export (not Upload)
6. Follow prompts, let Xcode sign with Developer ID
7. Export to a folder (e.g., `~/Desktop/NotaryTest-Export`)

### Step 1.4: Create Zip with ditto

```bash
cd ~/Desktop/NotaryTest-Export
ditto -c -k --keepParent "NotaryTest.app" "NotaryTest.zip"
```

### Step 1.5: Notarize

```bash
xcrun notarytool submit ~/Desktop/NotaryTest-Export/NotaryTest.zip \
  --apple-id "Matt@rainfall.llc" \
  --team-id "W2AT7M9482" \
  --password "wrni-zluz-hkmd-fopn" \
  --wait
```

### Step 1.6: Record Result

**Result:** _____________ (Accepted / Invalid / Error)  
**Submission ID:** _____________  
**Notes:** _____________

---

## Phase 2: Test Our App with Xcode

### If Phase 1 Succeeds

Try the same Xcode workflow with our actual project:

1. Open Knowledge_Chipper/desktop/SkipThePodcast.xcodeproj (or similar)
2. Archive
3. Export for Direct Distribution
4. ditto to create zip
5. Notarize

**Result:** _____________  
**Submission ID:** _____________  
**Notes:** _____________

---

## Phase 3: Compare Packaging Methods

### Our Current Scripts

Key files to analyze:
- `scripts/build_signed_notarized_pkg.sh`
- `scripts/build_signed_notarized_pkg_debug.sh`
- `scripts/test_notarization_simple.sh`

### What to Compare

| Aspect | Xcode Workflow | Our Scripts |
|--------|---------------|-------------|
| codesign flags | | |
| --options | | |
| --entitlements | | |
| Package format | .app in .zip | .pkg |
| Signing identity | | |
| Timestamp | | |
| Hardened runtime | | |

### Common Issues Apple Mentions

1. **Missing hardened runtime** - `--options runtime` required
2. **Missing timestamp** - `--timestamp` required  
3. **Wrong package format** - .pkg vs .zip of .app
4. **Missing entitlements** - Some apps need specific entitlements
5. **Nested code not signed** - Frameworks/helpers must be signed first
6. **Deep signing issues** - `--deep` can cause problems

---

## Our Test Script Analysis

**File:** `/scripts/test_notarization_simple.sh`

The test we ran used this approach:

```bash
# Our test created:
mkdir -p "$TEST_DIR/TestApp.app/Contents/MacOS"

# Created shell script as executable (LINE 61-64)
cat > "$TEST_APP/Contents/MacOS/test" << 'EOF'
#!/bin/bash
echo "Test app"
EOF

# Signed with codesign
codesign --force --options runtime --timestamp --sign "$DEV_ID_APP" "$TEST_APP"

# Packaged with pkgbuild (creates .pkg)
pkgbuild --root "$TEST_DIR" --sign "$DEV_ID_INST" "$TEST_PKG"
```

### 🚨 IDENTIFIED PROBLEMS

1. **Shell script as main executable** ❌
   - Our test uses a bash script (`#!/bin/bash`) as the main executable
   - This is NOT a compiled Mach-O binary
   - Code signing on scripts may not be recognized by notarization service
   
2. **Using .pkg format** ❌
   - We use `pkgbuild` → creates `.pkg` installer
   - Apple recommends `ditto` → creates `.zip` of `.app`
   - Different signing requirements for .pkg vs .app
   
3. **Not using Xcode's signing workflow** ❌
   - Xcode handles entitlements, hardened runtime, etc. properly
   - Manual codesign may miss important flags/settings

### Apple's Recommended Approach

```bash
# Apple recommends:
# 1. Build with Xcode (compiled binary)
# 2. Export from Xcode (proper signing)
# 3. Package with ditto (creates .zip)
ditto -c -k --keepParent "App.app" "App.zip"
# 4. Notarize the .zip
```

---

## Action Items

### Immediate (Today)
- [ ] Phase 1: Xcode baseline test
- [ ] Record results
- [ ] If passes, proceed to Phase 2

### If Phase 1 Passes
- [ ] Phase 2: Test our app with Xcode workflow
- [ ] Phase 3: Compare and identify differences
- [ ] Phase 4: Update our scripts

### If Phase 1 Fails
- [ ] Report back to Apple Support with new evidence
- [ ] May indicate deeper account/certificate issue

---

## Files to Review

Our current build/sign scripts:
- `/scripts/build_signed_notarized_pkg.sh`
- `/scripts/build_signed_notarized_pkg_debug.sh`
- `/scripts/test_notarization_simple.sh`

Desktop app files:
- Check if there's an Xcode project file
- Check entitlements files
- Check Info.plist

---

## Update Log

| Date | Phase | Result | Notes |
|------|-------|--------|-------|
| Dec 30, 2025 | Plan created | - | Based on Apple Support feedback |
| | | | |

---

## Apple Support Reference

**Case ID:** 102789234714

**Their recommendation:**
> 1. Create a new test project in Xcode, using the macOS > App template
> 2. Choose Product > Archive
> 3. In the Xcode organiser, click Distribute App and follow the Custom > Direct Distribution > Export path
> 4. That produces a folder containing your app binary. Use ditto to create a zip archive from that
> 5. Notarise that with notarytool
> 
> Does that have the same error?

