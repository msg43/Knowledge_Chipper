from pathlib import Path
from typing import List

from .models.llm_any import AnyLLM
from .types import Milestone, Segment


class Skimmer:
    def __init__(self, llm: AnyLLM, prompt_path: Path):
        self.llm = llm
        self.template = prompt_path.read_text()

    def skim(self, episode_id: str, segments: list[Segment]) -> list[Milestone]:
        # TODO: chunk by time, call llm.generate_json with skim prompt
        return []
