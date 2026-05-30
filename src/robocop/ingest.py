"""Load MU NICU data into a DuckDB database.

Two entry points:
- ``build()``       loads tidy CSVs from a flat dir (the synthetic generator),
                    including a ready-made ``NOTE.csv``.
- ``build_real()``  loads the real server drop: structured tables from
                    ``STRUCTURED_DATA_V1/`` (handling the ``DIAGONSIS`` typo) and
                    *assembles* ``mu_nicu.NOTE`` from the split note-text files
                    plus the NICU_*_METADATA / EVENTS / PROVIDERS sidecar files.

Both produce the same ``mu_nicu`` views, so every downstream module is agnostic
to the source. Everything is loaded as VARCHAR so null sentinels (``/n``, ``\\N``)
survive; numeric casting happens downstream via ``TRY_CAST`` / sentinel filters.
"""

from __future__ import annotations

import re
from pathlib import Path

import duckdb

from . import config

# The 11 documented structured tables (NOTE is handled separately).
STRUCTURED_TABLES = [
    "DEMOGRAPHIC", "ENCOUNTER", "DIAGNOSIS", "CONDITION", "LAB_RESULT_CM",
    "PRESCRIBING", "PROCEDURES", "VITAL", "OBS_CLIN_NICU_ENTERAL_GI",
    "OBS_CLIN_NICU_PAIN_SCORES", "OBS_CLIN_NICU_VENT",
]
TABLES = STRUCTURED_TABLES + ["NOTE"]

# Real filename aliases (case-insensitive). DIAGNOSIS is misspelled in the drop.
FILE_ALIASES = {
    "DIAGNOSIS": ["DIAGNOSIS.csv", "DIAGONSIS.csv"],
}

# Column-detection patterns by role (most specific first).
ROLE_PATTERNS = {
    "noteid": [r"^note_?id$", r"note.*id", r"^id$"],
    "text": [r"^deid_note_release$", r"^note_text$", r"^note$", r"^text$",
             r"deid.*note", r"note.*text", r"clinical.*note"],
    "patid": [r"^pat_?id$", r"^patient_?id$", r"pat.*id", r"patient"],
    "date": [r"note.*date", r"service.*date", r"event.*date", r"encounter.*date",
             r"^date$", r".*datetime.*", r".*dttm.*", r".*date.*"],
    "provider_type": [r"provider.*type", r"prov.*type", r"profession",
                      r"discipline", r"specialt", r"^role$", r".*role.*"],
    "provider_id": [r"provider.*id", r"prov.*id", r"^provider$", r"author.*id"],
    "encounter": [r"^encounter_?id$", r"enc.*id", r"encounter"],
}


# --- helpers --------------------------------------------------------------
def _columns(con, schema: str, table: str) -> list[str]:
    # PRAGMA table_info columns: cid, name, type, ... -> name is index 1.
    return [r[1] for r in con.execute(f'PRAGMA table_info("{schema}"."{table}")').fetchall()]


def detect_col(columns: list[str], role: str, override: str = "") -> str | None:
    """Return the column best matching ``role`` (override wins; else regex)."""
    if override and override in columns:
        return override
    for pat in ROLE_PATTERNS[role]:
        rx = re.compile(pat, re.IGNORECASE)
        for c in columns:                       # exact-ish first
            if rx.fullmatch(c):
                return c
        for c in columns:                       # then substring
            if rx.search(c):
                return c
    return None


def resolve_file(directory: Path, table: str) -> Path | None:
    """Find a table's CSV (alias-aware, case-insensitive)."""
    candidates = FILE_ALIASES.get(table, [f"{table}.csv"])
    existing = {p.name.lower(): p for p in directory.glob("*.csv")}
    for cand in candidates:
        if cand.lower() in existing:
            return existing[cand.lower()]
    return None


def _load_view(con, table: str, csv: Path) -> int:
    """Load one CSV into raw.<table> + create the mu_nicu.<table> view."""
    con.execute(
        f'CREATE OR REPLACE TABLE raw."{table}" AS '
        f"SELECT * FROM read_csv_auto(?, all_varchar=true, header=true, "
        f"ignore_errors=true, sample_size=-1)",
        [str(csv)],
    )
    cols = _columns(con, "raw", table)
    preds = []
    if "SITE" in cols:
        preds.append(f"SITE = '{config.SITE}'")
    if "COHORT" in cols:
        preds.append(f"COHORT = '{config.COHORT}'")
    where = (" WHERE " + " AND ".join(preds)) if preds else ""
    con.execute(f'CREATE OR REPLACE VIEW mu_nicu."{table}" AS '
                f'SELECT * FROM raw."{table}"{where}')
    return con.execute(f'SELECT count(*) FROM mu_nicu."{table}"').fetchone()[0]


def _fresh_db(db_path: Path) -> duckdb.DuckDBPyConnection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = duckdb.connect(str(db_path))
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    con.execute("CREATE SCHEMA IF NOT EXISTS mu_nicu")
    return con


