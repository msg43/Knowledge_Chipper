# GitHub Actions Workflows

## Automated GUI Tests

**File**: `automated-gui-tests.yml`

Runs comprehensive automated GUI testing on every push and pull request.

### What Gets Tested
- All GUI tabs and workflows
- Multiple platforms (macOS, Ubuntu)
- Multiple Python versions (3.11, 3.12)
- Complete workflow coverage
- Error handling and edge cases

### When It Runs
- On push to `main` or `develop` branches
- On pull requests to `main` or `develop`
- On manual trigger (workflow_dispatch)

### Results
- Test reports uploaded as artifacts (30-day retention)
- Coverage reports uploaded as artifacts (30-day retention)
- Combined summary uploaded (90-day retention)
- Automatic PR comments with test results

### Viewing Results
1. Go to repository on GitHub
2. Click "Actions" tab
3. Select "Automated GUI Tests" workflow
4. Click on a specific run to see results
5. Download artifacts for detailed reports

### Local Testing
To run the same tests locally before pushing:

```bash
# Quick smoke tests (5 minutes)
./test_gui_auto.sh  # Choose option 1

# Comprehensive tests (30 minutes)
./test_gui_auto.sh  # Choose option 2

# Full analysis (40 minutes)
./test_gui_auto.sh  # Choose option 3
```

### Troubleshooting CI/CD Failures

If tests fail in CI/CD:

1. **Check the test reports** (download artifacts)
2. **Run tests locally** to reproduce:
   ```bash
   export KNOWLEDGE_CHIPPER_TESTING_MODE=1
   export QT_QPA_PLATFORM=offscreen
   ./tests/run_comprehensive_automated_tests.sh
   ```
3. **Review bug reports** in artifacts
4. **Fix issues** and push again

### Configuration

The workflow is configured in `.github/workflows/automated-gui-tests.yml`.

Key settings:
- **Platforms**: macOS and Ubuntu
- **Python versions**: 3.11, 3.12
- **Timeouts**: Various per test phase
- **Artifacts**: 30-90 day retention
- **Environment**: Testing mode, offscreen rendering

For more information, see:
- `AUTOMATED_TESTING_QUICKSTART.md`
- `docs/AUTOMATED_TESTING_GUIDE.md`

