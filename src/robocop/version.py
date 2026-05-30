"""Build/version identity for the app, derived from git at runtime.

The point is a *sync check*: the short commit hash shown in the UI should match
the latest commit on your branch. If they differ, the running app is on stale
code (pull + restart Streamlit). Falls back gracefully when git is unavailable.
"""

from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(_REPO), *args],
            capture_output=True, text=True, timeout=2,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:  # noqa: BLE001 - git missing / not a repo / timeout
        return None
    return None


@lru_cache(maxsize=1)
def build_info() -> dict[str, str]:
    """Return short hash, commit date, and a dirty flag for the working tree."""
    sha = _git("rev-parse", "--short=8", "HEAD") or "unknown"
    date = _git("show", "-s", "--format=%cd", "--date=format:%Y-%m-%d %H:%M", "HEAD") or ""
    status = _git("status", "--porcelain")
    dirty = bool(status)  # uncommitted local changes present
    return {"sha": sha, "date": date, "dirty": "+" if dirty else ""}


def version_label() -> str:
    """Compact one-line label, e.g. 'build b6a793f · 2026-05-30 18:42'."""
    info = build_info()
    label = f"build {info['sha']}{info['dirty']}"
    if info["date"]:
        label += f" · {info['date']}"
    return label
