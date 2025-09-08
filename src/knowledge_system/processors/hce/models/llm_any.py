from urllib.parse import urlparse


class AnyLLM:
    """
    Minimal URI-driven wrapper. Implement backends as needed:
    - ollama://MODEL
    - openai://MODEL
    - local://llama.cpp?quant=q4
    - anthropic://MODEL
    """

    def __init__(self, model_uri: str):
        self.model_uri = model_uri
        self.scheme = urlparse(model_uri).scheme if model_uri else None

    def generate_json(self, prompt: str):
        """Generate JSON response from LLM based on model URI.

        Args:
            prompt: The prompt text to send to the LLM

        Returns:
            JSON response from the LLM
        """
        try:
            if self.scheme == "openai":
                return self._call_openai(prompt)
            elif self.scheme == "anthropic":
                return self._call_anthropic(prompt)
            elif self.scheme == "ollama":
                return self._call_ollama(prompt)
            elif self.scheme == "local":
                return self._call_local(prompt)
            else:
                raise ValueError(f"Unsupported LLM scheme: {self.scheme}")

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"LLM generation failed for {self.model_uri}: {e}")
            return []

    def judge_json(self, prompt: str):
        """Judge/evaluate content using LLM, returning JSON response.

        Args:
            prompt: The prompt text for judgment

        Returns:
            JSON response with judgment/evaluation
        """
        # For now, use the same implementation as generate_json
        # In a more sophisticated implementation, this might use different parameters
        return self.generate_json(prompt)

    def _call_openai(self, prompt: str):
        """Call OpenAI API."""
        try:
            # Import here to avoid dependency issues
            from ....utils.llm_providers import get_openai_client

            client = get_openai_client()
            model_name = urlparse(self.model_uri).netloc

            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=2000,
            )

            content = response.choices[0].message.content

            # Try to parse as JSON
            import json

            return json.loads(content)

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"OpenAI call failed: {e}")
            return []

    def _call_anthropic(self, prompt: str):
        """Call Anthropic API."""
        try:
            from ....utils.llm_providers import get_anthropic_client

            client = get_anthropic_client()
            model_name = urlparse(self.model_uri).netloc

            response = client.messages.create(
                model=model_name,
                max_tokens=2000,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}],
            )

            content = response.content[0].text

            # Try to parse as JSON
            import json

            return json.loads(content)

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Anthropic call failed: {e}")
            return []

    def _call_ollama(self, prompt: str):
        """Call Ollama local API."""
        try:
            from ....utils.ollama_manager import get_ollama_manager

            ollama = get_ollama_manager()
            model_name = urlparse(self.model_uri).netloc

            response = ollama.generate(
                model=model_name,
                prompt=prompt,
                options={"temperature": 0.1, "num_predict": 2000},
            )

            content = response.get("response", "")

            # Try to parse as JSON
            import json

            return json.loads(content)

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Ollama call failed: {e}")
            return []

    def _call_local(self, prompt: str):
        """Call local model."""
        # Placeholder for local model calls
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(f"Local model calls not fully implemented for {self.model_uri}")
        return []
