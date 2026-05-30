"""NLP Extraction: a fast NICU-vocabulary regex tagger over a note, plus an
optional LLM extractor that returns structured JSON entities."""

from __future__ import annotations

import pandas as pd
import streamlit as st

import services
from robocop import llm, nicu_vocab
from ._ui import entity_html, need_con


def render():
    st.header("NLP Extraction")
    st.caption("Tag NICU entities in a note — fast regex vocabulary, or an LLM.")
    con = services.get_con()
    if not need_con(con):
        return
    fb = services.get_features()

    patid = st.selectbox("Infant", list(fb.features.index))
    notes = con.execute(
        "SELECT NOTEID, NOTE_DATE, PROVIDER_TYPE, NOTE_TEXT FROM mu_nicu.NOTE "
        "WHERE PATID = ? ORDER BY NOTE_DATE", [patid],
    ).fetchdf()
    if notes.empty:
        st.info("No notes for this infant.")
        return
    nrow = st.selectbox(
        "Note", range(len(notes)),
        format_func=lambda i: f"{notes.iloc[i]['NOTE_DATE']} · {notes.iloc[i]['PROVIDER_TYPE']}",
    )
    note = notes.iloc[nrow]["NOTE_TEXT"]

    tab_regex, tab_llm = st.tabs(["Regex vocabulary", "LLM extractor"])
    with tab_regex:
        ents = nicu_vocab.extract_entities(note)
        left, right = st.columns([3, 2])
        with left:
            st.markdown(
                f"<div style='padding:1em;background:#fafafa;border:1px solid #eee;"
                f"border-radius:6px'>{entity_html(note, ents)}</div>",
                unsafe_allow_html=True,
            )
        with right:
            st.dataframe(
                pd.DataFrame(ents)[["mention", "canonical"]] if ents else pd.DataFrame(),
                hide_index=True, use_container_width=True, height=380,
            )

    with tab_llm:
        if not services.chat_models():
            st.error("No Ollama chat model available.")
            return
        model = st.selectbox("Chat model", services.chat_models())
        if st.button("Extract via LLM", type="primary"):
            with st.spinner(f"Querying {model}…"):
                try:
                    parsed = llm.extract_entities_llm(note, model=model)
                    if parsed:
                        st.dataframe(pd.DataFrame(parsed), hide_index=True,
                                     use_container_width=True)
                    else:
                        st.warning("Could not parse structured output.")
                except Exception as e:  # noqa: BLE001
                    st.error(f"Failed: {e}")
