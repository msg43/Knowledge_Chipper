"""
Phase 3 Installer Tests

Tests for the macOS installer components:
1. PyInstaller spec is valid
2. LaunchAgent plist is valid XML
3. Install script has correct structure

Note: Actual build tests require PyInstaller and are slow.
These tests validate the configuration files.
"""

import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree

import pytest

# Get paths
project_root = Path(__file__).parent.parent.parent
installer_dir = project_root / "installer"


class TestPyInstallerSpec:
    """Tests for daemon.spec PyInstaller configuration."""

    def test_spec_file_exists(self):
        """PyInstaller spec file exists."""
        spec_file = installer_dir / "daemon.spec"
        assert spec_file.exists(), f"Spec file not found: {spec_file}"

    def test_spec_file_has_analysis(self):
        """Spec file contains Analysis block."""
        spec_file = installer_dir / "daemon.spec"
        content = spec_file.read_text()
        assert "Analysis(" in content, "Spec must have Analysis block"

    def test_spec_file_has_exe(self):
        """Spec file contains EXE block."""
        spec_file = installer_dir / "daemon.spec"
        content = spec_file.read_text()
        assert "EXE(" in content, "Spec must have EXE block"

    def test_spec_file_references_daemon_main(self):
        """Spec file references daemon/main.py."""
        spec_file = installer_dir / "daemon.spec"
        content = spec_file.read_text()
        assert "daemon/main.py" in content or "../daemon/main.py" in content


class TestLaunchAgentPlist:
    """Tests for org.getreceipts.daemon.plist."""

    def test_plist_file_exists(self):
        """LaunchAgent plist file exists."""
        plist_file = installer_dir / "org.getreceipts.daemon.plist"
        assert plist_file.exists(), f"Plist file not found: {plist_file}"

    def test_plist_is_valid_xml(self):
        """Plist file is valid XML."""
        plist_file = installer_dir / "org.getreceipts.daemon.plist"
        try:
            ElementTree.parse(plist_file)
        except ElementTree.ParseError as e:
            pytest.fail(f"Plist is not valid XML: {e}")

    def test_plist_has_label(self):
        """Plist has Label key."""
        plist_file = installer_dir / "org.getreceipts.daemon.plist"
        content = plist_file.read_text()
        assert "<key>Label</key>" in content, "Plist must have Label key"
        assert "org.getreceipts.daemon" in content, "Label must be org.getreceipts.daemon"

    def test_plist_has_run_at_load(self):
        """Plist has RunAtLoad key."""
        plist_file = installer_dir / "org.getreceipts.daemon.plist"
        content = plist_file.read_text()
        assert "<key>RunAtLoad</key>" in content, "Plist must have RunAtLoad"

    def test_plist_plutil_validates(self):
        """Plist passes plutil validation (macOS only)."""
        plist_file = installer_dir / "org.getreceipts.daemon.plist"
        
        try:
            result = subprocess.run(
                ["plutil", "-lint", str(plist_file)],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, f"plutil validation failed: {result.stderr}"
        except FileNotFoundError:
            pytest.skip("plutil not available (not macOS)")


class TestInstallScript:
    """Tests for install.sh script."""

    def test_install_script_exists(self):
        """Install script exists."""
        script_file = installer_dir / "install.sh"
        assert script_file.exists(), f"Install script not found: {script_file}"

    def test_install_script_is_executable(self):
        """Install script has execute permission."""
        script_file = installer_dir / "install.sh"
        assert script_file.stat().st_mode & 0o111, "Install script must be executable"

    def test_install_script_has_shebang(self):
        """Install script has bash shebang."""
        script_file = installer_dir / "install.sh"
        content = script_file.read_text()
        assert content.startswith("#!/bin/bash"), "Script must start with #!/bin/bash"

    def test_install_script_has_uninstall_option(self):
        """Install script supports --uninstall."""
        script_file = installer_dir / "install.sh"
        content = script_file.read_text()
        assert "--uninstall" in content, "Script must support --uninstall"

    def test_install_script_creates_webloc(self):
        """Install script creates .webloc shortcut."""
        script_file = installer_dir / "install.sh"
        content = script_file.read_text()
        assert ".webloc" in content, "Script must create .webloc shortcut"
        assert "getreceipts.org/contribute" in content, "Shortcut must point to /contribute"


class TestBuildDmgScript:
    """Tests for build_dmg.sh script."""

    def test_build_script_exists(self):
        """Build DMG script exists."""
        script_file = installer_dir / "build_dmg.sh"
        assert script_file.exists(), f"Build script not found: {script_file}"

    def test_build_script_is_executable(self):
        """Build script has execute permission."""
        script_file = installer_dir / "build_dmg.sh"
        assert script_file.stat().st_mode & 0o111, "Build script must be executable"

    def test_build_script_uses_pyinstaller(self):
        """Build script calls PyInstaller."""
        script_file = installer_dir / "build_dmg.sh"
        content = script_file.read_text()
        assert "pyinstaller" in content.lower(), "Script must use pyinstaller"

