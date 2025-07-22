# GitHub Setup and Maintenance Guide for Knowledge System

This comprehensive guide covers everything needed to properly upload, configure, and maintain the Knowledge System app on GitHub.

## 🚀 **Initial GitHub Repository Setup**

### **1. Create Repository on GitHub**

**Option A: GitHub Web Interface**
1. Go to https://github.com and log in
2. Click "New repository" (green button)
3. Repository settings:
   ```
   Repository name: knowledge-system
   Description: A comprehensive knowledge management system for macOS that transforms videos, audio files, and documents into organized, searchable knowledge
   Visibility: Public (or Private if preferred)
   ☑️ Add a README file (uncheck - you already have one)
   ☐ Add .gitignore (you'll create a custom one)
   ☐ Choose a license (you already have MIT)
   ```

**Option B: GitHub CLI** (if you have `gh` installed)
```bash
gh repo create knowledge-system --public --description "Knowledge management system for macOS"
```

### **2. Initialize and Connect Git Repository**

```bash
# Navigate to your project directory
cd /Users/matthewgreer/Projects/App5

# Initialize git (if not already done)
git init

# Set up your identity (if not configured globally)
git config user.name "Your Name"
git config user.email "your.email@example.com"

# Add all files
git add .

# Create initial commit
git commit -m "Initial commit: Knowledge System v1.0

- Complete GUI application with PyQt6
- Audio transcription with Whisper.cpp
- YouTube extraction with proxy support
- Document summarization with AI
- Maps of Content generation
- Quality detection and automatic retry system
- Comprehensive test suite"

# Add GitHub remote (replace with your actual repo URL)
git remote add origin https://github.com/yourusername/knowledge-system.git

# Push to GitHub
git push -u origin main
```

## 📋 **Essential GitHub Files**

### **3. Create CONTRIBUTING.md**

```bash
cat > CONTRIBUTING.md << 'EOF'
# Contributing to Knowledge System

Thank you for your interest in contributing to the Knowledge System! This document provides guidelines for contributing to the project.

## 🚀 Quick Start for Contributors

### Development Setup

1. **Fork and clone the repository:**
```bash
git clone https://github.com/yourusername/knowledge-system.git
cd knowledge-system
```

2. **Set up development environment:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
pip install -e .
```

3. **Run tests to verify setup:**
```bash
pytest
```

## 🔧 Development Workflow

### Branch Strategy

- **`main`**: Production-ready code
- **`develop`**: Integration branch for new features
- **`feature/feature-name`**: Individual feature development
- **`bugfix/issue-description`**: Bug fixes
- **`hotfix/critical-fix`**: Emergency production fixes

### Making Changes

1. **Create a feature branch:**
```bash
git checkout -b feature/your-feature-name
```

2. **Make your changes:**
   - Follow the coding standards below
   - Add tests for new functionality
   - Update documentation as needed

3. **Test your changes:**
```bash
# Run full test suite
pytest

# Run specific tests
pytest tests/unit/test_your_feature.py

# Run with coverage
pytest --cov=knowledge_system
```

4. **Commit your changes:**
```bash
git add .
git commit -m "feat: add new feature description

- Detailed description of changes
- Any breaking changes noted
- Closes #issue-number if applicable"
```

### Commit Message Format

We use conventional commits:

- `feat:` New features
- `fix:` Bug fixes
- `docs:` Documentation changes
- `style:` Code style changes (formatting, etc.)
- `refactor:` Code refactoring
- `test:` Adding or updating tests
- `chore:` Maintenance tasks

## 📝 Coding Standards

### Python Code Style

- **PEP 8**: Follow Python style guidelines
- **Type hints**: Use type annotations for function signatures
- **Docstrings**: Use Google-style docstrings
- **Line length**: 100 characters maximum

### Code Quality Tools

```bash
# Format code
black src/

# Sort imports
isort src/

# Type checking
mypy src/

# Linting
flake8 src/
```

### Example Code Style

