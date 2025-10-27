# Requirements Files Structure

This directory contains organized dependency files for different use cases.

## Files Overview

### Core Files

- **`base.txt`** - Core dependencies required to run the application
  - Use for: Understanding what the app needs
  - Install: `pip install -r requirements/base.txt`

- **`production.txt`** - Exact locked versions from working environment
  - Use for: Reproducible deployments, CI/CD
  - Install: `pip install -r requirements/production.txt`
  - **Auto-generated** with `pip freeze` - do not edit manually

### Development

- **`development.txt`** - Dev tools (testing, linting, formatting)
  - Includes: base.txt + pytest, black, mypy, etc.
  - Install: `pip install -r requirements/development.txt`

### Optional Features

- **`gui.txt`** - GUI dependencies (PyQt6, Streamlit)
  - Install: `pip install -r requirements/gui.txt`
  - Or: `pip install -e ".[gui]"`

- **`diarization.txt`** - Speaker diarization (PyAnnote, ~377MB)
  - Install: `pip install -r requirements/diarization.txt`
  - Or: `pip install -e ".[diarization]"`

- **`hce.txt`** - Hybrid Claim Extractor ML deps (~500MB)
  - Install: `pip install -r requirements/hce.txt`
  - Or: `pip install -e ".[hce]"`

- **`cuda.txt`** - CUDA/GPU monitoring
  - Install: `pip install -r requirements/cuda.txt`
  - Or: `pip install -e ".[cuda]"`

## Installation Scenarios

### New Development Setup
```bash
# Install base + dev + GUI
pip install -r requirements/development.txt
pip install -r requirements/gui.txt

# Optionally add ML features
pip install -r requirements/diarization.txt
pip install -r requirements/hce.txt
```

### Production Deployment
```bash
# Install exact locked versions
pip install -r requirements/production.txt
```

### Editable Install (Recommended for Development)
```bash
# Use pyproject.toml with optional extras
pip install -e ".[gui,diarization,hce,dev]"
```

## Updating Dependencies

### Update Locked Versions
After updating any packages, regenerate production.txt:
```bash
pip freeze > requirements/production.txt
git add requirements/production.txt
git commit -m "chore: update locked dependencies"
```

### Check for Outdated Packages
```bash
pip list --outdated
```

### Security Audit
```bash
pip install pip-audit
pip-audit
```

## Dependency Management

- **Dependabot** automatically creates PRs for updates (see `.github/dependabot.yml`)
- **Critical pins**: `yt-dlp` is pinned to exact version (see docs/YT_DLP_UPGRADE_PROCEDURE.md)
- **Version strategy**: Use `>=` for flexibility in base.txt, `==` for reproducibility in production.txt
