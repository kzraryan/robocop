"""Data discovery and loading for the NICU cohort.

Designed to be robust to the messy reality of the data tree: file names vary
between sites and the data guide isn't always exact. So we *discover* files at
runtime (glob / listdir) instead of trusting hard-coded names, and load them
with pandas.

Typical use::

    from robocop import data
    data.inventory("MU")                 # what's actually on disk
    enc = data.load("MU", "ENCOUNTER")   # fuzzy-find ENCOUNTER*.csv and read it
    notes = data.load_notes("Iowa")      # concat the site's free-text notes
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from .config import COHORT, SITES, nicu_paths, site_root


# --- Discovery ----------------------------------------------------------------
def list_files(directory: str | Path, pattern: str = "*.csv") -> list[Path]:
    """Recursively list files matching ``pattern`` under ``directory``."""
    d = Path(directory)
    if not d.exists():
        return []
    return sorted(p for p in d.rglob(pattern) if p.is_file())


def inventory(site: str) -> pd.DataFrame:
    """Return a DataFrame of every CSV/XLSX under a site's NICU tree.

    Columns: path, name, dir, size_mb. Useful as the very first thing you run to
    see what's actually available (names here win over the data guide).
    """
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


def find(site: str, name_contains: str, pattern: str = "*.csv") -> list[Path]:
    """Find files in a site's tree whose name contains ``name_contains`` (ci)."""
    needle = name_contains.lower()
    return [p for p in list_files(site_root(site), pattern) if needle in p.name.lower()]


# --- Loading ------------------------------------------------------------------
def read_csv(path: str | Path, **kwargs) -> pd.DataFrame:
    """Read a CSV with hackathon-friendly defaults (everything as string unless
    told otherwise, so IDs/codes don't get mangled into floats)."""
    kwargs.setdefault("dtype", str)
    kwargs.setdefault("low_memory", False)
    return pd.read_csv(path, **kwargs)


def load(site: str, name_contains: str, **kwargs) -> pd.DataFrame:
    """Fuzzy-find a single table in a site's tree and read it.

    Raises if zero or multiple files match, so you fail loudly rather than
    silently grabbing the wrong file.
    """
    matches = find(site, name_contains)
    if not matches:
        raise FileNotFoundError(
            f"No CSV containing {name_contains!r} under {site_root(site)}. "
            f"Run robocop.data.inventory('{site}') to see what's there."
        )
    if len(matches) > 1:
        names = "\n  ".join(str(m) for m in matches)
        raise ValueError(
            f"{len(matches)} files match {name_contains!r}; be more specific:\n  {names}"
        )
    return read_csv(matches[0], **kwargs)


def load_glob(directory: str | Path, pattern: str = "*.csv", **kwargs) -> pd.DataFrame:
    """Read and concatenate every file matching ``pattern`` under ``directory``.

    Adds a ``__source_file`` column so you can trace rows back to their file.
    """
    files = list_files(directory, pattern)
    if not files:
        return pd.DataFrame()
    frames = []
    for f in files:
        df = read_csv(f, **kwargs)
        df["__source_file"] = f.name
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def load_notes(site: str, **kwargs) -> pd.DataFrame:
    """Load a site's free-text NICU clinical notes (concatenated).

    Note tables use two columns (NOTE_ID, NOTE / DEID_NOTE_RELEASE). The notes
    were split across many files to keep sizes manageable; we stitch them back.
    """
    paths = nicu_paths(site)
    if "notes_dir" in paths:                      # MU: directory of CSVs
        return load_glob(paths["notes_dir"], **kwargs)
    if "notes_glob" in paths:                     # UIC / Iowa: glob
        glob = paths["notes_glob"]
        base = Path(glob).parent
        # rglob from site root using the trailing pattern
        files = [p for p in list_files(paths["_root"]) if p.match(Path(glob).name)]
        if not files:  # fall back to a broader search
            files = [p for p in list_files(paths["_root"]) if "note" in p.name.lower()
                     or "deliver" in p.name.lower() or "redact" in p.name.lower()]
        frames = []
        for f in files:
            df = read_csv(f, **kwargs)
            df["__source_file"] = f.name
            frames.append(df)
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    raise KeyError(f"No notes location configured for site {site!r}")


def load_all_notes(sites: Iterable[str] = SITES, **kwargs) -> pd.DataFrame:
    """Concatenate notes across sites, tagging each row with its ``site``."""
    frames = []
    for s in sites:
        try:
            df = load_notes(s, **kwargs)
        except (FileNotFoundError, KeyError):
            continue
        if len(df):
            df["site"] = s
            frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
