"""Robocop — MU NICU Data Viewer.

Two tabs:
  1. Query data  — natural language -> local LLM writes DuckDB SQL -> run/edit.
  2. Search notes — semantic search over MU clinical notes with a timeline,
     matched-section highlighting, and full-note expansion.

Run:  streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from robocop import config, ingest, text2sql  # noqa: E402
from robocop.text2sql import SQLValidationError  # noqa: E402

st.set_page_config(page_title="Robocop — MU NICU Viewer", layout="wide")


# --- cached resources -----------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_con():
    if not config.DUCKDB_PATH.exists():
        return None
    return ingest.connect(config.DUCKDB_PATH, read_only=True)


@st.cache_resource(show_spinner=False)
def get_index():
    try:
        from robocop.notes_index import NotesIndex
        return NotesIndex.load()
    except Exception:  # noqa: BLE001 - index may not be built yet
        return None


def full_note_text(con, noteid: str) -> str:
    row = con.execute(
        "SELECT NOTE_TEXT FROM mu_nicu.NOTE WHERE NOTEID = ?", [noteid]
    ).fetchone()
    return row[0] if row else ""


def highlight(text: str, start: int, end: int) -> str:
    """Return HTML with the [start:end] span highlighted."""
    pre, mid, post = text[:start], text[start:end], text[end:]
    return (
        f"<div style='white-space:pre-wrap;font-family:monospace;font-size:0.85rem'>"
        f"{html.escape(pre)}"
        f"<mark style='background:#ffe08a'>{html.escape(mid)}</mark>"
        f"{html.escape(post)}</div>"
    )


# --- sidebar --------------------------------------------------------------
st.sidebar.title("🤖 Robocop")
st.sidebar.caption("MU NICU data viewer — text-to-SQL + note search")
st.sidebar.write(f"**Coder model:** `{config.CODER_MODEL}`")
st.sidebar.write(f"**Embed model:** `{config.EMBED_MODEL}`")
st.sidebar.write(f"**Ollama:** `{config.OLLAMA_HOST}`")
con = get_con()
if con is None:
    st.sidebar.error("DuckDB not found. Run `python scripts/build_index.py` first.")
else:
    st.sidebar.success("DuckDB connected.")

tab_sql, tab_notes = st.tabs(["🔎 Query data", "📝 Search notes"])

# === Tab 1: text-to-SQL ===================================================
with tab_sql:
    st.subheader("Ask the data a question")
    st.caption(
        "Describe what you want; the local coding LLM writes a DuckDB SQL query "
        "grounded in the column descriptions. Edit the SQL and re-run as needed."
    )
    st.session_state.setdefault("sql_text", "")
    prompt = st.text_input(
        "Prompt",
        placeholder="e.g. infants born before 28 weeks who received caffeine",
        key="sql_prompt",
    )
    col_a, col_b = st.columns([1, 1])
    if col_a.button("✨ Generate SQL", use_container_width=True, disabled=not prompt):
        try:
            with st.spinner("Asking the coding model…"):
                # safe to set before the widget is instantiated this run
                st.session_state["sql_text"] = text2sql.generate_sql(prompt)
        except Exception as e:  # noqa: BLE001
            st.error(f"Generation failed: {e}")

    # key-bound widget reads/writes st.session_state["sql_text"] directly
    st.text_area("SQL (editable)", height=180, key="sql_text")
    sql_text = st.session_state["sql_text"]
    run = col_b.button("▶ Run query", use_container_width=True, disabled=not sql_text)

    if run and con is not None:
        try:
            res = text2sql.run_sql(sql_text, con)
            st.success(f"{res.row_count} row(s)")
            st.dataframe(res.df, use_container_width=True, height=360)
            st.download_button(
                "Download CSV",
                res.df.to_csv(index=False).encode(),
                file_name="robocop_results.csv",
            )
            # Offer PATIDs to the notes tab.
            if "PATID" in res.df.columns:
                pats = sorted(res.df["PATID"].dropna().astype(str).unique().tolist())
                st.session_state["cohort_patids"] = pats
                st.caption(f"{len(pats)} patient(s) in result → available in the notes tab.")
        except SQLValidationError as e:
            st.error(f"Blocked unsafe SQL: {e}")
        except Exception as e:  # noqa: BLE001
            st.error(f"Query error: {e}")

# === Tab 2: note semantic search ==========================================
with tab_notes:
    st.subheader("Semantic search across MU clinical notes")
    idx = get_index()
    if idx is None:
        st.warning(
            "Note index not found. Run `python scripts/build_index.py` "
            "(requires Ollama) to build embeddings."
        )
    else:
        query = st.text_input(
            "Search notes",
            placeholder="e.g. feeding intolerance and abdominal distension",
            key="note_query",
        )
        c1, c2, c3 = st.columns([2, 2, 1])
        cohort = st.session_state.get("cohort_patids", [])
        patid_opts = ["(any)"] + cohort
        patid_sel = c1.selectbox("Patient (from query tab)", patid_opts)
        providers = c2.multiselect("Provider", ["MD", "RN", "OT", "PT", "SLP"])
        topk = c3.number_input("Top K", min_value=5, max_value=100, value=20, step=5)

        if st.button("🔍 Search", disabled=not query):
            patid = None if patid_sel == "(any)" else patid_sel
            try:
                with st.spinner("Embedding + searching…"):
                    hits = idx.search(query, patid=patid, providers=providers or None, k=int(topk))
            except Exception as e:  # noqa: BLE001
                st.error(f"Search failed: {e}")
                hits = []

            if not hits:
                st.info("No matches.")
            else:
                hit_df = pd.DataFrame([h.as_dict() for h in hits])
                hit_df["date"] = pd.to_datetime(hit_df["note_date"], errors="coerce")
                hit_df = hit_df.sort_values("date")

                # Timeline
                st.markdown("**Timeline of matching notes**")
                try:
                    import plotly.express as px
                    fig = px.scatter(
                        hit_df, x="date", y="provider_type", color="score",
                        hover_data=["patid", "noteid"], color_continuous_scale="YlOrRd",
                    )
                    fig.update_layout(height=240, margin=dict(l=10, r=10, t=10, b=10))
                    st.plotly_chart(fig, use_container_width=True)
                except Exception:  # noqa: BLE001 - plotly optional
                    st.line_chart(hit_df.set_index("date")["score"])

                st.markdown("**Matches** (most recent last) — click to expand")
                for h in hit_df.sort_values("date").itertuples(index=False):
                    label = f"{h.note_date} · {h.provider_type} · {h.patid} · score {h.score:.3f}"
                    with st.expander(label):
                        st.markdown("**Matched section:**")
                        st.markdown(
                            highlight(h.text, 0, len(h.text)), unsafe_allow_html=True
                        )
                        if con is not None and st.checkbox(
                            "Show full note", key=f"full_{h.noteid}_{h.start}"
                        ):
                            note = full_note_text(con, h.noteid)
                            st.markdown(
                                highlight(note, h.start, h.end), unsafe_allow_html=True
                            )
