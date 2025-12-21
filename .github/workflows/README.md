# GitHub Actions Workflows

This directory contains automated workflows for the Knowledge Chipper project.

## Current Status (December 2024)

### ✅ Active Workflows

- **`smoke-test.yml`** - **NEW** - Runs automatically on every push/PR
  - Lightweight Python syntax validation
  - Basic import checks
  - YAML/config file validation
  - No heavy dependencies required
  - Fast execution (~2-3 minutes)
  - Tests Python 3.11, 3.12, and 3.13

- **`watch-deno-releases.yml`** - Runs weekly (Mondays at 9am UTC)
  - Monitors for new Deno releases
  - Creates GitHub issues when updates available
  - Important for yt-dlp YouTube support

### 🔧 Manual-Only Workflows (Temporarily Disabled)

The following workflows are temporarily disabled for automatic runs but remain available for manual triggering via the GitHub Actions UI:

- **`automated-gui-tests.yml`** - Comprehensive GUI integration tests
  - **Status**: Temporarily disabled for automatic runs
  - **Reason**: Requires full system setup with heavy ML dependencies
  - **Re-enable after**: Claims-First Architecture overhaul complete
  - **Manual trigger**: Available via workflow_dispatch
  - **What it tests**: All GUI tabs, workflows, error handling, database integration

- **`build-and-sign.yml`** - macOS app build, sign, and release
  - **Status**: Temporarily disabled for automatic tag-based builds
  - **Reason**: Being updated for new architecture
  - **Re-enable after**: Major milestone reached
  - **Manual trigger**: Available via workflow_dispatch
  - **What it does**: Builds, signs, notarizes, and releases macOS .pkg installer

- **`comprehensive-gui-tests.yml`** - Real-mode GUI tests (60-90 min)
  - **Status**: Manual-only (by design)
  - **Requires**: Ollama, whisper.cpp, full dependencies
  - **What it tests**: Real transcription and summarization workflows

## Why Temporarily Disabled?

During active development and architecture refactoring:
- Heavy integration tests create noise on every commit
- Tests require significant CI resources (macOS runners, ML models)
- Architecture changes may require test updates
- Manual triggering available when needed for validation
- New lightweight smoke tests catch syntax errors and basic issues

## Re-enabling Workflows

When ready to re-enable automatic runs:

1. Edit the workflow file (e.g., `automated-gui-tests.yml`)
2. Uncomment the `push:` and/or `pull_request:` triggers
3. Remove the "TEMPORARILY DISABLED" comment block
4. Commit and push

Example:
```yaml
# Change this:
on:
  # push:
  #   branches: [main, develop]
  workflow_dispatch:

# To this:
on:
  push:
    branches: [main, develop]
  workflow_dispatch:
```

## Running Tests Manually

### Via GitHub UI
1. Go to Actions tab in GitHub
2. Select workflow from left sidebar
3. Click "Run workflow" button
4. Select branch and click "Run workflow"

### Via GitHub CLI
```bash
# Run smoke tests (fast)
gh workflow run smoke-test.yml

# Run comprehensive GUI tests (slow)
gh workflow run automated-gui-tests.yml

# Run real-mode tests (very slow, 60-90 min)
gh workflow run comprehensive-gui-tests.yml

# Build and sign app
gh workflow run build-and-sign.yml --field version=3.3.2
```

### Local Testing

To run the same tests locally before pushing:

```bash
# Quick smoke tests (5 minutes)
./test_gui_auto.sh  # Choose option 1

# Comprehensive tests (30 minutes)
./test_gui_auto.sh  # Choose option 2

# Or run the comprehensive test script directly
export KNOWLEDGE_CHIPPER_TESTING_MODE=1
export QT_QPA_PLATFORM=offscreen
./tests/run_comprehensive_automated_tests.sh
```

## Troubleshooting CI/CD Failures

If tests fail in CI/CD:

1. **Check the test reports** (download artifacts from Actions tab)
2. **Run tests locally** to reproduce
3. **Review bug reports** in artifacts
4. **Check the workflow logs** for specific error messages
5. **Fix issues** and push again

### Common Issues

- **Import errors**: Usually missing dependencies in requirements.txt
- **Syntax errors**: Caught by smoke-test.yml
- **GUI test failures**: May require full system setup (database, models, etc.)
- **Build failures**: Check Apple certificates and secrets configuration

## Workflow Details

### smoke-test.yml
- **Trigger**: Every push/PR to main or develop
- **Duration**: ~2-3 minutes
- **Resources**: Minimal (ubuntu-latest runner)
- **Dependencies**: Only lightweight core packages
- **Purpose**: Fast feedback on syntax and basic issues

### automated-gui-tests.yml
- **Trigger**: Manual only (temporarily)
- **Duration**: ~15-30 minutes
- **Resources**: macOS runner required
- **Dependencies**: Full application stack
- **Purpose**: Comprehensive GUI integration testing

### build-and-sign.yml
- **Trigger**: Manual only (temporarily)
- **Duration**: ~20-30 minutes
- **Resources**: macOS runner required
- **Dependencies**: Apple Developer certificates
- **Purpose**: Build signed and notarized macOS installer

### comprehensive-gui-tests.yml
- **Trigger**: Manual only (by design)
- **Duration**: 60-90 minutes
- **Resources**: macOS runner with Ollama
- **Dependencies**: Full ML stack (whisper.cpp, Ollama, models)
- **Purpose**: Real-world end-to-end testing

### watch-deno-releases.yml
- **Trigger**: Weekly cron (Mondays 9am UTC)
- **Duration**: ~1 minute
- **Resources**: Minimal (ubuntu-latest runner)
- **Dependencies**: None
- **Purpose**: Automated dependency monitoring

## Configuration

The workflows are configured in `.github/workflows/*.yml` files.

Key settings:
- **Platforms**: macOS (for GUI/build), Ubuntu (for smoke tests)
- **Python versions**: 3.11, 3.12, 3.13
- **Timeouts**: Various per workflow
- **Artifacts**: 30-90 day retention
- **Environment**: Testing mode, offscreen rendering for GUI tests

## For More Information

See also:
- `AUTOMATED_TESTING_QUICKSTART.md` - Quick start guide for testing
- `docs/AUTOMATED_TESTING_GUIDE.md` - Detailed testing documentation
- `HOW_TO_TEST.md` - General testing guidelines
