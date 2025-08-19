# HCE Starter Kit (Cursor-Ready)

**What this is:** a drop-in scaffold for Hybrid Claim Extraction with local/cloud flexibility and world-class features.

## How to use with Cursor
1. Unzip into your repo root.
2. Open Cursor → new Chat → paste `/.cursor/prompts/hce-master.txt`.
3. Let Cursor propose integration plan and diffs, then iterate with `/.cursor/prompts/hce-iter-fix.txt`.

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
pytest -q
python scripts/run_episode.py docs/architecture/sample_episode.json --outdir out
```

## Notes
- Backend calls are stubs; wire your model providers (OpenAI/Ollama/etc.) in `models/llm_any.py`, `embedder.py`, `cross_encoder.py`.
- Upgrades A,B,C,D(partial),E,G,H,I are scaffolded as modules.
- Feature flag and adapters should be added in your legacy CLI to call this pipeline when desired.
