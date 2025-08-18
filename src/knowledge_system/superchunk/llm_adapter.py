from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional, Type, TypeVar

from ..utils.llm_providers import UnifiedLLMClient
from .config import SuperChunkConfig
from .validators import ClaimItem, JargonItem, LocalContradictionItem

T = TypeVar("T")


@dataclass
class SuperChunkLLMAdapter:
    config: SuperChunkConfig
    client: UnifiedLLMClient
    event_logger: Callable[[dict[str, Any]], None] | None = None

    @staticmethod
    def create_default(
        provider: str | None = None, model: str | None = None
    ) -> SuperChunkLLMAdapter:
        cfg = SuperChunkConfig.from_global_settings()
        # Create client with proper provider and model
        client = (
            UnifiedLLMClient(provider=provider, model=model)
            if provider and model
            else UnifiedLLMClient()
        )
        # Set the model on the config so it can calculate dynamic windows
        if model:
            cfg.model = model
        elif client.model:
            cfg.model = client.model
        cfg.provider = provider or client.provider_name
        return SuperChunkLLMAdapter(config=cfg, client=client, event_logger=None)

    def _with_token_budget(self, prompt: str, estimated_output_tokens: int) -> str:
        from ..utils.text_utils import (
            estimate_tokens_improved,
            get_model_context_window,
        )

        # Get the actual model's context window
        model_context = get_model_context_window(self.client.model)

        # Use SuperChunk window as a guide, but respect model's actual limits
        window = self.config.get_window()

        # Calculate dynamic safety margin based on model context window
        if model_context >= 100000:  # 128k models
            safety_margin = 5000  # Can afford larger margin
        elif model_context >= 30000:  # 32k models
            safety_margin = 3000
        elif model_context >= 15000:  # 16k models
            safety_margin = 2000
        elif model_context >= 8000:  # 8k models
            safety_margin = 1500
        else:  # 4k models
            safety_margin = 500  # Tight margin for small models

        # Calculate safe input budget (leave room for output and safety margin)
        max_possible_input = model_context - estimated_output_tokens - safety_margin

        # Use the smaller of SuperChunk window or model's actual capacity
        input_budget = min(window.max_tokens, max_possible_input)
        output_budget = max(256, min(2048, estimated_output_tokens))

        # Check if prompt exceeds budget and truncate if necessary
        prompt_tokens = estimate_tokens_improved(prompt, self.client.model)

        if prompt_tokens > input_budget:
            # Calculate how much to keep (90% of budget to be safe)
            keep_ratio = (input_budget * 0.9) / prompt_tokens
            keep_chars = int(len(prompt) * keep_ratio)

            # Truncate prompt and add indicator
            prompt = (
                prompt[:keep_chars]
                + "\n\n[Note: Content truncated to fit model context window]"
            )

        header = (
            f"Token budgets — input: <= {input_budget} tokens; output: <= {output_budget} tokens. "
            "Return strictly JSON only, no prose."
        )
        return header + "\n\n" + prompt

    def _require_exact_count(self, base_prompt: str, count: int) -> str:
        return base_prompt + f"\n\nReturn exactly {count} items and STOP. JSON only."

    def _log_event(self, payload: dict[str, Any]) -> None:
        if self.event_logger:
            try:
                self.event_logger(payload)
            except Exception:
                pass

    def _extract_code_fence(self, content: str) -> str:
        if "```" not in content:
            return content
        parts = content.split("```")
        # If formatted as ```json\n...\n``` take the first fenced block content
        if len(parts) >= 3:
            body = parts[1]
            # Drop possible language tag on first line
            nl = body.find("\n")
            if nl != -1:
                return body[nl + 1 : parts[1].__len__()]  # content after first newline
            return body
        return content

    def _slice_balanced_json(self, content: str) -> str:
        # Find first opening brace/bracket
        start_obj = content.find("{")
        start_arr = content.find("[")
        starts = [i for i in [start_obj, start_arr] if i != -1]
        if not starts:
            return content
        i = min(starts)
        opener = content[i]
        closer = "}" if opener == "{" else "]"
        depth = 0
        in_string = False
        escape = False
        end = None
        for pos in range(i, len(content)):
            ch = content[pos]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
            else:
                if ch == '"':
                    in_string = True
                elif ch == opener:
                    depth += 1
                elif ch == closer:
                    depth -= 1
                    if depth == 0:
                        end = pos
                        break
        if end is not None:
            return content[i : end + 1]
        return content[i:]

    def _parse_json(self, content: str) -> Any:
        # Strip leading/trailing whitespace
        content = content.strip()
        # Prefer fenced code block content if present
        content = self._extract_code_fence(content).strip()
        # Slice to first balanced JSON block to avoid trailing text causing 'Extra data'
        content = self._slice_balanced_json(content).strip()
        return json.loads(content)

    def _call_raw(self, prompt: str) -> str:
        response = self.client.generate(prompt)
        self._log_event(
            {
                "event": "llm_call",
                "model": self.client.model,
                "provider": self.client.provider_name,
                "prompt_tokens": response.prompt_tokens,
                "completion_tokens": response.completion_tokens,
                "total_tokens": response.total_tokens,
            }
        )
        return response.content

    def _delta_reprompt(
        self,
        original_prompt: str,
        parsed: Any,
        schema: type[T],
        attempts_left: int,
    ) -> Any:
        try:
            return schema.model_validate(parsed)
        except Exception:
            if attempts_left <= 0:
                raise
            delta = (
                "The previous JSON was invalid or incomplete per the schema. "
                "Return corrected JSON ONLY, no prose."
            )
            prompt = original_prompt + "\n\n" + delta
            content = self._call_raw(prompt)
            data = self._parse_json(content)
            return self._delta_reprompt(
                original_prompt, data, schema, attempts_left - 1
            )

    def generate_json(
        self,
        prompt: str,
        schema: type[T],
        estimated_output_tokens: int = 800,
        attempts: int = 2,
    ) -> T:
        final_prompt = self._with_token_budget(prompt, estimated_output_tokens)
        content = self._call_raw(final_prompt)
        data = self._parse_json(content)
        return self._delta_reprompt(final_prompt, data, schema, attempts)

    # Convenience helpers for extractors
    def extract_claims(
        self, prompt: str, count: int, estimated_output_tokens: int = 800
    ):
        final_prompt = self._with_token_budget(
            self._require_exact_count(prompt, count), estimated_output_tokens
        )
        content = self._call_raw(final_prompt)
        try:
            data = self._parse_json(content)
            return [ClaimItem.model_validate(item) for item in data]
        except Exception:
            # Fallback: try schema-validated list; if single object, wrap
            tried = self.generate_json(
                final_prompt, ClaimItem, estimated_output_tokens, attempts=1
            )
            if isinstance(tried, list):
                return tried
            return [tried]

    def extract_contradictions(
        self, prompt: str, max_count: int, estimated_output_tokens: int = 400
    ):
        final_prompt = self._with_token_budget(
            self._require_exact_count(prompt, max_count), estimated_output_tokens
        )
        content = self._call_raw(final_prompt)
        try:
            data = self._parse_json(content)
            return [LocalContradictionItem.model_validate(item) for item in data]
        except Exception:
            tried = self.generate_json(
                final_prompt,
                LocalContradictionItem,
                estimated_output_tokens,
                attempts=1,
            )
            if isinstance(tried, list):
                return tried
            return [tried]

    def extract_jargon(
        self, prompt: str, count: int, estimated_output_tokens: int = 400
    ):
        final_prompt = self._with_token_budget(
            self._require_exact_count(prompt, count), estimated_output_tokens
        )
        content = self._call_raw(final_prompt)
        try:
            data = self._parse_json(content)
            return [JargonItem.model_validate(item) for item in data]
        except Exception:
            tried = self.generate_json(
                final_prompt, JargonItem, estimated_output_tokens, attempts=1
            )
            if isinstance(tried, list):
                return tried
            return [tried]
