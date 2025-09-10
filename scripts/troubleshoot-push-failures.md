# Troubleshooting push_to_github.sh Failures

## 🚨 When push_to_github.sh Fails: Your Action Plan

### Step 1: Identify the Failure Type (30 seconds)

```bash
# Run the pre-push checks manually to see what's failing
pre-commit run --hook-stage pre-push --all-files
```

Look for the **exit code** and **specific errors**:

### Step 2: Common Failure Types & Quick Fixes

#### ❌ **Flake8 Errors (F821, E501, etc.)**
**Symptoms:** `F821 undefined name`, `E501 line too long`, etc.

**Quick Fix:**
```bash
# Auto-fix what you can
make format

# Check remaining issues
make lint

# Fix specific issues manually, then commit
git add . && git commit -m "fix: resolve linting issues"
```

#### ❌ **Import/Syntax Errors**
**Symptoms:** `ModuleNotFoundError`, `SyntaxError`, undefined variables

**Quick Fix:**
```bash
# Find the specific files with issues
pre-commit run --hook-stage pre-push flake8 --all-files

# Fix the imports/variables in the reported files
# Example: Fix undefined variables like 'supported_extensions' → 'extensions'
```

#### ❌ **Security Issues (Bandit)**
**Symptoms:** `B301 pickle`, `B603 subprocess`, security warnings

**Quick Fix:**
```bash
# For legitimate security warnings, add nosec comments:
# import pickle  # nosec B403 # Safe: Only used for local caching
# subprocess.call(cmd)  # nosec B603 # Safe: cmd is sanitized

# Then commit the fixes
git add . && git commit -m "fix: add security exception comments"
```

#### ❌ **Test Collection Errors**
**Symptoms:** `pytest --collect-only` fails, import errors in tests

**Quick Fix:**
```bash
# Test specific modules
pytest --collect-only tests/

# Fix import paths in test files:
# from src.knowledge_system.module → from knowledge_system.module
```

#### ❌ **Formatting Issues (Black/isort)**
**Symptoms:** Black reformatted files, isort fixed imports

**Quick Fix:**
```bash
# These auto-fix themselves, just commit the changes
git add . && git commit -m "style: apply automatic formatting fixes"
```

### Step 3: The Universal Fix Workflow

If you're unsure what's wrong, follow this sequence:

```bash
# 1. Auto-fix formatting and simple issues
make format

# 2. Run our comprehensive test with auto-fixing
./scripts/full-test.sh --quick --auto-fix

# 3. Check what still needs manual fixing
pre-commit run --hook-stage pre-push --all-files

# 4. Fix any remaining issues manually

# 5. Commit all fixes
git add . && git commit -m "fix: resolve pre-commit issues"

# 6. Try push again
./scripts/push_to_github.sh
```

### Step 4: If All Else Fails - Override Mode

**⚠️ Use sparingly for urgent pushes:**

Edit `scripts/push_to_github.sh` temporarily and add this after line 40:

```bash
# TEMPORARY: Skip pre-commit checks for urgent push
echo "⚠️ Skipping pre-commit checks (TEMPORARY)"
# Comment out the pre-commit run line:
# if ! pre-commit run --hook-stage pre-push --all-files; then
```

**Remember to uncomment it after the push!**

### Step 5: Common File-Specific Fixes

#### **Undefined Variable Errors**
```python
# Wrong:
if file_path.suffix.lower() in supported_extensions:

# Right:
if file_path.suffix.lower() in extensions:
```

#### **Import Path Errors**
```python
# Wrong:
from src.knowledge_system.module import Class

# Right:
from knowledge_system.module import Class
```

#### **Security Exceptions**
```python
# For safe pickle usage:
import pickle  # nosec B403 # Safe: Only used for local caching
data = pickle.load(f)  # nosec B301 # Safe: Only loading local cache files

# For safe subprocess usage:
subprocess.run(cmd, shell=False)  # nosec B603 # Safe: shell=False used
```

### Step 6: Prevention Tips

1. **Use our local testing before pushing:**
   ```bash
   ./scripts/full-test.sh --quick --auto-fix
   ```

2. **Set up pre-commit hooks locally:**
   ```bash
   pre-commit install
   # Now checks run automatically on each commit
   ```

3. **Run lint checks during development:**
   ```bash
   make lint  # Quick check
   make test  # Full verification
   ```

### Emergency Contact Sheet

| Error Type | Quick Command | Time to Fix |
|------------|---------------|-------------|
| Formatting | `make format` | 30 seconds |
| Undefined vars | Manual edit + commit | 2 minutes |
| Import errors | Fix imports + commit | 3 minutes |
| Security warnings | Add `# nosec` comments | 2 minutes |
| Test collection | Fix test imports | 5 minutes |

### Last Resort: Bypass Pre-commit

If you need an emergency push and can't fix issues immediately:

```bash
# Skip pre-commit hooks entirely (NOT RECOMMENDED)
git push --no-verify origin main
```

**⚠️ Only use this for true emergencies and fix issues immediately after!**

---

## 💡 Pro Tip

Most failures are now automatically fixed by our integrated testing system:

```bash
# This will auto-fix most issues and run tests
./scripts/full-test.sh --release
```

Use this before any important push to catch and fix issues early!
