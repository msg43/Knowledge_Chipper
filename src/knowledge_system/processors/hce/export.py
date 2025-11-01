from pathlib import Path

from .io_utils import write_jsonl, write_md
from .types import PipelineOutputs


def export_all(outdir: Path, bundle: PipelineOutputs):
    outdir.mkdir(parents=True, exist_ok=True)
    write_jsonl(
        outdir / f"claims_{bundle.source_id}.jsonl",
        [c.model_dump() for c in bundle.claims],
    )
    write_md(outdir / f"claims_{bundle.source_id}.md", bundle.claims)
    rel_lines = ["graph LR"]
    for r in bundle.relations:
        rel_lines.append(
            f'  "{r.source_claim_id}" -- {r.type} --> "{r.target_claim_id}"'
        )
    (outdir / f"relations_{bundle.source_id}.mmd").write_text("\n".join(rel_lines))
    (outdir / f"people_{bundle.source_id}.md").write_text(
        "\n".join([f"- {p.normalized or p.surface} [{p.t0}]" for p in bundle.people])
    )
    (outdir / f"concepts_{bundle.source_id}.md").write_text(
        "\n".join(
            [f"- {m.name} [{m.first_mention_ts or '?'}]" for m in bundle.concepts]
        )
    )
    (outdir / f"glossary_{bundle.source_id}.md").write_text(
        "\n".join([f"- {t.term}" for t in bundle.jargon])
    )
