"""
Knowledge_Chipper Daemon

FastAPI-based REST API daemon that exposes local processing capabilities
for integration with GetReceipts.org website.

Architecture:
- Website (GetReceipts.org) = Primary UI
- Daemon (localhost:8765) = Local processing (Whisper, LLM, yt-dlp)
- All heavy lifting happens locally on user's Mac
"""

__version__ = "1.1.23"

