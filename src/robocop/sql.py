import re

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


def note_catalog(con: duckdb.DuckDBPyConnection, site: str) -> pd.DataFrame:
    """Note ids + lengths + source file, without loading the text column."""
    files = data.note_files(site)
    id_col, text_col = note_columns(con, site)
    id_expr = f'"{id_col}" AS note_id' if id_col else "row_number() OVER () AS note_id"
    return con.execute(
        f'SELECT {id_expr}, length("{text_col}") AS note_len, '
        f"parse_filename(filename) AS source_file "
        f"FROM read_csv_auto({_file_list(files)}, filename=true, "
        f"union_by_name=true, all_varchar=true)"
    ).df()


def get_note(con: duckdb.DuckDBPyConnection, site: str, note_id: str) -> str:
    files = data.note_files(site)
    id_col, text_col = note_columns(con, site)
    if not id_col:
        raise ValueError("Notes have no id column to look up by.")
    row = con.execute(
        f'SELECT "{text_col}" FROM read_csv_auto({_file_list(files)}, '
        f'union_by_name=true, all_varchar=true) WHERE "{id_col}" = ? LIMIT 1',
        [str(note_id)],
    ).fetchone()
    return row[0] if row else ""
