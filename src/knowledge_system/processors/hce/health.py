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

    # Required modules and attributes expected by HCEPipeline
    required = {
        # Functions used directly by pipeline
        "knowledge_system.processors.hce.skim": ["skim_episode"],
        "knowledge_system.processors.hce.miner": ["mine_claims"],
        "knowledge_system.processors.hce.evidence": ["link_evidence"],
        "knowledge_system.processors.hce.rerank": ["rerank_claims"],
        "knowledge_system.processors.hce.router": ["route_claims"],
        "knowledge_system.processors.hce.judge": ["judge_claims"],
        # Optional helpers/classes (if present)
        "knowledge_system.processors.hce.rerank_policy": ["adaptive_keep"],
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
            "HCE is not fully available. Missing symbols: " + ", ".join(missing)
        )
