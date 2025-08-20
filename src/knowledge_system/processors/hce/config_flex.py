from typing import Literal

from pydantic import BaseModel

ModelURI = (
    str  # e.g., "ollama://qwen2.5:14b", "openai://gpt-5-large", "local://llama.cpp?q4"
)


class StageModelConfig(BaseModel):
    miner: ModelURI = "ollama://qwen2.5:14b-instruct"
    heavy_miner: ModelURI | None = None
    judge: ModelURI = "openai://gpt-5-large"
    embedder: ModelURI = "local://bge-small-en-v1.5"
    reranker: ModelURI = "local://bge-reranker-base"
    people_disambiguator: ModelURI | None = None
    nli: ModelURI | None = "local://nli-mini"


class RerankPolicy(BaseModel):
    mode: Literal["adaptive", "threshold", "topk"] = "adaptive"
    base_density: float = 1.2
    min_keep: int = 25
    max_keep: int = 400
    percentile_floor: float = 0.55


class PipelineConfigFlex(BaseModel):
    models: StageModelConfig = StageModelConfig()
    rerank: RerankPolicy = RerankPolicy()
    use_skim: bool = True
