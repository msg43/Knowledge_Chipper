import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


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

            # Try to parse as JSON, handling markdown code blocks
            import json
            import re

            # Clean up the response - remove markdown code blocks if present
            json_content = content

            # Look for JSON in markdown code blocks
            json_match = re.search(
                r"```(?:json)?\s*(\[.*?\]|\{.*?\})\s*```", content, re.DOTALL
            )
            if json_match:
                json_content = json_match.group(1)
            else:
                # Look for JSON without code blocks
                json_match = re.search(r"(\[.*?\]|\{.*?\})", content, re.DOTALL)
                if json_match:
                    json_content = json_match.group(1)

            return json.loads(json_content)

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

            # Try to parse as JSON, handling markdown code blocks
            import json
            import re

            # Clean up the response - remove markdown code blocks if present
            json_content = content

            # Look for JSON in markdown code blocks
            json_match = re.search(
                r"```(?:json)?\s*(\[.*?\]|\{.*?\})\s*```", content, re.DOTALL
            )
            if json_match:
                json_content = json_match.group(1)
            else:
                # Look for JSON without code blocks
                json_match = re.search(r"(\[.*?\]|\{.*?\})", content, re.DOTALL)
                if json_match:
                    json_content = json_match.group(1)

            return json.loads(json_content)

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

            # Try to parse as JSON, handling markdown code blocks
            import json
            import re

            # Clean up the response - remove markdown code blocks if present
            json_content = content

            # Look for JSON in markdown code blocks
            json_match = re.search(
                r"```(?:json)?\s*(\[.*?\]|\{.*?\})\s*```", content, re.DOTALL
            )
            if json_match:
                json_content = json_match.group(1)
            else:
                # Look for JSON without code blocks
                json_match = re.search(r"(\[.*?\]|\{.*?\})", content, re.DOTALL)
                if json_match:
                    json_content = json_match.group(1)

            return json.loads(json_content)

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Ollama call failed: {e}")
            return []

    def _call_local(self, prompt: str):
        """Call local model via Ollama HTTP API."""
        try:
            import requests

            from ....config import get_settings

            settings = get_settings()
            base_url = settings.local_config.base_url.rstrip("/")

            # Extract model name from URI (e.g., "local://llama3.2:latest" -> "llama3.2:latest")
            model_name = urlparse(self.model_uri).netloc
            if not model_name:
                # Fallback: try to get the model name after the ://
                model_name = (
                    self.model_uri.split("://")[-1]
                    if "://" in self.model_uri
                    else self.model_uri
                )

            url = f"{base_url}/api/generate"

            payload = {
                "model": model_name,
                "prompt": prompt,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 2000,
                },
                "stream": False,
            }

            # Use timeout from settings instead of hardcoded value
            timeout = settings.local_config.timeout
            response = requests.post(url, json=payload, timeout=timeout)
            response.raise_for_status()

            result = response.json()
            content = result.get("response", "")

            # Try to parse as JSON, handling markdown code blocks
            import json
            import re

            # Clean up the response - remove markdown code blocks if present
            json_content = content.strip()

            # Return empty list if content is empty or just whitespace
            if not json_content:
                logger.warning(f"Empty response from model {model_name}")
                return []

            # Look for JSON in markdown code blocks
            json_match = re.search(
                r"```(?:json)?\s*(\[.*?\]|\{.*?\})\s*```", content, re.DOTALL
            )
            if json_match:
                json_content = json_match.group(1)
            else:
                # Look for JSON without code blocks
                json_match = re.search(r"(\[.*?\]|\{.*?\})", content, re.DOTALL)
                if json_match:
                    json_content = json_match.group(1)

            try:
                parsed_json = json.loads(json_content)
                # Ensure we return a list for consistency with other methods
                if isinstance(parsed_json, dict):
                    return [parsed_json]
                elif isinstance(parsed_json, list):
                    return parsed_json
                else:
                    logger.warning(
                        f"Unexpected JSON type from model {model_name}: {type(parsed_json)}"
                    )
                    return []
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON from model {model_name}: {e}")
                logger.debug(f"Raw content: {content[:500]}...")
                return []

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Local model call failed for {self.model_uri}: {e}")
            return []
