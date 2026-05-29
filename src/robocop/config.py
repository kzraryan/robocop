"""Configuration: data locations for the NICU cohort across the three sites.

The hackathon data lives on the server under ``CAIDF_DATA_ROOT`` (default
``/media/data/caidf_data``). Override with an environment variable if you mount
it elsewhere, e.g. ``export CAIDF_DATA_ROOT=/some/other/path``.

Exact file names occasionally differ from the data guide (spelling, date
suffixes, "multiple files" directories). Treat the entries below as a *map of
where to look*; use :mod:`robocop.data` to discover the actual files at runtime
rather than assuming a name exists.
"""

from __future__ import annotations

import os
from pathlib import Path

# --- Root ---------------------------------------------------------------------
DATA_ROOT = Path(os.environ.get("CAIDF_DATA_ROOT", "/media/data/caidf_data"))

COHORT = "NICU"  # this project's assigned focus
SITES = ("MU", "UIC", "Iowa")


def site_root(site: str) -> Path:
    """Top of a site's NICU tree, e.g. /media/data/caidf_data/MU/NICU."""
    return DATA_ROOT / site / COHORT


# --- Per-site NICU layout -----------------------------------------------------
# Values are paths *relative to* ``site_root(site)``. A trailing-glob entry means
# "directory of many files"; resolve with robocop.data.list_files().
NICU_LAYOUT: dict[str, dict[str, str]] = {
    "MU": {
        # structured "v1" + cohort-level event/provider/metadata tables
        "events": "NICU_EVENTS.csv",
        "providers": "NICU_PROVIDERS.csv",
        "note_metadata": "NICU_NOTE_METADATA.csv",
        "structured_dir": "STRUCTURED_DATA_V1",          # ENCOUNTER, CONDITION,
        # DEMOGRAPHIC, DIAGNOSIS, LAB_RESULT_CM, PRESCRIBING, PROCEDURES, VITAL,
        # OBS_CLIN_NICU_ENTERAL_GI, OBS_CLIN_NICU_PAIN_SCORES, OBS_CLIN_NICU_VENT
        "notes_dir": "2024-11-20",                        # many CSVs: NOTE_ID, NOTE
    },
    "UIC": {
        "notes_glob": "*Deliverable*/**/delivery_*.csv",  # nested deliverable dir
        "structured_dir": "arpa_h_nicu_structured_deid",  # arpa_h_nicu_*_deid.csv
    },
    "Iowa": {
        "notes_glob": "redacted_notes/*REDACTED*.csv",
        "structured_glob": "*_date_shifted.csv",          # demographics, diagnoses,
        # encounters, labs, MAR, vitals, newborn info, problem list, procedures,
        # head circumference, patient journey, discharged meds, ruca_drop_zip ...
        "careplans_dir": "CarePlans",                     # Goals/Intervention/Problem
        "flowsheets_dir": "Flowsheets",                   # many *_dropped_comment.csv
        "ldas_dir": "LDAs",                               # nicu_LDAs_*.csv
    },
}


def nicu_paths(site: str) -> dict[str, Path]:
    """Resolve the layout for ``site`` into absolute paths/globs.

    Returns a dict mapping logical name -> absolute Path (for a file/dir) or an
    absolute glob string (keys ending in ``_glob``).
    """
    if site not in NICU_LAYOUT:
        raise KeyError(f"Unknown site {site!r}; expected one of {SITES}")
    root = site_root(site)
    out: dict[str, Path] = {}
    for key, rel in NICU_LAYOUT[site].items():
        out[key] = str(root / rel) if key.endswith("_glob") else root / rel
    out["_root"] = root
    return out


# --- Ollama / model defaults --------------------------------------------------
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

# Sensible defaults from the models pulled on the server. Override per call.
DEFAULT_CHAT_MODEL = os.environ.get("ROBOCOP_CHAT_MODEL", "gemma3:27b")
DEFAULT_CODE_MODEL = os.environ.get("ROBOCOP_CODE_MODEL", "qwen2.5-coder:32b")
DEFAULT_EMBED_MODEL = os.environ.get("ROBOCOP_EMBED_MODEL", "mxbai-embed-large")
# Sentence-transformers fallback for embeddings (runs on the A100):
DEFAULT_ST_EMBED_MODEL = os.environ.get(
    "ROBOCOP_ST_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)
