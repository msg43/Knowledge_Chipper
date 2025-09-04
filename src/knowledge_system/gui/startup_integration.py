"""
Startup Integration for Process Isolation and Crash Recovery

Handles integration of the process isolation system with the main application
startup sequence, including automatic crash detection and recovery dialog
presentation to users.

Features:
- Automatic checkpoint detection on startup
- Crash recovery dialog integration
- System requirements validation
- Configuration initialization
- Analytics system startup
"""

import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QMessageBox

from .dialogs.crash_recovery_dialog import CrashRecoveryManager
from ..config.process_isolation import ProcessIsolationConfig, validate_system_requirements
from ..utils.process_analytics import ProcessAnalytics
from ..utils.memory_monitor import MemoryMonitor
from ..logger import get_logger

logger = get_logger(__name__)


class StartupIntegration:
    """Manages process isolation startup integration."""
    
    def __init__(self, main_window=None):
        """
        Initialize startup integration.
        
        Args:
            main_window: Reference to main application window
        """
        self.main_window = main_window
        self.config = None
        self.analytics = None
        self.memory_monitor = None
        self.recovery_manager = None
        
        # Startup state
        self.initialization_complete = False
        self.recovery_handled = False
        
    def initialize_on_startup(self) -> bool:
        """
        Initialize process isolation system on application startup.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            logger.info("Initializing process isolation system...")
            
            # Step 1: Validate system requirements
            if not self._validate_system_requirements():
                return False
            
            # Step 2: Load configuration
            if not self._initialize_configuration():
                return False
            
            # Step 3: Initialize analytics
            if not self._initialize_analytics():
                return False
            
            # Step 4: Initialize memory monitoring
            if not self._initialize_memory_monitoring():
                return False
            
            # Step 5: Set up crash recovery
            if not self._initialize_crash_recovery():
                return False
            
            # Step 6: Check for existing checkpoints (delayed)
            QTimer.singleShot(2000, self._check_for_recovery_on_startup)
            
            self.initialization_complete = True
            logger.info("Process isolation system initialized successfully")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize process isolation system: {e}")
            self._show_initialization_error(str(e))
            return False
    
    def _validate_system_requirements(self) -> bool:
        """Validate system requirements for process isolation."""
        try:
            requirements = validate_system_requirements()
            
            if not requirements["meets_requirements"]:
                # Show warning dialog
                self._show_requirements_warning(requirements)
                
                # Still allow startup, but log warnings
                for issue in requirements["issues"]:
                    logger.warning(f"System requirement issue: {issue}")
                
                # Continue anyway - system will fall back to thread mode if needed
                return True
            
            # Log any warnings
            for warning in requirements.get("warnings", []):
                logger.warning(f"System warning: {warning}")
            
            return True
            
        except Exception as e:
            logger.error(f"System requirements validation failed: {e}")
            return True  # Continue anyway
    
    def _initialize_configuration(self) -> bool:
        """Initialize process isolation configuration."""
        try:
            self.config = ProcessIsolationConfig()
            
            # Validate configuration
            issues = self.config.validate_config()
            for issue in issues:
                logger.warning(f"Configuration issue: {issue}")
            
            # Log configuration status
            if self.config.is_enabled():
                logger.info("Process isolation enabled")
            else:
                logger.info("Process isolation disabled")
            
            if self.config.should_fallback_to_threads():
                logger.info("Will use thread-based fallback mode")
            
            return True
            
        except Exception as e:
            logger.error(f"Configuration initialization failed: {e}")
            return False
    
    def _initialize_analytics(self) -> bool:
        """Initialize process analytics system."""
        try:
            self.analytics = ProcessAnalytics()
            
            # Record startup event
            self.analytics.record_event(
                "startup",
                "info",
                "system",
                "Application started with process isolation",
                {"version": self._get_app_version()}
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Analytics initialization failed: {e}")
            return False
    
    def _initialize_memory_monitoring(self) -> bool:
        """Initialize memory monitoring system."""
        try:
            memory_limits = self.config.get_memory_limits()
            
            self.memory_monitor = MemoryMonitor(
                memory_threshold=memory_limits["pressure_threshold"],
                swap_threshold=memory_limits["swap_threshold"],
                growth_rate_threshold=memory_limits["growth_rate_threshold"]
            )
            
            # Start background monitoring if enabled
            if self.config.get("safety_features", "memory_monitoring_enabled", True):
                self.memory_monitor.start_monitoring()
            
            return True
            
        except Exception as e:
            logger.error(f"Memory monitoring initialization failed: {e}")
            return False
    
    def _initialize_crash_recovery(self) -> bool:
        """Initialize crash recovery system."""
        try:
            self.recovery_manager = CrashRecoveryManager(self.main_window)
            return True
            
        except Exception as e:
            logger.error(f"Crash recovery initialization failed: {e}")
            return False
    
    def _check_for_recovery_on_startup(self):
        """Check for recoverable checkpoints and show recovery dialog if needed."""
        try:
            if self.recovery_handled:
                return
            
            # Only check if crash recovery is enabled
            if not self.config.get("safety_features", "crash_detection_enabled", True):
                return
            
            # Check for recoverable checkpoints
            if self.recovery_manager.check_and_show_recovery_dialog():
                self.recovery_handled = True
                logger.info("Crash recovery dialog presented to user")
                
                # Record analytics event
                self.analytics.record_event(
                    "recovery_dialog_shown",
                    "info",
                    "crash_recovery",
                    "Recovery dialog shown on startup"
                )
            
        except Exception as e:
            logger.error(f"Failed to check for recovery on startup: {e}")
    
    def _show_requirements_warning(self, requirements: Dict[str, Any]):
        """Show system requirements warning dialog."""
        try:
            if not self.main_window:
                return
            
            issues = requirements.get("issues", [])
            warnings = requirements.get("warnings", [])
            
            message_parts = [
                "System Requirements Check:",
                ""
            ]
            
            if issues:
                message_parts.extend([
                    "Issues found:",
                    *[f"• {issue}" for issue in issues],
                    ""
                ])
            
            if warnings:
                message_parts.extend([
                    "Warnings:",
                    *[f"• {warning}" for warning in warnings],
                    ""
                ])
            
            message_parts.extend([
                "The application will continue to run, but some features may be limited.",
                "Consider upgrading your system for optimal performance."
            ])
            
            QMessageBox.warning(
                self.main_window,
                "System Requirements",
                "\n".join(message_parts)
            )
            
        except Exception as e:
            logger.error(f"Failed to show requirements warning: {e}")
    
    def _show_initialization_error(self, error_message: str):
        """Show initialization error dialog."""
        try:
            if not self.main_window:
                return
            
            message = (
                f"Failed to initialize process isolation system:\n\n"
                f"{error_message}\n\n"
                f"The application will continue in compatibility mode."
            )
            
            QMessageBox.critical(
                self.main_window,
                "Initialization Error",
                message
            )
            
        except Exception as e:
            logger.error(f"Failed to show initialization error: {e}")
    
    def _get_app_version(self) -> str:
        """Get application version string."""
        try:
            # Try to get version from package metadata
            import importlib.metadata
            return importlib.metadata.version("knowledge_chipper")
        except Exception:
            # Fallback to default version
            return "unknown"
    
    def shutdown(self):
        """Shutdown process isolation system components."""
        try:
            logger.info("Shutting down process isolation system...")
            
            # Stop memory monitoring
            if self.memory_monitor:
                self.memory_monitor.stop_monitoring()
            
            # Record shutdown event
            if self.analytics:
                self.analytics.record_event(
                    "shutdown",
                    "info",
                    "system",
                    "Application shutdown with process isolation"
                )
            
            # Clean up old analytics data (optional)
            if self.analytics and self.config:
                cleanup_days = self.config.get("checkpoint_system", "max_checkpoint_age_days", 7)
                self.analytics.cleanup_old_data(cleanup_days)
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status of process isolation system."""
        if not self.initialization_complete:
            return {
                "status": "initializing",
                "message": "System still initializing"
            }
        
        try:
            if self.analytics:
                return self.analytics.get_health_status()
            else:
                return {
                    "status": "unknown",
                    "message": "Analytics not available"
                }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Health check failed: {e}"
            }
    
    def generate_diagnostics_report(self) -> str:
        """Generate a diagnostics report for troubleshooting."""
        try:
            report_lines = [
                "=== Process Isolation Diagnostics Report ===",
                f"Generated: {QTimer().timestamp()}",
                "",
                "System Information:",
                f"  Platform: {sys.platform}",
                f"  Python Version: {sys.version}",
                f"  PyQt Version: {QApplication.instance().metaObject().className() if QApplication.instance() else 'N/A'}",
                "",
                "Initialization Status:",
                f"  Complete: {self.initialization_complete}",
                f"  Recovery Handled: {self.recovery_handled}",
                ""
            ]
            
            # Configuration status
            if self.config:
                debug_info = self.config.get_debug_info()
                report_lines.extend([
                    "Configuration:",
                    f"  Enabled: {debug_info.get('enabled', 'Unknown')}",
                    f"  Fallback Mode: {debug_info.get('fallback_mode', 'Unknown')}",
                    f"  Config File: {debug_info.get('config_file', 'None')}",
                    ""
                ])
                
                issues = debug_info.get("validation_issues", [])
                if issues:
                    report_lines.extend([
                        "Configuration Issues:",
                        *[f"  • {issue}" for issue in issues],
                        ""
                    ])
            
            # Health status
            health = self.get_health_status()
            report_lines.extend([
                "Health Status:",
                f"  Status: {health.get('status', 'Unknown')}",
                f"  Message: {health.get('message', 'N/A')}",
                ""
            ])
            
            # Analytics report
            if self.analytics:
                analytics_report = self.analytics.generate_report("text")
                report_lines.extend([
                    "Analytics Report:",
                    analytics_report,
                    ""
                ])
            
            return "\n".join(report_lines)
            
        except Exception as e:
            return f"Failed to generate diagnostics report: {e}"


# Global startup integration instance
_global_startup = None


def get_startup_integration(main_window=None) -> StartupIntegration:
    """Get the global startup integration instance."""
    global _global_startup
    if _global_startup is None:
        _global_startup = StartupIntegration(main_window)
    return _global_startup


def initialize_process_isolation_on_startup(main_window=None) -> bool:
    """
    Convenience function to initialize process isolation on application startup.
    
    Args:
        main_window: Reference to main application window
        
    Returns:
        True if initialization successful, False otherwise
    """
    startup = get_startup_integration(main_window)
    return startup.initialize_on_startup()


def shutdown_process_isolation():
    """Convenience function to shutdown process isolation system."""
    global _global_startup
    if _global_startup:
        _global_startup.shutdown()
        _global_startup = None
