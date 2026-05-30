"""Parse the provided ``column_descriptions.txt`` into a structured schema catalog
and render an LLM-facing prompt. The per-column "Model Notes" carry the crucial
SQL hints (LOINC over raw text, null sentinels, ENC_TYPE='IP', etc.), so we feed
them to the model verbatim."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import config


@dataclass
class Column:
    name: str
    brief: str
    notes: str


@dataclass
class Table:
    name: str  # without .csv extension, e.g. "DEMOGRAPHIC"
    file: str  # original file name, e.g. "DEMOGRAPHIC.csv"
    description: str
    columns: list[Column] = field(default_factory=list)


def parse_schema(path: str | Path | None = None) -> dict[str, Table]:
    """Parse the column-descriptions document into ``{TABLE_NAME: Table}``."""
    path = Path(path or config.SCHEMA_DOC)
    text = path.read_text(encoding="utf-8-sig")  # strip BOM if present
    lines = text.splitlines()

    tables: dict[str, Table] = {}
    current: Table | None = None
    in_columns = False

    for raw in lines:
        line = raw.strip()
        if not line:
            continue

        if line.startswith("File Name:"):
            file = line.split(":", 1)[1].strip()
            name = file[:-4] if file.lower().endswith(".csv") else file
            current = Table(name=name, file=file, description="")
            tables[name] = current
            in_columns = False
            continue

        if current is None:
            continue

        if line.startswith("Description:"):
            current.description = line.split(":", 1)[1].strip()
            continue

        # Header row that introduces the column table.
        if line.lower().startswith("column name;"):
            in_columns = True
            continue

        if in_columns and ";" in line:
            parts = [p.strip() for p in line.split(";")]
            # name; brief; notes  (notes may itself contain extra ';' -> rejoin)
            name = parts[0]
            brief = parts[1] if len(parts) > 1 else ""
            notes = "; ".join(parts[2:]) if len(parts) > 2 else ""
            if name:
                current.columns.append(Column(name=name, brief=brief, notes=notes))

    return tables


# Columns we add to NOTE that are not in the structured-data doc (we define the
# note layout ourselves). Documented here so schema_prompt can advertise it.
NOTE_TABLE = Table(
    name="NOTE",
    file="NOTE.csv",
    description=(
        "Free-text clinical notes authored by five professions (MD, RN, OT, PT, "
        "SLP). Use the semantic-search tab for content search; this table is "
        "joinable for cohort/timeline queries."
    ),
    columns=[
        Column("PATID", "Unique Patient Identifier", "Foreign Key to the infant."),
        Column("ENCOUNTERID", "Hospital stay identifier", "Joins to ENCOUNTER."),
        Column("NOTEID", "Unique note identifier", "Primary Key for this table."),
        Column("NOTE_DATE", "Date the note was authored", "Use for timelines."),
        Column(
            "PROVIDER_TYPE",
            "Authoring profession",
            "One of MD, RN, OT, PT, SLP.",
        ),
        Column("NOTE_TEXT", "Full free-text note body", "Long text; embedded for search."),
    ],
)


def schema_prompt(tables: dict[str, Table] | None = None, include_note: bool = True) -> str:
    """Render a compact, model-friendly schema description."""
    tables = tables or parse_schema()
    ordered = dict(tables)
    if include_note and "NOTE" not in ordered:
        ordered["NOTE"] = NOTE_TABLE

    out: list[str] = []
    for t in ordered.values():
        out.append(f"TABLE {t.name}  -- {t.description}")
        for c in t.columns:
            hint = f"  -- {c.brief}"
            if c.notes:
                hint += f" | NOTE: {c.notes}"
            out.append(f"    {c.name}{hint}")
        out.append("")
    return "\n".join(out).strip()


if __name__ == "__main__":  # pragma: no cover - manual inspection
    print(schema_prompt())
