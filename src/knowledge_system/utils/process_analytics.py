"""
Process Analytics and Monitoring

Provides comprehensive monitoring, analytics, and health tracking for the
process isolation system. Collects metrics on crashes, performance, and
resource usage to help optimize the system.

Features:
- Crash rate tracking
- Performance monitoring
- Resource usage analytics
- Health dashboard data
- Alert generation
"""

import json
import sqlite3
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import threading

import psutil

from ..logger import get_logger

logger = get_logger(__name__)


class ProcessMetrics:
    """Data class for process metrics."""
    
    def __init__(self):
        self.crash_rate = 0.0          # crashes per hour of processing
        self.recovery_success_rate = 0.0  # successful recoveries / total crashes
        self.average_processing_speed = 0.0  # files per hour
        self.memory_efficiency = 0.0    # output per GB-hour
        self.user_satisfaction_score = 0  # 1-10 based on feedback
        self.uptime_percentage = 0.0    # percentage of time system is healthy
        
        # Resource metrics
        self.peak_memory_usage_gb = 0.0
        self.average_cpu_usage = 0.0
        self.disk_io_rate = 0.0
        
        # Processing metrics
        self.total_files_processed = 0
        self.total_processing_time = 0.0
        self.average_file_size_mb = 0.0
        
        # Error metrics
        self.total_crashes = 0
        self.total_recoveries = 0
        self.error_categories = {}


