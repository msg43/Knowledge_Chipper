#!/bin/bash
# Test Failure Handling Guide for Knowledge Chipper
# This script provides systematic approaches to fixing different types of test failures

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "\n${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}"
}

print_section() {
    echo -e "\n${YELLOW}--- $1 ---${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

show_help() {
    cat << EOF
Test Failure Handling Guide for Knowledge Chipper

This script helps you systematically fix different types of test failures:

Usage: $0 [OPTION]

Options:
    --linting           Fix linting issues (style, formatting)
    --test-failures     Debug and fix test failures
    --warnings          Handle deprecation and other warnings
    --security          Address security findings
    --dependencies      Fix dependency issues
    --all               Show guidance for all issue types
    -h, --help          Show this help

Examples:
    $0 --linting        # Fix code style issues
    $0 --test-failures  # Debug failing tests
    $0 --all            # Complete failure handling guide

EOF
}

handle_linting_issues() {
    print_header "Handling Linting Issues"

    print_section "1. Auto-Fix What You Can"
    echo "Many linting issues can be automatically fixed:"
    echo ""
    echo "# Auto-format code"
    echo "make format"
    echo ""
    echo "# This runs:"
    echo "black src/ tests/ scripts/     # Fix line length, formatting"
    echo "isort src/ tests/ scripts/     # Fix import ordering"
    echo ""

    print_section "2. Line Length Issues (E501)"
    echo "For lines too long (>100 characters):"
    echo ""
    echo "# Before (103 characters)"
    echo 'logger.info(f"Processing file {filename} with very long parameters and descriptions")'
    echo ""
    echo "# After (under 100 characters)"
    echo 'logger.info('
    echo '    f"Processing file {filename} with very long parameters "'
    echo '    f"and descriptions"'
    echo ')'
    echo ""

    print_section "3. Complexity Issues (C901)"
    echo "For functions that are too complex:"
    echo ""
    echo "# Break large functions into smaller ones"
    echo "# Extract helper methods"
    echo "# Use early returns to reduce nesting"
    echo ""
    echo "Example refactoring:"
    echo "def complex_function(data):"
    echo "    # Instead of deep nesting, use early returns"
    echo "    if not data:"
    echo "        return None"
    echo "    "
    echo "    if not validate_data(data):"
    echo "        return None"
    echo "    "
    echo "    return process_data(data)"
    echo ""

    print_section "4. Unused Imports (F401)"
    echo "Remove or fix unused imports:"
    echo ""
    echo "# Remove completely unused imports"
    echo "# Add '# noqa: F401' for imports used by other modules"
    echo "# Use TYPE_CHECKING for type-only imports"
    echo ""
    echo "from typing import TYPE_CHECKING"
    echo ""
    echo "if TYPE_CHECKING:"
    echo "    from some_module import SomeType"
    echo ""

    print_section "5. Batch Fix Approach"
    echo "For many violations, fix in batches:"
    echo ""
    echo "# 1. Run auto-fixers first"
    echo "make format"
    echo ""
    echo "# 2. Fix one file at a time"
    echo "flake8 src/knowledge_system/processors/youtube_transcript.py"
    echo ""
    echo "# 3. Check progress"
    echo "make lint | wc -l  # Count remaining violations"
    echo ""
}

handle_test_failures() {
    print_header "Handling Test Failures"

    print_section "1. Analyze the Error Messages"
    echo "Test failures usually fall into these categories:"
    echo ""
    echo "• Import Errors: Module path issues"
    echo "• Assertion Errors: Logic/expectation mismatches"
    echo "• Environment Errors: Missing dependencies"
    echo "• Configuration Errors: Wrong settings"
    echo ""

    print_section "2. Common Test Failure Types"
    echo ""
    echo "A) Import Errors:"
    echo "   Problem: ModuleNotFoundError: No module named 'src'"
    echo "   Solution: Fix import paths in tests"
    echo "   "
    echo "   # Wrong"
    echo "   from src.knowledge_system.module import Class"
    echo "   "
    echo "   # Right"
    echo "   from knowledge_system.module import Class"
    echo ""
    echo "B) Assertion Errors:"
    echo "   Problem: Expected behavior doesn't match actual"
    echo "   Solution: Debug the test logic"
    echo "   "
    echo "   # Add debug output"
    echo "   print(f'Expected: {expected}, Got: {actual}')"
    echo "   "
    echo "   # Check if test expectations are still valid"
    echo ""
    echo "C) Missing Dependencies:"
    echo "   Problem: Tests require optional packages"
    echo "   Solution: Install missing packages or skip tests"
    echo "   "
    echo "   # Skip if dependency missing"
    echo "   @pytest.mark.skipif(not has_librosa, reason='librosa not available')"
    echo ""

    print_section "3. Debugging Workflow"
    echo "1. Run single failing test for detailed output:"
    echo "   pytest tests/test_diarization_formatting.py::TestDiarizationFormatting::test_enhanced_speaker_intelligence -v -s"
    echo ""
    echo "2. Add debug prints to understand the issue"
    echo ""
    echo "3. Check if test data/expectations are still valid"
    echo ""
    echo "4. Fix the underlying code or update the test"
    echo ""
    echo "5. Re-run to verify fix"
    echo ""
}

handle_warnings() {
    print_header "Handling Warnings"

    print_section "1. Deprecation Warnings"
    echo "These are usually safe to defer but should be addressed:"
    echo ""
    echo "• Pydantic V1 style validators → V2 style"
    echo "• SQLAlchemy declarative_base() → orm.declarative_base()"
    echo "• TorchAudio backend warnings"
    echo ""
    echo "Approach:"
    echo "1. Note the warnings but don't block releases"
    echo "2. Create issues to track upgrades"
    echo "3. Fix during maintenance cycles"
    echo ""

    print_section "2. Filtering Warnings"
    echo "You can suppress warnings in pytest.ini or pyproject.toml:"
    echo ""
    echo "[tool.pytest.ini_options]"
    echo "filterwarnings = ["
    echo '    "ignore::DeprecationWarning",'
    echo '    "ignore::PytestReturnNotNoneWarning",'
    echo "]"
    echo ""
}

handle_security_issues() {
    print_header "Handling Security Issues"

    print_section "1. Review bandit-report.json"
    echo "After tests run, check the security report:"
    echo ""
    echo "cat bandit-report.json | jq '.results[] | {filename, test_name, issue_text}'"
    echo ""

    print_section "2. Common Security Issues"
    echo ""
    echo "B101: assert_used - Using assert in production code"
    echo "  Solution: Replace with proper error handling"
    echo ""
    echo "B601: shell injection - Using shell=True"
    echo "  Solution: Use subprocess with shell=False and list args"
    echo ""
    echo "B101: hardcoded passwords - Secrets in code"
    echo "  Solution: Use environment variables or config files"
    echo ""

    print_section "3. Acceptable Risks"
    echo "Some bandit warnings are acceptable for your use case:"
    echo ""
    echo "• Shell commands for system integration (with validation)"
    echo "• Asserts in test code"
    echo "• Local file operations"
    echo ""
    echo "Use # noqa: B601 to suppress specific acceptable warnings"
    echo ""
}

handle_dependencies() {
    print_header "Handling Dependency Issues"

    print_section "1. Missing Optional Dependencies"
    echo "Some features require optional packages:"
    echo ""
    echo "• librosa - Audio processing"
    echo "• PyQt6 - GUI functionality"
    echo "• whisper - Local transcription"
    echo ""
    echo "Solutions:"
    echo "1. Install if needed: pip install librosa"
    echo "2. Skip tests: pytest -k 'not slow and not librosa'"
    echo "3. Make features gracefully degrade"
    echo ""

    print_section "2. Version Conflicts"
    echo "If you get version conflicts:"
    echo ""
    echo "1. Check requirements.txt for pinned versions"
    echo "2. Update to compatible versions"
    echo "3. Use virtual environment isolation"
    echo ""
    echo "# Check current versions"
    echo "pip list | grep -E '(torch|transformers|pydantic)'"
    echo ""
}

show_complete_guide() {
    print_header "Complete Test Failure Handling Workflow"

    echo "When release mode fails, follow this systematic approach:"
    echo ""
    echo "1. 🔍 CATEGORIZE THE FAILURES"
    echo "   • Linting violations (style/format)"
    echo "   • Test failures (functional problems)"
    echo "   • Warnings (deprecation, etc.)"
    echo "   • Security issues"
    echo "   • Dependency problems"
    echo ""
    echo "2. 🚀 QUICK WINS FIRST"
    echo "   make format                    # Auto-fix formatting"
    echo "   pip install missing-deps      # Install missing packages"
    echo ""
    echo "3. 🎯 PRIORITIZE BY SEVERITY"
    echo "   High:   Test failures, security issues"
    echo "   Medium: Linting violations, import errors"
    echo "   Low:    Warnings, deprecation notices"
    echo ""
    echo "4. 🔧 FIX SYSTEMATICALLY"
    echo "   • One category at a time"
    echo "   • One file at a time for large issues"
    echo "   • Re-run tests after each batch of fixes"
    echo ""
    echo "5. 📋 ACCEPTABLE COMPROMISES"
    echo "   For solo development, you can:"
    echo "   • Defer deprecation warnings"
    echo "   • Accept some linting violations"
    echo "   • Skip tests for missing optional deps"
    echo ""
    echo "6. 🎉 VALIDATION"
    echo "   ./scripts/full-test.sh --release"
    echo "   → Should pass with only acceptable warnings"
    echo ""

    print_section "Decision Framework"
    echo ""
    echo "❌ MUST FIX (blocks release):"
    echo "   • Test failures in core functionality"
    echo "   • Import errors"
    echo "   • Critical security issues"
    echo ""
    echo "⚠️  SHOULD FIX (but doesn't block):"
    echo "   • Line length violations"
    echo "   • Unused imports"
    echo "   • Minor complexity issues"
    echo ""
    echo "✅ CAN DEFER:"
    echo "   • Deprecation warnings"
    echo "   • Optional dependency warnings"
    echo "   • Non-critical style issues"
    echo ""
}

# Main execution
case "${1:-}" in
    --linting)
        handle_linting_issues
        ;;
    --test-failures)
        handle_test_failures
        ;;
    --warnings)
        handle_warnings
        ;;
    --security)
        handle_security_issues
        ;;
    --dependencies)
        handle_dependencies
        ;;
    --all)
        show_complete_guide
        ;;
    -h|--help)
        show_help
        ;;
    *)
        show_help
        ;;
esac
