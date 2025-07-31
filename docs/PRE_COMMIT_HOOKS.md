# Pre-commit Hooks Documentation

This document explains the pre-commit hooks setup for Knowledge_Chipper and how to use them effectively.

## 🎯 Overview

Pre-commit hooks are automated quality checks that run before each Git commit. They ensure code consistency, catch errors early, and maintain high code quality across the project.

## 🚀 Quick Setup

```bash
# One-time setup
./setup_precommit.sh
```

That's it! The script will install all dependencies and configure the hooks.

## 🔧 What Hooks Are Configured

### Code Formatting
- **Black**: Python code formatting (line length: 88)
- **isort**: Import sorting and organization
- **Prettier**: YAML file formatting

### Code Quality
- **flake8**: Python linting with additional plugins:
  - flake8-docstrings: Docstring style checking
  - flake8-bugbear: Additional bug and design problem detection
  - flake8-comprehensions: Better list/dict/set comprehensions
- **mypy**: Static type checking
- **pyupgrade**: Upgrade syntax for newer Python versions
- **pydocstyle**: Google-style docstring validation

### Security & Best Practices
- **bandit**: Security vulnerability scanning
- **pygrep-hooks**: Anti-pattern detection:
  - No deprecated `log.warn()` usage
  - Enforce type annotations
  - Check for blanket `# noqa` comments

### File Hygiene
- **trailing-whitespace**: Remove trailing spaces
- **end-of-file-fixer**: Ensure files end with newline
- **check-yaml/json/toml**: Validate file formats
- **check-merge-conflict**: Detect merge conflict markers
- **debug-statements**: Find forgotten debug statements
- **check-added-large-files**: Prevent large file commits (>10MB)

### Git & Project Standards
- **commitizen**: Validate conventional commit messages
- **version-consistency**: Check version numbers in pyproject.toml
- **validate-config**: Ensure YAML config files are valid

## 📋 Common Workflows

### Normal Development
```bash
# Make your changes
git add .
git commit -m "feat: add new feature"
# Hooks run automatically - commit succeeds if all pass
```

### When Hooks Fail
```bash
# If formatting hooks fail, they often auto-fix
git add .  # Stage the auto-fixes
git commit -m "feat: add new feature"  # Try again

# If other hooks fail, fix manually then:
git add .
git commit -m "feat: add new feature"
```

### Manual Hook Execution
```bash
# Run all hooks without committing
pre-commit run --all-files

# Run specific hook
pre-commit run black
pre-commit run mypy
pre-commit run flake8

# Run only on changed files
pre-commit run
```

### Emergency Bypass (Use Sparingly!)
```bash
# Skip all hooks (emergency only)
git commit --no-verify -m "hotfix: emergency fix"
```

## 🔧 Configuration Files

### Primary Configuration
- `.pre-commit-config.yaml`: Main hook configuration
- `pyproject.toml`: Tool settings (Black, isort, mypy, pytest)
- `mypy.ini`: Additional mypy configuration

### Hook-Specific Settings
- **Black**: Line length 88, Python 3.13 target
- **isort**: Black-compatible profile, line length 88
- **flake8**: Max line length 100, complexity 10, critical errors only
- **mypy**: Strict typing enabled, ignores test files
- **bandit**: Scans src/ directory only

## 🚨 Troubleshooting

### Common Issues

#### "command not found: pre-commit"
```bash
pip install -r requirements-dev.txt
pre-commit install
```

#### "mypy: error: Cannot find implementation"
```bash
# Install missing type stubs
pip install types-requests types-PyYAML types-python-dateutil
```

#### "Hook failed" but no clear error
```bash
# Run hook individually for better error messages
pre-commit run --verbose <hook-name>
```

#### Too many formatting changes
```bash
# Let auto-fixers do their work first
pre-commit run black --all-files
pre-commit run isort --all-files
git add .
git commit -m "style: apply pre-commit formatting"
```

### Performance Notes

- **First run is slow**: Hooks download dependencies
- **Subsequent runs are fast**: Everything is cached
- **Large changesets**: Consider running hooks on smaller chunks

## 🔄 Maintenance

### Updating Hooks
```bash
# Update to latest hook versions
pre-commit autoupdate

# Test updated hooks
pre-commit run --all-files
```

### Adding New Hooks
1. Edit `.pre-commit-config.yaml`
2. Run `pre-commit install` to update
3. Test with `pre-commit run --all-files`

### Disabling Problematic Hooks
```yaml
# In .pre-commit-config.yaml
repos:
  - repo: https://github.com/example/hook
    rev: v1.0.0
    hooks:
      - id: problematic-hook
        exclude: ^problematic/file\.py$  # Exclude specific files
```

## 📚 Resources

- [Pre-commit documentation](https://pre-commit.com/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Black documentation](https://black.readthedocs.io/)
- [mypy documentation](https://mypy.readthedocs.io/)
- [flake8 documentation](https://flake8.pycqa.org/)

## 🎯 Benefits

✅ **Consistent code style** across all contributors  
✅ **Early error detection** before CI/CD  
✅ **Reduced review time** (less style nitpicking)  
✅ **Better security** (vulnerability scanning)  
✅ **Enforced standards** (type hints, docstrings)  
✅ **Automatic fixes** for many issues 
