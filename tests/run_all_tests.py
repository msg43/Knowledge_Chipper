#!/usr/bin/env python3
"""
Unified Test Runner for Knowledge Chipper System 2

Runs all test suites (unit, integration, GUI, comprehensive) with proper
orchestration and reporting. Supports both legacy System 1 tests and new
System 2 architecture tests.

Usage:
    python tests/run_all_tests.py all              # Run all tests
    python tests/run_all_tests.py unit             # Unit tests only
    python tests/run_all_tests.py integration      # Integration tests only
    python tests/run_all_tests.py system2          # System 2 tests only
    python tests/run_all_tests.py gui              # GUI tests only
    python tests/run_all_tests.py comprehensive    # Comprehensive tests only

    # With options
    python tests/run_all_tests.py all --verbose    # Detailed output
    python tests/run_all_tests.py all --coverage   # With coverage report
    python tests/run_all_tests.py all --fast       # Skip slow tests (no Ollama)
    python tests/run_all_tests.py all --parallel   # Run tests in parallel

Note: System 2 integration tests require Ollama running with qwen2.5:7b-instruct.
      Use --fast to skip integration tests that require Ollama.

Manual Test: python3 scripts/test_ollama_integration.py
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


class TestRunner:
    """Unified test runner for all Knowledge Chipper tests."""

    def __init__(
        self,
        verbose: bool = False,
        coverage: bool = False,
        fast: bool = False,
        parallel: bool = False,
    ):
        """
        Initialize test runner.

        Args:
            verbose: Enable verbose output
            coverage: Generate coverage report
            fast: Skip slow tests
            parallel: Run tests in parallel where possible
        """
        self.verbose = verbose
        self.coverage = coverage
        self.fast = fast
        self.parallel = parallel
        self.results: dict[str, Any] = {}
        self.project_root = Path(__file__).parent.parent

    def run_pytest_suite(
        self, name: str, path: str, markers: list[str] | None = None
    ) -> bool:
        """
        Run a pytest-based test suite.

        Args:
            name: Name of the test suite
            path: Path to test directory or file
            markers: List of pytest markers to filter tests

        Returns:
            True if tests passed, False otherwise
        """
        print(f"\n{'='*80}")
        print(f"Running {name}")
        print(f"{'='*80}\n")

        cmd = ["pytest", path]

        if self.verbose:
            cmd.append("-vv")
        else:
            cmd.append("-v")

        if self.coverage:
            cmd.extend(
                ["--cov=src/knowledge_system", "--cov-report=html", "--cov-report=term"]
            )

        if self.fast:
            cmd.extend(["-m", "not slow"])

        if markers:
            for marker in markers:
                cmd.extend(["-m", marker])

        if self.parallel:
            cmd.extend(["-n", "auto"])

        # Add JSON report output
        report_path = (
            self.project_root
            / "tests"
            / "reports"
            / f"{name.replace(' ', '_').lower()}_results.json"
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        cmd.extend(["--json-report", f"--json-report-file={report_path}"])

        try:
            result = subprocess.run(cmd, cwd=self.project_root, capture_output=False)
            success = result.returncode == 0

            self.results[name] = {
                "success": success,
                "return_code": result.returncode,
                "report_path": str(report_path),
            }

            return success
        except Exception as e:
            print(f"ERROR running {name}: {e}")
            self.results[name] = {
                "success": False,
                "error": str(e),
            }
            return False

    def run_python_script(
        self, name: str, script_path: str, args: list[str] | None = None
    ) -> bool:
        """
        Run a Python test script.

        Args:
            name: Name of the test suite
            script_path: Path to Python script
            args: Additional command-line arguments

        Returns:
            True if script succeeded, False otherwise
        """
        print(f"\n{'='*80}")
        print(f"Running {name}")
        print(f"{'='*80}\n")

        cmd = ["python", script_path]

        if args:
            cmd.extend(args)

        try:
            result = subprocess.run(cmd, cwd=self.project_root, capture_output=False)
            success = result.returncode == 0

            self.results[name] = {
                "success": success,
                "return_code": result.returncode,
            }

            return success
        except Exception as e:
            print(f"ERROR running {name}: {e}")
            self.results[name] = {
                "success": False,
                "error": str(e),
            }
            return False

    def run_unit_tests(self) -> bool:
        """Run unit tests."""
        return self.run_pytest_suite("Unit Tests", "tests/unit/", markers=["unit"])

    def run_integration_tests(self) -> bool:
        """Run integration tests."""
        return self.run_pytest_suite(
            "Integration Tests", "tests/integration/", markers=["integration"]
        )

    def run_system2_tests(self) -> bool:
        """Run System 2 specific tests."""
        success = True

        # Unified HCE Operations tests (unit tests)
        success &= self.run_pytest_suite(
            "System 2 Unified HCE Tests",
            "tests/system2/test_unified_hce_operations.py",
            markers=["not integration"] if self.fast else None,
        )

        # LLM Adapter tests (requires Ollama)
        if not self.fast:
            success &= self.run_pytest_suite(
                "System 2 LLM Adapter Tests (Integration)",
                "tests/system2/test_llm_adapter_real.py",
                markers=["integration"],
            )

        # Mining tests (requires Ollama)
        if not self.fast:
            success &= self.run_pytest_suite(
                "System 2 Mining Tests (Integration)",
                "tests/system2/test_mining_full.py",
                markers=["integration"],
            )

        # Orchestrator integration tests (requires Ollama)
        if not self.fast:
            success &= self.run_pytest_suite(
                "System 2 Orchestrator Integration Tests",
                "tests/system2/test_orchestrator_integration.py",
                markers=["integration"],
            )

        # Legacy System 2 tests (if they still exist)
        legacy_tests = [
            ("tests/integration/test_system2_database.py", "Database"),
            ("tests/integration/test_system2_orchestrator.py", "Orchestrator"),
            ("tests/integration/test_llm_adapter.py", "LLM Adapter"),
            ("tests/integration/test_schema_validation.py", "Schema Validation"),
        ]

        for test_path, test_name in legacy_tests:
            if Path(test_path).exists():
                success &= self.run_pytest_suite(
                    f"System 2 {test_name} Tests (Legacy)", test_path
                )

        return success

    def run_gui_tests(self) -> bool:
        """Run GUI tests."""
        args = ["smoke"]

        if self.verbose:
            args.append("--verbose")

        if self.fast:
            # Use smoke mode for fast testing
            args[0] = "smoke"
        else:
            # Use comprehensive mode for full testing
            args[0] = "comprehensive"

        return self.run_python_script(
            "GUI Tests", "tests/gui_comprehensive/main_test_runner.py", args=args
        )

    def run_comprehensive_tests(self) -> bool:
        """Run comprehensive test suites."""
        success = True

        # CLI comprehensive tests
        success &= self.run_python_script(
            "CLI Comprehensive Tests", "tests/comprehensive_test_suite.py"
        )

        # HCE pipeline comprehensive tests
        success &= self.run_python_script(
            "HCE Pipeline Comprehensive Tests", "test_comprehensive.py"
        )

        return success

    def run_all_tests(self) -> bool:
        """Run all test suites."""
        success = True

        print("\n" + "=" * 80)
        print("KNOWLEDGE CHIPPER SYSTEM 2 - COMPREHENSIVE TEST RUN")
        print("=" * 80)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Verbose: {self.verbose}")
        print(f"Coverage: {self.coverage}")
        print(f"Fast mode: {self.fast}")
        print(f"Parallel: {self.parallel}")
        print("=" * 80 + "\n")

        # Run test suites in order
        success &= self.run_unit_tests()
        success &= self.run_integration_tests()
        success &= self.run_system2_tests()
        success &= self.run_gui_tests()
        success &= self.run_comprehensive_tests()

        return success

    def generate_summary(self):
        """Generate and display test summary."""
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80 + "\n")

        total = len(self.results)
        passed = sum(1 for r in self.results.values() if r.get("success", False))
        failed = total - passed

        print(f"Total test suites: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Success rate: {(passed/total)*100:.1f}%\n")

        if failed > 0:
            print("Failed test suites:")
            for name, result in self.results.items():
                if not result.get("success", False):
                    error = result.get("error", "Unknown error")
                    return_code = result.get("return_code", "N/A")
                    print(f"  - {name}: {error} (exit code: {return_code})")

        print("\n" + "=" * 80)

        # Save summary to file
        summary_path = self.project_root / "tests" / "reports" / "test_summary.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)

        with open(summary_path, "w") as f:
            json.dump(
                {
                    "timestamp": datetime.now().isoformat(),
                    "total": total,
                    "passed": passed,
                    "failed": failed,
                    "success_rate": (passed / total) * 100,
                    "results": self.results,
                },
                f,
                indent=2,
            )

        print(f"\nDetailed results saved to: {summary_path}\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Unified test runner for Knowledge Chipper System 2"
    )

    parser.add_argument(
        "suite",
        choices=["all", "unit", "integration", "system2", "gui", "comprehensive"],
        help="Test suite to run",
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )

    parser.add_argument(
        "--coverage", "-c", action="store_true", help="Generate coverage report"
    )

    parser.add_argument("--fast", "-f", action="store_true", help="Skip slow tests")

    parser.add_argument(
        "--parallel", "-p", action="store_true", help="Run tests in parallel"
    )

    args = parser.parse_args()

    runner = TestRunner(
        verbose=args.verbose,
        coverage=args.coverage,
        fast=args.fast,
        parallel=args.parallel,
    )

    # Run appropriate test suite
    if args.suite == "all":
        success = runner.run_all_tests()
    elif args.suite == "unit":
        success = runner.run_unit_tests()
    elif args.suite == "integration":
        success = runner.run_integration_tests()
    elif args.suite == "system2":
        success = runner.run_system2_tests()
    elif args.suite == "gui":
        success = runner.run_gui_tests()
    elif args.suite == "comprehensive":
        success = runner.run_comprehensive_tests()
    else:
        print(f"Unknown test suite: {args.suite}")
        sys.exit(1)

    # Generate summary
    runner.generate_summary()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
