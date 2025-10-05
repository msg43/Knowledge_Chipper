#!/usr/bin/env python3
"""
Test runner for System 2 tests.

Run all System 2 tests with coverage reporting.
"""

import subprocess
import sys
from pathlib import Path


def run_tests():
    """Run all System 2 tests with pytest."""
    # Get the project root
    project_root = Path(__file__).parent.parent.parent

    # Test command
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/system2/",
        "-v",  # Verbose output
        "--cov=src.knowledge_system.core.system2_orchestrator",
        "--cov=src.knowledge_system.core.llm_adapter",
        "--cov=src.knowledge_system.database.system2_models",
        "--cov=src.knowledge_system.processors.hce.schema_validator",
        "--cov=src.knowledge_system.logger_system2",
        "--cov-report=term-missing",
        "--cov-report=html:coverage_system2",
        "-x",  # Stop on first failure
    ]

    # Run from project root
    result = subprocess.run(cmd, cwd=project_root)

    return result.returncode


if __name__ == "__main__":
    sys.exit(run_tests())
