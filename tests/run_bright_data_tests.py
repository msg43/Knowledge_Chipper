"""
Test runner for Bright Data integration tests.

Provides a convenient way to run all Bright Data-related tests with proper setup
and comprehensive reporting.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def setup_test_environment():
    """Set up test environment variables."""
    # Set up test database
    test_db_path = tempfile.mktemp(suffix=".db")

    # Set test environment variables
    test_env = {
        "PYTEST_CURRENT_TEST": "bright_data_tests",
        "TEST_DATABASE_URL": f"sqlite:///{test_db_path}",
        "BD_CUST": "c_test_customer",
        "BD_ZONE": "test_zone",
        "BD_PASS": "test_password",
    }

    # Merge with existing environment
    env = os.environ.copy()
    env.update(test_env)

    return env, test_db_path


def run_bright_data_tests(verbose=True, coverage=False):
    """
    Run all Bright Data integration tests.

    Args:
        verbose: Show detailed test output
        coverage: Generate coverage report
    """
    print("🧪 Running Bright Data Integration Tests")
    print("=" * 50)

    # Setup test environment
    env, test_db_path = setup_test_environment()

    try:
        # Define test files to run
        test_files = [
            "tests/test_bright_data_adapters.py",
            "tests/unit/test_bright_data_session_manager.py",
            "tests/unit/test_cost_tracking.py",
            "tests/integration/test_bright_data_integration.py",
        ]

        # Build pytest command
        cmd = ["python", "-m", "pytest"]

        if verbose:
            cmd.append("-v")
            cmd.append("-s")

        if coverage:
            cmd.extend(
                [
                    "--cov=knowledge_system.utils.bright_data",
                    "--cov=knowledge_system.utils.bright_data_adapters",
                    "--cov=knowledge_system.utils.cost_tracking",
                    "--cov=knowledge_system.utils.deduplication",
                    "--cov-report=html",
                    "--cov-report=term-missing",
                ]
            )

        # Add test files
        cmd.extend(test_files)

        # Add test markers for Bright Data tests
        cmd.extend(["-m", "not slow"])  # Skip slow tests by default

        print(f"Running command: {' '.join(cmd)}")
        print()

        # Run tests
        result = subprocess.run(cmd, env=env, capture_output=False)

        if result.returncode == 0:
            print("\n✅ All Bright Data tests passed!")

            if coverage:
                print("\n📊 Coverage report generated in htmlcov/")
        else:
            print(f"\n❌ Tests failed with exit code {result.returncode}")

        return result.returncode == 0

    except Exception as e:
        print(f"❌ Failed to run tests: {e}")
        return False

    finally:
        # Cleanup test database
        if os.path.exists(test_db_path):
            os.unlink(test_db_path)


def run_specific_test_category(category):
    """Run specific category of tests."""
    categories = {
        "adapters": ["tests/test_bright_data_adapters.py"],
        "session": ["tests/unit/test_bright_data_session_manager.py"],
        "cost": ["tests/unit/test_cost_tracking.py"],
        "integration": ["tests/integration/test_bright_data_integration.py"],
        "unit": [
            "tests/unit/test_bright_data_session_manager.py",
            "tests/unit/test_cost_tracking.py",
        ],
    }

    if category not in categories:
        print(f"❌ Unknown category: {category}")
        print(f"Available categories: {', '.join(categories.keys())}")
        return False

    print(f"🧪 Running {category} tests...")

    env, test_db_path = setup_test_environment()

    try:
        cmd = ["python", "-m", "pytest", "-v", "-s"] + categories[category]

        result = subprocess.run(cmd, env=env)
        return result.returncode == 0

    finally:
        if os.path.exists(test_db_path):
            os.unlink(test_db_path)


def validate_test_dependencies():
    """Validate that all test dependencies are available."""
    print("🔍 Validating test dependencies...")

    required_packages = ["pytest", "pytest-cov", "knowledge_system"]

    missing_packages = []

    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
            print(f"   ✅ {package}")
        except ImportError:
            missing_packages.append(package)
            print(f"   ❌ {package}")

    if missing_packages:
        print(f"\n❌ Missing packages: {', '.join(missing_packages)}")
        print("Install with: pip install " + " ".join(missing_packages))
        return False

    print("✅ All dependencies available")
    return True


def main():
    """Main test runner."""
    import argparse

    parser = argparse.ArgumentParser(description="Run Bright Data integration tests")
    parser.add_argument(
        "--category",
        choices=["adapters", "session", "cost", "integration", "unit"],
        help="Run specific test category",
    )
    parser.add_argument(
        "--coverage", action="store_true", help="Generate coverage report"
    )
    parser.add_argument("--quick", action="store_true", help="Run only fast tests")
    parser.add_argument(
        "--validate", action="store_true", help="Only validate dependencies"
    )

    args = parser.parse_args()

    # Validate dependencies first
    if not validate_test_dependencies():
        sys.exit(1)

    if args.validate:
        print("✅ Dependency validation complete")
        return

    # Run specific category if requested
    if args.category:
        success = run_specific_test_category(args.category)
        sys.exit(0 if success else 1)

    # Run all tests
    success = run_bright_data_tests(verbose=not args.quick, coverage=args.coverage)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
