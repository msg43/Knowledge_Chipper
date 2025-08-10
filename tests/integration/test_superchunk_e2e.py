from __future__ import annotations

from pathlib import Path

from knowledge_system.superchunk.config import SuperChunkConfig
from knowledge_system.superchunk.runner import Runner


def test_superchunk_e2e_tmp(tmp_path: Path):
    paragraphs = [
        "Alpha. Beta continues.",
        "Gamma is here and continues. Delta ends.",
        "Hotspot should not be split. Keep together.",
    ]
    artifacts = tmp_path / "artifacts"
    cfg = SuperChunkConfig.from_global_settings()
    Runner(config=cfg, artifacts_dir=artifacts).run(paragraphs)

    # Assert key artifacts exist
    for fname in [
        "global_context.json",
        "chunking_decisions.json",
        "final.md",
        "scorecard.json",
    ]:
        assert (artifacts / fname).exists()
