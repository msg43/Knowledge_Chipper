"""
GetReceipts.org OAuth Authentication Module for Knowledge_Chipper

This module handles the OAuth authentication flow with GetReceipts.org,
allowing Knowledge_Chipper users to securely authenticate and upload data.

Usage:
    from getreceipts_auth import GetReceiptsAuth

    auth = GetReceiptsAuth()
    auth_result = auth.authenticate()
    print(f"Authenticated as: {auth_result['user_info']['name']}")

Author: GetReceipts.org Team
License: MIT
"""

import json
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

import requests


class GetReceiptsAuth:
    """
    Handles OAuth authentication with GetReceipts.org

    This class manages the complete OAuth flow:
    1. Opens browser to GetReceipts.org OAuth page
    2. Starts local callback server
    3. Captures authentication response
    4. Extracts access tokens and user info
    """

    def __init__(self, base_url: str = "http://localhost:3000"):
        """
        Initialize the OAuth handler

        Args:
            base_url: Base URL of GetReceipts.org (default: development server)
        """
        self.base_url = base_url
        self.callback_port = 8080
        self.access_token = None
        self.user_info = None
        self.auth_server = None
        self._cancelled = False

    def authenticate(self) -> dict[str, Any]:
        """
        Start the OAuth authentication flow

        This method:
        1. Starts a local callback server
        2. Opens browser to GetReceipts.org OAuth page
        3. Waits for user to complete authentication
        4. Captures and returns authentication result

        Returns:
            Dict containing access_token and user_info

        Raises:
            Exception: If authentication fails or times out
        """
        print("🔐 Starting authentication with GetReceipts.org...")

        # Start callback server in background thread first
        auth_result = {}
        server_thread = threading.Thread(
            target=self._start_callback_server, args=(auth_result,)
        )
        server_thread.daemon = True
        server_thread.start()

        # Give the server a moment to start and potentially choose an alternative port
        time.sleep(0.5)

        # Build callback URL with the actual port being used
        callback_url = f"http://localhost:{self.callback_port}/auth/callback"
        oauth_url = f"{self.base_url}/auth/signin"

        # Build OAuth URL with Knowledge_Chipper parameters
        full_oauth_url = (
            f"{oauth_url}?redirect_to=knowledge_chipper&return_url={callback_url}"
        )

        print(f"🌐 Opening browser to: {full_oauth_url}")

        # Open browser to OAuth page
        webbrowser.open(full_oauth_url)

        # Wait for callback with timeout
        print("⏳ Waiting for authentication... (complete sign-in in browser)")
        timeout = 300  # 5 minutes
        start_time = time.time()

        while (
            not auth_result
            and (time.time() - start_time) < timeout
            and not self._cancelled
        ):
            time.sleep(1)

        # Check results
        if self._cancelled:
            raise Exception("Authentication cancelled by user")

        if not auth_result:
            raise Exception("Authentication timeout - please try again")

        if "error" in auth_result:
            raise Exception(f"Authentication failed: {auth_result['error']}")

        # Store authentication data
        self.access_token = auth_result.get("access_token")
        self.user_info = {
            "id": auth_result.get("user_id"),
            "email": auth_result.get("user_email"),
            "name": auth_result.get("user_name"),
        }

        print(f"✅ Authentication successful! Welcome, {self.user_info['name']}")
        return {"access_token": self.access_token, "user_info": self.user_info}

    def _start_callback_server(self, result_dict: dict):
        """
        Start HTTP server to handle OAuth callback

        This internal method starts a simple HTTP server that listens for
        the OAuth callback from GetReceipts.org and extracts the tokens.

        Args:
            result_dict: Shared dictionary to store authentication results
        """

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                # Parse the callback URL
                parsed_url = urlparse(self.path)
                query_params = parse_qs(parsed_url.query)

                if parsed_url.path == "/auth/callback":
                    # Extract OAuth response parameters
                    if "access_token" in query_params:
                        # Success case
                        result_dict.update(
                            {
                                "access_token": query_params["access_token"][0],
                                "user_id": query_params.get("user_id", [""])[0],
                                "user_email": query_params.get("user_email", [""])[0],
                                "user_name": query_params.get("user_name", [""])[0],
                            }
                        )

                        # Send success response to browser
                        self.send_response(200)
                        self.send_header("Content-type", "text/html")
                        self.end_headers()
                        html_content = """
                        <html>
                        <head>
                            <title>Authentication Successful</title>
                            <style>
                                body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                                .success { color: #4CAF50; }
                                .container { max-width: 500px; margin: 0 auto; }
                            </style>
                        </head>
                        <body>
                            <div class="container">
                                <h1 class="success">✅ Authentication Successful!</h1>
                                <p>You have successfully authenticated with GetReceipts.org.</p>
                                <p><strong>You can now close this window and return to Knowledge_Chipper.</strong></p>
                                <script>
                                    setTimeout(() => window.close(), 2000);
                                </script>
                            </div>
                        </body>
                        </html>
                        """
                        self.wfile.write(html_content.encode("utf-8"))
                    elif "error" in query_params:
                        # Error case
                        error_msg = query_params.get(
                            "error_description",
                            query_params.get("error", ["Unknown error"]),
                        )[0]
                        result_dict["error"] = error_msg

                        self.send_response(400)
                        self.send_header("Content-type", "text/html")
                        self.end_headers()
                        error_html = f"""
                        <html>
                        <head><title>Authentication Failed</title></head>
                        <body>
                            <h1>❌ Authentication Failed</h1>
                            <p>Error: {error_msg}</p>
                            <p>Please close this window and try again.</p>
                        </body>
                        </html>
                        """
                        self.wfile.write(error_html.encode("utf-8"))
                else:
                    # Unknown path
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, format, *args):
                # Suppress server access logs
                pass

        # Start the callback server
        try:
            # Try to bind to the callback port, if it fails try alternative ports
            ports_to_try = [self.callback_port, 8081, 8082, 8083, 8084]
            server = None

            for port in ports_to_try:
                try:
                    server = HTTPServer(("localhost", port), CallbackHandler)
                    print(f"🌐 Callback server started on port {port}")
                    self.callback_port = port  # Update the port we're actually using
                    break
                except OSError as e:
                    if "Address already in use" in str(e) and port != ports_to_try[-1]:
                        print(f"⚠️  Port {port} in use, trying next port...")
                        continue
                    else:
                        raise e

            if not server:
                raise Exception("Could not bind to any available port")

            server.timeout = 1

            # Handle requests until we get a result
            while not result_dict:
                server.handle_request()

            server.server_close()
            print(f"🔐 Callback server on port {self.callback_port} closed")
        except Exception as e:
            result_dict["error"] = f"Callback server error: {str(e)}"

    def is_authenticated(self) -> bool:
        """
        Check if user is currently authenticated

        Returns:
            True if user has valid access token and user info
        """
        return bool(self.access_token and self.user_info)

    def get_auth_headers(self) -> dict[str, str]:
        """
        Get authorization headers for API requests

        Returns:
            Dictionary with Authorization header for Supabase requests

        Raises:
            Exception: If not authenticated
        """
        if not self.access_token:
            raise Exception("Not authenticated - call authenticate() first")

        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def get_user_info(self) -> dict[str, str] | None:
        """
        Get authenticated user information

        Returns:
            Dictionary with user id, email, and name, or None if not authenticated
        """
        return self.user_info if self.is_authenticated() else None

    def cancel_authentication(self):
        """
        Cancel ongoing authentication process

        This method sets a flag that will cause the authentication
        loop to exit gracefully.
        """
        print("🚫 Cancelling OAuth authentication...")
        self._cancelled = True


# Example usage
if __name__ == "__main__":
    # Simple test of the authentication flow
    auth = GetReceiptsAuth()

    try:
        result = auth.authenticate()
        print(f"Success! User: {result['user_info']}")
        print(f"Headers: {auth.get_auth_headers()}")
    except Exception as e:
        print(f"Authentication failed: {e}")
