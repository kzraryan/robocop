"""Central configuration. Everything is overridable via environment variables so
the same code runs in the hackathon env (Ollama + A100) and elsewhere."""

from __future__ import annotations

import os
from pathlib import Path

# --- Paths ----------------------------------------------------------------
# Repo root = two levels up from this file (src/robocop/config.py).
ROOT = Path(__file__).resolve().parents[2]


def _path(env: str, default: Path) -> Path:
    return Path(os.environ.get(env, str(default)))


DATA_DIR: Path = _path("ROBOCOP_DATA_DIR", ROOT / "data")
RAW_DIR: Path = _path("ROBOCOP_RAW_DIR", DATA_DIR / "raw")

# --- Real MU NICU data on the hackathon server ----------------------------
# Root of the real, de-identified MU NICU drop. Overridable for other mounts.
REAL_DIR: Path = _path("ROBOCOP_REAL_DIR", Path("/media/data/caidf_data/MU/NICU"))
STRUCTURED_SUBDIR: str = os.environ.get("ROBOCOP_STRUCTURED_SUBDIR", "STRUCTURED_DATA_V1")
NOTES_SUBDIR: str = os.environ.get("ROBOCOP_NOTES_SUBDIR", "2024-11-20")
# Metadata files (at REAL_DIR root) used to recover per-note PATID/date/provider.
NOTE_METADATA_FILES: tuple[str, ...] = (
    "NICU_NOTE_METADATA.csv", "NICU_EVENTS.csv", "NICU_PROVIDERS.csv",
)
# Optional hard overrides for note-column auto-detection (set when inspect_data.py
# reveals the real headers). Empty string => auto-detect.
NOTE_COL_OVERRIDES: dict[str, str] = {
    "noteid": os.environ.get("ROBOCOP_NOTE_ID_COL", ""),
    "text": os.environ.get("ROBOCOP_NOTE_TEXT_COL", ""),
    "patid": os.environ.get("ROBOCOP_NOTE_PATID_COL", ""),
    "date": os.environ.get("ROBOCOP_NOTE_DATE_COL", ""),
    "provider": os.environ.get("ROBOCOP_NOTE_PROVIDER_COL", ""),
    "encounter": os.environ.get("ROBOCOP_NOTE_ENC_COL", ""),
}

# Null sentinels seen in numeric/text columns across the real data. Includes the
# documented '/n','//n','//N','/N' plus the classic '\N' and stray markers.
NULL_SENTINELS: frozenset[str] = frozenset(
    {"/n", "//n", "//N", "/N", "\\N", "\\n", "\\\\N", "N", "NA", "N/A",
     "NULL", "null", "None", "NaN", "nan", "", "."}
)
DUCKDB_PATH: Path = _path("ROBOCOP_DUCKDB", DATA_DIR / "mu.duckdb")
FAISS_DIR: Path = _path("ROBOCOP_FAISS_DIR", DATA_DIR / "faiss")
CACHE_DIR: Path = _path("ROBOCOP_CACHE_DIR", DATA_DIR / "cache")
SCHEMA_DOC: Path = _path(
    "ROBOCOP_SCHEMA_DOC", ROOT / "resources" / "column_descriptions.txt"
)

# --- Ollama / models ------------------------------------------------------
OLLAMA_HOST: str = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
# Newest Qwen coder available on the hackathon box; fits A100 80GB.
# Fallbacks: qwen3-coder-next:latest, qwen2.5-coder:{32b,14b,7b}
CODER_MODEL: str = os.environ.get("ROBOCOP_CODER_MODEL", "qwen3-coder:30b")
EMBED_MODEL: str = os.environ.get("ROBOCOP_EMBED_MODEL", "mxbai-embed-large")

# --- Misc -----------------------------------------------------------------
DEFAULT_SQL_LIMIT: int = int(os.environ.get("ROBOCOP_SQL_LIMIT", "200"))
# Site / cohort we restrict to. Synthetic data is already MU NICU only; this
# layer exists so real multi-site data can be narrowed identically.
SITE: str = os.environ.get("ROBOCOP_SITE", "MU")
COHORT: str = os.environ.get("ROBOCOP_COHORT", "NICU")

# Note chunking
CHUNK_SIZE: int = int(os.environ.get("ROBOCOP_CHUNK_SIZE", "500"))
CHUNK_OVERLAP: int = int(os.environ.get("ROBOCOP_CHUNK_OVERLAP", "80"))


def ensure_dirs() -> None:
    for p in (DATA_DIR, RAW_DIR, FAISS_DIR, CACHE_DIR):
        p.mkdir(parents=True, exist_ok=True)
