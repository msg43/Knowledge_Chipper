from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Optional, Type, TypeVar

from ..utils.llm_providers import UnifiedLLMClient
from .config import SuperChunkConfig
from .validators import ClaimItem, JargonItem, LocalContradictionItem

T = TypeVar("T")


@dataclass
class SuperChunkLLMAdapter:
    config: SuperChunkConfig
    client: UnifiedLLMClient
    event_logger: Optional[Callable[[dict[str, Any]], None]] = None

    @staticmethod
    def create_default() -> "SuperChunkLLMAdapter":
        cfg = SuperChunkConfig.from_global_settings()
        client = UnifiedLLMClient()
        return SuperChunkLLMAdapter(config=cfg, client=client, event_logger=None)

    def _with_token_budget(self, prompt: str, estimated_output_tokens: int) -> str:
        window = self.config.get_window()
        input_budget = window.max_tokens
        output_budget = max(256, min(2048, estimated_output_tokens))
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
        schema: Type[T],
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
            return self._delta_reprompt(original_prompt, data, schema, attempts_left - 1)

    def generate_json(self, prompt: str, schema: Type[T], estimated_output_tokens: int = 800, attempts: int = 2) -> T:
        final_prompt = self._with_token_budget(prompt, estimated_output_tokens)
        content = self._call_raw(final_prompt)
        data = self._parse_json(content)
        return self._delta_reprompt(final_prompt, data, schema, attempts)

    # Convenience helpers for extractors
    def extract_claims(self, prompt: str, count: int, estimated_output_tokens: int = 800):
        final_prompt = self._with_token_budget(self._require_exact_count(prompt, count), estimated_output_tokens)
        content = self._call_raw(final_prompt)
        try:
            data = self._parse_json(content)
            return [ClaimItem.model_validate(item) for item in data]
        except Exception:
            return self.generate_json(final_prompt, ClaimItem, estimated_output_tokens, attempts=1)

    def extract_contradictions(self, prompt: str, max_count: int, estimated_output_tokens: int = 400):
        final_prompt = self._with_token_budget(self._require_exact_count(prompt, max_count), estimated_output_tokens)
        content = self._call_raw(final_prompt)
        try:
            data = self._parse_json(content)
            return [LocalContradictionItem.model_validate(item) for item in data]
        except Exception:
            return self.generate_json(final_prompt, LocalContradictionItem, estimated_output_tokens, attempts=1)

    def extract_jargon(self, prompt: str, count: int, estimated_output_tokens: int = 400):
        final_prompt = self._with_token_budget(self._require_exact_count(prompt, count), estimated_output_tokens)
        content = self._call_raw(final_prompt)
        try:
            data = self._parse_json(content)
            return [JargonItem.model_validate(item) for item in data]
        except Exception:
            return self.generate_json(final_prompt, JargonItem, estimated_output_tokens, attempts=1)
