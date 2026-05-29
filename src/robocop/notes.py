_ID_CANDIDATES = ("NOTE_ID", "note_id", "noteid", "ID", "id")
_TEXT_CANDIDATES = (
    "DEID_NOTE_RELEASE",
    "NOTE",
    "note",
    "note_text",
    "TEXT",
    "text",
    "deid_note",
)


def note_column_names(columns) -> tuple[str | None, str | None]:
    """Best-effort (id_column, text_column) from a list of column names."""
    cols = list(columns)
    id_col = next((c for c in _ID_CANDIDATES if c in cols), None)
    text_col = next((c for c in _TEXT_CANDIDATES if c in cols), None)
    return id_col, text_col
