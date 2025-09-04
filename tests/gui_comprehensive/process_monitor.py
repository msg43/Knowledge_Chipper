"""
Process monitoring utilities for comprehensive testing.

Provides robust process management, timeout handling, and cleanup capabilities
to prevent hanging tests and ensure proper resource management.
"""

import os
import time
import signal
import psutil
import subprocess
import threading
from typing import List, Optional, Callable, Dict, Any
from pathlib import Path

try:
    from knowledge_system.logger import get_logger
except ImportError:
    import logging
    def get_logger(name):
        return logging.getLogger(name)

logger = get_logger(__name__)


class ProcessMonitor:
    """
    Monitor and manage processes during testing to prevent hanging.
    
    Features:
    - Process heartbeat monitoring
    - Automatic timeout and cleanup
    - Graceful and force termination
    - Resource usage tracking
    """
    
    def __init__(self):
        self.monitored_processes: Dict[int, Dict[str, Any]] = {}
        self.monitoring_thread: Optional[threading.Thread] = None
        self.stop_monitoring = threading.Event()
        
    def start_monitoring(self) -> None:
        """Start background process monitoring."""
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            return
            
        self.stop_monitoring.clear()
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True
        )
        self.monitoring_thread.start()
        logger.info("Process monitoring started")
    
    def stop_monitoring_service(self) -> None:
        """Stop background process monitoring."""
        self.stop_monitoring.set()
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=5)
        logger.info("Process monitoring stopped")
    
    def register_process(self, process: subprocess.Popen, 
                        timeout: int = 300, 
                        name: str = None,
                        cleanup_callback: Callable = None,
                        command: str = None,
                        context: Dict[str, Any] = None) -> None:
        """
        Register a process for monitoring with enhanced diagnostics.
        
        Args:
            process: subprocess.Popen instance
            timeout: Maximum time to allow process to run
            name: Human-readable name for the process
            cleanup_callback: Optional callback for cleanup
            command: Command line used to start process
            context: Additional context for debugging
        """
        if not process or process.poll() is not None:
            return
        
        # Gather process information for diagnostics
        try:
            proc_info = psutil.Process(process.pid)
            cpu_percent = proc_info.cpu_percent()
            memory_info = proc_info.memory_info()
            cmdline = proc_info.cmdline()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            cpu_percent = 0
            memory_info = None
            cmdline = []
            
        self.monitored_processes[process.pid] = {
            'process': process,
            'start_time': time.time(),
            'timeout': timeout,
            'name': name or f"Process-{process.pid}",
            'cleanup_callback': cleanup_callback,
            'last_heartbeat': time.time(),
            'command': command or ' '.join(cmdline),
            'context': context or {},
            'initial_memory': memory_info.rss if memory_info else 0,
            'cpu_samples': [cpu_percent],
            'memory_samples': [memory_info.rss if memory_info else 0]
        }
        
        logger.info(f"Registered process for monitoring: {name} (PID: {process.pid}, timeout: {timeout}s)")
        logger.info(f"Process command: {command or ' '.join(cmdline)}")
        if context:
            logger.info(f"Process context: {context}")
    
    def unregister_process(self, process: subprocess.Popen) -> None:
        """Unregister a process from monitoring."""
        if process and process.pid in self.monitored_processes:
            name = self.monitored_processes[process.pid]['name']
            del self.monitored_processes[process.pid]
            logger.info(f"Unregistered process: {name} (PID: {process.pid})")
    
    def heartbeat(self, process: subprocess.Popen) -> None:
        """Update heartbeat for a monitored process."""
        if process and process.pid in self.monitored_processes:
            self.monitored_processes[process.pid]['last_heartbeat'] = time.time()
    
    def _monitoring_loop(self) -> None:
        """Main monitoring loop running in background thread."""
        while not self.stop_monitoring.is_set():
            try:
                self._check_processes()
                time.sleep(5)  # Check every 5 seconds
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(10)  # Wait longer on error
    
    def _check_processes(self) -> None:
        """Check all monitored processes for timeouts or issues with enhanced diagnostics."""
        current_time = time.time()
        processes_to_remove = []
        
        for pid, info in self.monitored_processes.items():
            process = info['process']
            
            # Check if process is still running
            if process.poll() is not None:
                elapsed = current_time - info['start_time']
                logger.info(f"Process {info['name']} (PID: {pid}) completed normally after {elapsed:.1f}s")
                self._log_process_summary(info, elapsed, "completed")
                processes_to_remove.append(pid)
                continue
            
            # Update resource usage samples
            self._update_process_metrics(info)
            
            # Check for timeout
            elapsed = current_time - info['start_time']
            if elapsed > info['timeout']:
                logger.warning(f"Process {info['name']} (PID: {pid}) timed out after {elapsed:.1f}s")
                self._log_process_summary(info, elapsed, "timeout")
                self._terminate_process(info)
                processes_to_remove.append(pid)
                continue
            
            # Check for heartbeat timeout (if no activity for 60 seconds)
            heartbeat_elapsed = current_time - info['last_heartbeat']
            if heartbeat_elapsed > 60:
                logger.warning(f"Process {info['name']} (PID: {pid}) heartbeat timeout ({heartbeat_elapsed:.1f}s)")
                self._log_process_summary(info, elapsed, "heartbeat_timeout")
                # Could add heartbeat timeout handling here
            
            # Log periodic status for long-running processes
            if elapsed > 120 and int(elapsed) % 30 == 0:  # Every 30s after 2 minutes
                self._log_process_status(info, elapsed)
        
        # Remove completed/terminated processes
        for pid in processes_to_remove:
            if pid in self.monitored_processes:
                del self.monitored_processes[pid]
    
    def _update_process_metrics(self, process_info: Dict[str, Any]) -> None:
        """Update CPU and memory metrics for a process."""
        try:
            proc = psutil.Process(process_info['process'].pid)
            cpu_percent = proc.cpu_percent()
            memory_info = proc.memory_info()
            
            # Keep last 10 samples
            process_info['cpu_samples'].append(cpu_percent)
            process_info['memory_samples'].append(memory_info.rss)
            
            if len(process_info['cpu_samples']) > 10:
                process_info['cpu_samples'].pop(0)
            if len(process_info['memory_samples']) > 10:
                process_info['memory_samples'].pop(0)
                
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    def _log_process_status(self, process_info: Dict[str, Any], elapsed: float) -> None:
        """Log periodic status for long-running processes."""
        try:
            cpu_avg = sum(process_info['cpu_samples']) / len(process_info['cpu_samples'])
            memory_current = process_info['memory_samples'][-1] / (1024 * 1024)  # MB
            memory_peak = max(process_info['memory_samples']) / (1024 * 1024)  # MB
            
            logger.info(f"Process {process_info['name']} status at {elapsed:.0f}s: "
                       f"CPU: {cpu_avg:.1f}%, Memory: {memory_current:.1f}MB (peak: {memory_peak:.1f}MB)")
        except (IndexError, ZeroDivisionError):
            pass
    
    def _log_process_summary(self, process_info: Dict[str, Any], elapsed: float, reason: str) -> None:
        """Log comprehensive summary when process ends."""
        try:
            if process_info['cpu_samples'] and process_info['memory_samples']:
                cpu_avg = sum(process_info['cpu_samples']) / len(process_info['cpu_samples'])
                cpu_max = max(process_info['cpu_samples'])
                memory_peak = max(process_info['memory_samples']) / (1024 * 1024)  # MB
                memory_initial = process_info['initial_memory'] / (1024 * 1024)  # MB
                
                logger.info(f"=== Process Summary: {process_info['name']} ({reason}) ===")
                logger.info(f"Runtime: {elapsed:.1f}s")
                logger.info(f"Command: {process_info['command']}")
                logger.info(f"CPU Usage: avg={cpu_avg:.1f}%, max={cpu_max:.1f}%")
                logger.info(f"Memory: initial={memory_initial:.1f}MB, peak={memory_peak:.1f}MB")
                if process_info['context']:
                    logger.info(f"Context: {process_info['context']}")
                logger.info(f"=== End Summary ===")
            else:
                logger.info(f"Process {process_info['name']} ended ({reason}) after {elapsed:.1f}s")
                logger.info(f"Command: {process_info['command']}")
                
        except Exception as e:
            logger.warning(f"Error logging process summary: {e}")
    
    def _terminate_process(self, process_info: Dict[str, Any]) -> None:
        """Terminate a process gracefully, then forcefully if needed."""
        process = process_info['process']
        name = process_info['name']
        cleanup_callback = process_info.get('cleanup_callback')
        
        try:
            logger.info(f"Terminating process: {name} (PID: {process.pid})")
            
            # Try graceful termination first
            process.terminate()
            
            # Wait up to 10 seconds for graceful shutdown
            try:
                process.wait(timeout=10)
                logger.info(f"Process {name} terminated gracefully")
            except subprocess.TimeoutExpired:
                # Force kill if graceful termination didn't work
                logger.warning(f"Force killing process: {name} (PID: {process.pid})")
                process.kill()
                process.wait()
            
            # Run cleanup callback if provided
            if cleanup_callback:
                try:
                    cleanup_callback()
                except Exception as e:
                    logger.error(f"Error in cleanup callback for {name}: {e}")
                    
        except Exception as e:
            logger.error(f"Error terminating process {name}: {e}")


