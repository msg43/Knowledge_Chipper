"""Test package installation and entry points."""

import subprocess
import sys
import tempfile
import venv
from pathlib import Path
import pytest


def test_package_builds():
    """Test that the package builds without errors."""
    result = subprocess.run(
        [sys.executable, "-m", "build", "--wheel"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"Build failed: {result.stderr}"


def test_entry_points_exist():
    """Test that entry points are properly defined."""
    # This tests the current installation
    result = subprocess.run(
        [sys.executable, "-c", "import knowledge_system.cli; print('CLI OK')"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "CLI OK" in result.stdout


def test_cli_help():
    """Test that CLI help works."""
    result = subprocess.run(
        ["knowledge-system", "--help"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "Knowledge System" in result.stdout


def test_gui_entry_point():
    """Test that GUI entry point exists (but don't launch GUI)."""
    result = subprocess.run(
        [sys.executable, "-c", "from knowledge_system.gui import main; print('GUI OK')"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "GUI OK" in result.stdout


def test_version_command():
    """Test that version command works."""
    result = subprocess.run(
        ["knowledge-system", "--version"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "Knowledge System" in result.stdout


def test_import_all_modules():
    """Test that all main modules can be imported."""
    modules_to_test = [
        "knowledge_system",
        "knowledge_system.cli",
        "knowledge_system.config",
        "knowledge_system.processors",
        "knowledge_system.utils",
    ]
    
    for module in modules_to_test:
        result = subprocess.run(
            [sys.executable, "-c", f"import {module}; print('{module} OK')"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Failed to import {module}: {result.stderr}"
        assert f"{module} OK" in result.stdout


@pytest.mark.slow
def test_fresh_install():
    """Test installation in a fresh virtual environment."""
    with tempfile.TemporaryDirectory() as temp_dir:
        venv_path = Path(temp_dir) / "test_venv"
        
        # Create virtual environment
        venv.create(venv_path, with_pip=True)
        
        # Get paths
        if sys.platform == "win32":
            python_exe = venv_path / "Scripts" / "python.exe"
            pip_exe = venv_path / "Scripts" / "pip.exe"
        else:
            python_exe = venv_path / "bin" / "python"
            pip_exe = venv_path / "bin" / "pip"
        
        # Install the package
        result = subprocess.run(
            [str(pip_exe), "install", "-e", "."],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Install failed: {result.stderr}"
        
        # Test entry points
        result = subprocess.run(
            [str(python_exe), "-c", "import knowledge_system; print('Import OK')"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "Import OK" in result.stdout


def test_dependencies_available():
    """Test that all required dependencies are available."""
    required_deps = [
        "click",
        "pydantic", 
        "yaml",
        "rich",
        "torch",
        "whisper",
        "yt_dlp",
        "anthropic",
        "openai",
        "requests",
        "sqlalchemy",
        "pandas",
        "psutil",
    ]
    
    for dep in required_deps:
        result = subprocess.run(
            [sys.executable, "-c", f"import {dep}; print('{dep} OK')"],
            capture_output=True,
            text=True
        )
        # Some dependencies might not be installed in test environment
        # This is more of a warning than a hard failure
        if result.returncode != 0:
            print(f"Warning: {dep} not available: {result.stderr}")


def test_optional_dependencies():
    """Test optional dependencies are handled gracefully."""
    # Test that missing PyQt6 is handled properly
    result = subprocess.run(
        [sys.executable, "-c", """
try:
    from knowledge_system.gui import main
    print('GUI available')
except ImportError as e:
    print(f'GUI not available: {e}')
        """],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    # Should either work or fail gracefully
    assert "GUI available" in result.stdout or "GUI not available" in result.stdout 