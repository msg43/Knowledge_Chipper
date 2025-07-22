# PyPI Package Build Guide

This document explains how to build and test the Knowledge System package for PyPI distribution.

## Quick Start

```bash
# Build and test the package
python build.py

# Or use the manual process
pip install build twine pytest
python -m build
python -m twine check dist/*
```

## What's Been Added

### 1. Entry Points
The package now includes both CLI and GUI entry points:

```bash
# After installation via pip
knowledge-system --help           # Main CLI
ks --help                        # Short CLI alias
knowledge-system-gui             # Launch GUI
ks-gui                          # Short GUI alias
```

### 2. Complete Dependencies
All required dependencies are now properly declared in `pyproject.toml`:
- `youtube-transcript-api` - For YouTube transcript extraction
- `psutil` - For system resource monitoring
- Complete build dependencies in `[dev]` section

### 3. Installation Tests
New test suite in `tests/test_installation.py` that verifies:
- Package builds correctly
- Entry points work
- All modules can be imported
- Dependencies are available
- Fresh virtual environment installation

### 4. Automated Build Script
`build.py` provides a comprehensive build process:
- Prerequisites checking
- Cleaning old builds
- Running tests
- Building wheel and source distributions
- Package quality checks
- Installation testing

## Build Process

### Manual Build
```bash
# Install build dependencies
pip install build twine pytest

# Clean and build
rm -rf dist/ build/ *.egg-info/
python -m build

# Check package quality
python -m twine check dist/*

# Test installation
pip install dist/*.whl
knowledge-system --version
knowledge-system-gui
```

### Automated Build
```bash
# Full build with tests
python build.py

# Skip tests (faster)
python build.py --skip-tests

# Run only tests
python build.py --test-only

# Clean only
python build.py --clean-only
```

## Testing Installation

### Local Testing
```bash
# Run installation tests
python -m pytest tests/test_installation.py -v

# Test specific aspects
python -m pytest tests/test_installation.py::test_entry_points_exist -v
```

### Fresh Environment Testing
```bash
# Create test environment
python -m venv test_env
source test_env/bin/activate

# Install from wheel
pip install dist/knowledge_system-*.whl

# Test entry points
knowledge-system --help
knowledge-system-gui
```

## Publishing to PyPI

### Test PyPI (Recommended First)
```bash
# Upload to test PyPI
python -m twine upload --repository testpypi dist/*

# Test installation from test PyPI
pip install --index-url https://test.pypi.org/simple/ knowledge-system
```

### Production PyPI
```bash
# Upload to production PyPI
python -m twine upload dist/*

# Users can then install with
pip install knowledge-system
```

## Entry Point Usage

After installation via pip, users can:

```bash
# Use the CLI
knowledge-system transcribe --input video.mp4
ks summarize transcript.md

# Launch GUI
knowledge-system-gui
ks-gui

# Use as Python module (still works)
python -m knowledge_system.cli --help
python -m knowledge_system.gui
```

## Package Structure

```
knowledge-system/
├── src/knowledge_system/
│   ├── __init__.py
│   ├── __main__.py              # Module entry point
│   ├── cli.py                   # CLI entry point
│   └── gui/
│       ├── __init__.py          # Exports main for entry point
│       └── __main__.py          # GUI entry point
├── tests/
│   └── test_installation.py    # Installation tests
├── build.py                    # Automated build script
├── pyproject.toml              # Package configuration
└── PACKAGE_BUILD.md            # This file
```

## Troubleshooting

### Common Issues

**Entry point not found:**
```bash
# Reinstall in development mode
pip install -e .
```

**Import errors:**
```bash
# Check dependencies
pip install -r requirements.txt
pip install -e ".[dev]"
```

**Build failures:**
```bash
# Clean and retry
python build.py --clean-only
python build.py --skip-tests
```

### Verifying Installation

```bash
# Check entry points are installed
pip show knowledge-system

# Test entry points work
knowledge-system --version
python -c "from knowledge_system.gui import main; print('GUI OK')"

# Check all modules import
python -c "import knowledge_system; print('Package OK')"
```

## Next Steps

1. **Test locally:** Run `python build.py` to verify everything works
2. **Test installation:** Install the wheel in a fresh environment
3. **Test PyPI:** Upload to test.pypi.org first
4. **Production release:** Upload to pypi.org
5. **Documentation:** Update main README with pip installation instructions

The package is now ready for distribution via PyPI! 🎉 