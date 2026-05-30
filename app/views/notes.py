"""Note semantic search: embed the query, retrieve the most relevant note chunks
across the cohort (or one infant), show a timeline of matches, and expand each to
the matched section then the full note."""

from __future__ import annotations

import pandas as pd
import streamlit as st

import services
from ._ui import highlight, need_con


def _full_note(con, noteid):
    row = con.execute(
        "SELECT NOTE_TEXT FROM mu_nicu.NOTE WHERE NOTEID = ?", [noteid]
    ).fetchone()
    return row[0] if row else ""


def render():
    st.header("Note Semantic Search")
    st.caption("Search MU clinical notes by meaning, with a timeline of matches.")
    con = services.get_con()
    if not need_con(con):
        return
    idx = services.get_index()
    if idx is None:
        st.warning(
            "Note index not found. Run `python scripts/build_index.py` "
            "(needs Ollama) to build embeddings."
        )
        return
    fb = services.get_features()

    query = st.text_input(
        "Search", placeholder="e.g. feeding intolerance with abdominal distension",
    )
    c1, c2, c3 = st.columns([2, 2, 1])
    pats = ["(any)"] + (list(fb.features.index) if fb is not None else [])
    patid_sel = c1.selectbox("Infant", pats)
    providers = c2.multiselect("Provider", ["MD", "RN", "OT", "PT", "SLP"])
    topk = c3.number_input("Top K", 5, 100, 20, 5)

    if not (query and st.button("🔍 Search")):
        return
    patid = None if patid_sel == "(any)" else patid_sel
    try:
        hits = idx.search(query, patid=patid, providers=providers or None, k=int(topk))
    except Exception as e:  # noqa: BLE001
        st.error(f"Search failed: {e}")
        return
    if not hits:
        st.info("No matches.")
        return

    df = pd.DataFrame([h.as_dict() for h in hits])
    df["date"] = pd.to_datetime(df["note_date"], errors="coerce")
    df = df.sort_values("date")

    st.subheader("Timeline of matching notes")
    try:
        import plotly.express as px
        fig = px.scatter(df, x="date", y="provider_type", color="score",
                         hover_data=["patid", "noteid"], color_continuous_scale="YlOrRd",
                         render_mode="svg")  # avoid WebGL (scattergl)
        fig.update_layout(height=240, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, width="stretch")
    except Exception:  # noqa: BLE001
        st.line_chart(df.set_index("date")["score"])

    st.subheader("Matches")
    for h in df.itertuples(index=False):
        label = f"{h.note_date} · {h.provider_type} · {h.patid} · score {h.score:.3f}"
        with st.expander(label):
            st.markdown("**Matched section:**")
            st.markdown(highlight(h.text, 0, len(h.text)), unsafe_allow_html=True)
            if st.checkbox("Show full note", key=f"full_{h.noteid}_{h.start}"):
                st.markdown(
                    highlight(_full_note(con, h.noteid), h.start, h.end),
                    unsafe_allow_html=True,
                )