class ProcessAnalytics:
    """Main analytics and monitoring system."""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize analytics system.
        
        Args:
            db_path: Path to SQLite database for persistent storage
        """
        if db_path:
            self.db_path = Path(db_path)
        else:
            self.db_path = Path.home() / ".cache" / "knowledge_chipper" / "analytics.db"
        
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # In-memory data structures
        self.metrics = ProcessMetrics()
        self.event_history = deque(maxlen=10000)  # Last 10k events
        self.performance_samples = deque(maxlen=1000)  # Last 1k performance samples
        self.resource_samples = deque(maxlen=1000)  # Last 1k resource samples
        
        # Aggregated data
        self.hourly_stats = defaultdict(dict)
        self.daily_stats = defaultdict(dict)
        
        # Threading
        self._lock = threading.RLock()
        self._monitoring = False
        self._monitor_thread = None
        
        # Initialize database
        self._init_database()
        self._load_historical_data()
        
        logger.info("Process analytics system initialized")
    
    def _init_database(self):
        """Initialize SQLite database schema."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp REAL NOT NULL,
                        event_type TEXT NOT NULL,
                        severity TEXT NOT NULL,
                        component TEXT,
                        message TEXT,
                        metadata TEXT,  -- JSON
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    
                    CREATE TABLE IF NOT EXISTS performance_samples (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp REAL NOT NULL,
                        processing_speed REAL,  -- files per hour
                        memory_usage_gb REAL,
                        cpu_usage_percent REAL,
                        disk_io_rate REAL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    
                    CREATE TABLE IF NOT EXISTS crash_reports (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp REAL NOT NULL,
                        crash_type TEXT NOT NULL,
                        error_message TEXT,
                        stack_trace TEXT,
                        system_state TEXT,  -- JSON
                        recovery_attempted BOOLEAN,
                        recovery_successful BOOLEAN,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    
                    CREATE TABLE IF NOT EXISTS processing_sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT UNIQUE NOT NULL,
                        start_time REAL NOT NULL,
                        end_time REAL,
                        total_files INTEGER,
                        completed_files INTEGER,
                        failed_files INTEGER,
                        total_size_mb REAL,
                        configuration TEXT,  -- JSON
                        success BOOLEAN,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    
                    CREATE TABLE IF NOT EXISTS user_feedback (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp REAL NOT NULL,
                        satisfaction_score INTEGER,
                        feedback_text TEXT,
                        feature_used TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    );
                    
                    -- Indexes for performance
                    CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
                    CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
                    CREATE INDEX IF NOT EXISTS idx_performance_timestamp ON performance_samples(timestamp);
                    CREATE INDEX IF NOT EXISTS idx_crashes_timestamp ON crash_reports(timestamp);
                    CREATE INDEX IF NOT EXISTS idx_sessions_start_time ON processing_sessions(start_time);
                """)
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
    
    def _load_historical_data(self):
        """Load recent historical data for analysis."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Load recent events (last 24 hours)
                cutoff_time = time.time() - 86400  # 24 hours ago
                
                cursor = conn.execute("""
                    SELECT timestamp, event_type, severity, component, message, metadata
                    FROM events 
                    WHERE timestamp > ? 
                    ORDER BY timestamp DESC
                    LIMIT 1000
                """, (cutoff_time,))
                
                for row in cursor:
                    timestamp, event_type, severity, component, message, metadata = row
                    try:
                        metadata_dict = json.loads(metadata) if metadata else {}
                    except json.JSONDecodeError:
                        metadata_dict = {}
                    
                    self.event_history.append({
                        "timestamp": timestamp,
                        "type": event_type,
                        "severity": severity,
                        "component": component,
                        "message": message,
                        "metadata": metadata_dict
                    })
                
                logger.info(f"Loaded {len(self.event_history)} recent events")
                
        except Exception as e:
            logger.error(f"Failed to load historical data: {e}")
    
    def record_event(self, event_type: str, severity: str, component: str = None, 
                    message: str = None, metadata: Dict[str, Any] = None):
        """Record an event for analytics."""
        timestamp = time.time()
        
        with self._lock:
            # Add to in-memory history
            event = {
                "timestamp": timestamp,
                "type": event_type,
                "severity": severity,
                "component": component,
                "message": message,
                "metadata": metadata or {}
            }
            self.event_history.append(event)
            
            # Store in database
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("""
                        INSERT INTO events (timestamp, event_type, severity, component, message, metadata)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (timestamp, event_type, severity, component, message, 
                         json.dumps(metadata) if metadata else None))
                    conn.commit()
                    
            except Exception as e:
                logger.error(f"Failed to store event: {e}")
    
    def record_crash(self, crash_type: str, error_message: str = None, 
                    stack_trace: str = None, recovery_attempted: bool = False,
                    recovery_successful: bool = False):
        """Record a crash event with detailed information."""
        timestamp = time.time()
        
        # Gather system state
        system_state = self._gather_system_state()
        
        with self._lock:
            self.metrics.total_crashes += 1
            if recovery_attempted and recovery_successful:
                self.metrics.total_recoveries += 1
            
            # Store in database
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("""
                        INSERT INTO crash_reports 
                        (timestamp, crash_type, error_message, stack_trace, system_state,
                         recovery_attempted, recovery_successful)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (timestamp, crash_type, error_message, stack_trace, 
                         json.dumps(system_state), recovery_attempted, recovery_successful))
                    conn.commit()
                    
            except Exception as e:
                logger.error(f"Failed to store crash report: {e}")
        
        # Record as event too
        self.record_event(
            "crash", 
            "error", 
            "process_isolation",
            f"{crash_type}: {error_message}",
            {
                "crash_type": crash_type,
                "recovery_attempted": recovery_attempted,
                "recovery_successful": recovery_successful
            }
        )
    
    def record_performance_sample(self, processing_speed: float = None, 
                                 memory_usage_gb: float = None,
                                 cpu_usage_percent: float = None,
                                 disk_io_rate: float = None):
        """Record a performance sample."""
        timestamp = time.time()
        
        with self._lock:
            sample = {
                "timestamp": timestamp,
                "processing_speed": processing_speed,
                "memory_usage_gb": memory_usage_gb,
                "cpu_usage_percent": cpu_usage_percent,
                "disk_io_rate": disk_io_rate
            }
            self.performance_samples.append(sample)
            
            # Store in database
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("""
                        INSERT INTO performance_samples 
                        (timestamp, processing_speed, memory_usage_gb, cpu_usage_percent, disk_io_rate)
                        VALUES (?, ?, ?, ?, ?)
                    """, (timestamp, processing_speed, memory_usage_gb, 
                         cpu_usage_percent, disk_io_rate))
                    conn.commit()
                    
            except Exception as e:
                logger.error(f"Failed to store performance sample: {e}")
    
    def start_processing_session(self, session_id: str, total_files: int, 
                               total_size_mb: float, configuration: Dict[str, Any]):
        """Start tracking a processing session."""
        timestamp = time.time()
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO processing_sessions 
                    (session_id, start_time, total_files, total_size_mb, configuration)
                    VALUES (?, ?, ?, ?, ?)
                """, (session_id, timestamp, total_files, total_size_mb, 
                     json.dumps(configuration)))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to start processing session: {e}")
        
        self.record_event("session_start", "info", "processing", 
                         f"Started session {session_id}", 
                         {"total_files": total_files, "total_size_mb": total_size_mb})
    
    def end_processing_session(self, session_id: str, completed_files: int, 
                             failed_files: int, success: bool):
        """End tracking a processing session."""
        timestamp = time.time()
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE processing_sessions 
                    SET end_time = ?, completed_files = ?, failed_files = ?, success = ?
                    WHERE session_id = ?
                """, (timestamp, completed_files, failed_files, success, session_id))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to end processing session: {e}")
        
        self.record_event("session_end", "info", "processing",
                         f"Ended session {session_id}",
                         {"completed_files": completed_files, "failed_files": failed_files, "success": success})
    
    def record_user_feedback(self, satisfaction_score: int, feedback_text: str = None,
                           feature_used: str = None):
        """Record user feedback."""
        timestamp = time.time()
        
        with self._lock:
            # Update running average
            if self.metrics.user_satisfaction_score == 0:
                self.metrics.user_satisfaction_score = satisfaction_score
            else:
                # Simple exponential moving average
                self.metrics.user_satisfaction_score = (
                    0.8 * self.metrics.user_satisfaction_score + 
                    0.2 * satisfaction_score
                )
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO user_feedback 
                    (timestamp, satisfaction_score, feedback_text, feature_used)
                    VALUES (?, ?, ?, ?)
                """, (timestamp, satisfaction_score, feedback_text, feature_used))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to store user feedback: {e}")
    
    def _gather_system_state(self) -> Dict[str, Any]:
        """Gather current system state for crash analysis."""
        try:
            return {
                "memory_percent": psutil.virtual_memory().percent,
                "cpu_percent": psutil.cpu_percent(),
                "disk_usage": psutil.disk_usage('/').percent if hasattr(psutil.disk_usage('/'), 'percent') else None,
                "process_count": len(psutil.pids()),
                "timestamp": time.time()
            }
        except Exception as e:
            logger.warning(f"Failed to gather system state: {e}")
            return {}
    
    def calculate_metrics(self) -> ProcessMetrics:
        """Calculate current metrics from collected data."""
        with self._lock:
            metrics = ProcessMetrics()
            
            # Calculate crash rate (crashes per hour of processing)
            recent_time = time.time() - 3600  # Last hour
            recent_crashes = sum(1 for event in self.event_history 
                               if event["timestamp"] > recent_time and event["type"] == "crash")
            
            processing_hours = self._get_processing_hours_last_period(3600)
            if processing_hours > 0:
                metrics.crash_rate = recent_crashes / processing_hours
            
            # Calculate recovery success rate
            if self.metrics.total_crashes > 0:
                metrics.recovery_success_rate = self.metrics.total_recoveries / self.metrics.total_crashes
            
            # Calculate processing speed (from recent performance samples)
            recent_speeds = [s["processing_speed"] for s in self.performance_samples 
                           if s["processing_speed"] is not None and s["timestamp"] > recent_time]
            if recent_speeds:
                metrics.average_processing_speed = sum(recent_speeds) / len(recent_speeds)
            
            # Calculate memory efficiency
            recent_memory = [s["memory_usage_gb"] for s in self.performance_samples 
                           if s["memory_usage_gb"] is not None and s["timestamp"] > recent_time]
            if recent_memory and metrics.average_processing_speed > 0:
                avg_memory = sum(recent_memory) / len(recent_memory)
                if avg_memory > 0:
                    metrics.memory_efficiency = metrics.average_processing_speed / avg_memory
            
            # Calculate uptime percentage
            total_events = len([e for e in self.event_history if e["timestamp"] > recent_time])
            error_events = len([e for e in self.event_history 
                              if e["timestamp"] > recent_time and e["severity"] in ["error", "critical"]])
            if total_events > 0:
                metrics.uptime_percentage = ((total_events - error_events) / total_events) * 100
            else:
                metrics.uptime_percentage = 100.0
            
            # Resource metrics
            if self.performance_samples:
                memory_values = [s["memory_usage_gb"] for s in self.performance_samples 
                               if s["memory_usage_gb"] is not None]
                cpu_values = [s["cpu_usage_percent"] for s in self.performance_samples 
                            if s["cpu_usage_percent"] is not None]
                
                if memory_values:
                    metrics.peak_memory_usage_gb = max(memory_values)
                if cpu_values:
                    metrics.average_cpu_usage = sum(cpu_values) / len(cpu_values)
            
            # Copy other metrics
            metrics.total_crashes = self.metrics.total_crashes
            metrics.total_recoveries = self.metrics.total_recoveries
            metrics.user_satisfaction_score = self.metrics.user_satisfaction_score
            
            return metrics
    
    def _get_processing_hours_last_period(self, seconds: int) -> float:
        """Get processing hours in the last period."""
        cutoff_time = time.time() - seconds
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT SUM(end_time - start_time) / 3600.0 as hours
                    FROM processing_sessions
                    WHERE start_time > ? AND end_time IS NOT NULL
                """, (cutoff_time,))
                
                result = cursor.fetchone()
                return result[0] if result[0] is not None else 0.0
                
        except Exception as e:
            logger.error(f"Failed to calculate processing hours: {e}")
            return 0.0
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get overall system health status."""
        metrics = self.calculate_metrics()
        
        health_score = 100.0
        issues = []
        
        # Check crash rate
        if metrics.crash_rate > 0.5:  # More than 0.5 crashes per hour
            health_score -= 20
            issues.append(f"High crash rate: {metrics.crash_rate:.2f} crashes/hour")
        
        # Check recovery rate
        if metrics.recovery_success_rate < 0.8:  # Less than 80% recovery
            health_score -= 15
            issues.append(f"Low recovery rate: {metrics.recovery_success_rate:.1%}")
        
        # Check processing speed
        if metrics.average_processing_speed < 1.0:  # Less than 1 file per hour
            health_score -= 10
            issues.append(f"Low processing speed: {metrics.average_processing_speed:.2f} files/hour")
        
        # Check memory efficiency
        if metrics.memory_efficiency < 0.5:  # Less than 0.5 files per GB-hour
            health_score -= 10
            issues.append(f"Low memory efficiency: {metrics.memory_efficiency:.2f}")
        
        # Check uptime
        if metrics.uptime_percentage < 95:
            health_score -= 15
            issues.append(f"Low uptime: {metrics.uptime_percentage:.1f}%")
        
        # Check user satisfaction
        if metrics.user_satisfaction_score < 7:
            health_score -= 10
            issues.append(f"Low user satisfaction: {metrics.user_satisfaction_score:.1f}/10")
        
        # Determine status
        if health_score >= 90:
            status = "excellent"
        elif health_score >= 75:
            status = "good"
        elif health_score >= 50:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "health_score": max(0, health_score),
            "issues": issues,
            "metrics": metrics.__dict__,
            "last_updated": time.time()
        }
    
    def get_trend_data(self, hours: int = 24) -> Dict[str, List]:
        """Get trend data for the specified time period."""
        cutoff_time = time.time() - (hours * 3600)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Performance trends
                cursor = conn.execute("""
                    SELECT timestamp, processing_speed, memory_usage_gb, cpu_usage_percent
                    FROM performance_samples
                    WHERE timestamp > ?
                    ORDER BY timestamp
                """, (cutoff_time,))
                
                performance_data = []
                for row in cursor:
                    timestamp, speed, memory, cpu = row
                    performance_data.append({
                        "timestamp": timestamp,
                        "processing_speed": speed,
                        "memory_usage_gb": memory,
                        "cpu_usage_percent": cpu
                    })
                
                # Error trends
                cursor = conn.execute("""
                    SELECT timestamp, event_type, severity
                    FROM events
                    WHERE timestamp > ? AND severity IN ('error', 'critical')
                    ORDER BY timestamp
                """, (cutoff_time,))
                
                error_data = []
                for row in cursor:
                    timestamp, event_type, severity = row
                    error_data.append({
                        "timestamp": timestamp,
                        "type": event_type,
                        "severity": severity
                    })
                
                return {
                    "performance": performance_data,
                    "errors": error_data,
                    "period_hours": hours
                }
                
        except Exception as e:
            logger.error(f"Failed to get trend data: {e}")
            return {"performance": [], "errors": [], "period_hours": hours}
    
    def generate_report(self, format: str = "text") -> str:
        """Generate a comprehensive analytics report."""
        health = self.get_health_status()
        metrics = health["metrics"]
        
        if format == "text":
            report_lines = [
                "=== Process Isolation Analytics Report ===",
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "",
                f"Overall Health: {health['status'].upper()} (Score: {health['health_score']:.1f}/100)",
                "",
                "Key Metrics:",
                f"  • Crash Rate: {metrics['crash_rate']:.2f} crashes/hour",
                f"  • Recovery Success Rate: {metrics['recovery_success_rate']:.1%}",
                f"  • Processing Speed: {metrics['average_processing_speed']:.2f} files/hour",
                f"  • Memory Efficiency: {metrics['memory_efficiency']:.2f} files/GB-hour",
                f"  • Uptime: {metrics['uptime_percentage']:.1f}%",
                f"  • User Satisfaction: {metrics['user_satisfaction_score']:.1f}/10",
                "",
                "Resource Usage:",
                f"  • Peak Memory: {metrics['peak_memory_usage_gb']:.1f} GB",
                f"  • Average CPU: {metrics['average_cpu_usage']:.1f}%",
                "",
                "Error Summary:",
                f"  • Total Crashes: {metrics['total_crashes']}",
                f"  • Successful Recoveries: {metrics['total_recoveries']}",
                ""
            ]
            
            if health["issues"]:
                report_lines.extend([
                    "Issues Identified:",
                    *[f"  • {issue}" for issue in health["issues"]],
                    ""
                ])
            
            return "\n".join(report_lines)
        
        elif format == "json":
            return json.dumps(health, indent=2)
        
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def cleanup_old_data(self, days: int = 30):
        """Clean up old analytics data."""
        cutoff_time = time.time() - (days * 86400)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Clean up old events
                result = conn.execute("DELETE FROM events WHERE timestamp < ?", (cutoff_time,))
                events_deleted = result.rowcount
                
                # Clean up old performance samples
                result = conn.execute("DELETE FROM performance_samples WHERE timestamp < ?", (cutoff_time,))
                samples_deleted = result.rowcount
                
                # Clean up old crash reports
                result = conn.execute("DELETE FROM crash_reports WHERE timestamp < ?", (cutoff_time,))
                crashes_deleted = result.rowcount
                
                conn.commit()
                
                logger.info(f"Cleaned up old data: {events_deleted} events, {samples_deleted} samples, {crashes_deleted} crashes")
                
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")


# Global analytics instance
_global_analytics = None


def get_process_analytics(db_path: Optional[str] = None) -> ProcessAnalytics:
    """Get the global process analytics instance."""
    global _global_analytics
    if _global_analytics is None:
        _global_analytics = ProcessAnalytics(db_path)
    return _global_analytics


def reset_global_analytics():
    """Reset the global analytics instance (for testing)."""
    global _global_analytics
    _global_analytics = None