# --- synthetic / flat-dir build -------------------------------------------
def build(raw_dir: Path | None = None, db_path: Path | None = None) -> Path:
    raw_dir = Path(raw_dir or config.RAW_DIR)
    db_path = Path(db_path or config.DUCKDB_PATH)
    con = _fresh_db(db_path)
    for name in TABLES:
        csv = raw_dir / f"{name}.csv"
        if csv.exists():
            _load_view(con, name, csv)
    con.close()
    return db_path


# --- real server-drop build -----------------------------------------------
def build_real(real_dir: Path | None = None, db_path: Path | None = None,
               verbose: bool = True) -> Path:
    real_dir = Path(real_dir or config.REAL_DIR)
    db_path = Path(db_path or config.DUCKDB_PATH)
    structured = real_dir / config.STRUCTURED_SUBDIR
    if not structured.is_dir():
        raise FileNotFoundError(
            f"Structured data dir not found: {structured}. "
            "Set ROBOCOP_REAL_DIR to the MU/NICU root."
        )
    con = _fresh_db(db_path)

    for name in STRUCTURED_TABLES:
        csv = resolve_file(structured, name)
        if csv is None:
            if verbose:
                print(f"  ! missing {name} (looked for {FILE_ALIASES.get(name, [name + '.csv'])})")
            continue
        n = _load_view(con, name, csv)
        if verbose:
            print(f"  {name:28s} {n:8d} rows  <- {csv.name}")

    _assemble_notes(con, real_dir, verbose=verbose)
    con.close()
    return db_path


def _assemble_notes(con, real_dir: Path, verbose: bool = True) -> None:
    """Build mu_nicu.NOTE from split note-text files + sidecar metadata."""
    notes_dir = real_dir / config.NOTES_SUBDIR
    files = sorted(notes_dir.glob("*.csv")) if notes_dir.is_dir() else []
    if not files:
        if verbose:
            print(f"  ! no note-text files under {notes_dir}; NOTE will be empty")
        con.execute(
            "CREATE OR REPLACE VIEW mu_nicu.NOTE AS SELECT "
            "NULL::VARCHAR PATID, NULL::VARCHAR ENCOUNTERID, NULL::VARCHAR NOTEID, "
            "NULL::VARCHAR NOTE_DATE, NULL::VARCHAR PROVIDER_TYPE, "
            "NULL::VARCHAR NOTE_TEXT WHERE 1=0"
        )
        return

    # 1) union all note-text shards
    con.execute(
        "CREATE OR REPLACE TABLE raw.NOTE_TEXT AS SELECT * FROM read_csv_auto(?, "
        "union_by_name=true, all_varchar=true, header=true, ignore_errors=true, "
        "filename=true, sample_size=-1)",
        [str(notes_dir / "*.csv")],
    )
    tcols = [c for c in _columns(con, "raw", "NOTE_TEXT") if c != "filename"]
    id_col = detect_col(tcols, "noteid", config.NOTE_COL_OVERRIDES["noteid"])
    text_col = detect_col(tcols, "text", config.NOTE_COL_OVERRIDES["text"])
    if (id_col is None or text_col is None) and len(tcols) == 2:
        id_col, text_col = id_col or tcols[0], text_col or tcols[1]
    if id_col is None or text_col is None:
        raise ValueError(f"Could not detect NOTE_ID/text columns in {tcols}. "
                         "Set ROBOCOP_NOTE_ID_COL / ROBOCOP_NOTE_TEXT_COL.")
    con.execute(
        f'CREATE OR REPLACE TABLE raw.NOTE_TEXT_N AS '
        f'SELECT CAST("{id_col}" AS VARCHAR) NOTEID, "{text_col}" NOTE_TEXT '
        f'FROM raw.NOTE_TEXT'
    )
    if verbose:
        n_txt = con.execute("SELECT count(*) FROM raw.NOTE_TEXT_N").fetchone()[0]
        print(f"  NOTE text: {n_txt} rows from {len(files)} file(s) "
              f"(id='{id_col}', text='{text_col}')")

    # 2) merge sidecar metadata, coalescing detected fields onto NOTEID
    meta = _build_note_meta(con, real_dir, verbose=verbose)

    # 3) final canonical NOTE view
    if meta:
        con.execute(
            "CREATE OR REPLACE VIEW mu_nicu.NOTE AS SELECT "
            "m.PATID, m.ENCOUNTERID, t.NOTEID, m.NOTE_DATE, "
            "COALESCE(m.PROVIDER_TYPE, 'Unknown') PROVIDER_TYPE, t.NOTE_TEXT "
            "FROM raw.NOTE_TEXT_N t LEFT JOIN raw.NOTE_META m USING (NOTEID)"
        )
    else:
        con.execute(
            "CREATE OR REPLACE VIEW mu_nicu.NOTE AS SELECT "
            "NULL::VARCHAR PATID, NULL::VARCHAR ENCOUNTERID, NOTEID, "
            "NULL::VARCHAR NOTE_DATE, 'Unknown' PROVIDER_TYPE, NOTE_TEXT "
            "FROM raw.NOTE_TEXT_N"
        )
    if verbose:
        n = con.execute("SELECT count(*) FROM mu_nicu.NOTE").fetchone()[0]
        miss = con.execute("SELECT count(*) FROM mu_nicu.NOTE WHERE PATID IS NULL").fetchone()[0]
        print(f"  mu_nicu.NOTE: {n} rows ({miss} without a linked PATID)")


