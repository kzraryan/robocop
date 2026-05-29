import os
from pathlib import Path

DATA_ROOT = Path(os.environ.get("CAIDF_DATA_ROOT", "/media/data/caidf_data"))
COHORT = "NICU"
SITES = ("MU", "UIC", "Iowa")

# Where each site keeps its free-text notes, relative to the site root.
# Everything else under a site root is treated as structured data.
NOTES_GLOBS = {
    "MU": "2024-11-20/*.csv",
    "UIC": "**/delivery_*.csv",
    "Iowa": "redacted_notes/*.csv",
}


def site_root(site: str) -> Path:
    return DATA_ROOT / site / COHORT
