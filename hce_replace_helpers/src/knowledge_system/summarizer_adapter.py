"""Compatibility adapter that replaces the legacy summarizer with HCE while preserving the public API."""

from typing import Any, Dict

# Expect these modules to exist in your HCE package
# Adjust imports to match your repo structure.
try:
    from src.knowledge_system.hce.export import export_all
    from src.knowledge_system.hce.pipeline import run_episode
    from src.knowledge_system.hce.storage_sqlite import (
        ensure_schema,
        open_db,
        upsert_pipeline_outputs,
    )
except Exception:
    # Placeholder to let Cursor wire these modules during integration
    def run_episode(episode_bundle, **kwargs):
        raise NotImplementedError

    def open_db(path):
        raise NotImplementedError

    def ensure_schema(conn):
        raise NotImplementedError

    def upsert_pipeline_outputs(conn, outputs, **kwargs):
        raise NotImplementedError

    def export_all(outdir, outputs):
        raise NotImplementedError


def summarize_episode(
    episode_bundle: Any, *, db_path: str, outdir: str, **kwargs
) -> dict[str, Any]:
    """Signature mirrors the legacy entrypoint; delegates to HCE and preserves outputs.


    Returns a dict with episode_id and file paths the UI expects."""
    outputs = run_episode(episode_bundle, **kwargs)  # should return PipelineOutputs
    conn = open_db(db_path)
    ensure_schema(conn)
    upsert_pipeline_outputs(conn, outputs)
    export_all(outdir, outputs)
    return {
        "episode_id": getattr(outputs, "episode_id", None),
        "files": {
            "claims_jsonl": f"{outdir}/claims_{outputs.episode_id}.jsonl",
            "claims_md": f"{outdir}/claims_{outputs.episode_id}.md",
            "relations": f"{outdir}/relations_{outputs.episode_id}.mmd",
        },
    }