```python
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

def process_audio_file(
    file_path: str,
    model: str = "base",
    device: Optional[str] = None,
    enable_retry: bool = True
) -> ProcessorResult:
    """Process an audio file with transcription.
    
    Args:
        file_path: Path to the audio file
        model: Whisper model to use
        device: Device for processing (cpu/cuda/mps)
        enable_retry: Whether to enable quality retry
        
    Returns:
        ProcessorResult containing transcription and metadata
        
    Raises:
        ProcessorError: If processing fails
    """
    logger.info(f"Processing audio file: {file_path}")
    # Implementation here...
```

## 🧪 Testing Guidelines

### Test Structure

```
tests/
├── unit/           # Unit tests for individual components
├── integration/    # Integration tests for workflows
├── gui/           # GUI-specific tests
└── test_data/     # Test fixtures and sample data
```

### Writing Tests

- **Unit tests**: Test individual functions/classes
- **Integration tests**: Test complete workflows
- **GUI tests**: Test user interface components
- **Use fixtures**: For reusable test data

### Example Test

```python
import pytest
from knowledge_system.processors import AudioProcessor

def test_audio_processor_initialization():
    """Test AudioProcessor initializes correctly."""
    processor = AudioProcessor(model="base")
    assert processor.model == "base"
    assert processor.enable_quality_retry is True

@pytest.mark.integration
def test_audio_processing_workflow(sample_audio_file):
    """Test complete audio processing workflow."""
    processor = AudioProcessor()
    result = processor.process(sample_audio_file)
    assert result.success is True
    assert result.content is not None
```

## 📚 Documentation

### README Updates

- Update feature descriptions for new capabilities
- Add usage examples for new functionality
- Update installation instructions if dependencies change

### Code Documentation

- Document all public APIs
- Include usage examples in docstrings
- Update type hints for new parameters

### API Changes

- Document breaking changes in CHANGELOG.md
- Update version numbers following semantic versioning

## 🐛 Bug Reports

### Issue Template

When reporting bugs, include:

1. **Environment:**
   - OS version (macOS version)
   - Python version
   - Package versions (`pip list`)

2. **Steps to reproduce:**
   - Exact steps taken
   - Expected behavior
   - Actual behavior

3. **Logs and output:**
   - Error messages
   - Log files from `logs/` directory
   - Screenshots if GUI-related

4. **Sample files:**
   - Minimal example that reproduces the issue
   - Sanitized (remove personal content)

## 🚀 Feature Requests

### Enhancement Template

1. **Problem description:**
   - What problem does this solve?
   - Who would benefit from this feature?

2. **Proposed solution:**
   - Detailed description of the feature
   - How it would work from user perspective

3. **Alternatives considered:**
   - Other approaches you've considered
   - Why this approach is preferred

## 🔒 Security Considerations

### Sensitive Data

- Never commit API keys or credentials
- Use environment variables or config files (ignored by git)
- Sanitize any sample data of personal information

### Dependencies

- Keep dependencies up to date
- Use `requirements-dev.txt` for development dependencies
- Document any security-related dependency choices

## 📋 Pull Request Process

1. **Pre-submission checklist:**
   - [ ] Tests pass locally
   - [ ] Code follows style guidelines
   - [ ] Documentation updated
   - [ ] No sensitive data committed

2. **Pull request description:**
   - Clear description of changes
   - Reference any related issues
   - Note any breaking changes

3. **Review process:**
   - At least one maintainer review required
   - Address feedback promptly
   - Keep PR scope focused

## 🏷️ Release Process

### Version Numbering

We follow semantic versioning (MAJOR.MINOR.PATCH):

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)  
- **PATCH**: Bug fixes (backward compatible)

### Release Checklist

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Create release branch
4. Final testing
5. Create GitHub release with notes

## 💬 Community

### Communication

- **Issues**: For bug reports and feature requests
- **Discussions**: For questions and general discussion
- **Email**: For security-related concerns

### Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help maintain a welcoming environment
- Follow GitHub's community guidelines

## 🙏 Recognition

Contributors will be recognized in:
- `CONTRIBUTORS.md` file
- Release notes for significant contributions
- Special recognition for major features

