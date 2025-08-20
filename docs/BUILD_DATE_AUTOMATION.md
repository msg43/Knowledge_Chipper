# Automated Build Date Management

This project automatically updates build dates across multiple files to keep version information synchronized.

## How It Works

The system maintains build dates in two key files:
- `src/knowledge_system/version.py` - Source of truth for version info
- `README.md` - User-facing version display

## Automatic Updates

### Git Pre-Commit Hook
Every time you commit to git, the build date is automatically updated to the current date.

**Location:** `.git/hooks/pre-commit`

**What it does:**
1. Gets the current date in `YYYY-MM-DD` format
2. Updates `BUILD_DATE` in `version.py`
3. Updates `**Build Date:**` in `README.md`
4. Stages the updated files for the commit

### Manual Updates

You can also update build dates manually:

```bash
# Update to current date
bash scripts/update_build_date.sh

# Update to specific date
bash scripts/update_build_date.sh 2025-08-19
```

## Files Updated

1. **`src/knowledge_system/version.py`**
   ```python
   BUILD_DATE = "2025-08-19"
   ```

2. **`README.md`**
   ```markdown
   **Version:** 3.0.0 | **Build Date:** 2025-08-19 | **Branch:** feature/hce-replacement
   ```

## Adding New Files

To add more files that should have their build dates updated:

1. **Edit the pre-commit hook** (`.git/hooks/pre-commit`)
2. **Edit the manual script** (`scripts/update_build_date.sh`)
3. **Add the file path and sed pattern** for the new file

Example for a new file:
```bash
# Add to both scripts
NEW_FILE="path/to/new/file.txt"
if [ -f "$NEW_FILE" ]; then
    sed -i '' "s/old_pattern/new_pattern/" "$NEW_FILE"
    echo "✅ Updated $NEW_FILE"
    git add "$NEW_FILE"  # Only in pre-commit hook
fi
```

## Troubleshooting

### Hook Not Running
```bash
# Check if hook is executable
ls -la .git/hooks/pre-commit

# Make executable if needed
chmod +x .git/hooks/pre-commit
```

### Test the Hook
```bash
# Test without committing
.git/hooks/pre-commit
```

### Manual Override
If you need to commit without updating the build date:
```bash
# Skip pre-commit hooks
git commit --no-verify -m "commit message"
```

## Benefits

- ✅ **Automatic**: No manual date updates needed
- ✅ **Consistent**: All files stay synchronized
- ✅ **Reliable**: Runs on every commit
- ✅ **Flexible**: Manual override available
- ✅ **Transparent**: Clear feedback on what's updated
