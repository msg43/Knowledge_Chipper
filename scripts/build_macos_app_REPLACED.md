# build_macos_app.sh - REPLACED BY PKG WORKFLOW

This script has been replaced by the new PKG installer workflow.

## New Workflow Scripts:

- `build_complete_pkg.sh` - Master build script for PKG installer
- `build_pkg_installer.sh` - Creates the PKG installer
- `build_python_framework.sh` - Builds Python framework
- `bundle_ai_models.sh` - Bundles AI models
- `bundle_ffmpeg.sh` - Bundles FFmpeg

## To build the application:

```bash
# Build everything
./scripts/build_complete_pkg.sh

# Build and release
./scripts/build_complete_pkg.sh --upload-release

# Build individual components
./scripts/build_python_framework.sh
./scripts/bundle_ai_models.sh
./scripts/build_pkg_installer.sh
```

## Migration Benefits:

- 95% smaller initial download (10MB vs 603MB)
- No Python conflicts or permission issues
- Hardware-optimized component selection
- Professional macOS installer experience
- Reliable component distribution via GitHub releases

The original build_macos_app.sh has been backed up to scripts_backup_*/updated/
