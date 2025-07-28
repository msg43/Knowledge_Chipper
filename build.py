#!/usr/bin/env python3
"""Build script for the Knowledge_Chipper package."""

import subprocess
import sys
import shutil
from pathlib import Path
import argparse


def run_command(command, description, check=True):
    """Run a command and handle errors."""
    print(f"🔨 {description}...")
    
    if isinstance(command, str):
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
    else:
        result = subprocess.run(command, capture_output=True, text=True)
    
    if check and result.returncode != 0:
        print(f"❌ {description} failed:")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        sys.exit(1)
    elif result.returncode != 0:
        print(f"⚠️  {description} had warnings:")
        print(f"STDERR: {result.stderr}")
    else:
        print(f"✅ {description} completed")
    
    return result


def check_prerequisites():
    """Check that required tools are available."""
    print("🔍 Checking prerequisites...")
    
    # Check if we're in the project root
    if not Path("pyproject.toml").exists():
        print("❌ pyproject.toml not found. Run from project root.")
        sys.exit(1)
    
    # Check Python version
    if sys.version_info < (3, 9):
        print("❌ Python 3.9+ required")
        sys.exit(1)
    
    print("✅ Prerequisites checked")


def clean_build():
    """Clean previous builds."""
    print("🧹 Cleaning previous builds...")
    
    dirs_to_clean = ["dist", "build", "*.egg-info"]
    for pattern in dirs_to_clean:
        for path in Path(".").glob(pattern):
            if path.is_dir():
                shutil.rmtree(path)
                print(f"   Removed {path}")
            elif path.is_file():
                path.unlink()
                print(f"   Removed {path}")
    
    print("✅ Clean completed")


def install_build_deps():
    """Install build dependencies."""
    build_deps = ["build", "twine", "pytest"]
    
    for dep in build_deps:
        run_command(
            [sys.executable, "-m", "pip", "install", dep],
            f"Installing {dep}"
        )


def run_tests(skip_slow=False):
    """Run installation tests."""
    test_cmd = [sys.executable, "-m", "pytest", "tests/test_installation.py", "-v"]
    
    if skip_slow:
        test_cmd.extend(["-m", "not slow"])
        
    run_command(test_cmd, "Running installation tests")


def build_package():
    """Build the package."""
    run_command(
        [sys.executable, "-m", "build"],
        "Building wheel and source distribution"
    )


def check_package():
    """Check the built package quality."""
    run_command(
        [sys.executable, "-m", "twine", "check", "dist/*"],
        "Checking package quality"
    )


def test_install():
    """Test installation of the built package."""
    print("🧪 Testing package installation...")
    
    # Find the wheel file
    wheel_files = list(Path("dist").glob("*.whl"))
    if not wheel_files:
        print("❌ No wheel file found in dist/")
        sys.exit(1)
    
    wheel_file = wheel_files[0]
    
    # Test installation in current environment
    result = run_command(
        [sys.executable, "-m", "pip", "install", "--force-reinstall", str(wheel_file)],
        "Installing wheel package",
        check=False
    )
    
    if result.returncode == 0:
        # Test entry points
        run_command(
            ["knowledge-system", "--version"],
            "Testing CLI entry point"
        )
        
        # Test GUI entry point (without actually launching)
        run_command(
            [sys.executable, "-c", "from knowledge_system.gui import main; print('GUI entry point OK')"],
            "Testing GUI entry point"
        )
        
        print("✅ Package installation test passed")
    else:
        print("❌ Package installation failed")
        return False
    
    return True


def show_results():
    """Show build results."""
    print("\n🎉 Build completed successfully!")
    print("📦 Files created:")
    
    dist_path = Path("dist")
    if dist_path.exists():
        for file in sorted(dist_path.glob("*")):
            size = file.stat().st_size / (1024 * 1024)  # MB
            print(f"   {file.name} ({size:.1f} MB)")
    
    print("\n📋 Next steps:")
    print("1. Test install: pip install dist/*.whl")
    print("2. Test entry points:")
    print("   - knowledge-system --help")
    print("   - knowledge-system-gui")
    print("   - ks --help")
    print("   - ks-gui")
    print("3. Upload to PyPI: python -m twine upload dist/*")


def main():
    """Main build process."""
    parser = argparse.ArgumentParser(description="Build Knowledge_Chipper package")
    parser.add_argument("--skip-tests", action="store_true", help="Skip running tests")
    parser.add_argument("--skip-slow-tests", action="store_true", help="Skip slow tests")
    parser.add_argument("--test-only", action="store_true", help="Only run tests")
    parser.add_argument("--clean-only", action="store_true", help="Only clean build artifacts")
    
    args = parser.parse_args()
    
    print("🚀 Building Knowledge_Chipper package...")
    
    check_prerequisites()
    
    if args.clean_only:
        clean_build()
        return
    
    if args.test_only:
        if not args.skip_tests:
            install_build_deps()
            run_tests(skip_slow=args.skip_slow_tests)
        return
    
    # Full build process
    clean_build()
    install_build_deps()
    
    if not args.skip_tests:
        run_tests(skip_slow=args.skip_slow_tests)
    
    build_package()
    check_package()
    
    # Test the built package
    if test_install():
        show_results()
    else:
        print("❌ Build completed but package installation test failed")
        sys.exit(1)


if __name__ == "__main__":
    main() 