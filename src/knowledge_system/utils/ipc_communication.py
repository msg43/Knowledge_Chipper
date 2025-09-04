"""
Inter-Process Communication (IPC) Module

Handles communication between the main GUI process and standalone worker processes.
Uses JSON messages over stdout/stderr for robust cross-platform communication.

Message Types:
- PROGRESS: Real-time progress updates
- FILE_COMPLETE: Single file completion notification
- ERROR: Error messages and exceptions
- INFO: General information messages
- WARNING: Warning messages
- FINISHED: Final results and completion

Thread Safety:
All methods are thread-safe for use in multi-threaded environments.
"""

import json
import sys
import time
import threading
from typing import Any, Dict, Optional
from datetime import datetime


class IPCCommunicator:
    """Handles JSON-based IPC communication between processes."""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._sequence_number = 0
    
    def _get_next_sequence(self) -> int:
        """Get next sequence number for message ordering."""
        with self._lock:
            self._sequence_number += 1
            return self._sequence_number
    
    def _send_message(self, message_data: Dict[str, Any]):
        """Send a JSON message to stdout with proper formatting."""
        with self._lock:
            try:
                # Add metadata
                message_data.update({
                    "timestamp": datetime.now().isoformat(),
                    "sequence": self._get_next_sequence(),
                    "pid": sys.platform != "win32" and hasattr(sys, "getpid") and sys.getpid() or 0
                })
                
                # Serialize and send
                message_json = json.dumps(message_data, ensure_ascii=False)
                print(message_json, file=sys.stdout, flush=True)
                
            except Exception as e:
                # Fallback error reporting
                fallback_message = {
                    "type": "ERROR",
                    "message": f"IPC serialization error: {str(e)}",
                    "timestamp": datetime.now().isoformat(),
                    "sequence": self._sequence_number
                }
                try:
                    print(json.dumps(fallback_message), file=sys.stdout, flush=True)
                except:
                    # Last resort - raw text
                    print(f"FATAL_IPC_ERROR: {str(e)}", file=sys.stderr, flush=True)
    
    def send_progress(
        self, 
        current_file: int, 
        total_files: int, 
        stage: str, 
        message: str, 
        progress: Optional[int] = None
    ):
        """Send progress update message."""
        self._send_message({
            "type": "PROGRESS",
            "current_file": current_file,
            "total_files": total_files,
            "stage": stage,
            "message": message,
            "progress_percent": progress,
            "overall_progress": round((current_file - 1) / max(1, total_files) * 100, 1)
        })
    
    def send_file_completed(self, file_path: str, success: bool, message: str):
        """Send file completion notification."""
        self._send_message({
            "type": "FILE_COMPLETE",
            "file_path": file_path,
            "success": success,
            "message": message
        })
    
    def send_error(self, error_message: str, error_code: Optional[str] = None):
        """Send error message."""
        self._send_message({
            "type": "ERROR",
            "message": error_message,
            "error_code": error_code
        })
    
    def send_message(self, level: str, message: str):
        """Send general message (info, warning, etc.)."""
        self._send_message({
            "type": level.upper(),
            "message": message
        })
    
    def send_finished(self, results: Dict[str, Any]):
        """Send final completion message with results."""
        self._send_message({
            "type": "FINISHED",
            "results": results
        })
    
    def send_heartbeat(self, status: str = "alive"):
        """Send heartbeat message to indicate process is alive."""
        self._send_message({
            "type": "HEARTBEAT",
            "status": status
        })


class IPCMessageParser:
    """Parses incoming IPC messages from worker processes."""
    
    def __init__(self):
        self.message_handlers = {}
    
    def register_handler(self, message_type: str, handler_func):
        """Register a handler function for a specific message type."""
        self.message_handlers[message_type] = handler_func
    
    def parse_message(self, message_line: str) -> Optional[Dict[str, Any]]:
        """Parse a single JSON message line."""
        try:
            message_data = json.loads(message_line.strip())
            
            # Validate required fields
            if not isinstance(message_data, dict) or "type" not in message_data:
                return None
            
            return message_data
            
        except json.JSONDecodeError:
            return None
        except Exception:
            return None
    
    def handle_message(self, message_data: Dict[str, Any]):
        """Route message to appropriate handler."""
        message_type = message_data.get("type")
        handler = self.message_handlers.get(message_type)
        
        if handler:
            try:
                handler(message_data)
            except Exception as e:
                # Log handler errors but don't crash
                print(f"Handler error for {message_type}: {e}", file=sys.stderr)
        else:
            # Unknown message type - log but continue
            print(f"Unknown message type: {message_type}", file=sys.stderr)
    
    def process_line(self, line: str):
        """Process a single line of input."""
        message = self.parse_message(line)
        if message:
            self.handle_message(message)


