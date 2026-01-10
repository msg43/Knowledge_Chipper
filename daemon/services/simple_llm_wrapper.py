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
        self.adapter = LLMAdapter(provider=provider)
        
        logger.info(f"SimpleLLMWrapper initialized: {provider}/{model}")
    
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
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            self.adapter.complete(
                provider=self.provider,
                model=self.model,
                messages=messages,
                temperature=self.temperature,
            )
        )
        
        # Extract text content from response dict
        # Response format: {"content": "...", "model": "...", "usage": {...}}
        if isinstance(result, dict):
            return result.get('content', str(result))
        else:
            return str(result)
