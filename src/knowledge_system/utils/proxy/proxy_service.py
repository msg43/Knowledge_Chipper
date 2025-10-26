"""
Proxy Service Manager

Centralized proxy management service that handles provider selection, failover,
and provides a unified interface for all YouTube data extraction operations.
"""

import logging
from typing import Dict, Optional, Tuple

from .anyip_provider import AnyIPProvider
from .base_provider import BaseProxyProvider, ProxyType
from .brightdata_provider import BrightDataProvider
from .direct_provider import DirectConnectionProvider
from .gonzoproxy_provider import GonzoProxyProvider
from .oxylabs_provider import OxylabsProvider
from .packetstream_provider import PacketStreamProvider

logger = logging.getLogger(__name__)


class ProxyService:
    """
    Centralized proxy management service.

    Handles provider selection, failover, and configuration for all proxy operations.
    Acts as a facade that delegates to the active provider.
    """

    def __init__(self, preferred_provider: ProxyType | None = None):
        """
        Initialize proxy service.

        Args:
            preferred_provider: Optional provider preference, otherwise uses config
        """
        self.preferred_provider = preferred_provider or self._get_configured_provider()
        self.providers = self._initialize_providers()
        self.active_provider = self._select_active_provider()

        logger.info(
            f"Proxy service initialized with provider: {self.active_provider.provider_name}"
        )

    def _get_configured_provider(self) -> ProxyType:
        """
        Read preferred provider from config.

        Returns:
            ProxyType enum value
        """
        try:
            from ...config import get_settings

            settings = get_settings()
            provider_name = getattr(settings, "proxy_provider", "packetstream").lower()

            # Map string to ProxyType enum
            provider_map = {
                "packetstream": ProxyType.PACKETSTREAM,
                "anyip": ProxyType.ANYIP,
                "oxylabs": ProxyType.OXYLABS,
                "gonzoproxy": ProxyType.GONZOPROXY,
                "brightdata": ProxyType.BRIGHTDATA,
                "direct": ProxyType.DIRECT,
            }

            return provider_map.get(provider_name, ProxyType.PACKETSTREAM)
        except Exception as e:
            logger.warning(
                f"Failed to load proxy provider config: {e}, defaulting to PacketStream"
            )
            return ProxyType.PACKETSTREAM

    def _initialize_providers(self) -> dict[ProxyType, BaseProxyProvider]:
        """
        Initialize all available proxy providers.

        Returns:
            Dict mapping ProxyType to provider instance
        """
        return {
            ProxyType.PACKETSTREAM: PacketStreamProvider(),
            ProxyType.ANYIP: AnyIPProvider(),
            ProxyType.OXYLABS: OxylabsProvider(),
            ProxyType.GONZOPROXY: GonzoProxyProvider(),
            ProxyType.BRIGHTDATA: BrightDataProvider(),
            ProxyType.DIRECT: DirectConnectionProvider(),
        }

    def _select_active_provider(self) -> BaseProxyProvider:
        """
        Select which provider to use based on availability and configuration.

        Returns:
            Active provider instance
        """
        # Try preferred provider first
        preferred = self.providers[self.preferred_provider]
        if preferred.is_configured():
            logger.info(f"Using preferred proxy provider: {preferred.provider_name}")
            return preferred

        # Check if failover is enabled
        failover_enabled = self._is_failover_enabled()

        if failover_enabled:
            # Fall back to any configured provider
            for provider_type, provider in self.providers.items():
                if provider_type == self.preferred_provider:
                    continue  # Already tried
                if provider_type == ProxyType.DIRECT:
                    continue  # Save direct connection as last resort
                if provider.is_configured():
                    logger.info(
                        f"Preferred provider not available, falling back to {provider.provider_name}"
                    )
                    return provider

        # Ultimate fallback: direct connection (no proxy)
        # Check if strict mode prevents this fallback
        if self._is_strict_mode_enabled():
            logger.warning("Proxy strict mode enabled - no configured proxy available")
            # Return a placeholder that will raise errors when used
            # We can't raise here because initialization happens early
            return self.providers[ProxyType.DIRECT]

        logger.info("No proxy providers configured, using direct connection")
        return self.providers[ProxyType.DIRECT]

    def _is_failover_enabled(self) -> bool:
        """
        Check if proxy failover is enabled in config.

        Returns:
            True if failover is enabled
        """
        try:
            from ...config import get_settings

            settings = get_settings()
            return getattr(settings, "proxy_failover_enabled", True)
        except Exception:
            return True  # Default to enabled

    def _is_strict_mode_enabled(self) -> bool:
        """
        Check if proxy strict mode is enabled in config.

        Strict mode prevents direct connections when proxy fails,
        protecting user IP from exposure to YouTube.

        Returns:
            True if strict mode is enabled (default: True)
        """
        try:
            from ...config import get_settings

            settings = get_settings()
            # Check youtube_processing.proxy_strict_mode
            youtube_config = getattr(settings, "youtube_processing", None)
            if youtube_config:
                return getattr(youtube_config, "proxy_strict_mode", True)
            return True  # Default to strict mode for safety
        except Exception:
            return True  # Default to strict mode for safety

    def is_using_direct_connection(self) -> bool:
        """
        Check if currently using direct connection (no proxy).

        Returns:
            True if using direct connection
        """
        return isinstance(self.active_provider, DirectConnectionProvider)

    def validate_for_youtube_operation(self) -> tuple[bool, str]:
        """
        Validate that current proxy configuration is safe for YouTube operations.

        This should be called before any YouTube download/metadata operations
        when strict mode is enabled.

        Returns:
            Tuple of (is_valid: bool, error_message: str)
        """
        # If using direct connection, check if strict mode allows it
        if self.is_using_direct_connection():
            if self._is_strict_mode_enabled():
                return (
                    False,
                    "Proxy strict mode enabled: Direct YouTube connections blocked. "
                    "Configure a proxy (PacketStream/BrightData) or disable strict mode in Settings.",
                )
            else:
                # Strict mode disabled, but warn the user
                logger.warning(
                    "Using direct connection for YouTube - your IP may be exposed to rate limits"
                )
                return (True, "")

        # Using a proxy, validate it's working
        return (True, "")

    # Public API - delegates to active provider

    def get_proxy_url(self, session_id: str | None = None) -> str | None:
        """
        Get proxy URL from active provider.

        Args:
            session_id: Optional session identifier for sticky sessions

        Returns:
            Proxy URL string or None
        """
        return self.active_provider.get_proxy_url(session_id)

    def get_proxy_config(self) -> dict[str, str]:
        """
        Get proxy config from active provider.

        Returns:
            Dict with 'http' and 'https' keys, or empty dict
        """
        return self.active_provider.get_proxy_config()

    def test_connectivity(self, timeout: int = 10) -> tuple[bool, str]:
        """
        Test connectivity of active provider.

        Args:
            timeout: Connection timeout in seconds

        Returns:
            Tuple of (success: bool, message: str)
        """
        return self.active_provider.test_connectivity(timeout)

    def is_configured(self) -> bool:
        """
        Check if active provider is configured.

        Returns:
            True if active provider is configured
        """
        return self.active_provider.is_configured()

    @property
    def provider_name(self) -> str:
        """
        Get name of active provider.

        Returns:
            Provider name string
        """
        return self.active_provider.provider_name

    def get_provider(self, provider_type: ProxyType) -> BaseProxyProvider:
        """
        Get a specific provider instance.

        Args:
            provider_type: Type of provider to get

        Returns:
            Provider instance
        """
        return self.providers[provider_type]

    def switch_provider(self, provider_type: ProxyType) -> bool:
        """
        Switch to a different proxy provider.

        Args:
            provider_type: Type of provider to switch to

        Returns:
            True if switch was successful, False otherwise
        """
        provider = self.providers[provider_type]

        if not provider.is_configured() and provider_type != ProxyType.DIRECT:
            logger.warning(f"Cannot switch to {provider.provider_name}: not configured")
            return False

        self.active_provider = provider
        logger.info(f"Switched to proxy provider: {provider.provider_name}")
        return True
