"""Helpers for the free-text clinical notes.

Light, dependency-free utilities: locate the id/text columns regardless of the
site's naming, basic cleaning, and chunking for retrieval/LLM context.
"""

from __future__ import annotations

import re

import pandas as pd

# Columns we might see for the note id and the note body, across sites.
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

_WS = re.compile(r"[ \t]+")
_MULTINL = re.compile(r"\n{3,}")


def detect_columns(df: pd.DataFrame) -> tuple[str | None, str | None]:
    """Best-effort detection of (id_column, text_column) for a notes frame."""
    cols = list(df.columns)
    id_col = next((c for c in _ID_CANDIDATES if c in cols), None)
    text_col = next((c for c in _TEXT_CANDIDATES if c in cols), None)
    if text_col is None:  # fall back to the widest object column
        widths = {
            c: df[c].astype(str).str.len().mean()
            for c in cols
            if df[c].dtype == object
        }
        text_col = max(widths, key=widths.get) if widths else None
    return id_col, text_col


def clean_text(text: str) -> str:
    """Collapse whitespace and trim. Keeps clinical content intact."""
    if not isinstance(text, str):
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WS.sub(" ", text)
    text = _MULTINL.sub("\n\n", text)
    return text.strip()


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Return a tidy notes frame with ``note_id`` and cleaned ``text`` columns.

    Carries through ``site`` and ``__source_file`` if present.
    """
    id_col, text_col = detect_columns(df)
    if text_col is None:
        raise ValueError(f"Could not find a note-text column in: {list(df.columns)}")
    out = pd.DataFrame()
    out["note_id"] = df[id_col] if id_col else range(len(df))
    out["text"] = df[text_col].map(clean_text)
    for extra in ("site", "__source_file"):
        if extra in df.columns:
            out[extra] = df[extra].values
    return out[out["text"].str.len() > 0].reset_index(drop=True)


def chunk(text: str, size: int = 1200, overlap: int = 150) -> list[str]:
    """Split a long note into overlapping character windows for retrieval.

    Tries to break on paragraph/sentence boundaries near the window edge.
    """
    text = text.strip()
    if len(text) <= size:
        return [text] if text else []
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            window = text[start:end]
            brk = max(window.rfind("\n\n"), window.rfind(". "), window.rfind("\n"))
            if brk > size * 0.5:
                end = start + brk + 1
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = end - overlap
    return [c for c in chunks if c]
