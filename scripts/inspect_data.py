#!/usr/bin/env python
"""Inspect the real MU NICU drop *on the server* — prints file inventory,
column headers, row counts, and the auto-detected NOTE column mapping so the
note-assembly join can be confirmed.

Privacy: prints only file names, **column headers**, and row counts — never cell
values — so it is safe to share/paste.

Usage:
    python scripts/inspect_data.py [--real-dir /media/data/caidf_data/MU/NICU]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import duckdb  # noqa: E402

from robocop import config, ingest  # noqa: E402


def _headers(con, path: Path) -> list[str]:
    rows = con.execute(
        "DESCRIBE SELECT * FROM read_csv_auto(?, all_varchar=true, header=true, "
        "sample_size=1000) LIMIT 0", [str(path)]
    ).fetchall()
    return [r[0] for r in rows]


def _count(con, glob: str) -> int:
    try:
        return con.execute(
            "SELECT count(*) FROM read_csv_auto(?, all_varchar=true, header=true, "
            "ignore_errors=true, union_by_name=true)", [glob]
        ).fetchone()[0]
    except duckdb.Error as e:
        return -1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--real-dir", default=str(config.REAL_DIR))
    args = ap.parse_args()
    real = Path(args.real_dir)
    con = duckdb.connect()

    print(f"== MU NICU drop: {real} ==\n")
    if not real.exists():
        print("!! path does not exist on this machine.")
        return 1

    print("-- Structured tables (STRUCTURED_DATA_V1/) --")
    structured = real / config.STRUCTURED_SUBDIR
    for name in ingest.STRUCTURED_TABLES:
        csv = ingest.resolve_file(structured, name) if structured.is_dir() else None
        if csv is None:
            print(f"  {name:28s} MISSING")
            continue
        cols = _headers(con, csv)
        print(f"  {name:28s} {_count(con, str(csv)):>9} rows  [{csv.name}]")
        print(f"       cols: {cols}")

    print("\n-- Sidecar metadata files (root) --")
    meta_headers = {}
    for fname in config.NOTE_METADATA_FILES:
        path = ingest._ci_file(real, fname)
        if path is None:
            print(f"  {fname:28s} MISSING")
            continue
        cols = _headers(con, path)
        meta_headers[fname] = cols
        print(f"  {fname:28s} {_count(con, str(path)):>9} rows")
        print(f"       cols: {cols}")

    print(f"\n-- Note text shards ({config.NOTES_SUBDIR}/) --")
    notes_dir = real / config.NOTES_SUBDIR
    shards = sorted(notes_dir.glob("*.csv")) if notes_dir.is_dir() else []
    print(f"  {len(shards)} file(s); total rows: {_count(con, str(notes_dir / '*.csv')) if shards else 0}")
    text_cols = _headers(con, shards[0]) if shards else []
    if shards:
        print(f"  text-shard cols: {text_cols}")

    print("\n-- Auto-detected NOTE mapping --")
    ov = config.NOTE_COL_OVERRIDES
    print(f"  NOTE_ID (text shard):   {ingest.detect_col(text_cols, 'noteid', ov['noteid'])}")
    print(f"  NOTE_TEXT (text shard): {ingest.detect_col(text_cols, 'text', ov['text'])}")
    for fname, cols in meta_headers.items():
        print(f"  [{fname}]")
        print(f"     NOTE_ID:       {ingest.detect_col(cols, 'noteid', ov['noteid'])}")
        print(f"     PATID:         {ingest.detect_col(cols, 'patid', ov['patid'])}")
        print(f"     NOTE_DATE:     {ingest.detect_col(cols, 'date', ov['date'])}")
        print(f"     PROVIDER_TYPE: {ingest.detect_col(cols, 'provider_type', ov['provider'])}")
        print(f"     PROVIDER_ID:   {ingest.detect_col(cols, 'provider_id')}")
        print(f"     ENCOUNTERID:   {ingest.detect_col(cols, 'encounter', ov['encounter'])}")

    print("\nIf any mapping is wrong, set the matching ROBOCOP_NOTE_*_COL env var "
          "(see config.NOTE_COL_OVERRIDES) and re-run build_index.py.")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