Thank you for contributing to Knowledge System! 🚀
EOF
```

### **4. Create CHANGELOG.md**

```bash
cat > CHANGELOG.md << 'EOF'
# Changelog

All notable changes to the Knowledge System will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Intelligent quality detection with automatic retry
- Duration-based transcription validation
- Configurable retry attempts (0-3)
- Performance vs quality mode selection
- Real-time model download progress
- WebShare 402 payment error detection
- HuggingFace token input for speaker diarization
- Enhanced hardware recommendations layout

### Changed
- Removed "style" option from summarization (prompt-controlled)
- Improved Audio Transcription tab layout
- Better hardware recommendation text formatting
- Enhanced progress tracking for all operations

### Fixed
- Audio transcription silent failures
- YouTube extraction error handling
- GUI layout issues in transcription tab
- Process control and cancellation reliability

## [1.0.0] - 2024-01-XX

### Added
- Initial release of Knowledge System
- PyQt6 desktop GUI application
- Audio transcription with Whisper.cpp
- YouTube video/playlist extraction
- Document summarization with AI
- Maps of Content (MOC) generation
- Speaker diarization support
- WebShare proxy integration
- Comprehensive test suite
- Cross-platform support (macOS optimized)
- Hardware-aware performance optimization
- Process control with pause/resume/cancel
- Intelligent text chunking for large documents
- File watcher for automated processing
- CLI interface for scripting
- Multiple AI provider support (OpenAI, Anthropic)
- Batch processing capabilities
- Progress tracking and reporting
- Error handling and recovery
- Extensive documentation

### Security
- API key protection
- Secure credential storage
- Input validation and sanitization
EOF
```

### **5. Create GitHub Issue Templates**

```bash
mkdir -p .github/ISSUE_TEMPLATE

cat > .github/ISSUE_TEMPLATE/bug_report.yml << 'EOF'
name: Bug Report
description: File a bug report to help us improve
title: "[Bug]: "
labels: ["bug", "triage"]
body:
  - type: markdown
    attributes:
      value: |
        Thanks for taking the time to fill out this bug report!
        
  - type: checkboxes
    id: terms
    attributes:
      label: Pre-submission Checklist
      options:
        - label: I have searched existing issues to ensure this isn't a duplicate
          required: true
        - label: I have read the troubleshooting section in README.md
          required: true
          
  - type: textarea
    id: what-happened
    attributes:
      label: What happened?
      description: A clear description of what the bug is
      placeholder: Describe the issue you encountered
    validations:
      required: true
      
  - type: textarea
    id: steps
    attributes:
      label: Steps to Reproduce
      description: Exact steps to reproduce the behavior
      placeholder: |
        1. Go to '...'
        2. Click on '...'
        3. Enter '...'
        4. See error
    validations:
      required: true
      
  - type: textarea
    id: expected
    attributes:
      label: Expected Behavior
      description: What you expected to happen
    validations:
      required: true
      
  - type: dropdown
    id: os
    attributes:
      label: Operating System
      options:
        - macOS Sonoma (14.x)
        - macOS Monterey (12.x)
        - macOS Big Sur (11.x)
        - Other (please specify in additional context)
    validations:
      required: true
      
  - type: input
    id: python-version
    attributes:
      label: Python Version
      placeholder: "3.9.1"
    validations:
      required: true
      
  - type: textarea
    id: logs
    attributes:
      label: Relevant Log Output
      description: Please copy and paste any relevant log output (from GUI console or logs/ directory)
      render: shell
      
  - type: textarea
    id: context
    attributes:
      label: Additional Context
      description: Add any other context about the problem here
EOF

