from typing import Literal

from pydantic import BaseModel

ModelURI = (
    str  # e.g., "ollama://qwen2.5:14b", "openai://gpt-5-large", "local://llama.cpp?q4"
)


class StageModelConfig(BaseModel):
    miner: ModelURI = "local://llama3.2:latest"
    heavy_miner: ModelURI | None = None
    judge: ModelURI = "local://llama3.2:latest"
    flagship_judge: ModelURI | None = None
    embedder: ModelURI = "all-MiniLM-L6-v2"
    reranker: ModelURI = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    people_disambiguator: ModelURI | None = None
    nli: ModelURI | None = None
    skim: ModelURI | None = None


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
    router_uncertainty_threshold: float = 0.35
    flagship_max_claims_per_file: int | None = None
