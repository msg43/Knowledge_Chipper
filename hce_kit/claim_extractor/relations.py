from pathlib import Path
from typing import List

from .models.llm_any import AnyLLM
from .types import Relation, ScoredClaim


class RelationMiner:
    def __init__(self, llm: AnyLLM, prompt_path: Path):
        self.llm = llm
        self.template = prompt_path.read_text()

    def relate(self, claims: list[ScoredClaim]) -> list[Relation]:
        # TODO: pairwise or candidate selection then llm call
        return []
