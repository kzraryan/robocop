"""robocop demo — NICU clinical-notes explorer + local-LLM Q&A.

A starting point for the pitch demo. Run on the server:

    streamlit run app/streamlit_app.py --server.port 8501

Tabs:
  1. Inventory — what data is on disk per site
  2. Notes search — semantic / keyword / hybrid retrieval over notes
  3. Ask the notes — retrieval-augmented Q&A using a local Ollama model

Keep PHI on the server; never screenshot raw note text into a public deck.
"""

from __future__ import annotations

import streamlit as st

from robocop import SITES, data, llm, notes, rag
from robocop.config import DATA_ROOT, DEFAULT_CHAT_MODEL

st.set_page_config(page_title="robocop · CAIDF NICU", layout="wide")
st.title("robocop — CAIDF NICU explorer")
st.caption(f"Data root: `{DATA_ROOT}` · cohort: NICU · sites: {', '.join(SITES)}")


@st.cache_resource(show_spinner="Loading & indexing notes…")
def build_index(site: str, max_notes: int):
    df = data.load_notes(site)
    if not len(df):
        return None, None
    ndf = notes.normalize(df).head(max_notes)
    # chunk long notes so retrieval is granular
    chunks, meta = [], []
    for rec in ndf.to_dict("records"):
        for c in notes.chunk(rec["text"]):
            chunks.append(c)
            meta.append({"note_id": rec.get("note_id"), "source": rec.get("__source_file")})
    index = rag.NoteIndex.build(chunks, metadata=meta)
    return index, ndf


tab_inv, tab_search, tab_ask = st.tabs(["Inventory", "Notes search", "Ask the notes"])

with tab_inv:
    site = st.selectbox("Site", SITES, key="inv_site")
    inv = data.inventory(site)
    st.write(f"**{len(inv)}** files · **{inv['size_mb'].sum():.1f} MB**" if len(inv) else "No files found.")
    st.dataframe(inv, use_container_width=True, height=420)

with tab_search:
    c1, c2, c3 = st.columns([2, 1, 1])
    site = c1.selectbox("Site", SITES, key="search_site")
    mode = c2.selectbox("Mode", ["hybrid", "semantic", "keyword"])
    max_notes = c3.number_input("Max notes to index", 100, 20000, 2000, step=100)
    query = st.text_input("Search the notes", "apnea of prematurity")
    if st.button("Search", type="primary") and query:
        index, _ = build_index(site, int(max_notes))
        if index is None:
            st.warning("No notes loaded for this site.")
        else:
            fn = {"hybrid": index.search_hybrid, "semantic": index.search,
                  "keyword": index.search_bm25}[mode]
            for hit in fn(query, k=8):
                with st.expander(f"score={hit['score']:.3f} · note {hit['metadata'].get('note_id')}"):
                    st.write(hit["text"])

with tab_ask:
    c1, c2 = st.columns([2, 1])
    site = c1.selectbox("Site", SITES, key="ask_site")
    model = c2.text_input("Ollama model", DEFAULT_CHAT_MODEL)
    question = st.text_area("Question about the NICU notes", "What are common reasons for caffeine therapy?")
    if st.button("Answer", type="primary") and question:
        index, _ = build_index(site, 2000)
        if index is None:
            st.warning("No notes loaded for this site.")
        else:
            hits = index.search_hybrid(question, k=6)
            context = "\n\n---\n\n".join(h["text"] for h in hits)
            prompt = (
                "You are a careful clinical NLP assistant. Answer ONLY from the "
                "context below; if it isn't there, say so. Cite note ids.\n\n"
                f"Context:\n{context}\n\nQuestion: {question}"
            )
            with st.spinner(f"Asking {model}…"):
                st.markdown(llm.chat(prompt, model=model))
            with st.expander("Retrieved context"):
                for h in hits:
                    st.caption(f"note {h['metadata'].get('note_id')} · {h['score']:.3f}")
                    st.text(h["text"][:800])
