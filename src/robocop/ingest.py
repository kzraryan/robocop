"""Load the MU NICU CSVs into a DuckDB database.

All synthetic rows are already MU NICU, but we keep a thin filtering layer
(``mu_nicu`` schema with one view per table) so that when real, multi-site /
multi-cohort data is dropped into ``data/raw`` the same narrowing applies. The
app then queries the ``mu_nicu`` views.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from . import config

# Tables we expect (structured + NOTE). Order is arbitrary.
TABLES = [
    "DEMOGRAPHIC", "ENCOUNTER", "DIAGNOSIS", "CONDITION", "LAB_RESULT_CM",
    "PRESCRIBING", "PROCEDURES", "VITAL", "OBS_CLIN_NICU_ENTERAL_GI",
    "OBS_CLIN_NICU_PAIN_SCORES", "OBS_CLIN_NICU_VENT", "NOTE",
]


def build(raw_dir: Path | None = None, db_path: Path | None = None) -> Path:
    raw_dir = Path(raw_dir or config.RAW_DIR)
    db_path = Path(db_path or config.DUCKDB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    con = duckdb.connect(str(db_path))
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    con.execute("CREATE SCHEMA IF NOT EXISTS mu_nicu")

    loaded = []
    for name in TABLES:
        csv = raw_dir / f"{name}.csv"
        if not csv.exists():
            continue
        # all_varchar keeps documented null sentinels (/n, //N) intact; casts
        # happen in SQL where needed (the LLM is told about the sentinels).
        con.execute(
            f"CREATE TABLE raw.\"{name}\" AS "
            f"SELECT * FROM read_csv_auto(?, all_varchar=true, header=true)",
            [str(csv)],
        )
        # MU NICU narrowing layer. Real data may carry SITE/COHORT columns; only
        # filter on them when present so this is a no-op for synthetic data.
        cols = {r[0] for r in con.execute(f'PRAGMA table_info("raw"."{name}")').fetchall()}
        preds = []
        if "SITE" in cols:
            preds.append(f"SITE = '{config.SITE}'")
        if "COHORT" in cols:
            preds.append(f"COHORT = '{config.COHORT}'")
        where = (" WHERE " + " AND ".join(preds)) if preds else ""
        con.execute(
            f'CREATE VIEW mu_nicu."{name}" AS SELECT * FROM raw."{name}"{where}'
        )
        loaded.append((name, con.execute(f'SELECT count(*) FROM mu_nicu."{name}"').fetchone()[0]))

    con.close()
    return db_path


def connect(db_path: Path | None = None, read_only: bool = True) -> duckdb.DuckDBPyConnection:
    """Open a (default read-only) connection with ``mu_nicu`` as the search path
    so the LLM/user can reference tables unqualified (e.g. ``DEMOGRAPHIC``)."""
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