cat > .github/ISSUE_TEMPLATE/feature_request.yml << 'EOF'
name: Feature Request
description: Suggest an idea for this project
title: "[Feature]: "
labels: ["enhancement"]
body:
  - type: markdown
    attributes:
      value: |
        Thanks for suggesting a new feature!
        
  - type: textarea
    id: problem
    attributes:
      label: Problem Description
      description: Is your feature request related to a problem? Please describe.
      placeholder: A clear description of what the problem is. Ex. I'm always frustrated when [...]
    validations:
      required: true
      
  - type: textarea
    id: solution
    attributes:
      label: Proposed Solution
      description: Describe the solution you'd like
      placeholder: A clear description of what you want to happen
    validations:
      required: true
      
  - type: textarea
    id: alternatives
    attributes:
      label: Alternative Solutions
      description: Describe alternatives you've considered
      placeholder: A clear description of any alternative solutions or features you've considered
      
  - type: dropdown
    id: priority
    attributes:
      label: Priority
      options:
        - Low (nice to have)
        - Medium (would improve workflow)
        - High (significant improvement)
        - Critical (blocking current use)
    validations:
      required: true
      
  - type: checkboxes
    id: contribution
    attributes:
      label: Contribution
      options:
        - label: I would be willing to implement this feature
        - label: I would be willing to test this feature
EOF
```

### **6. Create Pull Request Template**

```bash
cat > .github/pull_request_template.md << 'EOF'
## Description

Brief description of changes made.

## Type of Change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Code refactoring

## Testing

- [ ] Tests pass locally
- [ ] New tests added for new functionality
- [ ] Manual testing completed

## Checklist

- [ ] Code follows project style guidelines
- [ ] Self-review of code completed
- [ ] Code is commented, particularly in hard-to-understand areas
- [ ] Documentation updated (README.md, docstrings, etc.)
- [ ] No sensitive data (API keys, personal info) included

## Screenshots (if applicable)

Add screenshots to show GUI changes or new features.

## Related Issues

Closes #(issue number)

## Additional Notes

Any additional information that reviewers should know.
EOF
```

### **7. Set Up GitHub Actions (CI/CD)**

```bash
mkdir -p .github/workflows

cat > .github/workflows/ci.yml << 'EOF'
name: CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  test:
    runs-on: macos-latest
    strategy:
      matrix:
        python-version: [3.9, 3.10, 3.11]

    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
        
    - name: Install system dependencies
      run: |
        brew install ffmpeg
        
    - name: Install Python dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements-dev.txt
        pip install -e .
        
    - name: Lint with flake8
      run: |
        flake8 src/ --count --select=E9,F63,F7,F82 --show-source --statistics
        flake8 src/ --count --exit-zero --max-complexity=10 --max-line-length=100 --statistics
        
    - name: Type check with mypy
      run: |
        mypy src/
        
    - name: Test with pytest
      run: |
        pytest tests/ --cov=knowledge_system --cov-report=xml
        
    - name: Upload coverage reports
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        flags: unittests
        name: codecov-umbrella

  build:
    runs-on: macos-latest
    needs: test
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: 3.9
        
    - name: Install build dependencies
      run: |
        python -m pip install --upgrade pip
        pip install build
        
    - name: Build package
      run: |
        python -m build
        
    - name: Upload build artifacts
      uses: actions/upload-artifact@v3
      with:
        name: dist
        path: dist/
EOF
```

### **8. Create Release Workflow**

```bash
cat > .github/workflows/release.yml << 'EOF'
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: macos-latest
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: 3.9
        
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install build
        
    - name: Build package
      run: |
        python -m build
        
    - name: Create Release
      uses: actions/create-release@v1
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      with:
        tag_name: ${{ github.ref }}
        release_name: Release ${{ github.ref }}
        draft: false
        prerelease: false
        
    - name: Upload Release Assets
      uses: actions/upload-release-asset@v1
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      with:
        upload_url: ${{ steps.create_release.outputs.upload_url }}
        asset_path: ./dist/
        asset_name: knowledge-system-dist
        asset_content_type: application/zip
EOF
```

## 🚀 **Upload and Initial Setup**

### **9. Push Everything to GitHub**

```bash
# Add all new files
git add .

# Commit GitHub configuration
git commit -m "docs: add GitHub templates and CI/CD workflows

- Add CONTRIBUTING.md with development guidelines
- Add CHANGELOG.md for version tracking
- Add GitHub issue templates for bugs and features
- Add pull request template
- Add CI/CD workflows for testing and releases
- Configure automated testing on multiple Python versions"

