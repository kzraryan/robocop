#!/usr/bin/env python
"""One-shot build: synthetic data -> DuckDB -> FAISS note index.

Usage:
    python scripts/build_index.py [--patients N] [--seed S] [--skip-embed]

The embedding step needs the local Ollama server (config.EMBED_MODEL). Pass
``--skip-embed`` to generate data + DuckDB only (e.g. on a box without Ollama).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as a plain script: add ../src to the path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from robocop import config, ingest, synth  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--patients", type=int, default=150)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--skip-embed", action="store_true",
                    help="Skip the FAISS/embedding step (no Ollama needed).")
    args = ap.parse_args()

    config.ensure_dirs()

    print("1/3  Generating synthetic MU NICU data ...")
    frames = synth.generate(n_patients=args.patients, seed=args.seed)
    synth.write_csvs(frames)
    print(f"     wrote {len(frames)} CSVs to {config.RAW_DIR}")

    print("2/3  Building DuckDB ...")
    db = ingest.build()
    print(f"     {db}")

    if args.skip_embed:
        print("3/3  Skipping embeddings (--skip-embed).")
        return 0

    print(f"3/3  Embedding notes with '{config.EMBED_MODEL}' and building FAISS ...")
    from robocop import notes_index  # imported here so --skip-embed avoids faiss import cost
    con = ingest.connect(db)
    try:
        idx = notes_index.build_from_duckdb(con)
    finally:
        con.close()
    out = idx.save()
    print(f"     indexed {idx.index.ntotal} chunks -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
