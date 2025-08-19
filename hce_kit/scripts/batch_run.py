import json
import os
from pathlib import Path

from scripts.run_episode import main as run_one


def main(input_dir: str, outdir: str):
    for p in Path(input_dir).glob("*.json"):
        run_one(str(p), outdir)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("input_dir")
    ap.add_argument("--outdir", default="./out")
    a = ap.parse_args()
    main(a.input_dir, a.outdir)
