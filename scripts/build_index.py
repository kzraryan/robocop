#!/usr/bin/env python
"""One-shot build: data -> DuckDB -> FAISS note index.

By default it uses the **real** MU NICU drop at ``config.REAL_DIR``
(``/media/data/caidf_data/MU/NICU``). If that directory is absent, or with
``--synthetic``, it falls back to the synthetic generator (for demos / off the
hackathon server).

Usage:
    python scripts/build_index.py --synthetic     # synthetic demo data
    python scripts/build_index.py --skip-embed    # data + DuckDB only (no Ollama)
    python scripts/build_index.py --max-notes 2000  # cap notes embedded (random rows)

    # Cohort mode: embed the *full* note history of patients who each have
    # enough notes -> coherent longitudinal data for timelines / similarity.
    python scripts/build_index.py --cohort-patients 10 --min-notes 50
    python scripts/build_index.py --cohort-patients 10 --min-notes 50 --dry-run

To bound real-data embedding volume you must pick one of --cohort-patients,
--max-notes, or --all-notes; otherwise the build refuses to embed the full
(very large) corpus. The embedding step needs Ollama (config.EMBED_MODEL).
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
                    help="Embed the note history of this many patients "
                         "(each with >= --min-notes notes). Overrides --max-notes.")
    ap.add_argument("--min-notes", type=int, default=50,
                    help="Min notes a patient must have to join the cohort "
                         "(used with --cohort-patients).")
    ap.add_argument("--per-patient-cap", type=int, default=None,
                    help="Hard cap on notes embedded per cohort patient "
                         "(earliest notes kept). Bounds total volume.")
    ap.add_argument("--all-notes", action="store_true",
                    help="Explicitly embed the ENTIRE corpus (can be very large).")
    ap.add_argument("--dry-run", action="store_true",
                    help="Select the cohort and print counts, but do not embed.")
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

    # Guard: on real data, refuse to embed the entire corpus unless the scope is
    # made explicit. This prevents a mistyped/omitted flag from silently kicking
    # off a full ~600k-note embedding run.
    scope_given = bool(args.cohort_patients or args.max_notes or args.all_notes)
    if use_real and not scope_given:
        print(
            "     REFUSING to embed the full real corpus (could be hundreds of\n"
            "     thousands of notes). Pick a scope:\n"
            "       --cohort-patients 10 --min-notes 50   (full history of 10 patients)\n"
            "       --max-notes 2000                       (random sample)\n"
            "       --all-notes                            (really embed everything)\n"
            "     or --skip-embed to stop here."
        )
        return 2

    con = ingest.connect(db)
    try:
        if args.cohort_patients:
            notes = _select_cohort_notes(
                con, n_patients=args.cohort_patients, min_notes=args.min_notes,
                per_patient_cap=args.per_patient_cap,
            )
        elif args.max_notes:
            notes = con.execute(
                "SELECT * FROM mu_nicu.NOTE WHERE NOTE_TEXT IS NOT NULL "
                f"USING SAMPLE {int(args.max_notes)} ROWS"
            ).fetchdf()
            print(f"     random sample: {len(notes)} notes (--max-notes {args.max_notes})")
        else:  # --all-notes, or synthetic (small) data
            notes = con.execute(
                "SELECT * FROM mu_nicu.NOTE WHERE NOTE_TEXT IS NOT NULL"
            ).fetchdf()
            print(f"     full corpus: {len(notes)} notes")

        if notes.empty:
            print("     no notes to embed; skipping index.")
            return 0
        if args.dry_run:
            print(f"     [dry-run] would embed {len(notes)} notes; no embeddings built.")
            return 0

        print(f"2/2  Embedding {len(notes)} notes with '{config.EMBED_MODEL}' "
              "and building FAISS ...")
        from robocop import notes_index  # local import so --skip-embed avoids faiss cost
        idx = notes_index.NotesIndex.build(notes)
    finally:
        con.close()
    out = idx.save()
    print(f"     indexed {idx.index.ntotal} chunks from {len(notes)} notes -> {out}")
    return 0


def _select_cohort_notes(con, n_patients: int, min_notes: int,
                         per_patient_cap: int | None = None):
    """Pick ``n_patients`` patients that each have >= ``min_notes`` notes and
    return their notes, so each patient's history is (near-)complete.

    Patients with the *fewest* qualifying notes are taken first: asking for "10
    patients with > 50 notes" yields ~50-note infants, not the few-thousand-note
    outliers, keeping the embedding job small and on-target. ``per_patient_cap``
    optionally trims each history to its earliest N notes as a hard volume bound.
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
        SELECT PATID, n FROM counts ORDER BY n ASC, PATID LIMIT ?
        """,
        [int(min_notes), int(n_patients)],
    ).fetchdf()

    if chosen.empty:
        print(f"     no patients have >= {min_notes} notes; nothing to embed.")
        return chosen.iloc[0:0]
    if len(chosen) < n_patients:
        print(f"     only {len(chosen)} patients have >= {min_notes} notes "
              f"(asked for {n_patients}).")

    patids = chosen["PATID"].tolist()
    placeholders = ", ".join("?" for _ in patids)
    notes = con.execute(
        f"SELECT * FROM mu_nicu.NOTE "
        f"WHERE NOTE_TEXT IS NOT NULL AND PATID IN ({placeholders})",
        patids,
    ).fetchdf()

    if per_patient_cap:
        # Keep each patient's earliest notes (stable, chronological) up to the cap.
        sort_col = "NOTE_DATE" if "NOTE_DATE" in notes.columns else None
        if sort_col:
            notes = notes.sort_values(["PATID", sort_col], kind="stable")
        notes = notes.groupby("PATID", sort=False).head(int(per_patient_cap))

    per = notes.groupby("PATID", sort=False).size()
    print(
        f"     cohort: {len(patids)} patients with >= {min_notes} notes "
        f"-> embedding {len(notes)} notes "
        f"({int(per.min())}-{int(per.max())} per patient"
        + (f", capped at {per_patient_cap}" if per_patient_cap else "")
        + ")"
    )
    return notes


if __name__ == "__main__":
    raise SystemExit(main())
