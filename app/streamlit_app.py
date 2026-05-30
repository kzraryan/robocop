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

st.set_page_config(page_title="Robocop — NICU Intelligence", layout="wide",
                   initial_sidebar_state="expanded")

import services  # noqa: E402
from views import (  # noqa: E402
    extraction, graph, notes, overview, patient_timeline, query, rag, risk,
    similarity, system,
)

PAGES = {
    "🏥 Cohort Overview": overview.render,
    "📈 Patient Timeline": patient_timeline.render,
    "🧬 Patient Similarity": similarity.render,
    "📝 Note Search": notes.render,
    "🔎 Ask the Data (SQL)": query.render,
    "🕸️ Phenotype Graph": graph.render,
    "⚠️ Risk Prediction": risk.render,
    "💬 RAG Q&A": rag.render,
    "🏷️ NLP Extraction": extraction.render,
    "⚙️ System & Health": system.render,
}


def main():
    st.sidebar.title("🤖 Robocop")
    st.sidebar.caption("NICU Patient Similarity & Cohort Intelligence")
    page = st.sidebar.radio("Page", list(PAGES.keys()))
    st.sidebar.divider()

    con = services.get_con()
    idx = services.get_index()
    st.sidebar.write("**DuckDB:**", "✅" if con else "❌ (build_index.py)")
    st.sidebar.write("**Notes index:**", f"✅ {idx.index.ntotal} chunks" if idx else "❌")
    models = services.ollama_models()
    st.sidebar.write("**Ollama:**", f"✅ {len(models)} models" if models else "❌")
    st.sidebar.caption(f"chat: `{services.default_chat()}`\n\nembed: `{services.default_embed()}`")

    PAGES[page]()


if __name__ == "__main__":
    main()
