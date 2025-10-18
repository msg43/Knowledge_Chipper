"""
Proxy Abstraction Layer

Provides a unified interface for multiple proxy providers, enabling easy switching
between different proxy services (PacketStream, AnyIP, Oxylabs, GonzoProxy, BrightData)
or direct connections without modifying application code.

Usage:
    from knowledge_system.utils.proxy import ProxyService
    
    # Create proxy service (auto-selects provider from config)
    proxy_service = ProxyService()
    
    # Get proxy configuration for requests library
    proxies = proxy_service.get_proxy_config()
    response = requests.get(url, proxies=proxies)
    
    # Get proxy URL for yt-dlp
    proxy_url = proxy_service.get_proxy_url(session_id="video_123")
    ydl_opts = {"proxy": proxy_url}
"""

from .base_provider import BaseProxyProvider, ProxyType
from .proxy_service import ProxyService

# Import providers for direct access if needed
from .anyip_provider import AnyIPProvider
from .brightdata_provider import BrightDataProvider
from .direct_provider import DirectConnectionProvider
from .gonzoproxy_provider import GonzoProxyProvider
from .oxylabs_provider import OxylabsProvider
from .packetstream_provider import PacketStreamProvider

__all__ = [
    # Main API
    "ProxyService",
    "ProxyType",
    "BaseProxyProvider",
    # Provider implementations
    "PacketStreamProvider",
    "AnyIPProvider",
    "OxylabsProvider",
    "GonzoProxyProvider",
    "BrightDataProvider",
    "DirectConnectionProvider",
]

