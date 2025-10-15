"""HCE health checks and validation utilities."""

from __future__ import annotations

from importlib import import_module


class HCEValidationError(RuntimeError):
    pass


def validate_hce_or_raise() -> None:
    """Validate that required HCE modules and entry points are available.

    Raises:
        HCEValidationError if any core HCE symbol is missing.
    """
    missing: list[str] = []

    # Required modules and attributes for unified HCE pipeline
    required = {
        # Core unified pipeline modules
        "knowledge_system.processors.hce.unified_miner": [
            "mine_episode_unified",
            "UnifiedMiner",
        ],
        "knowledge_system.processors.hce.flagship_evaluator": [
            "evaluate_claims_flagship",
            "FlagshipEvaluator",
        ],
        "knowledge_system.processors.hce.unified_pipeline": ["UnifiedHCEPipeline"],
        # Core data types
        "knowledge_system.processors.hce.types": [
            "EpisodeBundle",
            "PipelineOutputs",
            "ScoredClaim",
        ],
        "knowledge_system.processors.hce.config_flex": [
            "PipelineConfigFlex",
            "StageModelConfig",
        ],
        # LLM interface
        "knowledge_system.processors.hce.models.llm_system2": ["System2LLM"],
        # Optional modules (if present)
        "knowledge_system.processors.hce.relations": ["RelationMiner"],
    }

    for module_path, attrs in required.items():
        try:
            mod = import_module(module_path)
        except Exception:
            missing.append(module_path)
            continue
        for attr in attrs:
            if not hasattr(mod, attr):
                missing.append(f"{module_path}.{attr}")

    if missing:
        raise HCEValidationError(
            "Unified HCE pipeline is not fully available. Missing symbols: "
            + ", ".join(missing)
        )