# Push to GitHub
git push origin main
```

### **10. Configure Repository Settings**

**In GitHub Web Interface:**

1. **Go to Settings → General:**
   - Enable "Allow squash merging"
   - Enable "Allow rebase merging"
   - Disable "Allow merge commits" (optional, for cleaner history)

2. **Go to Settings → Branches:**
   - Add branch protection rule for `main`:
     - ☑️ Require a pull request before merging
     - ☑️ Require status checks to pass before merging
     - ☑️ Require branches to be up to date before merging

3. **Go to Settings → Security & Analysis:**
   - Enable Dependabot alerts
   - Enable Dependabot security updates

4. **Go to Issues → Labels:**
   - Create labels: `bug`, `enhancement`, `documentation`, `good first issue`, `help wanted`

## 🔄 **Ongoing Maintenance Workflow**

### **11. Daily Development Workflow**

```bash
# Start new feature
git checkout main
git pull origin main
git checkout -b feature/new-feature-name

# Make changes, commit regularly
git add .
git commit -m "feat: implement new feature"

# Push feature branch
git push origin feature/new-feature-name

# Create pull request on GitHub
# After review and approval, merge via GitHub
# Delete feature branch
git checkout main
git pull origin main
git branch -d feature/new-feature-name
```

### **12. Release Process**

```bash
# Update version in pyproject.toml
# Update CHANGELOG.md with new version
git add .
git commit -m "chore: prepare release v1.1.0"
git push origin main

# Create release tag
git tag -a v1.1.0 -m "Release v1.1.0: Add quality detection features"
git push origin v1.1.0

# GitHub Actions will automatically create release
```

### **13. Monitoring and Maintenance**

**Weekly Tasks:**
- Review open issues and PRs
- Update dependencies: `pip-audit` for security
- Check CI/CD pipeline health
- Review usage analytics (if enabled)

**Monthly Tasks:**
- Update dependencies in `requirements.txt`
- Review and update documentation
- Check for outdated GitHub Actions
- Security audit of dependencies

## 🔒 **Security Considerations**

### **14. Protect Sensitive Data**

Your `.gitignore` already protects:
- API keys (`config/settings.yaml`)
- Client secrets (`config/client_secret_*.json`)
- Environment files (`.env.local`)

**Additional security:**
```bash
# Use GitHub secrets for CI/CD
# Never commit:
# - API keys
# - User data
# - Large model files
# - Personal information

# Use environment variables in workflows:
# ${{ secrets.OPENAI_API_KEY }}
```

## 📊 **Repository Management Tools**

### **15. Useful GitHub Features**

**Enable in your repository:**
- **Discussions**: For community Q&A
- **Projects**: For roadmap tracking
- **Wiki**: For detailed documentation
- **Sponsors**: If accepting donations

**Third-party integrations:**
- **Codecov**: Code coverage reporting
- **Dependabot**: Automated dependency updates
- **CodeQL**: Security scanning

## 🎯 **Quick Start Commands Summary**

```bash
# Initial setup
git init
git add .
git commit -m "Initial commit: Knowledge System v1.0"
git remote add origin https://github.com/yourusername/knowledge-system.git
git push -u origin main

# Create all GitHub files (run these commands in your project directory)
# Then add and commit them:
git add .
git commit -m "docs: add GitHub templates and CI/CD workflows"
git push origin main

# Daily workflow
git checkout -b feature/new-feature
# Make changes
git add .
git commit -m "feat: add new feature"
git push origin feature/new-feature
# Create PR on GitHub

# Release workflow
git tag -a v1.1.0 -m "Release v1.1.0"
git push origin v1.1.0
```

This comprehensive setup gives you a professional, maintainable GitHub repository with automated testing, proper documentation, and clear contribution guidelines! 🚀

## 📝 **Notes**

- Replace `yourusername` with your actual GitHub username
- Update repository URLs to match your actual repository
- Customize labels, templates, and workflows as needed
- Consider enabling GitHub Discussions for community engagement
- Set up branch protection rules for better code quality control
- Monitor repository analytics and adjust workflows based on usage patterns

---

**Created:** 2024
**Version:** 1.0
**Author:** Knowledge System Project 