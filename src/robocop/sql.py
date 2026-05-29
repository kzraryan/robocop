import os
import re
from pathlib import Path

import duckdb
import pandas as pd

from . import data, notes


def connect() -> duckdb.DuckDBPyConnection:
    return duckdb.connect()


def _sql_str(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _file_list(paths) -> str:
    return "[" + ", ".join(_sql_str(str(p)) for p in paths) + "]"


def _view_name(stem: str, taken: set[str]) -> str:
    name = re.sub(r"[^0-9a-zA-Z]+", "_", stem).strip("_").lower() or "table"
    if name[0].isdigit():
        name = "t_" + name
    base, i = name, 2
    while name in taken:
        name = f"{base}_{i}"
        i += 1
    taken.add(name)
    return name


def register_site(con: duckdb.DuckDBPyConnection, site: str) -> dict[str, str]:
    """Register each structured CSV as a lazy view. Returns {view_name: path}."""
    views: dict[str, str] = {}
    taken: set[str] = set()
    for path in data.structured_files(site):
        if path.suffix.lower() != ".csv":
            continue
        name = _view_name(path.stem, taken)
        con.execute(
            f"CREATE OR REPLACE VIEW {name} AS "
            f"SELECT * FROM read_csv_auto({_sql_str(str(path))}, all_varchar=true)"
        )
        views[name] = str(path)
    return views


def list_views(con: duckdb.DuckDBPyConnection) -> list[str]:
    rows = con.execute(
        "SELECT table_name FROM information_schema.tables ORDER BY table_name"
    ).fetchall()
    return [r[0] for r in rows]


def table_schema(con: duckdb.DuckDBPyConnection, view: str) -> pd.DataFrame:
    return con.execute(f"DESCRIBE {view}").df()


def table_preview(con: duckdb.DuckDBPyConnection, view: str, limit: int = 100) -> pd.DataFrame:
    return con.execute(f"SELECT * FROM {view} LIMIT {int(limit)}").df()


def run(con: duckdb.DuckDBPyConnection, query: str, max_rows: int = 5000) -> pd.DataFrame:
    df = con.execute(query).df()
    return df.head(max_rows) if len(df) > max_rows else df


# --- Notes: load only the catalog, fetch text one note at a time --------------
def note_columns(con: duckdb.DuckDBPyConnection, site: str) -> tuple[str, str]:
    files = data.note_files(site)
    if not files:
        raise FileNotFoundError(f"No note files found for site {site!r}.")
    cols = con.execute(
        f"DESCRIBE SELECT * FROM read_csv_auto({_sql_str(str(files[0]))}, "
        f"all_varchar=true) LIMIT 0"
    ).df()["column_name"].tolist()
    id_col, text_col = notes.note_column_names(cols)
    if text_col is None:
        raise ValueError(f"No note-text column found in: {cols}")
    return id_col, text_col


def _cache_dir() -> Path:
    d = Path(os.environ.get("ROBOCOP_CACHE", Path.home() / ".cache" / "robocop"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def notes_parquet(con: duckdb.DuckDBPyConnection, site: str) -> str:
    """Path to a columnar (Parquet) copy of the site's notes (note_id, note).

    Built once from the heavy CSVs, then reused — so counting, listing ids, and
    fetching a single note are fast (columnar projection + filter, no repeated
    full-CSV parse). Rebuilt automatically if the source files change (their
    mtime is encoded in the filename).
    """
    files = data.note_files(site)
    if not files:
        raise FileNotFoundError(f"No note files found for site {site!r}.")
    sig = int(max(p.stat().st_mtime for p in files))
    out = _cache_dir() / f"{site}_notes_{sig}.parquet"
    if not out.exists():
        id_col, text_col = note_columns(con, site)
        id_expr = f'"{id_col}"' if id_col else "CAST(row_number() OVER () AS VARCHAR)"
        con.execute(
            f'COPY (SELECT {id_expr} AS note_id, "{text_col}" AS note '
            f"FROM read_csv_auto({_file_list(files)}, union_by_name=true, "
            f"all_varchar=true)) TO '{out}' (FORMAT parquet)"
        )
    return str(out)


def note_count(con: duckdb.DuckDBPyConnection, site: str) -> int:
    """Total notes (Parquet row count — metadata only, instant)."""
    return con.execute(
        f"SELECT count(*) FROM read_parquet('{notes_parquet(con, site)}')"
    ).fetchone()[0]


def note_id_at(con: duckdb.DuckDBPyConnection, site: str, index: int) -> str | None:
    """The note id at a 0-based position (for browse/paging)."""
    row = con.execute(
        f"SELECT note_id FROM read_parquet('{notes_parquet(con, site)}') "
        f"LIMIT 1 OFFSET {int(index)}"
    ).fetchone()
    return row[0] if row else None


def search_note_ids(con: duckdb.DuckDBPyConnection, site: str, term: str,
                    limit: int = 50) -> list[str]:
    """Note ids matching a (partial) id string."""
    rows = con.execute(
        f"SELECT note_id FROM read_parquet('{notes_parquet(con, site)}') "
        f"WHERE note_id ILIKE ? ORDER BY note_id LIMIT {int(limit)}",
        [f"%{term}%"],
    ).fetchall()
    return [r[0] for r in rows]


def search_note_text(con: duckdb.DuckDBPyConnection, site: str, term: str,
                     limit: int = 25) -> pd.DataFrame:
    """Notes whose text contains ``term`` — id + a short snippet."""
    return con.execute(
        f"SELECT note_id, substr(note, 1, 200) AS snippet "
        f"FROM read_parquet('{notes_parquet(con, site)}') "
        f"WHERE note ILIKE ? LIMIT {int(limit)}",
        [f"%{term}%"],
    ).df()


def get_note(con: duckdb.DuckDBPyConnection, site: str, note_id: str) -> str:
    """Fetch a single note's text by id (Parquet point lookup)."""
    row = con.execute(
        f"SELECT note FROM read_parquet('{notes_parquet(con, site)}') "
        f"WHERE note_id = ? LIMIT 1",
        [str(note_id)],
    ).fetchone()
    return row[0] if row else ""
