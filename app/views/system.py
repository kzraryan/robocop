"""System & Health: confirm DuckDB, the note index, and the Ollama models the
app will use."""

from __future__ import annotations

import pandas as pd
import streamlit as st

import services
from robocop import config


def render():
    st.header("System & Health")

    con = services.get_con()
    idx = services.get_index()
    models = services.ollama_models()

    c1, c2, c3 = st.columns(3)
    c1.metric("DuckDB", "connected" if con else "missing")
    c2.metric("Note index", f"{idx.index.ntotal} chunks" if idx else "not built")
    c3.metric("Ollama models", len(models) if models else 0)

    st.subheader("Configuration")
    st.table(pd.DataFrame([
        {"setting": "OLLAMA_HOST", "value": config.OLLAMA_HOST},
        {"setting": "coder/chat model", "value": services.default_chat()},
        {"setting": "embedding model", "value": services.default_embed()},
        {"setting": "DuckDB path", "value": str(config.DUCKDB_PATH)},
        {"setting": "FAISS dir", "value": str(config.FAISS_DIR)},
    ]))

    st.subheader("Ollama models available")
    if models:
        emb = set(services.embed_models())
        st.dataframe(
            pd.DataFrame({"model": models,
                          "kind": ["embedding" if m in emb else "chat/coder" for m in models]}),
            hide_index=True, width="stretch", height=360,
        )
    else:
        st.warning(f"No models reachable at {config.OLLAMA_HOST}. "
                   "Start Ollama and pull a coder + an embedding model.")

    if con is not None:
        st.subheader("Row counts")
        from robocop.ingest import TABLES
        rows = []
        for t in TABLES:
            try:
                n = con.execute(f'SELECT COUNT(*) FROM mu_nicu."{t}"').fetchone()[0]
                rows.append({"table": t, "rows": n})
            except Exception:  # noqa: BLE001
                pass
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
