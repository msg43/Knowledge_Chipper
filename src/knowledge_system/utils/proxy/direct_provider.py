"""
Direct connection provider (no proxy).

This provider is used as a fallback when no proxy is configured or available.
It simply returns empty/None values to indicate no proxy should be used.
"""

from typing import Dict, Optional, Tuple

from .base_provider import BaseProxyProvider


class DirectConnectionProvider(BaseProxyProvider):
    """
    Provider for direct connections without using a proxy.
    
    This is always available and serves as the ultimate fallback when
    no proxy providers are configured or working.
    """
    
    def get_proxy_url(self, session_id: Optional[str] = None) -> None:
        """
        Get proxy URL (always None for direct connections).
        
        Args:
            session_id: Ignored for direct connections
            
        Returns:
            None (no proxy URL)
        """
        return None
    
    def get_proxy_config(self) -> Dict[str, str]:
        """
        Get proxy configuration (always empty for direct connections).
        
        Returns:
            Empty dict (no proxy configuration)
        """
        return {}
    
    def test_connectivity(self, timeout: int = 10) -> Tuple[bool, str]:
        """
        Test connectivity (always succeeds for direct connections).
        
        Args:
            timeout: Ignored for direct connections
            
        Returns:
            Tuple of (True, success message)
        """
        return True, "Direct connection (no proxy)"
    
    def is_configured(self) -> bool:
        """
        Check if configured (always True for direct connections).
        
        Returns:
            True (direct connections are always available)
        """
        return True
    
    @property
    def provider_name(self) -> str:
        """
        Get provider name.
        
        Returns:
            "Direct Connection"
        """
        return "Direct Connection"

