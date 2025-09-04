"""
OAuth Callback Server

Handles OAuth callbacks from GetReceipts by running a local HTTP server
on localhost:8080 to receive authentication tokens.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, Optional, Any
from urllib.parse import urlparse, parse_qs

from ..logger import get_logger

logger = get_logger(__name__)


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OAuth callbacks."""
    
    def __init__(self, server_instance: 'OAuthCallbackServer', *args, **kwargs):
        self.server_instance = server_instance
        super().__init__(*args, **kwargs)
    
    def do_GET(self) -> None:
        """Handle GET request from OAuth callback."""
        try:
            # Parse the callback URL
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)
            
            # Extract tokens from query parameters
            access_token = query_params.get('access_token', [None])[0]
            refresh_token = query_params.get('refresh_token', [None])[0]
            user_id = query_params.get('user_id', [None])[0]
            
            if access_token and refresh_token and user_id:
                # Success - store tokens
                self.server_instance.tokens = {
                    'access_token': access_token,
                    'refresh_token': refresh_token,
                    'user_id': user_id
                }
                self.server_instance.callback_received = True
                
                # Send success response
                self._send_success_response()
                logger.info("OAuth callback received successfully")
                
            elif 'error' in query_params:
                # Error from OAuth provider
                error = query_params.get('error', ['unknown'])[0]
                error_description = query_params.get('error_description', [''])[0]
                
                self.server_instance.error = f"{error}: {error_description}"
                self.server_instance.callback_received = True
                
                # Send error response
                self._send_error_response(error, error_description)
                logger.error(f"OAuth callback error: {error} - {error_description}")
                
            else:
                # Invalid callback - missing required parameters
                self.server_instance.error = "Invalid callback - missing required parameters"
                self.server_instance.callback_received = True
                
                # Send error response
                self._send_error_response("invalid_request", "Missing required parameters")
                logger.error("OAuth callback missing required parameters")
        
        except Exception as e:
            logger.error(f"Error handling OAuth callback: {e}")
            self.server_instance.error = f"Callback processing error: {str(e)}"
            self.server_instance.callback_received = True
            self._send_error_response("processing_error", str(e))
    
    def _send_success_response(self) -> None:
        """Send success response to browser."""
        html_response = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Authentication Successful</title>
            <style>
                body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                .success { color: #4CAF50; font-size: 24px; margin-bottom: 20px; }
                .message { color: #666; font-size: 16px; }
            </style>
        </head>
        <body>
            <div class="success">✅ Authentication Successful!</div>
            <div class="message">
                You have successfully signed in to Knowledge_Chipper.<br/>
                You can now close this browser window and return to the application.
            </div>
            <script>
                // Auto-close after 3 seconds
                setTimeout(function() {
                    window.close();
                }, 3000);
            </script>
        </body>
        </html>
        """
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.send_header('Content-Length', str(len(html_response)))
        self.end_headers()
        self.wfile.write(html_response.encode('utf-8'))
    
    def _send_error_response(self, error: str, description: str) -> None:
        """Send error response to browser."""
        html_response = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Authentication Error</title>
            <style>
                body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
                .error {{ color: #F44336; font-size: 24px; margin-bottom: 20px; }}
                .message {{ color: #666; font-size: 16px; }}
            </style>
        </head>
        <body>
            <div class="error">❌ Authentication Error</div>
            <div class="message">
                <strong>Error:</strong> {error}<br/>
                <strong>Description:</strong> {description}<br/><br/>
                Please close this window and try again in the Knowledge_Chipper application.
            </div>
        </body>
        </html>
        """
        
        self.send_response(400)
        self.send_header('Content-type', 'text/html')
        self.send_header('Content-Length', str(len(html_response)))
        self.end_headers()
        self.wfile.write(html_response.encode('utf-8'))
    
    def log_message(self, format: str, *args) -> None:
        """Override to reduce HTTP server logging noise."""
        # Only log errors and important messages
        if "error" in format.lower():
            logger.error(f"OAuth callback server: {format % args}")


class OAuthCallbackServer:
    """Local HTTP server to handle OAuth callbacks."""
    
    def __init__(self, host: str = "localhost", port: int = 8080):
        self.host = host
        self.port = port
        self.server: Optional[HTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        
        # Callback results
        self.callback_received = False
        self.tokens: Optional[Dict[str, str]] = None
        self.error: Optional[str] = None
    
    def start(self) -> bool:
        """Start the callback server."""
        try:
            # Create handler class with server instance
            def handler_factory(*args, **kwargs):
                return OAuthCallbackHandler(self, *args, **kwargs)
            
            # Create and start server
            self.server = HTTPServer((self.host, self.port), handler_factory)
            
            # Start server in separate thread
            self.server_thread = threading.Thread(
                target=self.server.serve_forever,
                daemon=True
            )
            self.server_thread.start()
            
            logger.info(f"OAuth callback server started on {self.host}:{self.port}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start OAuth callback server: {e}")
            return False
    
    def stop(self) -> None:
        """Stop the callback server."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            logger.info("OAuth callback server stopped")
        
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=1.0)
    
    def wait_for_callback(self, timeout: float = 300.0) -> Optional[Dict[str, str]]:
        """
        Wait for OAuth callback with timeout.
        
        Args:
            timeout: Maximum time to wait in seconds (default: 5 minutes)
            
        Returns:
            Dictionary with tokens if successful, None if timeout or error
        """
        start_time = time.time()
        
        while not self.callback_received and (time.time() - start_time) < timeout:
            time.sleep(0.1)  # Check every 100ms
        
        # Stop the server
        self.stop()
        
        if self.error:
            logger.error(f"OAuth callback error: {self.error}")
            return None
        
        if self.tokens:
            logger.info("OAuth callback completed successfully")
            return self.tokens
        
        logger.warning("OAuth callback timed out")
        return None
    
    def get_callback_url(self) -> str:
        """Get the full callback URL for this server."""
        return f"http://{self.host}:{self.port}/auth/callback"
    
    def is_running(self) -> bool:
        """Check if the server is currently running."""
        return self.server is not None and self.server_thread is not None and self.server_thread.is_alive()


# Convenience function for easy use
def start_oauth_callback_server(timeout: float = 300.0) -> Optional[Dict[str, str]]:
    """
    Start OAuth callback server and wait for tokens.
    
    Args:
        timeout: Maximum time to wait in seconds
        
    Returns:
        Dictionary with tokens if successful, None otherwise
    """
    server = OAuthCallbackServer()
    
    if not server.start():
        return None
    
    try:
        return server.wait_for_callback(timeout)
    finally:
        server.stop()