class HeartbeatMonitor:
    """Monitors heartbeat messages from worker processes."""
    
    def __init__(self, timeout_seconds: int = 60):
        self.timeout_seconds = timeout_seconds
        self.last_heartbeat = time.time()
        self._lock = threading.Lock()
        self._monitoring = False
        self._monitor_thread = None
    
    def update_heartbeat(self):
        """Update the last heartbeat timestamp."""
        with self._lock:
            self.last_heartbeat = time.time()
    
    def is_alive(self) -> bool:
        """Check if the process is considered alive based on heartbeat."""
        with self._lock:
            return (time.time() - self.last_heartbeat) < self.timeout_seconds
    
    def start_monitoring(self, timeout_callback=None):
        """Start monitoring heartbeat in a separate thread."""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(timeout_callback,),
            daemon=True
        )
        self._monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop heartbeat monitoring."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1)
    
    def _monitor_loop(self, timeout_callback):
        """Monitor loop that runs in a separate thread."""
        while self._monitoring:
            if not self.is_alive() and timeout_callback:
                timeout_callback()
                break
            time.sleep(5)  # Check every 5 seconds


class ProcessCommunicationManager:
    """High-level manager for process communication."""
    
    def __init__(self):
        self.parser = IPCMessageParser()
        self.heartbeat_monitor = HeartbeatMonitor()
        self.message_buffer = []
        self._callbacks = {}
    
    def register_progress_callback(self, callback):
        """Register callback for progress messages."""
        self._callbacks["progress"] = callback
        self.parser.register_handler("PROGRESS", self._handle_progress)
    
    def register_file_complete_callback(self, callback):
        """Register callback for file completion messages."""
        self._callbacks["file_complete"] = callback
        self.parser.register_handler("FILE_COMPLETE", self._handle_file_complete)
    
    def register_error_callback(self, callback):
        """Register callback for error messages."""
        self._callbacks["error"] = callback
        self.parser.register_handler("ERROR", self._handle_error)
    
    def register_finished_callback(self, callback):
        """Register callback for completion messages."""
        self._callbacks["finished"] = callback
        self.parser.register_handler("FINISHED", self._handle_finished)
    
    def register_message_callback(self, callback):
        """Register callback for general messages."""
        self._callbacks["message"] = callback
        self.parser.register_handler("INFO", self._handle_message)
        self.parser.register_handler("WARNING", self._handle_message)
    
    def _handle_progress(self, message_data):
        """Handle progress messages."""
        callback = self._callbacks.get("progress")
        if callback:
            callback(
                message_data.get("current_file", 0),
                message_data.get("total_files", 0),
                message_data.get("message", ""),
                message_data.get("progress_percent"),
                message_data.get("stage", "unknown")
            )
    
    def _handle_file_complete(self, message_data):
        """Handle file completion messages."""
        callback = self._callbacks.get("file_complete")
        if callback:
            callback(
                message_data.get("file_path", ""),
                message_data.get("success", False),
                message_data.get("message", "")
            )
    
    def _handle_error(self, message_data):
        """Handle error messages."""
        callback = self._callbacks.get("error")
        if callback:
            callback(message_data.get("message", "Unknown error"))
    
    def _handle_finished(self, message_data):
        """Handle completion messages."""
        callback = self._callbacks.get("finished")
        if callback:
            callback(message_data.get("results", {}))
    
    def _handle_message(self, message_data):
        """Handle general messages."""
        callback = self._callbacks.get("message")
        if callback:
            callback(
                message_data.get("type", "INFO"),
                message_data.get("message", "")
            )
    
    def process_output_line(self, line: str):
        """Process a line of output from the worker process."""
        # Update heartbeat for any valid message
        message = self.parser.parse_message(line)
        if message:
            self.heartbeat_monitor.update_heartbeat()
        
        # Process the message
        self.parser.process_line(line)
    
    def start_heartbeat_monitoring(self, timeout_callback=None):
        """Start monitoring worker process heartbeat."""
        self.heartbeat_monitor.start_monitoring(timeout_callback)
    
    def stop_heartbeat_monitoring(self):
        """Stop heartbeat monitoring."""
        self.heartbeat_monitor.stop_monitoring()


# Utility functions for common IPC operations

def safe_json_encode(data: Any) -> str:
    """Safely encode data to JSON with Unicode handling."""
    try:
        return json.dumps(data, ensure_ascii=False, default=str)
    except Exception:
        # Fallback for non-serializable objects
        return json.dumps({"error": "serialization_failed", "type": str(type(data))})


def sanitize_error_message(error_msg: str) -> str:
    """Sanitize error messages for safe transmission."""
    # Remove potential control characters and limit length
    sanitized = "".join(char for char in error_msg if ord(char) >= 32 or char in '\n\t')
    return sanitized[:1000]  # Limit to 1000 characters


def chunk_large_data(data: Dict[str, Any], max_size: int = 64 * 1024) -> List[Dict[str, Any]]:
    """Split large data into chunks for transmission."""
    serialized = safe_json_encode(data)
    
    if len(serialized) <= max_size:
        return [data]
    
    # Split into chunks
    chunks = []
    chunk_id = int(time.time() * 1000)  # Unique chunk session ID
    
    for i in range(0, len(serialized), max_size):
        chunk = {
            "type": "DATA_CHUNK",
            "chunk_id": chunk_id,
            "chunk_index": i // max_size,
            "chunk_data": serialized[i:i + max_size],
            "is_final": i + max_size >= len(serialized)
        }
        chunks.append(chunk)
    
    return chunks
