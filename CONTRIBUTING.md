# Contributing to Knowledge_Chipper

Thank you for your interest in contributing to Knowledge_Chipper! This document provides guidelines for contributing to the project.

## 🚀 Quick Start for Contributors

### Development Setup

1. **Fork and clone the repository:**
```bash
git clone https://github.com/msg43/Knowledge_Chipper.git
cd Knowledge_Chipper
```

2. **Set up development environment:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements/development.txt
pip install -e .
```

3. **Run tests to verify setup:**
```bash
pytest
```

4. **Set up pre-commit hooks:**
```bash
./setup_precommit.sh
```

## 🔧 Development Workflow

### Pre-commit Hooks

This project uses pre-commit hooks to maintain code quality automatically. After running the setup script above, the following will happen before each commit:

- **Code formatting**: Black and isort automatically format your code
- **Linting**: flake8 catches potential issues and style violations  
- **Type checking**: mypy validates type annotations
- **Security scanning**: bandit checks for security vulnerabilities
- **File hygiene**: trailing whitespace, file endings, etc. are cleaned up
- **Commit message validation**: ensures conventional commit format

If any hook fails, the commit will be blocked until you fix the issues.

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
