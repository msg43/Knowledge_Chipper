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
        logger.debug(
            f"🔍 LLM DEBUG: generate_json called with model_uri: {self.model_uri}"
        )
        logger.debug(f"🔍 LLM DEBUG: Prompt length: {len(prompt)} chars")
        logger.debug(f"🔍 LLM DEBUG: Prompt preview: {prompt[:200]}...")

        try:
            if self.scheme == "openai":
                result = self._call_openai(prompt)
            elif self.scheme == "anthropic":
                result = self._call_anthropic(prompt)
            elif self.scheme == "ollama":
                result = self._call_ollama(prompt)
            elif self.scheme == "local":
                result = self._call_local(prompt)
            else:
                raise ValueError(f"Unsupported LLM scheme: {self.scheme}")

            logger.debug(f"🔍 LLM DEBUG: Result type: {type(result)}")
            logger.debug(f"🔍 LLM DEBUG: Result preview: {str(result)[:200]}...")
            return result

        except Exception as e:
            logger.error(f"🔍 LLM DEBUG: 💥 ERROR in generate_json: {e}")
            logger.error(f"🔍 LLM DEBUG: Exception type: {type(e).__name__}")
            import traceback

            logger.error(f"🔍 LLM DEBUG: Traceback: {traceback.format_exc()}")
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
            parsed = urlparse(self.model_uri)
            # Handle both openai://model and openai:model formats
            model_name = parsed.netloc or parsed.path.lstrip("/")

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
                r"```(?:json)?\s*(\[.*\]|\{.*\})\s*```", content, re.DOTALL
            )
            if json_match:
                json_content = json_match.group(1)
            else:
                # Use balanced bracket extraction for better JSON parsing
                json_content = self._extract_balanced_json(content)

            try:
                return json.loads(json_content)
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Failed to parse JSON from OpenAI model {model_name}: {e}"
                )
                logger.debug(f"Raw content: {content[:500]}...")
                logger.debug(f"JSON content being parsed: {json_content[:500]}...")

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
            parsed = urlparse(self.model_uri)
            # Handle both anthropic://model and anthropic:model formats
            model_name = parsed.netloc or parsed.path.lstrip("/")

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
            parsed = urlparse(self.model_uri)
            # Handle both ollama://model and ollama:model formats
            model_name = parsed.netloc or parsed.path.lstrip("/")

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
                # Look for JSON without code blocks using balanced bracket extraction
                json_content = self._extract_balanced_json(content)
                logger.debug(
                    f"Ollama balanced extraction: {len(json_content)} chars, ends with: {repr(json_content[-50:])}"
                )

            try:
                return json.loads(json_content)
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Failed to parse JSON from Ollama model {model_name}: {e}"
                )
                logger.warning(f"Raw Ollama response: {repr(content)}")
                logger.warning(f"Extracted JSON content: {repr(json_content)}")
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
            parsed = urlparse(self.model_uri)
            # Handle both local://model and local:model formats
            model_name = parsed.netloc or parsed.path.lstrip("/")
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
            self._repair_missing_commas,  # New strategy for Ollama comma issues
            self._repair_unescaped_quotes,
            self._repair_control_characters,
            self._repair_incomplete_json,
            self._repair_newlines_in_strings,
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

    def _repair_missing_commas(self, json_str: str) -> str:
        """Add missing commas between JSON object properties and array elements."""
        # Only add commas between complete property-value pairs, not within incomplete JSON

        # Pattern 1: Missing comma between complete object properties
        # Look for: "key": "value" "nextkey": (but not if we're in incomplete JSON)
        # Only match if the first part ends with a quote, number, or closing bracket/brace
        json_str = re.sub(
            r'("[\w_]+"\s*:\s*(?:"[^"]*"|[0-9]+|true|false|null))\s+("[\w_]+"\s*:)',
            r"\1,\n    \2",
            json_str,
            flags=re.MULTILINE,
        )

        # Pattern 2: Missing comma between array elements (complete objects)
        # Look for: } { (complete objects in array)
        json_str = re.sub(r"}\s*\n\s*{", r"},\n  {", json_str, flags=re.MULTILINE)

        return json_str

    def _extract_balanced_json(self, content: str) -> str:
        """Extract JSON using balanced bracket counting to handle incomplete JSON better."""
        # Find the first opening bracket or brace
        array_start = content.find("[")
        object_start = content.find("{")

        # Determine which comes first
        if array_start == -1 and object_start == -1:
            return content  # No JSON found

        if array_start == -1:
            start_pos = object_start
            start_char = "{"
            end_char = "}"
        elif object_start == -1:
            start_pos = array_start
            start_char = "["
            end_char = "]"
        else:
            if array_start < object_start:
                start_pos = array_start
                start_char = "["
                end_char = "]"
            else:
                start_pos = object_start
                start_char = "{"
                end_char = "}"

        # Count balanced brackets/braces
        bracket_count = 0
        end_pos = len(content)

        for i, char in enumerate(content[start_pos:], start_pos):
            if char == start_char:
                bracket_count += 1
            elif char == end_char:
                bracket_count -= 1
                if bracket_count == 0:
                    end_pos = i + 1
                    break

        return content[start_pos:end_pos]

    def _repair_unescaped_quotes(self, json_str: str) -> str:
        """Escape unescaped quotes within string values."""
        # Simple and effective approach: find strings with unescaped quotes inside them

        # Pattern 1: ": "text with "quoted phrase" more text" (for object values)
        pattern1 = r':\s*"([^"]*)\s+"([^"]+)"\s+([^"]*)"'

        def escape_inner_quotes1(match):
            before = match.group(1)
            quoted_part = match.group(2)
            after = match.group(3)
            return f': "{before} \\"{quoted_part}\\" {after}"'

        # Pattern 2: specific pattern that matches quotes followed by space and more text
        pattern2 = r'"([^"]*) " ([^"]*)"'

        def escape_inner_quotes2(match):
            before = match.group(1)
            after = match.group(2)
            return f'"{before} \\" {after}"'

        # Apply patterns
        repaired = re.sub(pattern1, escape_inner_quotes1, json_str)
        repaired = re.sub(pattern2, escape_inner_quotes2, repaired)

        return repaired

    def _repair_incomplete_json(self, json_str: str) -> str:
        """Try to complete incomplete JSON objects/arrays."""
        json_str = json_str.strip()

        # Count opening and closing braces/brackets
        open_braces = json_str.count("{")
        close_braces = json_str.count("}")
        open_brackets = json_str.count("[")
        close_brackets = json_str.count("]")

        # If JSON ends abruptly in the middle of a string, try to close it
        if (
            json_str.endswith('"')
            and not json_str.endswith('",')
            and not json_str.endswith('"}')
        ):
            # Check if we're in an object property value
            if (
                json_str.count('"') % 2 == 0
            ):  # Even number of quotes means we're outside a string
                # Look for the last property to see if we need a comma or closing brace
                lines = json_str.split("\n")
                last_line = lines[-1].strip() if lines else ""
                if ":" in last_line and not last_line.endswith(","):
                    # We're at the end of a property value, add proper closing
                    if open_braces > close_braces:
                        json_str += "\n    }"
                    if open_brackets > close_brackets:
                        json_str += "\n  ]"

        # Add missing closing braces
        if open_braces > close_braces:
            missing_braces = open_braces - close_braces
            # Add proper indentation for nested structures
            for i in range(missing_braces):
                indent = "  " * (missing_braces - i - 1)
                json_str += f"\n{indent}}}"

        # Add missing closing brackets
        if open_brackets > close_brackets:
            missing_brackets = open_brackets - close_brackets
            for i in range(missing_brackets):
                json_str += "\n]"

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
