"""
Main test runner for comprehensive GUI testing.

Entry point for executing comprehensive GUI tests for the Knowledge Chipper application.
Supports different test modes and configurations.
"""

import argparse
import atexit
import signal
import sys
from pathlib import Path
from typing import Optional

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

# Handle imports for both module and direct execution
try:
    from .test_orchestrator import TestOrchestrator
except ImportError:
    from test_orchestrator import TestOrchestrator

try:
    from src.knowledge_system.logger import get_logger
except ImportError:
    import logging

    def get_logger(name):
        return logging.getLogger(name)


logger = get_logger(__name__)


def setup_signal_handlers():
    """Set up signal handlers to catch crashes and clean up properly."""

    def signal_handler(signum, frame):
        print(f"\n⚠️  Received signal {signum}, cleaning up...")

        # Try to clean up any running GUI processes
        try:
            import os

            import psutil

            current_pid = os.getpid()
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    if (
                        proc.info["pid"] != current_pid
                        and "knowledge" in proc.info["name"].lower()
                    ):
                        proc.terminate()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            print(f"Cleanup error: {e}")

        # Exit with appropriate code
        sys.exit(1 if signum == signal.SIGABRT else 0)

    # Handle common crash signals
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Termination
    if hasattr(signal, "SIGABRT"):
        signal.signal(signal.SIGABRT, signal_handler)  # Abort (Qt crashes)


