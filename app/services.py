"""Shared, cached resources for the Streamlit app. Heavy objects (DuckDB
connection, note index, feature table, similarity engine, phenotype graph, risk
model) are built once and reused across pages."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from robocop import (  # noqa: E402
    config, features, ingest, llm, phenotype, risk, similarity,
)

EMBED_HINTS = ("mxbai-embed-large", "nomic-embed-text", "all-minilm")
CHAT_HINTS = ("qwen3-coder", "qwen2.5-coder", "llama3.1:8b", "llama3.2", "mistral")


@st.cache_resource(show_spinner=False)
def get_con():
    if not config.DUCKDB_PATH.exists():
        return None
    return ingest.connect(config.DUCKDB_PATH, read_only=True)


@st.cache_data(show_spinner=False)
def patients_with_notes() -> list[str]:
    """PATIDs that actually have at least one note, ordered by note volume.

    Note pages should offer only these — most infants have no notes (notes are
    built for a focused cohort), so listing every patient is misleading."""
    con = get_con()
    if con is None:
        return []
    try:
        rows = con.execute(
            "SELECT PATID FROM mu_nicu.NOTE "
            "WHERE NOTE_TEXT IS NOT NULL AND PATID IS NOT NULL "
            "GROUP BY PATID ORDER BY count(*) DESC, PATID"
        ).fetchall()
        return [r[0] for r in rows]
    except Exception:  # noqa: BLE001
        return []


@st.cache_resource(show_spinner="Loading note index…")
def get_index():
    try:
        from robocop.notes_index import NotesIndex
        return NotesIndex.load()
    except Exception:  # noqa: BLE001 - not built yet / no embeddings
        return None


@st.cache_resource(show_spinner="Building feature table…")
def get_features():
    con = get_con()
    if con is None:
        return None
    try:
        return features.build_features(con)
    except Exception:  # noqa: BLE001
        # Surface the real file:line + running build so a failure is diagnosable
        # (and tells us at a glance whether the app is on synced code).
        import traceback
        from robocop.version import version_label
        st.error(
            f"Feature build failed — running {version_label()}.\n\n"
            "```\n" + traceback.format_exc() + "\n```"
        )
        return None


@st.cache_resource(show_spinner="Building similarity engine…")
def get_similarity():
    fb = get_features()
    if fb is None:
        return None
    centroids = None
    idx = get_index()
    if idx is not None:
        try:
            centroids = idx.patient_centroids()
        except Exception:  # noqa: BLE001
            centroids = None
    return similarity.SimilarityEngine(fb, note_centroids=centroids)


@st.cache_resource(show_spinner="Building phenotype graph…")
def get_phenotype():
    fb = get_features()
    return phenotype.build_phenotype_graph(fb) if fb is not None else None


@st.cache_resource(show_spinner="Training risk model…")
def get_risk_model():
    fb = get_features()
    return risk.train_risk_model(fb) if fb is not None else None


@st.cache_data(ttl=60, show_spinner=False)
def ollama_models() -> list[str]:
    return llm.list_models()


def is_embed(name: str) -> bool:
    n = name.lower()
    return "embed" in n or "minilm" in n


def embed_models() -> list[str]:
    return [m for m in ollama_models() if is_embed(m)]


def chat_models() -> list[str]:
    return [m for m in ollama_models() if not is_embed(m)]


def _pick(models: list[str], hints, fallback: str) -> str:
    for h in hints:
        for m in models:
            if m == h or m.startswith(h):
                return m
    return models[0] if models else fallback


def default_chat() -> str:
    return _pick(chat_models(), CHAT_HINTS, config.CODER_MODEL)


def default_embed() -> str:
    return _pick(embed_models(), EMBED_HINTS, config.EMBED_MODEL)