def _build_note_meta(con, real_dir: Path, verbose: bool = True):
    """Assemble raw.NOTE_META(NOTEID, PATID, ENCOUNTERID, NOTE_DATE, PROVIDER_TYPE)
    from the sidecar files. Returns the detected mapping (truthy) or None."""
    import pandas as pd

    ov = config.NOTE_COL_OVERRIDES
    merged: "pd.DataFrame | None" = None
    provider_map: dict[str, str] = {}
    detected: dict[str, str] = {}

    for fname in config.NOTE_METADATA_FILES:
        path = _ci_file(real_dir, fname)
        if path is None:
            continue
        df = con.execute(
            "SELECT * FROM read_csv_auto(?, all_varchar=true, header=true, "
            "ignore_errors=true, sample_size=-1)", [str(path)]
        ).fetchdf()
        cols = list(df.columns)
        nid = detect_col(cols, "noteid", ov["noteid"])

        # a provider lookup table (id -> type) if this file looks like PROVIDERS
        pid = detect_col(cols, "provider_id")
        ptype = detect_col(cols, "provider_type", ov["provider"])
        if pid and ptype and "PROVIDER" in fname.upper():
            provider_map = dict(zip(df[pid].astype(str), df[ptype].astype(str)))

        if nid is None:
            continue
        keep = {"NOTEID": df[nid].astype(str)}
        patid = detect_col(cols, "patid", ov["patid"])
        date = detect_col(cols, "date", ov["date"])
        enc = detect_col(cols, "encounter", ov["encounter"])
        if patid:
            keep["PATID"] = df[patid]; detected["patid"] = f"{fname}:{patid}"
        if date:
            keep["NOTE_DATE"] = df[date]; detected["date"] = f"{fname}:{date}"
        if enc:
            keep["ENCOUNTERID"] = df[enc]; detected["encounter"] = f"{fname}:{enc}"
        if ptype:
            keep["PROVIDER_TYPE"] = df[ptype]; detected["provider_type"] = f"{fname}:{ptype}"
        elif pid:
            keep["_PROVIDER_ID"] = df[pid].astype(str); detected["provider_id"] = f"{fname}:{pid}"

        part = pd.DataFrame(keep).drop_duplicates("NOTEID")
        merged = part if merged is None else merged.merge(part, on="NOTEID", how="outer",
                                                          suffixes=("", "_y"))
        # coalesce duplicate columns from outer merges
        for col in [c for c in merged.columns if c.endswith("_y")]:
            base = col[:-2]
            merged[base] = merged[base].combine_first(merged[col])
            merged = merged.drop(columns=col)

    if merged is None:
        return None

    # resolve provider type from id if needed
    if "PROVIDER_TYPE" not in merged.columns and "_PROVIDER_ID" in merged.columns and provider_map:
        merged["PROVIDER_TYPE"] = merged["_PROVIDER_ID"].map(provider_map)
    for needed in ("PATID", "ENCOUNTERID", "NOTE_DATE", "PROVIDER_TYPE"):
        if needed not in merged.columns:
            merged[needed] = None
    merged = merged[["NOTEID", "PATID", "ENCOUNTERID", "NOTE_DATE", "PROVIDER_TYPE"]]

    con.register("note_meta_df", merged)
    con.execute("CREATE OR REPLACE TABLE raw.NOTE_META AS SELECT * FROM note_meta_df")
    con.unregister("note_meta_df")
    if verbose:
        print(f"  NOTE metadata mapping: {detected or '(none detected)'}")
    return detected or {"noteid": "ok"}


def _ci_file(directory: Path, name: str) -> Path | None:
    existing = {p.name.lower(): p for p in directory.glob("*.csv")}
    return existing.get(name.lower())


# --- connection -----------------------------------------------------------
def connect(db_path: Path | None = None, read_only: bool = True) -> duckdb.DuckDBPyConnection:
    """Open a (default read-only) connection with ``mu_nicu`` as the search path."""
    db_path = Path(db_path or config.DUCKDB_PATH)
    con = duckdb.connect(str(db_path), read_only=read_only)
    con.execute("SET search_path = 'mu_nicu'")
    return con


def main() -> None:
    config.ensure_dirs()
    db = build()
    con = connect(db)
    print(f"Built DuckDB at {db}")
    for name in TABLES:
        try:
            n = con.execute(f'SELECT count(*) FROM mu_nicu."{name}"').fetchone()[0]
            print(f"  mu_nicu.{name:28s} {n:6d} rows")
        except duckdb.Error:
            pass
    con.close()


if __name__ == "__main__":  # pragma: no cover
    main()
