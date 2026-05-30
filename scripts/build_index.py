#!/usr/bin/env python
"""One-shot build: data -> DuckDB -> FAISS note index.

By default it uses the **real** MU NICU drop at ``config.REAL_DIR``
(``/media/data/caidf_data/MU/NICU``). If that directory is absent, or with
``--synthetic``, it falls back to the synthetic generator (for demos / off the
hackathon server).

Usage:
    python scripts/build_index.py                 # real data (default)
    python scripts/build_index.py --synthetic     # synthetic demo data
    python scripts/build_index.py --skip-embed    # data + DuckDB only (no Ollama)
    python scripts/build_index.py --max-notes 2000  # cap notes embedded (random rows)

    # Cohort mode: embed the *full* note history of patients who each have
    # enough notes -> coherent longitudinal data for timelines / similarity.
    python scripts/build_index.py --cohort-patients 100 --min-notes 50

The embedding step needs the local Ollama server (config.EMBED_MODEL).
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
    ap.add_argument("--synthetic", action="store_true",
                    help="Use the synthetic generator instead of the real drop.")
    ap.add_argument("--patients", type=int, default=200, help="(synthetic only)")
    ap.add_argument("--seed", type=int, default=7, help="(synthetic only)")
    ap.add_argument("--skip-embed", action="store_true",
                    help="Skip the FAISS/embedding step (no Ollama needed).")
    ap.add_argument("--max-notes", type=int, default=None,
                    help="Cap how many notes are embedded, sampled as random rows.")
    ap.add_argument("--cohort-patients", type=int, default=None,
                    help="Embed the full note history of this many patients "
                         "(each with >= --min-notes notes). Overrides --max-notes.")
    ap.add_argument("--min-notes", type=int, default=50,
                    help="Min notes a patient must have to join the cohort "
                         "(used with --cohort-patients).")
    args = ap.parse_args()

    config.ensure_dirs()
    use_real = not args.synthetic and (config.REAL_DIR / config.STRUCTURED_SUBDIR).is_dir()

    if use_real:
        print(f"1/2  Ingesting REAL MU NICU data from {config.REAL_DIR} ...")
        db = ingest.build_real()
    else:
        if not args.synthetic:
            print(f"     (real data not found at {config.REAL_DIR}; using synthetic)")
        print("1/2  Generating synthetic MU NICU data ...")
        frames = synth.generate(n_patients=args.patients, seed=args.seed)
        synth.write_csvs(frames)
        print(f"     wrote {len(frames)} CSVs to {config.RAW_DIR}")
        db = ingest.build()
    print(f"     DuckDB: {db}")

    if args.skip_embed:
        print("2/2  Skipping embeddings (--skip-embed).")
        return 0

    print(f"2/2  Embedding notes with '{config.EMBED_MODEL}' and building FAISS ...")
    from robocop import notes_index  # local import so --skip-embed avoids faiss cost
    con = ingest.connect(db)
    try:
        if args.cohort_patients:
            notes = _select_cohort_notes(
                con, n_patients=args.cohort_patients, min_notes=args.min_notes
            )
        else:
            sql = "SELECT * FROM mu_nicu.NOTE WHERE NOTE_TEXT IS NOT NULL"
            if args.max_notes:
                sql += f" USING SAMPLE {int(args.max_notes)} ROWS"
            notes = con.execute(sql).fetchdf()
        if notes.empty:
            print("     no notes to embed; skipping index.")
            return 0
        idx = notes_index.NotesIndex.build(notes)
    finally:
        con.close()
    out = idx.save()
    print(f"     indexed {idx.index.ntotal} chunks from {len(notes)} notes -> {out}")
    return 0


def _select_cohort_notes(con, n_patients: int, min_notes: int):
    """Pick ``n_patients`` patients that each have >= ``min_notes`` notes and
    return *all* of their notes, so each patient's history is complete.

    Patients are ranked by note count (richest histories first) for a
    deterministic, signal-dense demo cohort.
    """
    chosen = con.execute(
        """
        WITH counts AS (
            SELECT PATID, count(*) AS n
            FROM mu_nicu.NOTE
            WHERE NOTE_TEXT IS NOT NULL AND PATID IS NOT NULL
            GROUP BY PATID
            HAVING count(*) >= ?
        )
        SELECT PATID, n FROM counts ORDER BY n DESC, PATID LIMIT ?
        """,
        [int(min_notes), int(n_patients)],
    ).fetchdf()

    if chosen.empty:
        print(f"     no patients have >= {min_notes} notes; nothing to embed.")
        return chosen.iloc[0:0]

    patids = chosen["PATID"].tolist()
    total_notes = int(chosen["n"].sum())
    print(
        f"     cohort: {len(patids)} patients with >= {min_notes} notes "
        f"({total_notes} notes total; "
        f"{chosen['n'].min()}-{chosen['n'].max()} per patient)"
    )
    placeholders = ", ".join("?" for _ in patids)
    notes = con.execute(
        f"SELECT * FROM mu_nicu.NOTE "
        f"WHERE NOTE_TEXT IS NOT NULL AND PATID IN ({placeholders})",
        patids,
    ).fetchdf()
    return notes


if __name__ == "__main__":
    raise SystemExit(main())
