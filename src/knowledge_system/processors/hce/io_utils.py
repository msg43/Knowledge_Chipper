import json
from collections.abc import Iterable
from pathlib import Path

from .types import EpisodeBundle, ScoredClaim


def load_episode(path: Path) -> EpisodeBundle:
    return EpisodeBundle.model_validate_json(path.read_text())


def write_jsonl(path: Path, items: Iterable[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")


def write_md(path: Path, claims: list[ScoredClaim]):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# Claims ({len(claims)})\n"]
    for c in claims:
        ev = c.evidence[0].t0 if c.evidence else "?"
        s = c.scores
        tier = c.tier or "-"
        lines.append(f"- **[{c.claim_type}]** [{ev}] {c.canonical}  (tier {tier})")
        if s:
            lines.append(
                f"  importance {s.get('importance', 0):.2f} · novelty {s.get('novelty', 0):.2f} · controversy {s.get('controversy', 0):.2f} · fragility {s.get('fragility', 0):.2f}"
            )
    path.write_text("\n".join(lines))