class ProcessCleanup:
    """Utility for cleaning up stuck processes by name/pattern."""
    
    @staticmethod
    def kill_processes_by_name(process_names: List[str], 
                              exclude_pids: List[int] = None) -> List[int]:
        """
        Kill processes by name patterns.
        
        Args:
            process_names: List of process names or patterns to kill
            exclude_pids: PIDs to exclude from killing
            
        Returns:
            List of PIDs that were killed
        """
        exclude_pids = exclude_pids or []
        exclude_pids.append(os.getpid())  # Don't kill ourselves
        killed_pids = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['pid'] in exclude_pids:
                    continue
                
                proc_name = proc.info['name'].lower()
                cmdline = ' '.join(proc.info.get('cmdline', [])).lower()
                
                # Check if this process matches any of our patterns
                should_kill = False
                for pattern in process_names:
                    pattern = pattern.lower()
                    if pattern in proc_name or pattern in cmdline:
                        should_kill = True
                        break
                
                if should_kill:
                    logger.warning(f"Killing process: {proc.info['pid']} ({proc_name})")
                    try:
                        proc.terminate()
                        proc.wait(timeout=3)
                        killed_pids.append(proc.info['pid'])
                    except (psutil.TimeoutExpired, psutil.NoSuchProcess):
                        try:
                            proc.kill()
                            killed_pids.append(proc.info['pid'])
                        except psutil.NoSuchProcess:
                            pass
                        
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        if killed_pids:
            logger.info(f"Killed {len(killed_pids)} processes: {killed_pids}")
        
        return killed_pids
    
    @staticmethod
    def cleanup_knowledge_system_processes() -> None:
        """Clean up all Knowledge System related processes."""
        patterns = [
            'whisper', 'ffmpeg', 'sox', 'speech',
            'knowledge_system', 'transcribe'
        ]
        
        # Don't kill GUI or test processes
        exclude_patterns = ['gui', 'test', 'pytest']
        
        killed = ProcessCleanup.kill_processes_by_name(patterns)
        
        # Also clean up any Python processes running Knowledge System code
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['name'].lower() == 'python':
                    cmdline = ' '.join(proc.info.get('cmdline', [])).lower()
                    if ('knowledge' in cmdline or 'chipper' in cmdline):
                        # Check if it's not a GUI or test process
                        if not any(exclude in cmdline for exclude in exclude_patterns):
                            logger.warning(f"Killing Python Knowledge System process: {proc.info['pid']}")
                            try:
                                proc.terminate()
                                proc.wait(timeout=3)
                            except (psutil.TimeoutExpired, psutil.NoSuchProcess):
                                try:
                                    proc.kill()
                                except psutil.NoSuchProcess:
                                    pass
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue


# Global process monitor instance
_global_monitor: Optional[ProcessMonitor] = None

def get_global_monitor() -> ProcessMonitor:
    """Get the global process monitor instance."""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = ProcessMonitor()
        _global_monitor.start_monitoring()
    return _global_monitor

def cleanup_global_monitor() -> None:
    """Clean up the global process monitor."""
    global _global_monitor
    if _global_monitor:
        _global_monitor.stop_monitoring_service()
        _global_monitor = None
