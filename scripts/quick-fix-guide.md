# Quick Fix Guide for Release Mode Testing

## 🎯 When Release Mode Fails: Your Action Plan

### Step 1: Quick Wins (5 minutes)
```bash
# Auto-fix most formatting issues
make format

# Install any missing optional dependencies  
pip install librosa whisper PyQt6

# Re-run to see remaining issues
./scripts/full-test.sh --quick
```

### Step 2: Categorize What's Left

**❌ MUST FIX (blocks release):**
- Import errors (`ModuleNotFoundError`)
- Test assertion failures
- Critical security issues (B601 shell injection)

**⚠️ SHOULD FIX (but acceptable for solo dev):**
- Line length violations (E501)
- Unused imports (F401)
- Function complexity (C901)

**✅ CAN IGNORE:**
- Deprecation warnings
- Pydantic V1 warnings
- PyPDF2 warnings

### Step 3: Common Quick Fixes

#### Import Errors
```python
# Wrong
from src.knowledge_system.module import Class

# Right  
from knowledge_system.module import Class
```

#### Line Length (E501)
```python
# Before (too long)
logger.info(f"Processing {filename} with parameters {param1} and {param2}")

# After (split)
logger.info(
    f"Processing {filename} with parameters {param1} and {param2}"
)
```

#### Unused Imports (F401)
```python
# Option 1: Remove if truly unused
# import unused_module  # Remove this

# Option 2: Mark as intentional
import used_by_other_files  # noqa: F401

# Option 3: Type-only imports
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from some_module import SomeType
```

#### Complex Functions (C901)
```python
# Break into smaller functions
# Use early returns
# Extract helper methods

def complex_function(data):
    if not data:
        return None  # Early return
    
    if not _validate_data(data):  # Extract helper
        return None
        
    return _process_data(data)  # Extract helper
```

### Step 4: Test-Specific Fixes

#### Single Test Debugging
```bash
# Run one failing test with full output
pytest tests/test_file.py::TestClass::test_method -v -s

# Add debug prints to the test
print(f"Expected: {expected}, Got: {actual}")
```

#### Skip Tests for Missing Dependencies
```python
@pytest.mark.skipif(not has_librosa, reason="librosa not available")
def test_audio_processing():
    # Test code here
```

### Step 5: Pragmatic Compromises for Solo Dev

```bash
# Accept some linting violations
make lint | grep -E "(E501|F401)" | wc -l  # Count remaining

# If under 50 violations, acceptable for solo project
if [ $(make lint 2>&1 | tail -1) -lt 50 ]; then
    echo "✅ Acceptable for solo development"
fi
```

#### Filter Out Acceptable Warnings
Add to `pyproject.toml`:
```toml
[tool.pytest.ini_options]
filterwarnings = [
    "ignore::DeprecationWarning",
    "ignore::PytestReturnNotNoneWarning",
    "ignore:.*declarative_base.*:sqlalchemy.exc.MovedIn20Warning",
]
```

### Step 6: Release Decision Framework

**Release Criteria for Solo Development:**

✅ **Good to Release:**
- Core functionality tests pass
- No import errors
- Security issues reviewed (not necessarily all fixed)
- < 50 non-critical linting violations

⚠️ **Consider Deferring:**
- > 100 linting violations
- Multiple test failures
- Critical security vulnerabilities

### Step 7: Validation

```bash
# Final check
./scripts/full-test.sh --release

# If it completes with only warnings/minor violations:
echo "🚀 Ready to release!"

# Create your release
git add .
git commit -m "Release preparation: fix critical issues"
git tag v3.2.1
git push origin main --tags
```

## 🛠️ Available Helper Scripts

```bash
# Complete guidance
./scripts/handle-test-failures.sh --all

# Specific issue types
./scripts/handle-test-failures.sh --linting
./scripts/handle-test-failures.sh --test-failures
./scripts/handle-test-failures.sh --warnings

# Quick fixes
make format                    # Auto-fix formatting
make lint | tail -1           # Count violations
make test-quick               # Fast verification
```

## 💡 Solo Developer Philosophy

**Perfect is the enemy of good.** For solo development:

1. **Prioritize functionality over perfect style**
2. **Fix critical issues, defer cosmetic ones**
3. **Use your judgment on acceptable compromises**
4. **Keep technical debt manageable, not zero**

Remember: You're not managing a team codebase. Optimize for your productivity, not enterprise standards.
