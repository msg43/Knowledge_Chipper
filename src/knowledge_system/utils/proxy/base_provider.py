"""
Base proxy provider interface for the proxy abstraction layer.

This module defines the abstract base class that all proxy providers must implement,
ensuring a consistent interface across different proxy services.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Optional, Tuple


class ProxyType(Enum):
    """Supported proxy provider types."""
    
    PACKETSTREAM = "packetstream"
    ANYIP = "anyip"
    OXYLABS = "oxylabs"
    GONZOPROXY = "gonzoproxy"
    BRIGHTDATA = "brightdata"
    DIRECT = "direct"  # No proxy (direct connection)


class BaseProxyProvider(ABC):
    """
    Abstract base class for proxy providers.
    
    All proxy providers must implement this interface to ensure consistent
    behavior across different proxy services.
    """
    
    @abstractmethod
    def get_proxy_url(self, session_id: Optional[str] = None) -> Optional[str]:
        """
        Get proxy URL string for use with yt-dlp and direct HTTP calls.
        
        Args:
            session_id: Optional session identifier for sticky sessions
            
        Returns:
            Proxy URL string (e.g., "http://user:pass@proxy.example.com:8080")
            or None if no proxy should be used
        """
        pass
    
    @abstractmethod
    def get_proxy_config(self) -> Dict[str, str]:
        """
        Get proxy configuration dict for use with requests library.
        
        Returns:
            Dict with 'http' and 'https' keys mapping to proxy URLs,
            or empty dict if no proxy should be used
        """
        pass
    
    @abstractmethod
    def test_connectivity(self, timeout: int = 10) -> Tuple[bool, str]:
        """
        Test if proxy connection is working.
        
        Args:
            timeout: Connection timeout in seconds
            
        Returns:
            Tuple of (success: bool, message: str)
            - success: True if proxy is working, False otherwise
            - message: Human-readable status message
        """
        pass
    
    @abstractmethod
    def is_configured(self) -> bool:
        """
        Check if this provider has valid credentials configured.
        
        Returns:
            True if provider is configured and ready to use, False otherwise
        """
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """
        Get human-readable provider name.
        
        Returns:
            Provider name (e.g., "PacketStream", "Oxylabs")
        """
        pass