def main():
    """Main entry point for GUI comprehensive testing."""
    setup_signal_handlers()

    parser = argparse.ArgumentParser(
        description="Comprehensive GUI testing for Knowledge Chipper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Test Modes:
  setup     - Generate test data files (run this first!)
  smoke     - Quick validation tests (5-10 minutes)
  basic     - Basic functionality tests (30 minutes)
  comprehensive - Full permutation testing (1-2 hours)
  stress    - Stress testing with large files (2+ hours)
  all       - Run all test suites sequentially

Examples:
  python -m tests.gui_comprehensive.main_test_runner setup
  python -m tests.gui_comprehensive.main_test_runner smoke
  python -m tests.gui_comprehensive.main_test_runner comprehensive --output ./test_results
  python -m tests.gui_comprehensive.main_test_runner smoke --no-gui-launch  # Use existing GUI
  python -m tests.gui_comprehensive.main_test_runner all --config comprehensive_config.yaml
        """,
    )

    parser.add_argument(
        "mode",
        choices=["smoke", "basic", "comprehensive", "stress", "all", "setup", "quick"],
        help="Test mode to run ('setup' generates test data, 'quick' runs with dry-run mode)",
    )

    parser.add_argument(
        "--test-data-dir",
        type=Path,
        default=Path(__file__).parent.parent / "fixtures",
        help="Directory containing test data (default: tests/fixtures)",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent.parent / "reports",
        help="Output directory for test results (default: tests/reports)",
    )

    parser.add_argument(
        "--config",
        type=str,
        help="Test configuration file name (in test_configs directory)",
    )

    parser.add_argument(
        "--timeout", type=int, help="Override default timeout per test (seconds)"
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be tested without running tests",
    )

    parser.add_argument(
        "--no-gui-launch",
        action="store_true",
        help="Don't launch GUI automatically (assume it's already running)",
    )

    parser.add_argument(
        "--gui-startup-timeout",
        type=int,
        default=30,
        help="Timeout for GUI startup in seconds (default: 30)",
    )

    args = parser.parse_args()

    # Configure logging level
    if args.verbose:
        import logging

        logging.getLogger().setLevel(logging.DEBUG)

    # Validate directories and offer to create test data if missing
    if not args.test_data_dir.exists():
        logger.error(f"Test data directory not found: {args.test_data_dir}")
        logger.info("You can generate test data by running:")
        logger.info(f"  cd {Path(__file__).parent}")
        logger.info("  ./setup_test_data.sh")
        sys.exit(1)

    # Check if sample files exist
    sample_files_dir = args.test_data_dir / "sample_files"
    if not sample_files_dir.exists() or not any(sample_files_dir.iterdir()):
        logger.warning("Sample files directory is empty or missing")
        logger.info("Generate test data by running:")
        logger.info(f"  cd {Path(__file__).parent}")
        logger.info("  ./setup_test_data.sh")
        logger.info("Continuing anyway - some tests may fail")

    # Create output directory if it doesn't exist
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize test orchestrator
    orchestrator = TestOrchestrator(
        args.test_data_dir,
        args.output_dir,
        auto_launch_gui=not args.no_gui_launch,
        gui_startup_timeout=args.gui_startup_timeout,
    )

    try:
        # Handle setup mode separately (doesn't need orchestrator)
        if args.mode == "setup":
            logger.info("Setting up test data files...")
            setup_script = Path(__file__).parent / "setup_test_data.sh"
            if setup_script.exists():
                logger.info("Running test data setup script...")
                import subprocess

                result = subprocess.run([str(setup_script)], cwd=Path(__file__).parent)
                if result.returncode == 0:
                    logger.info("Test data setup completed successfully")
                    logger.info("You can now run GUI tests with any of the test modes")
                else:
                    logger.error("Test data setup failed")
                    sys.exit(1)
            else:
                logger.error(f"Setup script not found: {setup_script}")
                sys.exit(1)
            return

        # For all other modes, proceed with normal testing setup
        logger.info(f"Starting GUI comprehensive testing - Mode: {args.mode}")
        logger.info(f"Test data directory: {args.test_data_dir}")
        logger.info(f"Output directory: {args.output_dir}")

        # Setup testing environment
        if not orchestrator.setup():
            logger.error("Failed to setup testing environment")
            sys.exit(1)

        # Run tests based on mode
        if args.mode == "smoke":
            results = orchestrator.run_smoke_tests()
            print_results_summary([results])

        elif args.mode == "basic":
            # Use basic config for faster testing
            results = orchestrator.run_comprehensive_tests()
            print_results_summary([results])

        elif args.mode == "comprehensive":
            results = orchestrator.run_comprehensive_tests()
            print_results_summary([results])

        elif args.mode == "stress":
            results = orchestrator.run_stress_tests()
            print_results_summary([results])

        elif args.mode == "quick":
            results = orchestrator.run_quick_tests()
            print_results_summary([results])

        elif args.mode == "all":
            results = orchestrator.run_all_tests()
            print_results_summary(results)

        logger.info("Testing completed successfully")

    except KeyboardInterrupt:
        logger.info("Testing interrupted by user")
        sys.exit(1)

    except Exception as e:
        logger.error(f"Testing failed with error: {e}")
        import traceback

        logger.error(traceback.format_exc())
        sys.exit(1)

    finally:
        # Clean up
        orchestrator.teardown()


def print_results_summary(results_list):
    """Print a summary of test results."""
    print("\n" + "=" * 60)
    print("COMPREHENSIVE GUI TEST RESULTS SUMMARY")
    print("=" * 60)

    total_suites = len(results_list)
    total_tests = sum(r.total_tests for r in results_list)
    total_passed = sum(r.passed_tests for r in results_list)
    total_failed = sum(r.failed_tests for r in results_list)

    overall_success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0

    print(f"Test Suites Run: {total_suites}")
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {total_passed}")
    print(f"Failed: {total_failed}")
    print(f"Overall Success Rate: {overall_success_rate:.1f}%")
    print()

    for result in results_list:
        print(f"Suite: {result.suite_name}")
        print(f"  Duration: {result.duration}")
        print(
            f"  Tests: {result.passed_tests}/{result.total_tests} passed ({result.success_rate:.1f}%)"
        )

        if result.failed_tests > 0:
            print(f"  ⚠️  {result.failed_tests} tests failed")
        else:
            print(f"  ✅ All tests passed!")
        print()

    print("=" * 60)

    if total_failed == 0:
        print("🎉 ALL TESTS PASSED! The GUI is working correctly.")
    else:
        print(
            f"⚠️  {total_failed} tests failed. Check the detailed reports for issues."
        )

    print("=" * 60)


if __name__ == "__main__":
    main()
