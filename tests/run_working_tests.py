#!/usr/bin/env python3
"""
Run all working test suites.

This script runs all test suites that are known to pass reliably:
- Basic unit tests
- Logger tests
- Evaluators unit tests
- Schema validation tests
- Error handling tests
- Backend integration tests (real data processing)

Usage:
    python tests/run_working_tests.py [options]

Options:
    --verbose, -v          Verbose output
    --coverage, -c         Run with coverage reporting
    --quiet, -q            Quiet mode (minimal output)
    --tb=short|long|line   Set traceback format
    --fast                 Skip slow tests
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Test suites that are known to work
WORKING_TEST_SUITES = [
    "tests/test_basic.py",
    "tests/test_logger.py",
    "tests/test_evaluators_unit.py",
    "tests/test_schema_validation.py",
    "tests/test_errors.py",
    "tests/comprehensive/test_real_integration_complete.py",
]


def main():
    """Run all working test suites."""
    import subprocess

    # Parse command line arguments
    args = sys.argv[1:]

    # Handle help
    if "--help" in args or "-h" in args:
        print(__doc__)
        return 0

    # Build pytest command
    pytest_args = ["python", "-m", "pytest"]

    # Add test files
    pytest_args.extend(WORKING_TEST_SUITES)

    # Process flags
    if "--coverage" in args or "-c" in args:
        pytest_args.extend(["--cov=src", "--cov-report=term-missing"])
        args = [a for a in args if a not in ["--coverage", "-c"]]

    if "--verbose" in args or "-v" in args:
        pytest_args.append("-v")
        args = [a for a in args if a not in ["--verbose", "-v"]]
    elif "--quiet" in args or "-q" in args:
        pytest_args.append("-q")
        args = [a for a in args if a not in ["--quiet", "-q"]]
    else:
        # Default: add -v for verbose
        pytest_args.append("-v")

    # Traceback format
    tb_format_found = False
    for arg in args:
        if arg.startswith("--tb="):
            pytest_args.append(arg)
            tb_format_found = True
            args = [a for a in args if a != arg]

    if not tb_format_found:
        pytest_args.append("--tb=line")

    # Fast mode (skip slow tests)
    if "--fast" in args:
        pytest_args.extend(["-m", "not slow"])
        args = [a for a in args if a != "--fast"]

    # Add any remaining args
    pytest_args.extend(args)

    # Print what we're running
    print("=" * 70)
    print("Running Working Test Suites")
    print("=" * 70)
    print(f"\nTest files ({len(WORKING_TEST_SUITES)} suites):")
    for suite in WORKING_TEST_SUITES:
        print(f"  ✓ {suite}")
    print(f"\nCommand: {' '.join(pytest_args)}")
    print("=" * 70)
    print()

    # Run pytest
    result = subprocess.run(pytest_args, cwd=project_root)

    return result.returncode


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
