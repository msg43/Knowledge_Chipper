#!/bin/bash
# Setup script for pre-commit hooks in Knowledge_Chipper

set -e  # Exit on any error

echo "🚀 Setting up pre-commit hooks for Knowledge_Chipper..."

# Check if we're in a virtual environment
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "⚠️  Warning: Not in a virtual environment. Activating venv..."
    if [ -d "venv" ]; then
        source venv/bin/activate
        echo "✅ Activated virtual environment"
    else
        echo "❌ Virtual environment not found. Please run:"
        echo "   python3 -m venv venv"
        echo "   source venv/bin/activate"
        echo "   pip install -r requirements-dev.txt"
        exit 1
    fi
fi

# Install/upgrade development dependencies
echo "📦 Installing development dependencies..."
pip install --upgrade pip
pip install -r requirements-dev.txt

# Install pre-commit hooks
echo "🔧 Installing pre-commit hooks..."
pre-commit install

# Install commit message hook for conventional commits
echo "📝 Installing commit message hooks..."
pre-commit install --hook-type commit-msg

# Run pre-commit on all files to check setup
echo "🧪 Testing pre-commit setup on all files..."
echo "This may take a few minutes on first run as hooks are downloaded..."

# Run with some hooks that might auto-fix issues
echo "Running auto-fixable hooks first..."
pre-commit run trailing-whitespace --all-files || true
pre-commit run end-of-file-fixer --all-files || true
pre-commit run mixed-line-ending --all-files || true
pre-commit run black --all-files || true
pre-commit run isort --all-files || true
pre-commit run pyupgrade --all-files || true

echo ""
echo "Running remaining checks..."
if pre-commit run --all-files; then
    echo ""
    echo "✅ All pre-commit hooks passed!"
else
    echo ""
    echo "⚠️  Some hooks failed. This is normal on first setup."
    echo "The hooks have auto-fixed what they can."
    echo "Please review the changes and commit them:"
    echo ""
    echo "  git add ."
    echo "  git commit -m 'style: apply pre-commit auto-fixes'"
    echo ""
    echo "Then run 'pre-commit run --all-files' again to check remaining issues."
fi

echo ""
echo "🎉 Pre-commit setup complete!"
echo ""
echo "📋 What happens now:"
echo "  • Before each commit, hooks will run automatically"
echo "  • Code will be formatted with Black and isort"
echo "  • Linting will catch potential issues"
echo "  • Type checking will run on src/ directory"
echo "  • Security scanning will check for vulnerabilities"
echo "  • Commit messages will be validated (conventional commits)"
echo ""
echo "🔧 Useful commands:"
echo "  pre-commit run --all-files    # Run all hooks manually"
echo "  pre-commit run <hook-name>    # Run specific hook"
echo "  pre-commit autoupdate         # Update hook versions"
echo "  git commit --no-verify        # Skip hooks (emergency only)"
echo ""
echo "📖 For more info: https://pre-commit.com/"

# Offer to install a pre-push hook that updates build metadata in version.py (no index mutation on commit)
HOOK_PATH=".git/hooks/pre-push"
if [ -d .git ]; then
  echo ""
  read -p "Install build-metadata pre-push hook to update src/knowledge_system/version.py (BRANCH/BUILD_DATE) automatically? (y/N): " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    cat > "$HOOK_PATH" << 'EOF'
#!/bin/bash
# Update build metadata (BRANCH, BUILD_DATE) in src/knowledge_system/version.py without changing semantic VERSION

VP="src/knowledge_system/version.py"
if [ ! -f "$VP" ]; then
  exit 0
fi

current_version=$(grep '^VERSION\s*=\s*"' "$VP" | sed -E 's/.*"([^"]+)".*/\1/')
current_branch=$(git rev-parse --abbrev-ref HEAD)
current_date=$(date +"%Y-%m-%d")

tmpfile=$(mktemp)
awk -v ver="$current_version" -v branch="$current_branch" -v today="$current_date" '
  /^VERSION\s*=/{ sub(/"[^"]+"/,"\"" ver "\"",$0); print; next }
  /^BRANCH\s*=/{ sub(/"[^"]+"/,"\"" branch "\"",$0); print; next }
  /^BUILD_DATE\s*=/{ sub(/"[^"]+"/,"\"" today "\"",$0); print; next }
  { print }
' "$VP" > "$tmpfile" && mv "$tmpfile" "$VP"

git add "$VP"
git commit --no-verify -m "chore(build): update build metadata (branch/date)"
exit 0
EOF
    chmod +x "$HOOK_PATH"
    echo "✅ Installed build-metadata pre-push hook."

    # Migrate any existing pre-commit version-bump hook to avoid GUI commit stalls
    if [ -f ".git/hooks/pre-commit" ]; then
      if grep -q 'src/knowledge_system/version.py' ".git/hooks/pre-commit"; then
        mv .git/hooks/pre-commit .git/hooks/pre-commit.disabled 2>/dev/null || true
        echo "ℹ️  Disabled existing pre-commit version-bump hook (migrated to pre-push)."
      fi
    fi
  else
    echo "ℹ️  Skipped installing version-bump hook."
  fi
fi
