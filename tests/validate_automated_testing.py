#!/usr/bin/env python3
"""
Validation script to verify automated testing system is properly installed.

Checks:
- Required files exist
- Scripts are executable
- Dependencies are installed
- Environment can run tests
"""

import subprocess
import sys
from pathlib import Path


def print_header(text: str) -> None:
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def print_check(name: str, passed: bool, details: str = "") -> bool:
    """Print a check result."""
    status = "✅" if passed else "❌"
    print(f"{status} {name}")
    if details:
        print(f"   {details}")
    return passed


def main() -> int:
    """Run validation checks."""
    project_root = Path(__file__).parent.parent
    all_passed = True
    
    print_header("Automated Testing System Validation")
    print(f"\nProject root: {project_root}\n")
    
    # Check 1: Required files exist
    print_header("File Existence Checks")
    
    required_files = [
        "test_gui_auto.sh",
        "tests/run_comprehensive_automated_tests.sh",
        "tests/gui_comprehensive/test_all_workflows_automated.py",
        "tests/tools/bug_detector.py",
        "tests/tools/coverage_analyzer.py",
        ".github/workflows/automated-gui-tests.yml",
        "AUTOMATED_TESTING_QUICKSTART.md",
        "AUTOMATED_TESTING_SUMMARY.md",
        "docs/AUTOMATED_TESTING_GUIDE.md",
    ]
    
    for file_path in required_files:
        full_path = project_root / file_path
        all_passed &= print_check(
            f"File: {file_path}",
            full_path.exists(),
            f"Path: {full_path}"
        )
    
    # Check 2: Scripts are executable
    print_header("Script Permissions Checks")
    
    executable_files = [
        "test_gui_auto.sh",
        "tests/run_comprehensive_automated_tests.sh",
        "tests/tools/bug_detector.py",
        "tests/tools/coverage_analyzer.py",
    ]
    
    for file_path in executable_files:
        full_path = project_root / file_path
        is_executable = full_path.exists() and (full_path.stat().st_mode & 0o111)
        all_passed &= print_check(
            f"Executable: {file_path}",
            is_executable,
            "chmod +x needed" if not is_executable else "Ready"
        )
    
    # Check 3: Python dependencies
    print_header("Python Dependencies Checks")
    
    dependencies = [
        ("pytest", "pytest"),
        ("PyQt6", "PyQt6.QtCore"),
        ("pytest-asyncio", "pytest_asyncio"),
        ("pytest-timeout", "pytest_timeout"),
    ]
    
    for dep_name, import_name in dependencies:
        try:
            __import__(import_name)
            all_passed &= print_check(f"Package: {dep_name}", True, "Installed")
        except ImportError:
            all_passed &= print_check(
                f"Package: {dep_name}",
                False,
                "Run: pip install pytest pytest-asyncio pytest-timeout"
            )
    
    # Check 4: Test directories
    print_header("Directory Structure Checks")
    
    required_dirs = [
        "tests/gui_comprehensive",
        "tests/tools",
        "tests/fixtures",
        ".github/workflows",
        "docs",
    ]
    
    for dir_path in required_dirs:
        full_path = project_root / dir_path
        all_passed &= print_check(
            f"Directory: {dir_path}",
            full_path.is_dir(),
            f"Path: {full_path}"
        )
    
    # Check 5: Can import knowledge_system
    print_header("Knowledge System Import Check")
    
    try:
        sys.path.insert(0, str(project_root / "src"))
        import knowledge_system
        version = getattr(knowledge_system, "__version__", "unknown")
        all_passed &= print_check(
            "Import knowledge_system",
            True,
            f"Version: {version}"
        )
    except ImportError as e:
        all_passed &= print_check(
            "Import knowledge_system",
            False,
            f"Error: {e}"
        )
    
    # Check 6: Virtual environment
    print_header("Virtual Environment Check")
    
    venv_python = project_root / "venv" / "bin" / "python3"
    if venv_python.exists():
        try:
            result = subprocess.run(
                [str(venv_python), "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            all_passed &= print_check(
                "Virtual environment",
                result.returncode == 0,
                result.stdout.strip()
            )
        except Exception as e:
            all_passed &= print_check(
                "Virtual environment",
                False,
                f"Error: {e}"
            )
    else:
        all_passed &= print_check(
            "Virtual environment",
            False,
            "Run: python3 -m venv venv"
        )
    
    # Final summary
    print_header("Validation Summary")
    
    if all_passed:
        print("\n✅ All checks passed!")
        print("\nThe automated testing system is ready to use.")
        print("\nQuick start:")
        print("  ./test_gui_auto.sh")
        print("\nOr run comprehensive tests:")
        print("  ./tests/run_comprehensive_automated_tests.sh")
        print("\nFor more information:")
        print("  cat AUTOMATED_TESTING_QUICKSTART.md")
        return 0
    else:
        print("\n❌ Some checks failed!")
        print("\nPlease fix the issues above and run this script again.")
        print("\nFor help, see:")
        print("  AUTOMATED_TESTING_QUICKSTART.md")
        print("  docs/AUTOMATED_TESTING_GUIDE.md")
        return 1


if __name__ == "__main__":
    sys.exit(main())

