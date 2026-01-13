"""
Simple LLM Wrapper for TwoPassPipeline

The TwoPassPipeline expects an LLM adapter with a simple complete(prompt) method,
but the core LLMAdapter has a complex async interface.
This wrapper bridges the gap.
"""

import logging
from src.knowledge_system.core.llm_adapter import LLMAdapter

logger = logging.getLogger(__name__)


class SimpleLLMWrapper:
    """
    Simple synchronous wrapper around LLMAdapter for TwoPassPipeline.
    
    Provides the simple complete(prompt) interface that ExtractionPass expects.
    """
    
    def __init__(self, provider: str, model: str, temperature: float = 0.3):
        """
        Initialize wrapper.
        
        Args:
            provider: LLM provider (openai, anthropic, etc.)
            model: Model name (gpt-4o, claude-3-5-sonnet, etc.)
            temperature: Sampling temperature
        """
        self.provider = provider
        self.model = model
        self.temperature = temperature
        
        # CRITICAL: Inject API keys from daemon store into environment
        # PyInstaller apps have issues with os.environ persistence, so we use a module-level store
        import os
        from daemon.services.api_key_store import get_api_key
        
        # Inject API keys from store into environment for this process
        for provider_name in ["openai", "anthropic", "google"]:
            key = get_api_key(provider_name)
            if key:
                env_var = f"{provider_name.upper()}_API_KEY"
                os.environ[env_var] = key
                logger.info(f"✅ Injected {provider_name} API key into environment")
        
        logger.info(f"🔑 API keys in environment:")
        logger.info(f"  - OPENAI_API_KEY: {'✅ Set' if os.environ.get('OPENAI_API_KEY') else '❌ Not set'}")
        logger.info(f"  - ANTHROPIC_API_KEY: {'✅ Set' if os.environ.get('ANTHROPIC_API_KEY') else '❌ Not set'}")
        logger.info(f"  - GOOGLE_API_KEY: {'✅ Set' if os.environ.get('GOOGLE_API_KEY') else '❌ Not set'}")
        
        # CRITICAL: Force reload settings to pick up the newly-injected environment variables
        # The Settings object caches on first load, so we must reload after setting env vars
        from src.knowledge_system.config import get_settings
        get_settings(reload=True)
        logger.info("🔄 Reloaded settings to pick up injected API keys")
        
        self.adapter = LLMAdapter(provider=provider)
        
        logger.info(f"🔧 SimpleLLMWrapper initialized: provider={provider}, model={model}, temperature={temperature}")
    
    def complete(self, prompt: str) -> str:
        """
        Simple synchronous completion method.
        
        Args:
            prompt: The prompt string
            
        Returns:
            The completion text
        """
        import asyncio
        
        # Convert prompt to messages format
        messages = [
            {"role": "user", "content": prompt}
        ]
        
        # Call the async method synchronously
        logger.info(f"🚀 Calling LLM: provider={self.provider}, model={self.model}")
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                self.adapter.complete(
                    provider=self.provider,
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=16384,  # Large enough for full extraction from long transcripts
                )
            )
            
            # Log response details for diagnostics
            content = result.get('content', '')
            logger.info(f"✅ LLM call successful: {len(content)} chars")
            logger.info(f"📄 Response preview (first 500 chars): {content[:500]}")
            
            # Check if response looks like JSON
            if content.strip().startswith('{') or '```json' in content:
                logger.info("✓ Response appears to be JSON format")
            else:
                logger.warning(f"⚠️  Response does NOT appear to be JSON! Starts with: {content[:100]}")
        except Exception as e:
            logger.error(f"❌ LLM call failed: provider={self.provider}, model={self.model}, error={e}")
            raise
        
        # Extract text content from response dict
        # Response format: {"content": "...", "model": "...", "usage": {...}}
        if isinstance(result, dict):
            content = result.get('content', '')
            if not content:
                logger.error(f"LLM returned empty content. Full response: {result}")
                logger.error(f"Response keys: {result.keys()}")
            return content or str(result)
        else:
            return str(result)
