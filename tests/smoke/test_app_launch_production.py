#!/usr/bin/env python3
"""
Smoke Test: App Launch in Production Mode

This test would have caught Bug #1: App wouldn't launch due to FFmpeg PATH issue.

What it tests:
- App can be imported without TESTING_MODE bypass
- Preflight checks run successfully
- GUI components initialize without crashing
- Session manager functions correctly

Why it's important:
- Most tests run with TESTING_MODE=1 which bypasses critical initialization
- Preflight checks only run in production mode
- Session management only tested in production mode
- This is what users actually experience

Runtime: ~15 seconds

Note: This test uses QT_QPA_PLATFORM=offscreen for headless environments.
"""

import os
import sys
import pytest


@pytest.mark.smoke
@pytest.mark.production
class TestAppLaunchProduction:
    """Test app can launch in production mode (no TESTING_MODE)."""

    def test_can_import_gui_module_without_testing_mode(self):
        """Verify GUI module can be imported in production mode."""
        # Save original testing mode
        original_testing_mode = os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE")

        try:
            # Remove TESTING_MODE to simulate production
            if "KNOWLEDGE_CHIPPER_TESTING_MODE" in os.environ:
                del os.environ["KNOWLEDGE_CHIPPER_TESTING_MODE"]

            # Set offscreen platform for headless testing
            os.environ["QT_QPA_PLATFORM"] = "offscreen"

            # This import triggers preflight checks in production mode
            from knowledge_system.gui import main_window_pyqt6

            # If we get here, preflight checks passed
            assert True, "GUI module imported successfully"

        finally:
            # Restore testing mode
            if original_testing_mode is not None:
                os.environ["KNOWLEDGE_CHIPPER_TESTING_MODE"] = original_testing_mode

    def test_preflight_checks_run_on_import(self):
        """Verify preflight checks actually run when importing GUI."""
        original_testing_mode = os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE")

        try:
            # Remove TESTING_MODE
            if "KNOWLEDGE_CHIPPER_TESTING_MODE" in os.environ:
                del os.environ["KNOWLEDGE_CHIPPER_TESTING_MODE"]

            # Import preflight module
            from knowledge_system.utils import preflight

            # Verify preflight functions are callable
            assert hasattr(preflight, 'check_ffmpeg'), "check_ffmpeg should exist"
            assert hasattr(preflight, 'check_yt_dlp'), "check_yt_dlp should exist"
            assert hasattr(preflight, 'quick_preflight'), "quick_preflight should exist"

            # Run preflight checks (should not raise)
            preflight.quick_preflight()

        finally:
            if original_testing_mode is not None:
                os.environ["KNOWLEDGE_CHIPPER_TESTING_MODE"] = original_testing_mode

    def test_session_manager_has_required_methods(self):
        """Verify SessionManager has all required methods (would have caught Bug #3)."""
        from knowledge_system.gui.core.session_manager import SessionManager

        manager = SessionManager()

        # These methods were missing and caused the session loading bug
        assert hasattr(manager, 'get_window_geometry'), \
            "SessionManager must have get_window_geometry method"
        assert hasattr(manager, 'set_window_geometry'), \
            "SessionManager must have set_window_geometry method"

        # Test that methods are callable
        result = manager.get_window_geometry()
        # Should return None (no saved geometry) or a dict
        assert result is None or isinstance(result, dict), \
            "get_window_geometry should return None or dict"

        # Test set_window_geometry doesn't crash
        manager.set_window_geometry(x=100, y=100, width=800, height=600)

    def test_main_window_class_exists_and_is_importable(self):
        """Verify MainWindow class can be imported."""
        original_testing_mode = os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE")

        try:
            # Set offscreen platform
            os.environ["QT_QPA_PLATFORM"] = "offscreen"

            # Remove TESTING_MODE
            if "KNOWLEDGE_CHIPPER_TESTING_MODE" in os.environ:
                del os.environ["KNOWLEDGE_CHIPPER_TESTING_MODE"]

            from knowledge_system.gui.main_window_pyqt6 import MainWindow

            # Verify class exists
            assert MainWindow is not None, "MainWindow class should exist"
            assert hasattr(MainWindow, '__init__'), "MainWindow should have __init__"

        finally:
            if original_testing_mode is not None:
                os.environ["KNOWLEDGE_CHIPPER_TESTING_MODE"] = original_testing_mode

    def test_gui_settings_manager_integration(self):
        """Test that GUISettingsManager works with SessionManager."""
        from knowledge_system.gui.core.session_manager import SessionManager
        from knowledge_system.gui.core.gui_settings_manager import GUISettingsManager

        session_manager = SessionManager()
        settings_manager = GUISettingsManager(session_manager)

        # Test window geometry methods exist and work
        geometry = settings_manager.get_window_geometry()
        assert geometry is None or isinstance(geometry, dict)

        # Test set doesn't crash
        settings_manager.set_window_geometry(x=100, y=100, width=800, height=600)

        # Verify it was saved
        saved_geometry = settings_manager.get_window_geometry()
        assert saved_geometry is not None, "Geometry should be saved"
        assert saved_geometry['x'] == 100
        assert saved_geometry['y'] == 100
        assert saved_geometry['width'] == 800
        assert saved_geometry['height'] == 600

    @pytest.mark.skipif(
        os.environ.get("CI") == "true",
        reason="Skip actual GUI instantiation in CI environments"
    )
    def test_main_window_can_be_instantiated(self):
        """Test that MainWindow can actually be created (may fail in headless)."""
        original_testing_mode = os.environ.get("KNOWLEDGE_CHIPPER_TESTING_MODE")

        try:
            # Set offscreen platform for headless testing
            os.environ["QT_QPA_PLATFORM"] = "offscreen"

            # Remove TESTING_MODE to simulate production
            if "KNOWLEDGE_CHIPPER_TESTING_MODE" in os.environ:
                del os.environ["KNOWLEDGE_CHIPPER_TESTING_MODE"]

            from PyQt6.QtWidgets import QApplication
            from knowledge_system.gui.main_window_pyqt6 import MainWindow

            # Create QApplication if not exists
            app = QApplication.instance()
            if app is None:
                app = QApplication(sys.argv)

            # Try to create window (this is where preflight runs)
            try:
                window = MainWindow()

                # Verify window was created
                assert window is not None, "Window should be created"

                # Cleanup
                window.close()
                window.deleteLater()

            except Exception as e:
                # If it fails, check if it's due to preflight or something else
                if "FFmpeg" in str(e) or "preflight" in str(e).lower():
                    pytest.fail(f"Preflight check failed: {e}")
                elif "no screens available" in str(e).lower():
                    pytest.skip("Headless environment - can't create actual GUI")
                else:
                    raise

        finally:
            if original_testing_mode is not None:
                os.environ["KNOWLEDGE_CHIPPER_TESTING_MODE"] = original_testing_mode
