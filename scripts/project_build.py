#!/usr/bin/env python3
"""Project build wrapper (renamed from top-level build.py to avoid module shadowing).

This script orchestrates building the package, running lightweight tests, and
optionally performing install smoke tests. It deliberately invokes the real
PyPA build module via `python -m build` so the dist is produced from
pyproject.toml. The top-level file was renamed to prevent `python -m build`
from importing our script instead of the PyPA package.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


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
    print("🔍 Checking prerequisites...")
    if not Path("pyproject.toml").exists():
        print("❌ pyproject.toml not found. Run from project root.")
        sys.exit(1)
    if sys.version_info < (3, 9):
        print("❌ Python 3.9+ required")
        sys.exit(1)
    print("✅ Prerequisites checked")


def clean_build():
    print("🧹 Cleaning previous builds...")
    for pattern in ("dist", "build", "*.egg-info"):
        for path in Path(".").glob(pattern):
            if path.is_dir():
                shutil.rmtree(path)
                print(f"   Removed {path}")
            elif path.is_file():
                path.unlink()
                print(f"   Removed {path}")
    print("✅ Clean completed")


def install_build_deps():
    build_deps = ["build", "twine", "pytest"]
    if os.getenv("CI", "").lower() in {"1", "true", "yes"}:
        print("ℹ️  CI detected: skipping build-deps install (workflow provides them)")
        return
    for dep in build_deps:
        run_command([sys.executable, "-m", "pip", "install", dep], f"Installing {dep}")


def run_tests(skip_slow=False):
    cmd = [sys.executable, "-m", "pytest", "tests/test_basic.py", "-v"]
    if skip_slow:
        cmd.extend(["-m", "not slow"])
    run_command(cmd, "Running installation tests")


def build_package():
    # Avoid `python -m build` to prevent shadowing by any local build.py files.
    # Build a wheel using pip directly (PEP 517) without build isolation.
    run_command(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-build-isolation",
            "--no-deps",
            "-w",
            "dist",
            ".",
        ],
        "Building wheel (pip wheel)",
    )


def check_package():
    # Use twine to validate metadata of built distributions.
    # Since we use pip wheel, ensure sdist is optional. Only check if files exist.
    dist = Path("dist")
    if not dist.exists():
        print("⚠️  dist/ not found; skipping twine check")
        return
    run_command([sys.executable, "-m", "twine", "check", "dist/*"], "Checking package quality")


def test_install():
    print("🧪 Testing package installation...")
    wheel_files = list(Path("dist").glob("*.whl"))
    if not wheel_files:
        print("❌ No wheel file found in dist/")
        sys.exit(1)
    wheel_file = wheel_files[0]
    result = run_command(
        [sys.executable, "-m", "pip", "install", "--force-reinstall", str(wheel_file)],
        "Installing wheel package",
        check=False,
    )
    if result.returncode == 0:
        run_command(["knowledge-system", "--version"], "Testing CLI entry point")
        run_command(
            [sys.executable, "-c", "from knowledge_system.gui import main; print('GUI OK')"],
            "Testing GUI entry point",
        )
        print("✅ Package installation test passed")
    else:
        print("❌ Package installation failed")
        return False
    return True


def show_results():
    print("\n🎉 Build completed successfully!")
    print("📦 Files created:")
    dist = Path("dist")
    if dist.exists():
        for f in sorted(dist.glob("*")):
            print(f"   {f.name} ({f.stat().st_size / (1024*1024):.1f} MB)")


def main():
    parser = argparse.ArgumentParser(description="Project build wrapper")
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--skip-slow-tests", action="store_true")
    parser.add_argument("--test-only", action="store_true")
    parser.add_argument("--clean-only", action="store_true")
    parser.add_argument("--skip-install-test", action="store_true")
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

    clean_build()
    install_build_deps()
    if not args.skip_tests:
        run_tests(skip_slow=args.skip_slow_tests)
    build_package()
    check_package()

    skip_install = args.skip_install_test or os.getenv("CI", "").lower() in {"1", "true", "yes"}
    if skip_install:
        show_results()
        return
    if test_install():
        show_results()
    else:
        print("❌ Build completed but package installation test failed")
        sys.exit(1)


if __name__ == "__main__":
    main()


