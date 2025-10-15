# Development Workflow Guide

## Quick Answers to Your Questions

### 1. What happened to `push_to_github.sh`?

✅ **It's still there!** `./scripts/push_to_github.sh` was **not affected** by the PKG migration cleanup. 

- **Purpose**: Pushes your code changes to GitHub (for development)
- **Use case**: Day-to-day development workflow
- **Different from**: Release process (which creates installable packages)

### 2. Avoiding Rebuilds of Static Components

✅ **Yes!** The build system now has **intelligent caching** and **selective rebuilding**.

## 🚀 Optimal Development Workflow

### **For App Code Changes (Most Common)**

When you update your application code (Python files, configs, etc.):

```bash
# Quick release - skips rebuilding static components
./scripts/quick_app_release.sh --bump-version --upload-release
```

This will:
- ✅ **Skip** Python framework rebuild (reuse existing)
- ✅ **Skip** AI models rebuild (reuse existing) 
- ✅ **Skip** FFmpeg rebuild (reuse existing)
- ✅ **Only rebuild** the PKG with your app changes
- ✅ **Bump version** and **upload to GitHub**

### **For First-Time Setup**

Only needed once or when dependencies change:

```bash
# Full build - creates all static components
./scripts/build_complete_pkg.sh --upload-release
```

## 📋 Complete Workflow Options

### **Daily Development Workflow**

1. **Make code changes**
2. **Push to GitHub** (development):
   ```bash
   ./scripts/push_to_github.sh
   ```

3. **Quick release** (when ready):
   ```bash
   ./scripts/quick_app_release.sh --bump-version --upload-release
   ```

### **Component Rebuild Matrix**

| Scenario | Command | Rebuilds | Time |
|----------|---------|----------|------|
| **App code changes** | `quick_app_release.sh` | PKG only | ~30 seconds |
| **Dependency updates** | `build_complete_pkg.sh --skip-models` | PKG + Python | ~5 minutes |
| **Model updates** | `build_complete_pkg.sh --skip-framework` | PKG + Models | ~15 minutes |
| **Full rebuild** | `build_complete_pkg.sh` | Everything | ~30 minutes |

### **Intelligent Caching**

The build system now automatically reuses existing components based on age:

- **Python Framework**: Reused if < 7 days old
- **AI Models**: Reused if < 30 days old  
- **FFmpeg**: Reused if < 7 days old

## 🎯 Recommended Workflows

### **Scenario 1: Daily App Development**
```bash
# 1. Code your changes
# 2. Test locally
# 3. Push code to GitHub
./scripts/push_to_github.sh

# 4. When ready for release
./scripts/quick_app_release.sh --bump-version --upload-release
```

### **Scenario 2: Dependency Updates**
```bash
# When you update Python dependencies or requirements
./scripts/build_complete_pkg.sh --skip-models --upload-release
```

### **Scenario 3: Model Updates**
```bash
# When AI models or versions change
./scripts/build_complete_pkg.sh --skip-framework --upload-release
```

### **Scenario 4: Clean Build**
```bash
# Complete rebuild (rare - only when major changes)
./scripts/build_complete_pkg.sh --upload-release
```

## 🔄 Available Scripts

### **Development Scripts**
- **`push_to_github.sh`** - Push code changes to GitHub (development)
- **`quick_app_release.sh`** - Fast release for app code changes

### **Build Scripts**
- **`build_complete_pkg.sh`** - Master build with selective options
- **`build_pkg_installer.sh`** - PKG installer only
- **`build_python_framework.sh`** - Python framework only
- **`bundle_ai_models.sh`** - AI models only
- **`bundle_ffmpeg.sh`** - FFmpeg only

### **Release Scripts**
- **`create_github_release.sh`** - Create GitHub release with existing files
- **`release_pkg_to_public.sh`** - Full version bump and release workflow

### **Utility Scripts**
- **`test_pkg_installation.sh`** - Test PKG installer
- **`monitor_pkg_workflow.sh`** - Health monitoring

## 💡 Pro Tips

### **For Frequent Releases**
```bash
# Set up an alias for quick releases
echo 'alias quick-release="./scripts/quick_app_release.sh --bump-version --upload-release"' >> ~/.zshrc

# Then just run:
quick-release
```

### **For Testing Before Release**
```bash
# Build PKG locally without releasing
./scripts/quick_app_release.sh --bump-version

# Test the PKG
./scripts/test_pkg_installation.sh

# Then release manually
./scripts/create_github_release.sh
```

### **For Version Management**
```bash
# Check current version
python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])"

# Specific version bumps
./scripts/quick_app_release.sh --bump-part minor --upload-release  # 3.2.22 → 3.3.0
./scripts/quick_app_release.sh --bump-part major --upload-release  # 3.2.22 → 4.0.0
```

## 📊 Performance Comparison

| Workflow | Download Size | Build Time | Use Case |
|----------|---------------|------------|----------|
| **Old DMG** | 603MB | 20+ minutes | All changes |
| **New PKG (full)** | 396K + components | 30 minutes first time | Dependencies changed |
| **New PKG (quick)** | 396K + reuse existing | 30 seconds | App code changes |

## 🎉 Summary

**Your questions answered:**

1. **`push_to_github.sh`**: ✅ Still available for development workflow
2. **Avoiding rebuilds**: ✅ Use `quick_app_release.sh` for app changes - it automatically skips static components!

**Optimal workflow for app updates:**
```bash
./scripts/quick_app_release.sh --bump-version --upload-release
```

This gives you **lightning-fast releases** (30 seconds vs 30 minutes) for day-to-day app development! 🚀
