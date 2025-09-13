import json
import logging
import re
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

            try:
                return json.loads(json_content)
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Failed to parse JSON from OpenAI model {model_name}: {e}"
                )
                logger.debug(f"Raw content: {content[:500]}...")

                # Try to repair the JSON and parse again
                repaired_json = self._attempt_json_repair(json_content, model_name)
                if repaired_json is not None:
                    return repaired_json

                return []

        except Exception as e:
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

            try:
                return json.loads(json_content)
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Failed to parse JSON from Anthropic model {model_name}: {e}"
                )
                logger.debug(f"Raw content: {content[:500]}...")

                # Try to repair the JSON and parse again
                repaired_json = self._attempt_json_repair(json_content, model_name)
                if repaired_json is not None:
                    return repaired_json

                return []

        except Exception as e:
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

            try:
                return json.loads(json_content)
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Failed to parse JSON from Ollama model {model_name}: {e}"
                )
                logger.debug(f"Raw content: {content[:500]}...")

                # Try to repair the JSON and parse again
                repaired_json = self._attempt_json_repair(json_content, model_name)
                if repaired_json is not None:
                    return repaired_json

                return []

        except Exception as e:
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

                # Try to repair the JSON and parse again
                repaired_json = self._attempt_json_repair(json_content, model_name)
                if repaired_json is not None:
                    # Ensure we return a list for consistency with other methods
                    if isinstance(repaired_json, dict):
                        return [repaired_json]
                    elif isinstance(repaired_json, list):
                        return repaired_json
                    else:
                        logger.warning(
                            f"Unexpected JSON type from repaired content {model_name}: {type(repaired_json)}"
                        )
                        return []

                # Log helpful information for debugging future JSON issues
                logger.warning(
                    f"JSON parsing and repair failed completely for model {model_name}. "
                    f"Error location: {e}. Consider checking model output format or prompts."
                )
                return []

        except Exception as e:
            logger.warning(f"Local model call failed for {self.model_uri}: {e}")
            return []

    def _attempt_json_repair(self, json_content: str, model_name: str):
        """Attempt to repair malformed JSON from LLM responses.

        Args:
            json_content: The potentially malformed JSON string
            model_name: The model name for logging purposes

        Returns:
            Parsed JSON object if repair was successful, None otherwise
        """
        logger.debug(f"Attempting to repair JSON from {model_name}")

        # Common repair strategies ordered by likelihood of success
        repair_strategies = [
            self._repair_trailing_commas,
            self._repair_incomplete_json,
            self._repair_newlines_in_strings,
            self._repair_control_characters,
            self._repair_unescaped_quotes,
        ]

        # Apply repairs iteratively until JSON parses or no more changes are made
        current_content = json_content
        for attempt in range(3):  # Max 3 attempts to avoid infinite loops
            logger.debug(f"Repair attempt {attempt + 1}")

            changes_made = False
            for strategy in repair_strategies:
                try:
                    repaired = strategy(current_content)
                    if repaired != current_content:
                        logger.debug(f"Applied repair strategy: {strategy.__name__}")
                        current_content = repaired
                        changes_made = True

                        # Try to parse after each repair
                        try:
                            parsed = json.loads(current_content)
                            logger.info(
                                f"Successfully repaired JSON using {strategy.__name__} for model {model_name}"
                            )
                            return parsed
                        except json.JSONDecodeError:
                            # Continue with next repair strategy
                            continue

                except Exception as e:
                    logger.debug(f"Repair strategy {strategy.__name__} failed: {e}")
                    continue

            # If no changes were made this round, break to avoid infinite loop
            if not changes_made:
                break

        logger.warning(f"All JSON repair strategies failed for model {model_name}")
        return None

    def _repair_trailing_commas(self, json_str: str) -> str:
        """Remove trailing commas that cause JSON parsing errors."""
        # Remove trailing commas before closing brackets/braces
        # This regex handles whitespace and newlines between comma and closing bracket
        json_str = re.sub(
            r",(\s*[}\]])", r"\1", json_str, flags=re.MULTILINE | re.DOTALL
        )
        return json_str

    def _repair_unescaped_quotes(self, json_str: str) -> str:
        """Escape unescaped quotes within string values."""
        # More targeted approach: only fix quotes that are clearly within string values,
        # not array elements or other JSON structures

        # Look for the specific pattern: ": "text with "quoted phrase" more text"
        # This ensures we're only fixing string values, not array elements
        pattern = r':\s*"([^"]*)\s+"([^"]+)"\s+([^"]*)"'

        def escape_inner_quotes(match):
            # Reconstruct the string with escaped inner quotes
            before = match.group(1)
            quoted_part = match.group(2)
            after = match.group(3)
            return f': "{before} \\"{quoted_part}\\" {after}"'

        # Apply the fix
        repaired = re.sub(pattern, escape_inner_quotes, json_str)

        return repaired

    def _repair_incomplete_json(self, json_str: str) -> str:
        """Try to complete incomplete JSON objects/arrays."""
        json_str = json_str.strip()

        # Count opening and closing braces/brackets
        open_braces = json_str.count("{")
        close_braces = json_str.count("}")
        open_brackets = json_str.count("[")
        close_brackets = json_str.count("]")

        # Add missing closing braces
        if open_braces > close_braces:
            json_str += "}" * (open_braces - close_braces)

        # Add missing closing brackets
        if open_brackets > close_brackets:
            json_str += "]" * (open_brackets - close_brackets)

        return json_str

    def _repair_control_characters(self, json_str: str) -> str:
        """Remove or escape control characters that break JSON parsing."""
        # Remove common control characters except for \n, \t, \r
        json_str = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", json_str)
        return json_str

    def _repair_newlines_in_strings(self, json_str: str) -> str:
        """Fix unescaped newlines within JSON string values."""
        # This repair should only target newlines that are actually within string values,
        # not structural newlines that are part of JSON formatting

        # For now, let's be very conservative and only handle cases where there are
        # literal newlines inside quoted strings

        # Pattern to find strings that contain actual newline characters
        def fix_string_newlines(match):
            string_content = match.group(1)
            # Only escape newlines if they're not already escaped
            fixed_content = string_content.replace("\n", "\\n")
            fixed_content = fixed_content.replace("\r", "\\r")
            fixed_content = fixed_content.replace("\t", "\\t")
            return f'"{fixed_content}"'

        # Only apply to quoted strings that contain unescaped newlines
        # This pattern matches strings that have actual newline characters inside them
        pattern = r'"([^"]*\n[^"]*)"'
        json_str = re.sub(pattern, fix_string_newlines, json_str, flags=re.DOTALL)

        return json_str
