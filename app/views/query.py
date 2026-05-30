"""Ask-the-data: natural language -> local LLM writes DuckDB SQL (grounded in the
column descriptions) -> editable + run. Also a raw SQL console."""

from __future__ import annotations

import time

import streamlit as st

import services
from robocop import text2sql
from robocop.text2sql import SQLValidationError
from ._ui import need_con


def render():
    st.header("Ask the Data (text-to-SQL)")
    con = services.get_con()
    if not need_con(con):
        return

    tab_nl, tab_console = st.tabs(["Natural language → SQL", "SQL console"])

    with tab_nl:
        st.caption(
            "The local coding LLM writes a read-only DuckDB query grounded in the "
            "column descriptions. Edit and re-run as you like."
        )
        st.session_state.setdefault("q_sql", "")
        prompt = st.text_input(
            "Prompt",
            placeholder="e.g. infants under 28 weeks who received caffeine and surfactant",
        )
        c1, c2 = st.columns(2)
        model = services.default_chat()
        if c1.button("✨ Generate SQL", width="stretch", disabled=not prompt):
            try:
                with st.spinner(f"Asking {model}…"):
                    st.session_state["q_sql"] = text2sql.generate_sql(prompt, model=model)
            except Exception as e:  # noqa: BLE001
                st.error(f"Generation failed: {e}")

        st.text_area("SQL (editable)", height=170, key="q_sql")
        sql = st.session_state["q_sql"]
        if c2.button("▶ Run", width="stretch", disabled=not sql):
            _run(con, sql, allow_patid_handoff=True)

    with tab_console:
        st.caption(f"Read-only DuckDB at `{services.config.DUCKDB_PATH}` "
                   "(search_path = mu_nicu).")
        with st.expander("Tables"):
            tbls = con.execute("SELECT table_name FROM information_schema.tables "
                               "WHERE table_schema='mu_nicu' ORDER BY 1").fetchdf()
            st.dataframe(tbls, hide_index=True, width="stretch")
        sql2 = st.text_area(
            "SQL", height=140,
            value="SELECT DRG, COUNT(*) n FROM ENCOUNTER GROUP BY DRG ORDER BY n DESC",
        )
        if st.button("Run query"):
            _run(con, sql2)


def _run(con, sql, allow_patid_handoff=False):
    try:
        t0 = time.time()
        res = text2sql.run_sql(sql, con)
        dt = (time.time() - t0) * 1000
        st.success(f"{res.row_count} row(s) in {dt:.0f} ms")
        st.code(res.sql, language="sql")
        st.dataframe(res.df, width="stretch", height=360)
        st.download_button("Download CSV", res.df.to_csv(index=False).encode(),
                           file_name="robocop_query.csv")
        if allow_patid_handoff and "PATID" in res.df.columns:
            pats = sorted(res.df["PATID"].dropna().astype(str).unique())
            st.session_state["cohort_patids"] = pats
            st.caption(f"{len(pats)} infant(s) captured → available to other pages.")
    except SQLValidationError as e:
        st.error(f"Blocked unsafe SQL: {e}")
    except Exception as e:  # noqa: BLE001
        st.error(f"Query error: {e}")
