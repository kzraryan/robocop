from pathlib import Path

import pandas as pd

from .config import NOTES_GLOBS, site_root

_NOTE_HINTS = ("redact", "deliver", "note")


def list_files(directory, pattern: str = "*.csv") -> list[Path]:
    d = Path(directory)
    if not d.exists():
        return []
    return sorted(p for p in d.rglob(pattern) if p.is_file())


def inventory(site: str) -> pd.DataFrame:
    root = site_root(site)
    rows = []
    for pat in ("*.csv", "*.xlsx", "*.xls"):
        for p in list_files(root, pat):
            rows.append(
                {
                    "path": str(p),
                    "name": p.name,
                    "dir": str(p.parent.relative_to(root)) if p.parent != root else ".",
                    "size_mb": round(p.stat().st_size / 1e6, 2),
                }
            )
    df = pd.DataFrame(rows)
    return df.sort_values(["dir", "name"]).reset_index(drop=True) if len(df) else df


def note_files(site: str) -> list[Path]:
    root = site_root(site)
    files = [p for p in list_files(root) if p.match(NOTES_GLOBS[site])]
    if not files:
        files = [
            p
            for p in list_files(root)
            if any(h in str(p).lower() for h in _NOTE_HINTS)
        ]
    return files


def structured_files(site: str) -> list[Path]:
    notes = set(note_files(site))
    return [p for p in list_files(site_root(site)) if p not in notes]
