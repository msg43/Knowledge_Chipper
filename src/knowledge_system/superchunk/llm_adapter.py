from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Type, TypeVar

from ..utils.llm_providers import UnifiedLLMClient
from .config import SuperChunkConfig
from .validators import ClaimItem, JargonItem, LocalContradictionItem

T = TypeVar("T")


@dataclass
class SuperChunkLLMAdapter:
    config: SuperChunkConfig
    client: UnifiedLLMClient

    @staticmethod
    def create_default() -> "SuperChunkLLMAdapter":
        cfg = SuperChunkConfig.from_global_settings()
        client = UnifiedLLMClient()
        return SuperChunkLLMAdapter(config=cfg, client=client)

    def _with_token_budget(self, prompt: str, estimated_output_tokens: int) -> str:
        # Present budgets explicitly inside the prompt to reduce overruns
        window = self.config.get_window()
        input_budget = window.max_tokens
        output_budget = max(256, min(2048, estimated_output_tokens))
        header = (
            f"Token budgets — input: <= {input_budget} tokens; output: <= {output_budget} tokens. "
            "Respect budgets strictly."
        )
        return header + "\n\n" + prompt

    def _require_exact_count(self, base_prompt: str, count: int) -> str:
        return base_prompt + f"\n\nReturn exactly {count} items and STOP."

    def _parse_json(self, content: str) -> Any:
        # Extract first JSON object/array from content, if the model adds text
        content = content.strip()
        first_brace = content.find("{")
        first_bracket = content.find("[")
        idx = min(x for x in [first_brace, first_bracket] if x != -1) if (
            first_brace != -1 or first_bracket != -1
        ) else -1
        if idx > 0:
            content = content[idx:]
        return json.loads(content)

    def _call_and_validate(self, prompt: str, schema: Type[T]) -> T:
        response = self.client.generate(prompt)
        data = self._parse_json(response.content)
        if isinstance(data, list):
            # For list schemas, validate each item and return list type if applicable
            return [schema.model_validate(item) for item in data]  # type: ignore[return-value]
        return schema.model_validate(data)  # type: ignore[return-value]

    # Public helpers for extractors (exact counts enforced by caller)
    def extract_claims(self, prompt: str, count: int, estimated_output_tokens: int = 800):
        final_prompt = self._with_token_budget(self._require_exact_count(prompt, count), estimated_output_tokens)
        return self._call_and_validate(final_prompt, ClaimItem)

    def extract_contradictions(self, prompt: str, max_count: int, estimated_output_tokens: int = 400):
        final_prompt = self._with_token_budget(self._require_exact_count(prompt, max_count), estimated_output_tokens)
        return self._call_and_validate(final_prompt, LocalContradictionItem)

    def extract_jargon(self, prompt: str, count: int, estimated_output_tokens: int = 400):
        final_prompt = self._with_token_budget(self._require_exact_count(prompt, count), estimated_output_tokens)
        return self._call_and_validate(final_prompt, JargonItem)
