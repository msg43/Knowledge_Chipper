# Final Setup Instructions

I have your Apple Developer credentials and have prepared everything for automated deployment. Here are the remaining steps:

## Your Credentials (Confirmed)
- ✅ **Apple ID**: Matt@rainfall.llc
- ✅ **Team ID**: W2AT7M9482
- ✅ **App Password**: pnae-cptz-s|px-tdml

## Step 1: Install Your Apple Developer Certificates

You mentioned you have the certificates but haven't added them to the app yet. Here's how:

### Download and Install Certificates

1. **Go to Apple Developer Portal**:
   - Visit: https://developer.apple.com/account/resources/certificates/list
   - Sign in with Matt@rainfall.llc

2. **Download both certificates**:
   - **Developer ID Application** (for signing apps)
   - **Developer ID Installer** (for signing PKGs)
   - Download as `.cer` files

3. **Install in Keychain**:
   - Double-click each `.cer` file
   - They will be added to your "My Certificates" in Keychain Access

4. **Verify installation**:
   ```bash
   security find-identity -v -p codesigning
   ```
   You should see both certificates listed.

## Step 2: Set Up GitHub Repository Secrets

Since GitHub CLI installation seems to be having issues, let's set up the secrets manually:

### Manual GitHub Secrets Setup

1. **Go to your GitHub repository**: https://github.com/msg43/skipthepodcast.com (or your actual repo)

2. **Navigate to Settings**:
   - Repository → Settings → Secrets and variables → Actions

3. **Add these Repository Secrets**:

   **APPLE_ID**
   ```
   Matt@rainfall.llc
   ```

   **APPLE_TEAM_ID**
   ```
   W2AT7M9482
   ```

   **APPLE_APP_PASSWORD**
   ```
   pnae-cptz-s|px-tdml
   ```

### Export Certificates as .p12 Files

You'll need to export your certificates for GitHub Actions:

1. **Open Keychain Access**
2. **Find "Developer ID Application" certificate**
3. **Right-click → Export "Developer ID Application"**
4. **Choose file format: Personal Information Exchange (.p12)**
5. **Set a password** (remember this!)
6. **Save the file**
7. **Repeat for "Developer ID Installer" certificate**

### Convert to Base64 and Add to GitHub

1. **Convert certificates to base64**:
   ```bash
   # For Application certificate
   base64 -i /path/to/Developer_ID_Application.p12 | pbcopy
   # Paste this as APPLE_CERTIFICATE_APPLICATION secret
   
   # For Installer certificate  
   base64 -i /path/to/Developer_ID_Installer.p12 | pbcopy
   # Paste this as APPLE_CERTIFICATE_INSTALLER secret
   ```

2. **Add the remaining secrets**:

   **APPLE_CERTIFICATE_APPLICATION**
   ```
   [Base64 encoded Developer ID Application .p12 file]
   ```

   **APPLE_CERTIFICATE_INSTALLER**
   ```
   [Base64 encoded Developer ID Installer .p12 file]
   ```

   **APPLE_CERTIFICATE_PASSWORD**
   ```
   [The password you set for the .p12 files]
   ```

## Step 3: Test the Deployment

Once all secrets are set up:

1. **Create a version tag**:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

2. **Monitor GitHub Actions**:
   - Go to Actions tab in your repository
   - Watch the "Build, Sign, and Release macOS Application" workflow

3. **Check the release**:
   - If successful, you'll see a new release with a signed .pkg file

## Alternative: Local Testing First

If you want to test locally before setting up GitHub Actions:

1. **Create local credentials file**:
   ```bash
   cp config/apple_signing_credentials.example config/apple_signing_credentials.env
   ```

2. **Edit with your credentials**:
   ```bash
   # Edit config/apple_signing_credentials.env
   APPLE_ID=Matt@rainfall.llc
   APPLE_TEAM_ID=W2AT7M9482
   APP_PASSWORD=pnae-cptz-s|px-tdml
   ```

3. **Test local build**:
   ```bash
   source config/apple_signing_credentials.env
   ./scripts/build_signed_notarized_pkg.sh
   ```

## What Happens Next

Once everything is set up:
- ✅ **Every version tag push** triggers automated build and release
- ✅ **Professional code signing** with your Developer ID
- ✅ **Apple notarization** (no security warnings)
- ✅ **GitHub release** with downloadable installer
- ✅ **Zero manual intervention** needed

## Need Help?

If you run into any issues:
1. Check that both certificates show up in: `security find-identity -v -p codesigning`
2. Verify all 6 GitHub secrets are set correctly
3. Check GitHub Actions logs for detailed error messages

Let me know when you've completed Step 1 (installing certificates) and I can help with the remaining steps!
