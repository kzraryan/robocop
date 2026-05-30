"""Robocop — NICU Patient Similarity & Cohort Intelligence.

A local clinical-intelligence dashboard over the MU NICU dataset, powered by
DuckDB + FAISS + Ollama. Pages:

  • Cohort Overview     — demographics, GA/LOS distributions, top dx/meds/procs
  • Patient Timeline    — every event for one infant on a day-of-life axis
  • Patient Similarity  — find similar infants (structured + note embeddings)
  • Note Search         — semantic search over notes with a timeline + highlight
  • Ask the Data        — natural language -> DuckDB SQL (+ SQL console)
  • Phenotype Graph     — patient-diagnosis graph + phenotype communities
  • Risk Prediction     — LightGBM prolonged-stay risk + SHAP
  • RAG Q&A             — note-grounded answers citing patients/dates
  • NLP Extraction      — NICU regex tagger + LLM entity extraction
  • System & Health     — DuckDB / index / Ollama status

Run:  streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Make both `app/` (for `services`, `views`) and `src/` importable.
APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR))
sys.path.insert(0, str(APP_DIR.parent / "src"))

st.set_page_config(
    page_title="Robocop — NICU Intelligence",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

import services  # noqa: E402
from views import (  # noqa: E402
    extraction, graph, notes, overview, patient_timeline, query, rag, risk,
    similarity, system,
)
from views._ui import inject_css, status_row  # noqa: E402


def _sidebar_status() -> None:
    """Live backend status, rendered below the navigation."""
    con = services.get_con()
    idx = services.get_index()
    models = services.ollama_models()

    st.sidebar.markdown("###### System status")
    with st.sidebar:
        status_row("DuckDB", con is not None,
                   "connected" if con is not None else "missing")
        status_row("Note index", idx is not None,
                   f"{idx.index.ntotal:,} chunks" if idx is not None else "not built")
        status_row("Ollama", bool(models),
                   f"{len(models)} models" if models else "offline")

    st.sidebar.divider()
    st.sidebar.caption(
        f"chat&nbsp;·&nbsp;`{services.default_chat()}`  \n"
        f"embed&nbsp;·&nbsp;`{services.default_embed()}`",
        unsafe_allow_html=True,
    )

    # Version marker (bottom-left): the short git hash should match the latest
    # commit on your branch — if not, the app is on stale code (pull + restart).
    from robocop.version import version_label  # noqa: E402
    st.sidebar.markdown(
        f"<div class='rc-version'>{version_label()}</div>",
        unsafe_allow_html=True,
    )


def main() -> None:
    inject_css()

    nav = st.navigation({
        "Patient Analytics": [
            st.Page(overview.render, title="Cohort Overview",
                    icon=":material/groups:", url_path="overview", default=True),
            st.Page(patient_timeline.render, title="Patient Timeline",
                    icon=":material/timeline:", url_path="timeline"),
            st.Page(similarity.render, title="Patient Similarity",
                    icon=":material/hub:", url_path="similarity"),
        ],
        "Notes & Language": [
            st.Page(notes.render, title="Note Search",
                    icon=":material/search:", url_path="notes"),
            st.Page(rag.render, title="RAG Q&A",
                    icon=":material/forum:", url_path="rag"),
            st.Page(extraction.render, title="NLP Extraction",
                    icon=":material/label:", url_path="extraction"),
        ],
        "Analytics": [
            st.Page(query.render, title="Ask the Data",
                    icon=":material/database:", url_path="ask"),
            st.Page(graph.render, title="Phenotype Graph",
                    icon=":material/share:", url_path="graph"),
            st.Page(risk.render, title="Risk Prediction",
                    icon=":material/warning:", url_path="risk"),
        ],
        "System": [
            st.Page(system.render, title="System & Health",
                    icon=":material/monitor_heart:", url_path="system"),
        ],
    })

    _sidebar_status()
    nav.run()


if __name__ == "__main__":
    main()
