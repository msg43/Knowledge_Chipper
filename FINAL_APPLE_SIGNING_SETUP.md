# 🍎 Final Apple Code Signing Setup

## ✅ Current Status: Ready to Deploy!

The Apple code signing pipeline is **99% complete**. All that's needed are the two additional GitHub secrets below.

## 🔐 Required GitHub Secrets to Add

Go to: https://github.com/msg43/Knowledge_Chipper/settings/secrets/actions

### **1. DEVELOPER_ID_INSTALLER_P12**
- **Name**: `DEVELOPER_ID_INSTALLER_P12`
- **Value**: (Base64 content - already copied to your clipboard)
- **Source**: `/Users/matthewgreer/Projects/Knowledge_Chipper/DevIDINSTALLER.p12`

### **2. INSTALLER_P12_PASSWORD** 
- **Name**: `INSTALLER_P12_PASSWORD`
- **Value**: `katana`

## 🚀 What Happens Next

Once you add these two secrets:

1. **Push a tag** (e.g., `git tag v3.2.41 && git push origin v3.2.41`)
2. **GitHub Actions will automatically**:
   - ✅ Build the app bundle
   - ✅ Sign with Developer ID Application certificate
   - ✅ Create signed .pkg installer with Developer ID Installer certificate
   - ✅ Upload to Apple for notarization
   - ✅ Staple the notarization ticket
   - ✅ Create GitHub release at: https://github.com/msg43/skipthepodcast.com/releases
   - ✅ Upload signed, notarized .pkg file

## 📋 Verification Checklist

### ✅ Already Working:
- [x] Python 3.13 environment
- [x] Dependencies installation  
- [x] Version parsing
- [x] App bundle creation
- [x] Developer ID Application certificate import
- [x] Personal Access Token for cross-repo releases
- [x] Correct repository targeting (msg43/skipthepodcast.com)

### 🔧 Final Steps:
- [ ] Add `DEVELOPER_ID_INSTALLER_P12` secret
- [ ] Add `INSTALLER_P12_PASSWORD` secret  
- [ ] Test with v3.2.41 tag

## 🎯 Test Command

After adding the secrets, test with:
```bash
git tag v3.2.41
git push origin v3.2.41
```

The release should appear at: https://github.com/msg43/skipthepodcast.com/releases

## 📁 Files Involved

- **Workflow**: `.github/workflows/build-and-sign.yml` 
- **Signing Script**: `scripts/build_signed_notarized_pkg.sh`
- **PKG Builder**: `scripts/build_pkg_installer.sh`
- **Certificates**: Local files imported to GitHub secrets

## 🔄 Deployment Triggers

- **Manual**: GitHub Actions → "Build, Sign, and Release macOS Application" → "Run workflow"
- **Automatic**: Push any tag starting with `v` (e.g., v3.2.41, v4.0.0)
- **Regular pushes**: Build and test only (no release)

---

*Setup completed on September 21, 2025*
