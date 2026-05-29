"""robocop — CAIDF Year 2 2026 Hackathon project (NICU cohort).

A small toolkit for working with the CAIDF de-identified clinical data on the
hackathon server: structured tables + free-text notes across the three
contributing sites (UIC, Iowa, MU), with local-LLM (Ollama) and retrieval
helpers.

Nothing in here ships data. All loaders read from ``CAIDF_DATA_ROOT`` on the
server (default ``/media/data/caidf_data``).
"""

from __future__ import annotations

__version__ = "0.1.0"

from .config import DATA_ROOT, SITES, COHORT, nicu_paths  # noqa: E402

__all__ = ["DATA_ROOT", "SITES", "COHORT", "nicu_paths", "__version__"]
