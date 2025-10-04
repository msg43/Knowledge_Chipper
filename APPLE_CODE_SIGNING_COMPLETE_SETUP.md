# Complete Apple Code Signing & GitHub Deployment Setup

This guide will finalize your Apple code signing setup and enable automated deployment to GitHub.

## 🎯 What You'll Achieve

- ✅ **Fully automated** code signing and notarization
- ✅ **GitHub Actions** workflow for releases
- ✅ **Zero security warnings** on user installations
- ✅ **Professional deployment** process

## 📋 Prerequisites

You mentioned you have:
- ✅ Developer ID Application certificate (downloaded)
- ✅ Developer ID Installer certificate (downloaded)  
- ✅ Apple ID email
- ✅ Team ID
- ✅ App-specific password

## 🚀 Setup Process

### Step 1: Install Your Certificates

1. **Install the certificates in Keychain**:
   ```bash
   # Double-click each .cer file to install in Keychain Access
   # They should appear in "My Certificates"
   ```

2. **Verify installation**:
   ```bash
   security find-identity -v -p codesigning
   ```
   You should see both certificates listed.

### Step 2: Set Up Local Credentials (For Testing)

1. **Copy the credentials template**:
   ```bash
   cp config/apple_signing_credentials.example config/apple_signing_credentials.env
   ```

2. **Edit with your credentials**:
   ```bash
   # Edit config/apple_signing_credentials.env
   APPLE_ID=your-apple-id@email.com
   APPLE_TEAM_ID=YOUR_TEAM_ID
   APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
   ```

3. **Test local signing** (optional):
   ```bash
   source config/apple_signing_credentials.env
   ./scripts/build_signed_notarized_pkg.sh
   ```

### Step 3: Set Up GitHub Repository Secrets

**Option A: Automated Setup (Recommended)**
```bash
# Install GitHub CLI if needed
brew install gh
gh auth login

# Run the automated setup script
./scripts/setup_github_secrets.sh
```

**Option B: Manual Setup**
1. Go to your GitHub repository
2. Settings → Secrets and variables → Actions
3. Add these secrets:
   - `APPLE_ID`: Your Apple ID email
   - `APPLE_TEAM_ID`: Your Team ID
   - `APPLE_APP_PASSWORD`: Your app-specific password
   - `APPLE_CERTIFICATE_APPLICATION`: Base64 of Developer ID Application .p12
   - `APPLE_CERTIFICATE_INSTALLER`: Base64 of Developer ID Installer .p12  
   - `APPLE_CERTIFICATE_PASSWORD`: Password for .p12 files

### Step 4: Export Your Certificates as .p12 Files

1. **Open Keychain Access**
2. **Find "Developer ID Application" certificate**
3. **Right-click → Export**
4. **Choose .p12 format and set a password**
5. **Repeat for "Developer ID Installer" certificate**

### Step 5: Test the Automated Deployment

1. **Create and push a version tag**:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

2. **Monitor the GitHub Actions workflow**:
   - Go to Actions tab in your GitHub repository
   - Watch the "Build, Sign, and Release macOS Application" workflow

3. **Check the release**:
   - A new release should appear in your GitHub releases
   - With a signed, notarized .pkg file attached

## 🔧 Workflow Features

The GitHub Actions workflow will:

1. **Build** your application bundle
2. **Sign** with Developer ID Application certificate
3. **Create PKG** and sign with Developer ID Installer certificate
4. **Submit for notarization** to Apple
5. **Wait for approval** (5-15 minutes)
6. **Staple** the notarization ticket
7. **Create GitHub release** with signed PKG
8. **Upload artifacts** for download

## 🎮 Usage

### Automated Release (Recommended)
```bash
# Create and push a version tag
git tag v1.2.3
git push origin v1.2.3
# GitHub Actions will handle the rest!
```

### Manual Workflow Trigger
1. Go to Actions tab in GitHub
2. Select "Build, Sign, and Release macOS Application"  
3. Click "Run workflow"
4. Optionally specify a version

### Local Testing
```bash
# Test locally before pushing
source config/apple_signing_credentials.env
./scripts/build_signed_notarized_pkg.sh
```

## 🔒 Security Notes

- ✅ **Certificates stored as encrypted GitHub secrets**
- ✅ **Secrets automatically masked in logs**
- ✅ **Temporary keychain created and destroyed**
- ✅ **No credentials stored in repository**

## 🐛 Troubleshooting

### Certificate Issues
```bash
# Check installed certificates
security find-identity -v -p codesigning

# List all keychains
security list-keychains
```

### Notarization Issues
- Check GitHub Actions logs for notarization details
- Common issues: unsigned nested components, invalid entitlements

### GitHub Secrets Issues
- Verify all 6 secrets are set correctly
- Re-run setup script if needed

## 📁 Files Created

- `.github/workflows/build-and-sign.yml` - GitHub Actions workflow
- `scripts/setup_github_secrets.sh` - Automated secrets setup
- `config/apple_signing_credentials.example` - Local credentials template
- Updated `.gitignore` - Protects credential files

## ✅ What to Provide Next

Please provide:

1. **Confirmation** that you've installed both certificates in Keychain
2. **Your Apple ID email**
3. **Your Team ID** (10 characters)
4. **Your app-specific password**
5. **Preferred setup method** (automated script vs manual)

Once you provide these, I'll help you complete the setup and test the first automated deployment!

## 🎉 End Result

After setup, every time you push a version tag, you'll get:
- ✅ **Professionally signed macOS application**
- ✅ **Notarized by Apple** (no security warnings)
- ✅ **GitHub release** with downloadable installer
- ✅ **Completely automated** - no manual intervention needed
