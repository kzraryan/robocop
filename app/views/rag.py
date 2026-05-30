"""RAG Q&A grounded in the cohort's clinical notes. Retrieve the most relevant
note chunks via FAISS, then have a local Ollama model answer, citing patient IDs
and note dates."""

from __future__ import annotations

import streamlit as st

import services
from robocop import llm
from ._ui import need_con


def render():
    st.header("RAG Q&A over Clinical Notes")
    st.caption("Retrieve relevant notes, then answer with a local LLM that cites "
               "patient IDs and dates. Optionally scope to one infant.")
    con = services.get_con()
    if not need_con(con):
        return
    idx = services.get_index()
    if idx is None:
        st.warning("Note index not built. Run `python scripts/build_index.py` (needs Ollama).")
        return
    if not services.chat_models():
        st.error("No Ollama chat model available.")
        return
    fb = services.get_features()

    question = st.text_input(
        "Question",
        value="Which infants had a sepsis work-up and what was started empirically?",
    )
    c1, c2, c3 = st.columns([2, 2, 1])
    pats = ["(any)"] + (list(fb.features.index) if fb is not None else [])
    patid_sel = c1.selectbox("Scope to infant", pats)
    model = c2.selectbox("Chat model", services.chat_models(),
                         index=_default_idx(services.chat_models(), services.default_chat()))
    k = c3.slider("Top-k notes", 2, 12, 6)

    if not (question and st.button("Ask", type="primary")):
        return
    patid = None if patid_sel == "(any)" else patid_sel
    with st.spinner("Retrieving notes…"):
        hits = idx.search(question, patid=patid, k=k)
    if not hits:
        st.info("No relevant notes found.")
        return

    st.subheader("Retrieved context")
    contexts = []
    for h in hits:
        contexts.append({"patid": h.patid, "note_date": h.note_date,
                         "provider_type": h.provider_type, "text": h.text})
        with st.expander(f"{h.patid} · {h.note_date} · {h.provider_type} · {h.score:.3f}"):
            st.write(h.text)

    st.subheader("Answer")
    messages = llm.rag_messages(question, contexts)
    try:
        st.write_stream(llm.chat_stream(messages, model=model))
    except Exception as e:  # noqa: BLE001
        st.error(f"Generation failed: {e}")
    cited = sorted({h.patid for h in hits})
    st.caption(f"Grounded in infants: {', '.join(cited)}")


def _default_idx(options, default):
    return options.index(default) if default in options else 0
